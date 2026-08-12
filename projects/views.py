"""Project workflows with owner-controlled settings and explicit sharing."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from tasks.models import Task

from .forms import MembershipInviteForm, MembershipRoleForm, ProjectForm
from .models import Project, ProjectMembership


TERMINAL_TASK_STATUSES = [Task.Status.COMPLETED, Task.Status.CANCELLED]


def _visible_projects(user):
    """Return active projects visible through the normal application boundary."""
    if not user or not user.is_authenticated:
        return Project.objects.none()

    return (
        Project.objects.filter(is_archived=False)
        .filter(
            Q(owner=user)
            | Q(
                visibility=Project.Visibility.SHARED,
                memberships__user=user,
                memberships__is_active=True,
            )
        )
        .select_related("owner")
        .distinct()
    )


def _visible_project_or_404(user, pk):
    """Resolve a project without revealing unauthorized object existence."""
    project = get_object_or_404(Project.objects.select_related("owner"), pk=pk)
    if not project.can_view(user):
        # Deliberately return 404 instead of exposing whether the object exists.
        from django.http import Http404

        raise Http404
    return project


def _owned_project_or_404(user, pk):
    """Resolve a project only when the current user owns its settings boundary."""
    return get_object_or_404(Project.objects.select_related("owner"), pk=pk, owner=user)


@login_required
def project_list(request):
    """List projects the current user owns or may explicitly access."""
    projects = list(_visible_projects(request.user))
    for project in projects:
        if project.owner_id == request.user.id:
            project.user_role_label = "Owner"
        else:
            membership = project.active_membership_for(request.user)
            project.user_role_label = membership.get_role_display() if membership else "Member"

    return render(
        request,
        "projects/project_list.html",
        {
            "projects": projects,
            "active_view": "projects",
        },
    )


@login_required
def project_detail(request, pk):
    """Show accessible project work and membership context."""
    project = _visible_project_or_404(request.user, pk)
    tasks = list(
        Task.objects.visible_to(request.user)
        .filter(project=project)
        .exclude(status__in=TERMINAL_TASK_STATUSES)
        .select_related("creator", "assignee", "project")
    )
    can_edit_tasks = project.can_edit(request.user)
    for task in tasks:
        task.user_can_edit = can_edit_tasks

    memberships = list(
        project.memberships.filter(is_active=True)
        .select_related("user")
        .order_by("user__username")
    )

    return render(
        request,
        "projects/project_detail.html",
        {
            "project": project,
            "tasks": tasks,
            "task_count": len(tasks),
            "memberships": memberships,
            "membership_form": MembershipInviteForm(project=project),
            "active_view": "projects",
            "user_is_owner": project.owner_id == request.user.id,
            "user_can_edit_tasks": can_edit_tasks,
        },
    )


@login_required
def project_create(request):
    """Create a private-by-default project owned by the current user."""
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            messages.success(request, "Project created.")
            return redirect("projects:detail", pk=project.pk)
    else:
        form = ProjectForm(initial={"visibility": Project.Visibility.PRIVATE})

    return render(
        request,
        "projects/project_form.html",
        {
            "form": form,
            "project": None,
            "active_view": "projects",
        },
    )


@login_required
@transaction.atomic
def project_edit(request, pk):
    """Edit owner-controlled project settings."""
    project = _owned_project_or_404(request.user, pk)
    previous_visibility = project.visibility

    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            project = form.save()
            if (
                previous_visibility == Project.Visibility.SHARED
                and project.visibility == Project.Visibility.PRIVATE
            ):
                deactivated = project.memberships.filter(is_active=True).update(
                    is_active=False
                )
                if deactivated:
                    messages.info(
                        request,
                        "Project sharing was disabled and active memberships were revoked.",
                    )
            messages.success(request, "Project settings updated.")
            return redirect("projects:detail", pk=project.pk)
    else:
        form = ProjectForm(instance=project)

    return render(
        request,
        "projects/project_form.html",
        {
            "form": form,
            "project": project,
            "active_view": "projects",
        },
    )


@login_required
@require_POST
@transaction.atomic
def membership_add(request, pk):
    """Add or reactivate a member by exact username; project owner only."""
    project = _owned_project_or_404(request.user, pk)
    if project.visibility != Project.Visibility.SHARED:
        messages.error(request, "Make the project shared before adding members.")
        return redirect("projects:detail", pk=project.pk)

    form = MembershipInviteForm(request.POST, project=project)
    if not form.is_valid():
        tasks = list(
            Task.objects.visible_to(request.user)
            .filter(project=project)
            .exclude(status__in=TERMINAL_TASK_STATUSES)
            .select_related("creator", "assignee", "project")
        )
        for task in tasks:
            task.user_can_edit = True
        return render(
            request,
            "projects/project_detail.html",
            {
                "project": project,
                "tasks": tasks,
                "task_count": len(tasks),
                "memberships": list(
                    project.memberships.filter(is_active=True)
                    .select_related("user")
                    .order_by("user__username")
                ),
                "membership_form": form,
                "active_view": "projects",
                "user_is_owner": True,
                "user_can_edit_tasks": True,
            },
            status=400,
        )

    user = form.target_user
    role = form.cleaned_data["role"]
    membership, created = ProjectMembership.objects.get_or_create(
        project=project,
        user=user,
        defaults={"role": role, "is_active": True},
    )
    if not created:
        membership.role = role
        membership.is_active = True
        membership.save(update_fields=["role", "is_active"])

    messages.success(request, f"{user.preferred_name} was added to the project.")
    return redirect("projects:detail", pk=project.pk)


@login_required
@require_POST
def membership_role_update(request, pk, membership_pk):
    """Change an active member role; project owner only."""
    project = _owned_project_or_404(request.user, pk)
    membership = get_object_or_404(
        project.memberships.select_related("user"),
        pk=membership_pk,
        is_active=True,
    )
    form = MembershipRoleForm(request.POST, instance=membership)
    if form.is_valid():
        form.save()
        messages.success(
            request,
            f"{membership.user.preferred_name}'s role was updated.",
        )
    else:
        messages.error(request, "The member role could not be updated.")
    return redirect("projects:detail", pk=project.pk)


@login_required
@require_POST
def membership_remove(request, pk, membership_pk):
    """Revoke future project access without deleting membership history."""
    project = _owned_project_or_404(request.user, pk)
    membership = get_object_or_404(
        project.memberships.select_related("user"),
        pk=membership_pk,
        is_active=True,
    )
    membership.is_active = False
    membership.save(update_fields=["is_active"])
    messages.success(
        request,
        f"{membership.user.preferred_name} no longer has project access.",
    )
    return redirect("projects:detail", pk=project.pk)
