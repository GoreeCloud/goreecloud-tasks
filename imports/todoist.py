"""Todoist project CSV normalization.

Todoist's current Help Center documents project CSV rows with ``task``,
``section``, and ``note`` types and columns for content, description, priority,
indentation, author/responsible identity, scheduling, duration, deadlines, and
section state. This adapter maps only semantics GoreeCloud Tasks can represent
safely and preserves unsupported source values as human-readable import metadata.

Provider identities never become GoreeCloud identities here. Database execution
remains the responsibility of ``imports.executor``, which creates private data
owned by the authenticated importing user.
"""

import csv
import io
import re
from datetime import datetime

from tasks.models import Task

from .schema import (
    NormalizedComment,
    NormalizedImportBundle,
    NormalizedLabel,
    NormalizedProject,
    NormalizedTask,
)


class TodoistCsvError(ValueError):
    """Raised when a Todoist CSV cannot be normalized safely."""


_LABEL_RE = re.compile(r"(?<!\S)@([^\s@]+)")
_REQUIRED_HEADERS = {"TYPE", "CONTENT"}
_KNOWN_HEADERS = {
    "TYPE",
    "CONTENT",
    "DESCRIPTION",
    "PRIORITY",
    "INDENT",
    "AUTHOR",
    "RESPONSIBLE",
    "DATE",
    "DATE_LANG",
    "TIMEZONE",
    "DURATION",
    "DURATION_UNIT",
    "META",
    "DEADLINE",
    "DEADLINE_LANG",
    "IS_COLLAPSED",
}
_PRIORITY_MAP = {
    "1": Task.Priority.P1_URGENT,
    "2": Task.Priority.P2_HIGH,
    "3": Task.Priority.P3_STANDARD,
    "4": Task.Priority.P4_LOW,
    "": Task.Priority.P4_LOW,
}


def _detect_dialect(text):
    sample = text[:8192]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        return csv.excel


def _safe_due_datetime(raw):
    """Return only an unambiguous timezone-aware datetime.

    Todoist CSV dates may be natural-language or recurring expressions. Those are
    preserved as source metadata instead of being guessed into a concrete due
    timestamp. RFC3339/ISO-8601 timestamps with an explicit offset are safe to map.
    """
    value = raw.strip()
    if not value or "T" not in value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _append_import_metadata(description, items):
    lines = [f"- {label}: {value}" for label, value in items if value]
    if not lines:
        return description
    block = "Imported from Todoist:\n" + "\n".join(lines)
    if description.strip():
        return description.rstrip() + "\n\n" + block
    return block


def _normalized_headers(fieldnames):
    if not fieldnames:
        raise TodoistCsvError("The Todoist CSV is missing a header row.")
    seen = set()
    for name in fieldnames:
        if name is None:
            continue
        header = name.strip().upper()
        if not header:
            continue
        if header in seen:
            raise TodoistCsvError(f"Duplicate Todoist CSV header: {header}.")
        seen.add(header)
    missing = sorted(_REQUIRED_HEADERS - seen)
    if missing:
        raise TodoistCsvError(
            "Todoist CSV is missing required header(s): " + ", ".join(missing) + "."
        )


class TodoistImportAdapter:
    source = "todoist_csv"

    def normalize_csv(self, text: str, *, project_name: str) -> NormalizedImportBundle:
        if not isinstance(text, str) or not text.strip():
            raise TodoistCsvError("The Todoist CSV is empty.")
        if not isinstance(project_name, str) or not project_name.strip():
            raise TodoistCsvError("A destination project name is required.")
        project_name = project_name.strip()
        if len(project_name) > 200:
            raise TodoistCsvError("Project names may not exceed 200 characters.")

        dialect = _detect_dialect(text)
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        _normalized_headers(reader.fieldnames)
        header_lookup = {
            original: original.strip().upper()
            for original in (reader.fieldnames or [])
            if original is not None and original.strip()
        }

        project_id = "todoist-project-1"
        projects = [NormalizedProject(source_id=project_id, name=project_name)]
        labels_by_key = {}
        tasks = []
        comments = []
        task_stack = {}
        previous_task_id = None
        current_section = ""
        current_section_description = ""

        for row_number, raw_row in enumerate(reader, start=2):
            extra_values = raw_row.get(None)
            if extra_values and any((value or "").strip() for value in extra_values):
                raise TodoistCsvError(
                    f"Row {row_number} contains more values than the CSV header defines."
                )
            row = {
                header_lookup.get(key, str(key).strip().upper()): (value or "").strip()
                for key, value in raw_row.items()
                if key is not None
            }
            row_type = row.get("TYPE", "")
            content = row.get("CONTENT", "")

            if not row_type:
                # Todoist template/export files can contain spacer or metadata rows.
                nonempty = {key: value for key, value in row.items() if value}
                if not nonempty or set(nonempty) <= {"META"}:
                    continue
                raise TodoistCsvError(
                    f"Row {row_number} has data but no TYPE value."
                )

            if row_type == "section":
                if not content:
                    raise TodoistCsvError(f"Row {row_number} section has no CONTENT.")
                current_section = content
                current_section_description = row.get("DESCRIPTION", "")
                task_stack.clear()
                previous_task_id = None
                continue

            if row_type == "note":
                if previous_task_id is None:
                    raise TodoistCsvError(
                        f"Row {row_number} note does not follow a task row."
                    )
                if not content:
                    raise TodoistCsvError(f"Row {row_number} note has no CONTENT.")
                note_metadata = []
                if row.get("DESCRIPTION"):
                    note_metadata.append(("Todoist note description", row["DESCRIPTION"]))
                for key, value in row.items():
                    if key not in _KNOWN_HEADERS and value:
                        note_metadata.append((f"Todoist {key}", value))
                body = _append_import_metadata(content, note_metadata)
                comments.append(
                    NormalizedComment(
                        source_id=f"todoist-comment-row-{row_number}",
                        task_source_id=previous_task_id,
                        body=body,
                    )
                )
                continue

            if row_type != "task":
                raise TodoistCsvError(
                    f"Row {row_number} has unsupported TYPE {row_type!r}; expected task, section, or note."
                )
            if not content:
                raise TodoistCsvError(f"Row {row_number} task has no CONTENT.")

            indent_raw = row.get("INDENT", "") or "1"
            try:
                indent = int(indent_raw)
            except ValueError as exc:
                raise TodoistCsvError(
                    f"Row {row_number} INDENT must be an integer from 1 through 4."
                ) from exc
            if indent not in {1, 2, 3, 4}:
                raise TodoistCsvError(
                    f"Row {row_number} INDENT must be an integer from 1 through 4."
                )

            source_id = f"todoist-task-row-{row_number}"
            parent_source_id = None
            if indent > 1:
                parent_source_id = task_stack.get(indent - 1)
                if parent_source_id is None:
                    raise TodoistCsvError(
                        f"Row {row_number} is indented without a task at level {indent - 1}."
                    )
            task_stack[indent] = source_id
            for level in tuple(task_stack):
                if level > indent:
                    task_stack.pop(level, None)

            label_ids = []
            label_names = _LABEL_RE.findall(content)
            clean_title = _LABEL_RE.sub("", content)
            clean_title = re.sub(r"\s{2,}", " ", clean_title).strip()
            if not clean_title:
                raise TodoistCsvError(
                    f"Row {row_number} task title is empty after Todoist label tokens are removed."
                )
            for label_name in label_names:
                name = label_name.strip()
                if not name:
                    continue
                if len(name) > 100:
                    raise TodoistCsvError(
                        f"Row {row_number} label {name!r} exceeds 100 characters."
                    )
                key = name.casefold()
                if key not in labels_by_key:
                    label_id = f"todoist-label-{len(labels_by_key) + 1}"
                    labels_by_key[key] = NormalizedLabel(
                        source_id=label_id,
                        name=name,
                        project_source_id=project_id,
                    )
                label_ids.append(labels_by_key[key].source_id)

            priority_raw = row.get("PRIORITY", "")
            if priority_raw not in _PRIORITY_MAP:
                raise TodoistCsvError(
                    f"Row {row_number} PRIORITY must be blank or one of 1, 2, 3, or 4."
                )

            due_raw = row.get("DATE", "")
            due_at = _safe_due_datetime(due_raw)
            metadata = []
            if current_section:
                metadata.append(("Todoist section", current_section))
            if current_section_description:
                metadata.append(
                    ("Todoist section description", current_section_description)
                )
            if due_raw:
                metadata.append(("Todoist date", due_raw))
            for key, label in (
                ("DATE_LANG", "Todoist date language"),
                ("TIMEZONE", "Todoist timezone"),
                ("DEADLINE", "Todoist deadline"),
                ("DEADLINE_LANG", "Todoist deadline language"),
                ("DURATION", "Todoist duration"),
                ("DURATION_UNIT", "Todoist duration unit"),
                ("AUTHOR", "Todoist author"),
                ("RESPONSIBLE", "Todoist responsible"),
                ("META", "Todoist meta"),
            ):
                if row.get(key):
                    metadata.append((label, row[key]))
            for key, value in row.items():
                if key not in _KNOWN_HEADERS and value:
                    metadata.append((f"Todoist {key}", value))

            description = _append_import_metadata(
                row.get("DESCRIPTION", ""), metadata
            )
            tasks.append(
                NormalizedTask(
                    source_id=source_id,
                    title=clean_title,
                    description=description,
                    project_source_id=project_id,
                    parent_source_id=parent_source_id,
                    label_source_ids=tuple(dict.fromkeys(label_ids)),
                    priority=_PRIORITY_MAP[priority_raw],
                    status=Task.Status.PLANNED,
                    due_at=due_at,
                )
            )
            previous_task_id = source_id

        if not tasks:
            raise TodoistCsvError("The Todoist CSV does not contain any task rows.")

        return NormalizedImportBundle(
            source=self.source,
            projects=tuple(projects),
            labels=tuple(labels_by_key.values()),
            tasks=tuple(tasks),
            comments=tuple(comments),
        )

    def normalize(self, payload, *, project_name=None) -> NormalizedImportBundle:
        """Compatibility entry point for decoded, verified project CSV text only."""
        if not isinstance(payload, str):
            raise NotImplementedError(
                "Unverified Todoist object/JSON payload formats are not supported; use a verified project CSV."
            )
        return self.normalize_csv(payload, project_name=project_name or "")
