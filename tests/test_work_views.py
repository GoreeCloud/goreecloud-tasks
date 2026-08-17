"""Regression coverage for authorization-safe Shared Work and GoreeCloud Work views."""

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from projects.models import Project, ProjectMembership
from tasks.models import Task


class FilteredWorkViewTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="alice-password")
        self.bob = User.objects.create_user(username="bob", password="bob-password")

        self.shared_project = Project.objects.create(
            owner=self.alice,
            name="Shared Operations",
            visibility=Project.Visibility.SHARED,
        )
        ProjectMembership.objects.create(
            project=self.shared_project,
            user=self.bob,
            role=ProjectMembership.Role.VIEWER,
        )
        self.private_project = Project.objects.create(
            owner=self.alice,
            name="Alice Private",
            visibility=Project.Visibility.PRIVATE,
        )

        self.shared_task = Task.objects.create(
            title="Visible shared task",
            creator=self.alice,
            assignee=self.alice,
            project=self.shared_project,
        )
        self.shared_goreecloud_task = Task.objects.create(
            title="Visible GoreeCloud task",
            creator=self.alice,
            assignee=self.alice,
            project=self.shared_project,
            is_goreecloud_work=True,
        )
        self.private_task = Task.objects.create(
            title="Private project task",
            creator=self.alice,
            assignee=self.alice,
            project=self.private_project,
            is_goreecloud_work=True,
        )
        self.personal_goreecloud_task = Task.objects.create(
            title="Alice personal GoreeCloud task",
            creator=self.alice,
            assignee=self.alice,
            is_goreecloud_work=True,
        )

    def test_filtered_views_require_authentication(self):
        for name in ("tasks:shared_work", "tasks:goreecloud_work"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302)

    def test_shared_work_includes_visible_shared_project_tasks(self):
        self.client.force_login(self.bob)
        response = self.client.get(reverse("tasks:shared_work"))

        self.assertContains(response, self.shared_task.title)
        self.assertContains(response, self.shared_goreecloud_task.title)
        self.assertNotContains(response, self.private_task.title)
        self.assertNotContains(response, self.personal_goreecloud_task.title)
        self.assertContains(response, "Shared Work")

    def test_goreecloud_work_respects_visibility_boundary(self):
        self.client.force_login(self.bob)
        response = self.client.get(reverse("tasks:goreecloud_work"))

        self.assertContains(response, self.shared_goreecloud_task.title)
        self.assertNotContains(response, self.shared_task.title)
        self.assertNotContains(response, self.private_task.title)
        self.assertNotContains(response, self.personal_goreecloud_task.title)
        self.assertContains(response, "GoreeCloud Work")

    def test_owner_sees_private_and_personal_goreecloud_work(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("tasks:goreecloud_work"))

        self.assertContains(response, self.shared_goreecloud_task.title)
        self.assertContains(response, self.private_task.title)
        self.assertContains(response, self.personal_goreecloud_task.title)

    def test_inactive_shared_membership_removes_both_filtered_views(self):
        membership = self.shared_project.memberships.get(user=self.bob)
        membership.is_active = False
        membership.save(update_fields=["is_active"])

        self.client.force_login(self.bob)
        shared_response = self.client.get(reverse("tasks:shared_work"))
        goreecloud_response = self.client.get(reverse("tasks:goreecloud_work"))

        self.assertNotContains(shared_response, self.shared_task.title)
        self.assertNotContains(shared_response, self.shared_goreecloud_task.title)
        self.assertNotContains(goreecloud_response, self.shared_goreecloud_task.title)

    def test_completed_tasks_are_excluded_from_filtered_work_views(self):
        self.shared_goreecloud_task.status = Task.Status.COMPLETED
        self.shared_goreecloud_task.save()

        self.client.force_login(self.bob)
        self.assertNotContains(
            self.client.get(reverse("tasks:shared_work")),
            self.shared_goreecloud_task.title,
        )
        self.assertNotContains(
            self.client.get(reverse("tasks:goreecloud_work")),
            self.shared_goreecloud_task.title,
        )
