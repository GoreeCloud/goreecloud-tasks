"""Reminder lifecycle hooks that keep closed tasks from producing future alerts."""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from tasks.models import Task

from .models import TaskReminder


@receiver(post_save, sender=Task)
def cancel_pending_reminders_for_closed_task(sender, instance, **kwargs):
    """Cancel unsent reminders when a task is completed or cancelled."""
    if instance.status not in {Task.Status.COMPLETED, Task.Status.CANCELLED}:
        return

    now = timezone.now()
    TaskReminder.objects.filter(
        task=instance,
        sent_at__isnull=True,
        cancelled_at__isnull=True,
    ).update(
        cancelled_at=now,
        last_error="Reminder cancelled because the task is closed.",
        updated_at=now,
    )
