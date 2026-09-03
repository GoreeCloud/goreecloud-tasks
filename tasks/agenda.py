"""Seven-day Tasks agenda composed with privacy-minimized Calendar busy context."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.utils.formats import date_format

from api.calendar_busy_client import CalendarBusyError, fetch_calendar_busy_context
from api.calendar_busy_config import load_calendar_busy_client_configuration

from .models import Task

TERMINAL_STATUSES = [Task.Status.COMPLETED, Task.Status.CANCELLED]
AGENDA_DAYS = 7


def _day_boundary(day, tz):
    """Return local midnight for one date in the active Django timezone."""

    return timezone.make_aware(datetime.combine(day, time.min), tz)


def _scheduled_tasks(user, window_start, window_end):
    """Return active scheduled tasks through the ordinary Tasks visibility boundary."""

    return (
        Task.objects.visible_to(user)
        .exclude(status__in=TERMINAL_STATUSES)
        .filter(due_at__gte=window_start, due_at__lt=window_end)
        .select_related("project", "creator", "assignee", "parent")
        .prefetch_related("labels")
        .order_by("due_at", "priority", "id")
    )


def _decorate_editability(user, tasks):
    tasks = list(tasks)
    if not tasks:
        return tasks

    editable_ids = set(
        Task.objects.editable_by(user)
        .filter(pk__in=[task.pk for task in tasks])
        .values_list("pk", flat=True)
    )
    for task in tasks:
        task.user_can_edit = task.pk in editable_ids
    return tasks


def _build_days(*, first_day, tasks, intervals, tz):
    """Compose display-only day buckets without manufacturing task duration semantics."""

    days = []
    for offset in range(AGENDA_DAYS):
        day = first_day + timedelta(days=offset)
        day_start = _day_boundary(day, tz)
        day_end = _day_boundary(day + timedelta(days=1), tz)

        day_tasks = []
        for task in tasks:
            local_due = timezone.localtime(task.due_at, tz)
            if local_due.date() == day:
                task.agenda_due_local = local_due
                day_tasks.append(task)

        busy_segments = []
        for interval in intervals:
            if interval.ends_at <= day_start or interval.starts_at >= day_end:
                continue
            segment_start = max(interval.starts_at, day_start)
            segment_end = min(interval.ends_at, day_end)
            busy_segments.append(
                {
                    "starts_at": timezone.localtime(segment_start, tz),
                    "ends_at": timezone.localtime(segment_end, tz),
                    "continues_before": interval.starts_at < day_start,
                    "continues_after": interval.ends_at > day_end,
                }
            )

        days.append(
            {
                "date": day,
                "label": date_format(day, "l, F j"),
                "tasks": day_tasks,
                "busy": busy_segments,
                "is_today": offset == 0,
            }
        )
    return days


@login_required
def agenda(request):
    """Render a seven-day planning view without blending Tasks and Calendar authority."""

    tz = timezone.get_current_timezone()
    first_day = timezone.localdate()
    window_start = _day_boundary(first_day, tz)
    window_end = _day_boundary(first_day + timedelta(days=AGENDA_DAYS), tz)

    tasks = _decorate_editability(
        request.user,
        _scheduled_tasks(request.user, window_start, window_end),
    )

    calendar_state = "disabled"
    calendar_intervals = ()
    config = load_calendar_busy_client_configuration()
    if config.enabled:
        if config.error:
            calendar_state = "unavailable"
        elif not config.allows_user(request.user):
            calendar_state = "not-authorized"
        else:
            try:
                calendar_context = fetch_calendar_busy_context(
                    base_url=config.base_url,
                    token=config.token,
                    start=window_start,
                    end=window_end,
                    timeout_seconds=config.timeout_seconds,
                )
            except (CalendarBusyError, TimeoutError, OSError):
                # Calendar is optional context. Never fail or fabricate Tasks state because
                # the peer is unavailable or rejects the bounded read.
                calendar_state = "unavailable"
            else:
                calendar_intervals = calendar_context.intervals
                calendar_state = "available"

    agenda_days = _build_days(
        first_day=first_day,
        tasks=tasks,
        intervals=calendar_intervals,
        tz=tz,
    )

    return render(
        request,
        "tasks/agenda.html",
        {
            "active_view": "agenda",
            "agenda_days": agenda_days,
            "task_count": len(tasks),
            "busy_interval_count": len(calendar_intervals),
            "calendar_state": calendar_state,
            "window_start": window_start,
            "window_end": window_end,
            "window_label": (
                f"{date_format(first_day, 'M j')} – "
                f"{date_format(first_day + timedelta(days=AGENDA_DAYS - 1), 'M j, Y')}"
            ),
        },
    )
