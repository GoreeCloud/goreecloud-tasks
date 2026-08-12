"""Source-neutral records external import adapters can normalize into."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class NormalizedLabel:
    source_id: str
    name: str


@dataclass(frozen=True)
class NormalizedProject:
    source_id: str
    name: str


@dataclass(frozen=True)
class NormalizedTask:
    source_id: str
    title: str
    description: str = ""
    project_source_id: str | None = None
    parent_source_id: str | None = None
    label_source_ids: tuple[str, ...] = ()
    priority: int | None = None
    status: str | None = None
    due_at: datetime | None = None


@dataclass(frozen=True)
class NormalizedImportBundle:
    """Provider-independent intermediate form used before database writes."""

    source: str
    projects: tuple[NormalizedProject, ...] = field(default_factory=tuple)
    labels: tuple[NormalizedLabel, ...] = field(default_factory=tuple)
    tasks: tuple[NormalizedTask, ...] = field(default_factory=tuple)
