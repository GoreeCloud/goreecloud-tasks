"""Strict contract tests for Tasks consumption of Calendar busy-time context."""

from __future__ import annotations

import io
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

from django.test import SimpleTestCase

from api.calendar_busy_client import (
    MAX_RESPONSE_BYTES,
    CalendarBusyError,
    fetch_calendar_busy_context,
    parse_busy_payload,
)
from api.calendar_busy_config import load_calendar_busy_client_configuration

TOKEN = "tasks-calendar-busy-test-token-0123456789abcdef0123456789abcdef"
START = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)
END = datetime(2026, 9, 4, 18, 0, tzinfo=timezone.utc)


def valid_payload():
    return {
        "schema": "goreecloud.calendar.tasks-busy.v1",
        "version": 1,
        "generated_at": "2026-09-03T05:00:00+00:00",
        "range": {
            "starts_at": START.isoformat(),
            "ends_at": END.isoformat(),
        },
        "returned": 2,
        "busy": [
            {
                "starts_at": "2026-09-04T11:00:00+00:00",
                "ends_at": "2026-09-04T12:00:00+00:00",
            },
            {
                "starts_at": "2026-09-04T14:00:00+00:00",
                "ends_at": "2026-09-04T16:00:00+00:00",
            },
        ],
    }


class FakeHTTPResponse:
    def __init__(self, payload: object):
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, amount=-1):
        return self.body if amount < 0 else self.body[:amount]


class CalendarBusyParserTests(SimpleTestCase):
    def test_valid_minimized_payload_is_normalized(self):
        context = parse_busy_payload(
            valid_payload(), expected_start=START, expected_end=END
        )
        self.assertEqual(context.starts_at, START)
        self.assertEqual(context.ends_at, END)
        self.assertEqual(len(context.intervals), 2)
        self.assertEqual(
            context.intervals[1].starts_at,
            datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc),
        )

    def test_schema_version_count_and_exact_field_set_fail_closed(self):
        cases = []
        payload = valid_payload()
        payload["schema"] = "unexpected.schema"
        cases.append(payload)
        payload = valid_payload()
        payload["version"] = 2
        cases.append(payload)
        payload = valid_payload()
        payload["returned"] = 99
        cases.append(payload)
        payload = valid_payload()
        payload["subject"] = "alice"
        cases.append(payload)
        payload = valid_payload()
        payload["busy"][0]["title"] = "must never become trusted planning data"
        cases.append(payload)
        payload = valid_payload()
        payload["range"]["calendar"] = "private"
        cases.append(payload)

        for payload in cases:
            with self.subTest(payload=payload):
                with self.assertRaises(CalendarBusyError):
                    parse_busy_payload(payload)

    def test_timestamps_must_be_aware_positive_and_inside_range(self):
        payload = valid_payload()
        payload["generated_at"] = "2026-09-03T05:00:00"
        with self.assertRaises(CalendarBusyError):
            parse_busy_payload(payload)

        payload = valid_payload()
        payload["range"]["ends_at"] = payload["range"]["starts_at"]
        with self.assertRaises(CalendarBusyError):
            parse_busy_payload(payload)

        payload = valid_payload()
        payload["busy"][0]["ends_at"] = payload["busy"][0]["starts_at"]
        with self.assertRaises(CalendarBusyError):
            parse_busy_payload(payload)

        payload = valid_payload()
        payload["busy"][0]["starts_at"] = "2026-09-04T09:59:59+00:00"
        with self.assertRaises(CalendarBusyError):
            parse_busy_payload(payload)

        payload = valid_payload()
        payload["busy"][1]["ends_at"] = "2026-09-04T18:00:01+00:00"
        with self.assertRaises(CalendarBusyError):
            parse_busy_payload(payload)

    def test_intervals_must_be_sorted_and_fully_merged(self):
        payload = valid_payload()
        payload["busy"] = list(reversed(payload["busy"]))
        with self.assertRaises(CalendarBusyError):
            parse_busy_payload(payload)

        payload = valid_payload()
        payload["busy"][1]["starts_at"] = payload["busy"][0]["ends_at"]
        with self.assertRaises(CalendarBusyError):
            parse_busy_payload(payload)

        payload = valid_payload()
        payload["busy"][1]["starts_at"] = "2026-09-04T11:30:00+00:00"
        with self.assertRaises(CalendarBusyError):
            parse_busy_payload(payload)

    def test_response_range_must_match_requested_window(self):
        payload = valid_payload()
        payload["range"]["ends_at"] = "2026-09-04T17:59:00+00:00"
        with self.assertRaises(CalendarBusyError):
            parse_busy_payload(payload, expected_start=START, expected_end=END)

        with self.assertRaises(CalendarBusyError):
            parse_busy_payload(valid_payload(), expected_start=START)

    def test_response_range_cannot_exceed_consumer_maximum(self):
        payload = valid_payload()
        payload["range"] = {
            "starts_at": "2026-09-01T00:00:00+00:00",
            "ends_at": "2026-10-03T00:00:00+00:00",
        }
        payload["returned"] = 0
        payload["busy"] = []
        with self.assertRaises(CalendarBusyError):
            parse_busy_payload(payload)


class CalendarBusyHTTPClientTests(SimpleTestCase):
    @patch("api.calendar_busy_client.urlopen")
    def test_request_uses_exact_get_path_window_and_bearer_header(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeHTTPResponse(valid_payload())

        context = fetch_calendar_busy_context(
            base_url="https://calendar.internal.example",
            token=TOKEN,
            start=START,
            end=END,
            timeout_seconds=7,
        )
        self.assertEqual(len(context.intervals), 2)

        request = mocked_urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        parsed = urlparse(request.full_url)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "calendar.internal.example")
        self.assertEqual(parsed.path, "/api/v1/tasks/busy-time")
        query = parse_qs(parsed.query)
        self.assertEqual(query["starts_at"], [START.isoformat()])
        self.assertEqual(query["ends_at"], [END.isoformat()])
        self.assertEqual(request.get_header("Authorization"), f"Bearer {TOKEN}")
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertEqual(mocked_urlopen.call_args.kwargs["timeout"], 7)

    @patch("api.calendar_busy_client.urlopen")
    def test_loopback_http_is_allowed_for_disposable_validation(self, mocked_urlopen):
        mocked_urlopen.return_value = FakeHTTPResponse(valid_payload())
        fetch_calendar_busy_context(
            base_url="http://127.0.0.1:8766",
            token=TOKEN,
            start=START,
            end=END,
        )
        self.assertTrue(mocked_urlopen.called)

    def test_external_plain_http_and_credential_bearing_urls_are_rejected(self):
        invalid_urls = (
            "http://calendar.example.test",
            "https://user:password@calendar.example.test",
            "https://calendar.example.test?subject=other",
            "https://calendar.example.test/#fragment",
            "calendar.example.test",
        )
        for base_url in invalid_urls:
            with self.subTest(base_url=base_url):
                with self.assertRaises(CalendarBusyError):
                    fetch_calendar_busy_context(
                        base_url=base_url,
                        token=TOKEN,
                        start=START,
                        end=END,
                    )

    def test_input_window_token_and_timeout_are_bounded(self):
        cases = (
            {"token": "short"},
            {"start": END, "end": START},
            {"start": START, "end": START + timedelta(days=31, seconds=1)},
            {"start": START.replace(tzinfo=None)},
            {"timeout_seconds": 0},
            {"timeout_seconds": 31},
        )
        for overrides in cases:
            values = {
                "base_url": "https://calendar.example.test",
                "token": TOKEN,
                "start": START,
                "end": END,
                "timeout_seconds": 5,
            }
            values.update(overrides)
            with self.subTest(overrides=overrides):
                with self.assertRaises(CalendarBusyError):
                    fetch_calendar_busy_context(**values)

    @patch("api.calendar_busy_client.urlopen")
    def test_http_and_transport_failures_are_low_detail(self, mocked_urlopen):
        upstream_body = b'{"private_event":"do-not-leak"}'
        mocked_urlopen.side_effect = HTTPError(
            "https://calendar.example.test/api/v1/tasks/busy-time",
            403,
            "Forbidden secret reason",
            {},
            io.BytesIO(upstream_body),
        )
        with self.assertRaises(CalendarBusyError) as context:
            fetch_calendar_busy_context(
                base_url="https://calendar.example.test",
                token=TOKEN,
                start=START,
                end=END,
            )
        self.assertIn("HTTP 403", str(context.exception))
        self.assertNotIn("private_event", str(context.exception))
        self.assertNotIn("Forbidden secret reason", str(context.exception))

        mocked_urlopen.side_effect = URLError("private network detail")
        with self.assertRaises(CalendarBusyError) as context:
            fetch_calendar_busy_context(
                base_url="https://calendar.example.test",
                token=TOKEN,
                start=START,
                end=END,
            )
        self.assertEqual(str(context.exception), "GoreeCloud Calendar is unreachable.")

    @patch("api.calendar_busy_client.urlopen")
    def test_malformed_and_oversized_responses_fail_closed(self, mocked_urlopen):
        class RawResponse:
            def __init__(self, body):
                self.body = body

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self, amount=-1):
                return self.body if amount < 0 else self.body[:amount]

        mocked_urlopen.return_value = RawResponse(b"not-json")
        with self.assertRaises(CalendarBusyError):
            fetch_calendar_busy_context(
                base_url="https://calendar.example.test",
                token=TOKEN,
                start=START,
                end=END,
            )

        mocked_urlopen.return_value = RawResponse(b"x" * (MAX_RESPONSE_BYTES + 1))
        with self.assertRaises(CalendarBusyError):
            fetch_calendar_busy_context(
                base_url="https://calendar.example.test",
                token=TOKEN,
                start=START,
                end=END,
            )


class CalendarBusyConfigurationTests(SimpleTestCase):
    def base_environment(self):
        return {
            "TASKS_CALENDAR_BUSY_ENABLED": "true",
            "TASKS_CALENDAR_BUSY_BASE_URL": "https://calendar.internal.example",
            "TASKS_CALENDAR_BUSY_TOKEN": TOKEN,
            "TASKS_CALENDAR_BUSY_TOKEN_FILE": "",
            "TASKS_CALENDAR_BUSY_TIMEOUT_SECONDS": "5",
        }

    def test_disabled_configuration_requires_no_network_or_secret_values(self):
        config = load_calendar_busy_client_configuration(
            {"TASKS_CALENDAR_BUSY_ENABLED": "false"}
        )
        self.assertFalse(config.enabled)
        self.assertIsNone(config.error)

    def test_valid_configuration_has_no_subject_or_collection_selector(self):
        config = load_calendar_busy_client_configuration(self.base_environment())
        self.assertTrue(config.enabled)
        self.assertIsNone(config.error)
        self.assertEqual(config.base_url, "https://calendar.internal.example")
        self.assertEqual(config.timeout_seconds, 5)
        self.assertFalse(hasattr(config, "subject"))
        self.assertFalse(hasattr(config, "calendar_hrefs"))

    def test_external_plain_http_invalid_token_and_timeout_fail_closed(self):
        environment = self.base_environment()
        environment.update(
            {
                "TASKS_CALENDAR_BUSY_BASE_URL": "http://calendar.example.test",
                "TASKS_CALENDAR_BUSY_TOKEN": "short",
                "TASKS_CALENDAR_BUSY_TIMEOUT_SECONDS": "999",
            }
        )
        config = load_calendar_busy_client_configuration(environment)
        self.assertIsNotNone(config.error)
        self.assertNotIn("short", config.error)

    def test_token_sources_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            token_path = Path(temporary_directory) / "token"
            token_path.write_text(TOKEN, encoding="utf-8")
            os.chmod(token_path, 0o600)
            environment = self.base_environment()
            environment["TASKS_CALENDAR_BUSY_TOKEN_FILE"] = str(token_path)
            config = load_calendar_busy_client_configuration(environment)
        self.assertIsNotNone(config.error)
        self.assertIn("only one", config.error)

    def test_protected_file_secret_is_supported(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            token_path = Path(temporary_directory) / "token"
            token_path.write_text(TOKEN + "\n", encoding="utf-8")
            os.chmod(token_path, 0o600)
            environment = self.base_environment()
            environment["TASKS_CALENDAR_BUSY_TOKEN"] = ""
            environment["TASKS_CALENDAR_BUSY_TOKEN_FILE"] = str(token_path)
            config = load_calendar_busy_client_configuration(environment)
        self.assertIsNone(config.error)
        self.assertEqual(config.token, TOKEN)

    def test_group_or_other_accessible_secret_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            token_path = Path(temporary_directory) / "token"
            token_path.write_text(TOKEN, encoding="utf-8")
            os.chmod(token_path, 0o640)
            environment = self.base_environment()
            environment["TASKS_CALENDAR_BUSY_TOKEN"] = ""
            environment["TASKS_CALENDAR_BUSY_TOKEN_FILE"] = str(token_path)
            config = load_calendar_busy_client_configuration(environment)
        self.assertIsNotNone(config.error)
        self.assertIn("permissions", config.error)
