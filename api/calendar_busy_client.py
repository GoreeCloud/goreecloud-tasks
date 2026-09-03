"""Strict read-only consumer for GoreeCloud Calendar busy-time context.

GoreeCloud Tasks uses this module only to obtain privacy-minimized busy intervals for planning.
Calendar remains authoritative for native events and event authorization. The client never
receives event titles, descriptions, locations, collection identifiers, or Calendar subjects.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

SCHEMA = "goreecloud.calendar.tasks-busy.v1"
VERSION = 1
MAX_WINDOW = timedelta(days=31)
MAX_RESPONSE_BYTES = 512 * 1024
_EXPECTED_ROOT_FIELDS = frozenset(
    {"schema", "version", "generated_at", "range", "returned", "busy"}
)
_EXPECTED_RANGE_FIELDS = frozenset({"starts_at", "ends_at"})
_EXPECTED_INTERVAL_FIELDS = frozenset({"starts_at", "ends_at"})
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class CalendarBusyError(RuntimeError):
    """Raised when Calendar cannot provide trustworthy busy-time context."""


@dataclass(frozen=True, slots=True)
class BusyInterval:
    """One Calendar-authoritative busy interval with no event-content metadata."""

    starts_at: datetime
    ends_at: datetime


@dataclass(frozen=True, slots=True)
class CalendarBusyContext:
    """Validated Calendar busy context for one requested planning window."""

    generated_at: datetime
    starts_at: datetime
    ends_at: datetime
    intervals: tuple[BusyInterval, ...]


def _require_dict(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CalendarBusyError(f"{field} must be an object.")
    return value


def _require_exact_fields(
    value: dict[str, Any], expected: frozenset[str], field: str
) -> None:
    if set(value) != expected:
        raise CalendarBusyError(f"{field} contains an unsupported field set.")


def _parse_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise CalendarBusyError(f"{field} must be a non-empty timestamp string.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise CalendarBusyError(f"{field} is not a valid ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CalendarBusyError(f"{field} must include timezone information.")
    return parsed


def _require_aware_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise CalendarBusyError(f"{field} must be a datetime.")
    if value.tzinfo is None or value.utcoffset() is None:
        raise CalendarBusyError(f"{field} must include timezone information.")
    return value


def _validate_window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    start = _require_aware_datetime(start, "start")
    end = _require_aware_datetime(end, "end")
    if end <= start:
        raise CalendarBusyError("end must be later than start.")
    if end - start > MAX_WINDOW:
        raise CalendarBusyError("The Calendar busy-time window cannot exceed 31 days.")
    return start, end


def _normalize_base_url(base_url: str) -> str:
    if not isinstance(base_url, str) or not base_url.strip():
        raise CalendarBusyError("Calendar base URL is required.")
    value = base_url.strip().rstrip("/")
    parsed = urlparse(value)
    if not parsed.netloc or parsed.scheme not in {"http", "https"}:
        raise CalendarBusyError("Calendar base URL must be an absolute HTTP(S) URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise CalendarBusyError("Calendar base URL contains unsupported URL components.")
    if parsed.scheme == "http" and parsed.hostname not in _LOOPBACK_HOSTS:
        raise CalendarBusyError(
            "Calendar base URL must use HTTPS except for loopback validation."
        )
    return value


def _validate_transport_inputs(
    *, base_url: str, token: str, timeout_seconds: float
) -> tuple[str, str]:
    base = _normalize_base_url(base_url)
    if not isinstance(token, str) or not 32 <= len(token.strip()) <= 512:
        raise CalendarBusyError("Calendar integration token is invalid.")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
        raise CalendarBusyError("timeout_seconds must be numeric.")
    if timeout_seconds <= 0 or timeout_seconds > 30:
        raise CalendarBusyError("timeout_seconds must be greater than zero and at most 30.")
    return base, token.strip()


def parse_busy_payload(
    payload: Any,
    *,
    expected_start: datetime | None = None,
    expected_end: datetime | None = None,
) -> CalendarBusyContext:
    """Validate one complete Calendar-to-Tasks busy-time response.

    The v1 peer contract deliberately uses an exact field allowlist so an upstream response
    containing event content or identity/collection metadata cannot silently become trusted
    Tasks planning input. Such additions require an explicit contract revision.
    """

    root = _require_dict(payload, "payload")
    _require_exact_fields(root, _EXPECTED_ROOT_FIELDS, "payload")
    if root.get("schema") != SCHEMA:
        raise CalendarBusyError("Unsupported GoreeCloud Calendar busy-time schema.")
    if root.get("version") != VERSION:
        raise CalendarBusyError("Unsupported GoreeCloud Calendar busy-time version.")

    generated_at = _parse_datetime(root.get("generated_at"), "generated_at")
    range_value = _require_dict(root.get("range"), "range")
    _require_exact_fields(range_value, _EXPECTED_RANGE_FIELDS, "range")
    starts_at = _parse_datetime(range_value.get("starts_at"), "range.starts_at")
    ends_at = _parse_datetime(range_value.get("ends_at"), "range.ends_at")
    if ends_at <= starts_at:
        raise CalendarBusyError("Calendar busy-time range must have positive duration.")
    if ends_at - starts_at > MAX_WINDOW:
        raise CalendarBusyError("Calendar busy-time response range exceeds 31 days.")

    if expected_start is not None or expected_end is not None:
        if expected_start is None or expected_end is None:
            raise CalendarBusyError(
                "expected_start and expected_end must be supplied together."
            )
        expected_start, expected_end = _validate_window(expected_start, expected_end)
        if starts_at != expected_start or ends_at != expected_end:
            raise CalendarBusyError(
                "Calendar busy-time response range does not match the requested range."
            )

    raw_busy = root.get("busy")
    if not isinstance(raw_busy, list):
        raise CalendarBusyError("busy must be an array.")
    returned = root.get("returned")
    if not isinstance(returned, int) or isinstance(returned, bool) or returned < 0:
        raise CalendarBusyError("returned must be a non-negative integer.")
    if returned != len(raw_busy):
        raise CalendarBusyError("returned does not match the busy interval count.")

    intervals: list[BusyInterval] = []
    previous_end: datetime | None = None
    for index, raw_interval in enumerate(raw_busy):
        interval_value = _require_dict(raw_interval, f"busy[{index}]")
        _require_exact_fields(
            interval_value, _EXPECTED_INTERVAL_FIELDS, f"busy[{index}]"
        )
        interval_start = _parse_datetime(
            interval_value.get("starts_at"), f"busy[{index}].starts_at"
        )
        interval_end = _parse_datetime(
            interval_value.get("ends_at"), f"busy[{index}].ends_at"
        )
        if interval_end <= interval_start:
            raise CalendarBusyError(f"busy[{index}] must have positive duration.")
        if interval_start < starts_at or interval_end > ends_at:
            raise CalendarBusyError(f"busy[{index}] falls outside the response range.")
        # Calendar's provider emits fully merged intervals. Touching or overlapping output
        # therefore indicates an ambiguous/non-canonical response and fails closed.
        if previous_end is not None and interval_start <= previous_end:
            raise CalendarBusyError(
                "busy intervals must be strictly ordered and fully merged."
            )
        intervals.append(BusyInterval(interval_start, interval_end))
        previous_end = interval_end

    return CalendarBusyContext(
        generated_at=generated_at,
        starts_at=starts_at,
        ends_at=ends_at,
        intervals=tuple(intervals),
    )


def _decode_json_body(body: bytes) -> Any:
    if len(body) > MAX_RESPONSE_BYTES:
        raise CalendarBusyError("GoreeCloud Calendar returned an oversized response.")
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CalendarBusyError("GoreeCloud Calendar returned invalid JSON.") from exc


def fetch_calendar_busy_context(
    *,
    base_url: str,
    token: str,
    start: datetime,
    end: datetime,
    timeout_seconds: float = 5.0,
) -> CalendarBusyContext:
    """Fetch one bounded privacy-minimized busy-time window from Calendar."""

    base, normalized_token = _validate_transport_inputs(
        base_url=base_url,
        token=token,
        timeout_seconds=timeout_seconds,
    )
    start, end = _validate_window(start, end)
    endpoint = base + "/api/v1/tasks/busy-time?" + urlencode(
        {"starts_at": start.isoformat(), "ends_at": end.isoformat()}
    )
    request = Request(
        endpoint,
        method="GET",
        headers={
            "Authorization": f"Bearer {normalized_token}",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise CalendarBusyError(
            f"GoreeCloud Calendar rejected the busy-time request with HTTP {exc.code}."
        ) from exc
    except URLError as exc:
        raise CalendarBusyError("GoreeCloud Calendar is unreachable.") from exc

    payload = _decode_json_body(body)
    return parse_busy_payload(
        payload,
        expected_start=start,
        expected_end=end,
    )
