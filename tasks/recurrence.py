"""Recurring-task completion helpers with authorization-preserving cloning."""

import calendar
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from collaboration.models import ActivityEvent
from collaboration.services import record_activity

from .models import Task
from .views import _safe_redirect_back


def _next_month(value):
    """Advance one calendar month while clamping to the target month's last day."""
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def next_due_at(task):
    """Return the next due time for a supported repeat rule."""
    if task.due_at is None or task.recurrence == Task.Recurrence.NONE:
        return None
    if task.recurrence == Task.Recurrence.DAILY:
        return task.due_at + timedelta(days=1)
    if task.recurrence == Task.Recurrence.WEEKLY:
        return task.due_at + timedelta(days=7)
    if task.recurrence == Task.Recurrence.MONTHLY:
        return _next_month(task.due_at)
    return None


def create_next_occurrence(task, *, actor):
    """Create the next task without carrying comments, reminders, or activity history."""
    due_at = next_due_at(task)
    if due_at is None:
        return None

    creator = task.creator
    assignee = task.assignee
    if task.project_id:
        if not task.project.can_edit(creator):
            creator = actor
        if assignee is not None and not task.project.can_receive_assigned_work(assignee):
            assignee = None

    next_task = Task(
        title=task.title,
        description=task.description,
        creator=creator,
        assignee=assignee,
        project=task.project,
        parent=task.parent,
        priority=task.priority,
        status=Task.Status.READY,
        due_at=due_at,
        recurrence=task.recurrence,
        is_goreecloud_work=task.is_goreecloud_work,
        assigned_system=task.assigned_system,
        assigned_service=task.assigned_service,
        environment=task.environment,
        workload_category=task.workload_category,
        blocker=task.blocker,
        resume_condition=task.resume_condition,
        backup_prerequisite=task.backup_prerequisite,
        recovery_requirement=task.recovery_requirement,
        validation_requirement=task.validation_requirement,
        documentation_requirement=task.documentation_requirement,
        related_change_record=task.related_change_record,
        related_documentation=task.related_documentation,
    )
    next_task.save()
    next_task.labels.set(task.labels.all())

    record_activity(
        actor=actor,
        kind=ActivityEvent.Kind.TASK_CREATED,
        summary="created the next recurring occurrence",
        task=next_task,
        details={"source": "recurrence", "previous_task_id": task.pk},
    )
    return next_task


@login_required
@require_POST
def task_toggle_complete(request, pk):
    """Complete/reopen a task and create the next occurrence when required."""
    task = get_object_or_404(
        Task.objects.editable_by(request.user)
        .select_related("project", "creator", "assignee", "parent")
        .prefetch_related("labels"),
        pk=pk,
    )

    if task.status == Task.Status.COMPLETED:
        task.status = Task.Status.READY
        task.save(update_fields=["status", "completed_at", "updated_at"])
        record_activity(
            actor=request.user,
            kind=ActivityEvent.Kind.TASK_REOPENED,
            summary="reopened the task",
            task=task,
        )
        messages.success(request, "Task reopened.")
        return _safe_redirect_back(request)

    task.status = Task.Status.COMPLETED
    task.save(update_fields=["status", "completed_at", "updated_at"])
    record_activity(
        actor=request.user,
        kind=ActivityEvent.Kind.TASK_COMPLETED,
        summary="completed the task",
        task=task,
    )

    next_task = create_next_occurrence(task, actor=request.user)
    if next_task is None:
        messages.success(request, "Task completed.")
    else:
        messages.success(
            request,
            f"Task completed. Next occurrence: {date_format(next_task.due_at, 'M j, Y g:i A')}.",
        )
    return _safe_redirect_back(request)
