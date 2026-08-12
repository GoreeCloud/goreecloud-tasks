"""Project and membership URL configuration."""

from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.project_list, name="list"),
    path("new/", views.project_create, name="create"),
    path("<int:pk>/", views.project_detail, name="detail"),
    path("<int:pk>/edit/", views.project_edit, name="edit"),
    path("<int:pk>/members/add/", views.membership_add, name="membership_add"),
    path(
        "<int:pk>/members/<int:membership_pk>/role/",
        views.membership_role_update,
        name="membership_role_update",
    ),
    path(
        "<int:pk>/members/<int:membership_pk>/remove/",
        views.membership_remove,
        name="membership_remove",
    ),
]
