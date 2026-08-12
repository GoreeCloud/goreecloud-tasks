#!/usr/bin/env python3
"""Create and mutate disposable data for Manager cross-application validation.

This helper is intentionally limited to CI/development databases. It creates synthetic
accounts, projects, memberships, tasks, and a comment that exercise the authorization and
data-minimization contract exposed through the GoreeCloud Tasks Manager API.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "goreecloud_tasks.settings")

import django

django.setup()

from django.contrib.auth import get_user_model

from collaboration.models import TaskComment
from projects.models import Project, ProjectMembership
from tasks.models import Task

OWNER_USERNAME = "manager-e2e-owner"
INTEGRATION_USERNAME = "goreecloud-manager-integration"
OUTSIDER_USERNAME = "manager-e2e-outsider"
SHARED_PROJECT_NAME = "Manager E2E Infrastructure Work"
PRIVATE_PROJECT_NAME = "Manager E2E Private Work"
VISIBLE_TASK_TITLE = "Validate Manager cross-application recovery visibility"
SENSITIVE_DESCRIPTION = "MANAGER-E2E-SENSITIVE-DESCRIPTION-MUST-NOT-LEAK"
SENSITIVE_COMMENT = "MANAGER-E2E-SENSITIVE-COMMENT-MUST-NOT-LEAK"


def _user(username: str):
    user_model = get_user_model()
    user, _ = user_model.objects.get_or_create(username=username)
    if not user.is_active:
        user.is_active = True
        user.save(update_fields=["is_active"])
    return user


def seed() -> None:
    """Create a deterministic synthetic integration scope."""

    owner = _user(OWNER_USERNAME)
    integration = _user(INTEGRATION_USERNAME)
    outsider = _user(OUTSIDER_USERNAME)

    shared_project, _ = Project.objects.get_or_create(
        owner=owner,
        name=SHARED_PROJECT_NAME,
        defaults={"visibility": Project.Visibility.SHARED},
    )
    if shared_project.visibility != Project.Visibility.SHARED:
        shared_project.visibility = Project.Visibility.SHARED
        shared_project.save(update_fields=["visibility", "updated_at"])

    membership, _ = ProjectMembership.objects.get_or_create(
        project=shared_project,
        user=integration,
        defaults={"role": ProjectMembership.Role.VIEWER, "is_active": True},
    )
    membership.role = ProjectMembership.Role.VIEWER
    membership.is_active = True
    membership.save(update_fields=["role", "is_active"])

    private_project, _ = Project.objects.get_or_create(
        owner=owner,
        name=PRIVATE_PROJECT_NAME,
        defaults={"visibility": Project.Visibility.PRIVATE},
    )
    if private_project.visibility != Project.Visibility.PRIVATE:
        private_project.visibility = Project.Visibility.PRIVATE
        private_project.save(update_fields=["visibility", "updated_at"])

    visible_task, created = Task.objects.get_or_create(
        creator=owner,
        project=shared_project,
        title=VISIBLE_TASK_TITLE,
        defaults={
            "description": SENSITIVE_DESCRIPTION,
            "priority": Task.Priority.P1_URGENT,
            "status": Task.Status.BLOCKED,
            "is_goreecloud_work": True,
            "assigned_system": "Infrastructure Services VM",
            "assigned_service": "GoreeCloud Manager",
            "environment": "disposable-ci",
            "workload_category": "Integration Validation",
            "blocker": "Cross-application validation pending",
            "resume_condition": "Complete disposable integration gate",
            "backup_prerequisite": True,
            "recovery_requirement": True,
            "validation_requirement": True,
            "documentation_requirement": True,
            "related_change_record": "GoreeCloud Tasks change log",
            "related_documentation": "Manager cross-application validation",
        },
    )
    if not created:
        visible_task.description = SENSITIVE_DESCRIPTION
        visible_task.priority = Task.Priority.P1_URGENT
        visible_task.status = Task.Status.BLOCKED
        visible_task.is_goreecloud_work = True
        visible_task.assigned_system = "Infrastructure Services VM"
        visible_task.assigned_service = "GoreeCloud Manager"
        visible_task.environment = "disposable-ci"
        visible_task.workload_category = "Integration Validation"
        visible_task.blocker = "Cross-application validation pending"
        visible_task.resume_condition = "Complete disposable integration gate"
        visible_task.backup_prerequisite = True
        visible_task.recovery_requirement = True
        visible_task.validation_requirement = True
        visible_task.documentation_requirement = True
        visible_task.related_change_record = "GoreeCloud Tasks change log"
        visible_task.related_documentation = "Manager cross-application validation"
        visible_task.save()

    TaskComment.objects.get_or_create(
        task=visible_task,
        author=owner,
        body=SENSITIVE_COMMENT,
    )

    Task.objects.get_or_create(
        creator=owner,
        project=shared_project,
        title="Manager E2E ordinary shared task",
        defaults={"is_goreecloud_work": False},
    )
    Task.objects.get_or_create(
        creator=owner,
        project=private_project,
        title="Manager E2E private operational task",
        defaults={"is_goreecloud_work": True},
    )
    Task.objects.get_or_create(
        creator=integration,
        title="Manager E2E integration personal task",
        defaults={"is_goreecloud_work": True},
    )
    Task.objects.get_or_create(
        creator=owner,
        project=shared_project,
        title="Manager E2E completed operational task",
        defaults={
            "status": Task.Status.COMPLETED,
            "is_goreecloud_work": True,
        },
    )
    Task.objects.get_or_create(
        creator=outsider,
        title="Manager E2E outsider personal task",
        defaults={"is_goreecloud_work": True},
    )

    print("Seeded disposable Manager cross-application fixture.")


def revoke() -> None:
    """Deactivate the integration user's project membership."""

    updated = ProjectMembership.objects.filter(
        project__name=SHARED_PROJECT_NAME,
        project__owner__username=OWNER_USERNAME,
        user__username=INTEGRATION_USERNAME,
        is_active=True,
    ).update(is_active=False)
    if updated != 1:
        raise SystemExit(
            f"Expected to revoke exactly one Manager integration membership; updated {updated}."
        )
    print("Revoked disposable Manager integration membership.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("seed", "revoke"))
    args = parser.parse_args()
    if args.action == "seed":
        seed()
    else:
        revoke()


if __name__ == "__main__":
    main()
