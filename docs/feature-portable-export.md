# Portable export, import, and restoration boundary

## Purpose

This capability provides machine-readable portability for GoreeCloud Tasks without turning ordinary read access into a new bulk-exfiltration permission and without treating an uploaded archive or provider file as trusted database state.

## Export format

Exports use UTF-8 JSON with the format identifier `goreecloud.tasks.export` and schema version `2`. Every document includes an export timestamp, an explicit scope, and application-owned records grouped by users, projects, memberships, labels, tasks, comments, and activity. Schema version 2 additionally carries user-private notification state inside complete user archives.

The current schema preserves object identifiers and relationship identifiers so restoration can remap projects, parents, labels, creators, assignees, membership records, comments, activity, and eligible task reminders into new local database identifiers. Timestamps are ISO 8601 values. Task status and priority use their stored stable codes or values rather than presentation text.

## User archive boundary

A user's archive contains private personal tasks and labels plus projects owned by that user and the records contained by those owned projects. A project owned by somebody else is excluded even when the exporter currently has Manager, Member, or Viewer access. Normal read access does not automatically become a bulk-export right over another person's project.

Schema version 2 adds the user's persisted notification preferences and reminders whose referenced tasks are already inside that same user-archive ownership boundary. A reminder attached only to a task in another owner's shared project is not exported because exporting the reminder would otherwise require widening the archive to include task content that the user does not own. The archive records only the count of such excluded reminders so the limitation is visible without disclosing the excluded task content.

## Project archive boundary

Project archive download is owner-only in v0.1. It contains the selected project and its memberships, labels, tasks, comments, activity, and referenced users.

Project archives deliberately do not contain user notification preferences or reminder schedules. Reminder state is private to the individual user and ordinary project ownership is not treated as authority to export a collaborator's personal reminder configuration.

Project archive restoration is not enabled yet. The guarded restoration workflow described below accepts complete `user_archive` documents only.

## Sensitive-data minimization

The export does not include passwords, password hashes, email addresses, sessions, authentication tokens, ntfy publisher credentials, secret configuration, or unrelated account fields. User references contain only the local user ID and username. Comment bodies and task descriptions are included because they are application-owned task content inside the approved export scope.

A schema-v2 user archive may include the user's generated ntfy topic because that topic is application configuration rather than an authentication credential. ntfy access remains controlled by the external server's authenticated identities and ACLs. Transient reminder `last_error` delivery text is intentionally omitted from portable archives so internal publisher/server error detail is not carried into user data portability. Reminder schedule, sent/cancelled state, attempt count, last-attempt timestamp, and historical timestamps are preserved.

Downloads and the authenticated portability page are marked `private, no-store`. JSON downloads are served as attachments.

## Source-neutral external import execution

The `imports` package defines a provider-neutral normalization schema and a database executor. Provider adapters translate provider-specific exports into `NormalizedImportBundle` before persistence.

The executor validates the complete normalized bundle before writing. Validation covers unique source identifiers, project and label names, project references, label scope, task-parent scope, parent cycles, task priorities, task statuses, timezone-aware due timestamps, comment task references, and comment body limits.

Execution is atomic. If validation or persistence fails, the import does not intentionally leave a partially created provider import.

External provider imports follow a deliberately narrow authorization boundary:

- imported projects are created as Private;
- imported projects are owned by the authenticated importing user;
- imported tasks are created and assigned to the authenticated importing user;
- imported labels are owned by the authenticated importing user;
- imported comments are attributed to the authenticated importing user;
- no user accounts are created;
- no project memberships are created;
- no shared projects are created;
- existing projects or personal labels are not silently overwritten or merged when names collide.

This boundary allows provider migration work to proceed without allowing an external file to grant access to another account.

## Full-fidelity user archive restoration

GoreeCloud-native recovery uses the richer versioned archive schema directly because a full Tasks recovery must preserve application relationships that ordinary provider imports do not normally carry, including memberships, creators, assignees, comments, material activity, historical role state, timestamps, GoreeCloud operational metadata, notification preferences, and eligible reminder state.

The v0.1 user-archive restore workflow is intentionally conservative:

- `goreecloud.tasks.export` user archives using schema version `1` or `2` are accepted;
- schema version 1 remains supported as a legacy core-data archive and contains no notification state;
- schema version 2 validates and restores the user-private notification state carried by the archive;
- only complete `user_archive` scope is accepted;
- the archived username must exactly match the authenticated account username;
- every archived collaborator username must already exist as a local account;
- the restore process never creates user accounts from archive content;
- the authenticated user must have no existing owned Tasks projects, personal Tasks labels, or private personal Tasks before restoration begins;
- schema-v2 restoration additionally requires that the target user have no existing Tasks reminders, preventing reminder-state merge ambiguity;
- existing application-owned Tasks data is not overwritten or merged;
- project, membership, label, task, parent, label-assignment, user, comment, activity, notification-preference, and reminder references are validated before persistence;
- task priorities, statuses, timestamps, visibility values, membership roles, activity kinds, reminder timestamps, reminder lifecycle state, lead time, and ntfy topic syntax are validated against the current application model;
- an archived ntfy topic is refused if that topic is already assigned to another local user;
- private projects may not restore with active memberships;
- archived user records contain only the identity references already present in the export schema.

The complete schema-v2 reconstruction occurs inside one outer database transaction. The existing core archive restorer reconstructs projects, memberships, labels, tasks, comments, activity, and historical timestamps. The notification layer then remaps archived reminder task IDs to the newly reconstructed task records and restores the user's notification preference plus eligible reminders before that outer transaction is allowed to commit.

Historical collaborators are temporarily granted the minimum model-compatible project state needed to reconstruct records that were valid before a later role reduction or membership revocation. That temporary state exists only inside the uncommitted transaction. The archived project visibility, membership role, active/inactive state, and timestamps are restored before commit.

This design allows records such as a task created by a collaborator who was later removed to remain historically attributable after recovery without permanently reactivating that collaborator.

## User interface recovery controls

The Data portability page provides a user-archive upload control with an explicit recovery acknowledgement. Uploads are limited to 25 MiB and must be valid UTF-8 JSON. The server performs all archive validation; the file extension and browser-provided MIME type are not treated as proof that the archive is safe.

The restore form does not provide merge or overwrite options in v0.1. Those behaviors would require separate conflict-resolution semantics and additional authorization tests.

## Todoist CSV migration

The Todoist adapter now supports the currently documented Todoist project CSV structure. The official format identifies rows as `task`, `section`, or `note` and documents columns including `CONTENT`, `DESCRIPTION`, `PRIORITY`, `INDENT`, `AUTHOR`, `RESPONSIBLE`, `DATE`, `DATE_LANG`, `TIMEZONE`, `DURATION`, `DURATION_UNIT`, `meta`, `DEADLINE`, `DEADLINE_LANG`, and optional section `IS_COLLAPSED` state.

The parser accepts UTF-8 text and detects comma, semicolon, or tab delimiters. `TYPE` and `CONTENT` are required. Blank spacer rows and metadata-only rows are ignored; unsupported nonblank row types are rejected.

The current migration mapping is deliberately explicit:

- each uploaded project CSV becomes one new private GoreeCloud project;
- Todoist p1, p2, p3, and p4 map to GoreeCloud P1, P2, P3, and P4 respectively, leaving GoreeCloud P0 reserved for critical operational work;
- a blank Todoist `PRIORITY` cell maps to GoreeCloud P1 because Todoist's current CSV format guide explicitly defines a blank priority cell as p1;
- `INDENT` levels 1 through 4 reconstruct task/subtask hierarchy and an orphaned indent is rejected;
- task-content `@label` tokens become project-scoped GoreeCloud labels and are removed from the imported title;
- `note` rows become task comments attributed to the authenticated importing user;
- only a timezone-aware ISO-8601/RFC3339 `DATE` value is mapped to the current native due timestamp;
- natural-language and recurring Todoist dates are preserved as source metadata instead of being guessed into a concrete timestamp;
- section names and section descriptions are preserved in task import metadata because GoreeCloud Tasks does not yet expose a native section entity;
- Todoist author and responsible text is preserved as source metadata and never creates, resolves, or assigns a GoreeCloud user identity;
- deadline, duration, language, timezone, and provider metadata are preserved in the task description when they do not have a safe native field;
- unknown future nonblank CSV columns are also preserved as source metadata rather than silently discarded.

Todoist project CSV export has provider-level limitations that GoreeCloud cannot reconstruct from absent source data. In particular, completed tasks are not present in Todoist project CSV exports, and the start date of a recurring date is not preserved by that export path. GoreeCloud Tasks does not claim to recover information that Todoist did not include in the supplied CSV.

The upload endpoint is authenticated, limited to 25 MiB, decodes UTF-8 with optional BOM, normalizes the CSV, and then uses the same atomic source-neutral executor as other provider imports. A project-name collision stops the operation rather than merging into an existing project.

## Validation

Regression coverage verifies:

- authenticated schema-v2 export;
- owner-only project bulk export;
- exclusion of other users' private and other-owned shared work;
- export relationship and GoreeCloud operational-field preservation;
- schema-v2 notification-preference export and reminder export for archive-owned tasks;
- exclusion and non-disclosure of reminder state tied only to another owner's shared project;
- omission of transient reminder publisher error text;
- project archives do not contain private user notification state;
- schema-v2 notification preference and reminder restoration with task-ID remapping;
- schema-v1 user-archive backward compatibility;
- ntfy topic collision refusal before core restored data can commit;
- sensitive account-field omission;
- source-neutral import execution into private user-owned data;
- atomic rejection of invalid normalized relationships;
- normalized comment persistence and attribution;
- collision refusal instead of silent merging;
- full user-archive restoration of projects, memberships, labels, tasks, subtasks, comments, activity, identity relationships, historical inactive membership state, timestamps, and GoreeCloud operational metadata;
- refusal to restore into a non-clean target account;
- refusal to restore an archive to a differently named account;
- refusal to restore when a required collaborator account is missing;
- authentication and explicit confirmation on the web restore path;
- Todoist comma-delimited and semicolon-delimited parsing;
- Todoist section, label, priority, blank-priority, indent, note/comment, and source-metadata mapping;
- conservative due-date mapping;
- preservation of unknown future columns;
- rejection of malformed Todoist headers and task hierarchy;
- authenticated Todoist web import into a new private project; and
- project-name collision refusal on Todoist web import.
