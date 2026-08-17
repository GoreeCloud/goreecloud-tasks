"""Regression tests for the authorization-safe Overdue task view."""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from tasks.models import Task


class OverdueViewTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice-overdue",
            password="test-password-alice",
        )
        self.bob = User.objects.create_user(
            username="bob-overdue",
            password="test-password-bob",
        )
        now = timezone.now()
        self.overdue = Task.objects.create(
            title="Past-due private task",
            creator=self.alice,
            assignee=self.alice,
            due_at=now - timedelta(days=2),
        )
        self.future = Task.objects.create(
            title="Future private task",
            creator=self.alice,
            assignee=self.alice,
            due_at=now + timedelta(days=2),
        )
        self.completed_overdue = Task.objects.create(
            title="Completed past-due task",
            creator=self.alice,
            assignee=self.alice,
            due_at=now - timedelta(days=3),
            status=Task.Status.COMPLETED,
        )
        self.other_user_overdue = Task.objects.create(
            title="Bob private overdue task",
            creator=self.bob,
            assignee=self.bob,
            due_at=now - timedelta(days=4),
        )

    def test_overdue_requires_authentication(self):
        response = self.client.get(reverse("tasks:overdue"))
        self.assertEqual(response.status_code, 302)

    def test_overdue_shows_only_visible_unfinished_past_due_tasks(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("tasks:overdue"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_view"], "overdue")
        self.assertEqual(response.context["heading"], "Overdue")
        self.assertContains(response, self.overdue.title)
        self.assertNotContains(response, self.future.title)
        self.assertNotContains(response, self.completed_overdue.title)
        self.assertNotContains(response, self.other_user_overdue.title)

    def test_overdue_empty_state_is_specific(self):
        self.overdue.delete()
        self.client.force_login(self.alice)
        response = self.client.get(reverse("tasks:overdue"))

        self.assertContains(response, "Nothing overdue.")
        self.assertContains(
            response,
            "Tasks that pass their due date without being completed will appear here.",
        )
