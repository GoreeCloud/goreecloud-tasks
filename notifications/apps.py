"""Django application configuration for user-specific reminders and notifications."""

from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"

    def ready(self):
        """Register reminder lifecycle hooks after the application registry is ready."""
        from . import signals  # noqa: F401
