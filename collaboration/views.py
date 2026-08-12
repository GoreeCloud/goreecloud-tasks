"""Authorized comment mutations."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from tasks.models import Task

from .forms import TaskCommentForm
from .models import ActivityEvent
from .services import record_activity


@login_required
@require_POST
def comment_add(request, task_pk):
    """Add a comment only when the user may edit the task."""
    task = get_object_or_404(
        Task.objects.editable_by(request.user).select_related("project"),
        pk=task_pk,
    )
    form = TaskCommentForm(request.POST)
    if not form.is_valid():
        messages.error(request, "The comment could not be posted.")
        return redirect("tasks:task_detail", pk=task.pk)

    comment = form.save(commit=False)
    comment.task = task
    comment.author = request.user
    comment.save()

    record_activity(
        actor=request.user,
        kind=ActivityEvent.Kind.COMMENT_ADDED,
        summary="added a comment",
        task=task,
        details={"comment_id": comment.pk},
    )
    messages.success(request, "Comment added.")
    return redirect("tasks:task_detail", pk=task.pk)
