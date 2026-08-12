"""Versioned, authorization-scoped GoreeCloud Tasks JSON exports."""

from django.db.models import Q
from django.utils import timezone

from collaboration.models import ActivityEvent, TaskComment
from labels.models import Label
from projects.models import Project, ProjectMembership
from tasks.models import Task

from .notification_state import attach_user_notification_state

EXPORT_FORMAT = "goreecloud.tasks.export"
SCHEMA_VERSION = 2


def _iso(value):
    return value.isoformat() if value else None


def _user_ref(user):
    if user is None:
        return None
    return {"id": user.pk, "username": user.username}


def _project_record(project):
    return {
        "id": project.pk,
        "owner_id": project.owner_id,
        "name": project.name,
        "visibility": project.visibility,
        "is_archived": project.is_archived,
        "created_at": _iso(project.created_at),
        "updated_at": _iso(project.updated_at),
    }


def _membership_record(membership):
    return {
        "id": membership.pk,
        "project_id": membership.project_id,
        "user_id": membership.user_id,
        "role": membership.role,
        "is_active": membership.is_active,
        "created_at": _iso(membership.created_at),
    }


def _label_record(label):
    return {
        "id": label.pk,
        "owner_id": label.owner_id,
        "project_id": label.project_id,
        "name": label.name,
        "created_at": _iso(label.created_at),
    }


def _task_record(task):
    return {
        "id": task.pk,
        "title": task.title,
        "description": task.description,
        "creator_id": task.creator_id,
        "assignee_id": task.assignee_id,
        "project_id": task.project_id,
        "parent_id": task.parent_id,
        "label_ids": list(task.labels.order_by("id").values_list("id", flat=True)),
        "priority": task.priority,
        "status": task.status,
        "due_at": _iso(task.due_at),
        "completed_at": _iso(task.completed_at),
        "is_goreecloud_work": task.is_goreecloud_work,
        "assigned_system": task.assigned_system,
        "assigned_service": task.assigned_service,
        "environment": task.environment,
        "workload_category": task.workload_category,
        "blocker": task.blocker,
        "resume_condition": task.resume_condition,
        "backup_prerequisite": task.backup_prerequisite,
        "recovery_requirement": task.recovery_requirement,
        "validation_requirement": task.validation_requirement,
        "documentation_requirement": task.documentation_requirement,
        "related_change_record": task.related_change_record,
        "related_documentation": task.related_documentation,
        "created_at": _iso(task.created_at),
        "updated_at": _iso(task.updated_at),
    }


def _comment_record(comment):
    return {
        "id": comment.pk,
        "task_id": comment.task_id,
        "author_id": comment.author_id,
        "body": comment.body,
        "created_at": _iso(comment.created_at),
        "updated_at": _iso(comment.updated_at),
    }


def _activity_record(event):
    return {
        "id": event.pk,
        "actor_id": event.actor_id,
        "project_id": event.project_id,
        "task_id": event.task_id,
        "kind": event.kind,
        "summary": event.summary,
        "details": event.details,
        "created_at": _iso(event.created_at),
    }


def _document(*, scope, users, projects, memberships, labels, tasks, comments, activity):
    return {
        "format": EXPORT_FORMAT,
        "schema_version": SCHEMA_VERSION,
        "exported_at": timezone.now().isoformat(),
        "scope": scope,
        "data": {
            "users": users,
            "projects": [_project_record(item) for item in projects],
            "memberships": [_membership_record(item) for item in memberships],
            "labels": [_label_record(item) for item in labels],
            "tasks": [_task_record(item) for item in tasks],
            "comments": [_comment_record(item) for item in comments],
            "activity": [_activity_record(item) for item in activity],
        },
    }


def build_user_archive(user):
    """Export data owned by one user without bulk-exporting others' projects."""
    owned_projects = list(
        Project.objects.filter(owner=user).select_related("owner").order_by("id")
    )
    owned_project_ids = [project.pk for project in owned_projects]
    memberships = list(
        ProjectMembership.objects.filter(project_id__in=owned_project_ids)
        .select_related("project", "user")
        .order_by("id")
    )
    labels = list(
        Label.objects.filter(
            Q(project__isnull=True, owner=user) | Q(project_id__in=owned_project_ids)
        )
        .select_related("owner", "project")
        .order_by("id")
    )
    tasks = list(
        Task.objects.filter(
            Q(project__isnull=True, creator=user) | Q(project_id__in=owned_project_ids)
        )
        .select_related("creator", "assignee", "project", "parent")
        .prefetch_related("labels")
        .order_by("id")
    )
    task_ids = [task.pk for task in tasks]
    comments = list(
        TaskComment.objects.filter(task_id__in=task_ids)
        .select_related("task", "author")
        .order_by("id")
    )
    activity = list(
        ActivityEvent.objects.filter(
            Q(task_id__in=task_ids)
            | Q(project_id__in=owned_project_ids)
            | Q(actor=user, project__isnull=True, task__isnull=True)
        )
        .select_related("actor", "project", "task")
        .distinct()
        .order_by("id")
    )

    users = {user.pk: _user_ref(user)}
    for collection, fields in (
        (owned_projects, ("owner",)),
        (memberships, ("user",)),
        (labels, ("owner",)),
        (tasks, ("creator", "assignee")),
        (comments, ("author",)),
        (activity, ("actor",)),
    ):
        for obj in collection:
            for field in fields:
                account = getattr(obj, field, None)
                if account is not None:
                    users[account.pk] = _user_ref(account)

    document = _document(
        scope={"kind": "user_archive", "user_id": user.pk, "username": user.username},
        users=[users[key] for key in sorted(users)],
        projects=owned_projects,
        memberships=memberships,
        labels=labels,
        tasks=tasks,
        comments=comments,
        activity=activity,
    )
    return attach_user_notification_state(
        document,
        user=user,
        archived_task_ids=task_ids,
    )


def build_project_archive(project):
    """Export one owner-authorized project and its application-owned records."""
    memberships = list(project.memberships.select_related("project", "user").order_by("id"))
    labels = list(project.labels.select_related("owner", "project").order_by("id"))
    tasks = list(
        project.tasks.select_related("creator", "assignee", "project", "parent")
        .prefetch_related("labels")
        .order_by("id")
    )
    task_ids = [task.pk for task in tasks]
    comments = list(
        TaskComment.objects.filter(task_id__in=task_ids)
        .select_related("task", "author")
        .order_by("id")
    )
    activity = list(
        project.activity_events.select_related("actor", "project", "task").order_by("id")
    )

    users = {project.owner_id: _user_ref(project.owner)}
    for collection, fields in (
        (memberships, ("user",)),
        (labels, ("owner",)),
        (tasks, ("creator", "assignee")),
        (comments, ("author",)),
        (activity, ("actor",)),
    ):
        for obj in collection:
            for field in fields:
                account = getattr(obj, field, None)
                if account is not None:
                    users[account.pk] = _user_ref(account)

    return _document(
        scope={
            "kind": "project_archive",
            "project_id": project.pk,
            "project_name": project.name,
            "owner_id": project.owner_id,
        },
        users=[users[key] for key in sorted(users)],
        projects=[project],
        memberships=memberships,
        labels=labels,
        tasks=tasks,
        comments=comments,
        activity=activity,
    )
