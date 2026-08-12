"""Read-only integration endpoints for GoreeCloud Tasks.

The Manager endpoint deliberately maps one deployment-configured bearer token to one
existing Tasks user. The user remains the authorization principal: every returned task is
selected through ``Task.objects.visible_to(identity)`` before the integration-specific
operational filter is applied. Manager therefore cannot choose or impersonate another user.
"""

from __future__ import annotations

import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponseNotAllowed, JsonResponse
from django.utils import timezone

from tasks.models import Task

SCHEMA = "goreecloud.tasks.manager.v1"


def _authentication_failure() -> JsonResponse:
    response = JsonResponse({"detail": "Authentication required."}, status=401)
    response["WWW-Authenticate"] = "Bearer"
    response["Cache-Control"] = "private, no-store"
    return response


def _configured_identity(request):
    authorization = request.headers.get("Authorization", "")
    scheme, separator, supplied_token = authorization.partition(" ")
    if not separator or scheme.casefold() != "bearer" or not supplied_token.strip():
        return None

    configured_token = settings.TASKS_MANAGER_API_TOKEN
    if not configured_token or not secrets.compare_digest(
        supplied_token.strip(), configured_token
    ):
        return None

    return (
        get_user_model()
        .objects.filter(
            username=settings.TASKS_MANAGER_API_USERNAME,
            is_active=True,
        )
        .first()
    )


def _serialize_task(task: Task) -> dict[str, object]:
    """Return only fields approved for Manager operational visibility."""

    return {
        "id": task.id,
        "title": task.title,
        "project": {
            "id": task.project_id,
            "name": task.project.name,
        },
        "priority": {
            "value": int(task.priority),
            "label": task.get_priority_display(),
        },
        "status": {
            "value": task.status,
            "label": task.get_status_display(),
        },
        "due_at": task.due_at.isoformat() if task.due_at else None,
        "assigned_system": task.assigned_system,
        "assigned_service": task.assigned_service,
        "environment": task.environment,
        "workload_category": task.workload_category,
        "blocker": task.blocker,
        "resume_condition": task.resume_condition,
        "requirements": {
            "backup": task.backup_prerequisite,
            "recovery": task.recovery_requirement,
            "validation": task.validation_requirement,
            "documentation": task.documentation_requirement,
        },
        "related_change_record": task.related_change_record,
        "related_documentation": task.related_documentation,
        "updated_at": task.updated_at.isoformat(),
    }


def manager_operational_tasks(request):
    """Expose authorization-scoped active GoreeCloud work to Manager.

    This is intentionally a GET-only, data-minimized integration surface. It does not expose
    personal Inbox tasks, ordinary non-operational tasks, descriptions, comments, labels,
    account details, notification state, or any write operation.
    """

    if not settings.TASKS_MANAGER_API_ENABLED:
        return JsonResponse({"detail": "Not found."}, status=404)

    if request.method != "GET":
        response = HttpResponseNotAllowed(["GET"])
        response["Cache-Control"] = "private, no-store"
        return response

    identity = _configured_identity(request)
    if identity is None:
        return _authentication_failure()

    queryset = (
        Task.objects.visible_to(identity)
        .filter(
            is_goreecloud_work=True,
            project__isnull=False,
            project__is_archived=False,
        )
        .exclude(status__in=[Task.Status.COMPLETED, Task.Status.CANCELLED])
        .select_related("project")
        .order_by("priority", "due_at", "created_at", "id")
    )

    total_open = queryset.count()
    blocked = queryset.filter(status=Task.Status.BLOCKED).count()
    p0 = queryset.filter(priority=Task.Priority.P0_CRITICAL).count()
    p1 = queryset.filter(priority=Task.Priority.P1_URGENT).count()
    tasks = tuple(queryset[: settings.TASKS_MANAGER_API_MAX_TASKS])

    response = JsonResponse(
        {
            "schema": SCHEMA,
            "version": 1,
            "generated_at": timezone.now().isoformat(),
            "authorization": {
                "identity": identity.username,
                "scope": "visible operational project tasks only",
            },
            "summary": {
                "total_open": total_open,
                "blocked": blocked,
                "p0": p0,
                "p1": p1,
                "returned": len(tasks),
            },
            "tasks": [_serialize_task(task) for task in tasks],
        }
    )
    response["Cache-Control"] = "private, no-store"
    response["Vary"] = "Authorization"
    return response
