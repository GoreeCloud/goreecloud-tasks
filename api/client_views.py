"""Read-only first-party client API for GoreeCloud Tasks.

This surface is intentionally authenticated with the normal GoreeCloud Tasks user
session for its first Development tranche. It does not introduce a second user,
service credential, bearer-token registry, or mobile-only authorization model.
Every task is selected through the same ``visible_to`` / ``editable_by`` helpers
used by the application before it is serialized for a native client.
"""

from __future__ import annotations

from django.db.models import F
from django.http import HttpResponseNotAllowed, JsonResponse
from django.utils import timezone

from tasks.models import Task

SCHEMA = "goreecloud.tasks.client-task-list.v1"
DEFAULT_LIMIT = 100
MAX_LIMIT = 200


def _private_json(payload: dict[str, object], *, status: int = 200) -> JsonResponse:
    response = JsonResponse(payload, status=status)
    response["Cache-Control"] = "private, no-store"
    response["Vary"] = "Cookie"
    return response


def _bad_request(detail: str) -> JsonResponse:
    return _private_json({"detail": detail}, status=400)


def _parse_limit(raw_value: str | None) -> int | JsonResponse:
    if raw_value is None:
        return DEFAULT_LIMIT
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return _bad_request("limit must be an integer between 1 and 200.")
    if not 1 <= value <= MAX_LIMIT:
        return _bad_request("limit must be an integer between 1 and 200.")
    return value


def _parse_project(raw_value: str | None) -> int | None | JsonResponse:
    if raw_value is None:
        return None
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return _bad_request("project must be a positive integer project id.")
    if value <= 0:
        return _bad_request("project must be a positive integer project id.")
    return value


def _serialize_task(task: Task, *, editable: bool) -> dict[str, object]:
    return {
        "id": task.id,
        "title": task.title,
        "project": (
            {"id": task.project_id, "name": task.project.name}
            if task.project_id
            else None
        ),
        "parent_id": task.parent_id,
        "assignee": (
            {"id": task.assignee_id, "username": task.assignee.username}
            if task.assignee_id
            else None
        ),
        "priority": {
            "value": int(task.priority),
            "label": task.get_priority_display(),
        },
        "status": {
            "value": task.status,
            "label": task.get_status_display(),
        },
        "due_at": task.due_at.isoformat() if task.due_at else None,
        "recurrence": {
            "value": task.recurrence,
            "label": task.get_recurrence_display(),
        },
        "editable": editable,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


def client_tasks(request):
    """List tasks visible to the currently authenticated GoreeCloud user.

    Query parameters:

    ``state``
        ``active`` (default), ``completed``, or ``all``.
    ``status``
        Optional exact task status value.
    ``project``
        Optional positive project id. Visibility is still enforced first.
    ``limit``
        Result cap from 1 through 200; defaults to 100.

    Descriptions, comments, labels, reminder state, operational notes, and other
    non-list content are deliberately omitted from this first native-client
    contract. Mutation endpoints are also intentionally absent.
    """

    if request.method != "GET":
        response = HttpResponseNotAllowed(["GET"])
        response["Cache-Control"] = "private, no-store"
        response["Vary"] = "Cookie"
        return response

    identity = request.user
    if not identity.is_authenticated or not identity.is_active:
        return _private_json({"detail": "Authentication required."}, status=401)

    state = request.GET.get("state", "active")
    if state not in {"active", "completed", "all"}:
        return _bad_request("state must be one of: active, completed, all.")

    status_filter = request.GET.get("status")
    if status_filter is not None and status_filter not in Task.Status.values:
        return _bad_request("status is not a recognized task status value.")

    project_filter = _parse_project(request.GET.get("project"))
    if isinstance(project_filter, JsonResponse):
        return project_filter

    limit = _parse_limit(request.GET.get("limit"))
    if isinstance(limit, JsonResponse):
        return limit

    queryset = Task.objects.visible_to(identity)
    if state == "active":
        queryset = queryset.exclude(
            status__in=[Task.Status.COMPLETED, Task.Status.CANCELLED]
        )
    elif state == "completed":
        queryset = queryset.filter(status=Task.Status.COMPLETED)

    if status_filter is not None:
        queryset = queryset.filter(status=status_filter)
    if project_filter is not None:
        queryset = queryset.filter(project_id=project_filter)

    tasks = tuple(
        queryset.select_related("project", "assignee")
        .order_by("priority", F("due_at").asc(nulls_last=True), "created_at", "id")[:limit]
    )
    editable_ids = set(
        Task.objects.editable_by(identity)
        .filter(id__in=[task.id for task in tasks])
        .values_list("id", flat=True)
    )

    return _private_json(
        {
            "schema": SCHEMA,
            "version": 1,
            "generated_at": timezone.now().isoformat(),
            "authorization": {
                "identity": identity.username,
                "scope": "tasks visible to the authenticated GoreeCloud user",
            },
            "filters": {
                "state": state,
                "status": status_filter,
                "project": project_filter,
                "limit": limit,
            },
            "returned": len(tasks),
            "tasks": [
                _serialize_task(task, editable=task.id in editable_ids)
                for task in tasks
            ],
        }
    )
