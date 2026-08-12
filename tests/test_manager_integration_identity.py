"""Regression tests for the GoreeCloud Manager integration identity lifecycle."""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from projects.models import Project, ProjectMembership
from tasks.models import Task


class ManagerIntegrationIdentityValidationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="project-owner",
            password="owner-test-password",
        )
        self.identity = user_model.objects.create(username="goreecloud-manager-integration")
        self.identity.set_unusable_password()
        self.identity.save(update_fields=["password"])
        self.project = Project.objects.create(
            owner=self.owner,
            name="Approved Operations",
            visibility=Project.Visibility.SHARED,
        )
        ProjectMembership.objects.create(
            project=self.project,
            user=self.identity,
            role=ProjectMembership.Role.VIEWER,
        )

    def validate(self, *, require_membership=True):
        output = StringIO()
        args = [
            "validate_manager_integration_identity",
            "--username",
            self.identity.username,
        ]
        if require_membership:
            args.append("--require-membership")
        call_command(*args, stdout=output)
        return output.getvalue()

    def test_dedicated_viewer_identity_passes_validation(self):
        output = self.validate()

        self.assertIn("passed least-privilege validation", output)
        self.assertIn("Approved Operations", output)

    def test_privileged_or_interactive_identity_is_rejected(self):
        cases = (
            ("is_staff", True, "staff access"),
            ("is_superuser", True, "superuser access"),
        )
        for field, value, expected in cases:
            with self.subTest(field=field):
                setattr(self.identity, field, value)
                self.identity.save(update_fields=[field])
                with self.assertRaisesMessage(CommandError, expected):
                    self.validate()
                setattr(self.identity, field, False)
                self.identity.save(update_fields=[field])

        self.identity.set_password("interactive-test-password")
        self.identity.save(update_fields=["password"])
        with self.assertRaisesMessage(CommandError, "usable interactive password"):
            self.validate()

    def test_non_viewer_or_invalid_project_scope_is_rejected(self):
        membership = ProjectMembership.objects.get(
            project=self.project,
            user=self.identity,
        )
        membership.role = ProjectMembership.Role.MEMBER
        membership.save(update_fields=["role"])
        with self.assertRaisesMessage(CommandError, "not Viewer"):
            self.validate()

        membership.role = ProjectMembership.Role.VIEWER
        membership.save(update_fields=["role"])
        self.project.visibility = Project.Visibility.PRIVATE
        self.project.save(update_fields=["visibility"])
        with self.assertRaisesMessage(CommandError, "is not Shared"):
            self.validate()

        self.project.visibility = Project.Visibility.SHARED
        self.project.is_archived = True
        self.project.save(update_fields=["visibility", "is_archived"])
        with self.assertRaisesMessage(CommandError, "is archived"):
            self.validate()

    def test_project_ownership_and_personal_tasks_are_rejected(self):
        owned = Project.objects.create(
            owner=self.identity,
            name="Service Account Project",
            visibility=Project.Visibility.PRIVATE,
        )
        with self.assertRaisesMessage(CommandError, f"owns project(s): {owned.id}"):
            self.validate()

        owned.delete()
        task = Task.objects.create(
            title="Service account personal task",
            creator=self.identity,
            assignee=self.identity,
        )
        with self.assertRaisesMessage(
            CommandError,
            f"owns private personal task(s): {task.id}",
        ):
            self.validate()

    def test_membership_can_be_optional_during_preprovisioning(self):
        ProjectMembership.objects.filter(user=self.identity).update(is_active=False)

        output = self.validate(require_membership=False)
        self.assertIn("Active approved Viewer memberships: none", output)

        with self.assertRaisesMessage(CommandError, "no active Viewer project membership"):
            self.validate(require_membership=True)

    def test_email_address_is_rejected(self):
        self.identity.email = "integration@example.invalid"
        self.identity.save(update_fields=["email"])

        with self.assertRaisesMessage(CommandError, "email address assigned"):
            self.validate()
