# Comments and Material Activity History — v0.1 Development Note

This increment adds attributable collaboration records without weakening the existing GoreeCloud Tasks user-content boundary.

## Implemented

- Task detail pages available to users who already have read access to the task.
- Task comments attributed to individual GoreeCloud Tasks accounts.
- Comment creation limited to users who may edit the task; Viewer access remains read-only.
- Material activity events for task creation, material edits, completion, reopening, deletion, and comments.
- Material activity events for project creation, project settings changes, sharing revocation, member addition, role changes, and member removal.
- Project activity feeds that include project and project-scoped task events.
- Task activity feeds that remain scoped to the task's normal visibility boundary.
- Membership removal immediately removes future access to comments and activity along with the underlying task/project access.
- Activity metadata stores compact field names and identifiers rather than copies of task descriptions or comment bodies.
- Deleted project-task events retain an attributable project-history record through nullable task references.
- All displayed collaboration timestamps use the application timezone and 12-hour format.

## Authorization Boundary

Comments and activity never create a new visibility path. A user must first be able to read the underlying task or project before its collaboration history is rendered.

Only users who can edit a task may add comments. Project Viewer membership can read the task discussion and activity that the Viewer is otherwise authorized to see but cannot post a comment. Users whose project membership is deactivated lose the same future visibility they lose for the task itself.

The application does not expose a global activity stream in this increment. Activity is deliberately rendered only inside an already-authorized task or project context.

## Activity Semantics

Activity records material application mutations rather than page views or low-value interaction telemetry. Task edit events store which fields changed, but do not duplicate task descriptions or comment text into the activity payload. This reduces sensitive-data duplication while retaining an attributable change record.

Comment records are preserved as authored task content. The v0.1 interface supports comment creation but intentionally does not yet expose comment editing or deletion controls.

## Validation

The collaboration test suite covers:

- Member comment creation and attribution.
- Viewer read-only discussion access.
- Cross-user and outsider isolation.
- Private-task comment isolation.
- Output escaping for comment content.
- Task creation, edit, completion, and reopen activity.
- Project membership activity.
- Project activity visibility.
- Access loss after membership revocation.
- Project-sharing revocation history.

The existing Django system checks, migration-drift check, full test suite, PostgreSQL-backed Docker migrations, application startup, and live health verification remain required before merge.

## Production Boundary

This remains development-only v0.1 functionality. Production publication is still blocked on the broader release requirements including labels, subtasks, search, expanded GoreeCloud operational metadata, export/import, backup and restoration validation, monitoring, private publication, upgrade/rollback validation, and remaining acceptance requirements.
