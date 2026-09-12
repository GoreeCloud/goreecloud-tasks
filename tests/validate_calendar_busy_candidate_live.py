#!/usr/bin/env python
"""Validate the Tasks busy client against the exact pinned Calendar provider source.

This is a disposable CI-only wire test. It binds the framework-neutral Calendar provider to a
loopback HTTP server with synthetic event data, then exercises the real Tasks urllib client.
No production Calendar service, identity, secret, network, or event data is used.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CALENDAR_SOURCE = Path(os.environ.get("CALENDAR_REPO_DIR", ROOT / "calendar-source")).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(CALENDAR_SOURCE))

from api.calendar_busy_client import CalendarBusyError, fetch_calendar_busy_context  # noqa: E402
from goreecloud_calendar.events import CalendarEvent  # noqa: E402
from goreecloud_calendar.integrations.tasks_busy_api import (  # noqa: E402
    TasksBusyAPIConfiguration,
    dispatch_tasks_busy_time,
)
from goreecloud_calendar.service import CalendarService  # noqa: E402

TOKEN = "tasks-calendar-live-contract-token-0123456789abcdef0123456789abcdef"
SUBJECT = "calendar-contract-user"
ALLOWED_HREFS = (
    "/calendars/calendar-contract-user/personal/",
    "/calendars/calendar-contract-user/work/",
)
OTHER_HREF = "/calendars/other/private/"
START = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
END = datetime(2026, 9, 4, 18, 0, tzinfo=timezone.utc)


class SyntheticCalendarStore:
    """Synthetic store containing deliberately sensitive content that must not cross the API."""

    def __init__(self) -> None:
        self.queries: list[str] = []
        self.events = {
            ALLOWED_HREFS[0]: (
                CalendarEvent(
                    uid="private-personal-event",
                    title="Synthetic private medical appointment",
                    starts_at=datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc),
                    ends_at=datetime(2026, 9, 4, 15, 0, tzinfo=timezone.utc),
                    description="synthetic private diagnosis",
                    location="synthetic private clinic",
                ),
            ),
            ALLOWED_HREFS[1]: (
                CalendarEvent(
                    uid="private-work-event",
                    title="Synthetic confidential meeting",
                    starts_at=datetime(2026, 9, 4, 14, 30, tzinfo=timezone.utc),
                    ends_at=datetime(2026, 9, 4, 16, 0, tzinfo=timezone.utc),
                    description="synthetic confidential agenda",
                    location="synthetic private office",
                ),
            ),
            OTHER_HREF: (
                CalendarEvent(
                    uid="other-user-event",
                    title="Synthetic other-user secret",
                    starts_at=datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc),
                    ends_at=datetime(2026, 9, 4, 13, 0, tzinfo=timezone.utc),
                ),
            ),
        }

    def query_events(self, *, calendar_href, starts_at, ends_at):
        self.queries.append(calendar_href)
        return tuple(
            event
            for event in self.events.get(calendar_href, ())
            if event.starts_at < ends_at and starts_at < event.ends_at
        )

    def put_event(self, *, calendar_href, event):
        raise AssertionError("busy-time wire validation must remain read-only")

    def delete_event(self, *, event_href, etag):
        raise AssertionError("busy-time wire validation must remain read-only")


STORE = SyntheticCalendarStore()
SERVICE = CalendarService(STORE)
CONFIG = TasksBusyAPIConfiguration(
    enabled=True,
    token=TOKEN,
    subject=SUBJECT,
    calendar_hrefs=ALLOWED_HREFS,
    max_window_minutes=31 * 24 * 60,
)


class Handler(BaseHTTPRequestHandler):
    def _dispatch(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/v1/tasks/busy-time":
            self.send_response(404)
            self.end_headers()
            return

        parsed_query = parse_qs(parsed.query, keep_blank_values=True)
        query: dict[str, str] = {}
        for key, values in parsed_query.items():
            if len(values) != 1:
                query[f"duplicate:{key}"] = ""
            else:
                query[key] = values[0]

        response = dispatch_tasks_busy_time(
            service=SERVICE,
            config=CONFIG,
            method=self.command,
            headers=dict(self.headers.items()),
            query=query,
            now=datetime(2026, 9, 3, 5, 5, tzinfo=timezone.utc),
        )
        self.send_response(response.status)
        for name, value in response.headers:
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(response.body)))
        self.end_headers()
        self.wfile.write(response.body)

    do_GET = _dispatch
    do_POST = _dispatch

    def log_message(self, format, *args):  # noqa: A003
        return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"

    try:
        context = fetch_calendar_busy_context(
            base_url=base_url,
            token=TOKEN,
            start=START,
            end=END,
            timeout_seconds=5,
        )
        assert context.starts_at == START
        assert context.ends_at == END
        assert len(context.intervals) == 1
        assert context.intervals[0].starts_at == datetime(
            2026, 9, 4, 14, 0, tzinfo=timezone.utc
        )
        assert context.intervals[0].ends_at == datetime(
            2026, 9, 4, 16, 0, tzinfo=timezone.utc
        )
        assert STORE.queries == list(ALLOWED_HREFS)
        assert OTHER_HREF not in STORE.queries

        query_count = len(STORE.queries)
        try:
            fetch_calendar_busy_context(
                base_url=base_url,
                token="wrong-token-but-long-enough-0123456789abcdef0123456789abcdef",
                start=START,
                end=END,
            )
        except CalendarBusyError as exc:
            assert "HTTP 401" in str(exc)
        else:
            raise AssertionError("wrong Calendar peer credential was accepted")
        assert len(STORE.queries) == query_count

        selector_url = base_url + "/api/v1/tasks/busy-time?" + urlencode(
            {
                "starts_at": START.isoformat(),
                "ends_at": END.isoformat(),
                "subject": "other",
            }
        )
        selector_request = Request(
            selector_url,
            method="GET",
            headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"},
        )
        try:
            urlopen(selector_request, timeout=5)
        except HTTPError as exc:
            assert exc.code == 400
            body = exc.read().decode("utf-8")
            assert json.loads(body) == {"error": "invalid_request"}
            assert "other" not in body
        else:
            raise AssertionError("request-selected Calendar subject was accepted")
        assert len(STORE.queries) == query_count

        print(
            "Validated live Calendar busy-time contract: fixed provider scope, merged "
            "privacy-minimized intervals, strict Tasks parsing, bearer rejection, and "
            "request-selector denial."
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
