"""Data portability URL configuration."""

from django.urls import path

from . import views

app_name = "portability"

urlpatterns = [
    path("", views.index, name="index"),
    path("export/me/", views.user_export, name="user_export"),
    path("export/projects/<int:pk>/", views.project_export, name="project_export"),
    path("restore/me/", views.restore_user_archive, name="restore_user_archive"),
]
