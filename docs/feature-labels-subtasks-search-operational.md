# Labels, Subtasks, Search, and Initial GoreeCloud Operational Metadata

## Scope

This increment extends the v0.1 task-management foundation without changing the
existing private-by-default or explicit shared-project authorization model.

## Labels

Labels have two scopes:

- Personal labels belong to one user and remain private to that user's personal task space.
- Project labels belong to exactly one project and are visible only to users who can already read that project.

Project Manager and Member roles may create project labels because those roles
can edit project task content. Viewer membership remains read-only. A label may
be deleted only when it is not currently assigned to any task; this avoids a
single label deletion silently changing many task records and their material
history.

Task forms expose only labels valid for the selected task scope. A private task
cannot accept another user's personal label, and a project task cannot accept a
label from another project.

## Subtasks

Subtasks are ordinary Task records linked through a parent relationship. They
inherit the parent's project scope at creation and therefore continue to use the
same authorization helpers, assignment rules, completion workflow, comments,
and activity history as any other task.

The model rejects a task as its own parent, cross-project parent/child
relationships, private subtasks whose parent belongs to another user, and cyclic
parent relationships. Subtask creation requires task edit permission. Shared
project Viewer membership cannot create subtasks.

## Search

Search begins from `Task.objects.visible_to(user)` before applying any search
conditions. It therefore does not create a new path to private or revoked
content.

The initial search covers task title and description, project name, label name,
creator and assignee username, assigned GoreeCloud system and service,
environment or virtual machine, workload category, blocker and resume condition,
and related change-record and documentation references.

Completed and cancelled tasks remain searchable because search is also a
retrieval workflow, not only an active-work view.

## Initial GoreeCloud Operational Metadata

Ordinary tasks remain valid with every operational field empty. A task may be
marked as GoreeCloud operational work and can then record assigned system,
assigned service, environment or virtual machine, workload category, blocker,
resume condition, backup prerequisite, recovery requirement, validation
requirement, documentation requirement, related change record, and related
GoreeCloud documentation.

The editor keeps these fields in a separate optional section so personal and
family task capture does not require infrastructure terminology.

## Activity and Data Minimization

Material task edits include label and operational-field changes in the existing
activity stream. Activity metadata records changed field keys, not copies of
label names, blockers, documentation references, or other field content.

Subtask creation creates the normal attributable task-created activity event and
stores only the parent task identifier as structured metadata.

## Security and Privacy Invariants

This increment preserves the existing invariants: visibility begins with
server-side task/project authorization; Viewer membership remains read-only;
removed project members lose future access; personal labels cannot leak across
users; project labels cannot leak across projects; search cannot enumerate
inaccessible content; and Django staff status does not automatically provide
normal application access to private task or label content.

## Validation

The feature test suite covers personal-label isolation, project-label roles,
invalid cross-scope label assignment, used-label deletion protection, subtask
creation and Viewer denial, cross-project parent rejection, search isolation,
completed-task search, optional operational metadata, operational field display,
and data-minimized label-change activity.
