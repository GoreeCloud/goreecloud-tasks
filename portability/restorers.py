"""Full-fidelity restoration for GoreeCloud Tasks user archives.

Restoration is intentionally stricter than ordinary provider import. A user archive
contains multi-user project history, so the restore path validates the complete archive,
requires exact existing collaborator usernames, requires a clean target account-owned
Tasks data set, and reconstructs everything inside one database transaction.

No user accounts are created, no existing Tasks data is overwritten or merged, and no
archive can restore into a differently named account.
"""

from dataclasses import dataclass
from datetime import datetime

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from collaboration.models import ActivityEvent, TaskComment
from labels.models import Label
from projects.models import Project, ProjectMembership
from tasks.models import Task

from .exporters import EXPORT_FORMAT, SCHEMA_VERSION


class ArchiveRestoreError(ValueError):
    """Raised when an archive cannot be restored safely."""


@dataclass(frozen=True)
class RestoreSummary:
    projects_restored: int
    memberships_restored: int
    labels_restored: int
    tasks_restored: int
    comments_restored: int
    activity_events_restored: int


def _require_dict(value, label):
    if not isinstance(value, dict):
        raise ArchiveRestoreError(f"{label} must be a JSON object.")
    return value


def _require_list(value, label):
    if not isinstance(value, list):
        raise ArchiveRestoreError(f"{label} must be a JSON array.")
    return value


def _record_id(record, label):
    value = record.get("id")
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ArchiveRestoreError(f"Every {label} requires a positive integer id.")
    return value


def _foreign_id(record, field, *, allow_none=False):
    value = record.get(field)
    if value is None and allow_none:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ArchiveRestoreError(f"{field} must be a positive integer reference.")
    return value


def _text(record, field, *, max_length=None, allow_blank=True):
    value = record.get(field, "")
    if not isinstance(value, str):
        raise ArchiveRestoreError(f"{field} must be text.")
    if not allow_blank and not value.strip():
        raise ArchiveRestoreError(f"{field} may not be blank.")
    if max_length is not None and len(value) > max_length:
        raise ArchiveRestoreError(f"{field} may not exceed {max_length} characters.")
    return value


def _boolean(record, field):
    value = record.get(field)
    if not isinstance(value, bool):
        raise ArchiveRestoreError(f"{field} must be true or false.")
    return value


def _timestamp(record, field, *, allow_none=False):
    value = record.get(field)
    if value is None:
        if allow_none:
            return None
        raise ArchiveRestoreError(f"{field} is required.")
    if not isinstance(value, str):
        raise ArchiveRestoreError(f"{field} must be an ISO-8601 timestamp.")
    parsed = parse_datetime(value)
    if parsed is None or timezone.is_naive(parsed):
        raise ArchiveRestoreError(f"{field} must include a valid timezone offset.")
    return parsed


def _index(records, label):
    indexed = {}
    for raw in records:
        record = _require_dict(raw, f"{label} record")
        record_id = _record_id(record, label)
        if record_id in indexed:
            raise ArchiveRestoreError(f"Duplicate {label} id: {record_id}.")
        indexed[record_id] = record
    return indexed


def _validate_parent_graph(tasks):
    parent_map = {}
    for task_id, record in tasks.items():
        parent_id = record.get("parent_id")
        if parent_id is not None:
            parent_map[task_id] = parent_id

    for task_id in tasks:
        seen = set()
        current = task_id
        while current in parent_map:
            if current in seen:
                raise ArchiveRestoreError("Archived task parents may not contain a cycle.")
            seen.add(current)
            current = parent_map[current]


def _validate_clean_target(user):
    if Project.objects.filter(owner=user).exists():
        raise ArchiveRestoreError(
            "Archive restoration requires an account with no existing owned Tasks projects."
        )
    if Label.objects.filter(owner=user, project__isnull=True).exists():
        raise ArchiveRestoreError(
            "Archive restoration requires an account with no existing personal Tasks labels."
        )
    if Task.objects.filter(creator=user, project__isnull=True).exists():
        raise ArchiveRestoreError(
            "Archive restoration requires an account with no existing private personal Tasks."
        )


def validate_user_archive(payload, *, user):
    """Validate a version-1 user archive and return resolved restore state."""
    if not user or not user.is_authenticated:
        raise ArchiveRestoreError("An authenticated user is required for restoration.")

    payload = _require_dict(payload, "Archive")
    if payload.get("format") != EXPORT_FORMAT:
        raise ArchiveRestoreError("This file is not a GoreeCloud Tasks export archive.")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ArchiveRestoreError(
            f"Unsupported archive schema version. Expected {SCHEMA_VERSION}."
        )

    scope = _require_dict(payload.get("scope"), "Archive scope")
    if scope.get("kind") != "user_archive":
        raise ArchiveRestoreError(
            "Only complete user archives can be restored through this recovery workflow."
        )
    if scope.get("username") != user.username:
        raise ArchiveRestoreError(
            "The archive username must exactly match the authenticated account username."
        )
    source_owner_id = scope.get("user_id")
    if not isinstance(source_owner_id, int) or isinstance(source_owner_id, bool):
        raise ArchiveRestoreError("Archive scope user_id is invalid.")

    data = _require_dict(payload.get("data"), "Archive data")
    users = _index(_require_list(data.get("users"), "users"), "user")
    projects = _index(_require_list(data.get("projects"), "projects"), "project")
    memberships = _index(
        _require_list(data.get("memberships"), "memberships"), "membership"
    )
    labels = _index(_require_list(data.get("labels"), "labels"), "label")
    tasks = _index(_require_list(data.get("tasks"), "tasks"), "task")
    comments = _index(_require_list(data.get("comments"), "comments"), "comment")
    activity = _index(_require_list(data.get("activity"), "activity"), "activity event")

    if source_owner_id not in users:
        raise ArchiveRestoreError("The archive owner is missing from data.users.")
    owner_username = _text(
        users[source_owner_id], "username", max_length=150, allow_blank=False
    )
    if owner_username != user.username:
        raise ArchiveRestoreError("Archive owner identity does not match the archive scope.")

    usernames = {}
    for source_id, record in users.items():
        username = _text(record, "username", max_length=150, allow_blank=False)
        if username in usernames:
            raise ArchiveRestoreError(f"Duplicate archived username: {username}.")
        usernames[username] = source_id

    User = get_user_model()
    resolved_accounts = {
        account.username: account
        for account in User.objects.filter(username__in=list(usernames))
    }
    missing = sorted(set(usernames) - set(resolved_accounts))
    if missing:
        raise ArchiveRestoreError(
            "Restore requires existing accounts for archived collaborator username(s): "
            + ", ".join(missing)
            + "."
        )
    user_map = {
        source_id: resolved_accounts[record["username"]]
        for source_id, record in users.items()
    }
    if user_map[source_owner_id].pk != user.pk:
        raise ArchiveRestoreError("Archive owner resolved to a different local account.")

    valid_visibility = {value for value, _label in Project.Visibility.choices}
    project_names = set()
    for project_id, record in projects.items():
        if _foreign_id(record, "owner_id") != source_owner_id:
            raise ArchiveRestoreError(
                f"Project {project_id} is not owned by the user archive owner."
            )
        name = _text(record, "name", max_length=200, allow_blank=False).strip()
        if name in project_names:
            raise ArchiveRestoreError(f"Duplicate archived project name: {name}.")
        project_names.add(name)
        if record.get("visibility") not in valid_visibility:
            raise ArchiveRestoreError(f"Project {project_id} has invalid visibility.")
        _boolean(record, "is_archived")
        _timestamp(record, "created_at")
        _timestamp(record, "updated_at")

    valid_roles = {value for value, _label in ProjectMembership.Role.choices}
    membership_pairs = set()
    project_member_ids = {project_id: set() for project_id in projects}
    for membership_id, record in memberships.items():
        project_id = _foreign_id(record, "project_id")
        user_id = _foreign_id(record, "user_id")
        if project_id not in projects:
            raise ArchiveRestoreError(
                f"Membership {membership_id} references unknown project {project_id}."
            )
        if user_id not in users:
            raise ArchiveRestoreError(
                f"Membership {membership_id} references unknown user {user_id}."
            )
        if user_id == source_owner_id:
            raise ArchiveRestoreError("Project owners must not be duplicated as members.")
        pair = (project_id, user_id)
        if pair in membership_pairs:
            raise ArchiveRestoreError("Duplicate project membership relationship.")
        membership_pairs.add(pair)
        project_member_ids[project_id].add(user_id)
        if record.get("role") not in valid_roles:
            raise ArchiveRestoreError(f"Membership {membership_id} has invalid role.")
        _boolean(record, "is_active")
        _timestamp(record, "created_at")

    for project_id, record in projects.items():
        if record.get("visibility") == Project.Visibility.PRIVATE:
            active_members = [
                membership
                for membership in memberships.values()
                if membership.get("project_id") == project_id
                and membership.get("is_active") is True
            ]
            if active_members:
                raise ArchiveRestoreError(
                    f"Private project {project_id} cannot contain active memberships."
                )

    personal_label_names = set()
    project_label_names = set()
    for label_id, record in labels.items():
        owner_id = _foreign_id(record, "owner_id")
        if owner_id not in users:
            raise ArchiveRestoreError(f"Label {label_id} references unknown owner.")
        project_id = _foreign_id(record, "project_id", allow_none=True)
        name = _text(record, "name", max_length=100, allow_blank=False).strip()
        if project_id is None:
            if owner_id != source_owner_id:
                raise ArchiveRestoreError("Personal labels must belong to the archive owner.")
            if name in personal_label_names:
                raise ArchiveRestoreError(f"Duplicate archived personal label: {name}.")
            personal_label_names.add(name)
        else:
            if project_id not in projects:
                raise ArchiveRestoreError(
                    f"Label {label_id} references unknown project {project_id}."
                )
            if owner_id != source_owner_id and owner_id not in project_member_ids[project_id]:
                raise ArchiveRestoreError(
                    f"Label {label_id} owner is not related to its project."
                )
            key = (project_id, name)
            if key in project_label_names:
                raise ArchiveRestoreError(
                    f"Duplicate archived project label {name} in project {project_id}."
                )
            project_label_names.add(key)
        _timestamp(record, "created_at")

    valid_priorities = {value for value, _label in Task.Priority.choices}
    valid_statuses = {value for value, _label in Task.Status.choices}
    for task_id, record in tasks.items():
        creator_id = _foreign_id(record, "creator_id")
        assignee_id = _foreign_id(record, "assignee_id", allow_none=True)
        project_id = _foreign_id(record, "project_id", allow_none=True)
        parent_id = _foreign_id(record, "parent_id", allow_none=True)
        if creator_id not in users or (assignee_id is not None and assignee_id not in users):
            raise ArchiveRestoreError(f"Task {task_id} references an unknown user.")
        if project_id is not None and project_id not in projects:
            raise ArchiveRestoreError(f"Task {task_id} references unknown project.")
        if parent_id is not None and parent_id not in tasks:
            raise ArchiveRestoreError(f"Task {task_id} references unknown parent task.")
        if parent_id == task_id:
            raise ArchiveRestoreError("A task cannot be its own parent.")

        if project_id is None:
            if creator_id != source_owner_id:
                raise ArchiveRestoreError("Private tasks must belong to the archive owner.")
            if assignee_id not in {None, source_owner_id}:
                raise ArchiveRestoreError(
                    "Private tasks may only be assigned to the archive owner."
                )
        else:
            allowed_users = project_member_ids[project_id] | {source_owner_id}
            if creator_id not in allowed_users:
                raise ArchiveRestoreError(
                    f"Task {task_id} creator is unrelated to its project."
                )
            if assignee_id is not None and assignee_id not in allowed_users:
                raise ArchiveRestoreError(
                    f"Task {task_id} assignee is unrelated to its project."
                )

        _text(record, "title", max_length=500, allow_blank=False)
        _text(record, "description")
        if record.get("priority") not in valid_priorities:
            raise ArchiveRestoreError(f"Task {task_id} has invalid priority.")
        if record.get("status") not in valid_statuses:
            raise ArchiveRestoreError(f"Task {task_id} has invalid status.")
        _timestamp(record, "due_at", allow_none=True)
        completed_at = _timestamp(record, "completed_at", allow_none=True)
        if record.get("status") == Task.Status.COMPLETED and completed_at is None:
            raise ArchiveRestoreError(
                f"Completed task {task_id} is missing completed_at."
            )
        if record.get("status") != Task.Status.COMPLETED and completed_at is not None:
            raise ArchiveRestoreError(
                f"Non-completed task {task_id} unexpectedly contains completed_at."
            )

        label_ids = record.get("label_ids")
        if not isinstance(label_ids, list):
            raise ArchiveRestoreError(f"Task {task_id} label_ids must be an array.")
        for label_id in label_ids:
            if label_id not in labels:
                raise ArchiveRestoreError(
                    f"Task {task_id} references unknown label {label_id}."
                )
            if labels[label_id].get("project_id") != project_id:
                raise ArchiveRestoreError(
                    f"Task {task_id} references a label from another scope."
                )

        for field in (
            "is_goreecloud_work",
            "backup_prerequisite",
            "recovery_requirement",
            "validation_requirement",
            "documentation_requirement",
        ):
            _boolean(record, field)
        for field, max_length in (
            ("assigned_system", 200),
            ("assigned_service", 200),
            ("environment", 200),
            ("workload_category", 120),
            ("related_change_record", 500),
            ("related_documentation", 500),
        ):
            _text(record, field, max_length=max_length)
        _text(record, "blocker")
        _text(record, "resume_condition")
        _timestamp(record, "created_at")
        _timestamp(record, "updated_at")

    for task_id, record in tasks.items():
        parent_id = record.get("parent_id")
        if parent_id is not None:
            if tasks[parent_id].get("project_id") != record.get("project_id"):
                raise ArchiveRestoreError(
                    f"Task {task_id} and its parent are in different scopes."
                )
            if record.get("project_id") is None and (
                tasks[parent_id].get("creator_id") != record.get("creator_id")
            ):
                raise ArchiveRestoreError(
                    f"Private task {task_id} and its parent have different owners."
                )
    _validate_parent_graph(tasks)

    for comment_id, record in comments.items():
        task_id = _foreign_id(record, "task_id")
        author_id = _foreign_id(record, "author_id")
        if task_id not in tasks or author_id not in users:
            raise ArchiveRestoreError(f"Comment {comment_id} has an unknown reference.")
        task = tasks[task_id]
        project_id = task.get("project_id")
        if project_id is None and author_id != source_owner_id:
            raise ArchiveRestoreError("Private task comments must belong to the archive owner.")
        if project_id is not None and author_id not in (
            project_member_ids[project_id] | {source_owner_id}
        ):
            raise ArchiveRestoreError(
                f"Comment {comment_id} author is unrelated to its project."
            )
        _text(record, "body", max_length=10000, allow_blank=False)
        _timestamp(record, "created_at")
        _timestamp(record, "updated_at")

    valid_activity_kinds = {value for value, _label in ActivityEvent.Kind.choices}
    for event_id, record in activity.items():
        actor_id = _foreign_id(record, "actor_id")
        project_id = _foreign_id(record, "project_id", allow_none=True)
        task_id = _foreign_id(record, "task_id", allow_none=True)
        if actor_id not in users:
            raise ArchiveRestoreError(f"Activity event {event_id} has unknown actor.")
        if project_id is not None and project_id not in projects:
            raise ArchiveRestoreError(f"Activity event {event_id} has unknown project.")
        if task_id is not None and task_id not in tasks:
            raise ArchiveRestoreError(f"Activity event {event_id} has unknown task.")
        if record.get("kind") not in valid_activity_kinds:
            raise ArchiveRestoreError(f"Activity event {event_id} has invalid kind.")
        _text(record, "summary", max_length=500, allow_blank=False)
        if not isinstance(record.get("details"), dict):
            raise ArchiveRestoreError(f"Activity event {event_id} details must be an object.")
        _timestamp(record, "created_at")

    return {
        "source_owner_id": source_owner_id,
        "user_map": user_map,
        "projects": projects,
        "memberships": memberships,
        "labels": labels,
        "tasks": tasks,
        "comments": comments,
        "activity": activity,
    }


@transaction.atomic
def restore_user_archive(payload, *, user) -> RestoreSummary:
    """Restore a complete v1 user archive into a clean account-owned data set."""
    _validate_clean_target(user)
    state = validate_user_archive(payload, user=user)

    users = state["user_map"]
    projects = state["projects"]
    memberships = state["memberships"]
    labels = state["labels"]
    tasks = state["tasks"]
    comments = state["comments"]
    activity = state["activity"]

    project_map = {}
    for source_id, record in projects.items():
        # Shared visibility is temporary so historical collaborators can satisfy
        # model validation while records are reconstructed inside this transaction.
        project_map[source_id] = Project.objects.create(
            owner=user,
            name=record["name"].strip(),
            visibility=Project.Visibility.SHARED,
            is_archived=record["is_archived"],
        )

    membership_map = {}
    for source_id, record in memberships.items():
        # Every historical member is temporarily an active Manager. This is never
        # observable outside the atomic transaction and permits faithful restoration
        # of records created or assigned before a later role change or revocation.
        membership_map[source_id] = ProjectMembership.objects.create(
            project=project_map[record["project_id"]],
            user=users[record["user_id"]],
            role=ProjectMembership.Role.MANAGER,
            is_active=True,
        )

    label_map = {}
    for source_id, record in labels.items():
        label_map[source_id] = Label.objects.create(
            owner=users[record["owner_id"]],
            project=(
                project_map[record["project_id"]]
                if record["project_id"] is not None
                else None
            ),
            name=record["name"].strip(),
        )

    task_map = {}
    for source_id, record in tasks.items():
        task_map[source_id] = Task.objects.create(
            title=record["title"],
            description=record["description"],
            creator=users[record["creator_id"]],
            assignee=(users[record["assignee_id"]] if record["assignee_id"] else None),
            project=(
                project_map[record["project_id"]]
                if record["project_id"] is not None
                else None
            ),
            priority=record["priority"],
            status=record["status"],
            due_at=_timestamp(record, "due_at", allow_none=True),
            is_goreecloud_work=record["is_goreecloud_work"],
            assigned_system=record["assigned_system"],
            assigned_service=record["assigned_service"],
            environment=record["environment"],
            workload_category=record["workload_category"],
            blocker=record["blocker"],
            resume_condition=record["resume_condition"],
            backup_prerequisite=record["backup_prerequisite"],
            recovery_requirement=record["recovery_requirement"],
            validation_requirement=record["validation_requirement"],
            documentation_requirement=record["documentation_requirement"],
            related_change_record=record["related_change_record"],
            related_documentation=record["related_documentation"],
        )

    for source_id, record in tasks.items():
        if record["label_ids"]:
            task_map[source_id].labels.set(
                [label_map[label_id] for label_id in record["label_ids"]]
            )

    for source_id, record in tasks.items():
        if record["parent_id"] is None:
            continue
        task = task_map[source_id]
        task.parent = task_map[record["parent_id"]]
        task.save()

    comment_map = {}
    for source_id, record in comments.items():
        comment_map[source_id] = TaskComment.objects.create(
            task=task_map[record["task_id"]],
            author=users[record["author_id"]],
            body=record["body"],
        )

    activity_map = {}
    for source_id, record in activity.items():
        activity_map[source_id] = ActivityEvent.objects.create(
            actor=users[record["actor_id"]],
            project=(
                project_map[record["project_id"]]
                if record["project_id"] is not None
                else None
            ),
            task=(
                task_map[record["task_id"]]
                if record["task_id"] is not None
                else None
            ),
            kind=record["kind"],
            summary=record["summary"],
            details=record["details"],
        )

    # Restore historical timestamps and final authorization state only after all
    # model-level relationship checks have succeeded.
    for source_id, restored in membership_map.items():
        record = memberships[source_id]
        ProjectMembership.objects.filter(pk=restored.pk).update(
            role=record["role"],
            is_active=record["is_active"],
            created_at=_timestamp(record, "created_at"),
        )

    for source_id, restored in projects.items():
        project = project_map[source_id]
        Project.objects.filter(pk=project.pk).update(
            visibility=restored["visibility"],
            is_archived=restored["is_archived"],
            created_at=_timestamp(restored, "created_at"),
            updated_at=_timestamp(restored, "updated_at"),
        )

    for source_id, restored in label_map.items():
        Label.objects.filter(pk=restored.pk).update(
            created_at=_timestamp(labels[source_id], "created_at")
        )

    for source_id, restored in task_map.items():
        record = tasks[source_id]
        Task.objects.filter(pk=restored.pk).update(
            completed_at=_timestamp(record, "completed_at", allow_none=True),
            created_at=_timestamp(record, "created_at"),
            updated_at=_timestamp(record, "updated_at"),
        )

    for source_id, restored in comment_map.items():
        record = comments[source_id]
        TaskComment.objects.filter(pk=restored.pk).update(
            created_at=_timestamp(record, "created_at"),
            updated_at=_timestamp(record, "updated_at"),
        )

    for source_id, restored in activity_map.items():
        ActivityEvent.objects.filter(pk=restored.pk).update(
            created_at=_timestamp(activity[source_id], "created_at")
        )

    return RestoreSummary(
        projects_restored=len(project_map),
        memberships_restored=len(membership_map),
        labels_restored=len(label_map),
        tasks_restored=len(task_map),
        comments_restored=len(comment_map),
        activity_events_restored=len(activity_map),
    )
