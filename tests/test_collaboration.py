"""Launch-blocking tests for comments and attributable material activity."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from collaboration.models import ActivityEvent, TaskComment
from projects.models import Project, ProjectMembership
from tasks.models import Task


class CollaborationWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="owner",
            password="test-password",
            display_name="Project Owner",
        )
        self.member = User.objects.create_user(
            username="member",
            password="test-password",
            display_name="Project Member",
        )
        self.viewer = User.objects.create_user(
            username="viewer",
            password="test-password",
            display_name="Project Viewer",
        )
        self.outsider = User.objects.create_user(
            username="outsider",
            password="test-password",
            display_name="Outsider",
        )

        self.project = Project.objects.create(
            owner=self.owner,
            name="Shared project",
            visibility=Project.Visibility.SHARED,
        )
        self.member_membership = ProjectMembership.objects.create(
            project=self.project,
            user=self.member,
            role=ProjectMembership.Role.MEMBER,
        )
        self.viewer_membership = ProjectMembership.objects.create(
            project=self.project,
            user=self.viewer,
            role=ProjectMembership.Role.VIEWER,
        )
        self.task = Task.objects.create(
            title="Collaborative task",
            creator=self.owner,
            assignee=self.member,
            project=self.project,
            status=Task.Status.READY,
        )

    def test_member_can_add_comment_and_comment_activity_is_attributed(self):
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("tasks:task_comment_add", args=[self.task.pk]),
            {"body": "I finished the first verification step."},
        )

        self.assertRedirects(
            response,
            reverse("tasks:task_detail", args=[self.task.pk]),
        )
        comment = TaskComment.objects.get(task=self.task)
        self.assertEqual(comment.author, self.member)
        self.assertEqual(comment.body, "I finished the first verification step.")

        event = ActivityEvent.objects.get(
            task=self.task,
            kind=ActivityEvent.Kind.COMMENT_ADDED,
        )
        self.assertEqual(event.actor, self.member)
        self.assertEqual(event.project, self.project)
        self.assertEqual(event.details["comment_id"], comment.pk)

    def test_viewer_can_read_comments_but_cannot_post(self):
        TaskComment.objects.create(
            task=self.task,
            author=self.owner,
            body="Visible shared discussion.",
        )

        self.client.force_login(self.viewer)
        detail = self.client.get(reverse("tasks:task_detail", args=[self.task.pk]))
        self.assertContains(detail, "Visible shared discussion.")
        self.assertContains(detail, "Read only")

        response = self.client.post(
            reverse("tasks:task_comment_add", args=[self.task.pk]),
            {"body": "Viewer should not be able to write."},
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(TaskComment.objects.filter(task=self.task).count(), 1)

    def test_outsider_cannot_read_task_comments_or_activity(self):
        TaskComment.objects.create(
            task=self.task,
            author=self.owner,
            body="Project-only information.",
        )
        ActivityEvent.objects.create(
            actor=self.owner,
            project=self.project,
            task=self.task,
            kind=ActivityEvent.Kind.TASK_UPDATED,
            summary="updated the task status",
        )

        self.client.force_login(self.outsider)
        response = self.client.get(reverse("tasks:task_detail", args=[self.task.pk]))
        self.assertEqual(response.status_code, 404)

    def test_private_task_comments_remain_private(self):
        private_task = Task.objects.create(
            title="Private task",
            creator=self.owner,
            assignee=self.owner,
            status=Task.Status.READY,
        )
        TaskComment.objects.create(
            task=private_task,
            author=self.owner,
            body="Private note.",
        )

        self.client.force_login(self.member)
        response = self.client.get(
            reverse("tasks:task_detail", args=[private_task.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_comment_content_is_escaped_in_task_detail(self):
        self.client.force_login(self.member)
        self.client.post(
            reverse("tasks:task_comment_add", args=[self.task.pk]),
            {"body": "<script>alert('x')</script>"},
        )

        response = self.client.get(reverse("tasks:task_detail", args=[self.task.pk]))
        self.assertContains(
            response,
            "&lt;script&gt;alert(&#x27;x&#x27;)&lt;/script&gt;",
            html=False,
        )
        self.assertNotContains(response, "<script>alert('x')</script>")

    def test_full_task_creation_records_actor_and_source(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("tasks:task_create"),
            {
                "title": "New tracked task",
                "description": "",
                "project": self.project.pk,
                "assignee": self.owner.pk,
                "priority": Task.Priority.P2_HIGH,
                "status": Task.Status.READY,
                "due_at": "",
            },
        )

        task = Task.objects.get(title="New tracked task")
        self.assertRedirects(response, reverse("tasks:task_edit", args=[task.pk]))
        event = ActivityEvent.objects.get(
            task=task,
            kind=ActivityEvent.Kind.TASK_CREATED,
        )
        self.assertEqual(event.actor, self.owner)
        self.assertEqual(event.project, self.project)
        self.assertEqual(event.details["source"], "full_editor")

    def test_task_edit_records_changed_field_names_without_copying_description(self):
        self.client.force_login(self.owner)
        sensitive_description = "Material detail that belongs only on the task."
        self.client.post(
            reverse("tasks:task_edit", args=[self.task.pk]),
            {
                "title": self.task.title,
                "description": sensitive_description,
                "project": self.project.pk,
                "assignee": self.member.pk,
                "priority": self.task.priority,
                "status": self.task.status,
                "due_at": "",
            },
        )

        event = ActivityEvent.objects.get(
            task=self.task,
            kind=ActivityEvent.Kind.TASK_UPDATED,
        )
        self.assertEqual(event.actor, self.owner)
        self.assertEqual(event.details["fields"], ["description"])
        self.assertNotIn(sensitive_description, event.summary)
        self.assertNotIn(sensitive_description, str(event.details))

    def test_completion_and_reopen_record_distinct_events(self):
        self.client.force_login(self.member)

        self.client.post(
            reverse("tasks:task_toggle_complete", args=[self.task.pk]),
            {"next": reverse("tasks:task_detail", args=[self.task.pk])},
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.COMPLETED)
        completed = ActivityEvent.objects.get(
            task=self.task,
            kind=ActivityEvent.Kind.TASK_COMPLETED,
        )
        self.assertEqual(completed.actor, self.member)

        self.client.post(
            reverse("tasks:task_toggle_complete", args=[self.task.pk]),
            {"next": reverse("tasks:task_detail", args=[self.task.pk])},
        )
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, Task.Status.READY)
        reopened = ActivityEvent.objects.get(
            task=self.task,
            kind=ActivityEvent.Kind.TASK_REOPENED,
        )
        self.assertEqual(reopened.actor, self.member)

    def test_membership_changes_are_recorded_in_project_activity(self):
        self.client.force_login(self.owner)

        self.client.post(
            reverse("projects:membership_add", args=[self.project.pk]),
            {
                "username": self.outsider.username,
                "role": ProjectMembership.Role.MEMBER,
            },
        )
        membership = ProjectMembership.objects.get(
            project=self.project,
            user=self.outsider,
        )
        added = ActivityEvent.objects.get(
            project=self.project,
            kind=ActivityEvent.Kind.MEMBER_ADDED,
        )
        self.assertEqual(added.actor, self.owner)
        self.assertEqual(added.details["subject_user_id"], self.outsider.pk)

        self.client.post(
            reverse(
                "projects:membership_role_update",
                args=[self.project.pk, membership.pk],
            ),
            {"role": ProjectMembership.Role.VIEWER},
        )
        changed = ActivityEvent.objects.get(
            project=self.project,
            kind=ActivityEvent.Kind.MEMBER_ROLE_CHANGED,
        )
        self.assertEqual(changed.details["subject_user_id"], self.outsider.pk)
        self.assertEqual(changed.details["from_role"], ProjectMembership.Role.MEMBER)
        self.assertEqual(changed.details["to_role"], ProjectMembership.Role.VIEWER)

        self.client.post(
            reverse(
                "projects:membership_remove",
                args=[self.project.pk, membership.pk],
            )
        )
        removed = ActivityEvent.objects.get(
            project=self.project,
            kind=ActivityEvent.Kind.MEMBER_REMOVED,
        )
        self.assertEqual(removed.actor, self.owner)
        self.assertEqual(removed.details["subject_user_id"], self.outsider.pk)

    def test_viewer_can_read_project_activity(self):
        ActivityEvent.objects.create(
            actor=self.owner,
            project=self.project,
            kind=ActivityEvent.Kind.PROJECT_UPDATED,
            summary="updated the project name",
        )

        self.client.force_login(self.viewer)
        response = self.client.get(
            reverse("projects:detail", args=[self.project.pk])
        )
        self.assertContains(response, "Project activity")
        self.assertContains(response, "updated the project name")
        self.assertContains(response, "Project Owner")

    def test_removed_member_loses_comment_and_activity_visibility(self):
        TaskComment.objects.create(
            task=self.task,
            author=self.member,
            body="Historical member comment.",
        )
        ActivityEvent.objects.create(
            actor=self.member,
            project=self.project,
            task=self.task,
            kind=ActivityEvent.Kind.COMMENT_ADDED,
            summary="added a comment",
        )

        self.member_membership.is_active = False
        self.member_membership.save(update_fields=["is_active"])

        self.client.force_login(self.member)
        response = self.client.get(reverse("tasks:task_detail", args=[self.task.pk]))
        self.assertEqual(response.status_code, 404)

    def test_making_project_private_records_revocation_event(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("projects:edit", args=[self.project.pk]),
            {
                "name": self.project.name,
                "visibility": Project.Visibility.PRIVATE,
            },
        )

        self.assertRedirects(
            response,
            reverse("projects:detail", args=[self.project.pk]),
        )
        event = ActivityEvent.objects.get(
            project=self.project,
            kind=ActivityEvent.Kind.PROJECT_SHARING_REVOKED,
        )
        self.assertEqual(event.actor, self.owner)
        self.assertEqual(event.details["revoked_memberships"], 2)
        self.member_membership.refresh_from_db()
        self.viewer_membership.refresh_from_db()
        self.assertFalse(self.member_membership.is_active)
        self.assertFalse(self.viewer_membership.is_active)
