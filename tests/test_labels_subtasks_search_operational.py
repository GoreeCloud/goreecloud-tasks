"""Tests for labels, subtasks, search, and GoreeCloud operational metadata."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from collaboration.models import ActivityEvent
from labels.models import Label
from projects.models import Project, ProjectMembership
from tasks.models import Task


class LabelAuthorizationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="test-password")
        self.member = User.objects.create_user(username="member", password="test-password")
        self.viewer = User.objects.create_user(username="viewer", password="test-password")
        self.other = User.objects.create_user(username="other", password="test-password")
        self.client.force_login(self.owner)

    def test_personal_labels_remain_private(self):
        response = self.client.post(reverse("labels:list"), {"name": "Private planning", "project": ""})
        self.assertRedirects(response, reverse("labels:list"))
        label = Label.objects.get(name="Private planning")
        self.assertEqual(label.owner, self.owner)
        self.assertIsNone(label.project)
        self.client.force_login(self.other)
        response = self.client.get(reverse("labels:list"))
        self.assertNotContains(response, "Private planning")
        self.assertFalse(Label.objects.visible_to(self.other).filter(pk=label.pk).exists())
        self.assertFalse(Label.objects.editable_by(self.other).filter(pk=label.pk).exists())

    def test_project_labels_follow_project_roles(self):
        project = Project.objects.create(owner=self.owner, name="Shared infrastructure", visibility=Project.Visibility.SHARED)
        ProjectMembership.objects.create(project=project, user=self.member, role=ProjectMembership.Role.MEMBER)
        ProjectMembership.objects.create(project=project, user=self.viewer, role=ProjectMembership.Role.VIEWER)
        self.client.force_login(self.member)
        response = self.client.post(reverse("labels:list"), {"name": "Maintenance", "project": project.pk})
        self.assertRedirects(response, reverse("labels:list"))
        label = Label.objects.get(project=project, name="Maintenance")
        self.assertEqual(label.owner, self.member)
        self.client.force_login(self.viewer)
        response = self.client.get(reverse("labels:list"))
        self.assertContains(response, "Maintenance")
        self.assertContains(response, "Read only")
        response = self.client.post(reverse("labels:list"), {"name": "Viewer should not create", "project": project.pk})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Label.objects.filter(name="Viewer should not create").exists())

    def test_task_editor_rejects_label_from_another_scope(self):
        personal_label = Label.objects.create(name="Mine", owner=self.owner)
        other_label = Label.objects.create(name="Other", owner=self.other)
        task = Task.objects.create(title="My task", creator=self.owner, assignee=self.owner, status=Task.Status.READY)
        response = self.client.post(reverse("tasks:task_edit", args=[task.pk]), {"title": task.title, "description": "", "project": "", "assignee": self.owner.pk, "priority": Task.Priority.P3_STANDARD, "status": Task.Status.READY, "due_at": "", "labels": [personal_label.pk, other_label.pk]})
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertFalse(task.labels.exists())

    def test_used_label_cannot_be_deleted_silently(self):
        label = Label.objects.create(name="In use", owner=self.owner)
        task = Task.objects.create(title="Labeled task", creator=self.owner, assignee=self.owner, status=Task.Status.READY)
        task.labels.add(label)
        response = self.client.post(reverse("labels:delete", args=[label.pk]))
        self.assertRedirects(response, reverse("labels:list"))
        self.assertTrue(Label.objects.filter(pk=label.pk).exists())
        self.assertTrue(task.labels.filter(pk=label.pk).exists())


class SubtaskTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="test-password")
        self.member = User.objects.create_user(username="member", password="test-password")
        self.viewer = User.objects.create_user(username="viewer", password="test-password")
        self.client.force_login(self.owner)

    def test_authorized_user_can_create_subtask_in_parent_scope(self):
        project = Project.objects.create(owner=self.owner, name="Build", visibility=Project.Visibility.SHARED)
        ProjectMembership.objects.create(project=project, user=self.member, role=ProjectMembership.Role.MEMBER)
        parent = Task.objects.create(title="Deploy service", creator=self.owner, assignee=self.owner, project=project, status=Task.Status.READY)
        self.client.force_login(self.member)
        response = self.client.post(reverse("tasks:subtask_add", args=[parent.pk]), {"title": "Run validation", "priority": Task.Priority.P2_HIGH, "due_at": ""})
        self.assertRedirects(response, reverse("tasks:task_detail", args=[parent.pk]))
        subtask = Task.objects.get(title="Run validation")
        self.assertEqual(subtask.parent, parent)
        self.assertEqual(subtask.project, project)
        self.assertEqual(subtask.creator, self.member)
        self.assertEqual(subtask.assignee, self.member)
        event = ActivityEvent.objects.get(task=subtask, kind=ActivityEvent.Kind.TASK_CREATED)
        self.assertEqual(event.actor, self.member)
        self.assertEqual(event.details["parent_task_id"], parent.pk)

    def test_viewer_cannot_create_subtask(self):
        project = Project.objects.create(owner=self.owner, name="Read only", visibility=Project.Visibility.SHARED)
        ProjectMembership.objects.create(project=project, user=self.viewer, role=ProjectMembership.Role.VIEWER)
        parent = Task.objects.create(title="Parent", creator=self.owner, assignee=self.owner, project=project, status=Task.Status.READY)
        self.client.force_login(self.viewer)
        response = self.client.post(reverse("tasks:subtask_add", args=[parent.pk]), {"title": "Forbidden child", "priority": Task.Priority.P3_STANDARD, "due_at": ""})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Task.objects.filter(title="Forbidden child").exists())

    def test_model_rejects_cross_project_parent(self):
        first = Project.objects.create(owner=self.owner, name="First")
        second = Project.objects.create(owner=self.owner, name="Second")
        parent = Task.objects.create(title="Parent", creator=self.owner, assignee=self.owner, project=first)
        with self.assertRaises(ValidationError):
            Task.objects.create(title="Invalid child", creator=self.owner, assignee=self.owner, project=second, parent=parent)


class SearchAndOperationalMetadataTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="test-password")
        self.other = User.objects.create_user(username="other", password="test-password")
        self.client.force_login(self.owner)

    def test_search_uses_visible_task_boundary_and_searches_labels_and_operational_fields(self):
        label = Label.objects.create(name="Network", owner=self.owner)
        visible = Task.objects.create(title="Review edge routing", description="Inspect private routing notes", creator=self.owner, assignee=self.owner, status=Task.Status.READY, is_goreecloud_work=True, assigned_system="Brume 3", assigned_service="NetBird", blocker="Waiting for maintenance window")
        visible.labels.add(label)
        hidden = Task.objects.create(title="Other user's secret NetBird work", creator=self.other, assignee=self.other, status=Task.Status.READY)
        for query in ("routing", "Network", "Brume 3", "NetBird", "maintenance"):
            response = self.client.get(reverse("tasks:search"), {"q": query})
            self.assertContains(response, visible.title)
            self.assertNotContains(response, hidden.title)

    def test_search_can_find_completed_accessible_work(self):
        task = Task.objects.create(title="Completed recovery rehearsal", creator=self.owner, assignee=self.owner, status=Task.Status.COMPLETED)
        response = self.client.get(reverse("tasks:search"), {"q": "recovery rehearsal"})
        self.assertContains(response, task.title)

    def test_operational_metadata_is_optional_for_ordinary_tasks(self):
        task = Task.objects.create(title="Buy groceries", creator=self.owner, assignee=self.owner, status=Task.Status.READY)
        self.assertFalse(task.is_goreecloud_work)
        self.assertEqual(task.assigned_system, "")
        self.assertFalse(task.backup_prerequisite)
        self.assertFalse(task.validation_requirement)

    def test_full_editor_saves_and_displays_operational_metadata(self):
        response = self.client.post(reverse("tasks:task_create"), {"title": "Upgrade Nextcloud", "description": "", "project": "", "assignee": self.owner.pk, "priority": Task.Priority.P2_HIGH, "status": Task.Status.PLANNED, "due_at": "", "is_goreecloud_work": "on", "assigned_system": "Infrastructure Services VM", "assigned_service": "Nextcloud", "environment": "Production", "workload_category": "Maintenance", "blocker": "Backup not yet verified", "resume_condition": "Verified backup is available", "backup_prerequisite": "on", "recovery_requirement": "on", "validation_requirement": "on", "documentation_requirement": "on", "related_change_record": "GoreeCloud — Change Log — Nextcloud", "related_documentation": "GoreeCloud — Strategy — Nextcloud and ONLYOFFICE Docs"})
        task = Task.objects.get(title="Upgrade Nextcloud")
        self.assertRedirects(response, reverse("tasks:task_edit", args=[task.pk]))
        self.assertTrue(task.is_goreecloud_work)
        self.assertEqual(task.assigned_service, "Nextcloud")
        self.assertTrue(task.backup_prerequisite)
        self.assertTrue(task.validation_requirement)
        detail = self.client.get(reverse("tasks:task_detail", args=[task.pk]))
        self.assertContains(detail, "Operational metadata")
        self.assertContains(detail, "Infrastructure Services VM")
        self.assertContains(detail, "Verified backup is available")
        self.assertContains(detail, "Validation required")

    def test_label_change_is_recorded_without_copying_label_names_into_activity_metadata(self):
        label = Label.objects.create(name="Sensitive-ish label", owner=self.owner)
        task = Task.objects.create(title="Track label update", creator=self.owner, assignee=self.owner, status=Task.Status.READY)
        response = self.client.post(reverse("tasks:task_edit", args=[task.pk]), {"title": task.title, "description": "", "project": "", "assignee": self.owner.pk, "priority": Task.Priority.P3_STANDARD, "status": Task.Status.READY, "due_at": "", "labels": [label.pk]})
        self.assertRedirects(response, reverse("tasks:task_edit", args=[task.pk]))
        event = ActivityEvent.objects.filter(task=task, kind=ActivityEvent.Kind.TASK_UPDATED).latest("id")
        self.assertEqual(event.details, {"fields": ["labels"]})
        self.assertNotIn(label.name, str(event.details))
