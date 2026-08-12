"""Projects, memberships, and project-scoped authorization."""

from django.conf import settings
from django.db import models


class Project(models.Model):
    """A private or explicitly shared collection of tasks."""

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        SHARED = "shared", "Shared"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_task_projects",
    )
    name = models.CharField(max_length=200)
    visibility = models.CharField(
        max_length=16,
        choices=Visibility.choices,
        default=Visibility.PRIVATE,
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="ProjectMembership",
        related_name="task_projects",
    )
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "name"),
                name="unique_project_name_per_owner",
            )
        ]
        ordering = ("name", "id")

    def __str__(self):
        return self.name

    def active_membership_for(self, user):
        """Return an active explicit membership for a user, if one exists."""
        if not user or not user.is_authenticated:
            return None
        return self.memberships.filter(user=user, is_active=True).first()

    def can_view(self, user):
        """Return whether the user may read project task content."""
        if not user or not user.is_authenticated:
            return False
        if self.owner_id == user.id:
            return True
        return (
            self.visibility == self.Visibility.SHARED
            and self.active_membership_for(user) is not None
        )

    def can_edit(self, user):
        """Return whether the user may change project task content."""
        if not user or not user.is_authenticated:
            return False
        if self.owner_id == user.id:
            return True
        membership = self.active_membership_for(user)
        return (
            self.visibility == self.Visibility.SHARED
            and membership is not None
            and membership.role
            in {
                ProjectMembership.Role.MANAGER,
                ProjectMembership.Role.MEMBER,
            }
        )


class ProjectMembership(models.Model):
    """Explicit, revocable access to a shared project."""

    class Role(models.TextChoices):
        MANAGER = "manager", "Manager"
        MEMBER = "member", "Member"
        VIEWER = "viewer", "Viewer"

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="task_project_memberships",
    )
    role = models.CharField(
        max_length=16,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("project", "user"),
                name="unique_project_membership",
            )
        ]

    def __str__(self):
        return f"{self.project} — {self.user} ({self.get_role_display()})"
