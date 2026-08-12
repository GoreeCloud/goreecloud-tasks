"""Forms for task collaboration."""

from django import forms

from .models import TaskComment


class TaskCommentForm(forms.ModelForm):
    """Create a comment without exposing unrelated account information."""

    class Meta:
        model = TaskComment
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 4,
                    "maxlength": 10000,
                    "placeholder": "Add a comment…",
                    "aria-label": "Comment",
                }
            )
        }

    def clean_body(self):
        body = self.cleaned_data["body"].strip()
        if not body:
            raise forms.ValidationError("Enter a comment before posting.")
        return body
