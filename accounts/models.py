"""User identity and preferences for GoreeCloud Tasks."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Individual GoreeCloud Tasks identity.

    A custom user model exists from the first migration so account behavior can
    evolve without a disruptive user-table replacement later.
    """

    display_name = models.CharField(max_length=150, blank=True)
    timezone = models.CharField(max_length=64, default="America/Chicago")

    @property
    def preferred_name(self):
        """Return the user's configured display name or a safe account fallback."""
        return self.display_name.strip() or self.get_full_name().strip() or self.username
