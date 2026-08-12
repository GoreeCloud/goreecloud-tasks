#!/usr/bin/env python3
"""Assertions for the live GoreeCloud Tasks -> Manager integration contract.

Run this script with the GoreeCloud Manager virtual environment and Manager repository on
``PYTHONPATH`` while disposable Tasks and Manager web processes are running.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx

from integrations.tasks import (
    MANAGER_API_PATH,
    TasksProtocolError,
    _healthy_snapshot,
    tasks_snapshot,
)

INTEGRATION_USERNAME = "goreecloud-manager-integration"
VISIBLE_TASK_TITLE = "Validate Manager cross-application recovery visibility"
SENSITIVE_DESCRIPTION = "MANAGER-E2E-SENSITIVE-DESCRIPTION-MUST-NOT-LEAK"
SENSITIVE_COMMENT = "MANAGER-E2E-SENSITIVE-COMMENT-MUST-NOT-LEAK"
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


def _api_url() -> str:
    return os.environ["TASKS_API_URL"].rstrip("/") + MANAGER_API_PATH


def _headers(token: str | None = None) -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {token or os.environ['TASKS_ACCESS_TOKEN']}",
    }


def _raw_payload() -> tuple[httpx.Response, dict]:
    response = httpx.get(_api_url(), headers=_headers(), timeout=5.0)
    response.raise_for_status()
    return response, response.json()


def _assert_manager_web(*, expect_task: bool) -> None:
    base_url = os.environ.get("MANAGER_BASE_URL", "http://127.0.0.1:18090").rstrip("/")
    username = os.environ["MANAGER_WEB_USERNAME"]
    password = os.environ["MANAGER_WEB_PASSWORD"]

    with httpx.Client(base_url=base_url, follow_redirects=True, timeout=5.0) as client:
        health = client.get("/healthz/")
        assert health.status_code == 200, health.text
        assert health.json() == {"status": "ok", "service": "goreecloud-manager"}

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


def _assert_invalid_schema_is_fail_soft(payload: dict) -> None:
    invalid = json.loads(json.dumps(payload))
    invalid["version"] = 999
    encoded = json.dumps(invalid).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib HTTP handler API
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format, *args):  # noqa: A003 - stdlib API name
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


def assert_healthy() -> None:
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
    assert snapshot.tasks[0].environment == "disposable-ci"

    response, payload = _raw_payload()
    assert response.headers.get("Cache-Control") == "private, no-store"
    assert "Authorization" in response.headers.get("Vary", "")
    assert payload["schema"] == "goreecloud.tasks.manager.v1"
    assert payload["version"] == 1
    assert payload["authorization"]["identity"] == INTEGRATION_USERNAME
    assert payload["authorization"]["scope"] == "visible operational project tasks only"
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
    assert "Manager E2E ordinary shared task" not in serialized
    assert "Manager E2E private operational task" not in serialized
    assert "Manager E2E integration personal task" not in serialized
    assert "Manager E2E completed operational task" not in serialized
    assert "Manager E2E outsider personal task" not in serialized

    wrong = httpx.get(
        _api_url(),
        headers=_headers("manager-e2e-deliberately-wrong-token"),
        timeout=5.0,
    )
    assert wrong.status_code == 401
    assert wrong.json() == {"detail": "Authentication required."}

    original_token = os.environ["TASKS_ACCESS_TOKEN"]
    try:
        os.environ["TASKS_ACCESS_TOKEN"] = "manager-e2e-deliberately-wrong-token"
        rejected = tasks_snapshot()
        assert rejected.state == "unavailable", rejected
        assert "rejected the configured integration credential" in rejected.detail
    finally:
        os.environ["TASKS_ACCESS_TOKEN"] = original_token

    # Validate Manager's protocol boundary against a mutated copy of the real live payload.
    invalid = json.loads(json.dumps(payload))
    invalid["schema"] = "goreecloud.tasks.manager.unsupported"
    try:
        _healthy_snapshot(invalid)
    except TasksProtocolError:
        pass
    else:
        raise AssertionError("Manager accepted an unsupported Tasks API schema.")
    _assert_invalid_schema_is_fail_soft(payload)

    _assert_manager_web(expect_task=True)
    print("Healthy Manager cross-application integration assertions passed.")


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

    _assert_manager_web(expect_task=False)
    print("Membership-revocation Manager cross-application assertions passed.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("healthy", "revoked"))
    args = parser.parse_args()
    if args.phase == "healthy":
        assert_healthy()
    else:
        assert_revoked()


if __name__ == "__main__":
    main()
