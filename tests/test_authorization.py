"""Launch-blocking tests for multi-user content separation."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import User
from projects.models import Project, ProjectMembership
from tasks.models import Task


class MultiUserAuthorizationTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice",
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

        self.alice_private_task = Task.objects.create(
            title="Alice private task",
            creator=self.alice,
            assignee=self.alice,
        )

        self.shared_project = Project.objects.create(
            owner=self.alice,
            name="Family Chores",
            visibility=Project.Visibility.SHARED,
        )
        ProjectMembership.objects.create(
            project=self.shared_project,
            user=self.bob,
            role=ProjectMembership.Role.MEMBER,
        )
        ProjectMembership.objects.create(
            project=self.shared_project,
            user=self.viewer,
            role=ProjectMembership.Role.VIEWER,
        )

        self.shared_task = Task.objects.create(
            title="Shared task",
            creator=self.alice,
            assignee=self.bob,
            project=self.shared_project,
        )

    def test_private_task_is_visible_only_to_its_owner(self):
        self.assertIn(
            self.alice_private_task,
            Task.objects.visible_to(self.alice),
        )
        self.assertNotIn(
            self.alice_private_task,
            Task.objects.visible_to(self.bob),
        )

    def test_shared_member_can_view_shared_task(self):
        self.assertIn(self.shared_task, Task.objects.visible_to(self.bob))

    def test_viewer_can_read_but_not_edit_shared_task(self):
        self.assertIn(self.shared_task, Task.objects.visible_to(self.viewer))
        self.assertNotIn(self.shared_task, Task.objects.editable_by(self.viewer))

    def test_superuser_status_does_not_bypass_normal_task_query_visibility(self):
        self.bob.is_staff = True
        self.bob.is_superuser = True
        self.bob.save(update_fields=["is_staff", "is_superuser"])

        self.assertNotIn(
            self.alice_private_task,
            Task.objects.visible_to(self.bob),
        )

    def test_deactivated_membership_removes_future_shared_access(self):
        membership = self.shared_project.memberships.get(user=self.bob)
        membership.is_active = False
        membership.save(update_fields=["is_active"])

        self.assertNotIn(self.shared_task, Task.objects.visible_to(self.bob))

    def test_personal_task_cannot_be_assigned_to_another_user(self):
        task = Task(
            title="Invalid private assignment",
            creator=self.alice,
            assignee=self.bob,
        )

        with self.assertRaises(ValidationError):
            task.full_clean()
