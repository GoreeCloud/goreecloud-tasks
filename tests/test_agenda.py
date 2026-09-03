"""Regression tests for the seven-day Agenda privacy and scheduling boundary."""

from datetime import datetime, time, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from api.calendar_busy_config import CalendarBusyClientConfiguration
from tasks.models import Task

TOKEN = "agenda-calendar-test-token-0123456789abcdef0123456789abcdef"


class AgendaWorkspaceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="test-password")
        self.other = User.objects.create_user(username="other", password="test-password")
        self.client.force_login(self.owner)
        self.tz = timezone.get_current_timezone()
        self.today = timezone.localdate()

    def due(self, day_offset, hour=9):
        return timezone.make_aware(
            datetime.combine(self.today + timedelta(days=day_offset), time(hour=hour)),
            self.tz,
        )

    def config(self, username="owner"):
        return CalendarBusyClientConfiguration(
            enabled=True,
            username=username,
            base_url="https://calendar.internal.example",
            token=TOKEN,
            timeout_seconds=5,
        )

    def test_agenda_requires_authentication(self):
        self.client.logout()
        response = self.client.get(reverse("tasks:agenda"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    @patch("tasks.agenda.load_calendar_busy_client_configuration")
    def test_agenda_uses_visible_active_tasks_in_seven_day_window(self, load_config):
        load_config.return_value = CalendarBusyClientConfiguration(enabled=False)
        Task.objects.create(title="Today point", creator=self.owner, assignee=self.owner, due_at=self.due(0, 10), status=Task.Status.READY)
        Task.objects.create(title="Sixth day point", creator=self.owner, assignee=self.owner, due_at=self.due(6, 16), status=Task.Status.READY)
        Task.objects.create(title="Outside window", creator=self.owner, assignee=self.owner, due_at=self.due(7, 0), status=Task.Status.READY)
        Task.objects.create(title="Completed point", creator=self.owner, assignee=self.owner, due_at=self.due(1, 12), status=Task.Status.COMPLETED)
        Task.objects.create(title="Other private point", creator=self.other, assignee=self.other, due_at=self.due(1, 13), status=Task.Status.READY)

        response = self.client.get(reverse("tasks:agenda"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Today point")
        self.assertContains(response, "Sixth day point")
        self.assertNotContains(response, "Outside window")
        self.assertNotContains(response, "Completed point")
        self.assertNotContains(response, "Other private point")
        self.assertEqual(response.context["task_count"], 2)
        self.assertEqual(len(response.context["agenda_days"]), 7)

    @patch("tasks.agenda.fetch_calendar_busy_context")
    @patch("tasks.agenda.load_calendar_busy_client_configuration")
    def test_calendar_context_is_requested_only_for_exact_local_recipient(self, load_config, fetch_busy):
        load_config.return_value = self.config(username="other")
        response = self.client.get(reverse("tasks:agenda"))
        self.assertEqual(response.context["calendar_state"], "not-authorized")
        fetch_busy.assert_not_called()

        load_config.return_value = self.config(username="owner")
        fetch_busy.return_value = SimpleNamespace(intervals=())
        response = self.client.get(reverse("tasks:agenda"))
        self.assertEqual(response.context["calendar_state"], "available")
        fetch_busy.assert_called_once()
        kwargs = fetch_busy.call_args.kwargs
        self.assertEqual(kwargs["start"].date(), self.today)
        self.assertEqual(kwargs["end"].date(), self.today + timedelta(days=7))

    @patch("tasks.agenda.fetch_calendar_busy_context")
    @patch("tasks.agenda.load_calendar_busy_client_configuration")
    def test_calendar_failure_degrades_to_tasks_without_free_time_claim(self, load_config, fetch_busy):
        load_config.return_value = self.config()
        fetch_busy.side_effect = TimeoutError("synthetic timeout")
        Task.objects.create(title="Still scheduled", creator=self.owner, assignee=self.owner, due_at=self.due(0, 11), status=Task.Status.READY)

        response = self.client.get(reverse("tasks:agenda"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Still scheduled")
        self.assertContains(response, "Calendar context is temporarily unavailable")
        self.assertContains(response, "No free-time assumption is made")

    @patch("tasks.agenda.fetch_calendar_busy_context")
    @patch("tasks.agenda.load_calendar_busy_client_configuration")
    def test_agenda_renders_only_generic_calendar_busy_metadata(self, load_config, fetch_busy):
        load_config.return_value = self.config()
        starts_at = self.due(1, 14)
        ends_at = self.due(1, 15)
        fetch_busy.return_value = SimpleNamespace(
            intervals=(SimpleNamespace(starts_at=starts_at, ends_at=ends_at, title="Synthetic confidential title", location="Synthetic private room"),)
        )

        response = self.client.get(reverse("tasks:agenda"))
        self.assertContains(response, "Calendar busy")
        self.assertNotContains(response, "Synthetic confidential title")
        self.assertNotContains(response, "Synthetic private room")

    @patch("tasks.agenda.load_calendar_busy_client_configuration")
    def test_task_due_time_is_presented_as_point_not_duration(self, load_config):
        load_config.return_value = CalendarBusyClientConfiguration(enabled=False)
        task = Task.objects.create(title="Point in time", creator=self.owner, assignee=self.owner, due_at=self.due(2, 10), status=Task.Status.READY)

        response = self.client.get(reverse("tasks:agenda"))
        self.assertContains(response, "Point in time")
        self.assertContains(response, "Due")
        self.assertContains(response, task.due_at.isoformat())
        self.assertContains(response, "A task due time is shown as a point in time, not a duration")
        self.assertNotContains(response, "task-duration")
        self.assertNotContains(response, "data-task-ends-at")
