"""Authorization and minimization tests for GoreeCloud Calendar task projections."""

import json
import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from projects.models import Project, ProjectMembership
from tasks.models import Task


class CalendarProjectionAPITests(TestCase):
    TOKEN = "calendar-api-test-token-0123456789abcdef0123456789abcdef"

    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(
            username="calendar-owner", password="owner-test-password"
        )
        self.viewer = users.objects.create_user(
            username="calendar-viewer", password="viewer-test-password"
        )
        self.other = users.objects.create_user(
            username="calendar-other", password="other-test-password"
        )

        self.shared_project = Project.objects.create(
            owner=self.owner,
            name="Shared Schedule",
            visibility=Project.Visibility.SHARED,
        )
        self.membership = ProjectMembership.objects.create(
            project=self.shared_project,
            user=self.viewer,
            role=ProjectMembership.Role.VIEWER,
        )
        self.private_project = Project.objects.create(
            owner=self.owner,
            name="Owner Private",
            visibility=Project.Visibility.PRIVATE,
        )

        due = timezone.now() + timedelta(days=1)
        self.personal = Task.objects.create(
            creator=self.viewer,
            assignee=self.viewer,
            title="Personal scheduled task",
            description="Private detail not required by Calendar",
            due_at=due,
            priority=Task.Priority.P2_HIGH,
            recurrence=Task.Recurrence.DAILY,
        )
        self.shared = Task.objects.create(
            creator=self.owner,
            project=self.shared_project,
            title="Shared scheduled task",
            description="Shared sensitive details",
            due_at=due + timedelta(hours=1),
            priority=Task.Priority.P1_URGENT,
        )
        Task.objects.create(
            creator=self.owner,
            project=self.private_project,
            title="Private owner task",
            due_at=due,
        )
        Task.objects.create(
            creator=self.other,
            title="Other personal task",
            due_at=due,
        )
        Task.objects.create(
            creator=self.viewer,
            assignee=self.viewer,
            title="Unscheduled task",
        )
        Task.objects.create(
            creator=self.viewer,
            assignee=self.viewer,
            title="Completed scheduled task",
            due_at=due,
            status=Task.Status.COMPLETED,
        )

        self.url = reverse("api:calendar-task-projections")

    def _environment(self, **overrides):
        values = {
            "TASKS_CALENDAR_API_ENABLED": "true",
            "TASKS_CALENDAR_API_USERNAME": self.viewer.username,
            "TASKS_CALENDAR_API_TOKEN": self.TOKEN,
            "TASKS_CALENDAR_API_TOKEN_FILE": "",
            "TASKS_CALENDAR_API_MAX_TASKS": "500",
        }
        values.update(overrides)
        return patch.dict(os.environ, values, clear=False)

    def _get(self, token=None):
        with self._environment():
            return self.client.get(
                self.url,
                HTTP_AUTHORIZATION=f"Bearer {token or self.TOKEN}",
            )

    def test_api_is_hidden_when_disabled(self):
        with self._environment(TASKS_CALENDAR_API_ENABLED="false"):
            response = self.client.get(
                self.url, HTTP_AUTHORIZATION=f"Bearer {self.TOKEN}"
            )
        self.assertEqual(response.status_code, 404)

    def test_missing_or_wrong_bearer_token_is_rejected(self):
        with self._environment():
            missing = self.client.get(self.url)
            wrong = self.client.get(
                self.url, HTTP_AUTHORIZATION="Bearer not-the-calendar-token"
            )
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(missing["WWW-Authenticate"], "Bearer")

    def test_invalid_enabled_configuration_fails_closed(self):
        with self._environment(TASKS_CALENDAR_API_TOKEN="short"):
            response = self.client.get(
                self.url, HTTP_AUTHORIZATION="Bearer short"
            )
        self.assertEqual(response.status_code, 503)

    def test_projection_contains_only_visible_scheduled_active_tasks(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["schema"], "goreecloud.tasks.calendar-projections.v1")
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["authorization"]["identity"], self.viewer.username)
        self.assertEqual(payload["returned"], 2)

        task_ids = [task["id"] for task in payload["tasks"]]
        self.assertEqual(task_ids, [self.personal.id, self.shared.id])

        personal = payload["tasks"][0]
        self.assertEqual(personal["project"], None)
        self.assertEqual(personal["recurrence"]["value"], Task.Recurrence.DAILY)
        self.assertEqual(personal["priority"]["value"], Task.Priority.P2_HIGH)

        shared = payload["tasks"][1]
        self.assertEqual(shared["project"]["name"], "Shared Schedule")

        serialized = json.dumps(payload)
        self.assertNotIn("Private detail not required by Calendar", serialized)
        self.assertNotIn("Shared sensitive details", serialized)
        self.assertNotIn("Private owner task", serialized)
        self.assertNotIn("Other personal task", serialized)
        self.assertNotIn("Unscheduled task", serialized)
        self.assertNotIn("Completed scheduled task", serialized)
        self.assertNotIn("description", serialized)
        self.assertNotIn("comments", serialized)
        self.assertNotIn("labels", serialized)
        self.assertNotIn("assignee", serialized)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertIn("Authorization", response["Vary"].split(", "))

    def test_membership_revocation_removes_shared_projection_immediately(self):
        self.assertEqual(self._get().json()["returned"], 2)

        self.membership.is_active = False
        self.membership.save(update_fields=["is_active"])

        payload = self._get().json()
        self.assertEqual(payload["returned"], 1)
        self.assertEqual(payload["tasks"][0]["id"], self.personal.id)

    def test_inactive_configured_user_cannot_authenticate(self):
        self.viewer.is_active = False
        self.viewer.save(update_fields=["is_active"])
        self.assertEqual(self._get().status_code, 401)

    def test_request_cannot_choose_another_tasks_identity(self):
        with self._environment():
            response = self.client.get(
                self.url + f"?username={self.owner.username}",
                HTTP_AUTHORIZATION=f"Bearer {self.TOKEN}",
            )
        payload = response.json()
        self.assertEqual(payload["authorization"]["identity"], self.viewer.username)
        self.assertNotIn("Private owner task", json.dumps(payload))

    def test_api_is_get_only(self):
        with self._environment():
            response = self.client.post(
                self.url,
                data={},
                HTTP_AUTHORIZATION=f"Bearer {self.TOKEN}",
            )
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "GET")
