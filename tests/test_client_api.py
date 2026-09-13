"""Authorization and minimization tests for the first-party native client API."""

import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from projects.models import Project, ProjectMembership
from tasks.models import Task


class NativeClientTaskAPITests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(
            username="client-owner", password="owner-test-password"
        )
        self.viewer = users.objects.create_user(
            username="client-viewer", password="viewer-test-password"
        )
        self.other = users.objects.create_user(
            username="client-other", password="other-test-password"
        )

        self.shared_project = Project.objects.create(
            owner=self.owner,
            name="Shared Native Project",
            visibility=Project.Visibility.SHARED,
        )
        self.membership = ProjectMembership.objects.create(
            project=self.shared_project,
            user=self.viewer,
            role=ProjectMembership.Role.VIEWER,
        )
        self.private_project = Project.objects.create(
            owner=self.owner,
            name="Owner Private Project",
            visibility=Project.Visibility.PRIVATE,
        )

        due = timezone.now() + timedelta(days=1)
        self.personal = Task.objects.create(
            creator=self.viewer,
            assignee=self.viewer,
            title="Personal client task",
            description="Personal description must not appear in list payloads",
            due_at=due,
            priority=Task.Priority.P2_HIGH,
        )
        self.shared = Task.objects.create(
            creator=self.owner,
            project=self.shared_project,
            title="Shared read-only task",
            description="Shared sensitive description",
            due_at=due + timedelta(hours=1),
            priority=Task.Priority.P1_URGENT,
        )
        self.completed = Task.objects.create(
            creator=self.viewer,
            assignee=self.viewer,
            title="Completed personal task",
            status=Task.Status.COMPLETED,
            due_at=due - timedelta(days=1),
        )
        Task.objects.create(
            creator=self.owner,
            project=self.private_project,
            title="Private owner task",
        )
        Task.objects.create(
            creator=self.other,
            title="Other personal task",
        )

        self.url = reverse("api:client-tasks")

    def test_unauthenticated_request_is_rejected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertIn("Cookie", response["Vary"])

    def test_default_list_contains_only_visible_active_tasks(self):
        self.client.force_login(self.viewer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["schema"], "goreecloud.tasks.client-task-list.v1")
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["authorization"]["identity"], self.viewer.username)
        self.assertEqual(payload["returned"], 2)

        by_id = {task["id"]: task for task in payload["tasks"]}
        self.assertEqual(set(by_id), {self.personal.id, self.shared.id})
        self.assertTrue(by_id[self.personal.id]["editable"])
        self.assertFalse(by_id[self.shared.id]["editable"])
        self.assertEqual(by_id[self.shared.id]["project"]["name"], "Shared Native Project")

        serialized = json.dumps(payload)
        self.assertNotIn("Personal description must not appear", serialized)
        self.assertNotIn("Shared sensitive description", serialized)
        self.assertNotIn("Private owner task", serialized)
        self.assertNotIn("Other personal task", serialized)
        self.assertNotIn("Completed personal task", serialized)
        self.assertNotIn("description", serialized)
        self.assertNotIn("comments", serialized)
        self.assertNotIn("reminder", serialized)

    def test_completed_state_is_explicit(self):
        self.client.force_login(self.viewer)
        response = self.client.get(self.url, {"state": "completed"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["returned"], 1)
        self.assertEqual(payload["tasks"][0]["id"], self.completed.id)

    def test_project_and_status_filters_cannot_broaden_visibility(self):
        self.client.force_login(self.viewer)
        visible = self.client.get(
            self.url,
            {"project": self.shared_project.id, "status": Task.Status.PLANNED},
        )
        self.assertEqual(visible.status_code, 200)
        self.assertEqual(visible.json()["returned"], 1)
        self.assertEqual(visible.json()["tasks"][0]["id"], self.shared.id)

        hidden = self.client.get(self.url, {"project": self.private_project.id})
        self.assertEqual(hidden.status_code, 200)
        self.assertEqual(hidden.json()["returned"], 0)

    def test_membership_revocation_removes_shared_task_immediately(self):
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.url).json()["returned"], 2)

        self.membership.is_active = False
        self.membership.save(update_fields=["is_active"])

        payload = self.client.get(self.url).json()
        self.assertEqual(payload["returned"], 1)
        self.assertEqual(payload["tasks"][0]["id"], self.personal.id)

    def test_identity_cannot_be_selected_by_query_parameter(self):
        self.client.force_login(self.viewer)
        response = self.client.get(self.url, {"username": self.owner.username, "state": "all"})
        payload = response.json()
        self.assertEqual(payload["authorization"]["identity"], self.viewer.username)
        self.assertNotIn("Private owner task", json.dumps(payload))

    def test_invalid_filters_fail_closed(self):
        self.client.force_login(self.viewer)
        for params in (
            {"state": "everything"},
            {"status": "not-a-status"},
            {"project": "abc"},
            {"project": "0"},
            {"limit": "0"},
            {"limit": "201"},
            {"limit": "lots"},
        ):
            with self.subTest(params=params):
                response = self.client.get(self.url, params)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_limit_is_bounded_and_reported(self):
        self.client.force_login(self.viewer)
        response = self.client.get(self.url, {"limit": "1"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["filters"]["limit"], 1)
        self.assertEqual(payload["returned"], 1)

    def test_inactive_user_is_rejected_even_with_session(self):
        self.client.force_login(self.viewer)
        self.viewer.is_active = False
        self.viewer.save(update_fields=["is_active"])
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_endpoint_is_get_only(self):
        self.client.force_login(self.viewer)
        response = self.client.post(self.url, data={})
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response["Allow"], "GET")
        self.assertEqual(response["Cache-Control"], "private, no-store")
