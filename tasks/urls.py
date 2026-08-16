"""Task application URL configuration."""

from django.urls import path

from collaboration import views as collaboration_views

from . import overdue as overdue_views
from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("today/", views.today, name="today"),
    path("overdue/", overdue_views.overdue, name="overdue"),
    path("upcoming/", views.upcoming, name="upcoming"),
    path("search/", views.search, name="search"),
    path("tasks/add/", views.quick_add, name="quick_add"),
    path("tasks/new/", views.task_create, name="task_create"),
    path("tasks/<int:pk>/", views.task_detail, name="task_detail"),
    path("tasks/<int:pk>/edit/", views.task_edit, name="task_edit"),
    path(
        "tasks/<int:task_pk>/comments/add/",
        collaboration_views.comment_add,
        name="task_comment_add",
    ),
    path(
        "tasks/<int:parent_pk>/subtasks/add/",
        views.subtask_add,
        name="subtask_add",
    ),
    path(
        "tasks/<int:pk>/toggle-complete/",
        views.task_toggle_complete,
        name="task_toggle_complete",
    ),
    path("tasks/<int:pk>/delete/", views.task_delete, name="task_delete"),
]
