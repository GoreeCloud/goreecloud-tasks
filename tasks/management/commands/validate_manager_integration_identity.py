"""Validate the least-privilege Tasks identity used by GoreeCloud Manager."""

from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from projects.models import Project, ProjectMembership
from tasks.models import Task


class Command(BaseCommand):
    """Fail closed when a Manager integration identity is over-privileged."""

    help = (
        "Validate that the configured GoreeCloud Manager Tasks identity is a dedicated, "
        "non-login, Viewer-only service account."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            help=(
                "Tasks username to validate. Defaults to TASKS_MANAGER_API_USERNAME."
            ),
        )
        parser.add_argument(
            "--require-membership",
            action="store_true",
            help="Require at least one active approved Viewer membership.",
        )

    def handle(self, *args, **options):
        username = (
            options.get("username")
            or os.getenv("TASKS_MANAGER_API_USERNAME", "")
        ).strip()
        if not username:
            raise CommandError(
                "Provide --username or set TASKS_MANAGER_API_USERNAME before validation."
            )

        user_model = get_user_model()
        user = user_model.objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"Tasks user {username!r} does not exist.")

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
            ids = ", ".join(str(project_id) for project_id in owned_projects.values_list("id", flat=True))
            errors.append(f"the identity owns project(s): {ids}")

        personal_tasks = Task.objects.filter(creator=user, project__isnull=True).order_by("id")
        if personal_tasks.exists():
            ids = ", ".join(str(task_id) for task_id in personal_tasks.values_list("id", flat=True))
            errors.append(f"the identity owns private personal task(s): {ids}")

        memberships = list(
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
                errors.append(f"project {project.id} is archived but membership remains active")

        if options.get("require_membership") and not memberships:
            errors.append("the identity has no active Viewer project membership")

        if errors:
            formatted = "\n - ".join(errors)
            raise CommandError(
                f"Manager integration identity validation failed for {username!r}:\n - {formatted}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Manager integration identity {username!r} passed least-privilege validation."
            )
        )
        if memberships:
            self.stdout.write("Active approved Viewer memberships:")
            for membership in memberships:
                self.stdout.write(
                    f" - project {membership.project_id}: {membership.project.name}"
                )
        else:
            self.stdout.write("Active approved Viewer memberships: none")
