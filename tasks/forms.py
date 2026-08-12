"""Forms for private and explicitly shared GoreeCloud Tasks work."""

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from projects.models import Project, ProjectMembership

from .models import Task


def editable_projects_for(user):
    """Return non-archived projects the user may modify."""
    if not user or not user.is_authenticated:
        return Project.objects.none()

    return (
        Project.objects.filter(is_archived=False)
        .filter(
            Q(owner=user)
            | Q(
                visibility=Project.Visibility.SHARED,
                memberships__user=user,
                memberships__is_active=True,
                memberships__role__in=[
                    ProjectMembership.Role.MANAGER,
                    ProjectMembership.Role.MEMBER,
                ],
            )
        )
        .distinct()
    )


def assignable_users_for(user, projects):
    """Return users visible through projects the current user may edit."""
    User = get_user_model()
    if not user or not user.is_authenticated:
        return User.objects.none()

    return (
        User.objects.filter(
            Q(pk=user.pk)
            | Q(owned_task_projects__in=projects)
            | Q(
                task_project_memberships__project__in=projects,
                task_project_memberships__is_active=True,
            )
        )
        .distinct()
        .order_by("username")
    )


class LocalDateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("format", "%Y-%m-%dT%H:%M")
        super().__init__(*args, **kwargs)


class QuickAddForm(forms.ModelForm):
    """Low-friction task capture with an optional editable project target."""

    due_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=LocalDateTimeInput(attrs={"aria-label": "Due date and time"}),
    )

    class Meta:
        model = Task
        fields = ("title", "project", "priority", "due_at")
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "Add a task…",
                    "autocomplete": "off",
                    "aria-label": "Task title",
                }
            ),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["project"].queryset = editable_projects_for(user)
        self.fields["project"].required = False
        self.fields["project"].empty_label = "Inbox"


class TaskForm(forms.ModelForm):
    """Full task editor constrained to the current user's authorization scope."""

    due_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=LocalDateTimeInput,
    )

    class Meta:
        model = Task
        fields = (
            "title",
            "description",
            "project",
            "assignee",
            "priority",
            "status",
            "due_at",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        projects = editable_projects_for(user)
        self.fields["project"].queryset = projects
        self.fields["project"].required = False
        self.fields["project"].empty_label = "Inbox"
        self.fields["assignee"].queryset = assignable_users_for(user, projects)
        self.fields["assignee"].required = False

    def clean(self):
        """Validate assignment against the selected task context before saving."""
        cleaned = super().clean()
        project = cleaned.get("project")
        assignee = cleaned.get("assignee")

        if project is None:
            if assignee is not None and assignee.pk != self.user.pk:
                self.add_error(
                    "assignee",
                    "A private personal task can only be assigned to its creator.",
                )
            return cleaned

        if not project.can_edit(self.user):
            self.add_error("project", "You do not have permission to edit this project.")
            return cleaned

        if assignee is not None:
            assignee_is_owner = project.owner_id == assignee.pk
            assignee_is_member = project.memberships.filter(
                user=assignee,
                is_active=True,
            ).exists()
            if not (assignee_is_owner or assignee_is_member):
                self.add_error(
                    "assignee",
                    "The assignee must own or actively belong to the selected project.",
                )

        return cleaned
