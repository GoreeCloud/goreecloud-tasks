"""Authorization-safe filtered task views for shared and GoreeCloud work."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from projects.models import Project

from .views import _active_tasks, _list_context


@login_required
def shared_work(request):
    """Render active tasks in shared projects already visible to the user."""
    tasks = (
        _active_tasks(request.user)
        .filter(project__visibility=Project.Visibility.SHARED)
        .order_by("due_at", "priority", "id")
    )
    context = _list_context(
        request,
        tasks=tasks,
        active_view="shared-work",
        heading="Shared Work",
        eyebrow="Projects shared with approved people",
        empty_heading="No shared work.",
        empty_copy="Tasks from shared projects you can access will appear here.",
    )
    return render(request, "tasks/task_list.html", context)


@login_required
def goreecloud_work(request):
    """Render active GoreeCloud operational tasks already visible to the user."""
    tasks = (
        _active_tasks(request.user)
        .filter(is_goreecloud_work=True)
        .order_by("due_at", "priority", "id")
    )
    context = _list_context(
        request,
        tasks=tasks,
        active_view="goreecloud-work",
        heading="GoreeCloud Work",
        eyebrow="Operational and infrastructure work",
        empty_heading="No active GoreeCloud work.",
        empty_copy="Accessible tasks marked as GoreeCloud work will appear here.",
    )
    return render(request, "tasks/task_list.html", context)
