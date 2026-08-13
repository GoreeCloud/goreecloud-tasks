"""Least-privilege authorization validation for the GoreeCloud Manager identity."""

from __future__ import annotations

from dataclasses import dataclass

from projects.models import Project, ProjectMembership
from tasks.models import Task


@dataclass(frozen=True)
class ManagerIdentityValidation:
    """Result of validating the dedicated Manager service identity."""

    errors: tuple[str, ...]
    memberships: tuple[ProjectMembership, ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_manager_identity(
    user,
    *,
    require_membership: bool = False,
) -> ManagerIdentityValidation:
    """Validate the approved non-interactive, Viewer-only Manager identity posture.

    The deployment validation command and live API share this check so authorization drift
    fails closed at runtime instead of relying only on a pre-deployment validation step.
    """

    errors: list[str] = []

    if not user.is_active:
        errors.append("the identity is inactive")
    if user.is_staff:
        errors.append("the identity has Django staff access")
    if user.is_superuser:
        errors.append("the identity has Django superuser access")
    if user.has_usable_password():
        errors.append("the identity has a usable interactive password")
    if getattr(user, "email", "").strip():
        errors.append("the identity has an email address assigned")

    owned_projects = Project.objects.filter(owner=user).order_by("id")
    if owned_projects.exists():
        ids = ", ".join(
            str(project_id)
            for project_id in owned_projects.values_list("id", flat=True)
        )
        errors.append(f"the identity owns project(s): {ids}")

    personal_tasks = Task.objects.filter(creator=user, project__isnull=True).order_by("id")
    if personal_tasks.exists():
        ids = ", ".join(
            str(task_id)
            for task_id in personal_tasks.values_list("id", flat=True)
        )
        errors.append(f"the identity owns private personal task(s): {ids}")

    memberships = tuple(
        ProjectMembership.objects.filter(user=user, is_active=True)
        .select_related("project")
        .order_by("project_id")
    )
    for membership in memberships:
        project = membership.project
        if membership.role != ProjectMembership.Role.VIEWER:
            errors.append(
                f"project {project.id} membership is {membership.role!r}, not Viewer"
            )
        if project.visibility != Project.Visibility.SHARED:
            errors.append(f"project {project.id} is not Shared")
        if project.is_archived:
            errors.append(
                f"project {project.id} is archived but membership remains active"
            )

    if require_membership and not memberships:
        errors.append("the identity has no active Viewer project membership")

    return ManagerIdentityValidation(
        errors=tuple(errors),
        memberships=memberships,
    )
