# Generated for GoreeCloud Tasks v0.1 collaboration history.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("projects", "0001_initial"),
        ("tasks", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ActivityEvent",
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
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("task_created", "Task created"),
                            ("task_updated", "Task updated"),
                            ("task_completed", "Task completed"),
                            ("task_reopened", "Task reopened"),
                            ("task_deleted", "Task deleted"),
                            ("comment_added", "Comment added"),
                            ("project_created", "Project created"),
                            ("project_updated", "Project updated"),
                            (
                                "project_sharing_revoked",
                                "Project sharing revoked",
                            ),
                            ("member_added", "Project member added"),
                            (
                                "member_role_changed",
                                "Project member role changed",
                            ),
                            ("member_removed", "Project member removed"),
                        ],
                        max_length=40,
                    ),
                ),
                ("summary", models.CharField(max_length=500)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="task_activity_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="activity_events",
                        to="projects.project",
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="activity_events",
                        to="tasks.task",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at", "-id"),
            },
        ),
        migrations.CreateModel(
            name="TaskComment",
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
                ("body", models.TextField(max_length=10000)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="task_comments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "task",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comments",
                        to="tasks.task",
                    ),
                ),
            ],
            options={
                "ordering": ("created_at", "id"),
            },
        ),
    ]
