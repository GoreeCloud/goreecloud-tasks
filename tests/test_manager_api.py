"""Authorization and data-minimization tests for the GoreeCloud Manager API."""

import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from projects.models import Project, ProjectMembership
from tasks.models import Task


class ManagerAPITests(TestCase):
    TOKEN = "manager-api-test-token-0123456789abcdef0123456789abcdef"

    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            username="project-owner",
            password="owner-test-password",
        )
        self.manager_identity = user_model.objects.create_user(
            username="goreecloud-manager-integration",
            password=None,
        )
        self.other = user_model.objects.create_user(
            username="other-user",
            password="other-test-password",
        )

        self.shared_project = Project.objects.create(
            owner=self.owner,
            name="Infrastructure Work",
            visibility=Project.Visibility.SHARED,
        )
        self.membership = ProjectMembership.objects.create(
            project=self.shared_project,
            user=self.manager_identity,
            role=ProjectMembership.Role.VIEWER,
        )
        self.private_project = Project.objects.create(
            owner=self.owner,
            name="Owner Private Work",
            visibility=Project.Visibility.PRIVATE,
        )

        self.visible_operational = Task.objects.create(
            creator=self.owner,
            project=self.shared_project,
            title="Validate backup recovery path",
            description="Sensitive implementation details must not enter Manager output.",
            priority=Task.Priority.P1_URGENT,
            status=Task.Status.BLOCKED,
            is_goreecloud_work=True,
            assigned_system="Infrastructure Services VM",
            assigned_service="Kopia",
            environment="production-planning",
            workload_category="Recovery",
            blocker="Restore test not yet completed",
            resume_condition="Complete isolated restore validation",
            backup_prerequisite=True,
            recovery_requirement=True,
            validation_requirement=True,
            documentation_requirement=True,
            related_change_record="GoreeCloud Tasks change log",
            related_documentation="Backup and recovery standard",
        )
        Task.objects.create(
            creator=self.owner,
            project=self.shared_project,
            title="Ordinary shared family task",
            is_goreecloud_work=False,
        )
        Task.objects.create(
            creator=self.owner,
            project=self.private_project,
            title="Private operational task",
            is_goreecloud_work=True,
        )
        Task.objects.create(
            creator=self.other,
            title="Other user personal task",
            is_goreecloud_work=True,
        )
        Task.objects.create(
            creator=self.owner,
            project=self.shared_project,
            title="Completed operational task",
            status=Task.Status.COMPLETED,
            is_goreecloud_work=True,
        )

        self.url = reverse("api:manager-operational-tasks")

    def _environment(self, **overrides):
        values = {
            "TASKS_MANAGER_API_ENABLED": "true",
            "TASKS_MANAGER_API_USERNAME": self.manager_identity.username,
            "TASKS_MANAGER_API_TOKEN": self.TOKEN,
            "TASKS_MANAGER_API_TOKEN_FILE": "",
            "TASKS_MANAGER_API_MAX_TASKS": "100",
        }
        values.update(overrides)
        return patch.dict(os.environ, values, clear=False)

    def _get(self, token=None):
        with self._environment():
            return self.client.get(
                self.url,
                HTTP_AUTHORIZATION=f"Bearer {token or self.TOKEN}",
            )

    def test_api_is_hidden_when_not_enabled(self):
        with self._environment(TASKS_MANAGER_API_ENABLED="false"):
            response = self.client.get(
                self.url,
                HTTP_AUTHORIZATION=f"Bearer {self.TOKEN}",
            )
        self.assertEqual(response.status_code, 404)

    def test_missing_or_wrong_bearer_token_is_rejected(self):
        with self._environment():
            missing = self.client.get(self.url)
            wrong = self.client.get(
                self.url,
                HTTP_AUTHORIZATION="Bearer definitely-not-the-configured-token",
            )

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(missing["WWW-Authenticate"], "Bearer")

    def test_invalid_enabled_configuration_fails_closed(self):
        with self._environment(TASKS_MANAGER_API_TOKEN="short"):
            response = self.client.get(
                self.url,
                HTTP_AUTHORIZATION="Bearer short",
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"detail": "Integration configuration is unavailable."},
        )

    def test_get_returns_only_visible_active_operational_project_tasks(self):
        response = self._get()

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["schema"], "goreecloud.tasks.manager.v1")
        self.assertEqual(payload["version"], 1)
        self.assertEqual(
            payload["authorization"]["identity"],
            self.manager_identity.username,
        )
        self.assertEqual(payload["summary"]["total_open"], 1)
        self.assertEqual(payload["summary"]["blocked"], 1)
        self.assertEqual(payload["summary"]["p0"], 0)
        self.assertEqual(payload["summary"]["p1"], 1)
        self.assertEqual(payload["summary"]["returned"], 1)

        task = payload["tasks"][0]
        self.assertEqual(task["id"], self.visible_operational.id)
        self.assertEqual(task["title"], "Validate backup recovery path")
        self.assertEqual(task["project"]["name"], "Infrastructure Work")
        self.assertEqual(task["status"]["value"], Task.Status.BLOCKED)
        self.assertEqual(task["priority"]["value"], Task.Priority.P1_URGENT)
        self.assertEqual(task["assigned_service"], "Kopia")
        self.assertTrue(task["requirements"]["recovery"])

        serialized = json.dumps(payload)
        self.assertNotIn("Sensitive implementation details", serialized)
        self.assertNotIn("Ordinary shared family task", serialized)
        self.assertNotIn("Private operational task", serialized)
        self.assertNotIn("Other user personal task", serialized)
        self.assertNotIn("Completed operational task", serialized)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_revoking_last_viewer_membership_denies_future_api_authorization(self):
        self.assertEqual(self._get().status_code, 200)

        self.membership.is_active = False
        self.membership.save(update_fields=["is_active"])

        response = self._get()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"detail": "Integration identity is not authorized."},
        )
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_staff_or_superuser_drift_is_rejected_by_runtime_guard(self):
        self.manager_identity.is_staff = True
        self.manager_identity.is_superuser = True
        self.manager_identity.save(update_fields=["is_staff", "is_superuser"])

        response = self._get()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {"detail": "Integration identity is not authorized."},
        )

    def test_non_viewer_role_drift_is_rejected_by_runtime_guard(self):
        self.membership.role = ProjectMembership.Role.MEMBER
        self.membership.save(update_fields=["role"])

        response = self._get()
        self.assertEqual(response.status_code, 403)

    def test_interactive_password_drift_is_rejected_by_runtime_guard(self):
        self.manager_identity.set_password("unexpected-interactive-password")
        self.manager_identity.save(update_fields=["password"])

        response = self._get()
        self.assertEqual(response.status_code, 403)

    def test_api_is_get_only(self):
        with self._environment():
            response = self.client.post(
                self.url,
                data={},
                HTTP_AUTHORIZATION=f"Bearer {self.TOKEN}",
            )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "GET")
