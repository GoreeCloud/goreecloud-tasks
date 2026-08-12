"""Authenticated task workflows with explicit authorization boundaries."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from collaboration.forms import TaskCommentForm
from collaboration.models import ActivityEvent
from collaboration.services import record_activity

from .forms import QuickAddForm, SubtaskForm, TaskForm, editable_projects_for
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
    ("is_goreecloud_work", "GoreeCloud work classification"),
    ("assigned_system", "assigned system"),
    ("assigned_service", "assigned service"),
    ("environment", "environment"),
    ("workload_category", "workload category"),
    ("blocker", "blocker"),
    ("resume_condition", "resume condition"),
    ("backup_prerequisite", "backup prerequisite"),
    ("recovery_requirement", "recovery requirement"),
    ("validation_requirement", "validation requirement"),
    ("documentation_requirement", "documentation requirement"),
    ("related_change_record", "related change record"),
    ("related_documentation", "related documentation"),
)

OPERATIONAL_FIELDS = (
    "assigned_system",
    "assigned_service",
    "environment",
    "workload_category",
    "blocker",
    "resume_condition",
    "backup_prerequisite",
    "recovery_requirement",
    "validation_requirement",
    "documentation_requirement",
    "related_change_record",
    "related_documentation",
)


def _active_tasks(user):
    """Return active tasks visible through the normal application boundary."""
    return (
        Task.objects.visible_to(user)
        .exclude(status__in=TERMINAL_STATUSES)
        .select_related("project", "creator", "assignee", "parent")
        .prefetch_related("labels")
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


def _list_context(
    request,
    *,
    tasks,
    active_view,
    heading,
    eyebrow,
    search_query="",
    empty_heading="No tasks here.",
    empty_copy="Use Quick Add above to capture work without leaving this view.",
):
    """Build shared context for Inbox, date views, and search."""
    decorated = _decorate_editability(request.user, tasks)
    return {
        "tasks": decorated,
        "task_count": len(decorated),
        "active_view": active_view,
        "heading": heading,
        "eyebrow": eyebrow,
        "search_query": search_query,
        "empty_heading": empty_heading,
        "empty_copy": empty_copy,
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
    snapshot = {
        field_name: getattr(task, field_name)
        for field_name, _ in TASK_ACTIVITY_FIELDS
    }
    snapshot["labels"] = set(task.labels.values_list("pk", flat=True))
    return snapshot


def _changed_task_fields(before, task):
    """Return stable field keys and user-facing labels changed by an edit."""
    changed = []
    for field_name, label in TASK_ACTIVITY_FIELDS:
        if before[field_name] != getattr(task, field_name):
            changed.append((field_name, label))

    current_labels = set(task.labels.values_list("pk", flat=True))
    if before["labels"] != current_labels:
        changed.append(("labels", "labels"))
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
            summary = (
                "updated "
                + ", ".join(changed_labels[:-1])
                + f", and {changed_labels[-1]}"
            )

    record_activity(
        actor=request.user,
        kind=kind,
        summary=summary,
        task=task,
        details={"fields": changed_keys},
    )


def _has_operational_metadata(task):
    """Return whether the task should present the GoreeCloud operational panel."""
    return task.is_goreecloud_work or any(
        bool(getattr(task, field_name)) for field_name in OPERATIONAL_FIELDS
    )


def _operational_editor_open(form, task=None):
    """Keep the advanced editor collapsed unless it is relevant or has errors."""
    if task is not None and _has_operational_metadata(task):
        return True
    if form.is_bound:
        if form.data.get("is_goreecloud_work"):
            return True
        return any(form[field_name].errors for field_name in OPERATIONAL_FIELDS)
    return False


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
def search(request):
    """Search only tasks already visible to the authenticated user."""
    query = request.GET.get("q", "").strip()[:200]
    tasks = (
        Task.objects.visible_to(request.user)
        .select_related("project", "creator", "assignee", "parent")
        .prefetch_related("labels")
    )
    if query:
        tasks = tasks.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(project__name__icontains=query)
            | Q(labels__name__icontains=query)
            | Q(creator__username__icontains=query)
            | Q(assignee__username__icontains=query)
            | Q(assigned_system__icontains=query)
            | Q(assigned_service__icontains=query)
            | Q(environment__icontains=query)
            | Q(workload_category__icontains=query)
            | Q(blocker__icontains=query)
            | Q(resume_condition__icontains=query)
            | Q(related_change_record__icontains=query)
            | Q(related_documentation__icontains=query)
        ).distinct()
    else:
        tasks = tasks.none()

    context = _list_context(
        request,
        tasks=tasks,
        active_view="search",
        heading="Search",
        eyebrow=f'Results for “{query}”' if query else "Find accessible work",
        search_query=query,
        empty_heading="No matching tasks." if query else "Enter a search term.",
        empty_copy=(
            "Try a task title, description, project, label, system, service, blocker, or related record."
            if query
            else "Search only returns work your account is already authorized to read."
        ),
    )
    return render(request, "tasks/task_list.html", context)


@login_required
def task_detail(request, pk):
    """Show task content, subtasks, comments, labels, and material history."""
    task = get_object_or_404(
        Task.objects.visible_to(request.user)
        .select_related(
            "project",
            "project__owner",
            "creator",
            "assignee",
            "parent",
        )
        .prefetch_related("labels"),
        pk=pk,
    )
    can_edit = Task.objects.editable_by(request.user).filter(pk=task.pk).exists()
    subtasks = _decorate_editability(
        request.user,
        Task.objects.visible_to(request.user)
        .filter(parent=task)
        .select_related("project", "creator", "assignee", "parent")
        .prefetch_related("labels")
        .order_by("priority", "created_at", "id"),
    )

    return render(
        request,
        "tasks/task_detail.html",
        {
            "task": task,
            "subtasks": subtasks,
            "subtask_form": SubtaskForm(),
            "comments": task.comments.select_related("author").all(),
            "activity_events": task.activity_events.select_related("actor").all()[:100],
            "comment_form": TaskCommentForm(),
            "user_can_edit": can_edit,
            "has_operational_metadata": _has_operational_metadata(task),
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
            form.save_m2m()

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
        {
            "form": form,
            "task": None,
            "active_view": "",
            "operational_open": _operational_editor_open(form),
        },
    )


@login_required
def task_edit(request, pk):
    """Edit a task only when the normal application authorization permits it."""
    task = get_object_or_404(
        Task.objects.editable_by(request.user)
        .select_related("project")
        .prefetch_related("labels"),
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
        {
            "form": form,
            "task": task,
            "active_view": "",
            "operational_open": _operational_editor_open(form, task),
        },
    )


@login_required
@require_POST
def subtask_add(request, parent_pk):
    """Create a subtask only inside a parent task the user may edit."""
    parent = get_object_or_404(
        Task.objects.editable_by(request.user).select_related("project"),
        pk=parent_pk,
    )
    form = SubtaskForm(request.POST)
    if not form.is_valid():
        messages.error(request, "The subtask could not be added. Check the entered values.")
        return redirect("tasks:task_detail", pk=parent.pk)

    subtask = form.save(commit=False)
    subtask.parent = parent
    subtask.project = parent.project
    subtask.creator = request.user
    subtask.assignee = request.user
    subtask.status = Task.Status.READY
    subtask.save()

    record_activity(
        actor=request.user,
        kind=ActivityEvent.Kind.TASK_CREATED,
        summary="created the subtask",
        task=subtask,
        details={"source": "subtask", "parent_task_id": parent.pk},
    )
    messages.success(request, "Subtask added.")
    return redirect("tasks:task_detail", pk=parent.pk)


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
