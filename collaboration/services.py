"""Small explicit helpers for attributable activity recording."""

from .models import ActivityEvent


def record_activity(
    *,
    actor,
    kind,
    summary,
    task=None,
    project=None,
    details=None,
):
    """Persist one material action with its authenticated actor.

    Task events inherit the task's current project when the caller does not
    provide a project explicitly. Activity payloads intentionally store compact
    structured metadata instead of copies of task descriptions or comment text.
    """
    if project is None and task is not None:
        project = task.project

    return ActivityEvent.objects.create(
        actor=actor,
        kind=kind,
        summary=summary,
        task=task,
        project=project,
        details=details or {},
    )
