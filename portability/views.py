"""User-facing data portability workflows."""

import json

from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from imports.executor import ImportExecutionError, execute_import
from imports.todoist import TodoistCsvError, TodoistImportAdapter
from projects.models import Project

from .exporters import build_project_archive, build_user_archive
from .restorers import ArchiveRestoreError, restore_user_archive as restore_archive_data

MAX_RESTORE_ARCHIVE_BYTES = 25 * 1024 * 1024
MAX_PROVIDER_IMPORT_BYTES = 25 * 1024 * 1024


def _json_download(payload, filename):
    response = HttpResponse(
        json.dumps(payload, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False) + "\n",
        content_type="application/json; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _index_context(request, **extra):
    context = {
        "owned_projects": Project.objects.filter(owner=request.user).order_by("name", "id"),
    }
    context.update(extra)
    return context


def _render_index(request, **extra):
    response = render(request, "portability/index.html", _index_context(request, **extra))
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def index(request):
    return _render_index(request)


@login_required
def user_export(request):
    payload = build_user_archive(request.user)
    username = slugify(request.user.username) or f"user-{request.user.pk}"
    return _json_download(payload, f"goreecloud-tasks-{username}.json")


@login_required
def project_export(request, pk):
    project = get_object_or_404(
        Project.objects.select_related("owner"),
        pk=pk,
        owner=request.user,
    )
    payload = build_project_archive(project)
    project_name = slugify(project.name) or f"project-{project.pk}"
    return _json_download(payload, f"goreecloud-tasks-{project_name}.json")


@login_required
@require_POST
def restore_user_archive(request):
    """Restore one complete user archive after explicit confirmation and validation."""
    if request.POST.get("confirm_restore") != "yes":
        return _render_index(
            request,
            restore_error="Confirm the recovery acknowledgement before restoring an archive.",
        )

    archive = request.FILES.get("archive")
    if archive is None:
        return _render_index(request, restore_error="Choose a GoreeCloud Tasks JSON archive.")
    if archive.size > MAX_RESTORE_ARCHIVE_BYTES:
        return _render_index(
            request,
            restore_error="The selected archive exceeds the 25 MiB recovery-upload limit.",
        )

    try:
        raw = archive.read(MAX_RESTORE_ARCHIVE_BYTES + 1)
        if len(raw) > MAX_RESTORE_ARCHIVE_BYTES:
            raise ArchiveRestoreError(
                "The selected archive exceeds the 25 MiB recovery-upload limit."
            )
        payload = json.loads(raw.decode("utf-8"))
        summary = restore_archive_data(payload, user=request.user)
    except UnicodeDecodeError:
        return _render_index(
            request,
            restore_error="The archive must be UTF-8 encoded JSON.",
        )
    except json.JSONDecodeError:
        return _render_index(
            request,
            restore_error="The selected file does not contain valid JSON.",
        )
    except ArchiveRestoreError as exc:
        return _render_index(request, restore_error=str(exc))

    return _render_index(request, restore_summary=summary)


@login_required
@require_POST
def import_todoist_csv(request):
    """Import one verified-format Todoist project CSV as a private project."""
    project_name = request.POST.get("project_name", "").strip()
    upload = request.FILES.get("todoist_csv")
    if not project_name:
        return _render_index(
            request,
            todoist_error="Enter the private GoreeCloud project name for this Todoist CSV.",
        )
    if upload is None:
        return _render_index(request, todoist_error="Choose a Todoist project CSV file.")
    if upload.size > MAX_PROVIDER_IMPORT_BYTES:
        return _render_index(
            request,
            todoist_error="The selected CSV exceeds the 25 MiB import-upload limit.",
        )

    try:
        raw = upload.read(MAX_PROVIDER_IMPORT_BYTES + 1)
        if len(raw) > MAX_PROVIDER_IMPORT_BYTES:
            raise TodoistCsvError(
                "The selected CSV exceeds the 25 MiB import-upload limit."
            )
        text = raw.decode("utf-8-sig")
        bundle = TodoistImportAdapter().normalize_csv(
            text,
            project_name=project_name,
        )
        summary = execute_import(user=request.user, bundle=bundle)
    except UnicodeDecodeError:
        return _render_index(
            request,
            todoist_error="Todoist CSV files must be UTF-8 encoded.",
        )
    except (TodoistCsvError, ImportExecutionError) as exc:
        return _render_index(request, todoist_error=str(exc))

    return _render_index(
        request,
        todoist_summary=summary,
        todoist_project_name=project_name,
    )
