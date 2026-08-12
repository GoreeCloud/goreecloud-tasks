"""Label URL configuration."""

from django.urls import path

from . import views

app_name = "labels"

urlpatterns = [
    path("", views.label_list, name="list"),
    path("<int:pk>/delete/", views.label_delete, name="delete"),
]
