"""User-facing data portability workflows."""

import json

from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify

from projects.models import Project

from .exporters import build_project_archive, build_user_archive


def _json_download(payload, filename):
    response = HttpResponse(
        json.dumps(payload, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False) + "\n",
        content_type="application/json; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def index(request):
    owned_projects = Project.objects.filter(owner=request.user).order_by("name", "id")
    return render(request, "portability/index.html", {"owned_projects": owned_projects})


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
