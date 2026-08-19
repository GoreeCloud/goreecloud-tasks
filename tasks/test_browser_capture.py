import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from collaboration.models import ActivityEvent
from projects.models import Project

from .models import Task


class BrowserCaptureTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="capture-user", password="test-password")
        self.url = reverse("tasks:browser_capture")

    def _post(self, payload, *, content_type="application/json"):
        body = json.dumps(payload) if content_type == "application/json" else str(payload)
        return self.client.post(self.url, data=body, content_type=content_type)

    def test_capture_requires_authenticated_service_session(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_capture_page_is_no_store_and_frame_denied(self):
        self.client.force_login(self.user)
        for path in (self.url, f"{self.url}/"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("default-src 'none'", response["Content-Security-Policy"])
            self.assertIn("script-src 'self'", response["Content-Security-Policy"])
            self.assertEqual(response["Cache-Control"], "no-store, max-age=0")
            self.assertEqual(response["Referrer-Policy"], "no-referrer")
            self.assertEqual(response["X-Frame-Options"], "DENY")

    def test_capture_page_rejects_query_parameters(self):
        self.client.force_login(self.user)
        response = self.client.get(f"{self.url}?payload=must-not-travel-in-url")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Task.objects.exists())

    def test_selection_capture_creates_private_ready_task_through_normal_boundary(self):
        self.client.force_login(self.user)
        response = self._post(
            {
                "kind": "selection",
                "title": "Review captured deployment note",
                "description": "Selected text\n\nSource: https://example.com/guide",
                "source_url": "https://example.com/guide",
                "project": 999999,
                "assignee": 999999,
                "status": Task.Status.COMPLETED,
            }
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["ok"])

        task = Task.objects.get(pk=body["task_id"])
        self.assertEqual(task.creator, self.user)
        self.assertEqual(task.assignee, self.user)
        self.assertIsNone(task.project)
        self.assertEqual(task.priority, Task.Priority.P3_STANDARD)
        self.assertEqual(task.status, Task.Status.READY)
        self.assertEqual(task.title, "Review captured deployment note")
        self.assertIn("https://example.com/guide", task.description)
        self.assertTrue(
            ActivityEvent.objects.filter(
                task=task,
                kind=ActivityEvent.Kind.TASK_CREATED,
                actor=self.user,
            ).exists()
        )

    def test_capture_cannot_inject_an_existing_project(self):
        project = Project.objects.create(name="Private Project", owner=self.user)
        self.client.force_login(self.user)
        response = self._post(
            {
                "kind": "link",
                "title": "Captured link",
                "description": "Source: https://example.com/task",
                "source_url": "https://example.com/task",
                "project": project.pk,
            }
        )
        self.assertEqual(response.status_code, 201)
        task = Task.objects.get(pk=response.json()["task_id"])
        self.assertIsNone(task.project)

    def test_capture_rejects_embedded_url_credentials(self):
        self.client.force_login(self.user)
        response = self._post(
            {
                "kind": "link",
                "title": "Unsafe URL",
                "description": "",
                "source_url": "https://user:secret@example.com/path",
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Task.objects.exists())

    def test_capture_rejects_wrong_content_type_and_kind(self):
        self.client.force_login(self.user)
        response = self._post({"title": "No JSON"}, content_type="text/plain")
        self.assertEqual(response.status_code, 400)

        response = self._post(
            {
                "kind": "page",
                "title": "Wrong kind",
                "description": "",
                "source_url": "https://example.com",
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Task.objects.exists())

    def test_capture_rejects_oversized_title_and_request(self):
        self.client.force_login(self.user)
        response = self._post(
            {
                "kind": "selection",
                "title": "x" * 501,
                "description": "",
                "source_url": "https://example.com",
            }
        )
        self.assertEqual(response.status_code, 400)

        response = self._post(
            {
                "kind": "selection",
                "title": "Bounded",
                "description": "x" * (24 * 1024),
                "source_url": "https://example.com",
            }
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Task.objects.exists())

    def test_browser_client_contract_avoids_persistent_storage_and_url_payloads(self):
        source = Path("static/js/browser-capture.js").read_text(encoding="utf-8")
        for forbidden in (
            "localStorage",
            "sessionStorage",
            "indexedDB",
            "BroadcastChannel",
            "URLSearchParams",
            "window.location.search",
            "window.location.hash",
            "Authorization",
            "Bearer ",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn('const PAYLOAD_EVENT = "GoreeCloudCapturePayload"', source)
        self.assertIn('const RESULT_EVENT = "GoreeCloudCaptureResult"', source)
        self.assertIn('payload.destination !== "task"', source)
        self.assertIn('credentials: "same-origin"', source)
        self.assertIn('notifyBrowser("saved")', source)
        self.assertIn('notifyBrowser("cancelled")', source)
