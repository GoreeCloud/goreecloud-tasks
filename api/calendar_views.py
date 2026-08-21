"""Read-only task projections for GoreeCloud Calendar."""

from __future__ import annotations

import secrets

from django.contrib.auth import get_user_model
from django.http import HttpResponseNotAllowed, JsonResponse
from django.utils import timezone

from tasks.models import Task

from .calendar_config import CalendarAPIConfiguration, load_calendar_api_configuration

SCHEMA = "goreecloud.tasks.calendar-projections.v1"


def _authentication_failure() -> JsonResponse:
    response = JsonResponse({"detail": "Authentication required."}, status=401)
    response["WWW-Authenticate"] = "Bearer"
    response["Cache-Control"] = "private, no-store"
    return response


def _configuration_failure() -> JsonResponse:
    response = JsonResponse(
        {"detail": "Integration configuration is unavailable."}, status=503
    )
    response["Cache-Control"] = "private, no-store"
    return response


def _configured_identity(request, config: CalendarAPIConfiguration):
    authorization = request.headers.get("Authorization", "")
    scheme, separator, supplied_token = authorization.partition(" ")
    if not separator or scheme.casefold() != "bearer" or not supplied_token.strip():
        return None
    if not config.token or not secrets.compare_digest(
        supplied_token.strip(), config.token
    ):
        return None
    return (
        get_user_model()
        .objects.filter(username=config.username, is_active=True)
        .first()
    )


def _serialize_task(task: Task) -> dict[str, object]:
    """Return the minimal Calendar-safe projection of one task."""

    return {
        "id": task.id,
        "title": task.title,
        "due_at": task.due_at.isoformat(),
        "priority": {
            "value": int(task.priority),
            "label": task.get_priority_display(),
        },
        "status": {
            "value": task.status,
            "label": task.get_status_display(),
        },
        "recurrence": {
            "value": task.recurrence,
            "label": task.get_recurrence_display(),
        },
        "project": (
            {"id": task.project_id, "name": task.project.name}
            if task.project_id
            else None
        ),
        "updated_at": task.updated_at.isoformat(),
    }


def calendar_task_projections(request):
    """Expose scheduled tasks currently visible to one configured Tasks principal.

    The projection is deliberately read-only and omits descriptions, comments, labels,
    reminders, account details, operational notes, and other content Calendar does not need
    merely to place a task on a schedule. Authorization is recalculated on every request via
    ``Task.objects.visible_to(identity)``.
    """

    config = load_calendar_api_configuration()
    if not config.enabled:
        return JsonResponse({"detail": "Not found."}, status=404)
    if config.error:
        return _configuration_failure()

    if request.method != "GET":
        response = HttpResponseNotAllowed(["GET"])
        response["Cache-Control"] = "private, no-store"
        return response

    identity = _configured_identity(request, config)
    if identity is None:
        return _authentication_failure()

    queryset = (
        Task.objects.visible_to(identity)
        .filter(due_at__isnull=False)
        .exclude(status__in=[Task.Status.COMPLETED, Task.Status.CANCELLED])
        .select_related("project")
        .order_by("due_at", "priority", "id")
    )
    tasks = tuple(queryset[: config.max_tasks])

    response = JsonResponse(
        {
            "schema": SCHEMA,
            "version": 1,
            "generated_at": timezone.now().isoformat(),
            "authorization": {
                "identity": identity.username,
                "scope": "scheduled tasks visible to the configured Tasks principal",
            },
            "returned": len(tasks),
            "tasks": [_serialize_task(task) for task in tasks],
        }
    )
    response["Cache-Control"] = "private, no-store"
    response["Vary"] = "Authorization"
    return response
