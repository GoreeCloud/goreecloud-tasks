"""Regression tests for the verified Todoist project CSV migration path."""

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from collaboration.models import TaskComment
from imports.executor import execute_import
from imports.todoist import TodoistCsvError, TodoistImportAdapter
from labels.models import Label
from projects.models import Project
from tasks.models import Task


OFFICIAL_STYLE_CSV = """TYPE,CONTENT,DESCRIPTION,PRIORITY,INDENT,AUTHOR,RESPONSIBLE,DATE,DATE_LANG,TIMEZONE,DURATION,DURATION_UNIT,meta,DEADLINE,DEADLINE_LANG,IS_COLLAPSED
section,Home,Household work,,,,,,,,,,,,,FALSE
task,Buy milk @errands,Get two cartons,1,1,Alice (100),Bob (200),tomorrow at 5pm,en,US/Central,30,minute,,Friday,en,
note,Remember organic if available,,,,,,,,,,,,,,
task,Check refrigerator,Before shopping,4,2,Alice (100),,2026-08-13T18:30:00-05:00,en,US/Central,,,,,,
"""


class TodoistCsvAdapterTests(TestCase):
    def test_verified_columns_normalize_tasks_labels_comments_and_indent(self):
        bundle = TodoistImportAdapter().normalize_csv(
            OFFICIAL_STYLE_CSV,
            project_name="Imported Todoist Home",
        )

        self.assertEqual(bundle.source, "todoist_csv")
        self.assertEqual(bundle.projects[0].name, "Imported Todoist Home")
        self.assertEqual(len(bundle.tasks), 2)
        self.assertEqual(len(bundle.labels), 1)
        self.assertEqual(len(bundle.comments), 1)

        parent, child = bundle.tasks
        self.assertEqual(parent.title, "Buy milk")
        self.assertEqual(parent.priority, Task.Priority.P1_URGENT)
        self.assertEqual(parent.label_source_ids, (bundle.labels[0].source_id,))
        self.assertIn("Todoist section: Home", parent.description)
        self.assertIn("Todoist date: tomorrow at 5pm", parent.description)
        self.assertIn("Todoist responsible: Bob (200)", parent.description)
        self.assertIn("Todoist deadline: Friday", parent.description)
        self.assertIsNone(parent.due_at)

        self.assertEqual(child.parent_source_id, parent.source_id)
        self.assertEqual(child.priority, Task.Priority.P4_LOW)
        self.assertIsNotNone(child.due_at)
        self.assertEqual(child.due_at.isoformat(), "2026-08-13T18:30:00-05:00")
        self.assertEqual(bundle.comments[0].task_source_id, parent.source_id)
        self.assertEqual(bundle.comments[0].body, "Remember organic if available")

    def test_semicolon_delimited_csv_is_detected(self):
        text = (
            "TYPE;CONTENT;DESCRIPTION;PRIORITY;INDENT\n"
            "task;Semicolon task;Imported;3;1\n"
        )
        bundle = TodoistImportAdapter().normalize_csv(text, project_name="Semicolon")
        self.assertEqual(bundle.tasks[0].title, "Semicolon task")
        self.assertEqual(bundle.tasks[0].priority, Task.Priority.P3_STANDARD)

    def test_unknown_columns_are_preserved_as_import_metadata(self):
        text = (
            "TYPE,CONTENT,DESCRIPTION,PRIORITY,INDENT,FUTURE_FIELD\n"
            "task,Portable task,Original,3,1,provider-value\n"
        )
        task = TodoistImportAdapter().normalize_csv(
            text,
            project_name="Future fields",
        ).tasks[0]
        self.assertIn("Todoist FUTURE_FIELD: provider-value", task.description)

    def test_invalid_indent_is_rejected_before_execution(self):
        text = (
            "TYPE,CONTENT,DESCRIPTION,PRIORITY,INDENT\n"
            "task,Orphan child,,3,2\n"
        )
        with self.assertRaises(TodoistCsvError):
            TodoistImportAdapter().normalize_csv(text, project_name="Broken")

    def test_missing_required_headers_are_rejected(self):
        with self.assertRaises(TodoistCsvError):
            TodoistImportAdapter().normalize_csv(
                "TYPE,DESCRIPTION\ntask,Missing content header\n",
                project_name="Broken",
            )


class TodoistCsvExecutionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="todoist-importer",
            password="test-password",
        )

    def test_normalized_todoist_project_executes_as_private_user_owned_data(self):
        bundle = TodoistImportAdapter().normalize_csv(
            OFFICIAL_STYLE_CSV,
            project_name="Migrated Home",
        )
        summary = execute_import(user=self.user, bundle=bundle)

        self.assertEqual(summary.projects_created, 1)
        self.assertEqual(summary.tasks_created, 2)
        self.assertEqual(summary.labels_created, 1)
        self.assertEqual(summary.comments_created, 1)

        project = Project.objects.get(owner=self.user, name="Migrated Home")
        self.assertEqual(project.visibility, Project.Visibility.PRIVATE)
        self.assertFalse(project.memberships.exists())
        parent = Task.objects.get(project=project, title="Buy milk")
        child = Task.objects.get(project=project, title="Check refrigerator")
        self.assertEqual(parent.creator, self.user)
        self.assertEqual(parent.assignee, self.user)
        self.assertEqual(child.parent, parent)
        self.assertEqual(Label.objects.get(project=project).name, "errands")
        self.assertEqual(TaskComment.objects.get(task=parent).author, self.user)

    def test_web_import_requires_login_and_creates_private_project(self):
        upload = SimpleUploadedFile(
            "Home.csv",
            OFFICIAL_STYLE_CSV.encode("utf-8"),
            content_type="text/csv",
        )
        response = self.client.post(
            reverse("portability:import_todoist_csv"),
            {"project_name": "Web Todoist", "todoist_csv": upload},
        )
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.user)
        upload = SimpleUploadedFile(
            "Home.csv",
            OFFICIAL_STYLE_CSV.encode("utf-8"),
            content_type="text/csv",
        )
        response = self.client.post(
            reverse("portability:import_todoist_csv"),
            {"project_name": "Web Todoist", "todoist_csv": upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Todoist project imported.")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        project = Project.objects.get(owner=self.user, name="Web Todoist")
        self.assertEqual(project.visibility, Project.Visibility.PRIVATE)

    def test_web_import_refuses_existing_project_collision(self):
        Project.objects.create(owner=self.user, name="Existing")
        self.client.force_login(self.user)
        upload = SimpleUploadedFile(
            "Home.csv",
            OFFICIAL_STYLE_CSV.encode("utf-8"),
            content_type="text/csv",
        )
        response = self.client.post(
            reverse("portability:import_todoist_csv"),
            {"project_name": "Existing", "todoist_csv": upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Todoist import blocked.")
        self.assertEqual(Project.objects.filter(owner=self.user, name="Existing").count(), 1)
