# Generated for the GoreeCloud Tasks notification foundation.

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import notifications.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("tasks", "0002_labels_subtasks_and_operational_metadata"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationPreference",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("reminders_enabled", models.BooleanField(default=True)),
                (
                    "default_lead_minutes",
                    models.PositiveIntegerField(
                        default=30,
                        help_text="Default minutes before a task due time for a new reminder.",
                        validators=[django.core.validators.MaxValueValidator(10080)],
                    ),
                ),
                ("ntfy_enabled", models.BooleanField(default=False)),
                (
                    "ntfy_topic",
                    models.CharField(
                        default=notifications.models.default_ntfy_topic,
                        editable=False,
                        max_length=64,
                        unique=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notification_preferences",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="TaskReminder",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("remind_at", models.DateTimeField(db_index=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("last_error", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reminders",
                        to="tasks.task",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="task_reminders",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("remind_at", "id"),
            },
        ),
        migrations.AddConstraint(
            model_name="taskreminder",
            constraint=models.UniqueConstraint(
                condition=models.Q(("cancelled_at__isnull", True)),
                fields=("user", "task", "remind_at"),
                name="uniq_active_task_reminder",
            ),
        ),
        migrations.AddIndex(
            model_name="taskreminder",
            index=models.Index(
                fields=["remind_at", "sent_at", "cancelled_at"],
                name="notification_due_idx",
            ),
        ),
    ]
