#!/usr/bin/env python3
"""Assertions for the disposable production-pattern Tasks -> Manager topology.

The script runs inside the GoreeCloud Manager container. It exercises Manager's real
``integrations.tasks`` adapter over the dedicated ``manager-tasks`` Docker network and
checks the authenticated Manager Tasks page without publishing either application to a host
port.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP_ROOT = Path("/app")
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import httpx

from integrations.tasks import MANAGER_API_PATH, tasks_snapshot

INTEGRATION_USERNAME = "goreecloud-manager-integration"
VISIBLE_TASK_TITLE = "Validate Manager cross-application recovery visibility"
SENSITIVE_DESCRIPTION = "MANAGER-E2E-SENSITIVE-DESCRIPTION-MUST-NOT-LEAK"
SENSITIVE_COMMENT = "MANAGER-E2E-SENSITIVE-COMMENT-MUST-NOT-LEAK"
FORBIDDEN_TITLES = (
    "Manager E2E ordinary shared task",
    "Manager E2E private operational task",
    "Manager E2E integration personal task",
    "Manager E2E owner personal task",
    "Manager E2E completed operational task",
    "Manager E2E outsider personal task",
)
EXPECTED_TASK_KEYS = {
    "id",
    "title",
    "project",
    "priority",
    "status",
    "due_at",
    "assigned_system",
    "assigned_service",
    "environment",
    "workload_category",
    "blocker",
    "resume_condition",
    "requirements",
    "related_change_record",
    "related_documentation",
    "updated_at",
}


def _token() -> str:
    direct = os.getenv("TASKS_ACCESS_TOKEN", "").strip()
    assert not direct, "Final-topology validation unexpectedly received a direct Tasks token."
    path = Path(os.environ["TASKS_ACCESS_TOKEN_FILE"])
    token = path.read_text(encoding="utf-8").strip()
    assert len(token) >= 32, "Mounted Tasks token is unexpectedly short."
    return token


def _api_url() -> str:
    return os.environ["TASKS_API_URL"].rstrip("/") + MANAGER_API_PATH


def _headers(token: str | None = None) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {token or _token()}",
    }


def _raw_payload() -> tuple[httpx.Response, dict]:
    response = httpx.get(_api_url(), headers=_headers(), timeout=5.0)
    response.raise_for_status()
    return response, response.json()


def _assert_manager_health() -> None:
    response = httpx.get("http://127.0.0.1:8000/healthz/", timeout=5.0)
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok", "service": "goreecloud-manager"}


def _assert_manager_web(*, expect_task: bool) -> None:
    username = os.environ["MANAGER_WEB_USERNAME"]
    password = os.environ["MANAGER_WEB_PASSWORD"]
    base_url = "http://127.0.0.1:8000"

    with httpx.Client(base_url=base_url, follow_redirects=True, timeout=5.0) as client:
        login = client.get("/login/")
        assert login.status_code == 200, login.text
        match = re.search(
            r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)',
            login.text,
        )
        assert match, "Manager login page did not provide a CSRF token."

        authenticated = client.post(
            "/login/",
            data={
                "username": username,
                "password": password,
                "csrfmiddlewaretoken": match.group(1),
                "next": "/tasks/",
            },
            headers={"Referer": f"{base_url}/login/"},
        )
        assert authenticated.status_code == 200, authenticated.text

        page = client.get("/tasks/")
        assert page.status_code == 200, page.text
        if expect_task:
            assert VISIBLE_TASK_TITLE in page.text
        else:
            assert VISIBLE_TASK_TITLE not in page.text
        assert SENSITIVE_DESCRIPTION not in page.text
        assert SENSITIVE_COMMENT not in page.text
        for title in FORBIDDEN_TITLES:
            assert title not in page.text


def _assert_schema_fail_soft(payload: dict) -> None:
    invalid = json.loads(json.dumps(payload))
    invalid["version"] = 999
    encoded = json.dumps(invalid).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib callback name
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format, *args):  # noqa: A003 - stdlib callback name
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original_url = os.environ["TASKS_API_URL"]
    try:
        os.environ["TASKS_API_URL"] = f"http://127.0.0.1:{server.server_port}"
        snapshot = tasks_snapshot()
        assert snapshot.state == "unavailable", snapshot
        assert "could not safely interpret" in snapshot.detail
    finally:
        os.environ["TASKS_API_URL"] = original_url
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _assert_fail_soft(payload: dict) -> None:
    original_enabled = os.environ.get("TASKS_ENABLED", "")
    original_file = os.environ.get("TASKS_ACCESS_TOKEN_FILE", "")
    original_direct = os.environ.get("TASKS_ACCESS_TOKEN")
    original_url = os.environ.get("TASKS_API_URL", "")

    try:
        os.environ["TASKS_ENABLED"] = "false"
        disabled = tasks_snapshot()
        assert disabled.state == "disabled", disabled

        os.environ["TASKS_ENABLED"] = "true"
        os.environ["TASKS_ACCESS_TOKEN_FILE"] = "/tmp/manager-final-topology-missing-token"
        missing = tasks_snapshot()
        assert missing.state == "misconfigured", missing
        assert "could not be read" in missing.detail

        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False) as handle:
            empty_path = handle.name
        try:
            os.environ["TASKS_ACCESS_TOKEN_FILE"] = empty_path
            empty = tasks_snapshot()
            assert empty.state == "misconfigured", empty
            assert "empty" in empty.detail
        finally:
            Path(empty_path).unlink(missing_ok=True)

        os.environ["TASKS_ACCESS_TOKEN_FILE"] = ""
        os.environ["TASKS_ACCESS_TOKEN"] = "manager-final-topology-deliberately-wrong-token-value"
        rejected = tasks_snapshot()
        assert rejected.state == "unavailable", rejected
        assert "rejected the configured integration credential" in rejected.detail

        os.environ.pop("TASKS_ACCESS_TOKEN", None)
        os.environ["TASKS_ACCESS_TOKEN_FILE"] = original_file
        os.environ["TASKS_API_URL"] = "http://127.0.0.1:1"
        unavailable = tasks_snapshot()
        assert unavailable.state == "unavailable", unavailable
        assert "could not reach" in unavailable.detail or "did not respond" in unavailable.detail

        os.environ["TASKS_API_URL"] = original_url
        _assert_schema_fail_soft(payload)
    finally:
        os.environ["TASKS_ENABLED"] = original_enabled
        os.environ["TASKS_ACCESS_TOKEN_FILE"] = original_file
        os.environ["TASKS_API_URL"] = original_url
        if original_direct is None:
            os.environ.pop("TASKS_ACCESS_TOKEN", None)
        else:
            os.environ["TASKS_ACCESS_TOKEN"] = original_direct

    _assert_manager_health()


def assert_visible(*, include_fail_soft: bool) -> None:
    snapshot = tasks_snapshot()
    assert snapshot.state == "healthy", snapshot
    assert snapshot.identity == INTEGRATION_USERNAME
    assert snapshot.total_open == 1
    assert snapshot.blocked == 1
    assert snapshot.p0 == 0
    assert snapshot.p1 == 1
    assert snapshot.returned == 1
    assert snapshot.tasks[0].title == VISIBLE_TASK_TITLE
    assert snapshot.tasks[0].assigned_service == "GoreeCloud Manager"

    response, payload = _raw_payload()
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert "Authorization" in response.headers.get("Vary", "")
    assert payload["schema"] == "goreecloud.tasks.manager.v1"
    assert payload["version"] == 1
    assert payload["authorization"]["identity"] == INTEGRATION_USERNAME
    assert payload["summary"] == {
        "total_open": 1,
        "blocked": 1,
        "p0": 0,
        "p1": 1,
        "returned": 1,
    }
    assert len(payload["tasks"]) == 1
    task = payload["tasks"][0]
    assert task["title"] == VISIBLE_TASK_TITLE
    assert set(task) == EXPECTED_TASK_KEYS
    for forbidden in ("description", "comments", "labels", "creator", "assignee"):
        assert forbidden not in task

    serialized = json.dumps(payload)
    assert SENSITIVE_DESCRIPTION not in serialized
    assert SENSITIVE_COMMENT not in serialized
    for title in FORBIDDEN_TITLES:
        assert title not in serialized

    wrong = httpx.get(
        _api_url(),
        headers=_headers("manager-final-topology-deliberately-wrong-token-value"),
        timeout=5.0,
    )
    assert wrong.status_code == 401, wrong.text
    assert wrong.json() == {"detail": "Authentication required."}

    write_attempt = httpx.post(_api_url(), headers=_headers(), timeout=5.0)
    assert write_attempt.status_code == 405, write_attempt.text

    _assert_manager_health()
    _assert_manager_web(expect_task=True)
    if include_fail_soft:
        _assert_fail_soft(payload)
    print("Final-topology visible-scope assertions passed.")


def assert_revoked() -> None:
    snapshot = tasks_snapshot()
    assert snapshot.state == "healthy", snapshot
    assert snapshot.identity == INTEGRATION_USERNAME
    assert snapshot.total_open == 0
    assert snapshot.returned == 0
    assert snapshot.tasks == ()

    _, payload = _raw_payload()
    assert payload["summary"]["total_open"] == 0
    assert payload["summary"]["returned"] == 0
    assert payload["tasks"] == []
    assert VISIBLE_TASK_TITLE not in json.dumps(payload)
    _assert_manager_health()
    _assert_manager_web(expect_task=False)
    print("Final-topology membership-revocation assertions passed.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("healthy", "revoked", "restored"))
    args = parser.parse_args()
    if args.phase == "healthy":
        assert_visible(include_fail_soft=True)
    elif args.phase == "revoked":
        assert_revoked()
    else:
        assert_visible(include_fail_soft=False)


if __name__ == "__main__":
    main()
