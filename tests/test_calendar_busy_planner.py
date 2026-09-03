from datetime import datetime, timedelta, timezone
from unittest import TestCase

from api.calendar_busy_client import BusyInterval, CalendarBusyContext, CalendarBusyError
from api.calendar_busy_planner import FreeWindow, derive_free_windows


def context(*intervals: BusyInterval) -> CalendarBusyContext:
    start = datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc)
    return CalendarBusyContext(
        generated_at=start - timedelta(minutes=1),
        starts_at=start,
        ends_at=start + timedelta(hours=8),
        intervals=tuple(intervals),
    )


class CalendarBusyPlannerTests(TestCase):
    def test_derives_only_complement_windows_at_or_above_minimum_duration(self) -> None:
        start = datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc)
        busy = context(
            BusyInterval(start + timedelta(hours=1), start + timedelta(hours=2)),
            BusyInterval(start + timedelta(hours=3), start + timedelta(hours=5)),
            BusyInterval(
                start + timedelta(hours=7, minutes=30),
                start + timedelta(hours=8),
            ),
        )

        windows = derive_free_windows(busy, minimum_duration=timedelta(minutes=45))

        self.assertEqual(
            windows,
            (
                FreeWindow(start, start + timedelta(hours=1)),
                FreeWindow(start + timedelta(hours=2), start + timedelta(hours=3)),
                FreeWindow(
                    start + timedelta(hours=5),
                    start + timedelta(hours=7, minutes=30),
                ),
            ),
        )

    def test_empty_busy_context_returns_whole_range_as_one_advisory_window(self) -> None:
        busy = context()

        windows = derive_free_windows(busy, minimum_duration=timedelta(minutes=30))

        self.assertEqual(windows, (FreeWindow(busy.starts_at, busy.ends_at),))

    def test_limit_returns_earliest_qualifying_windows_deterministically(self) -> None:
        start = datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc)
        busy = context(
            BusyInterval(start + timedelta(hours=1), start + timedelta(hours=2)),
            BusyInterval(start + timedelta(hours=3), start + timedelta(hours=4)),
        )

        windows = derive_free_windows(
            busy,
            minimum_duration=timedelta(minutes=30),
            limit=2,
        )

        self.assertEqual(
            windows,
            (
                FreeWindow(start, start + timedelta(hours=1)),
                FreeWindow(start + timedelta(hours=2), start + timedelta(hours=3)),
            ),
        )

    def test_rejects_manually_constructed_overlapping_busy_context(self) -> None:
        start = datetime(2026, 9, 3, 9, 0, tzinfo=timezone.utc)
        busy = context(
            BusyInterval(start + timedelta(hours=1), start + timedelta(hours=3)),
            BusyInterval(start + timedelta(hours=2), start + timedelta(hours=4)),
        )

        with self.assertRaisesRegex(CalendarBusyError, "strictly ordered and fully merged"):
            derive_free_windows(busy, minimum_duration=timedelta(minutes=30))

    def test_rejects_unbounded_or_invalid_planning_parameters(self) -> None:
        busy = context()

        for duration in (timedelta(minutes=4), timedelta(hours=25)):
            with self.subTest(duration=duration):
                with self.assertRaisesRegex(
                    CalendarBusyError,
                    "between 5 minutes and 24 hours",
                ):
                    derive_free_windows(busy, minimum_duration=duration)

        for invalid_limit in (0, 33, True):
            with self.subTest(limit=invalid_limit):
                with self.assertRaisesRegex(CalendarBusyError, "between 1 and 32"):
                    derive_free_windows(
                        busy,
                        minimum_duration=timedelta(minutes=30),
                        limit=invalid_limit,
                    )
