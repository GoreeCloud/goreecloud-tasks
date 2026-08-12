"""Personal and project-scoped labels with explicit authorization boundaries."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from projects.models import Project, ProjectMembership


class LabelQuerySet(models.QuerySet):
    """Authorization-aware label query helpers."""

    def visible_to(self, user):
        """Return labels the user may read through normal application access."""
        if not user or not user.is_authenticated:
            return self.none()

        return self.filter(
            Q(project__isnull=True, owner=user)
            | Q(project__owner=user)
            | Q(
                project__visibility=Project.Visibility.SHARED,
                project__memberships__user=user,
                project__memberships__is_active=True,
            )
        ).distinct()

    def editable_by(self, user):
        """Return labels the user may create, rename, or delete in context."""
        if not user or not user.is_authenticated:
            return self.none()

        return self.filter(
            Q(project__isnull=True, owner=user)
            | Q(project__owner=user)
            | Q(
                project__visibility=Project.Visibility.SHARED,
                project__memberships__user=user,
                project__memberships__is_active=True,
                project__memberships__role__in=[
                    ProjectMembership.Role.MANAGER,
                    ProjectMembership.Role.MEMBER,
                ],
            )
        ).distinct()


class Label(models.Model):
    """A personal label or a label shared only inside one project."""

    name = models.CharField(max_length=100)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="task_labels",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="labels",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = LabelQuerySet.as_manager()

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("owner", "name"),
                condition=Q(project__isnull=True),
                name="unique_personal_label_name_per_owner",
            ),
            models.UniqueConstraint(
                fields=("project", "name"),
                condition=Q(project__isnull=False),
                name="unique_project_label_name",
            ),
        ]

    def __str__(self):
        if self.project_id:
            return f"{self.name} — {self.project}"
        return self.name

    def clean(self):
        """Normalize the name and prevent creating labels outside owner access."""
        super().clean()
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": "A label name is required."})

        if self.project_id and self.owner_id and not self.project.can_edit(self.owner):
            raise ValidationError(
                {"project": "The label owner must be allowed to edit this project."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
