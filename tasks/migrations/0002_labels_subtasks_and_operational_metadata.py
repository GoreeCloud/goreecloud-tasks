# Add labels, subtasks, and the first GoreeCloud operational metadata fields.

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("labels", "0001_initial"),
        ("tasks", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="assigned_service",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="task",
            name="assigned_system",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="task",
            name="backup_prerequisite",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="task",
            name="blocker",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="task",
            name="documentation_requirement",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="task",
            name="environment",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="task",
            name="is_goreecloud_work",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="task",
            name="labels",
            field=models.ManyToManyField(blank=True, related_name="tasks", to="labels.label"),
        ),
        migrations.AddField(
            model_name="task",
            name="parent",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subtasks",
                to="tasks.task",
            ),
        ),
        migrations.AddField(
            model_name="task",
            name="recovery_requirement",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="task",
            name="related_change_record",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="task",
            name="related_documentation",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="task",
            name="resume_condition",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="task",
            name="validation_requirement",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="task",
            name="workload_category",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
