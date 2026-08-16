"""Overdue task workflow built on the normal Tasks authorization boundary."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from .views import _active_tasks, _list_context


@login_required
def overdue(request):
    """Render unfinished accessible tasks whose due date has already passed."""
    local_today = timezone.localdate()
    tasks = (
        _active_tasks(request.user)
        .filter(due_at__date__lt=local_today)
        .order_by("due_at", "priority", "id")
    )
    context = _list_context(
        request,
        tasks=tasks,
        active_view="overdue",
        heading="Overdue",
        eyebrow="Needs attention",
        empty_heading="Nothing overdue.",
        empty_copy="Tasks that pass their due date without being completed will appear here.",
    )
    return render(request, "tasks/task_list.html", context)
