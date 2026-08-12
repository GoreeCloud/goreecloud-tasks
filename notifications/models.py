"""User-specific reminder state and notification-delivery preferences."""

import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


def default_ntfy_topic():
    """Create a non-identifying topic name inside the approved Tasks namespace."""
    prefix = getattr(settings, "NTFY_TOPIC_PREFIX", "goreecloud-tasks").strip()
    return f"{prefix}-{secrets.token_hex(8)}"


class NotificationPreference(models.Model):
    """One user's reminder defaults and ntfy delivery destination.

    The topic is application-generated and deliberately does not contain a username,
    email address, or other personal identifier. Topic access remains controlled by
    ntfy authentication and ACLs; the topic string itself is not treated as a token.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    reminders_enabled = models.BooleanField(default=True)
    default_lead_minutes = models.PositiveIntegerField(
        default=30,
        validators=[MaxValueValidator(10080)],
        help_text="Default minutes before a task due time for a new reminder.",
    )
    ntfy_enabled = models.BooleanField(default=False)
    ntfy_topic = models.CharField(
        max_length=64,
        unique=True,
        default=default_ntfy_topic,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Notification preferences for {self.user.username}"


class TaskReminderQuerySet(models.QuerySet):
    """Query helpers for pending reminder delivery."""

    def pending(self):
        return self.filter(sent_at__isnull=True, cancelled_at__isnull=True)

    def due(self, at=None):
        at = at or timezone.now()
        return self.pending().filter(remind_at__lte=at)


class TaskReminder(models.Model):
    """A private reminder owned by one user for one task they may read."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="task_reminders",
    )
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.CASCADE,
        related_name="reminders",
    )
    remind_at = models.DateTimeField(db_index=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    last_attempt_at = models.DateTimeField(blank=True, null=True)
    attempt_count = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TaskReminderQuerySet.as_manager()

    class Meta:
        ordering = ("remind_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "task", "remind_at"),
                condition=Q(cancelled_at__isnull=True),
                name="uniq_active_task_reminder",
            )
        ]
        indexes = [
            models.Index(
                fields=("remind_at", "sent_at", "cancelled_at"),
                name="notification_due_idx",
            )
        ]

    def __str__(self):
        return f"Reminder for {self.user.username}: {self.task.title}"

    @property
    def delivery_state(self):
        if self.cancelled_at:
            return "Cancelled"
        if self.sent_at:
            return "Sent"
        if self.remind_at <= timezone.now():
            return "Due"
        return "Scheduled"

    def clean(self):
        """Keep reminder ownership inside the task authorization boundary."""
        super().clean()
        if self.sent_at and self.cancelled_at:
            raise ValidationError(
                "A reminder cannot be both delivered and cancelled."
            )

        if not self.user_id or not self.task_id:
            return

        from tasks.models import Task

        if not Task.objects.visible_to(self.user).filter(pk=self.task_id).exists():
            raise ValidationError(
                {"task": "You may create reminders only for tasks you can read."}
            )

        if self.task.status in {Task.Status.COMPLETED, Task.Status.CANCELLED}:
            if self.pk is None and self.cancelled_at is None:
                raise ValidationError(
                    {"task": "A new reminder cannot be created for a closed task."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
