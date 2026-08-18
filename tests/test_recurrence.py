"""Regression tests for GoreeCloud Tasks recurrence behavior."""

from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from labels.models import Label
from projects.models import Project, ProjectMembership
from tasks.models import Task
from tasks.recurrence import next_due_at


class TaskRecurrenceTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice-repeat", password="alice-password")
        self.bob = User.objects.create_user(username="bob-repeat", password="bob-password")

    def aware(self, year, month, day, hour=9):
        return timezone.make_aware(datetime(year, month, day, hour, 0))

    def test_repeating_task_requires_due_date(self):
        task = Task(
            title="No due date repeat",
            creator=self.alice,
            assignee=self.alice,
            recurrence=Task.Recurrence.WEEKLY,
        )
        with self.assertRaises(ValidationError):
            task.full_clean()

    def test_next_due_date_supports_daily_weekly_and_monthly_clamping(self):
        task = Task(due_at=self.aware(2027, 1, 31), recurrence=Task.Recurrence.DAILY)
        self.assertEqual(next_due_at(task), self.aware(2027, 2, 1))

        task.recurrence = Task.Recurrence.WEEKLY
        self.assertEqual(next_due_at(task), self.aware(2027, 2, 7))

        task.recurrence = Task.Recurrence.MONTHLY
        self.assertEqual(next_due_at(task), self.aware(2027, 2, 28))

    def test_completion_creates_next_private_occurrence_and_preserves_metadata(self):
        label = Label.objects.create(owner=self.alice, name="Routine")
        due_at = timezone.now() + timedelta(days=1)
        task = Task.objects.create(
            title="Weekly backup review",
            description="Review the synthetic backup report",
            creator=self.alice,
            assignee=self.alice,
            priority=Task.Priority.P2_HIGH,
            status=Task.Status.READY,
            due_at=due_at,
            recurrence=Task.Recurrence.WEEKLY,
            is_goreecloud_work=True,
            assigned_service="Kopia",
            validation_requirement=True,
        )
        task.labels.add(label)

        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("tasks:task_toggle_complete", args=[task.pk]),
            {"next": reverse("tasks:dashboard")},
        )
        self.assertEqual(response.status_code, 302)

        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.COMPLETED)
        self.assertIsNotNone(task.completed_at)

        next_task = Task.objects.exclude(pk=task.pk).get(title=task.title)
        self.assertEqual(next_task.creator, self.alice)
        self.assertEqual(next_task.assignee, self.alice)
        self.assertEqual(next_task.status, Task.Status.READY)
        self.assertEqual(next_task.recurrence, Task.Recurrence.WEEKLY)
        self.assertEqual(next_task.due_at, due_at + timedelta(days=7))
        self.assertTrue(next_task.is_goreecloud_work)
        self.assertEqual(next_task.assigned_service, "Kopia")
        self.assertTrue(next_task.validation_requirement)
        self.assertEqual(list(next_task.labels.all()), [label])
        self.assertFalse(next_task.comments.exists())

    def test_non_repeating_completion_does_not_create_another_task(self):
        task = Task.objects.create(
            title="One-time task",
            creator=self.alice,
            assignee=self.alice,
            due_at=timezone.now() + timedelta(days=1),
            status=Task.Status.READY,
        )
        self.client.force_login(self.alice)
        self.client.post(reverse("tasks:task_toggle_complete", args=[task.pk]))

        self.assertEqual(Task.objects.filter(title=task.title).count(), 1)

    def test_unauthorized_user_cannot_complete_or_spawn_private_recurrence(self):
        task = Task.objects.create(
            title="Alice private repeat",
            creator=self.alice,
            assignee=self.alice,
            due_at=timezone.now() + timedelta(days=1),
            recurrence=Task.Recurrence.DAILY,
            status=Task.Status.READY,
        )
        self.client.force_login(self.bob)
        response = self.client.post(reverse("tasks:task_toggle_complete", args=[task.pk]))

        self.assertEqual(response.status_code, 404)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.READY)
        self.assertEqual(Task.objects.filter(title=task.title).count(), 1)

    def test_revoked_project_assignee_is_not_reassigned_to_new_occurrence(self):
        project = Project.objects.create(
            owner=self.alice,
            name="Shared recurring work",
            visibility=Project.Visibility.SHARED,
        )
        membership = ProjectMembership.objects.create(
            project=project,
            user=self.bob,
            role=ProjectMembership.Role.MEMBER,
        )
        task = Task.objects.create(
            title="Shared weekly task",
            creator=self.alice,
            assignee=self.bob,
            project=project,
            due_at=timezone.now() + timedelta(days=1),
            recurrence=Task.Recurrence.WEEKLY,
            status=Task.Status.READY,
        )
        membership.is_active = False
        membership.save(update_fields=["is_active"])

        self.client.force_login(self.alice)
        self.client.post(reverse("tasks:task_toggle_complete", args=[task.pk]))

        task.refresh_from_db()
        next_task = Task.objects.exclude(pk=task.pk).get(title=task.title)
        self.assertEqual(task.assignee, self.bob)
        self.assertIsNone(next_task.assignee)

    def test_full_editor_requires_complete_action_for_repeating_task(self):
        task = Task.objects.create(
            title="Repeat through complete action",
            creator=self.alice,
            assignee=self.alice,
            due_at=timezone.now() + timedelta(days=1),
            recurrence=Task.Recurrence.DAILY,
            status=Task.Status.READY,
        )
        self.client.force_login(self.alice)
        response = self.client.post(
            reverse("tasks:task_edit", args=[task.pk]),
            {
                "title": task.title,
                "description": "",
                "project": "",
                "assignee": self.alice.pk,
                "priority": Task.Priority.P3_STANDARD,
                "status": Task.Status.COMPLETED,
                "due_at": timezone.localtime(task.due_at).strftime("%Y-%m-%dT%H:%M"),
                "recurrence": Task.Recurrence.DAILY,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Use the Complete action for a repeating task")
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.READY)
