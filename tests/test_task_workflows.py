"""Functional tests for task capture, editing, scheduling, and privacy."""

from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from projects.models import Project, ProjectMembership
from tasks.models import Task


class TaskWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="test-password")
        self.other = User.objects.create_user(username="other", password="test-password")
        self.client.force_login(self.owner)

    def test_quick_add_creates_private_ready_task_for_current_user(self):
        response = self.client.post(
            reverse("tasks:quick_add"),
            {
                "title": "Capture this privately",
                "priority": Task.Priority.P2_HIGH,
                "project": "",
                "due_at": "",
                "next": reverse("tasks:dashboard"),
            },
        )

        self.assertRedirects(response, reverse("tasks:dashboard"))
        task = Task.objects.get(title="Capture this privately")
        self.assertEqual(task.creator, self.owner)
        self.assertEqual(task.assignee, self.owner)
        self.assertIsNone(task.project)
        self.assertEqual(task.status, Task.Status.READY)
        self.assertFalse(Task.objects.visible_to(self.other).filter(pk=task.pk).exists())

    def test_quick_add_rejects_project_where_user_is_only_viewer(self):
        project = Project.objects.create(
            owner=self.other,
            name="Read-only shared project",
            visibility=Project.Visibility.SHARED,
        )
        ProjectMembership.objects.create(
            project=project,
            user=self.owner,
            role=ProjectMembership.Role.VIEWER,
        )

        response = self.client.post(
            reverse("tasks:quick_add"),
            {
                "title": "Should not be created",
                "priority": Task.Priority.P3_STANDARD,
                "project": project.pk,
                "due_at": "",
                "next": reverse("tasks:dashboard"),
            },
        )

        self.assertRedirects(response, reverse("tasks:dashboard"))
        self.assertFalse(Task.objects.filter(title="Should not be created").exists())

    def test_shared_member_can_quick_add_to_editable_project(self):
        project = Project.objects.create(
            owner=self.other,
            name="Shared build",
            visibility=Project.Visibility.SHARED,
        )
        ProjectMembership.objects.create(
            project=project,
            user=self.owner,
            role=ProjectMembership.Role.MEMBER,
        )

        self.client.post(
            reverse("tasks:quick_add"),
            {
                "title": "Member-created task",
                "priority": Task.Priority.P3_STANDARD,
                "project": project.pk,
                "due_at": "",
                "next": reverse("tasks:dashboard"),
            },
        )

        task = Task.objects.get(title="Member-created task")
        self.assertEqual(task.project, project)
        self.assertEqual(task.creator, self.owner)
        self.assertEqual(task.assignee, self.owner)

    def test_private_task_edit_endpoint_does_not_cross_user_boundary(self):
        task = Task.objects.create(
            title="Other user's private task",
            creator=self.other,
            assignee=self.other,
        )

        response = self.client.get(reverse("tasks:task_edit", args=[task.pk]))
        self.assertEqual(response.status_code, 404)

    def test_toggle_completion_is_limited_to_editable_tasks(self):
        task = Task.objects.create(
            title="My task",
            creator=self.owner,
            assignee=self.owner,
            status=Task.Status.READY,
        )

        response = self.client.post(
            reverse("tasks:task_toggle_complete", args=[task.pk]),
            {"next": reverse("tasks:dashboard")},
        )
        self.assertRedirects(response, reverse("tasks:dashboard"))
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.COMPLETED)
        self.assertIsNotNone(task.completed_at)

        self.client.force_login(self.other)
        response = self.client.post(
            reverse("tasks:task_toggle_complete", args=[task.pk]),
            {"next": reverse("tasks:dashboard")},
        )
        self.assertEqual(response.status_code, 404)

    def test_today_and_upcoming_use_visible_active_due_tasks(self):
        local_today = timezone.localdate()
        current_tz = timezone.get_current_timezone()
        today_due = timezone.make_aware(
            datetime.combine(local_today, time(hour=9)), current_tz
        )
        tomorrow_due = timezone.make_aware(
            datetime.combine(local_today + timedelta(days=1), time(hour=9)), current_tz
        )

        Task.objects.create(
            title="Due today",
            creator=self.owner,
            assignee=self.owner,
            due_at=today_due,
            status=Task.Status.READY,
        )
        Task.objects.create(
            title="Due tomorrow",
            creator=self.owner,
            assignee=self.owner,
            due_at=tomorrow_due,
            status=Task.Status.READY,
        )
        Task.objects.create(
            title="Completed today",
            creator=self.owner,
            assignee=self.owner,
            due_at=today_due,
            status=Task.Status.COMPLETED,
        )
        Task.objects.create(
            title="Invisible tomorrow",
            creator=self.other,
            assignee=self.other,
            due_at=tomorrow_due,
            status=Task.Status.READY,
        )

        today_response = self.client.get(reverse("tasks:today"))
        self.assertContains(today_response, "Due today")
        self.assertNotContains(today_response, "Due tomorrow")
        self.assertNotContains(today_response, "Completed today")

        upcoming_response = self.client.get(reverse("tasks:upcoming"))
        self.assertContains(upcoming_response, "Due tomorrow")
        self.assertNotContains(upcoming_response, "Due today")
        self.assertNotContains(upcoming_response, "Invisible tomorrow")

    def test_full_editor_creates_task_and_preserves_creator(self):
        response = self.client.post(
            reverse("tasks:task_create"),
            {
                "title": "Detailed task",
                "description": "Created in the full editor",
                "project": "",
                "assignee": self.owner.pk,
                "priority": Task.Priority.P1_URGENT,
                "status": Task.Status.IN_PROGRESS,
                "due_at": "",
            },
        )

        task = Task.objects.get(title="Detailed task")
        self.assertRedirects(response, reverse("tasks:task_edit", args=[task.pk]))
        self.assertEqual(task.creator, self.owner)
        self.assertEqual(task.assignee, self.owner)
        self.assertEqual(task.status, Task.Status.IN_PROGRESS)
