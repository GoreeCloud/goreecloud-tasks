"""Portability regression coverage for recurring-task state."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from portability.exporters import build_user_archive
from portability.recurrence_state import restore_user_archive_with_recurrence
from portability.restorers import ArchiveRestoreError
from tasks.models import Task


class RecurrencePortabilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="recurrence-archive-user",
            password="test-password",
        )

    def _task(self, *, recurrence=Task.Recurrence.WEEKLY):
        return Task.objects.create(
            title="Recurring portable task",
            creator=self.user,
            assignee=self.user,
            status=Task.Status.READY,
            due_at=timezone.now() + timedelta(days=2),
            recurrence=recurrence,
        )

    def test_user_archive_round_trips_recurrence(self):
        task = self._task()
        payload = build_user_archive(self.user)

        task_record = payload["data"]["tasks"][0]
        self.assertEqual(task_record["recurrence"], Task.Recurrence.WEEKLY)

        task.delete()
        restore_user_archive_with_recurrence(payload, user=self.user)

        restored = Task.objects.get(title="Recurring portable task")
        self.assertEqual(restored.recurrence, Task.Recurrence.WEEKLY)

    def test_older_schema_v2_task_record_without_recurrence_defaults_to_none(self):
        task = self._task(recurrence=Task.Recurrence.NONE)
        payload = build_user_archive(self.user)
        payload["data"]["tasks"][0].pop("recurrence")

        task.delete()
        restore_user_archive_with_recurrence(payload, user=self.user)

        restored = Task.objects.get(title="Recurring portable task")
        self.assertEqual(restored.recurrence, Task.Recurrence.NONE)

    def test_invalid_recurrence_is_rejected_before_restore(self):
        task = self._task()
        payload = build_user_archive(self.user)
        payload["data"]["tasks"][0]["recurrence"] = "every-fortnight-ish"

        task.delete()
        with self.assertRaises(ArchiveRestoreError):
            restore_user_archive_with_recurrence(payload, user=self.user)
        self.assertFalse(Task.objects.exists())

    def test_repeating_archive_record_without_due_date_is_rejected(self):
        task = self._task()
        payload = build_user_archive(self.user)
        payload["data"]["tasks"][0]["due_at"] = None

        task.delete()
        with self.assertRaises(ArchiveRestoreError):
            restore_user_archive_with_recurrence(payload, user=self.user)
        self.assertFalse(Task.objects.exists())
