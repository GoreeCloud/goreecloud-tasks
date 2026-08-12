"""User-private notification preference and reminder archive support.

Notification state is intentionally scoped to a user archive. Project archives must not
expose another person's reminder preferences or private reminder schedule. Reminders
for tasks that are visible only through a project owned by somebody else are also not
bulk-exported because the corresponding task is outside the user-archive ownership
boundary.
"""

from copy import deepcopy
import re

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from notifications.models import NotificationPreference, TaskReminder
from tasks.models import Task

LEGACY_USER_ARCHIVE_SCHEMA_VERSION = 1
_TOPIC_RE = re.compile(r"^[-_A-Za-z0-9]{1,64}$")


def _iso(value):
    return value.isoformat() if value else None


def _preference_record(preference):
    if preference is None:
        return None
    return {
        "user_id": preference.user_id,
        "reminders_enabled": preference.reminders_enabled,
        "default_lead_minutes": preference.default_lead_minutes,
        "ntfy_enabled": preference.ntfy_enabled,
        "ntfy_topic": preference.ntfy_topic,
        "created_at": _iso(preference.created_at),
        "updated_at": _iso(preference.updated_at),
    }


def _reminder_record(reminder):
    return {
        "id": reminder.pk,
        "user_id": reminder.user_id,
        "task_id": reminder.task_id,
        "remind_at": _iso(reminder.remind_at),
        "sent_at": _iso(reminder.sent_at),
        "cancelled_at": _iso(reminder.cancelled_at),
        "last_attempt_at": _iso(reminder.last_attempt_at),
        "attempt_count": reminder.attempt_count,
        "created_at": _iso(reminder.created_at),
        "updated_at": _iso(reminder.updated_at),
    }


def attach_user_notification_state(document, *, user, archived_task_ids):
    """Attach user-private notification state without widening archive ownership scope."""
    task_ids = set(archived_task_ids)
    preference = NotificationPreference.objects.filter(user=user).first()
    reminders = list(
        TaskReminder.objects.filter(user=user, task_id__in=task_ids)
        .select_related("task")
        .order_by("id")
    )
    total_reminders = TaskReminder.objects.filter(user=user).count()

    document["data"]["notifications"] = {
        "preference": _preference_record(preference),
        "reminders": [_reminder_record(item) for item in reminders],
        "excluded_shared_task_reminder_count": total_reminders - len(reminders),
    }
    return document


def _require_dict(value, label, *, error_type):
    if not isinstance(value, dict):
        raise error_type(f"{label} must be a JSON object.")
    return value


def _require_list(value, label, *, error_type):
    if not isinstance(value, list):
        raise error_type(f"{label} must be a JSON array.")
    return value


def _timestamp(value, label, *, allow_none, error_type):
    if value is None:
        if allow_none:
            return None
        raise error_type(f"{label} is required.")
    if not isinstance(value, str):
        raise error_type(f"{label} must be an ISO-8601 timestamp.")
    parsed = parse_datetime(value)
    if parsed is None or timezone.is_naive(parsed):
        raise error_type(f"{label} must include a valid timezone offset.")
    return parsed


def _validate_v2_notification_state(payload, *, user, error_type):
    data = _require_dict(payload.get("data"), "Archive data", error_type=error_type)
    scope = _require_dict(payload.get("scope"), "Archive scope", error_type=error_type)
    source_owner_id = scope.get("user_id")
    task_records = _require_list(data.get("tasks"), "tasks", error_type=error_type)
    task_ids = {
        item.get("id")
        for item in task_records
        if isinstance(item, dict) and isinstance(item.get("id"), int)
    }

    notifications = _require_dict(
        data.get("notifications"),
        "data.notifications",
        error_type=error_type,
    )
    preference = notifications.get("preference")
    if preference is not None:
        preference = _require_dict(
            preference,
            "Notification preference",
            error_type=error_type,
        )
        if preference.get("user_id") != source_owner_id:
            raise error_type("Notification preferences must belong to the archive owner.")
        for field in ("reminders_enabled", "ntfy_enabled"):
            if not isinstance(preference.get(field), bool):
                raise error_type(f"Notification preference {field} must be true or false.")
        lead = preference.get("default_lead_minutes")
        if (
            not isinstance(lead, int)
            or isinstance(lead, bool)
            or lead < 0
            or lead > 10080
        ):
            raise error_type(
                "Notification preference default_lead_minutes must be between 0 and 10080."
            )
        topic = preference.get("ntfy_topic")
        if not isinstance(topic, str) or not _TOPIC_RE.fullmatch(topic):
            raise error_type("Notification preference ntfy_topic is invalid.")
        _timestamp(
            preference.get("created_at"),
            "Notification preference created_at",
            allow_none=False,
            error_type=error_type,
        )
        _timestamp(
            preference.get("updated_at"),
            "Notification preference updated_at",
            allow_none=False,
            error_type=error_type,
        )
        if NotificationPreference.objects.exclude(user=user).filter(ntfy_topic=topic).exists():
            raise error_type(
                "The archived ntfy topic is already assigned to another local user."
            )

    reminder_records = _require_list(
        notifications.get("reminders"),
        "Notification reminders",
        error_type=error_type,
    )
    reminder_ids = set()
    active_keys = set()
    for reminder in reminder_records:
        reminder = _require_dict(reminder, "Reminder record", error_type=error_type)
        reminder_id = reminder.get("id")
        if (
            not isinstance(reminder_id, int)
            or isinstance(reminder_id, bool)
            or reminder_id <= 0
            or reminder_id in reminder_ids
        ):
            raise error_type("Every reminder requires a unique positive integer id.")
        reminder_ids.add(reminder_id)
        if reminder.get("user_id") != source_owner_id:
            raise error_type("Every archived reminder must belong to the archive owner.")
        task_id = reminder.get("task_id")
        if task_id not in task_ids:
            raise error_type("An archived reminder references a task outside the archive.")

        remind_at = _timestamp(
            reminder.get("remind_at"),
            "Reminder remind_at",
            allow_none=False,
            error_type=error_type,
        )
        sent_at = _timestamp(
            reminder.get("sent_at"),
            "Reminder sent_at",
            allow_none=True,
            error_type=error_type,
        )
        cancelled_at = _timestamp(
            reminder.get("cancelled_at"),
            "Reminder cancelled_at",
            allow_none=True,
            error_type=error_type,
        )
        _timestamp(
            reminder.get("last_attempt_at"),
            "Reminder last_attempt_at",
            allow_none=True,
            error_type=error_type,
        )
        _timestamp(
            reminder.get("created_at"),
            "Reminder created_at",
            allow_none=False,
            error_type=error_type,
        )
        _timestamp(
            reminder.get("updated_at"),
            "Reminder updated_at",
            allow_none=False,
            error_type=error_type,
        )
        attempt_count = reminder.get("attempt_count")
        if (
            not isinstance(attempt_count, int)
            or isinstance(attempt_count, bool)
            or attempt_count < 0
        ):
            raise error_type("Reminder attempt_count must be a non-negative integer.")
        if sent_at is not None and cancelled_at is not None:
            raise error_type("A reminder cannot be both delivered and cancelled.")
        if cancelled_at is None:
            key = (task_id, remind_at)
            if key in active_keys:
                raise error_type("The archive contains duplicate active reminders.")
            active_keys.add(key)

    excluded_count = notifications.get("excluded_shared_task_reminder_count")
    if (
        not isinstance(excluded_count, int)
        or isinstance(excluded_count, bool)
        or excluded_count < 0
    ):
        raise error_type(
            "excluded_shared_task_reminder_count must be a non-negative integer."
        )

    return {
        "preference": preference,
        "reminders": reminder_records,
        "source_task_ids": [item["id"] for item in task_records],
    }


@transaction.atomic
def restore_user_archive_with_notifications(payload, *, user):
    """Restore core user-archive data plus schema-v2 private notification state.

    Schema-v1 user archives remain restorable. Version 2 adds notification state while
    preserving the existing clean-target and identity checks from the core restorer.
    """
    from .exporters import SCHEMA_VERSION
    from .restorers import ArchiveRestoreError, restore_user_archive as restore_core_archive

    if not isinstance(payload, dict):
        raise ArchiveRestoreError("Archive must be a JSON object.")
    schema_version = payload.get("schema_version")
    if schema_version not in {LEGACY_USER_ARCHIVE_SCHEMA_VERSION, SCHEMA_VERSION}:
        raise ArchiveRestoreError(
            f"Unsupported archive schema version. Expected 1 or {SCHEMA_VERSION}."
        )

    notification_state = None
    if schema_version == SCHEMA_VERSION:
        notification_state = _validate_v2_notification_state(
            payload,
            user=user,
            error_type=ArchiveRestoreError,
        )
        if TaskReminder.objects.filter(user=user).exists():
            raise ArchiveRestoreError(
                "Schema-v2 restoration requires an account with no existing Tasks reminders."
            )

    core_payload = deepcopy(payload)
    core_payload["schema_version"] = SCHEMA_VERSION
    summary = restore_core_archive(core_payload, user=user)

    if notification_state is None:
        return summary

    preference_record = notification_state["preference"]
    if preference_record is not None:
        preference, _created = NotificationPreference.objects.update_or_create(
            user=user,
            defaults={
                "reminders_enabled": preference_record["reminders_enabled"],
                "default_lead_minutes": preference_record["default_lead_minutes"],
                "ntfy_enabled": preference_record["ntfy_enabled"],
                "ntfy_topic": preference_record["ntfy_topic"],
            },
        )
        NotificationPreference.objects.filter(pk=preference.pk).update(
            created_at=_timestamp(
                preference_record["created_at"],
                "Notification preference created_at",
                allow_none=False,
                error_type=ArchiveRestoreError,
            ),
            updated_at=_timestamp(
                preference_record["updated_at"],
                "Notification preference updated_at",
                allow_none=False,
                error_type=ArchiveRestoreError,
            ),
        )

    source_task_ids = notification_state["source_task_ids"]
    restored_tasks = list(
        Task.objects.filter(
            Q(project__owner=user) | Q(project__isnull=True, creator=user)
        )
        .distinct()
        .order_by("id")
    )
    if len(restored_tasks) != len(source_task_ids):
        raise ArchiveRestoreError(
            "Restored task count did not match the archive while rebuilding reminders."
        )
    task_map = dict(zip(source_task_ids, restored_tasks, strict=True))

    reminder_objects = []
    for record in notification_state["reminders"]:
        reminder_objects.append(
            TaskReminder(
                user=user,
                task=task_map[record["task_id"]],
                remind_at=_timestamp(
                    record["remind_at"],
                    "Reminder remind_at",
                    allow_none=False,
                    error_type=ArchiveRestoreError,
                ),
                sent_at=_timestamp(
                    record["sent_at"],
                    "Reminder sent_at",
                    allow_none=True,
                    error_type=ArchiveRestoreError,
                ),
                cancelled_at=_timestamp(
                    record["cancelled_at"],
                    "Reminder cancelled_at",
                    allow_none=True,
                    error_type=ArchiveRestoreError,
                ),
                last_attempt_at=_timestamp(
                    record["last_attempt_at"],
                    "Reminder last_attempt_at",
                    allow_none=True,
                    error_type=ArchiveRestoreError,
                ),
                attempt_count=record["attempt_count"],
                last_error="",
            )
        )

    restored_reminders = TaskReminder.objects.bulk_create(reminder_objects)
    for restored, record in zip(
        restored_reminders,
        notification_state["reminders"],
        strict=True,
    ):
        TaskReminder.objects.filter(pk=restored.pk).update(
            created_at=_timestamp(
                record["created_at"],
                "Reminder created_at",
                allow_none=False,
                error_type=ArchiveRestoreError,
            ),
            updated_at=_timestamp(
                record["updated_at"],
                "Reminder updated_at",
                allow_none=False,
                error_type=ArchiveRestoreError,
            ),
        )

    return summary
