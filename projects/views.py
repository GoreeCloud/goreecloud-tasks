"""Project workflows with owner-controlled settings and explicit sharing."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from collaboration.models import ActivityEvent
from collaboration.services import record_activity
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
        raise Http404
    return project


def _owned_project_or_404(user, pk):
    """Resolve a project only when the current user owns its settings boundary."""
    return get_object_or_404(Project.objects.select_related("owner"), pk=pk, owner=user)


def _project_detail_context(request, project, membership_form=None):
    """Build project detail context through the current user's authorization boundary."""
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

    return {
        "project": project,
        "tasks": tasks,
        "task_count": len(tasks),
        "memberships": memberships,
        "membership_form": membership_form or MembershipInviteForm(project=project),
        "role_choices": ProjectMembership.Role.choices,
        "activity_events": project.activity_events.select_related("actor").all()[:100],
        "active_view": "projects",
        "user_is_owner": project.owner_id == request.user.id,
        "user_can_edit_tasks": can_edit_tasks,
    }


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
    """Show accessible project work, membership, and material history."""
    project = _visible_project_or_404(request.user, pk)
    return render(
        request,
        "projects/project_detail.html",
        _project_detail_context(request, project),
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
            record_activity(
                actor=request.user,
                kind=ActivityEvent.Kind.PROJECT_CREATED,
                summary="created the project",
                project=project,
            )
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
    """Edit owner-controlled project settings and record material changes."""
    project = _owned_project_or_404(request.user, pk)
    previous_name = project.name
    previous_visibility = project.visibility

    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            project = form.save()

            changed_fields = []
            if previous_name != project.name:
                changed_fields.append("name")
            if previous_visibility != project.visibility:
                changed_fields.append("visibility")

            if changed_fields:
                if len(changed_fields) == 1:
                    summary = f"updated the project {changed_fields[0]}"
                else:
                    summary = "updated the project name and visibility"
                record_activity(
                    actor=request.user,
                    kind=ActivityEvent.Kind.PROJECT_UPDATED,
                    summary=summary,
                    project=project,
                    details={"fields": changed_fields},
                )

            if (
                previous_visibility == Project.Visibility.SHARED
                and project.visibility == Project.Visibility.PRIVATE
            ):
                deactivated = project.memberships.filter(is_active=True).update(
                    is_active=False
                )
                if deactivated:
                    record_activity(
                        actor=request.user,
                        kind=ActivityEvent.Kind.PROJECT_SHARING_REVOKED,
                        summary=(
                            f"made the project private and revoked "
                            f"{deactivated} active membership"
                            f"{'' if deactivated == 1 else 's'}"
                        ),
                        project=project,
                        details={"revoked_memberships": deactivated},
                    )
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
        return render(
            request,
            "projects/project_detail.html",
            _project_detail_context(request, project, membership_form=form),
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

    record_activity(
        actor=request.user,
        kind=ActivityEvent.Kind.MEMBER_ADDED,
        summary=(
            f"{'added' if created else 'restored'} "
            f"{user.preferred_name} as {membership.get_role_display()}"
        ),
        project=project,
        details={
            "subject_user_id": user.pk,
            "role": membership.role,
            "reactivated": not created,
        },
    )
    messages.success(request, f"{user.preferred_name} was added to the project.")
    return redirect("projects:detail", pk=project.pk)


@login_required
@require_POST
@transaction.atomic
def membership_role_update(request, pk, membership_pk):
    """Change an active member role; project owner only."""
    project = _owned_project_or_404(request.user, pk)
    membership = get_object_or_404(
        project.memberships.select_related("user"),
        pk=membership_pk,
        is_active=True,
    )
    previous_role = membership.role
    form = MembershipRoleForm(request.POST, instance=membership)
    if form.is_valid():
        membership = form.save()
        if membership.role != previous_role:
            previous_label = ProjectMembership.Role(previous_role).label
            record_activity(
                actor=request.user,
                kind=ActivityEvent.Kind.MEMBER_ROLE_CHANGED,
                summary=(
                    f"changed {membership.user.preferred_name}'s role "
                    f"from {previous_label} to {membership.get_role_display()}"
                ),
                project=project,
                details={
                    "subject_user_id": membership.user_id,
                    "from_role": previous_role,
                    "to_role": membership.role,
                },
            )
        messages.success(
            request,
            f"{membership.user.preferred_name}'s role was updated.",
        )
    else:
        messages.error(request, "The member role could not be updated.")
    return redirect("projects:detail", pk=project.pk)


@login_required
@require_POST
@transaction.atomic
def membership_remove(request, pk, membership_pk):
    """Revoke future project access without deleting membership history."""
    project = _owned_project_or_404(request.user, pk)
    membership = get_object_or_404(
        project.memberships.select_related("user"),
        pk=membership_pk,
        is_active=True,
    )
    removed_user_id = membership.user_id
    removed_name = membership.user.preferred_name
    removed_role = membership.role

    membership.is_active = False
    membership.save(update_fields=["is_active"])
    record_activity(
        actor=request.user,
        kind=ActivityEvent.Kind.MEMBER_REMOVED,
        summary=f"removed {removed_name} from the project",
        project=project,
        details={
            "subject_user_id": removed_user_id,
            "previous_role": removed_role,
        },
    )
    messages.success(
        request,
        f"{removed_name} no longer has project access.",
    )
    return redirect("projects:detail", pk=project.pk)
