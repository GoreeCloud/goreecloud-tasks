from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0002_labels_subtasks_and_operational_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="recurrence",
            field=models.CharField(
                choices=[
                    ("none", "Does not repeat"),
                    ("daily", "Daily"),
                    ("weekly", "Weekly"),
                    ("monthly", "Monthly"),
                ],
                default="none",
                max_length=16,
            ),
        ),
    ]
