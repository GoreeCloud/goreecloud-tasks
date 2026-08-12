"""Task application URL configuration."""

from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("today/", views.today, name="today"),
    path("upcoming/", views.upcoming, name="upcoming"),
    path("tasks/add/", views.quick_add, name="quick_add"),
    path("tasks/new/", views.task_create, name="task_create"),
    path("tasks/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path(
        "tasks/<int:pk>/toggle-complete/",
        views.task_toggle_complete,
        name="task_toggle_complete",
    ),
    path("tasks/<int:pk>/delete/", views.task_delete, name="task_delete"),
]
