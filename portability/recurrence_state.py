"""Backward-compatible recurring-task restoration for GoreeCloud Tasks archives."""

from django.db import transaction
from django.db.models import Q

from tasks.models import Task

from .notification_state import (
    LEGACY_USER_ARCHIVE_SCHEMA_VERSION,
    restore_user_archive_with_notifications,
)
from .restorers import ArchiveRestoreError


def _task_records(payload):
    if not isinstance(payload, dict):
        raise ArchiveRestoreError("Archive must be a JSON object.")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ArchiveRestoreError("Archive data must be a JSON object.")
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        raise ArchiveRestoreError("tasks must be a JSON array.")
    return tasks


def _validated_recurrence_records(payload):
    """Return recurrence values in archive task order, defaulting older records to none."""
    from .exporters import SCHEMA_VERSION

    schema_version = payload.get("schema_version") if isinstance(payload, dict) else None
    if schema_version not in {LEGACY_USER_ARCHIVE_SCHEMA_VERSION, SCHEMA_VERSION}:
        raise ArchiveRestoreError(
            f"Unsupported archive schema version. Expected 1 or {SCHEMA_VERSION}."
        )

    valid_recurrences = {value for value, _label in Task.Recurrence.choices}
    values = []
    for record in _task_records(payload):
        if not isinstance(record, dict):
            raise ArchiveRestoreError("task record must be a JSON object.")
        recurrence = record.get("recurrence", Task.Recurrence.NONE)
        if recurrence not in valid_recurrences:
            raise ArchiveRestoreError("Archived task has an invalid recurrence value.")
        if recurrence != Task.Recurrence.NONE and record.get("due_at") is None:
            raise ArchiveRestoreError("A repeating archived task requires due_at.")
        values.append(recurrence)
    return values


@transaction.atomic
def restore_user_archive_with_recurrence(payload, *, user):
    """Restore core, notification, and additive recurrence state atomically.

    Recurrence was added as an optional schema-v2 task field. Existing schema-v1 and
    schema-v2 archives that predate the field therefore restore with `none` rather than
    being rejected or silently assigned a repeat rule.
    """
    recurrence_values = _validated_recurrence_records(payload)
    summary = restore_user_archive_with_notifications(payload, user=user)

    restored_tasks = list(
        Task.objects.filter(
            Q(project__owner=user) | Q(project__isnull=True, creator=user)
        )
        .distinct()
        .order_by("id")
    )
    if len(restored_tasks) != len(recurrence_values):
        raise ArchiveRestoreError(
            "Restored task count did not match the archive while rebuilding recurrence state."
        )

    for task, recurrence in zip(restored_tasks, recurrence_values, strict=True):
        if task.recurrence != recurrence:
            Task.objects.filter(pk=task.pk).update(recurrence=recurrence)

    return summary
