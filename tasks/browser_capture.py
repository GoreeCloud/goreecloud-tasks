"""Secure GoreeCloud Browser handoff for explicit user-confirmed task capture."""

import json
from urllib.parse import urlsplit

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse, QueryDict
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from collaboration.models import ActivityEvent
from collaboration.services import record_activity

from .forms import TaskForm
from .models import Task

MAX_REQUEST_BYTES = 24 * 1024
MAX_TITLE_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 8192
MAX_URL_LENGTH = 8192
ALLOWED_KINDS = {"selection", "link"}
CAPTURE_CSP = (
    "default-src 'none'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "base-uri 'none'; "
    "frame-ancestors 'none'"
)


def _secure_response(response: HttpResponse) -> HttpResponse:
    response["Content-Security-Policy"] = CAPTURE_CSP
    response["Cache-Control"] = "no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["Referrer-Policy"] = "no-referrer"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "DENY"
    response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


def _error(message: str, status: int = 400) -> JsonResponse:
    return _secure_response(JsonResponse({"ok": False, "error": message}, status=status))


def _clean_text(value, *, maximum: int, field: str, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field} is required")
    if len(value) > maximum:
        raise ValueError(f"{field} is too long")
    return value


def _clean_source_url(value) -> str:
    value = _clean_text(value, maximum=MAX_URL_LENGTH, field="source_url")
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError as error:
        raise ValueError("source_url is invalid") from error
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("source_url must use http or https")
    if parsed.username or parsed.password:
        raise ValueError("source_url must not contain embedded credentials")
    return value


def _parse_payload(request) -> dict:
    if len(request.body) > MAX_REQUEST_BYTES:
        raise ValueError("capture request is too large")
    if request.content_type != "application/json":
        raise ValueError("capture request must use application/json")
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("capture request contains invalid JSON") from error
    if not isinstance(payload, dict):
        raise ValueError("capture request must be a JSON object")

    kind = payload.get("kind")
    if kind not in ALLOWED_KINDS:
        raise ValueError("capture kind is invalid")

    return {
        "kind": kind,
        "title": _clean_text(
            payload.get("title"),
            maximum=MAX_TITLE_LENGTH,
            field="title",
            required=True,
        ),
        "description": _clean_text(
            payload.get("description"),
            maximum=MAX_DESCRIPTION_LENGTH,
            field="description",
        ),
        "source_url": _clean_source_url(payload.get("source_url")),
    }


def _task_form_data(payload: dict, user) -> QueryDict:
    """Build the narrow personal-task submission through the normal TaskForm."""
    data = QueryDict("", mutable=True)
    data["title"] = payload["title"]
    data["description"] = payload["description"]
    data["project"] = ""
    data["assignee"] = str(user.pk)
    data["priority"] = str(Task.Priority.P3_STANDARD)
    data["status"] = Task.Status.READY
    data["due_at"] = ""
    data.setlist("labels", [])
    return data


@login_required
@require_http_methods(["GET", "POST"])
def browser_capture(request):
    """Receive a Browser handoff without Browser-managed Tasks credentials."""
    if request.GET:
        return _error("capture URL must not use query parameters", status=404)

    if request.method == "GET":
        return _secure_response(render(request, "tasks/browser_capture.html"))

    try:
        payload = _parse_payload(request)
    except ValueError as error:
        return _error(str(error))

    form = TaskForm(_task_form_data(payload, request.user), user=request.user)
    if not form.is_valid():
        return _secure_response(
            JsonResponse(
                {
                    "ok": False,
                    "error": "task validation failed",
                    "fields": form.errors.get_json_data(),
                },
                status=422,
            )
        )

    with transaction.atomic():
        task = form.save(commit=False)
        task.creator = request.user
        task.assignee = request.user
        task.status = Task.Status.READY
        task.save()
        form.save_m2m()
        record_activity(
            actor=request.user,
            kind=ActivityEvent.Kind.TASK_CREATED,
            summary="created the task",
            task=task,
            details={
                "source": "browser_capture",
                "capture_kind": payload["kind"],
                "source_url_present": bool(payload["source_url"]),
            },
        )

    return _secure_response(
        JsonResponse({"ok": True, "task_id": task.pk}, status=201)
    )
