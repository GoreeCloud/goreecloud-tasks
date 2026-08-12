"""Safe database execution for provider-neutral task import bundles.

External adapters normalize provider-specific data into ``NormalizedImportBundle``
first. This module then validates every cross-record relationship before opening a
transaction and creates only data owned by the authenticated importing user.

The executor deliberately does not create users, shared memberships, or shared
projects. Provider imports therefore cannot silently broaden access.
"""

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from labels.models import Label
from projects.models import Project
from tasks.models import Task

from .schema import NormalizedImportBundle


class ImportExecutionError(ValueError):
    """Raised when a normalized bundle is unsafe or internally inconsistent."""


@dataclass(frozen=True)
class ImportSummary:
    source: str
    projects_created: int
    labels_created: int
    tasks_created: int


def _clean_source_id(value, kind):
    if not isinstance(value, str) or not value.strip():
        raise ImportExecutionError(f"Every {kind} requires a non-empty string source_id.")
    return value.strip()


def _clean_name(value, *, kind, max_length):
    if not isinstance(value, str):
        raise ImportExecutionError(f"Every {kind} name must be text.")
    value = value.strip()
    if not value:
        raise ImportExecutionError(f"Every {kind} requires a name.")
    if len(value) > max_length:
        raise ImportExecutionError(
            f"{kind.capitalize()} names may not exceed {max_length} characters."
        )
    return value


def _index(records, *, kind):
    indexed = {}
    for record in records:
        source_id = _clean_source_id(record.source_id, kind)
        if source_id in indexed:
            raise ImportExecutionError(f"Duplicate {kind} source_id: {source_id}")
        indexed[source_id] = record
    return indexed


def _validate_parent_graph(tasks):
    parent_map = {
        source_id: task.parent_source_id
        for source_id, task in tasks.items()
        if task.parent_source_id is not None
    }
    for source_id in tasks:
        seen = set()
        current = source_id
        while current in parent_map:
            if current in seen:
                raise ImportExecutionError("Imported task parents may not contain a cycle.")
            seen.add(current)
            current = parent_map[current]


def validate_import_bundle(bundle: NormalizedImportBundle):
    """Validate a normalized external import without mutating the database."""
    if not isinstance(bundle, NormalizedImportBundle):
        raise ImportExecutionError("Import adapters must return NormalizedImportBundle.")
    if not isinstance(bundle.source, str) or not bundle.source.strip():
        raise ImportExecutionError("The import bundle requires a source identifier.")

    projects = _index(bundle.projects, kind="project")
    labels = _index(bundle.labels, kind="label")
    tasks = _index(bundle.tasks, kind="task")

    project_names = set()
    for project in projects.values():
        name = _clean_name(project.name, kind="project", max_length=200)
        if name in project_names:
            raise ImportExecutionError(f"Duplicate imported project name: {name}")
        project_names.add(name)

    personal_label_names = set()
    project_label_names = set()
    for label_id, label in labels.items():
        name = _clean_name(label.name, kind="label", max_length=100)
        if label.project_source_id is None:
            if name in personal_label_names:
                raise ImportExecutionError(f"Duplicate imported personal label: {name}")
            personal_label_names.add(name)
        else:
            project_id = _clean_source_id(label.project_source_id, "project reference")
            if project_id not in projects:
                raise ImportExecutionError(
                    f"Label {label_id} references unknown project {project_id}."
                )
            key = (project_id, name)
            if key in project_label_names:
                raise ImportExecutionError(
                    f"Duplicate imported label {name} in project {project_id}."
                )
            project_label_names.add(key)

    valid_priorities = {value for value, _label in Task.Priority.choices}
    valid_statuses = {value for value, _label in Task.Status.choices}
    for task_id, task in tasks.items():
        _clean_name(task.title, kind="task", max_length=500)
        if not isinstance(task.description, str):
            raise ImportExecutionError(f"Task {task_id} description must be text.")

        project_id = None
        if task.project_source_id is not None:
            project_id = _clean_source_id(task.project_source_id, "project reference")
            if project_id not in projects:
                raise ImportExecutionError(
                    f"Task {task_id} references unknown project {project_id}."
                )

        if task.parent_source_id is not None:
            parent_id = _clean_source_id(task.parent_source_id, "parent task reference")
            if parent_id not in tasks:
                raise ImportExecutionError(
                    f"Task {task_id} references unknown parent task {parent_id}."
                )
            if parent_id == task_id:
                raise ImportExecutionError("A task cannot be its own parent.")
            if tasks[parent_id].project_source_id != task.project_source_id:
                raise ImportExecutionError(
                    f"Task {task_id} and parent {parent_id} must share one import scope."
                )

        for label_source_id in task.label_source_ids:
            label_id = _clean_source_id(label_source_id, "label reference")
            if label_id not in labels:
                raise ImportExecutionError(
                    f"Task {task_id} references unknown label {label_id}."
                )
            if labels[label_id].project_source_id != task.project_source_id:
                raise ImportExecutionError(
                    f"Task {task_id} references label {label_id} from another scope."
                )

        if task.priority is not None and task.priority not in valid_priorities:
            raise ImportExecutionError(
                f"Task {task_id} uses unsupported priority {task.priority}."
            )
        if task.status is not None and task.status not in valid_statuses:
            raise ImportExecutionError(
                f"Task {task_id} uses unsupported status {task.status}."
            )
        if task.due_at is not None and timezone.is_naive(task.due_at):
            raise ImportExecutionError(
                f"Task {task_id} due_at must include a timezone offset."
            )

    _validate_parent_graph(tasks)
    return projects, labels, tasks


@transaction.atomic
def execute_import(*, user, bundle: NormalizedImportBundle) -> ImportSummary:
    """Create a validated external import as private data owned by ``user``.

    The operation is atomic. Existing records are never overwritten or merged.
    Imported projects are always private, imported tasks are created and assigned
    to the importing user, and no project memberships are created.
    """
    if not user or not user.is_authenticated:
        raise ImportExecutionError("An authenticated user is required for import.")

    projects, labels, tasks = validate_import_bundle(bundle)

    project_names = [_clean_name(item.name, kind="project", max_length=200) for item in projects.values()]
    existing_projects = set(
        Project.objects.filter(owner=user, name__in=project_names).values_list("name", flat=True)
    )
    if existing_projects:
        names = ", ".join(sorted(existing_projects))
        raise ImportExecutionError(
            f"Import would collide with existing owned project name(s): {names}."
        )

    personal_names = [
        _clean_name(item.name, kind="label", max_length=100)
        for item in labels.values()
        if item.project_source_id is None
    ]
    existing_personal_labels = set(
        Label.objects.filter(
            owner=user,
            project__isnull=True,
            name__in=personal_names,
        ).values_list("name", flat=True)
    )
    if existing_personal_labels:
        names = ", ".join(sorted(existing_personal_labels))
        raise ImportExecutionError(
            f"Import would collide with existing personal label name(s): {names}."
        )

    project_map = {}
    for source_id, record in projects.items():
        project_map[source_id] = Project.objects.create(
            owner=user,
            name=_clean_name(record.name, kind="project", max_length=200),
            visibility=Project.Visibility.PRIVATE,
        )

    label_map = {}
    for source_id, record in labels.items():
        label_map[source_id] = Label.objects.create(
            name=_clean_name(record.name, kind="label", max_length=100),
            owner=user,
            project=(
                project_map[record.project_source_id]
                if record.project_source_id is not None
                else None
            ),
        )

    task_map = {}
    for source_id, record in tasks.items():
        task_map[source_id] = Task.objects.create(
            title=_clean_name(record.title, kind="task", max_length=500),
            description=record.description,
            creator=user,
            assignee=user,
            project=(
                project_map[record.project_source_id]
                if record.project_source_id is not None
                else None
            ),
            priority=(record.priority if record.priority is not None else Task.Priority.P3_STANDARD),
            status=(record.status if record.status is not None else Task.Status.PLANNED),
            due_at=record.due_at,
        )

    for source_id, record in tasks.items():
        task = task_map[source_id]
        if record.label_source_ids:
            task.labels.set([label_map[label_id] for label_id in record.label_source_ids])

    for source_id, record in tasks.items():
        if record.parent_source_id is None:
            continue
        task = task_map[source_id]
        task.parent = task_map[record.parent_source_id]
        task.save()

    return ImportSummary(
        source=bundle.source.strip(),
        projects_created=len(project_map),
        labels_created=len(label_map),
        tasks_created=len(task_map),
    )
