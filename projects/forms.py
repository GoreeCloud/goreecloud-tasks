"""Project settings and explicit membership administration forms."""

from django import forms
from django.contrib.auth import get_user_model

from .models import Project, ProjectMembership


class ProjectForm(forms.ModelForm):
    """Owner-controlled project settings."""

    class Meta:
        model = Project
        fields = ("name", "visibility")
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "autocomplete": "off",
                    "placeholder": "Project name",
                }
            ),
        }


class MembershipInviteForm(forms.Form):
    """Add an existing active account by exact username without enumerating users."""

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "placeholder": "Exact username",
            }
        ),
        help_text="Enter the exact username of an existing active GoreeCloud Tasks account.",
    )
    role = forms.ChoiceField(choices=ProjectMembership.Role.choices)

    def __init__(self, *args, project, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        self.target_user = None

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        User = get_user_model()
        user = User.objects.filter(username__iexact=username, is_active=True).first()
        if user is None:
            raise forms.ValidationError("No active account matches that username.")
        if user.pk == self.project.owner_id:
            raise forms.ValidationError("The project owner does not need a membership record.")

        active_membership = self.project.memberships.filter(
            user=user,
            is_active=True,
        ).first()
        if active_membership is not None:
            raise forms.ValidationError("That user is already an active project member.")

        self.target_user = user
        return username


class MembershipRoleForm(forms.ModelForm):
    """Change an active member's project role."""

    class Meta:
        model = ProjectMembership
        fields = ("role",)
