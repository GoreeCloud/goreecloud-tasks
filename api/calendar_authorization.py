"""Fail-closed delegated authorization gate for future Tasks→Calendar busy-time requests.

The gate accepts only already-validated identity claims. It deliberately does not model, store,
or mint bearer tokens, cookies, static service credentials, or Calendar database credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

CALENDAR_BUSY_AUDIENCE = "goreecloud-calendar-busy"
CALENDAR_BUSY_SCOPE = "calendar.busy.read"
MAX_REVIEWED_SCOPES = 16


class CalendarDelegatedAuthorizationError(PermissionError):
    """Raised when the reviewed delegated Calendar authorization contract is not satisfied."""


@dataclass(frozen=True, slots=True)
class CalendarDelegatedAuthorization:
    owner_id: str
    audience: str
    scopes: frozenset[str]
    expires_at: datetime

    def __post_init__(self) -> None:
        owner_id = self.owner_id.strip()
        audience = self.audience.strip()
        if not owner_id:
            raise ValueError("delegated Calendar owner is required")
        if not audience:
            raise ValueError("delegated Calendar audience is required")
        if not self.scopes or len(self.scopes) > MAX_REVIEWED_SCOPES:
            raise ValueError("delegated Calendar scopes are outside the reviewed bound")
        if any(not isinstance(scope, str) or not scope.strip() for scope in self.scopes):
            raise ValueError("delegated Calendar scopes must be non-empty strings")
        if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
            raise ValueError("delegated Calendar expiry must include timezone information")
        object.__setattr__(self, "owner_id", owner_id)
        object.__setattr__(self, "audience", audience)
        object.__setattr__(self, "scopes", frozenset(scope.strip() for scope in self.scopes))
        object.__setattr__(self, "expires_at", self.expires_at.astimezone(timezone.utc))


def require_calendar_busy_authorization(
    task_owner_id: str,
    authorization: CalendarDelegatedAuthorization | None,
    *,
    now: datetime,
) -> None:
    """Require same-owner, audience-bound, scoped, unexpired delegated identity context.

    Success only means that a future transport is allowed to *attempt* the reviewed busy-time
    request. It does not itself perform network I/O or establish that Calendar accepted a request.
    """

    task_owner_id = task_owner_id.strip()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("authorization check time must include timezone information")
    checked_at = now.astimezone(timezone.utc)

    if (
        not task_owner_id
        or authorization is None
        or authorization.owner_id != task_owner_id
        or authorization.audience != CALENDAR_BUSY_AUDIENCE
        or CALENDAR_BUSY_SCOPE not in authorization.scopes
        or authorization.expires_at <= checked_at
    ):
        raise CalendarDelegatedAuthorizationError("Calendar busy-time authorization unavailable")
