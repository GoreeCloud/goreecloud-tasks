"""Tests for versioned, authorization-scoped export and import boundaries."""

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from collaboration.models import ActivityEvent, TaskComment
from imports.schema import NormalizedImportBundle, NormalizedTask
from imports.todoist import TodoistImportAdapter
from labels.models import Label
from portability.exporters import EXPORT_FORMAT, SCHEMA_VERSION
from projects.models import Project, ProjectMembership
from tasks.models import Task


class PortableExportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", email="owner@example.invalid", password="test-password")
        self.member = User.objects.create_user(username="member", email="member@example.invalid", password="test-password")
        self.other = User.objects.create_user(username="other", email="other@example.invalid", password="test-password")
        self.client.force_login(self.owner)

    def _payload(self, response):
        return json.loads(response.content.decode("utf-8"))

    def test_user_export_is_authenticated_download_with_versioned_schema(self):
        response = self.client.get(reverse("portability:user_export"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment;", response["Content-Disposition"])
        self.assertEqual(response["Cache-Control"], "private, no-store")
        payload = self._payload(response)
        self.assertEqual(payload["format"], EXPORT_FORMAT)
        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        self.assertEqual(payload["scope"]["kind"], "user_archive")
        self.assertEqual(payload["scope"]["user_id"], self.owner.pk)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("portability:user_export")).status_code, 302)

    def test_user_archive_includes_owned_data_and_excludes_other_owned_project(self):
        personal_label = Label.objects.create(name="Private", owner=self.owner)
        personal_task = Task.objects.create(title="My private task", creator=self.owner, assignee=self.owner, status=Task.Status.COMPLETED)
        personal_task.labels.add(personal_label)
        owned_project = Project.objects.create(owner=self.owner, name="Owned shared project", visibility=Project.Visibility.SHARED)
        ProjectMembership.objects.create(project=owned_project, user=self.member, role=ProjectMembership.Role.MEMBER)
        project_label = Label.objects.create(name="Migration", owner=self.owner, project=owned_project)
        owned_task = Task.objects.create(title="Owned project task", creator=self.owner, assignee=self.member, project=owned_project, status=Task.Status.READY)
        owned_task.labels.add(project_label)
        TaskComment.objects.create(task=owned_task, author=self.member, body="Preserve this comment")
        ActivityEvent.objects.create(actor=self.owner, project=owned_project, task=owned_task, kind=ActivityEvent.Kind.TASK_UPDATED, summary="Updated task", details={"fields": ["labels"]})
        other_project = Project.objects.create(owner=self.other, name="Other user's shared project", visibility=Project.Visibility.SHARED)
        ProjectMembership.objects.create(project=other_project, user=self.owner, role=ProjectMembership.Role.MEMBER)
        hidden_shared_task = Task.objects.create(title="Visible but not export-owned", creator=self.other, assignee=self.owner, project=other_project)
        hidden_private_task = Task.objects.create(title="Completely private to other", creator=self.other, assignee=self.other)

        data = self._payload(self.client.get(reverse("portability:user_export")))["data"]
        task_ids = {item["id"] for item in data["tasks"]}
        project_ids = {item["id"] for item in data["projects"]}
        label_ids = {item["id"] for item in data["labels"]}
        self.assertIn(personal_task.pk, task_ids)
        self.assertIn(owned_task.pk, task_ids)
        self.assertNotIn(hidden_shared_task.pk, task_ids)
        self.assertNotIn(hidden_private_task.pk, task_ids)
        self.assertIn(owned_project.pk, project_ids)
        self.assertNotIn(other_project.pk, project_ids)
        self.assertIn(personal_label.pk, label_ids)
        self.assertIn(project_label.pk, label_ids)
        self.assertEqual(data["comments"][0]["body"], "Preserve this comment")
        self.assertEqual(data["activity"][0]["details"], {"fields": ["labels"]})

    def test_export_preserves_relationships_and_operational_fields(self):
        project = Project.objects.create(owner=self.owner, name="Operations")
        label = Label.objects.create(name="Backup", owner=self.owner, project=project)
        parent = Task.objects.create(title="Upgrade service", creator=self.owner, assignee=self.owner, project=project, is_goreecloud_work=True, assigned_system="Infrastructure Services VM", assigned_service="Tasks", backup_prerequisite=True, validation_requirement=True, related_change_record="GoreeCloud — Change Log — Tasks")
        parent.labels.add(label)
        child = Task.objects.create(title="Validate upgrade", creator=self.owner, assignee=self.owner, project=project, parent=parent)
        payload = self._payload(self.client.get(reverse("portability:project_export", args=[project.pk])))
        tasks = {item["id"]: item for item in payload["data"]["tasks"]}
        self.assertEqual(tasks[parent.pk]["label_ids"], [label.pk])
        self.assertEqual(tasks[child.pk]["parent_id"], parent.pk)
        self.assertEqual(tasks[parent.pk]["assigned_system"], "Infrastructure Services VM")
        self.assertTrue(tasks[parent.pk]["backup_prerequisite"])
        self.assertTrue(tasks[parent.pk]["validation_requirement"])
        self.assertEqual(tasks[parent.pk]["related_change_record"], "GoreeCloud — Change Log — Tasks")

    def test_project_bulk_export_is_owner_only(self):
        project = Project.objects.create(owner=self.owner, name="Shared", visibility=Project.Visibility.SHARED)
        ProjectMembership.objects.create(project=project, user=self.member, role=ProjectMembership.Role.MANAGER)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(reverse("portability:project_export", args=[project.pk])).status_code, 404)

    def test_export_user_references_do_not_include_email_or_authentication_fields(self):
        Task.objects.create(title="Portable", creator=self.owner, assignee=self.owner)
        payload = self._payload(self.client.get(reverse("portability:user_export")))
        serialized = json.dumps(payload)
        self.assertNotIn("owner@example.invalid", serialized)
        self.assertNotIn("password", serialized.lower())
        self.assertNotIn("session", serialized.lower())
        self.assertEqual(payload["data"]["users"], [{"id": self.owner.pk, "username": "owner"}])


class ImportBoundaryTests(TestCase):
    def test_source_neutral_bundle_can_represent_future_normalized_tasks(self):
        bundle = NormalizedImportBundle(source="fixture", tasks=(NormalizedTask(source_id="task-1", title="Imported task"),))
        self.assertEqual(bundle.tasks[0].source_id, "task-1")
        self.assertEqual(bundle.tasks[0].title, "Imported task")

    def test_todoist_adapter_does_not_claim_unverified_format_support(self):
        with self.assertRaises(NotImplementedError):
            TodoistImportAdapter().normalize({"unverified": "payload"})
