"""Regression coverage for Todoist CSV priority semantics."""

from django.test import SimpleTestCase

from imports.todoist import TodoistImportAdapter
from tasks.models import Task


class TodoistPrioritySemanticsTests(SimpleTestCase):
    def test_blank_priority_follows_current_todoist_csv_p1_semantics(self):
        bundle = TodoistImportAdapter().normalize_csv(
            "TYPE,CONTENT,DESCRIPTION,PRIORITY,INDENT\n"
            "task,Blank priority task,,,1\n",
            project_name="Priority semantics",
        )

        self.assertEqual(bundle.tasks[0].priority, Task.Priority.P1_URGENT)
