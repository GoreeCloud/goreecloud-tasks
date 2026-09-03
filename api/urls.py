"""Versioned application API routes."""

from django.urls import path

from .calendar_views import (
    calendar_task_create,
    calendar_task_projection_detail,
    calendar_task_projections,
    calendar_task_reschedule,
)
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
        "calendar/task-projections/<int:task_id>/",
        calendar_task_projection_detail,
        name="calendar-task-projection-detail",
    ),
    path(
        "calendar/tasks/",
        calendar_task_create,
        name="calendar-task-create",
    ),
    path(
        "calendar/tasks/<int:task_id>/reschedule/",
        calendar_task_reschedule,
        name="calendar-task-reschedule",
    ),
]
