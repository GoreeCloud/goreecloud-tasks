"""Authorization-scoped GoreeCloud Calendar integration endpoints for Tasks."""

from __future__ import annotations

import json
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt

from collaboration.models import ActivityEvent
from collaboration.services import record_activity
from projects.models import Project
from tasks.models import Task

from .calendar_config import CalendarAPIConfiguration, load_calendar_api_configuration


SCHEMA = "goreecloud.tasks.calendar-projections.v1"
SOURCE_APPLICATION = "goreecloud-tasks"
SOURCE_API_VERSION = 1
MAX_WINDOW = timedelta(days=93)
MAX_REQUEST_BYTES = 16 * 1024
TERMINAL_STATUSES = (Task.Status.COMPLETED, Task.Status.CANCELLED)


def _private(response: HttpResponse) -> HttpResponse:
    response["Cache-Control"] = "private, no-store"
    response["Vary"] = "Authorization"
    return response


def _authentication_failure() -> JsonResponse:
    response = JsonResponse({"detail": "Authentication required."}, status=401)
    response["WWW-Authenticate"] = "Bearer"
    return _private(response)


def _configuration_failure() -> JsonResponse:
    return _private(
        JsonResponse(
            {"detail": "Integration configuration is unavailable."},
            status=503,
        )
    )


def _not_found() -> JsonResponse:
    return _private(JsonResponse({"detail": "Not found."}, status=404))


def _bad_request(detail: str, *, status: int = 400, **extra) -> JsonResponse:
    payload = {"detail": detail}
    payload.update(extra)
    return _private(JsonResponse(payload, status=status))


def _method_not_allowed(methods: list[str]) -> HttpResponseNotAllowed:
    return _private(HttpResponseNotAllowed(methods))


def _configured_identity(request, config: CalendarAPIConfiguration):
    """Map the deployment-scoped Calendar credential to exactly one Tasks user."""
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


def _authorize_request(request):
    """Resolve the configured Calendar integration principal or return an error."""
    config = load_calendar_api_configuration()
    if not config.enabled:
        return None, None, _not_found()
    if config.error:
        return None, None, _configuration_failure()

    identity = _configured_identity(request, config)
    if identity is None:
        return None, None, _authentication_failure()
    return config, identity, None


def _parse_timestamp(value, *, field: str):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO 8601 timestamp.")
    parsed = parse_datetime(value.strip())
    if parsed is None:
        raise ValueError(f"{field} must be a valid ISO 8601 timestamp.")
    if timezone.is_naive(parsed):
        raise ValueError(f"{field} must include a time-zone offset.")
    return parsed


def _parse_window(request):
    start_raw = request.GET.get("start")
    end_raw = request.GET.get("end")
    if start_raw is None and end_raw is None:
        return None, None
    if start_raw is None or end_raw is None:
        raise ValueError("start and end must be supplied together.")

    start = _parse_timestamp(start_raw, field="start")
    end = _parse_timestamp(end_raw, field="end")
    if end <= start:
        raise ValueError("end must be later than start.")
    if end - start > MAX_WINDOW:
        raise ValueError("The requested window cannot exceed 93 days.")
    return start, end


def _read_json_object(request, *, allowed_fields: set[str]):
    content_type = (request.content_type or "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise ValueError("Content-Type must be application/json.")

    try:
        content_length = int(request.META.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        content_length = 0
    if content_length > MAX_REQUEST_BYTES:
        raise ValueError("Request body is too large.")

    if len(request.body) > MAX_REQUEST_BYTES:
        raise ValueError("Request body is too large.")

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Request body must be a valid UTF-8 JSON object.") from exc

    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")

    unknown = sorted(set(payload) - allowed_fields)
    if unknown:
        raise ValueError(f"Unsupported field(s): {', '.join(unknown)}.")
    return payload


def _serialize_task(request, task: Task) -> dict[str, object]:
    """Return the minimized, versioned Calendar projection of one task."""
    task_url = request.build_absolute_uri(
        reverse("tasks:task_detail", args=[task.pk])
    )
    revision = task.updated_at.isoformat()
    return {
        "source": {
            "application": SOURCE_APPLICATION,
            "api_version": SOURCE_API_VERSION,
        },
        "id": task.id,
        "authoritative_url": task_url,
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
        "revision": revision,
        # Kept for compatibility with the existing Calendar consumer.
        "updated_at": revision,
    }


def _scheduled_visible_tasks(identity):
    return (
        Task.objects.visible_to(identity)
        .filter(due_at__isnull=False)
        .exclude(status__in=TERMINAL_STATUSES)
        .select_related("project")
    )


def calendar_task_projections(request):
    """List active scheduled tasks visible to the configured Calendar principal."""
    config, identity, error = _authorize_request(request)
    if error is not None:
        return error
    if request.method != "GET":
        return _method_not_allowed(["GET"])

    try:
        start, end = _parse_window(request)
    except ValueError as exc:
        return _bad_request(str(exc))

    queryset = _scheduled_visible_tasks(identity)
    if start is not None:
        queryset = queryset.filter(due_at__gte=start, due_at__lt=end)
    queryset = queryset.order_by("due_at", "priority", "id")
    tasks = tuple(queryset[: config.max_tasks])

    return _private(
        JsonResponse(
            {
                "schema": SCHEMA,
                "version": SOURCE_API_VERSION,
                "generated_at": timezone.now().isoformat(),
                "authorization": {
                    "identity": identity.username,
                    "scope": "scheduled tasks visible to the configured Tasks principal",
                },
                "window": (
                    {"start": start.isoformat(), "end": end.isoformat()}
                    if start is not None
                    else None
                ),
                "returned": len(tasks),
                "tasks": [_serialize_task(request, task) for task in tasks],
            }
        )
    )


def calendar_task_projection_detail(request, task_id: int):
    """Read one active scheduled task projection after current authorization."""
    _, identity, error = _authorize_request(request)
    if error is not None:
        return error
    if request.method != "GET":
        return _method_not_allowed(["GET"])

    task = _scheduled_visible_tasks(identity).filter(pk=task_id).first()
    if task is None:
        return _not_found()

    return _private(
        JsonResponse(
            {
                "schema": SCHEMA,
                "version": SOURCE_API_VERSION,
                "task": _serialize_task(request, task),
            }
        )
    )


def _priority_from_payload(value):
    if value is None:
        return Task.Priority.P3_STANDARD
    if isinstance(value, bool):
        raise ValueError("priority must be a valid GoreeCloud priority integer.")
    try:
        priority = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "priority must be a valid GoreeCloud priority integer."
        ) from exc
    if priority not in {choice.value for choice in Task.Priority}:
        raise ValueError("priority must be a valid GoreeCloud priority integer.")
    return priority


def _project_from_payload(identity, value):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("project_id must be a positive integer or null.")
    try:
        project_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("project_id must be a positive integer or null.") from exc
    if project_id <= 0:
        raise ValueError("project_id must be a positive integer or null.")

    project = Project.objects.filter(pk=project_id, is_archived=False).first()
    if project is None or not project.can_edit(identity):
        return False
    return project


@csrf_exempt
def calendar_task_create(request):
    """Create a deliberately limited task from authenticated Calendar context."""
    _, identity, error = _authorize_request(request)
    if error is not None:
        return error
    if request.method != "POST":
        return _method_not_allowed(["POST"])

    try:
        payload = _read_json_object(
            request,
            allowed_fields={"title", "due_at", "priority", "project_id"},
        )
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title is required.")
        title = title.strip()
        max_length = Task._meta.get_field("title").max_length
        if len(title) > max_length:
            raise ValueError(f"title cannot exceed {max_length} characters.")

        due_at = _parse_timestamp(payload.get("due_at"), field="due_at")
        priority = _priority_from_payload(payload.get("priority"))
        project = _project_from_payload(identity, payload.get("project_id"))
        if project is False:
            return _not_found()
    except ValueError as exc:
        return _bad_request(str(exc))

    task = Task(
        title=title,
        creator=identity,
        assignee=identity,
        project=project,
        priority=priority,
        status=Task.Status.READY,
        due_at=due_at,
        recurrence=Task.Recurrence.NONE,
    )
    try:
        with transaction.atomic():
            task.save()
            record_activity(
                actor=identity,
                kind=ActivityEvent.Kind.TASK_CREATED,
                summary="Created task from GoreeCloud Calendar",
                task=task,
                details={
                    "source": "goreecloud-calendar",
                    "fields": ["title", "due_at", "priority", "project"],
                },
            )
    except ValidationError as exc:
        return _bad_request("Task validation failed.", errors=exc.message_dict)

    return _private(
        JsonResponse(
            {
                "schema": SCHEMA,
                "version": SOURCE_API_VERSION,
                "task": _serialize_task(request, task),
            },
            status=201,
        )
    )


@csrf_exempt
def calendar_task_reschedule(request, task_id: int):
    """Move one editable task after an optimistic revision check."""
    _, identity, error = _authorize_request(request)
    if error is not None:
        return error
    if request.method != "POST":
        return _method_not_allowed(["POST"])

    try:
        payload = _read_json_object(
            request,
            allowed_fields={"due_at", "expected_updated_at"},
        )
        due_at = _parse_timestamp(payload.get("due_at"), field="due_at")
        expected_revision = _parse_timestamp(
            payload.get("expected_updated_at"),
            field="expected_updated_at",
        )
    except ValueError as exc:
        return _bad_request(str(exc))

    with transaction.atomic():
        task = (
            Task.objects.select_for_update()
            .exclude(status__in=TERMINAL_STATUSES)
            .select_related("project")
            .filter(pk=task_id)
            .first()
        )
        if task is None:
            return _not_found()

        if not Task.objects.editable_by(identity).filter(pk=task.pk).exists():
            return _not_found()

        if task.updated_at != expected_revision:
            return _bad_request(
                "Task revision conflict.",
                status=409,
                current_revision=task.updated_at.isoformat(),
            )

        task.due_at = due_at
        try:
            task.save(update_fields=["due_at", "updated_at"])
        except ValidationError as exc:
            return _bad_request("Task validation failed.", errors=exc.message_dict)

        record_activity(
            actor=identity,
            kind=ActivityEvent.Kind.TASK_UPDATED,
            summary="Rescheduled task from GoreeCloud Calendar",
            task=task,
            details={
                "source": "goreecloud-calendar",
                "fields": ["due_at"],
            },
        )

    return _private(
        JsonResponse(
            {
                "schema": SCHEMA,
                "version": SOURCE_API_VERSION,
                "task": _serialize_task(request, task),
            }
        )
    )
