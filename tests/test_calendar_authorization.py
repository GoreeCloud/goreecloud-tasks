from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from api.calendar_authorization import (
    CALENDAR_BUSY_AUDIENCE,
    CALENDAR_BUSY_SCOPE,
    CalendarDelegatedAuthorization,
    CalendarDelegatedAuthorizationError,
    require_calendar_busy_authorization,
)


class CalendarDelegatedAuthorizationTests(SimpleTestCase):
    now = datetime(2026, 9, 1, 16, 0, tzinfo=timezone.utc)

    def authorization(self, **overrides):
        values = {
            "owner_id": "owner-a",
            "audience": CALENDAR_BUSY_AUDIENCE,
            "scopes": frozenset({CALENDAR_BUSY_SCOPE}),
            "expires_at": self.now + timedelta(minutes=5),
        }
        values.update(overrides)
        return CalendarDelegatedAuthorization(**values)

    def test_allows_same_owner_reviewed_busy_scope(self):
        require_calendar_busy_authorization("owner-a", self.authorization(), now=self.now)

    def test_rejects_missing_or_cross_owner_authorization(self):
        with self.assertRaises(CalendarDelegatedAuthorizationError):
            require_calendar_busy_authorization("owner-a", None, now=self.now)
        with self.assertRaises(CalendarDelegatedAuthorizationError):
            require_calendar_busy_authorization("owner-b", self.authorization(), now=self.now)

    def test_rejects_wrong_audience_or_missing_scope(self):
        with self.assertRaises(CalendarDelegatedAuthorizationError):
            require_calendar_busy_authorization(
                "owner-a",
                self.authorization(audience="goreecloud-calendar-full"),
                now=self.now,
            )
        with self.assertRaises(CalendarDelegatedAuthorizationError):
            require_calendar_busy_authorization(
                "owner-a",
                self.authorization(scopes=frozenset({"calendar.events.read"})),
                now=self.now,
            )

    def test_rejects_expired_authorization(self):
        with self.assertRaises(CalendarDelegatedAuthorizationError):
            require_calendar_busy_authorization(
                "owner-a",
                self.authorization(expires_at=self.now),
                now=self.now,
            )

    def test_rejects_naive_expiry_and_check_time(self):
        with self.assertRaises(ValueError):
            self.authorization(expires_at=datetime(2026, 9, 1, 16, 5))
        with self.assertRaises(ValueError):
            require_calendar_busy_authorization(
                "owner-a",
                self.authorization(),
                now=datetime(2026, 9, 1, 16, 0),
            )
