"""Functional tests for project settings, membership, and sharing boundaries."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from projects.models import Project, ProjectMembership
from tasks.forms import TaskForm
from tasks.models import Task


class ProjectWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="test-password")
        self.member = User.objects.create_user(username="member", password="test-password")
        self.viewer = User.objects.create_user(username="viewer", password="test-password")
        self.outsider = User.objects.create_user(username="outsider", password="test-password")

        self.private_project = Project.objects.create(
            owner=self.owner,
            name="Private planning",
            visibility=Project.Visibility.PRIVATE,
        )
        self.shared_project = Project.objects.create(
            owner=self.owner,
            name="Shared planning",
            visibility=Project.Visibility.SHARED,
        )
        self.member_membership = ProjectMembership.objects.create(
            project=self.shared_project,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )
        self.viewer_membership = ProjectMembership.objects.create(
            project=self.shared_project,
            user=self.viewer,
            role=ProjectMembership.Role.VIEWER,
        )
        self.shared_task = Task.objects.create(
            title="Shared project task",
            creator=self.owner,
            assignee=self.member,
            project=self.shared_project,
            status=Task.Status.READY,
        )

    def test_project_list_shows_only_owned_or_explicitly_shared_projects(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse("projects:list"))

        self.assertContains(response, "Shared planning")
        self.assertNotContains(response, "Private planning")

        self.client.force_login(self.outsider)
        response = self.client.get(reverse("projects:list"))
        self.assertNotContains(response, "Shared planning")
        self.assertNotContains(response, "Private planning")

    def test_owner_can_create_project_and_is_assigned_as_owner(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("projects:create"),
            {
                "name": "New private project",
                "visibility": Project.Visibility.PRIVATE,
            },
        )

        project = Project.objects.get(name="New private project")
        self.assertRedirects(response, reverse("projects:detail", args=[project.pk]))
        self.assertEqual(project.owner, self.owner)
        self.assertEqual(project.visibility, Project.Visibility.PRIVATE)

    def test_unauthorized_user_cannot_open_private_project(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("projects:detail", args=[self.private_project.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_non_owner_cannot_edit_project_settings(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("projects:edit", args=[self.shared_project.pk]),
            {
                "name": "Changed by member",
                "visibility": Project.Visibility.SHARED,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.shared_project.refresh_from_db()
        self.assertEqual(self.shared_project.name, "Shared planning")

    def test_private_project_rejects_membership_add_until_sharing_is_explicit(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("projects:membership_add", args=[self.private_project.pk]),
            {
                "username": self.outsider.username,
                "role": ProjectMembership.Role.MEMBER,
            },
        )

        self.assertRedirects(
            response,
            reverse("projects:detail", args=[self.private_project.pk]),
        )
        self.assertFalse(
            ProjectMembership.objects.filter(
                project=self.private_project,
                user=self.outsider,
                is_active=True,
            ).exists()
        )

    def test_owner_can_add_existing_account_by_exact_username(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("projects:membership_add", args=[self.shared_project.pk]),
            {
                "username": self.outsider.username,
                "role": ProjectMembership.Role.MANAGER,
            },
        )

        self.assertRedirects(
            response,
            reverse("projects:detail", args=[self.shared_project.pk]),
        )
        membership = ProjectMembership.objects.get(
            project=self.shared_project,
            user=self.outsider,
        )
        self.assertTrue(membership.is_active)
        self.assertEqual(membership.role, ProjectMembership.Role.MANAGER)

    def test_owner_can_change_member_role(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse(
                "projects:membership_role_update",
                args=[self.shared_project.pk, self.member_membership.pk],
            ),
            {"role": ProjectMembership.Role.VIEWER},
        )

        self.assertRedirects(
            response,
            reverse("projects:detail", args=[self.shared_project.pk]),
        )
        self.member_membership.refresh_from_db()
        self.assertEqual(self.member_membership.role, ProjectMembership.Role.VIEWER)
        self.assertNotIn(self.shared_task, Task.objects.editable_by(self.member))

    def test_member_cannot_administer_membership(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse(
                "projects:membership_role_update",
                args=[self.shared_project.pk, self.viewer_membership.pk],
            ),
            {"role": ProjectMembership.Role.MANAGER},
        )

        self.assertEqual(response.status_code, 404)
        self.viewer_membership.refresh_from_db()
        self.assertEqual(self.viewer_membership.role, ProjectMembership.Role.VIEWER)

    def test_removing_member_revokes_future_project_access_without_deleting_record(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse(
                "projects:membership_remove",
                args=[self.shared_project.pk, self.member_membership.pk],
            )
        )

        self.assertRedirects(
            response,
            reverse("projects:detail", args=[self.shared_project.pk]),
        )
        self.member_membership.refresh_from_db()
        self.assertFalse(self.member_membership.is_active)
        self.assertFalse(self.shared_project.can_view(self.member))
        self.assertTrue(
            ProjectMembership.objects.filter(pk=self.member_membership.pk).exists()
        )

    def test_existing_assignee_can_be_retained_after_membership_revocation(self):
        self.member_membership.is_active = False
        self.member_membership.save(update_fields=["is_active"])

        self.shared_task.status = Task.Status.COMPLETED
        self.shared_task.save(update_fields=["status", "completed_at", "updated_at"])
        self.shared_task.refresh_from_db()

        self.assertEqual(self.shared_task.assignee, self.member)
        self.assertEqual(self.shared_task.status, Task.Status.COMPLETED)
        self.assertIsNotNone(self.shared_task.completed_at)

    def test_existing_assignee_can_be_retained_after_role_downgrade_to_viewer(self):
        self.member_membership.role = ProjectMembership.Role.VIEWER
        self.member_membership.save(update_fields=["role"])

        self.shared_task.status = Task.Status.COMPLETED
        self.shared_task.save(update_fields=["status", "completed_at", "updated_at"])
        self.shared_task.refresh_from_db()

        self.assertEqual(self.shared_task.assignee, self.member)
        self.assertEqual(self.shared_task.status, Task.Status.COMPLETED)
        self.assertIsNotNone(self.shared_task.completed_at)

    def test_switching_shared_project_to_private_revokes_active_memberships(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("projects:edit", args=[self.shared_project.pk]),
            {
                "name": self.shared_project.name,
                "visibility": Project.Visibility.PRIVATE,
            },
        )

        self.assertRedirects(
            response,
            reverse("projects:detail", args=[self.shared_project.pk]),
        )
        self.shared_project.refresh_from_db()
        self.member_membership.refresh_from_db()
        self.viewer_membership.refresh_from_db()
        self.assertEqual(self.shared_project.visibility, Project.Visibility.PRIVATE)
        self.assertFalse(self.member_membership.is_active)
        self.assertFalse(self.viewer_membership.is_active)

    def test_viewer_sees_project_tasks_as_read_only(self):
        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse("projects:detail", args=[self.shared_project.pk])
        )

        self.assertContains(response, "Shared project task")
        self.assertContains(response, "Read only")
        self.assertNotContains(
            response,
            reverse("tasks:task_edit", args=[self.shared_task.pk]),
        )

    def test_viewer_is_not_offered_as_new_task_assignee(self):
        form = TaskForm(user=self.owner, initial={"project": self.shared_project})
        assignees = form.fields["assignee"].queryset

        self.assertIn(self.owner, assignees)
        self.assertIn(self.member, assignees)
        self.assertNotIn(self.viewer, assignees)

    def test_task_form_rejects_new_viewer_assignment(self):
        form = TaskForm(
            data={
                "title": "Viewer assignment must fail",
                "project": self.shared_project.pk,
                "assignee": self.viewer.pk,
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
                project=self.shared_project,
                status=Task.Status.READY,
            )

    def test_model_accepts_owner_member_and_manager_assignments(self):
        manager_membership = ProjectMembership.objects.create(
            project=self.shared_project,
            user=self.outsider,
            role=ProjectMembership.Role.MANAGER,
        )
        self.assertTrue(manager_membership.is_active)

        owner_task = Task.objects.create(
            title="Owner assignment",
            creator=self.owner,
            assignee=self.owner,
            project=self.shared_project,
            status=Task.Status.READY,
        )
        member_task = Task.objects.create(
            title="Member assignment",
            creator=self.owner,
            assignee=self.member,
            project=self.shared_project,
            status=Task.Status.READY,
        )
        manager_task = Task.objects.create(
            title="Manager assignment",
            creator=self.owner,
            assignee=self.outsider,
            project=self.shared_project,
            status=Task.Status.READY,
        )

        self.assertEqual(owner_task.assignee, self.owner)
        self.assertEqual(member_task.assignee, self.member)
        self.assertEqual(manager_task.assignee, self.outsider)

    def test_task_create_preselects_only_an_authorized_editable_project(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("tasks:task_create"),
            {"project": self.shared_project.pk},
        )
        self.assertEqual(
            response.context["form"].initial["project"],
            self.shared_project,
        )

        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse("tasks:task_create"),
            {"project": self.shared_project.pk},
        )
        self.assertNotIn("project", response.context["form"].initial)
