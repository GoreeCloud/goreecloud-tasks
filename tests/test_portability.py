"""Tests for versioned, authorization-scoped export, import, and restoration."""

import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from collaboration.models import ActivityEvent, TaskComment
from imports.executor import ImportExecutionError, execute_import
from imports.schema import (
    NormalizedImportBundle,
    NormalizedLabel,
    NormalizedProject,
    NormalizedTask,
)
from imports.todoist import TodoistImportAdapter
from labels.models import Label
from portability.exporters import (
    EXPORT_FORMAT,
    SCHEMA_VERSION,
    build_user_archive,
)
from portability.restorers import ArchiveRestoreError, restore_user_archive
from projects.models import Project, ProjectMembership
from tasks.models import Task


class PortableExportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.invalid",
            password="test-password",
        )
        self.member = User.objects.create_user(
            username="member",
            email="member@example.invalid",
            password="test-password",
        )
        self.other = User.objects.create_user(
            username="other",
            email="other@example.invalid",
            password="test-password",
        )
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
        self.assertEqual(
            self.client.get(reverse("portability:user_export")).status_code,
            302,
        )

    def test_user_archive_includes_owned_data_and_excludes_other_owned_project(self):
        personal_label = Label.objects.create(name="Private", owner=self.owner)
        personal_task = Task.objects.create(
            title="My private task",
            creator=self.owner,
            assignee=self.owner,
            status=Task.Status.COMPLETED,
        )
        personal_task.labels.add(personal_label)
        owned_project = Project.objects.create(
            owner=self.owner,
            name="Owned shared project",
            visibility=Project.Visibility.SHARED,
        )
        ProjectMembership.objects.create(
            project=owned_project,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )
        project_label = Label.objects.create(
            name="Migration",
            owner=self.owner,
            project=owned_project,
        )
        owned_task = Task.objects.create(
            title="Owned project task",
            creator=self.owner,
            assignee=self.member,
            project=owned_project,
            status=Task.Status.READY,
        )
        owned_task.labels.add(project_label)
        TaskComment.objects.create(
            task=owned_task,
            author=self.member,
            body="Preserve this comment",
        )
        ActivityEvent.objects.create(
            actor=self.owner,
            project=owned_project,
            task=owned_task,
            kind=ActivityEvent.Kind.TASK_UPDATED,
            summary="Updated task",
            details={"fields": ["labels"]},
        )
        other_project = Project.objects.create(
            owner=self.other,
            name="Other user's shared project",
            visibility=Project.Visibility.SHARED,
        )
        ProjectMembership.objects.create(
            project=other_project,
            user=self.owner,
            role=ProjectMembership.Role.MEMBER,
        )
        hidden_shared_task = Task.objects.create(
            title="Visible but not export-owned",
            creator=self.other,
            assignee=self.owner,
            project=other_project,
        )
        hidden_private_task = Task.objects.create(
            title="Completely private to other",
            creator=self.other,
            assignee=self.other,
        )

        data = self._payload(
            self.client.get(reverse("portability:user_export"))
        )["data"]
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
        label = Label.objects.create(
            name="Backup",
            owner=self.owner,
            project=project,
        )
        parent = Task.objects.create(
            title="Upgrade service",
            creator=self.owner,
            assignee=self.owner,
            project=project,
            is_goreecloud_work=True,
            assigned_system="Infrastructure Services VM",
            assigned_service="Tasks",
            backup_prerequisite=True,
            validation_requirement=True,
            related_change_record="GoreeCloud — Change Log — Tasks",
        )
        parent.labels.add(label)
        child = Task.objects.create(
            title="Validate upgrade",
            creator=self.owner,
            assignee=self.owner,
            project=project,
            parent=parent,
        )
        payload = self._payload(
            self.client.get(reverse("portability:project_export", args=[project.pk]))
        )
        tasks = {item["id"]: item for item in payload["data"]["tasks"]}
        self.assertEqual(tasks[parent.pk]["label_ids"], [label.pk])
        self.assertEqual(tasks[child.pk]["parent_id"], parent.pk)
        self.assertEqual(
            tasks[parent.pk]["assigned_system"],
            "Infrastructure Services VM",
        )
        self.assertTrue(tasks[parent.pk]["backup_prerequisite"])
        self.assertTrue(tasks[parent.pk]["validation_requirement"])
        self.assertEqual(
            tasks[parent.pk]["related_change_record"],
            "GoreeCloud — Change Log — Tasks",
        )

    def test_project_bulk_export_is_owner_only(self):
        project = Project.objects.create(
            owner=self.owner,
            name="Shared",
            visibility=Project.Visibility.SHARED,
        )
        ProjectMembership.objects.create(
            project=project,
            user=self.member,
            role=ProjectMembership.Role.MANAGER,
        )
        self.client.force_login(self.member)
        self.assertEqual(
            self.client.get(
                reverse("portability:project_export", args=[project.pk])
            ).status_code,
            404,
        )

    def test_export_user_references_do_not_include_email_or_authentication_fields(self):
        Task.objects.create(
            title="Portable",
            creator=self.owner,
            assignee=self.owner,
        )
        payload = self._payload(self.client.get(reverse("portability:user_export")))
        serialized = json.dumps(payload)
        self.assertNotIn("owner@example.invalid", serialized)
        self.assertNotIn("password", serialized.lower())
        self.assertNotIn("session", serialized.lower())
        self.assertEqual(
            payload["data"]["users"],
            [{"id": self.owner.pk, "username": "owner"}],
        )


class ImportBoundaryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="importer",
            password="test-password",
        )

    def test_source_neutral_bundle_can_represent_future_normalized_tasks(self):
        bundle = NormalizedImportBundle(
            source="fixture",
            tasks=(NormalizedTask(source_id="task-1", title="Imported task"),),
        )
        self.assertEqual(bundle.tasks[0].source_id, "task-1")
        self.assertEqual(bundle.tasks[0].title, "Imported task")

    def test_normalized_import_executes_as_private_user_owned_data(self):
        due_at = timezone.now()
        bundle = NormalizedImportBundle(
            source="fixture",
            projects=(NormalizedProject(source_id="project-1", name="Imported"),),
            labels=(
                NormalizedLabel(
                    source_id="label-1",
                    name="Migration",
                    project_source_id="project-1",
                ),
            ),
            tasks=(
                NormalizedTask(
                    source_id="task-1",
                    title="Parent task",
                    project_source_id="project-1",
                    label_source_ids=("label-1",),
                    priority=Task.Priority.P2_HIGH,
                    status=Task.Status.READY,
                    due_at=due_at,
                ),
                NormalizedTask(
                    source_id="task-2",
                    title="Child task",
                    project_source_id="project-1",
                    parent_source_id="task-1",
                ),
            ),
        )

        summary = execute_import(user=self.user, bundle=bundle)

        self.assertEqual(summary.projects_created, 1)
        self.assertEqual(summary.labels_created, 1)
        self.assertEqual(summary.tasks_created, 2)
        project = Project.objects.get(owner=self.user, name="Imported")
        self.assertEqual(project.visibility, Project.Visibility.PRIVATE)
        self.assertFalse(project.memberships.exists())
        parent = Task.objects.get(title="Parent task")
        child = Task.objects.get(title="Child task")
        self.assertEqual(parent.creator, self.user)
        self.assertEqual(parent.assignee, self.user)
        self.assertEqual(parent.project, project)
        self.assertEqual(parent.labels.get().name, "Migration")
        self.assertEqual(parent.priority, Task.Priority.P2_HIGH)
        self.assertEqual(parent.status, Task.Status.READY)
        self.assertEqual(parent.due_at, due_at)
        self.assertEqual(child.parent, parent)
        self.assertEqual(child.creator, self.user)
        self.assertEqual(child.assignee, self.user)

    def test_invalid_normalized_relationship_rolls_back_without_partial_writes(self):
        bundle = NormalizedImportBundle(
            source="fixture",
            projects=(NormalizedProject(source_id="project-1", name="Imported"),),
            tasks=(
                NormalizedTask(
                    source_id="task-1",
                    title="Broken",
                    project_source_id="project-1",
                    label_source_ids=("missing-label",),
                ),
            ),
        )
        with self.assertRaises(ImportExecutionError):
            execute_import(user=self.user, bundle=bundle)
        self.assertFalse(Project.objects.filter(owner=self.user).exists())
        self.assertFalse(Task.objects.filter(creator=self.user).exists())

    def test_normalized_import_refuses_existing_project_name_collision(self):
        Project.objects.create(owner=self.user, name="Imported")
        bundle = NormalizedImportBundle(
            source="fixture",
            projects=(NormalizedProject(source_id="project-1", name="Imported"),),
        )
        with self.assertRaises(ImportExecutionError):
            execute_import(user=self.user, bundle=bundle)
        self.assertEqual(Project.objects.filter(owner=self.user, name="Imported").count(), 1)

    def test_todoist_adapter_does_not_claim_unverified_format_support(self):
        with self.assertRaises(NotImplementedError):
            TodoistImportAdapter().normalize({"unverified": "payload"})


class UserArchiveRestoreTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="owner",
            email="owner@example.invalid",
            password="test-password",
        )
        self.member = User.objects.create_user(
            username="member",
            email="member@example.invalid",
            password="test-password",
        )

    def _build_full_archive(self):
        personal_label = Label.objects.create(name="Personal", owner=self.owner)
        personal_task = Task.objects.create(
            title="Private recovery task",
            creator=self.owner,
            assignee=self.owner,
            priority=Task.Priority.P1_URGENT,
        )
        personal_task.labels.add(personal_label)

        project = Project.objects.create(
            owner=self.owner,
            name="Recovered operations",
            visibility=Project.Visibility.SHARED,
        )
        membership = ProjectMembership.objects.create(
            project=project,
            user=self.member,
            role=ProjectMembership.Role.MANAGER,
        )
        project_label = Label.objects.create(
            name="Recovery",
            owner=self.member,
            project=project,
        )
        parent = Task.objects.create(
            title="Restore parent",
            creator=self.member,
            assignee=self.member,
            project=project,
            status=Task.Status.COMPLETED,
            is_goreecloud_work=True,
            assigned_system="Infrastructure Services VM",
            assigned_service="Tasks",
            environment="Development",
            workload_category="Recovery",
            blocker="None",
            resume_condition="Restore validation completes",
            backup_prerequisite=True,
            recovery_requirement=True,
            validation_requirement=True,
            documentation_requirement=True,
            related_change_record="GoreeCloud — Change Log — Tasks",
            related_documentation="GoreeCloud — Project Specification — Tasks",
        )
        parent.labels.add(project_label)
        child = Task.objects.create(
            title="Restore child",
            creator=self.owner,
            assignee=self.member,
            project=project,
            parent=parent,
        )
        comment = TaskComment.objects.create(
            task=parent,
            author=self.member,
            body="Historical collaboration survives restore.",
        )
        ActivityEvent.objects.create(
            actor=self.member,
            project=project,
            task=parent,
            kind=ActivityEvent.Kind.TASK_UPDATED,
            summary="Updated recovery task",
            details={"fields": ["status"]},
        )

        # Preserve a historical state that ordinary model creation cannot produce
        # directly: the collaborator created records while authorized and was later
        # reduced to an inactive Viewer when the project became private.
        ProjectMembership.objects.filter(pk=membership.pk).update(
            role=ProjectMembership.Role.VIEWER,
            is_active=False,
        )
        Project.objects.filter(pk=project.pk).update(
            visibility=Project.Visibility.PRIVATE
        )

        payload = build_user_archive(self.owner)
        original = {
            "project_created_at": project.created_at,
            "parent_created_at": parent.created_at,
            "comment_created_at": comment.created_at,
        }
        return payload, original

    def _wipe_application_data(self):
        ActivityEvent.objects.all().delete()
        TaskComment.objects.all().delete()
        Task.objects.all().delete()
        Label.objects.all().delete()
        ProjectMembership.objects.all().delete()
        Project.objects.all().delete()

    def test_user_archive_restores_private_and_shared_history_with_identity_remapping(self):
        payload, original = self._build_full_archive()
        self._wipe_application_data()

        summary = restore_user_archive(payload, user=self.owner)

        self.assertEqual(summary.projects_restored, 1)
        self.assertEqual(summary.memberships_restored, 1)
        self.assertEqual(summary.labels_restored, 2)
        self.assertEqual(summary.tasks_restored, 3)
        self.assertEqual(summary.comments_restored, 1)
        self.assertEqual(summary.activity_events_restored, 1)

        project = Project.objects.get(name="Recovered operations")
        self.assertEqual(project.owner, self.owner)
        self.assertEqual(project.visibility, Project.Visibility.PRIVATE)
        membership = project.memberships.get(user=self.member)
        self.assertEqual(membership.role, ProjectMembership.Role.VIEWER)
        self.assertFalse(membership.is_active)

        parent = Task.objects.get(title="Restore parent")
        child = Task.objects.get(title="Restore child")
        personal = Task.objects.get(title="Private recovery task")
        self.assertEqual(parent.creator, self.member)
        self.assertEqual(parent.assignee, self.member)
        self.assertEqual(child.parent, parent)
        self.assertEqual(personal.creator, self.owner)
        self.assertEqual(personal.assignee, self.owner)
        self.assertTrue(parent.is_goreecloud_work)
        self.assertEqual(parent.assigned_system, "Infrastructure Services VM")
        self.assertTrue(parent.backup_prerequisite)
        self.assertTrue(parent.recovery_requirement)
        self.assertTrue(parent.validation_requirement)
        self.assertTrue(parent.documentation_requirement)
        self.assertEqual(
            parent.related_change_record,
            "GoreeCloud — Change Log — Tasks",
        )
        self.assertEqual(
            parent.related_documentation,
            "GoreeCloud — Project Specification — Tasks",
        )
        self.assertEqual(parent.labels.get().owner, self.member)
        self.assertEqual(parent.comments.get().author, self.member)
        self.assertEqual(parent.comments.get().body, "Historical collaboration survives restore.")
        event = project.activity_events.get()
        self.assertEqual(event.actor, self.member)
        self.assertEqual(event.details, {"fields": ["status"]})

        project.refresh_from_db()
        parent.refresh_from_db()
        restored_comment = parent.comments.get()
        self.assertEqual(project.created_at, original["project_created_at"])
        self.assertEqual(parent.created_at, original["parent_created_at"])
        self.assertEqual(restored_comment.created_at, original["comment_created_at"])

    def test_restore_refuses_non_clean_target_without_overwriting(self):
        payload, _original = self._build_full_archive()
        project_count = Project.objects.filter(owner=self.owner).count()
        task_count = Task.objects.filter(creator=self.owner).count()
        with self.assertRaises(ArchiveRestoreError):
            restore_user_archive(payload, user=self.owner)
        self.assertEqual(Project.objects.filter(owner=self.owner).count(), project_count)
        self.assertEqual(Task.objects.filter(creator=self.owner).count(), task_count)

    def test_restore_refuses_archive_for_different_username(self):
        payload, _original = self._build_full_archive()
        self._wipe_application_data()
        other = get_user_model().objects.create_user(
            username="different-user",
            password="test-password",
        )
        with self.assertRaises(ArchiveRestoreError):
            restore_user_archive(payload, user=other)
        self.assertFalse(Project.objects.filter(owner=other).exists())

    def test_restore_refuses_missing_collaborator_account(self):
        payload, _original = self._build_full_archive()
        self._wipe_application_data()
        self.member.delete()
        with self.assertRaises(ArchiveRestoreError):
            restore_user_archive(payload, user=self.owner)
        self.assertFalse(Project.objects.filter(owner=self.owner).exists())
        self.assertFalse(Task.objects.filter(creator=self.owner).exists())

    def test_restore_web_workflow_requires_authentication_and_confirmation(self):
        payload, _original = self._build_full_archive()
        self._wipe_application_data()
        upload = SimpleUploadedFile(
            "goreecloud-tasks-owner.json",
            json.dumps(payload).encode("utf-8"),
            content_type="application/json",
        )

        response = self.client.post(
            reverse("portability:restore_user_archive"),
            {"archive": upload, "confirm_restore": "yes"},
        )
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.owner)
        upload = SimpleUploadedFile(
            "goreecloud-tasks-owner.json",
            json.dumps(payload).encode("utf-8"),
            content_type="application/json",
        )
        response = self.client.post(
            reverse("portability:restore_user_archive"),
            {"archive": upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm the recovery acknowledgement")
        self.assertFalse(Project.objects.filter(owner=self.owner).exists())

        upload = SimpleUploadedFile(
            "goreecloud-tasks-owner.json",
            json.dumps(payload).encode("utf-8"),
            content_type="application/json",
        )
        response = self.client.post(
            reverse("portability:restore_user_archive"),
            {"archive": upload, "confirm_restore": "yes"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Archive restored.")
        self.assertTrue(Project.objects.filter(owner=self.owner).exists())
        self.assertEqual(response["Cache-Control"], "private, no-store")
