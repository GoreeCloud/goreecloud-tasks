"""Environment and protected-file configuration for the Calendar projection API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CalendarAPIConfiguration:
    enabled: bool
    username: str
    token: str | None
    max_tasks: int
    error: str | None = None


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def load_calendar_api_configuration() -> CalendarAPIConfiguration:
    """Load one authorization principal for the initial Calendar integration.

    This foundation deliberately maps one bearer credential to exactly one existing Tasks
    account. The caller cannot choose a username or user ID in the request. A future
    multi-user deployment may replace this configuration shape with individually scoped
    integration credentials or GoreeCloud Identity, but must preserve the same principal
    binding and authorization rules.
    """

    enabled = _enabled(os.getenv("TASKS_CALENDAR_API_ENABLED"))
    username = os.getenv("TASKS_CALENDAR_API_USERNAME", "").strip()
    direct_token = os.getenv("TASKS_CALENDAR_API_TOKEN", "").strip()
    token_file = os.getenv("TASKS_CALENDAR_API_TOKEN_FILE", "").strip()

    token: str | None = None
    error: str | None = None

    if direct_token and token_file:
        error = "Set only one Calendar API token source."
    elif token_file:
        try:
            token = Path(token_file).read_text(encoding="utf-8").strip()
        except OSError:
            error = "The configured Calendar API token file could not be read."
    elif direct_token:
        token = direct_token

    raw_max = os.getenv("TASKS_CALENDAR_API_MAX_TASKS", "500").strip()
    try:
        max_tasks = int(raw_max)
    except ValueError:
        max_tasks = 500
        error = error or "TASKS_CALENDAR_API_MAX_TASKS must be an integer."
    if not 1 <= max_tasks <= 2000:
        max_tasks = 500
        error = error or "TASKS_CALENDAR_API_MAX_TASKS must be between 1 and 2000."

    if enabled:
        if not username:
            error = error or "TASKS_CALENDAR_API_USERNAME is required when enabled."
        if not token:
            error = error or "A Calendar API token is required when enabled."
        elif len(token) < 32:
            error = error or "The Calendar API token must be at least 32 characters."

    return CalendarAPIConfiguration(
        enabled=enabled,
        username=username,
        token=token,
        max_tasks=max_tasks,
        error=error,
    )
