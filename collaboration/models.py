"""Task comments and attributable material activity history."""

from django.conf import settings
from django.db import models


class TaskComment(models.Model):
    """A user-authored comment attached to a task."""

    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="task_comments",
    )
    body = models.TextField(max_length=10000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at", "id")

    def __str__(self):
        return f"Comment by {self.author} on {self.task}"


class ActivityEvent(models.Model):
    """Append-only application history for material user actions."""

    class Kind(models.TextChoices):
        TASK_CREATED = "task_created", "Task created"
        TASK_UPDATED = "task_updated", "Task updated"
        TASK_COMPLETED = "task_completed", "Task completed"
        TASK_REOPENED = "task_reopened", "Task reopened"
        TASK_DELETED = "task_deleted", "Task deleted"
        COMMENT_ADDED = "comment_added", "Comment added"
        PROJECT_CREATED = "project_created", "Project created"
        PROJECT_UPDATED = "project_updated", "Project updated"
        PROJECT_SHARING_REVOKED = (
            "project_sharing_revoked",
            "Project sharing revoked",
        )
        MEMBER_ADDED = "member_added", "Project member added"
        MEMBER_ROLE_CHANGED = "member_role_changed", "Project member role changed"
        MEMBER_REMOVED = "member_removed", "Project member removed"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="task_activity_events",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        related_name="activity_events",
        blank=True,
        null=True,
    )
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.SET_NULL,
        related_name="activity_events",
        blank=True,
        null=True,
    )
    kind = models.CharField(max_length=40, choices=Kind.choices)
    summary = models.CharField(max_length=500)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self):
        return f"{self.actor}: {self.summary}"
