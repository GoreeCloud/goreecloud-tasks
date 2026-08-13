#!/usr/bin/env python3
"""Seed and validate a disposable PostgreSQL backup/restoration fixture.

This helper is intentionally limited to isolated validation databases. It creates only
synthetic GoreeCloud Tasks data and provides a normalized snapshot plus semantic
assertions that can be run before and after a PostgreSQL dump/restoration cycle.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone as datetime_timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "goreecloud_tasks.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.db import transaction

from collaboration.models import ActivityEvent, TaskComment
from labels.models import Label
from notifications.models import NotificationPreference, TaskReminder
from projects.models import Project, ProjectMembership
from tasks.models import Task

PREFIX = "backup-restore-"
OWNER_USERNAME = f"{PREFIX}owner"
MEMBER_USERNAME = f"{PREFIX}member"
REVOKED_USERNAME = f"{PREFIX}revoked"
SYNTHETIC_PASSWORD = "ci-only-backup-restore-password"

SHARED_PROJECT = "Backup Restore Shared Project"
PRIVATE_PROJECT = "Backup Restore Private Project"
PERSONAL_LABEL = "recovery-personal"
PROJECT_LABEL = "recovery-project"
PERSONAL_TASK = "Backup Restore Personal Task"
OPERATIONAL_TASK = "Backup Restore Operational Task"
SUBTASK = "Backup Restore Shared Subtask"
COMMENT_BODY = "Synthetic shared recovery comment"
ACTIVITY_SUMMARY = "Synthetic recovery fixture activity"
OWNER_TOPIC = "goreecloud-tasks-backuprestore-owner"
MEMBER_TOPIC = "goreecloud-tasks-backuprestore-member"

DUE_AT = datetime(2031, 1, 15, 18, 30, tzinfo=datetime_timezone.utc)
OWNER_REMIND_AT = datetime(2031, 1, 15, 18, 0, tzinfo=datetime_timezone.utc)
MEMBER_REMIND_AT = datetime(2031, 1, 15, 17, 45, tzinfo=datetime_timezone.utc)
LAST_ATTEMPT_AT = datetime(2031, 1, 14, 18, 0, tzinfo=datetime_timezone.utc)


def _iso(value):
    if value is None:
        return None
    return value.isoformat()


def _require_clean_target() -> None:
    user_model = get_user_model()
    if user_model.objects.filter(username__startswith=PREFIX).exists():
        raise SystemExit(
            "Synthetic backup/restoration identities already exist; refusing to merge fixtures."
        )


def _create_user(username: str, *, display_name: str, timezone_name: str = "America/Chicago"):
    user_model = get_user_model()
    user = user_model(
        username=username,
        display_name=display_name,
        timezone=timezone_name,
        is_active=True,
        is_staff=False,
        is_superuser=False,
        email="",
    )
    user.set_password(SYNTHETIC_PASSWORD)
    user.save()
    return user


def seed() -> None:
    """Create deterministic, production-representative synthetic application state."""

    _require_clean_target()

    with transaction.atomic():
        owner = _create_user(OWNER_USERNAME, display_name="Recovery Owner")
        member = _create_user(MEMBER_USERNAME, display_name="Recovery Member")
        revoked = _create_user(REVOKED_USERNAME, display_name="Recovery Revoked")

        shared = Project.objects.create(
            owner=owner,
            name=SHARED_PROJECT,
            visibility=Project.Visibility.SHARED,
        )
        private = Project.objects.create(
            owner=owner,
            name=PRIVATE_PROJECT,
            visibility=Project.Visibility.PRIVATE,
        )

        ProjectMembership.objects.create(
            project=shared,
            user=member,
            role=ProjectMembership.Role.MEMBER,
            is_active=True,
        )
        ProjectMembership.objects.create(
            project=shared,
            user=revoked,
            role=ProjectMembership.Role.VIEWER,
            is_active=False,
        )

        personal_label = Label.objects.create(
            owner=owner,
            name=PERSONAL_LABEL,
        )
        project_label = Label.objects.create(
            owner=owner,
            project=shared,
            name=PROJECT_LABEL,
        )

        personal_task = Task.objects.create(
            title=PERSONAL_TASK,
            description="Synthetic private task body preserved by database recovery.",
            creator=owner,
            assignee=owner,
            priority=Task.Priority.P2_HIGH,
            status=Task.Status.READY,
            due_at=DUE_AT,
        )
        personal_task.labels.add(personal_label)

        operational_task = Task.objects.create(
            title=OPERATIONAL_TASK,
            description="Synthetic shared operational task body.",
            creator=owner,
            assignee=member,
            project=shared,
            priority=Task.Priority.P1_URGENT,
            status=Task.Status.BLOCKED,
            due_at=DUE_AT,
            is_goreecloud_work=True,
            assigned_system="Infrastructure Services VM",
            assigned_service="GoreeCloud Tasks",
            environment="disposable-backup-restore-ci",
            workload_category="Recovery Validation",
            blocker="Synthetic restore validation pending",
            resume_condition="Database restore assertions pass",
            backup_prerequisite=True,
            recovery_requirement=True,
            validation_requirement=True,
            documentation_requirement=True,
            related_change_record="GoreeCloud Tasks change log",
            related_documentation="PostgreSQL backup restoration validation",
        )
        operational_task.labels.add(project_label)

        Task.objects.create(
            title=SUBTASK,
            description="Synthetic subtask relationship preserved through PostgreSQL restore.",
            creator=member,
            assignee=member,
            project=shared,
            parent=operational_task,
            priority=Task.Priority.P3_STANDARD,
            status=Task.Status.IN_PROGRESS,
        )

        TaskComment.objects.create(
            task=operational_task,
            author=member,
            body=COMMENT_BODY,
        )
        ActivityEvent.objects.create(
            actor=member,
            project=shared,
            task=operational_task,
            kind=ActivityEvent.Kind.TASK_UPDATED,
            summary=ACTIVITY_SUMMARY,
            details={
                "changed_fields": ["status", "priority"],
                "fixture": "postgres-backup-restore",
            },
        )

        NotificationPreference.objects.create(
            user=owner,
            reminders_enabled=True,
            default_lead_minutes=30,
            ntfy_enabled=True,
            ntfy_topic=OWNER_TOPIC,
        )
        NotificationPreference.objects.create(
            user=member,
            reminders_enabled=True,
            default_lead_minutes=45,
            ntfy_enabled=False,
            ntfy_topic=MEMBER_TOPIC,
        )

        TaskReminder.objects.create(
            user=owner,
            task=personal_task,
            remind_at=OWNER_REMIND_AT,
            last_attempt_at=LAST_ATTEMPT_AT,
            attempt_count=2,
        )
        TaskReminder.objects.create(
            user=member,
            task=operational_task,
            remind_at=MEMBER_REMIND_AT,
            attempt_count=0,
        )

        # Keep a separate private project in the fixture even without tasks so the
        # project ownership/privacy boundary itself is part of the database image.
        if private.can_view(member):
            raise AssertionError("Synthetic private project unexpectedly visible to member.")

    print("Seeded disposable PostgreSQL backup/restoration fixture.")


def snapshot() -> dict:
    """Return normalized synthetic application state suitable for exact comparison."""

    user_model = get_user_model()
    users = list(user_model.objects.filter(username__startswith=PREFIX).order_by("username"))
    projects = list(Project.objects.filter(owner__username__startswith=PREFIX).order_by("id"))
    project_ids = [project.id for project in projects]
    tasks = list(
        Task.objects.filter(creator__username__startswith=PREFIX)
        .select_related("creator", "assignee", "project", "parent")
        .prefetch_related("labels")
        .order_by("id")
    )

    return {
        "users": [
            {
                "id": user.id,
                "username": user.username,
                "display_name": user.display_name,
                "timezone": user.timezone,
                "password_hash": user.password,
                "is_active": user.is_active,
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "date_joined": _iso(user.date_joined),
                "last_login": _iso(user.last_login),
            }
            for user in users
        ],
        "projects": [
            {
                "id": project.id,
                "owner": project.owner.username,
                "name": project.name,
                "visibility": project.visibility,
                "is_archived": project.is_archived,
                "created_at": _iso(project.created_at),
                "updated_at": _iso(project.updated_at),
            }
            for project in projects
        ],
        "memberships": [
            {
                "id": membership.id,
                "project": membership.project.name,
                "user": membership.user.username,
                "role": membership.role,
                "is_active": membership.is_active,
                "created_at": _iso(membership.created_at),
            }
            for membership in ProjectMembership.objects.filter(project_id__in=project_ids)
            .select_related("project", "user")
            .order_by("id")
        ],
        "labels": [
            {
                "id": label.id,
                "name": label.name,
                "owner": label.owner.username,
                "project": label.project.name if label.project_id else None,
                "created_at": _iso(label.created_at),
            }
            for label in Label.objects.filter(owner__username__startswith=PREFIX)
            .select_related("owner", "project")
            .order_by("id")
        ],
        "tasks": [
            {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "creator": task.creator.username,
                "assignee": task.assignee.username if task.assignee_id else None,
                "project": task.project.name if task.project_id else None,
                "parent": task.parent.title if task.parent_id else None,
                "labels": sorted(label.name for label in task.labels.all()),
                "priority": task.priority,
                "status": task.status,
                "due_at": _iso(task.due_at),
                "completed_at": _iso(task.completed_at),
                "is_goreecloud_work": task.is_goreecloud_work,
                "assigned_system": task.assigned_system,
                "assigned_service": task.assigned_service,
                "environment": task.environment,
                "workload_category": task.workload_category,
                "blocker": task.blocker,
                "resume_condition": task.resume_condition,
                "backup_prerequisite": task.backup_prerequisite,
                "recovery_requirement": task.recovery_requirement,
                "validation_requirement": task.validation_requirement,
                "documentation_requirement": task.documentation_requirement,
                "related_change_record": task.related_change_record,
                "related_documentation": task.related_documentation,
                "created_at": _iso(task.created_at),
                "updated_at": _iso(task.updated_at),
            }
            for task in tasks
        ],
        "comments": [
            {
                "id": comment.id,
                "task": comment.task.title,
                "author": comment.author.username,
                "body": comment.body,
                "created_at": _iso(comment.created_at),
                "updated_at": _iso(comment.updated_at),
            }
            for comment in TaskComment.objects.filter(task__in=tasks)
            .select_related("task", "author")
            .order_by("id")
        ],
        "activity": [
            {
                "id": event.id,
                "actor": event.actor.username,
                "project": event.project.name if event.project_id else None,
                "task": event.task.title if event.task_id else None,
                "kind": event.kind,
                "summary": event.summary,
                "details": event.details,
                "created_at": _iso(event.created_at),
            }
            for event in ActivityEvent.objects.filter(actor__username__startswith=PREFIX)
            .select_related("actor", "project", "task")
            .order_by("id")
        ],
        "notification_preferences": [
            {
                "id": preference.id,
                "user": preference.user.username,
                "reminders_enabled": preference.reminders_enabled,
                "default_lead_minutes": preference.default_lead_minutes,
                "ntfy_enabled": preference.ntfy_enabled,
                "ntfy_topic": preference.ntfy_topic,
                "created_at": _iso(preference.created_at),
                "updated_at": _iso(preference.updated_at),
            }
            for preference in NotificationPreference.objects.filter(
                user__username__startswith=PREFIX
            )
            .select_related("user")
            .order_by("id")
        ],
        "reminders": [
            {
                "id": reminder.id,
                "user": reminder.user.username,
                "task": reminder.task.title,
                "remind_at": _iso(reminder.remind_at),
                "sent_at": _iso(reminder.sent_at),
                "cancelled_at": _iso(reminder.cancelled_at),
                "last_attempt_at": _iso(reminder.last_attempt_at),
                "attempt_count": reminder.attempt_count,
                "last_error": reminder.last_error,
                "created_at": _iso(reminder.created_at),
                "updated_at": _iso(reminder.updated_at),
            }
            for reminder in TaskReminder.objects.filter(user__username__startswith=PREFIX)
            .select_related("user", "task")
            .order_by("id")
        ],
    }


def assert_semantics() -> None:
    """Verify restored state still enforces the intended application boundaries."""

    user_model = get_user_model()
    owner = user_model.objects.get(username=OWNER_USERNAME)
    member = user_model.objects.get(username=MEMBER_USERNAME)
    revoked = user_model.objects.get(username=REVOKED_USERNAME)

    if not owner.check_password(SYNTHETIC_PASSWORD):
        raise AssertionError("Owner authentication state was not restored correctly.")
    if not member.check_password(SYNTHETIC_PASSWORD):
        raise AssertionError("Member authentication state was not restored correctly.")
    if not revoked.check_password(SYNTHETIC_PASSWORD):
        raise AssertionError("Revoked-member authentication state was not restored correctly.")

    shared = Project.objects.get(owner=owner, name=SHARED_PROJECT)
    private = Project.objects.get(owner=owner, name=PRIVATE_PROJECT)
    active_membership = ProjectMembership.objects.get(project=shared, user=member)
    revoked_membership = ProjectMembership.objects.get(project=shared, user=revoked)

    if active_membership.role != ProjectMembership.Role.MEMBER or not active_membership.is_active:
        raise AssertionError("Active shared-project membership was not restored correctly.")
    if revoked_membership.role != ProjectMembership.Role.VIEWER or revoked_membership.is_active:
        raise AssertionError("Revoked historical membership was not restored correctly.")
    if private.can_view(member) or private.can_view(revoked):
        raise AssertionError("Private-project authorization widened after restoration.")

    personal_task = Task.objects.get(creator=owner, title=PERSONAL_TASK)
    operational_task = Task.objects.get(project=shared, title=OPERATIONAL_TASK)
    subtask = Task.objects.get(project=shared, title=SUBTASK)

    if not Task.objects.visible_to(owner).filter(pk=personal_task.pk).exists():
        raise AssertionError("Owner lost access to restored personal task.")
    if Task.objects.visible_to(member).filter(pk=personal_task.pk).exists():
        raise AssertionError("Member gained access to restored private personal task.")
    if not Task.objects.visible_to(member).filter(pk=operational_task.pk).exists():
        raise AssertionError("Active member lost access to restored shared task.")
    if Task.objects.visible_to(revoked).filter(pk=operational_task.pk).exists():
        raise AssertionError("Revoked member regained shared-task access after restoration.")
    if subtask.parent_id != operational_task.id:
        raise AssertionError("Subtask parent relationship was not restored correctly.")

    if set(personal_task.labels.values_list("name", flat=True)) != {PERSONAL_LABEL}:
        raise AssertionError("Personal label relationship was not restored correctly.")
    if set(operational_task.labels.values_list("name", flat=True)) != {PROJECT_LABEL}:
        raise AssertionError("Project label relationship was not restored correctly.")

    comment = TaskComment.objects.get(task=operational_task, author=member)
    if comment.body != COMMENT_BODY:
        raise AssertionError("Shared comment content was not restored correctly.")

    event = ActivityEvent.objects.get(actor=member, task=operational_task)
    if event.summary != ACTIVITY_SUMMARY or event.details.get("fixture") != "postgres-backup-restore":
        raise AssertionError("Shared activity history was not restored correctly.")

    if operational_task.description != "Synthetic shared operational task body.":
        raise AssertionError("Task content was not restored correctly.")
    if operational_task.assignee_id != member.id or operational_task.creator_id != owner.id:
        raise AssertionError("Task ownership/assignment was not restored correctly.")
    if not (
        operational_task.is_goreecloud_work
        and operational_task.backup_prerequisite
        and operational_task.recovery_requirement
        and operational_task.validation_requirement
        and operational_task.documentation_requirement
    ):
        raise AssertionError("GoreeCloud operational metadata was not restored correctly.")

    owner_preference = NotificationPreference.objects.get(user=owner)
    member_preference = NotificationPreference.objects.get(user=member)
    if owner_preference.ntfy_topic != OWNER_TOPIC or not owner_preference.ntfy_enabled:
        raise AssertionError("Owner notification preferences were not restored correctly.")
    if member_preference.ntfy_topic != MEMBER_TOPIC or member_preference.default_lead_minutes != 45:
        raise AssertionError("Member notification preferences were not restored correctly.")

    owner_reminder = TaskReminder.objects.get(user=owner, task=personal_task)
    member_reminder = TaskReminder.objects.get(user=member, task=operational_task)
    if owner_reminder.remind_at != OWNER_REMIND_AT or owner_reminder.attempt_count != 2:
        raise AssertionError("Owner reminder state was not restored correctly.")
    if owner_reminder.last_attempt_at != LAST_ATTEMPT_AT:
        raise AssertionError("Reminder retry metadata was not restored correctly.")
    if member_reminder.remind_at != MEMBER_REMIND_AT or member_reminder.attempt_count != 0:
        raise AssertionError("Shared-task user reminder state was not restored correctly.")

    print("PostgreSQL restore application semantics validated successfully.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("seed", "snapshot", "assert"))
    args = parser.parse_args()

    if args.action == "seed":
        seed()
    elif args.action == "snapshot":
        print(json.dumps(snapshot(), sort_keys=True, separators=(",", ":")))
    else:
        assert_semantics()


if __name__ == "__main__":
    main()
