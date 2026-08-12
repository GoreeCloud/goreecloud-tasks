"""Versioned application API routes."""

from django.urls import path

from .views import manager_operational_tasks

app_name = "api"

urlpatterns = [
    path(
        "manager/operational-tasks/",
        manager_operational_tasks,
        name="manager-operational-tasks",
    ),
]
