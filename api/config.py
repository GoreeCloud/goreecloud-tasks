"""Environment and protected-file configuration for the Manager API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ManagerAPIConfiguration:
    enabled: bool
    username: str
    token: str | None
    max_tasks: int
    error: str | None = None


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def load_manager_api_configuration() -> ManagerAPIConfiguration:
    enabled = _enabled(os.getenv("TASKS_MANAGER_API_ENABLED"))
    username = os.getenv("TASKS_MANAGER_API_USERNAME", "").strip()
    direct_token = os.getenv("TASKS_MANAGER_API_TOKEN", "").strip()
    token_file = os.getenv("TASKS_MANAGER_API_TOKEN_FILE", "").strip()

    token: str | None = None
    error: str | None = None

    if direct_token and token_file:
        error = "Set only one Manager API token source."
    elif token_file:
        try:
            token = Path(token_file).read_text(encoding="utf-8").strip()
        except OSError:
            error = "The configured Manager API token file could not be read."
    elif direct_token:
        token = direct_token

    raw_max = os.getenv("TASKS_MANAGER_API_MAX_TASKS", "100").strip()
    try:
        max_tasks = int(raw_max)
    except ValueError:
        max_tasks = 100
        error = error or "TASKS_MANAGER_API_MAX_TASKS must be an integer."
    if not 1 <= max_tasks <= 500:
        max_tasks = 100
        error = error or "TASKS_MANAGER_API_MAX_TASKS must be between 1 and 500."

    if enabled:
        if not username:
            error = error or "TASKS_MANAGER_API_USERNAME is required when enabled."
        if not token:
            error = error or "A Manager API token is required when enabled."
        elif len(token) < 32:
            error = error or "The Manager API token must be at least 32 characters."

    return ManagerAPIConfiguration(
        enabled=enabled,
        username=username,
        token=token,
        max_tasks=max_tasks,
        error=error,
    )
