from datetime import timedelta

from django.test import SimpleTestCase

from api.calendar_busy import CalendarBusyPayloadError, parse_busy_payload


class CalendarBusyPayloadTests(SimpleTestCase):
    def payload(self):
        return {
            "schema": "goreecloud.calendar.busy.v1",
            "version": 1,
            "range": {
                "starts_at": "2026-08-31T08:00:00-05:00",
                "ends_at": "2026-08-31T18:00:00-05:00",
            },
            "returned": 2,
            "busy": [
                {
                    "starts_at": "2026-08-31T09:00:00-05:00",
                    "ends_at": "2026-08-31T10:30:00-05:00",
                },
                {
                    "starts_at": "2026-08-31T13:00:00-05:00",
                    "ends_at": "2026-08-31T14:00:00-05:00",
                },
            ],
        }

    def test_accepts_privacy_minimized_calendar_contract(self):
        availability = parse_busy_payload(self.payload())

        self.assertEqual(len(availability.busy), 2)
        self.assertEqual(availability.busy_duration, timedelta(hours=2, minutes=30))
        self.assertEqual(availability.free_duration, timedelta(hours=7, minutes=30))

    def test_rejects_event_content_fields(self):
        payload = self.payload()
        payload["busy"][0]["title"] = "Sensitive appointment"

        with self.assertRaises(CalendarBusyPayloadError):
            parse_busy_payload(payload)

    def test_rejects_top_level_unreviewed_fields(self):
        payload = self.payload()
        payload["calendar_name"] = "Private calendar"

        with self.assertRaises(CalendarBusyPayloadError):
            parse_busy_payload(payload)

    def test_rejects_intervals_outside_requested_range(self):
        payload = self.payload()
        payload["busy"][0]["starts_at"] = "2026-08-31T07:59:00-05:00"

        with self.assertRaises(CalendarBusyPayloadError):
            parse_busy_payload(payload)

    def test_rejects_overlapping_or_unsorted_intervals(self):
        payload = self.payload()
        payload["busy"][1]["starts_at"] = "2026-08-31T10:00:00-05:00"

        with self.assertRaises(CalendarBusyPayloadError):
            parse_busy_payload(payload)

    def test_rejects_count_mismatch(self):
        payload = self.payload()
        payload["returned"] = 1

        with self.assertRaises(CalendarBusyPayloadError):
            parse_busy_payload(payload)

    def test_rejects_naive_datetimes(self):
        payload = self.payload()
        payload["range"]["starts_at"] = "2026-08-31T08:00:00"

        with self.assertRaises(CalendarBusyPayloadError):
            parse_busy_payload(payload)
