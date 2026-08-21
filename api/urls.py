"""Versioned application API routes."""

from django.urls import path

from .calendar_views import calendar_task_projections
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
]
