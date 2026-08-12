"""Privacy, authorization, and delivery tests for user-specific reminders."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from notifications.models import NotificationPreference, TaskReminder
from notifications.services import dispatch_due_reminders, publish_ntfy_reminder
from projects.models import Project, ProjectMembership
from tasks.models import Task


class ReminderPrivacyTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice",
            email="alice@example.test",
            password="test-password-alice",
        )
        self.bob = User.objects.create_user(
            username="bob",
            password="test-password-bob",
        )
        self.viewer = User.objects.create_user(
            username="viewer",
            password="test-password-viewer",
        )
        self.alice_private = Task.objects.create(
            title="Alice private reminder task",
            description="private detail that must not leak",
            creator=self.alice,
            assignee=self.alice,
            status=Task.Status.READY,
            due_at=timezone.now() + timedelta(hours=4),
        )
        self.bob_private = Task.objects.create(
            title="Bob private reminder task",
            creator=self.bob,
            assignee=self.bob,
            status=Task.Status.READY,
        )
        self.shared_project = Project.objects.create(
            owner=self.alice,
            name="Shared Reminder Project",
            visibility=Project.Visibility.SHARED,
        )
        ProjectMembership.objects.create(
            project=self.shared_project,
            user=self.viewer,
            role=ProjectMembership.Role.VIEWER,
        )
        self.shared_task = Task.objects.create(
            title="Shared viewer task",
            creator=self.alice,
            assignee=self.viewer,
            project=self.shared_project,
            status=Task.Status.READY,
            due_at=timezone.now() + timedelta(hours=5),
        )

    def test_notification_settings_require_authentication(self):
        response = self.client.get(reverse("notifications:settings"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_preferences_use_non_identifying_topic_and_user_timezone(self):
        self.client.login(username="alice", password="test-password-alice")
        response = self.client.post(
            reverse("notifications:settings"),
            {
                "action": "preferences",
                "reminders_enabled": "on",
                "default_lead_minutes": "45",
                "timezone_name": "America/New_York",
                "ntfy_enabled": "on",
            },
        )
        self.assertRedirects(response, reverse("notifications:settings"))

        preference = NotificationPreference.objects.get(user=self.alice)
        self.alice.refresh_from_db()
        self.assertTrue(preference.reminders_enabled)
        self.assertTrue(preference.ntfy_enabled)
        self.assertEqual(preference.default_lead_minutes, 45)
        self.assertEqual(self.alice.timezone, "America/New_York")
        self.assertTrue(preference.ntfy_topic.startswith("goreecloud-tasks-"))
        self.assertNotIn("alice", preference.ntfy_topic.lower())
        self.assertNotIn("example", preference.ntfy_topic.lower())

    def test_invalid_timezone_is_rejected(self):
        self.client.login(username="alice", password="test-password-alice")
        response = self.client.post(
            reverse("notifications:settings"),
            {
                "action": "preferences",
                "reminders_enabled": "on",
                "default_lead_minutes": "30",
                "timezone_name": "Not/A_Real_Zone",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid IANA time zone name.")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.timezone, "America/Chicago")

    def test_reminder_task_choices_are_authorization_scoped(self):
        self.client.login(username="bob", password="test-password-bob")
        response = self.client.get(reverse("notifications:settings"))
        self.assertEqual(response.status_code, 200)

        queryset = response.context["reminder_form"].fields["task"].queryset
        self.assertIn(self.bob_private, queryset)
        self.assertNotIn(self.alice_private, queryset)
        self.assertNotIn(self.shared_task, queryset)
        self.assertNotContains(response, self.alice_private.title)

    def test_viewer_can_schedule_private_reminder_for_readable_shared_task(self):
        self.client.login(username="viewer", password="test-password-viewer")
        remind_at = timezone.localtime(timezone.now() + timedelta(hours=1)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        response = self.client.post(
            reverse("notifications:settings"),
            {
                "action": "create_reminder",
                "task": str(self.shared_task.pk),
                "remind_at": remind_at,
            },
        )
        self.assertRedirects(response, reverse("notifications:settings"))
        reminder = TaskReminder.objects.get(user=self.viewer, task=self.shared_task)
        self.assertIsNone(reminder.sent_at)
        self.assertIsNone(reminder.cancelled_at)
        self.assertNotIn(
            self.shared_task,
            Task.objects.editable_by(self.viewer),
            "Viewer reminder ownership must not expand task edit authorization.",
        )

    def test_reminder_rejects_task_outside_user_visibility(self):
        reminder = TaskReminder(
            user=self.bob,
            task=self.alice_private,
            remind_at=timezone.now() + timedelta(hours=1),
        )
        with self.assertRaises(ValidationError):
            reminder.full_clean()

    def test_past_reminder_is_rejected_by_user_form(self):
        self.client.login(username="alice", password="test-password-alice")
        remind_at = timezone.localtime(timezone.now() - timedelta(minutes=10)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        response = self.client.post(
            reverse("notifications:settings"),
            {
                "action": "create_reminder",
                "task": str(self.alice_private.pk),
                "remind_at": remind_at,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a reminder time in the future.")
        self.assertFalse(TaskReminder.objects.filter(user=self.alice).exists())

    def test_user_cannot_cancel_another_users_reminder(self):
        reminder = TaskReminder.objects.create(
            user=self.alice,
            task=self.alice_private,
            remind_at=timezone.now() + timedelta(hours=1),
        )
        self.client.login(username="bob", password="test-password-bob")
        response = self.client.post(
            reverse("notifications:reminder_cancel", args=[reminder.pk])
        )
        self.assertEqual(response.status_code, 404)
        reminder.refresh_from_db()
        self.assertIsNone(reminder.cancelled_at)

    def test_closing_task_cancels_pending_reminders(self):
        reminder = TaskReminder.objects.create(
            user=self.alice,
            task=self.alice_private,
            remind_at=timezone.now() + timedelta(hours=1),
        )
        self.alice_private.status = Task.Status.COMPLETED
        self.alice_private.save()

        reminder.refresh_from_db()
        self.assertIsNotNone(reminder.cancelled_at)
        self.assertIn("closed", reminder.last_error)


class ReminderDispatchTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner",
            password="test-password-owner",
        )
        self.member = User.objects.create_user(
            username="member",
            password="test-password-member",
        )
        self.project = Project.objects.create(
            owner=self.owner,
            name="Dispatch Project",
            visibility=Project.Visibility.SHARED,
        )
        self.membership = ProjectMembership.objects.create(
            project=self.project,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )
        self.task = Task.objects.create(
            title="Dispatch reminder task",
            description="Do not send this description through ntfy.",
            creator=self.owner,
            assignee=self.member,
            project=self.project,
            priority=Task.Priority.P0_CRITICAL,
            status=Task.Status.READY,
            due_at=timezone.now() + timedelta(hours=1),
        )
        self.preference = NotificationPreference.objects.create(
            user=self.member,
            reminders_enabled=True,
            ntfy_enabled=True,
        )

    def _due_reminder(self):
        return TaskReminder.objects.create(
            user=self.member,
            task=self.task,
            remind_at=timezone.now() - timedelta(minutes=1),
        )

    @patch("notifications.services.publish_ntfy_reminder")
    def test_dispatch_marks_successful_due_reminder_sent(self, publish):
        reminder = self._due_reminder()
        summary = dispatch_due_reminders()

        self.assertEqual(summary.sent, 1)
        self.assertEqual(summary.failed, 0)
        publish.assert_called_once()
        reminder.refresh_from_db()
        self.assertIsNotNone(reminder.sent_at)
        self.assertEqual(reminder.attempt_count, 1)
        self.assertEqual(reminder.last_error, "")

    @patch("notifications.services.publish_ntfy_reminder")
    def test_dispatch_rechecks_authorization_and_cancels_after_revocation(self, publish):
        reminder = self._due_reminder()
        self.membership.is_active = False
        self.membership.save(update_fields=["is_active"])

        summary = dispatch_due_reminders()

        self.assertEqual(summary.cancelled, 1)
        self.assertEqual(summary.sent, 0)
        publish.assert_not_called()
        reminder.refresh_from_db()
        self.assertIsNotNone(reminder.cancelled_at)
        self.assertIn("no longer authorized", reminder.last_error)

    @patch("notifications.services.publish_ntfy_reminder")
    def test_disabled_ntfy_preference_does_not_dispatch(self, publish):
        reminder = self._due_reminder()
        self.preference.ntfy_enabled = False
        self.preference.save(update_fields=["ntfy_enabled"])

        summary = dispatch_due_reminders()

        self.assertEqual(summary.candidates, 0)
        publish.assert_not_called()
        reminder.refresh_from_db()
        self.assertIsNone(reminder.sent_at)
        self.assertIsNone(reminder.cancelled_at)

    @override_settings(
        NTFY_BASE_URL="https://notify.example.test",
        NTFY_ACCESS_TOKEN="tk_test_only",
        TASKS_BASE_URL="https://tasks.example.test",
        NTFY_TIMEOUT_SECONDS=3,
    )
    @patch("notifications.services.urlopen")
    def test_ntfy_publication_is_authenticated_and_data_minimized(self, urlopen):
        response = SimpleNamespace(status=200, close=lambda: None)
        urlopen.return_value = response
        reminder = TaskReminder.objects.create(
            user=self.member,
            task=self.task,
            remind_at=timezone.now() + timedelta(minutes=30),
        )

        publish_ntfy_reminder(reminder)

        request = urlopen.call_args.args[0]
        body = request.data.decode("utf-8")
        self.assertEqual(
            request.full_url,
            f"https://notify.example.test/{self.preference.ntfy_topic}",
        )
        self.assertEqual(request.get_header("Authorization"), "Bearer tk_test_only")
        self.assertEqual(request.get_header("Priority"), "urgent")
        self.assertEqual(
            request.get_header("Click"),
            f"https://tasks.example.test/tasks/{self.task.pk}/",
        )
        self.assertIn(self.task.title, body)
        self.assertIn(self.project.name, body)
        self.assertNotIn(self.task.description, body)
        self.assertNotIn("tk_test_only", body)

    @patch("notifications.services.publish_ntfy_reminder")
    def test_delivery_failure_keeps_reminder_pending_for_retry(self, publish):
        from notifications.services import NtfyPublishError

        reminder = self._due_reminder()
        publish.side_effect = NtfyPublishError("temporary publish failure")

        summary = dispatch_due_reminders()

        self.assertEqual(summary.failed, 1)
        reminder.refresh_from_db()
        self.assertIsNone(reminder.sent_at)
        self.assertIsNone(reminder.cancelled_at)
        self.assertEqual(reminder.attempt_count, 1)
        self.assertEqual(reminder.last_error, "temporary publish failure")
