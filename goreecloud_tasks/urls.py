"""Root URL configuration for GoreeCloud Tasks."""

from django.contrib import admin
from django.urls import include, path

from .views import health

urlpatterns = [
    path("health/", health, name="health"),
    path("api/v1/", include("api.urls")),
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("projects/", include("projects.urls")),
    path("labels/", include("labels.urls")),
    path("data/", include("portability.urls")),
    path("notifications/", include("notifications.urls")),
    path("", include("tasks.urls")),
]
