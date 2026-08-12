"""Regression tests for private reminder and notification-preference portability."""

from datetime import timedelta
import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from notifications.models import NotificationPreference, TaskReminder
from portability.exporters import SCHEMA_VERSION, build_project_archive, build_user_archive
from portability.notification_state import restore_user_archive_with_notifications
from portability.restorers import ArchiveRestoreError
from projects.models import Project, ProjectMembership
from tasks.models import Task


class NotificationPortabilityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.invalid",
            password="test-password",
        )
        self.other = User.objects.create_user(
            username="other",
            email="other@example.invalid",
            password="test-password",
        )

    def test_user_archive_exports_private_notification_state_without_widening_task_scope(self):
        preference = NotificationPreference.objects.create(
            user=self.owner,
            reminders_enabled=True,
            default_lead_minutes=45,
            ntfy_enabled=True,
            ntfy_topic="goreecloud-tasks-owner-fixture",
        )
        owned_task = Task.objects.create(
            title="Owned reminder task",
            creator=self.owner,
            assignee=self.owner,
        )
        shared_project = Project.objects.create(
            owner=self.other,
            name="Other owner's project",
            visibility=Project.Visibility.SHARED,
        )
        ProjectMembership.objects.create(
            project=shared_project,
            user=self.owner,
            role=ProjectMembership.Role.MEMBER,
        )
        shared_task = Task.objects.create(
            title="Shared reminder task",
            creator=self.other,
            assignee=self.owner,
            project=shared_project,
        )
        owned_reminder = TaskReminder.objects.create(
            user=self.owner,
            task=owned_task,
            remind_at=timezone.now() + timedelta(hours=1),
        )
        TaskReminder.objects.filter(pk=owned_reminder.pk).update(
            last_error="internal-delivery-detail-that-must-not-be-exported"
        )
        TaskReminder.objects.create(
            user=self.owner,
            task=shared_task,
            remind_at=timezone.now() + timedelta(hours=2),
        )

        payload = build_user_archive(self.owner)

        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        self.assertEqual(SCHEMA_VERSION, 2)
        state = payload["data"]["notifications"]
        self.assertEqual(state["preference"]["user_id"], self.owner.pk)
        self.assertEqual(state["preference"]["default_lead_minutes"], 45)
        self.assertTrue(state["preference"]["ntfy_enabled"])
        self.assertEqual(state["preference"]["ntfy_topic"], preference.ntfy_topic)
        self.assertEqual(len(state["reminders"]), 1)
        self.assertEqual(state["reminders"][0]["task_id"], owned_task.pk)
        self.assertEqual(state["excluded_shared_task_reminder_count"], 1)
        self.assertNotIn(shared_task.pk, {item["id"] for item in payload["data"]["tasks"]})
        self.assertNotIn(
            "internal-delivery-detail-that-must-not-be-exported",
            json.dumps(payload),
        )

    def test_schema_v2_restore_preserves_preferences_and_owned_task_reminders(self):
        preference = NotificationPreference.objects.create(
            user=self.owner,
            reminders_enabled=False,
            default_lead_minutes=120,
            ntfy_enabled=True,
            ntfy_topic="goreecloud-tasks-restore-fixture",
        )
        task = Task.objects.create(
            title="Restore notification state",
            creator=self.owner,
            assignee=self.owner,
        )
        reminder = TaskReminder.objects.create(
            user=self.owner,
            task=task,
            remind_at=timezone.now() + timedelta(days=1),
        )
        TaskReminder.objects.filter(pk=reminder.pk).update(
            last_attempt_at=timezone.now(),
            attempt_count=2,
            last_error="transient publisher error",
        )
        reminder.refresh_from_db()
        payload = build_user_archive(self.owner)
        original_topic = preference.ntfy_topic
        original_remind_at = reminder.remind_at
        original_attempt_at = reminder.last_attempt_at

        TaskReminder.objects.all().delete()
        NotificationPreference.objects.filter(user=self.owner).delete()
        Task.objects.all().delete()

        restore_user_archive_with_notifications(payload, user=self.owner)

        restored_preference = NotificationPreference.objects.get(user=self.owner)
        self.assertFalse(restored_preference.reminders_enabled)
        self.assertEqual(restored_preference.default_lead_minutes, 120)
        self.assertTrue(restored_preference.ntfy_enabled)
        self.assertEqual(restored_preference.ntfy_topic, original_topic)

        restored_task = Task.objects.get(title="Restore notification state")
        restored_reminder = TaskReminder.objects.get(user=self.owner)
        self.assertEqual(restored_reminder.task, restored_task)
        self.assertEqual(restored_reminder.remind_at, original_remind_at)
        self.assertEqual(restored_reminder.last_attempt_at, original_attempt_at)
        self.assertEqual(restored_reminder.attempt_count, 2)
        self.assertEqual(restored_reminder.last_error, "")

    def test_schema_v1_user_archive_remains_restorable_without_notification_state(self):
        Task.objects.create(
            title="Legacy archive task",
            creator=self.owner,
            assignee=self.owner,
        )
        payload = build_user_archive(self.owner)
        payload["schema_version"] = 1
        payload["data"].pop("notifications")
        Task.objects.all().delete()

        restore_user_archive_with_notifications(payload, user=self.owner)

        self.assertTrue(Task.objects.filter(title="Legacy archive task").exists())
        self.assertFalse(TaskReminder.objects.filter(user=self.owner).exists())

    def test_restore_refuses_ntfy_topic_collision_before_core_data_is_written(self):
        NotificationPreference.objects.create(
            user=self.owner,
            ntfy_enabled=True,
            ntfy_topic="goreecloud-tasks-collision-fixture",
        )
        Task.objects.create(
            title="Must roll back",
            creator=self.owner,
            assignee=self.owner,
        )
        payload = build_user_archive(self.owner)

        Task.objects.all().delete()
        NotificationPreference.objects.filter(user=self.owner).delete()
        NotificationPreference.objects.create(
            user=self.other,
            ntfy_enabled=True,
            ntfy_topic="goreecloud-tasks-collision-fixture",
        )

        with self.assertRaises(ArchiveRestoreError):
            restore_user_archive_with_notifications(payload, user=self.owner)

        self.assertFalse(Task.objects.filter(creator=self.owner).exists())

    def test_project_archive_does_not_include_private_notification_state(self):
        NotificationPreference.objects.create(
            user=self.owner,
            ntfy_enabled=True,
            ntfy_topic="goreecloud-tasks-private-project-fixture",
        )
        project = Project.objects.create(owner=self.owner, name="Portable project")
        task = Task.objects.create(
            title="Project reminder",
            creator=self.owner,
            assignee=self.owner,
            project=project,
        )
        TaskReminder.objects.create(
            user=self.owner,
            task=task,
            remind_at=timezone.now() + timedelta(hours=1),
        )

        payload = build_project_archive(project)

        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        self.assertNotIn("notifications", payload["data"])
