from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from api.calendar_authorization import (
    CALENDAR_BUSY_AUDIENCE,
    CALENDAR_BUSY_SCOPE,
    CalendarDelegatedAuthorization,
    CalendarDelegatedAuthorizationError,
)
from api.calendar_request import CALENDAR_BUSY_PATH, plan_calendar_busy_request


class CalendarBusyRequestPlanTests(SimpleTestCase):
    now = datetime(2026, 9, 1, 16, 0, tzinfo=timezone.utc)
    starts_at = datetime(2026, 9, 2, 8, 0, tzinfo=timezone(timedelta(hours=-5)))
    ends_at = datetime(2026, 9, 2, 18, 0, tzinfo=timezone(timedelta(hours=-5)))

    def authorization(self):
        return CalendarDelegatedAuthorization(
            owner_id="owner-a",
            audience=CALENDAR_BUSY_AUDIENCE,
            scopes=frozenset({CALENDAR_BUSY_SCOPE}),
            expires_at=self.now + timedelta(minutes=5),
        )

    def test_builds_exact_calendar_busy_request_shape_after_authorization(self):
        plan = plan_calendar_busy_request(
            task_owner_id="owner-a",
            authorization=self.authorization(),
            calendar_href=" /calendars/owner-a/work/ ",
            starts_at=self.starts_at,
            ends_at=self.ends_at,
            now=self.now,
        )

        self.assertEqual(plan.method, "GET")
        self.assertEqual(plan.path, CALENDAR_BUSY_PATH)
        self.assertEqual(
            plan.query_dict(),
            {
                "calendar": "/calendars/owner-a/work/",
                "starts_at": self.starts_at.isoformat(),
                "ends_at": self.ends_at.isoformat(),
            },
        )

    def test_plan_contains_no_delegated_authorization_or_task_owner_field(self):
        plan = plan_calendar_busy_request(
            task_owner_id="owner-a",
            authorization=self.authorization(),
            calendar_href="/calendars/opaque/work/",
            starts_at=self.starts_at,
            ends_at=self.ends_at,
            now=self.now,
        )

        self.assertFalse(hasattr(plan, "authorization"))
        self.assertFalse(hasattr(plan, "owner_id"))
        self.assertNotIn("goreecloud-calendar-busy", repr(plan))
        self.assertNotIn("calendar.busy.read", repr(plan))

    def test_rejects_request_planning_when_delegated_authorization_fails(self):
        with self.assertRaises(CalendarDelegatedAuthorizationError):
            plan_calendar_busy_request(
                task_owner_id="owner-b",
                authorization=self.authorization(),
                calendar_href="/calendars/opaque/work/",
                starts_at=self.starts_at,
                ends_at=self.ends_at,
                now=self.now,
            )

    def test_rejects_missing_calendar_reference_or_invalid_window(self):
        with self.assertRaises(ValueError):
            plan_calendar_busy_request(
                task_owner_id="owner-a",
                authorization=self.authorization(),
                calendar_href=" ",
                starts_at=self.starts_at,
                ends_at=self.ends_at,
                now=self.now,
            )
        with self.assertRaises(ValueError):
            plan_calendar_busy_request(
                task_owner_id="owner-a",
                authorization=self.authorization(),
                calendar_href="/calendars/opaque/work/",
                starts_at=self.ends_at,
                ends_at=self.starts_at,
                now=self.now,
            )

    def test_rejects_naive_window_boundaries(self):
        with self.assertRaises(ValueError):
            plan_calendar_busy_request(
                task_owner_id="owner-a",
                authorization=self.authorization(),
                calendar_href="/calendars/opaque/work/",
                starts_at=datetime(2026, 9, 2, 8, 0),
                ends_at=self.ends_at,
                now=self.now,
            )
