"""Live ntfy integration validation for the GoreeCloud Tasks publisher boundary.

This module is skipped during the ordinary test suite. GitHub Actions enables it only
while a disposable authenticated ntfy instance with least-privilege ACLs is running.
"""

import json
import os
import unittest
from datetime import timedelta
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from notifications.models import NotificationPreference, TaskReminder
from notifications.services import publish_ntfy_reminder
from projects.models import Project
from tasks.models import Task


def _urlopen(request):
    return urlopen(request, timeout=5)


def _request(url, *, token=None, method="GET", body=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = body.encode("utf-8") if body is not None else None
    request = Request(url, data=data, method=method, headers=headers)
    return _urlopen(request)


@unittest.skipUnless(
    os.getenv("NTFY_VALIDATION_LIVE") == "1",
    "Disposable ntfy integration server is not enabled.",
)
class NtfyLiveIntegrationTests(TestCase):
    """Exercise the real Tasks HTTP publisher against an ACL-protected ntfy server."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base_url = os.environ["NTFY_BASE_URL"].rstrip("/")
        cls.subscriber_token = os.environ["NTFY_VALIDATION_SUBSCRIBER_TOKEN"]
        cls.outsider_token = os.environ["NTFY_VALIDATION_OUTSIDER_TOKEN"]
        cls.topic = os.environ.get(
            "NTFY_VALIDATION_TOPIC",
            "goreecloud-tasks-validation-user",
        )

    def setUp(self):
        self.user = User.objects.create_user(
            username="ntfy-validation-user",
            password="test-only-password",
        )
        self.project = Project.objects.create(
            owner=self.user,
            name="Ntfy validation project",
            visibility=Project.Visibility.PRIVATE,
        )
        self.task = Task.objects.create(
            title="Validate GoreeCloud Tasks ntfy delivery",
            description="SENSITIVE-DESCRIPTION-MUST-NOT-LEAVE-TASKS",
            creator=self.user,
            assignee=self.user,
            project=self.project,
            priority=Task.Priority.P0_CRITICAL,
            status=Task.Status.READY,
            due_at=timezone.now() + timedelta(hours=1),
        )
        NotificationPreference.objects.create(
            user=self.user,
            reminders_enabled=True,
            ntfy_enabled=True,
            ntfy_topic=self.topic,
        )
        self.reminder = TaskReminder.objects.create(
            user=self.user,
            task=self.task,
            remind_at=timezone.now() + timedelta(minutes=5),
        )

    def _expect_http_status(self, expected, request):
        with self.assertRaises(HTTPError) as ctx:
            _urlopen(request)
        self.assertEqual(ctx.exception.code, expected)

    def test_real_publish_and_acl_isolation(self):
        """Publish through Tasks, read as the exact subscriber, and deny broader paths."""
        publish_ntfy_reminder(self.reminder)

        with _request(
            f"{self.base_url}/{self.topic}/json?poll=1&since=latest",
            token=self.subscriber_token,
        ) as response:
            events = [
                json.loads(line)
                for line in response.read().decode("utf-8").splitlines()
                if line.strip()
            ]

        messages = [event for event in events if event.get("event") == "message"]
        self.assertEqual(len(messages), 1)
        message = messages[0]

        self.assertEqual(message["topic"], self.topic)
        self.assertEqual(message["title"], "GoreeCloud Tasks reminder")
        self.assertEqual(message["priority"], 5)
        self.assertIn("alarm_clock", message.get("tags", []))
        self.assertIn(self.task.title, message["message"])
        self.assertIn(self.project.name, message["message"])
        self.assertNotIn(self.task.description, message["message"])
        self.assertNotIn(os.environ["NTFY_ACCESS_TOKEN"], message["message"])

        publisher_read = Request(
            f"{self.base_url}/{self.topic}/json?poll=1&since=latest",
            headers={"Authorization": f"Bearer {os.environ['NTFY_ACCESS_TOKEN']}"},
            method="GET",
        )
        self._expect_http_status(403, publisher_read)

        subscriber_write = Request(
            f"{self.base_url}/{self.topic}",
            data=b"subscriber must not publish",
            headers={"Authorization": f"Bearer {self.subscriber_token}"},
            method="POST",
        )
        self._expect_http_status(403, subscriber_write)

        outsider_read = Request(
            f"{self.base_url}/{self.topic}/json?poll=1&since=latest",
            headers={"Authorization": f"Bearer {self.outsider_token}"},
            method="GET",
        )
        self._expect_http_status(403, outsider_read)

        anonymous_read = Request(
            f"{self.base_url}/{self.topic}/json?poll=1&since=latest",
            method="GET",
        )
        self._expect_http_status(403, anonymous_read)

        unrelated_write = Request(
            f"{self.base_url}/goreecloud-other-validation",
            data=b"publisher must not leave its namespace",
            headers={"Authorization": f"Bearer {os.environ['NTFY_ACCESS_TOKEN']}"},
            method="POST",
        )
        self._expect_http_status(403, unrelated_write)
