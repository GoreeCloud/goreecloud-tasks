"""Forms for personal and explicitly shared project labels."""

from django import forms
from django.db.models import Q

from projects.models import Project, ProjectMembership

from .models import Label


def editable_projects_for(user):
    """Return projects in which the user may manage project labels."""
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
        .order_by("name", "id")
    )


class LabelCreateForm(forms.ModelForm):
    """Create either a private personal label or one project-scoped label."""

    class Meta:
        model = Label
        fields = ("name", "project")
        widgets = {
            "name": forms.TextInput(
                attrs={"placeholder": "Label name", "autocomplete": "off"}
            )
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["project"].queryset = editable_projects_for(user)
        self.fields["project"].required = False
        self.fields["project"].empty_label = "Personal label"
        self.fields["project"].help_text = (
            "Personal labels remain private. Project labels are visible only to authorized project readers."
        )

    def clean_name(self):
        return self.cleaned_data["name"].strip()

    def clean(self):
        cleaned = super().clean()
        name = cleaned.get("name")
        project = cleaned.get("project")
        if not name:
            return cleaned

        if project is None:
            duplicate = Label.objects.filter(
                owner=self.user,
                project__isnull=True,
                name=name,
            ).exists()
        else:
            duplicate = Label.objects.filter(project=project, name=name).exists()

        if duplicate:
            self.add_error("name", "A label with this name already exists in this scope.")
        return cleaned
