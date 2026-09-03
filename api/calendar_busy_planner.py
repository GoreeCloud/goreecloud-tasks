"""Pure advisory planning over privacy-minimized GoreeCloud Calendar busy context.

Calendar remains authoritative for native events and busy-time derivation. This module computes
only the complement of an already validated busy interval set inside the requested planning range.
It creates no Tasks records and receives no event content or Calendar identity metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .calendar_busy_client import CalendarBusyContext, CalendarBusyError

MIN_FREE_WINDOW = timedelta(minutes=5)
MAX_FREE_WINDOW = timedelta(hours=24)
MAX_RETURNED_WINDOWS = 32


@dataclass(frozen=True, slots=True)
class FreeWindow:
    """One advisory free interval derived only from the validated busy-time complement."""

    starts_at: datetime
    ends_at: datetime

    @property
    def duration(self) -> timedelta:
        return self.ends_at - self.starts_at


def derive_free_windows(
    context: CalendarBusyContext,
    *,
    minimum_duration: timedelta,
    limit: int = 8,
) -> tuple[FreeWindow, ...]:
    """Return earliest qualifying free windows without creating scheduling authority.

    `context` is expected to come from `parse_busy_payload`/`fetch_calendar_busy_context`, where
    busy intervals are already timezone-aware, bounded, strictly ordered, non-overlapping, and
    fully merged. Defensive checks here prevent a manually constructed invalid context from being
    converted into trustworthy-looking planning suggestions.
    """

    if not isinstance(context, CalendarBusyContext):
        raise CalendarBusyError("Calendar busy context is required.")
    if not isinstance(minimum_duration, timedelta):
        raise CalendarBusyError("minimum_duration must be a timedelta.")
    if minimum_duration < MIN_FREE_WINDOW or minimum_duration > MAX_FREE_WINDOW:
        raise CalendarBusyError("minimum_duration must be between 5 minutes and 24 hours.")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > MAX_RETURNED_WINDOWS:
        raise CalendarBusyError("limit must be an integer between 1 and 32.")
    if context.starts_at.tzinfo is None or context.starts_at.utcoffset() is None:
        raise CalendarBusyError("Calendar busy context start must be timezone-aware.")
    if context.ends_at.tzinfo is None or context.ends_at.utcoffset() is None:
        raise CalendarBusyError("Calendar busy context end must be timezone-aware.")
    if context.ends_at <= context.starts_at:
        raise CalendarBusyError("Calendar busy context must have positive duration.")

    windows: list[FreeWindow] = []
    cursor = context.starts_at
    previous_end: datetime | None = None

    for index, interval in enumerate(context.intervals):
        if interval.starts_at.tzinfo is None or interval.starts_at.utcoffset() is None:
            raise CalendarBusyError(f"busy interval {index} start must be timezone-aware.")
        if interval.ends_at.tzinfo is None or interval.ends_at.utcoffset() is None:
            raise CalendarBusyError(f"busy interval {index} end must be timezone-aware.")
        if interval.ends_at <= interval.starts_at:
            raise CalendarBusyError(f"busy interval {index} must have positive duration.")
        if interval.starts_at < context.starts_at or interval.ends_at > context.ends_at:
            raise CalendarBusyError(f"busy interval {index} falls outside the planning range.")
        if previous_end is not None and interval.starts_at <= previous_end:
            raise CalendarBusyError("busy intervals must be strictly ordered and fully merged.")

        if interval.starts_at - cursor >= minimum_duration:
            windows.append(FreeWindow(cursor, interval.starts_at))
            if len(windows) >= limit:
                return tuple(windows)
        cursor = interval.ends_at
        previous_end = interval.ends_at

    if context.ends_at - cursor >= minimum_duration and len(windows) < limit:
        windows.append(FreeWindow(cursor, context.ends_at))

    return tuple(windows)
