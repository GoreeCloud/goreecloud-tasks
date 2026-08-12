"""Reminder scheduling helpers and the least-privilege ntfy publisher boundary."""

from dataclasses import dataclass
from datetime import timedelta
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.formats import date_format

from tasks.models import Task

from .models import NotificationPreference, TaskReminder


_TOPIC_RE = re.compile(r"^[-_A-Za-z0-9]{1,64}$")


class NotificationDeliveryError(RuntimeError):
    """Base class for reminder-delivery failures safe to persist or display."""


class NtfyConfigurationError(NotificationDeliveryError):
    """Raised when the application-side ntfy publisher is not configured safely."""


class NtfyPublishError(NotificationDeliveryError):
    """Raised when an authenticated ntfy publication fails."""


@dataclass(frozen=True)
class DispatchSummary:
    candidates: int = 0
    sent: int = 0
    cancelled: int = 0
    failed: int = 0


def get_preferences(user):
    """Return the persisted notification preferences for one authenticated user."""
    preference, _created = NotificationPreference.objects.get_or_create(user=user)
    return preference


def preference_snapshot(user):
    """Return preferences without forcing a database write during ordinary page reads."""
    preference = NotificationPreference.objects.filter(user=user).first()
    if preference is not None:
        return preference
    return NotificationPreference(user=user)


def default_reminder_time(*, user, task, now=None):
    """Choose a useful default reminder time from the user's configured lead time."""
    now = now or timezone.now()
    preference = preference_snapshot(user)
    if task.due_at is not None:
        candidate = task.due_at - timedelta(minutes=preference.default_lead_minutes)
    else:
        candidate = now + timedelta(hours=1)

    if candidate <= now:
        candidate = now + timedelta(minutes=5)
    return candidate


def ntfy_is_configured():
    return bool(
        getattr(settings, "NTFY_BASE_URL", "")
        and getattr(settings, "NTFY_ACCESS_TOKEN", "")
    )


def _user_zone(user):
    try:
        return ZoneInfo(user.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(settings.TIME_ZONE)


def _ntfy_priority(task):
    """Map GoreeCloud task priority to ntfy urgency without making routine work noisy."""
    return {
        Task.Priority.P0_CRITICAL: "urgent",
        Task.Priority.P1_URGENT: "high",
        Task.Priority.P2_HIGH: "default",
        Task.Priority.P3_STANDARD: "low",
        Task.Priority.P4_LOW: "min",
    }[task.priority]


def _ntfy_endpoint(topic):
    base_url = getattr(settings, "NTFY_BASE_URL", "").strip().rstrip("/")
    token = getattr(settings, "NTFY_ACCESS_TOKEN", "")
    if not base_url or not token:
        raise NtfyConfigurationError(
            "The GoreeCloud Tasks ntfy publisher is not configured."
        )

    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise NtfyConfigurationError("NTFY_BASE_URL must be an HTTP or HTTPS URL.")
    if not _TOPIC_RE.fullmatch(topic):
        raise NtfyConfigurationError("The configured ntfy topic is invalid.")
    return f"{base_url}/{topic}", token


def _reminder_message(reminder):
    """Build a deliberately data-minimized reminder message.

    Descriptions, comments, labels, blockers, recovery notes, related records, and
    other potentially sensitive task detail are intentionally not sent to ntfy.
    """
    task = reminder.task
    lines = [task.title]
    if task.due_at is not None:
        local_due = timezone.localtime(task.due_at, _user_zone(reminder.user))
        lines.append(f"Due {date_format(local_due, 'M j, Y g:i A')}.")
    if task.project_id:
        lines.append(f"Project: {task.project.name}.")
    return "\n".join(lines)


def publish_ntfy_reminder(reminder):
    """Publish one reminder using the dedicated Tasks ntfy service token."""
    preference = get_preferences(reminder.user)
    endpoint, token = _ntfy_endpoint(preference.ntfy_topic)

    request = Request(
        endpoint,
        data=_reminder_message(reminder).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "text/plain; charset=utf-8",
            "Title": "GoreeCloud Tasks reminder",
            "Priority": _ntfy_priority(reminder.task),
            "Tags": "alarm_clock",
        },
    )

    tasks_base_url = getattr(settings, "TASKS_BASE_URL", "").strip().rstrip("/")
    if tasks_base_url:
        parsed_tasks_url = urlparse(tasks_base_url)
        if parsed_tasks_url.scheme in {"http", "https"} and parsed_tasks_url.netloc:
            request.add_header(
                "Click",
                f"{tasks_base_url}/tasks/{reminder.task_id}/",
            )

    timeout = getattr(settings, "NTFY_TIMEOUT_SECONDS", 10)
    try:
        response = urlopen(request, timeout=timeout)
        status = getattr(response, "status", 200)
        response.close()
    except HTTPError as exc:
        raise NtfyPublishError(
            f"ntfy rejected the reminder publication with HTTP {exc.code}."
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise NtfyPublishError(
            "The ntfy reminder publication could not reach the configured server."
        ) from exc

    if not 200 <= status < 300:
        raise NtfyPublishError(
            f"ntfy returned unexpected HTTP status {status}."
        )


def _cancel_locked_reminder(reminder, *, at, reason=""):
    """Cancel a locked reminder without re-running authorization validation."""
    reminder.cancelled_at = at
    reminder.last_error = reason[:500]
    reminder.updated_at = at
    TaskReminder.objects.filter(pk=reminder.pk).update(
        cancelled_at=reminder.cancelled_at,
        last_error=reminder.last_error,
        updated_at=reminder.updated_at,
    )


def dispatch_due_reminders(*, at=None, limit=100):
    """Publish due ntfy reminders after re-checking authorization at send time.

    The ntfy service is not an authorization boundary. A reminder is cancelled if
    the user has lost normal application visibility to the task before dispatch.
    Each candidate is row-locked while delivery state changes to prevent duplicate
    sends when multiple scheduler processes overlap on PostgreSQL.
    """
    at = at or timezone.now()
    candidate_ids = list(
        TaskReminder.objects.due(at)
        .filter(
            user__notification_preferences__reminders_enabled=True,
            user__notification_preferences__ntfy_enabled=True,
        )
        .order_by("remind_at", "id")
        .values_list("id", flat=True)[:limit]
    )

    sent = cancelled = failed = 0
    for reminder_id in candidate_ids:
        with transaction.atomic():
            reminder = (
                TaskReminder.objects.select_for_update()
                .select_related("user", "task", "task__project")
                .get(pk=reminder_id)
            )
            if reminder.sent_at is not None or reminder.cancelled_at is not None:
                continue

            if reminder.task.status in {Task.Status.COMPLETED, Task.Status.CANCELLED}:
                _cancel_locked_reminder(
                    reminder,
                    at=at,
                    reason="Reminder cancelled because the task is closed.",
                )
                cancelled += 1
                continue

            still_visible = Task.objects.visible_to(reminder.user).filter(
                pk=reminder.task_id
            ).exists()
            if not still_visible:
                _cancel_locked_reminder(
                    reminder,
                    at=at,
                    reason="Reminder cancelled because task access is no longer authorized.",
                )
                cancelled += 1
                continue

            reminder.attempt_count += 1
            reminder.last_attempt_at = at
            try:
                publish_ntfy_reminder(reminder)
            except NotificationDeliveryError as exc:
                reminder.last_error = str(exc)[:500]
                reminder.save(
                    update_fields=(
                        "attempt_count",
                        "last_attempt_at",
                        "last_error",
                        "updated_at",
                    )
                )
                failed += 1
                continue

            reminder.sent_at = at
            reminder.last_error = ""
            reminder.save(
                update_fields=(
                    "attempt_count",
                    "last_attempt_at",
                    "sent_at",
                    "last_error",
                    "updated_at",
                )
            )
            sent += 1

    return DispatchSummary(
        candidates=len(candidate_ids),
        sent=sent,
        cancelled=cancelled,
        failed=failed,
    )
