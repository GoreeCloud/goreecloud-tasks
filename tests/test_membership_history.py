"""Regression tests for task history after project access is revoked."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from projects.models import Project, ProjectMembership
from tasks.models import Task


class MembershipHistoryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner-history", password="test-password")
        self.member = User.objects.create_user(username="member-history", password="test-password")
        self.project = Project.objects.create(
            owner=self.owner,
            name="Historical access",
            visibility=Project.Visibility.SHARED,
        )
        self.membership = ProjectMembership.objects.create(
            project=self.project,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )
        self.task = Task.objects.create(
            title="Created and assigned before revocation",
            creator=self.member,
            assignee=self.member,
            project=self.project,
            status=Task.Status.READY,
        )

    def test_owner_can_complete_member_created_task_after_access_is_revoked(self):
        self.membership.is_active = False
        self.membership.save(update_fields=["is_active"])
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("tasks:task_toggle_complete", args=[self.task.pk]),
            {"next": reverse("projects:detail", args=[self.project.pk])},
        )

        self.assertRedirects(
            response,
            reverse("projects:detail", args=[self.project.pk]),
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.creator, self.member)
        self.assertEqual(self.task.assignee, self.member)
        self.assertEqual(self.task.status, Task.Status.COMPLETED)
        self.assertIsNotNone(self.task.completed_at)
