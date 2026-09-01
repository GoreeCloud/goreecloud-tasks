"""Transport-neutral request planning for authorized Tasks→Calendar busy-time context.

This module deliberately performs no network I/O and carries no credential material. It converts
an already-reviewed delegated authorization decision plus a bounded Calendar selection/window into
the exact method/path/query shape expected by GoreeCloud Calendar's busy-time API.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from api.calendar_authorization import (
    CalendarDelegatedAuthorization,
    require_calendar_busy_authorization,
)

CALENDAR_BUSY_PATH = "/api/v1/busy-time"


@dataclass(frozen=True, slots=True)
class CalendarBusyRequestPlan:
    """Credential-free metadata for one future authorized Calendar busy-time request."""

    method: str
    path: str
    query: tuple[tuple[str, str], ...]

    def query_dict(self) -> dict[str, str]:
        return dict(self.query)


def _aware(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must include timezone information")
    return value


def plan_calendar_busy_request(
    *,
    task_owner_id: str,
    authorization: CalendarDelegatedAuthorization | None,
    calendar_href: str,
    starts_at: datetime,
    ends_at: datetime,
    now: datetime,
) -> CalendarBusyRequestPlan:
    """Build the reviewed Calendar busy request shape after delegated authorization succeeds.

    The returned plan contains no owner identity, bearer token, cookie, service credential,
    Radicale credential, or other authentication material. A separately approved transport may
    consume this metadata only after it establishes the delegated identity context independently.
    """

    require_calendar_busy_authorization(task_owner_id, authorization, now=now)

    if not isinstance(calendar_href, str) or not calendar_href.strip():
        raise ValueError("Calendar reference is required")
    normalized_calendar = calendar_href.strip()
    starts_at = _aware(starts_at, field="Calendar busy start")
    ends_at = _aware(ends_at, field="Calendar busy end")
    if ends_at <= starts_at:
        raise ValueError("Calendar busy window must have positive duration")

    return CalendarBusyRequestPlan(
        method="GET",
        path=CALENDAR_BUSY_PATH,
        query=(
            ("calendar", normalized_calendar),
            ("starts_at", starts_at.isoformat()),
            ("ends_at", ends_at.isoformat()),
        ),
    )
