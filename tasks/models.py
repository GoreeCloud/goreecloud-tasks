"""Core task model and authorization-aware query helpers."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from projects.models import Project, ProjectMembership


class TaskQuerySet(models.QuerySet):
    """Query helpers that make the user-content boundary explicit."""

    def visible_to(self, user):
        """Return tasks the user may read through the normal application."""
        if not user or not user.is_authenticated:
            return self.none()

        return self.filter(
            Q(project__isnull=True, creator=user)
            | Q(project__owner=user)
            | Q(
                project__visibility=Project.Visibility.SHARED,
                project__memberships__user=user,
                project__memberships__is_active=True,
            )
        ).distinct()

    def editable_by(self, user):
        """Return tasks the user may edit through the normal application."""
        if not user or not user.is_authenticated:
            return self.none()

        return self.filter(
            Q(project__isnull=True, creator=user)
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


class Task(models.Model):
    """A personal or project-scoped item of work."""

    class Priority(models.IntegerChoices):
        P0_CRITICAL = 0, "P0 — Critical"
        P1_URGENT = 1, "P1 — Urgent"
        P2_HIGH = 2, "P2 — High"
        P3_STANDARD = 3, "P3 — Standard"
        P4_LOW = 4, "P4 — Low"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        READY = "ready", "Ready"
        IN_PROGRESS = "in_progress", "In Progress"
        BLOCKED = "blocked", "Blocked"
        DELAYED = "delayed", "Delayed"
        WAITING = "waiting", "Waiting"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tasks",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_tasks",
        blank=True,
        null=True,
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="tasks",
        blank=True,
        null=True,
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="subtasks",
        blank=True,
        null=True,
    )
    labels = models.ManyToManyField(
        "labels.Label",
        related_name="tasks",
        blank=True,
    )
    priority = models.PositiveSmallIntegerField(
        choices=Priority.choices,
        default=Priority.P3_STANDARD,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
    )
    due_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    # GoreeCloud operational metadata remains optional so ordinary personal,
    # family, and collaborative tasks are never forced into infrastructure fields.
    is_goreecloud_work = models.BooleanField(default=False)
    assigned_system = models.CharField(max_length=200, blank=True)
    assigned_service = models.CharField(max_length=200, blank=True)
    environment = models.CharField(max_length=200, blank=True)
    workload_category = models.CharField(max_length=120, blank=True)
    blocker = models.TextField(blank=True)
    resume_condition = models.TextField(blank=True)
    backup_prerequisite = models.BooleanField(default=False)
    recovery_requirement = models.BooleanField(default=False)
    validation_requirement = models.BooleanField(default=False)
    documentation_requirement = models.BooleanField(default=False)
    related_change_record = models.CharField(max_length=500, blank=True)
    related_documentation = models.CharField(max_length=500, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TaskQuerySet.as_manager()

    class Meta:
        ordering = ("priority", "created_at", "id")

    def __str__(self):
        return self.title

    def _previous_project_actor_state(self):
        """Return persisted project, creator, and assignee for an existing task."""
        if not self.pk:
            return None
        return (
            type(self).objects.filter(pk=self.pk)
            .values("project_id", "creator_id", "assignee_id")
            .first()
        )

    def _validate_parent(self):
        """Keep subtasks inside the same authorization scope and prevent cycles."""
        if not self.parent_id:
            return

        if self.pk and self.parent_id == self.pk:
            raise ValidationError({"parent": "A task cannot be its own parent."})

        parent = self.parent
        if parent.project_id != self.project_id:
            raise ValidationError(
                {"parent": "A subtask must belong to the same project as its parent."}
            )

        if self.project_id is None and parent.creator_id != self.creator_id:
            raise ValidationError(
                {"parent": "A private subtask must belong to the same user as its parent."}
            )

        seen = {self.pk} if self.pk else set()
        ancestor = parent
        while ancestor is not None:
            if ancestor.pk in seen:
                raise ValidationError({"parent": "Subtask relationships cannot contain a cycle."})
            seen.add(ancestor.pk)
            ancestor = ancestor.parent

    def clean(self):
        """Enforce ownership, assignment, and subtask boundaries at model level."""
        super().clean()

        previous = self._previous_project_actor_state()

        if self.project_id:
            retains_previous_creator = bool(
                previous
                and previous["project_id"] == self.project_id
                and previous["creator_id"] == self.creator_id
            )
            if (
                self.creator_id
                and not self.project.can_edit(self.creator)
                and not retains_previous_creator
            ):
                raise ValidationError(
                    {"creator": "The creator must be allowed to edit this project."}
                )

            if self.assignee_id:
                assignee_is_owner = self.project.owner_id == self.assignee_id
                assignee_is_active_member = self.project.memberships.filter(
                    user_id=self.assignee_id,
                    is_active=True,
                ).exists()
                retains_previous_assignee = bool(
                    previous
                    and previous["project_id"] == self.project_id
                    and previous["assignee_id"] == self.assignee_id
                )
                if not (
                    assignee_is_owner
                    or assignee_is_active_member
                    or retains_previous_assignee
                ):
                    raise ValidationError(
                        {
                            "assignee": (
                                "The assignee must own or actively belong to the project."
                            )
                        }
                    )
        elif (
            self.assignee_id
            and self.creator_id
            and self.assignee_id != self.creator_id
        ):
            raise ValidationError(
                {"assignee": "A private personal task can only be assigned to its creator."}
            )

        self._validate_parent()

    def save(self, *args, **kwargs):
        """Keep completion metadata synchronized and validate the object."""
        if self.status == self.Status.COMPLETED and self.completed_at is None:
            self.completed_at = timezone.now()
        elif self.status != self.Status.COMPLETED:
            self.completed_at = None

        self.full_clean()
        return super().save(*args, **kwargs)
