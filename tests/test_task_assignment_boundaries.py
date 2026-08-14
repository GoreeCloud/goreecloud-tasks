"""Regression tests for task-assignment eligibility and historical retention."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from projects.models import Project, ProjectMembership
from tasks.forms import TaskForm
from tasks.models import Task


class TaskAssignmentBoundaryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="test-password")
        self.member = User.objects.create_user(username="member", password="test-password")
        self.manager = User.objects.create_user(username="manager", password="test-password")
        self.viewer = User.objects.create_user(username="viewer", password="test-password")
        self.other_project_member = User.objects.create_user(
            username="other-project-member",
            password="test-password",
        )
        self.disabled_member = User.objects.create_user(
            username="disabled-member",
            password="test-password",
            is_active=False,
        )

        self.project = Project.objects.create(
            owner=self.owner,
            name="Shared assignment project",
            visibility=Project.Visibility.SHARED,
        )
        self.other_project = Project.objects.create(
            owner=self.owner,
            name="Other shared project",
            visibility=Project.Visibility.SHARED,
        )
        self.member_membership = ProjectMembership.objects.create(
            project=self.project,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )
        self.manager_membership = ProjectMembership.objects.create(
            project=self.project,
            user=self.manager,
            role=ProjectMembership.Role.MANAGER,
        )
        self.viewer_membership = ProjectMembership.objects.create(
            project=self.project,
            user=self.viewer,
            role=ProjectMembership.Role.VIEWER,
        )
        self.disabled_membership = ProjectMembership.objects.create(
            project=self.project,
            user=self.disabled_member,
            role=ProjectMembership.Role.MEMBER,
        )
        self.other_project_membership = ProjectMembership.objects.create(
            project=self.other_project,
            user=self.other_project_member,
            role=ProjectMembership.Role.MEMBER,
        )

        self.member_task = Task.objects.create(
            title="Existing member assignment",
            creator=self.owner,
            assignee=self.member,
            project=self.project,
            status=Task.Status.READY,
        )

    def test_form_offers_only_active_users_with_editable_project_roles(self):
        form = TaskForm(user=self.owner, initial={"project": self.project})
        assignees = form.fields["assignee"].queryset

        self.assertIn(self.owner, assignees)
        self.assertIn(self.manager, assignees)
        self.assertIn(self.member, assignees)
        self.assertNotIn(self.viewer, assignees)
        self.assertNotIn(self.disabled_member, assignees)

    def test_project_form_does_not_offer_member_from_another_editable_project(self):
        form = TaskForm(user=self.owner, initial={"project": self.project})

        self.assertNotIn(
            self.other_project_member,
            form.fields["assignee"].queryset,
        )

    def test_private_task_form_offers_only_current_user(self):
        form = TaskForm(user=self.owner)

        self.assertEqual(
            list(form.fields["assignee"].queryset),
            [self.owner],
        )

    def test_bound_form_scopes_assignees_to_posted_project(self):
        form = TaskForm(
            data={
                "title": "Bound project assignment",
                "project": self.project.pk,
                "assignee": self.member.pk,
                "priority": Task.Priority.P3_STANDARD,
                "status": Task.Status.READY,
            },
            user=self.owner,
        )

        self.assertIn(self.member, form.fields["assignee"].queryset)
        self.assertNotIn(
            self.other_project_member,
            form.fields["assignee"].queryset,
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_new_viewer_assignment(self):
        form = TaskForm(
            data={
                "title": "Viewer assignment must fail",
                "project": self.project.pk,
                "assignee": self.viewer.pk,
                "priority": Task.Priority.P3_STANDARD,
                "status": Task.Status.READY,
            },
            user=self.owner,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("assignee", form.errors)

    def test_form_rejects_new_assignment_to_disabled_member(self):
        form = TaskForm(
            data={
                "title": "Disabled assignment must fail",
                "project": self.project.pk,
                "assignee": self.disabled_member.pk,
                "priority": Task.Priority.P3_STANDARD,
                "status": Task.Status.READY,
            },
            user=self.owner,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("assignee", form.errors)

    def test_form_rejects_assignment_to_member_of_different_project(self):
        form = TaskForm(
            data={
                "title": "Cross-project assignment must fail",
                "project": self.project.pk,
                "assignee": self.other_project_member.pk,
                "priority": Task.Priority.P3_STANDARD,
                "status": Task.Status.READY,
            },
            user=self.owner,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("assignee", form.errors)

    def test_model_rejects_new_viewer_assignment(self):
        with self.assertRaises(ValidationError):
            Task.objects.create(
                title="Viewer assignment must fail at model boundary",
                creator=self.owner,
                assignee=self.viewer,
                project=self.project,
                status=Task.Status.READY,
            )

    def test_model_rejects_new_assignment_to_disabled_member(self):
        with self.assertRaises(ValidationError):
            Task.objects.create(
                title="Disabled assignment must fail at model boundary",
                creator=self.owner,
                assignee=self.disabled_member,
                project=self.project,
                status=Task.Status.READY,
            )

    def test_model_rejects_assignment_to_member_of_different_project(self):
        with self.assertRaises(ValidationError):
            Task.objects.create(
                title="Cross-project assignment must fail at model boundary",
                creator=self.owner,
                assignee=self.other_project_member,
                project=self.project,
                status=Task.Status.READY,
            )

    def test_model_accepts_owner_member_and_manager_assignments(self):
        owner_task = Task.objects.create(
            title="Owner assignment",
            creator=self.owner,
            assignee=self.owner,
            project=self.project,
            status=Task.Status.READY,
        )
        member_task = Task.objects.create(
            title="Member assignment",
            creator=self.owner,
            assignee=self.member,
            project=self.project,
            status=Task.Status.READY,
        )
        manager_task = Task.objects.create(
            title="Manager assignment",
            creator=self.owner,
            assignee=self.manager,
            project=self.project,
            status=Task.Status.READY,
        )

        self.assertEqual(owner_task.assignee, self.owner)
        self.assertEqual(member_task.assignee, self.member)
        self.assertEqual(manager_task.assignee, self.manager)

    def test_existing_assignment_survives_role_downgrade_to_viewer(self):
        self.member_membership.role = ProjectMembership.Role.VIEWER
        self.member_membership.save(update_fields=["role"])

        self.member_task.status = Task.Status.COMPLETED
        self.member_task.save(update_fields=["status", "completed_at", "updated_at"])
        self.member_task.refresh_from_db()

        self.assertEqual(self.member_task.assignee, self.member)
        self.assertEqual(self.member_task.status, Task.Status.COMPLETED)

    def test_existing_assignment_survives_account_disablement(self):
        self.member.is_active = False
        self.member.save(update_fields=["is_active"])

        self.member_task.status = Task.Status.COMPLETED
        self.member_task.save(update_fields=["status", "completed_at", "updated_at"])
        self.member_task.refresh_from_db()

        self.assertEqual(self.member_task.assignee, self.member)
        self.assertEqual(self.member_task.status, Task.Status.COMPLETED)

    def test_existing_ineligible_assignee_remains_in_edit_form_for_retention(self):
        self.member_membership.role = ProjectMembership.Role.VIEWER
        self.member_membership.save(update_fields=["role"])
        self.member.is_active = False
        self.member.save(update_fields=["is_active"])

        form = TaskForm(instance=self.member_task, user=self.owner)

        self.assertIn(self.member, form.fields["assignee"].queryset)
