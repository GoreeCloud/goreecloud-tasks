"""Notification and reminder URL configuration."""

from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("settings/", views.settings_view, name="settings"),
    path(
        "tasks/<int:task_pk>/reminders/add/",
        views.reminder_add,
        name="reminder_add",
    ),
    path(
        "reminders/<int:pk>/cancel/",
        views.reminder_cancel,
        name="reminder_cancel",
    ),
]
