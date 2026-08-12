"""Authenticated user workflows for reminder preferences and private reminders."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from tasks.models import Task

from .forms import NotificationPreferenceForm, ReminderCreateForm, TaskReminderForm
from .models import TaskReminder
from .services import default_reminder_time, get_preferences, ntfy_is_configured


@login_required
def settings_view(request):
    """Manage one user's reminder defaults without exposing ntfy credentials."""
    preference = get_preferences(request.user)
    form = NotificationPreferenceForm(instance=preference, user=request.user)
    reminder_form = ReminderCreateForm(user=request.user)

    if request.method == "POST":
        action = request.POST.get("action", "preferences")
        if action == "create_reminder":
            reminder_form = ReminderCreateForm(request.POST, user=request.user)
            reminder_valid = reminder_form.is_valid()
            if not preference.reminders_enabled:
                reminder_form.add_error(
                    None,
                    "Task reminders are disabled in your notification preferences.",
                )
            elif reminder_valid:
                reminder_form.save()
                messages.success(request, "Private reminder scheduled.")
                return redirect("notifications:settings")
        else:
            form = NotificationPreferenceForm(
                request.POST,
                instance=preference,
                user=request.user,
            )
            if form.is_valid():
                form.save()
                messages.success(request, "Notification preferences updated.")
                return redirect("notifications:settings")
    else:
        requested_task = request.GET.get("task", "").strip()
        if requested_task:
            task = (
                Task.objects.visible_to(request.user)
                .exclude(status__in=[Task.Status.COMPLETED, Task.Status.CANCELLED])
                .filter(pk=requested_task)
                .first()
            )
            if task is not None:
                reminder_form = ReminderCreateForm(
                    user=request.user,
                    initial={
                        "task": task,
                        "remind_at": timezone.localtime(
                            default_reminder_time(user=request.user, task=task)
                        ),
                    },
                )

    visible_task_ids = Task.objects.visible_to(request.user).values_list("pk", flat=True)
    active_reminders = (
        TaskReminder.objects.filter(
            user=request.user,
            task_id__in=visible_task_ids,
            sent_at__isnull=True,
            cancelled_at__isnull=True,
        )
        .select_related("task", "task__project")
        .order_by("remind_at", "id")[:50]
    )

    response = render(
        request,
        "notifications/settings.html",
        {
            "form": form,
            "reminder_form": reminder_form,
            "preference": preference,
            "active_reminders": active_reminders,
            "ntfy_configured": ntfy_is_configured(),
            "active_view": "notifications",
        },
    )
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_POST
def reminder_add(request, task_pk):
    """Create a private reminder without requiring permission to edit the task."""
    task = get_object_or_404(
        Task.objects.visible_to(request.user).select_related("project"),
        pk=task_pk,
    )
    preference = get_preferences(request.user)
    if not preference.reminders_enabled:
        messages.error(
            request,
            "Task reminders are disabled in your notification preferences.",
        )
        return redirect("tasks:task_detail", pk=task.pk)

    form = TaskReminderForm(
        request.POST,
        user=request.user,
        task=task,
    )
    if not form.is_valid():
        messages.error(
            request,
            "The reminder could not be scheduled. Choose a valid future time.",
        )
        return redirect("tasks:task_detail", pk=task.pk)

    reminder = form.save(commit=False)
    reminder.user = request.user
    reminder.task = task
    reminder.save()
    messages.success(request, "Private reminder scheduled.")
    return redirect("tasks:task_detail", pk=task.pk)


@login_required
@require_POST
def reminder_cancel(request, pk):
    """Cancel only a reminder owned by the authenticated user."""
    reminder = get_object_or_404(TaskReminder, pk=pk, user=request.user)
    if reminder.sent_at is not None:
        messages.error(request, "A delivered reminder cannot be cancelled.")
    elif reminder.cancelled_at is not None:
        messages.info(request, "The reminder is already cancelled.")
    else:
        now = timezone.now()
        TaskReminder.objects.filter(pk=reminder.pk, user=request.user).update(
            cancelled_at=now,
            last_error="Reminder cancelled by the user.",
            updated_at=now,
        )
        messages.success(request, "Reminder cancelled.")

    next_path = request.POST.get("next", "")
    if next_path.startswith("/") and not next_path.startswith("//"):
        return redirect(next_path)
    return redirect("notifications:settings")
