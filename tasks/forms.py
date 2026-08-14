"""Forms for private and explicitly shared GoreeCloud Tasks work."""

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from labels.models import Label
from projects.models import Project, ProjectMembership

from .models import Task


ASSIGNABLE_PROJECT_ROLES = (
    ProjectMembership.Role.MANAGER,
    ProjectMembership.Role.MEMBER,
)


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
                memberships__role__in=ASSIGNABLE_PROJECT_ROLES,
            )
        )
        .distinct()
    )


def assignable_users_for(user, projects):
    """Return active users eligible to receive work in editable projects."""
    User = get_user_model()
    if not user or not user.is_authenticated:
        return User.objects.none()

    return (
        User.objects.filter(is_active=True)
        .filter(
            Q(pk=user.pk)
            | Q(owned_task_projects__in=projects)
            | Q(
                task_project_memberships__project__in=projects,
                task_project_memberships__is_active=True,
                task_project_memberships__role__in=ASSIGNABLE_PROJECT_ROLES,
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
            "labels",
            "is_goreecloud_work",
            "assigned_system",
            "assigned_service",
            "environment",
            "workload_category",
            "blocker",
            "resume_condition",
            "backup_prerequisite",
            "recovery_requirement",
            "validation_requirement",
            "documentation_requirement",
            "related_change_record",
            "related_documentation",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "labels": forms.CheckboxSelectMultiple,
            "blocker": forms.Textarea(attrs={"rows": 3}),
            "resume_condition": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "is_goreecloud_work": "GoreeCloud operational work",
            "environment": "Environment or virtual machine",
            "backup_prerequisite": "Backup prerequisite required",
            "recovery_requirement": "Recovery requirement applies",
            "validation_requirement": "Validation required",
            "documentation_requirement": "Documentation required",
            "related_documentation": "Related GoreeCloud documentation",
        }
        help_texts = {
            "labels": (
                "Personal tasks use your private labels. Project tasks use only labels scoped to that project."
            ),
            "is_goreecloud_work": (
                "Enable this when the task represents GoreeCloud infrastructure or operational work."
            ),
            "related_change_record": (
                "Reference a related change record without copying sensitive change content into the task."
            ),
            "related_documentation": (
                "Reference the authoritative GoreeCloud document or record when applicable."
            ),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        projects = editable_projects_for(user)
        self.fields["project"].queryset = projects
        self.fields["project"].required = False
        self.fields["project"].empty_label = "Inbox"

        assignees = assignable_users_for(user, projects)
        if self.instance and self.instance.pk and self.instance.assignee_id:
            User = get_user_model()
            assignees = (
                User.objects.filter(
                    Q(pk__in=assignees.values("pk")) | Q(pk=self.instance.assignee_id)
                )
                .distinct()
                .order_by("username")
            )
        self.fields["assignee"].queryset = assignees
        self.fields["assignee"].required = False

        selected_project = self._selected_project(projects)
        if selected_project is None:
            label_queryset = Label.objects.filter(
                owner=user,
                project__isnull=True,
            )
        else:
            label_queryset = Label.objects.filter(project=selected_project)
        self.fields["labels"].queryset = label_queryset.order_by("name", "id")
        self.fields["labels"].required = False

    def _selected_project(self, projects):
        """Resolve the editor's current project without broadening project access."""
        project_id = None
        if self.is_bound:
            project_id = self.data.get(self.add_prefix("project"))
        elif self.instance and self.instance.pk:
            project_id = self.instance.project_id
        else:
            initial_project = self.initial.get("project")
            project_id = getattr(initial_project, "pk", initial_project)

        if not project_id:
            return None
        return projects.filter(pk=project_id).first()

    def clean(self):
        """Validate assignment and labels against the selected task context."""
        cleaned = super().clean()
        project = cleaned.get("project")
        assignee = cleaned.get("assignee")
        labels = cleaned.get("labels")

        if project is None:
            if assignee is not None and assignee.pk != self.user.pk:
                self.add_error(
                    "assignee",
                    "A private personal task can only be assigned to its creator.",
                )
            if labels is not None and labels.exclude(
                owner=self.user,
                project__isnull=True,
            ).exists():
                self.add_error("labels", "Private tasks can only use your personal labels.")
            return cleaned

        if not project.can_edit(self.user):
            self.add_error("project", "You do not have permission to edit this project.")
            return cleaned

        if labels is not None and labels.exclude(project=project).exists():
            self.add_error("labels", "Project tasks can only use labels from that project.")

        if assignee is not None:
            assignee_can_receive_work = assignee.is_active and project.can_edit(assignee)
            retains_previous_assignee = bool(
                self.instance
                and self.instance.pk
                and self.instance.project_id == project.pk
                and self.instance.assignee_id == assignee.pk
            )
            if not (assignee_can_receive_work or retains_previous_assignee):
                self.add_error(
                    "assignee",
                    "The assignee must have an active account and be the project owner or an active Manager or Member.",
                )

        return cleaned


class SubtaskForm(forms.ModelForm):
    """Focused subtask capture that inherits the parent's authorization scope."""

    due_at = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=LocalDateTimeInput(attrs={"aria-label": "Subtask due date and time"}),
    )

    class Meta:
        model = Task
        fields = ("title", "priority", "due_at")
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "Add a subtask…",
                    "autocomplete": "off",
                    "aria-label": "Subtask title",
                }
            )
        }
