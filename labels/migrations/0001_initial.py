# Initial GoreeCloud Tasks label schema.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Label",
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
                ("name", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="task_labels",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="labels",
                        to="projects.project",
                    ),
                ),
            ],
            options={
                "ordering": ("name", "id"),
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("project__isnull", True)),
                        fields=("owner", "name"),
                        name="unique_personal_label_name_per_owner",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("project__isnull", False)),
                        fields=("project", "name"),
                        name="unique_project_label_name",
                    ),
                ],
            },
        ),
    ]
