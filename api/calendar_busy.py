"""Privacy-minimized Calendar busy-time consumer primitives for Tasks planning.

This module validates the GoreeCloud Calendar v1 busy-time projection without
introducing a network credential model. A future transport must provide an
already-authorized, owner-scoped payload; Tasks deliberately does not accept a
static cross-user Calendar credential here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence

BUSY_SCHEMA = "goreecloud.calendar.busy.v1"
BUSY_VERSION = 1
MAX_BUSY_INTERVALS = 512


class CalendarBusyPayloadError(ValueError):
    """Raised when Calendar busy-time data violates the reviewed contract."""


@dataclass(frozen=True, slots=True)
class BusyInterval:
    starts_at: datetime
    ends_at: datetime

    @property
    def duration(self) -> timedelta:
        return self.ends_at - self.starts_at


@dataclass(frozen=True, slots=True)
class PlanningAvailability:
    starts_at: datetime
    ends_at: datetime
    busy: tuple[BusyInterval, ...]

    @property
    def total_duration(self) -> timedelta:
        return self.ends_at - self.starts_at

    @property
    def busy_duration(self) -> timedelta:
        return sum((item.duration for item in self.busy), timedelta())

    @property
    def free_duration(self) -> timedelta:
        return self.total_duration - self.busy_duration


def _aware_datetime(value: object, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise CalendarBusyPayloadError(f"{field} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CalendarBusyPayloadError(f"{field} is not a valid ISO-8601 datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CalendarBusyPayloadError(f"{field} must include timezone information")
    return parsed


def _range(payload: Mapping[str, Any]) -> tuple[datetime, datetime]:
    raw_range = payload.get("range")
    if not isinstance(raw_range, Mapping):
        raise CalendarBusyPayloadError("busy payload range must be an object")
    starts_at = _aware_datetime(raw_range.get("starts_at"), field="range.starts_at")
    ends_at = _aware_datetime(raw_range.get("ends_at"), field="range.ends_at")
    if ends_at <= starts_at:
        raise CalendarBusyPayloadError("busy payload range must have positive duration")
    return starts_at, ends_at


def parse_busy_payload(payload: Mapping[str, Any]) -> PlanningAvailability:
    """Validate and normalize one privacy-minimized Calendar busy-time payload.

    Only schema/version/range/count and busy interval timestamps are accepted.
    Event titles, descriptions, locations, attendees, calendar names, and other
    content are intentionally outside this contract.
    """

    if payload.get("schema") != BUSY_SCHEMA or payload.get("version") != BUSY_VERSION:
        raise CalendarBusyPayloadError("unsupported Calendar busy-time contract")

    allowed_keys = {"schema", "version", "range", "returned", "busy"}
    if set(payload) - allowed_keys:
        raise CalendarBusyPayloadError("busy payload contains unreviewed fields")

    starts_at, ends_at = _range(payload)
    raw_busy = payload.get("busy")
    if not isinstance(raw_busy, Sequence) or isinstance(raw_busy, (str, bytes, bytearray)):
        raise CalendarBusyPayloadError("busy must be an array")
    if len(raw_busy) > MAX_BUSY_INTERVALS:
        raise CalendarBusyPayloadError("busy payload contains too many intervals")
    if payload.get("returned") != len(raw_busy):
        raise CalendarBusyPayloadError("busy payload count does not match returned")

    intervals: list[BusyInterval] = []
    previous_end: datetime | None = None
    for index, item in enumerate(raw_busy):
        if not isinstance(item, Mapping):
            raise CalendarBusyPayloadError(f"busy[{index}] must be an object")
        if set(item) != {"starts_at", "ends_at"}:
            raise CalendarBusyPayloadError(f"busy[{index}] contains unreviewed fields")
        interval_start = _aware_datetime(item.get("starts_at"), field=f"busy[{index}].starts_at")
        interval_end = _aware_datetime(item.get("ends_at"), field=f"busy[{index}].ends_at")
        if interval_end <= interval_start:
            raise CalendarBusyPayloadError(f"busy[{index}] must have positive duration")
        if interval_start < starts_at or interval_end > ends_at:
            raise CalendarBusyPayloadError(f"busy[{index}] escapes the requested range")
        if previous_end is not None and interval_start < previous_end:
            raise CalendarBusyPayloadError("busy intervals must be ordered and non-overlapping")
        intervals.append(BusyInterval(starts_at=interval_start, ends_at=interval_end))
        previous_end = interval_end

    return PlanningAvailability(
        starts_at=starts_at,
        ends_at=ends_at,
        busy=tuple(intervals),
    )
