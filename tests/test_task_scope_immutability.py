"""Regression tests for immutable task authorization scope after creation."""

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from projects.models import Project
from tasks.forms import TaskForm
from tasks.models import Task


class TaskScopeImmutabilityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(username="owner", password="test-password")
        self.project_a = Project.objects.create(
            owner=self.owner,
            name="Project A",
            visibility=Project.Visibility.PRIVATE,
        )
        self.project_b = Project.objects.create(
            owner=self.owner,
            name="Project B",
            visibility=Project.Visibility.PRIVATE,
        )
        self.project_task = Task.objects.create(
            title="Project-scoped task",
            creator=self.owner,
            assignee=self.owner,
            project=self.project_a,
            status=Task.Status.READY,
        )
        self.private_task = Task.objects.create(
            title="Private task",
            creator=self.owner,
            assignee=self.owner,
            status=Task.Status.READY,
        )

    def test_model_rejects_project_to_project_move(self):
        self.project_task.project = self.project_b

        with self.assertRaises(ValidationError):
            self.project_task.save()

        self.project_task.refresh_from_db()
        self.assertEqual(self.project_task.project, self.project_a)

    def test_model_rejects_project_to_private_move(self):
        self.project_task.project = None

        with self.assertRaises(ValidationError):
            self.project_task.save()

        self.project_task.refresh_from_db()
        self.assertEqual(self.project_task.project, self.project_a)

    def test_model_rejects_private_to_project_move(self):
        self.private_task.project = self.project_a

        with self.assertRaises(ValidationError):
            self.private_task.save()

        self.private_task.refresh_from_db()
        self.assertIsNone(self.private_task.project)

    def test_model_allows_non_scope_edits(self):
        self.project_task.title = "Updated in original project"
        self.project_task.status = Task.Status.IN_PROGRESS
        self.project_task.save()
        self.project_task.refresh_from_db()

        self.assertEqual(self.project_task.project, self.project_a)
        self.assertEqual(self.project_task.title, "Updated in original project")
        self.assertEqual(self.project_task.status, Task.Status.IN_PROGRESS)

    def test_edit_form_disables_project_scope(self):
        form = TaskForm(instance=self.project_task, user=self.owner)
        project_field = form.fields["project"]

        self.assertTrue(project_field.disabled)
        self.assertEqual(list(project_field.queryset), [self.project_a])
        self.assertIn("fixed after creation", project_field.help_text)

    def test_private_edit_form_keeps_inbox_scope_disabled(self):
        form = TaskForm(instance=self.private_task, user=self.owner)
        project_field = form.fields["project"]

        self.assertTrue(project_field.disabled)
        self.assertFalse(project_field.queryset.exists())

    def test_crafted_edit_post_cannot_move_task_to_other_project(self):
        form = TaskForm(
            data={
                "title": self.project_task.title,
                "description": "",
                "project": self.project_b.pk,
                "assignee": self.owner.pk,
                "priority": Task.Priority.P3_STANDARD,
                "status": Task.Status.READY,
                "due_at": "",
            },
            instance=self.project_task,
            user=self.owner,
        )

        self.assertTrue(form.is_valid(), form.errors)
        task = form.save()
        self.assertEqual(task.project, self.project_a)

    def test_crafted_edit_post_cannot_move_private_task_into_project(self):
        form = TaskForm(
            data={
                "title": self.private_task.title,
                "description": "",
                "project": self.project_a.pk,
                "assignee": self.owner.pk,
                "priority": Task.Priority.P3_STANDARD,
                "status": Task.Status.READY,
                "due_at": "",
            },
            instance=self.private_task,
            user=self.owner,
        )

        self.assertTrue(form.is_valid(), form.errors)
        task = form.save()
        self.assertIsNone(task.project)

    def test_new_task_form_still_allows_authorized_scope_selection(self):
        form = TaskForm(user=self.owner, initial={"project": self.project_b})

        self.assertFalse(form.fields["project"].disabled)
        self.assertIn(self.project_a, form.fields["project"].queryset)
        self.assertIn(self.project_b, form.fields["project"].queryset)
