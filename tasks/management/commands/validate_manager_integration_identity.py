"""Validate the least-privilege Tasks identity used by GoreeCloud Manager."""

from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from api.authorization import validate_manager_identity


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

        validation = validate_manager_identity(
            user,
            require_membership=bool(options.get("require_membership")),
        )
        if not validation.is_valid:
            formatted = "\n - ".join(validation.errors)
            raise CommandError(
                f"Manager integration identity validation failed for {username!r}:\n - {formatted}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Manager integration identity {username!r} passed least-privilege validation."
            )
        )
        if validation.memberships:
            self.stdout.write("Active approved Viewer memberships:")
            for membership in validation.memberships:
                self.stdout.write(
                    f" - project {membership.project_id}: {membership.project.name}"
                )
        else:
            self.stdout.write("Active approved Viewer memberships: none")
