"""Authenticated task workflows with explicit authorization boundaries."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from collaboration.forms import TaskCommentForm
from collaboration.models import ActivityEvent
from collaboration.services import record_activity

from .forms import QuickAddForm, TaskForm, editable_projects_for
from .models import Task


TERMINAL_STATUSES = [Task.Status.COMPLETED, Task.Status.CANCELLED]

TASK_ACTIVITY_FIELDS = (
    ("title", "title"),
    ("description", "description"),
    ("project_id", "project"),
    ("assignee_id", "assignee"),
    ("priority", "priority"),
    ("status", "status"),
    ("due_at", "due date"),
)


def _active_tasks(user):
    """Return active tasks visible through the normal application boundary."""
    return (
        Task.objects.visible_to(user)
        .exclude(status__in=TERMINAL_STATUSES)
        .select_related("project", "creator", "assignee")
    )


def _decorate_editability(user, queryset):
    """Materialize tasks and mark whether each may be changed by the user."""
    tasks = list(queryset)
    if not tasks:
        return tasks

    editable_ids = set(
        Task.objects.editable_by(user)
        .filter(pk__in=[task.pk for task in tasks])
        .values_list("pk", flat=True)
    )
    for task in tasks:
        task.user_can_edit = task.pk in editable_ids
    return tasks


def _list_context(request, *, tasks, active_view, heading, eyebrow):
    """Build shared context for Inbox, Today, and Upcoming."""
    decorated = _decorate_editability(request.user, tasks)
    return {
        "tasks": decorated,
        "task_count": len(decorated),
        "active_view": active_view,
        "heading": heading,
        "eyebrow": eyebrow,
        "quick_add_form": QuickAddForm(user=request.user),
    }


def _safe_redirect_back(request):
    """Return to an internal path supplied by the application, otherwise Inbox."""
    next_path = request.POST.get("next", "")
    if next_path.startswith("/") and not next_path.startswith("//"):
        return redirect(next_path)
    return redirect("tasks:dashboard")


def _task_snapshot(task):
    """Capture only fields used to decide whether an edit is material."""
    return {field_name: getattr(task, field_name) for field_name, _ in TASK_ACTIVITY_FIELDS}


def _changed_task_fields(before, task):
    """Return stable field keys and user-facing labels changed by an edit."""
    changed = []
    for field_name, label in TASK_ACTIVITY_FIELDS:
        if before[field_name] != getattr(task, field_name):
            changed.append((field_name, label))
    return changed


def _record_task_edit_activity(request, task, before):
    """Record one attributable event for a material full-editor change."""
    changed = _changed_task_fields(before, task)
    if not changed:
        return

    changed_keys = [field_name for field_name, _ in changed]
    changed_labels = [label for _, label in changed]

    if changed_keys == ["status"] and task.status == Task.Status.COMPLETED:
        kind = ActivityEvent.Kind.TASK_COMPLETED
        summary = "completed the task"
    elif (
        changed_keys == ["status"]
        and before["status"] == Task.Status.COMPLETED
        and task.status != Task.Status.COMPLETED
    ):
        kind = ActivityEvent.Kind.TASK_REOPENED
        summary = "reopened the task"
    else:
        kind = ActivityEvent.Kind.TASK_UPDATED
        if len(changed_labels) == 1:
            summary = f"updated the task {changed_labels[0]}"
        elif len(changed_labels) == 2:
            summary = f"updated {changed_labels[0]} and {changed_labels[1]}"
        else:
            summary = "updated " + ", ".join(changed_labels[:-1]) + f", and {changed_labels[-1]}"

    record_activity(
        actor=request.user,
        kind=kind,
        summary=summary,
        task=task,
        details={"fields": changed_keys},
    )


@login_required
def dashboard(request):
    """Render the user's private personal Inbox."""
    tasks = _active_tasks(request.user).filter(project__isnull=True)
    context = _list_context(
        request,
        tasks=tasks,
        active_view="inbox",
        heading="Inbox",
        eyebrow="Private personal workspace",
    )
    return render(request, "tasks/task_list.html", context)


@login_required
def today(request):
    """Render active accessible tasks due on the user's current local date."""
    local_today = timezone.localdate()
    tasks = _active_tasks(request.user).filter(due_at__date=local_today).order_by(
        "due_at", "priority", "id"
    )
    context = _list_context(
        request,
        tasks=tasks,
        active_view="today",
        heading="Today",
        eyebrow=date_format(local_today, "l, F j"),
    )
    return render(request, "tasks/task_list.html", context)


@login_required
def upcoming(request):
    """Render active accessible tasks due after the current local date."""
    local_today = timezone.localdate()
    tasks = _active_tasks(request.user).filter(due_at__date__gt=local_today).order_by(
        "due_at", "priority", "id"
    )
    context = _list_context(
        request,
        tasks=tasks,
        active_view="upcoming",
        heading="Upcoming",
        eyebrow="Scheduled work",
    )
    return render(request, "tasks/task_list.html", context)


@login_required
def task_detail(request, pk):
    """Show task content, comments, and material history to authorized readers."""
    task = get_object_or_404(
        Task.objects.visible_to(request.user).select_related(
            "project",
            "project__owner",
            "creator",
            "assignee",
        ),
        pk=pk,
    )
    can_edit = Task.objects.editable_by(request.user).filter(pk=task.pk).exists()

    return render(
        request,
        "tasks/task_detail.html",
        {
            "task": task,
            "comments": task.comments.select_related("author").all(),
            "activity_events": task.activity_events.select_related("actor").all()[:100],
            "comment_form": TaskCommentForm(),
            "user_can_edit": can_edit,
            "active_view": "",
        },
    )


@login_required
@require_POST
def quick_add(request):
    """Capture a task quickly into Inbox or an editable project."""
    form = QuickAddForm(request.POST, user=request.user)
    if not form.is_valid():
        messages.error(request, "The task could not be added. Check the entered values.")
        return _safe_redirect_back(request)

    task = form.save(commit=False)
    task.creator = request.user
    task.assignee = request.user
    task.status = Task.Status.READY
    task.save()

    record_activity(
        actor=request.user,
        kind=ActivityEvent.Kind.TASK_CREATED,
        summary="created the task",
        task=task,
        details={"source": "quick_add"},
    )
    messages.success(request, "Task added.")
    return _safe_redirect_back(request)


@login_required
def task_create(request):
    """Create a task using the full editor."""
    if request.method == "POST":
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.creator = request.user
            if task.assignee_id is None:
                task.assignee = request.user
            task.save()

            record_activity(
                actor=request.user,
                kind=ActivityEvent.Kind.TASK_CREATED,
                summary="created the task",
                task=task,
                details={"source": "full_editor"},
            )
            messages.success(request, "Task created.")
            return redirect("tasks:task_edit", pk=task.pk)
    else:
        initial = {"assignee": request.user}
        requested_project = request.GET.get("project")
        if requested_project:
            project = editable_projects_for(request.user).filter(pk=requested_project).first()
            if project is not None:
                initial["project"] = project
        form = TaskForm(user=request.user, initial=initial)

    return render(
        request,
        "tasks/task_form.html",
        {"form": form, "task": None, "active_view": ""},
    )


@login_required
def task_edit(request, pk):
    """Edit a task only when the normal application authorization permits it."""
    task = get_object_or_404(
        Task.objects.editable_by(request.user).select_related("project"),
        pk=pk,
    )

    if request.method == "POST":
        before = _task_snapshot(task)
        form = TaskForm(request.POST, instance=task, user=request.user)
        if form.is_valid():
            task = form.save()
            _record_task_edit_activity(request, task, before)
            messages.success(request, "Task updated.")
            return redirect("tasks:task_edit", pk=task.pk)
    else:
        form = TaskForm(instance=task, user=request.user)

    return render(
        request,
        "tasks/task_form.html",
        {"form": form, "task": task, "active_view": ""},
    )


@login_required
@require_POST
def task_toggle_complete(request, pk):
    """Complete or reopen an editable task and retain an attributable event."""
    task = get_object_or_404(
        Task.objects.editable_by(request.user).select_related("project"),
        pk=pk,
    )
    if task.status == Task.Status.COMPLETED:
        task.status = Task.Status.READY
        kind = ActivityEvent.Kind.TASK_REOPENED
        summary = "reopened the task"
        messages.success(request, "Task reopened.")
    else:
        task.status = Task.Status.COMPLETED
        kind = ActivityEvent.Kind.TASK_COMPLETED
        summary = "completed the task"
        messages.success(request, "Task completed.")

    task.save(update_fields=["status", "completed_at", "updated_at"])
    record_activity(
        actor=request.user,
        kind=kind,
        summary=summary,
        task=task,
    )
    return _safe_redirect_back(request)


@login_required
@require_POST
def task_delete(request, pk):
    """Delete an editable task after retaining material project history."""
    task = get_object_or_404(
        Task.objects.editable_by(request.user).select_related("project"),
        pk=pk,
    )
    task_id = task.pk
    task_title = task.title
    activity_title = task_title if len(task_title) <= 440 else task_title[:437] + "…"

    record_activity(
        actor=request.user,
        kind=ActivityEvent.Kind.TASK_DELETED,
        summary=f'deleted task “{activity_title}”',
        task=task,
        details={"deleted_task_id": task_id},
    )
    task.delete()
    messages.success(request, "Task deleted.")
    return redirect("tasks:dashboard")
