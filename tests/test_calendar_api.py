"""Authorization, minimization, mutation, and conflict tests for Calendar integration."""

import json
import os
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from collaboration.models import ActivityEvent
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
        self.member = users.objects.create_user(
            username="calendar-member", password="member-test-password"
        )
        self.other = users.objects.create_user(
            username="calendar-other", password="other-test-password"
        )

        self.shared_project = Project.objects.create(
            owner=self.owner,
            name="Shared Schedule",
            visibility=Project.Visibility.SHARED,
        )
        self.viewer_membership = ProjectMembership.objects.create(
            project=self.shared_project,
            user=self.viewer,
            role=ProjectMembership.Role.VIEWER,
        )
        self.member_membership = ProjectMembership.objects.create(
            project=self.shared_project,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
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
        self.member_task = Task.objects.create(
            creator=self.member,
            assignee=self.member,
            project=self.shared_project,
            title="Member editable scheduled task",
            due_at=due + timedelta(hours=2),
        )
        Task.objects.create(
            creator=self.owner,
            project=self.private_project,
            title="Private owner task",
            due_at=due,
        )
        Task.objects.create(
            creator=self.other,
            assignee=self.other,
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

        self.list_url = reverse("api:calendar-task-projections")
        self.create_url = reverse("api:calendar-task-create")

    def _environment(self, *, username=None, **overrides):
        values = {
            "TASKS_CALENDAR_API_ENABLED": "true",
            "TASKS_CALENDAR_API_USERNAME": username or self.viewer.username,
            "TASKS_CALENDAR_API_TOKEN": self.TOKEN,
            "TASKS_CALENDAR_API_TOKEN_FILE": "",
            "TASKS_CALENDAR_API_MAX_TASKS": "500",
        }
        values.update(overrides)
        return patch.dict(os.environ, values, clear=False)

    def _auth(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.TOKEN}"}

    def _get(self, url=None, *, username=None, query=None):
        with self._environment(username=username):
            return self.client.get(
                url or self.list_url,
                data=query or {},
                **self._auth(),
            )

    def _post(self, url, payload, *, username=None, client=None, content_type="application/json"):
        target_client = client or self.client
        with self._environment(username=username):
            return target_client.post(
                url,
                data=json.dumps(payload),
                content_type=content_type,
                **self._auth(),
            )

    def test_api_is_hidden_when_disabled(self):
        with self._environment(TASKS_CALENDAR_API_ENABLED="false"):
            response = self.client.get(self.list_url, **self._auth())
        self.assertEqual(response.status_code, 404)

    def test_missing_or_wrong_bearer_token_is_rejected(self):
        with self._environment():
            missing = self.client.get(self.list_url)
            wrong = self.client.get(
                self.list_url,
                HTTP_AUTHORIZATION="Bearer not-the-calendar-token",
            )
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(wrong.status_code, 401)
        self.assertEqual(missing["WWW-Authenticate"], "Bearer")

    def test_invalid_enabled_configuration_fails_closed(self):
        with self._environment(TASKS_CALENDAR_API_TOKEN="short"):
            response = self.client.get(
                self.list_url,
                HTTP_AUTHORIZATION="Bearer short",
            )
        self.assertEqual(response.status_code, 503)

    def test_projection_contains_only_visible_scheduled_active_tasks(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertEqual(payload["schema"], "goreecloud.tasks.calendar-projections.v1")
        self.assertEqual(payload["version"], 1)
        self.assertEqual(payload["authorization"]["identity"], self.viewer.username)
        self.assertIsNone(payload["window"])

        task_ids = [task["id"] for task in payload["tasks"]]
        self.assertEqual(
            task_ids,
            [self.personal.id, self.shared.id, self.member_task.id],
        )

        personal = payload["tasks"][0]
        self.assertEqual(personal["source"]["application"], "goreecloud-tasks")
        self.assertEqual(personal["source"]["api_version"], 1)
        self.assertEqual(personal["project"], None)
        self.assertEqual(personal["recurrence"]["value"], Task.Recurrence.DAILY)
        self.assertEqual(personal["priority"]["value"], Task.Priority.P2_HIGH)
        self.assertEqual(personal["revision"], personal["updated_at"])
        self.assertIn(f"/tasks/{self.personal.id}/", personal["authoritative_url"])

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

    def test_list_supports_bounded_time_window(self):
        start = self.personal.due_at - timedelta(minutes=1)
        end = self.shared.due_at + timedelta(minutes=1)
        response = self._get(
            query={"start": start.isoformat(), "end": end.isoformat()}
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            [item["id"] for item in payload["tasks"]],
            [self.personal.id, self.shared.id],
        )
        self.assertEqual(payload["window"]["start"], start.isoformat())
        self.assertEqual(payload["window"]["end"], end.isoformat())

    def test_invalid_windows_fail_closed(self):
        now = timezone.now()
        cases = [
            {"start": now.isoformat()},
            {"end": (now + timedelta(days=1)).isoformat()},
            {"start": now.isoformat(), "end": now.isoformat()},
            {
                "start": now.isoformat(),
                "end": (now + timedelta(days=94)).isoformat(),
            },
            {
                "start": now.replace(tzinfo=None).isoformat(),
                "end": (now + timedelta(days=1)).replace(tzinfo=None).isoformat(),
            },
        ]
        for query in cases:
            with self.subTest(query=query):
                self.assertEqual(self._get(query=query).status_code, 400)

    def test_projection_detail_rechecks_visibility(self):
        url = reverse(
            "api:calendar-task-projection-detail",
            args=[self.shared.id],
        )
        response = self._get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["task"]["id"], self.shared.id)

        self.viewer_membership.is_active = False
        self.viewer_membership.save(update_fields=["is_active"])
        self.assertEqual(self._get(url).status_code, 404)

    def test_membership_revocation_removes_shared_projections_immediately(self):
        before = self._get().json()
        self.assertIn(self.shared.id, [item["id"] for item in before["tasks"]])

        self.viewer_membership.is_active = False
        self.viewer_membership.save(update_fields=["is_active"])

        after = self._get().json()
        self.assertEqual(
            [item["id"] for item in after["tasks"]],
            [self.personal.id],
        )

    def test_inactive_configured_user_cannot_authenticate(self):
        self.viewer.is_active = False
        self.viewer.save(update_fields=["is_active"])
        self.assertEqual(self._get().status_code, 401)

    def test_request_cannot_choose_another_tasks_identity(self):
        response = self._get(query={"username": self.owner.username})
        payload = response.json()
        self.assertEqual(payload["authorization"]["identity"], self.viewer.username)
        self.assertNotIn("Private owner task", json.dumps(payload))

    def test_read_endpoints_are_get_only(self):
        detail_url = reverse(
            "api:calendar-task-projection-detail",
            args=[self.personal.id],
        )
        with self._environment():
            list_post = self.client.post(self.list_url, **self._auth())
            detail_post = self.client.post(detail_url, **self._auth())
        self.assertEqual(list_post.status_code, 405)
        self.assertEqual(detail_post.status_code, 405)
        self.assertEqual(list_post["Allow"], "GET")
        self.assertEqual(detail_post["Allow"], "GET")

    def test_calendar_can_create_limited_personal_task(self):
        due = timezone.now() + timedelta(days=2)
        response = self._post(
            self.create_url,
            {
                "title": "Created from Calendar",
                "due_at": due.isoformat(),
                "priority": Task.Priority.P1_URGENT,
                "project_id": None,
            },
        )
        self.assertEqual(response.status_code, 201)

        task = Task.objects.get(title="Created from Calendar")
        self.assertEqual(task.creator, self.viewer)
        self.assertEqual(task.assignee, self.viewer)
        self.assertIsNone(task.project)
        self.assertEqual(task.status, Task.Status.READY)
        self.assertEqual(task.recurrence, Task.Recurrence.NONE)
        self.assertEqual(task.priority, Task.Priority.P1_URGENT)
        self.assertEqual(task.due_at, due)

        event = ActivityEvent.objects.get(
            task=task,
            kind=ActivityEvent.Kind.TASK_CREATED,
        )
        self.assertEqual(event.details["source"], "goreecloud-calendar")
        self.assertNotIn(task.title, json.dumps(event.details))

    def test_viewer_cannot_create_into_shared_project(self):
        response = self._post(
            self.create_url,
            {
                "title": "Viewer cannot create",
                "due_at": (timezone.now() + timedelta(days=1)).isoformat(),
                "project_id": self.shared_project.id,
            },
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Task.objects.filter(title="Viewer cannot create").exists())

    def test_member_can_create_into_shared_project(self):
        response = self._post(
            self.create_url,
            {
                "title": "Member created",
                "due_at": (timezone.now() + timedelta(days=1)).isoformat(),
                "project_id": self.shared_project.id,
            },
            username=self.member.username,
        )
        self.assertEqual(response.status_code, 201)
        task = Task.objects.get(title="Member created")
        self.assertEqual(task.project, self.shared_project)
        self.assertEqual(task.creator, self.member)
        self.assertEqual(task.assignee, self.member)

    def test_create_rejects_unsupported_content_fields(self):
        response = self._post(
            self.create_url,
            {
                "title": "Should fail",
                "due_at": (timezone.now() + timedelta(days=1)).isoformat(),
                "description": "Calendar must not write this",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Task.objects.filter(title="Should fail").exists())

    def test_service_post_uses_bearer_auth_without_browser_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = self._post(
            self.create_url,
            {
                "title": "Bearer service task",
                "due_at": (timezone.now() + timedelta(days=1)).isoformat(),
            },
            client=csrf_client,
        )
        self.assertEqual(response.status_code, 201)

    def test_create_requires_json_and_timezone_aware_due_date(self):
        not_json = self._post(
            self.create_url,
            {
                "title": "Wrong content type",
                "due_at": timezone.now().isoformat(),
            },
            content_type="text/plain",
        )
        naive = self._post(
            self.create_url,
            {
                "title": "Naive time",
                "due_at": timezone.now().replace(tzinfo=None).isoformat(),
            },
        )
        self.assertEqual(not_json.status_code, 400)
        self.assertEqual(naive.status_code, 400)

    def test_editable_personal_task_can_be_rescheduled_with_revision_guard(self):
        old_revision = self.personal.updated_at.isoformat()
        new_due = self.personal.due_at + timedelta(days=3)
        url = reverse(
            "api:calendar-task-reschedule",
            args=[self.personal.id],
        )
        response = self._post(
            url,
            {
                "due_at": new_due.isoformat(),
                "expected_updated_at": old_revision,
            },
        )
        self.assertEqual(response.status_code, 200)

        self.personal.refresh_from_db()
        self.assertEqual(self.personal.due_at, new_due)
        self.assertNotEqual(self.personal.updated_at.isoformat(), old_revision)
        self.assertEqual(
            response.json()["task"]["revision"],
            self.personal.updated_at.isoformat(),
        )

        event = ActivityEvent.objects.filter(
            task=self.personal,
            kind=ActivityEvent.Kind.TASK_UPDATED,
        ).latest("id")
        self.assertEqual(event.details["source"], "goreecloud-calendar")
        self.assertEqual(event.details["fields"], ["due_at"])

    def test_viewer_cannot_reschedule_shared_task(self):
        url = reverse(
            "api:calendar-task-reschedule",
            args=[self.shared.id],
        )
        response = self._post(
            url,
            {
                "due_at": (self.shared.due_at + timedelta(days=1)).isoformat(),
                "expected_updated_at": self.shared.updated_at.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_member_can_reschedule_shared_task(self):
        url = reverse(
            "api:calendar-task-reschedule",
            args=[self.member_task.id],
        )
        new_due = self.member_task.due_at + timedelta(days=1)
        response = self._post(
            url,
            {
                "due_at": new_due.isoformat(),
                "expected_updated_at": self.member_task.updated_at.isoformat(),
            },
            username=self.member.username,
        )
        self.assertEqual(response.status_code, 200)
        self.member_task.refresh_from_db()
        self.assertEqual(self.member_task.due_at, new_due)

    def test_stale_revision_returns_conflict_without_overwriting_task(self):
        old_revision = self.personal.updated_at.isoformat()
        authoritative_due = self.personal.due_at + timedelta(hours=6)
        self.personal.due_at = authoritative_due
        self.personal.save(update_fields=["due_at", "updated_at"])
        current_revision = self.personal.updated_at.isoformat()

        url = reverse(
            "api:calendar-task-reschedule",
            args=[self.personal.id],
        )
        response = self._post(
            url,
            {
                "due_at": (authoritative_due + timedelta(days=2)).isoformat(),
                "expected_updated_at": old_revision,
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["current_revision"], current_revision)

        self.personal.refresh_from_db()
        self.assertEqual(self.personal.due_at, authoritative_due)

    def test_reschedule_requires_expected_revision(self):
        url = reverse(
            "api:calendar-task-reschedule",
            args=[self.personal.id],
        )
        response = self._post(
            url,
            {"due_at": (self.personal.due_at + timedelta(days=1)).isoformat()},
        )
        self.assertEqual(response.status_code, 400)
