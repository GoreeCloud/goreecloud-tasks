"""Forms for private reminder scheduling and user notification preferences."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import NotificationPreference, TaskReminder


class NotificationPreferenceForm(forms.ModelForm):
    """Edit user-controlled reminder defaults without exposing integration secrets."""

    timezone_name = forms.CharField(
        label="Time zone",
        max_length=64,
        help_text="IANA time zone name used for task and reminder times, for example America/Chicago.",
    )

    class Meta:
        model = NotificationPreference
        fields = (
            "reminders_enabled",
            "default_lead_minutes",
            "ntfy_enabled",
        )
        labels = {
            "reminders_enabled": "Enable task reminders",
            "default_lead_minutes": "Default reminder lead time (minutes)",
            "ntfy_enabled": "Enable ntfy delivery",
        }
        help_texts = {
            "default_lead_minutes": "Used to prefill a new reminder from a task due time. Maximum 10,080 minutes (7 days).",
            "ntfy_enabled": "Delivery also requires the GoreeCloud Tasks ntfy publisher and topic ACLs to be configured by an administrator.",
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if not self.is_bound:
            self.fields["timezone_name"].initial = user.timezone

    def clean_timezone_name(self):
        value = self.cleaned_data["timezone_name"].strip()
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValidationError("Enter a valid IANA time zone name.") from exc
        return value

    def save(self, commit=True):
        preference = super().save(commit=commit)
        self.user.timezone = self.cleaned_data["timezone_name"]
        if commit:
            self.user.save(update_fields=["timezone"])
        return preference


class TaskReminderForm(forms.ModelForm):
    """Schedule one private reminder for a task visible to the current user."""

    remind_at = forms.DateTimeField(
        label="Remind me at",
        input_formats=("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"),
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={"type": "datetime-local"},
        ),
    )

    class Meta:
        model = TaskReminder
        fields = ("remind_at",)

    def __init__(self, *args, user, task, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.task = task

    def clean_remind_at(self):
        remind_at = self.cleaned_data["remind_at"]
        if remind_at <= timezone.now():
            raise ValidationError("Choose a reminder time in the future.")

        duplicate = TaskReminder.objects.filter(
            user=self.user,
            task=self.task,
            remind_at=remind_at,
            cancelled_at__isnull=True,
        ).exists()
        if duplicate:
            raise ValidationError("You already have an active reminder at this time.")
        return remind_at
