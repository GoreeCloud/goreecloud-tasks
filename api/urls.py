"""Versioned application API routes."""

from django.urls import path

from .calendar_views import calendar_task_projections
from .client_views import client_task_detail, client_tasks
from .views import manager_operational_tasks

app_name = "api"

urlpatterns = [
    path(
        "manager/operational-tasks/",
        manager_operational_tasks,
        name="manager-operational-tasks",
    ),
    path(
        "calendar/task-projections/",
        calendar_task_projections,
        name="calendar-task-projections",
    ),
    path(
        "client/tasks/",
        client_tasks,
        name="client-tasks",
    ),
    path(
        "client/tasks/<int:task_id>/",
        client_task_detail,
        name="client-task-detail",
    ),
]
