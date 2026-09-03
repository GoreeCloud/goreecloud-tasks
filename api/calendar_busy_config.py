"""Environment and protected-file configuration for Calendar busy-time reads."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


@dataclass(frozen=True, slots=True)
class CalendarBusyClientConfiguration:
    """Validated Tasks-side configuration for privacy-minimized Calendar context."""

    enabled: bool
    base_url: str = ""
    token: str = ""
    timeout_seconds: int = 5
    error: str | None = None


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _protected_secret(path_value: str) -> str:
    path = Path(path_value)
    try:
        info = path.stat()
    except OSError as exc:
        raise ValueError("configured Calendar busy token file is unavailable") from exc
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("configured Calendar busy token path is not a regular file")
    if info.st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ValueError("configured Calendar busy token file permissions are too broad")
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ValueError("configured Calendar busy token file is unreadable") from exc


def _valid_base_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return False
    if parsed.scheme == "http" and parsed.hostname not in _LOOPBACK_HOSTS:
        return False
    return True


def load_calendar_busy_client_configuration(
    environment: Mapping[str, str] | None = None,
) -> CalendarBusyClientConfiguration:
    """Load the optional outgoing Calendar busy-time client configuration.

    The Calendar provider, not this client, owns the subject and collection authorization
    mapping. Tasks therefore stores no Calendar subject or collection selector in this
    configuration and cannot widen the peer-service scope through request data.
    """

    env = os.environ if environment is None else environment
    enabled = _enabled(env.get("TASKS_CALENDAR_BUSY_ENABLED"))
    if not enabled:
        return CalendarBusyClientConfiguration(enabled=False)

    errors: list[str] = []
    base_url = env.get("TASKS_CALENDAR_BUSY_BASE_URL", "").strip().rstrip("/")
    if not base_url or not _valid_base_url(base_url):
        errors.append(
            "TASKS_CALENDAR_BUSY_BASE_URL must be an absolute HTTPS URL or loopback HTTP URL"
        )

    direct_token = env.get("TASKS_CALENDAR_BUSY_TOKEN", "").strip()
    token_file = env.get("TASKS_CALENDAR_BUSY_TOKEN_FILE", "").strip()
    token = ""
    if direct_token and token_file:
        errors.append("set only one Calendar busy token source")
    elif token_file:
        try:
            token = _protected_secret(token_file)
        except ValueError as exc:
            errors.append(str(exc))
    else:
        token = direct_token

    if not 32 <= len(token) <= 512:
        errors.append("Calendar busy token must contain 32 to 512 characters")

    raw_timeout = env.get("TASKS_CALENDAR_BUSY_TIMEOUT_SECONDS", "5").strip()
    try:
        timeout_seconds = int(raw_timeout)
    except ValueError:
        timeout_seconds = 5
        errors.append("TASKS_CALENDAR_BUSY_TIMEOUT_SECONDS must be an integer")
    if not 1 <= timeout_seconds <= 30:
        errors.append("TASKS_CALENDAR_BUSY_TIMEOUT_SECONDS must be between 1 and 30")

    return CalendarBusyClientConfiguration(
        enabled=True,
        base_url=base_url,
        token=token,
        timeout_seconds=timeout_seconds,
        error="; ".join(errors) if errors else None,
    )
