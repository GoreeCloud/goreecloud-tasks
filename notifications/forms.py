"""Forms for private reminder scheduling and user notification preferences."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from tasks.models import Task

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
    """Schedule one private reminder for a known task visible to the current user."""

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


class VisibleTaskChoiceField(forms.ModelChoiceField):
    """Present enough task context without exposing any task outside the queryset."""

    def label_from_instance(self, task):
        scope = task.project.name if task.project_id else "Private Inbox"
        return f"{scope} — {task.title}"


class ReminderCreateForm(forms.Form):
    """Schedule a private reminder from the central Notifications page."""

    task = VisibleTaskChoiceField(queryset=Task.objects.none(), label="Task")
    remind_at = forms.DateTimeField(
        label="Remind me at",
        input_formats=("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"),
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={"type": "datetime-local"},
        ),
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["task"].queryset = (
            Task.objects.visible_to(user)
            .exclude(status__in=[Task.Status.COMPLETED, Task.Status.CANCELLED])
            .select_related("project")
            .order_by("project__name", "priority", "title", "id")
        )

    def clean(self):
        cleaned = super().clean()
        task = cleaned.get("task")
        remind_at = cleaned.get("remind_at")
        if task is None or remind_at is None:
            return cleaned
        if remind_at <= timezone.now():
            self.add_error("remind_at", "Choose a reminder time in the future.")
            return cleaned
        if TaskReminder.objects.filter(
            user=self.user,
            task=task,
            remind_at=remind_at,
            cancelled_at__isnull=True,
        ).exists():
            self.add_error(
                "remind_at",
                "You already have an active reminder for this task at this time.",
            )
        return cleaned

    def save(self):
        reminder = TaskReminder(
            user=self.user,
            task=self.cleaned_data["task"],
            remind_at=self.cleaned_data["remind_at"],
        )
        reminder.save()
        return reminder
