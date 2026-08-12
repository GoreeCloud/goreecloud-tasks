"""Initial authenticated task views."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .models import Task


@login_required
def dashboard(request):
    """Render the user's initial private Inbox and accessible active work."""
    active_tasks = (
        Task.objects.visible_to(request.user)
        .exclude(status__in=[Task.Status.COMPLETED, Task.Status.CANCELLED])
        .select_related("project", "creator", "assignee")
    )
    personal_inbox = active_tasks.filter(project__isnull=True)

    return render(
        request,
        "tasks/dashboard.html",
        {
            "active_tasks": active_tasks,
            "personal_inbox": personal_inbox,
        },
    )
