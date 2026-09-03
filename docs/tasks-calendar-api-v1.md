# GoreeCloud Tasks ↔ Calendar API v1

## Status

**Development Candidate / source implementation. Not production accepted.**

This document records the first versioned GoreeCloud Tasks API surface intended for first-party GoreeCloud Calendar integration. It describes the source behavior on the current development branch; it does not establish deployed runtime acceptance, Stable application conformance, GoreeCloud Identity production service identity, Privacy Shield runtime acceptance, Wardveil Security production coverage, or Everkeep production continuity acceptance.

GoreeCloud Tasks remains authoritative for task content, workflow, assignment, project membership, completion, recurrence, and task authorization. GoreeCloud Calendar remains authoritative for native calendar events, calendar membership, event scheduling semantics, and Calendar-specific metadata. Neither application may read or mutate the other's database directly.

## Authentication boundary

The current v1 development transport preserves the existing Tasks Calendar integration configuration:

- `TASKS_CALENDAR_API_ENABLED`
- `TASKS_CALENDAR_API_USERNAME`
- `TASKS_CALENDAR_API_TOKEN` or `TASKS_CALENDAR_API_TOKEN_FILE`
- `TASKS_CALENDAR_API_MAX_TASKS`

One deployment-scoped bearer credential maps to exactly one configured active Tasks account. The request cannot select or impersonate another account. Every object read is re-evaluated through the Tasks authorization model, and every mutation is re-evaluated through the Tasks edit boundary.

This is an intentionally bounded development/service integration mechanism. It is **not** represented as the final GoreeCloud Identity service-identity or delegated-user authorization architecture. A future production integration must adopt the applicable current GoreeCloud Identity contract and complete application-specific runtime acceptance without weakening Tasks authorization.

The two service-to-service POST routes are CSRF-exempt because they do not use browser session authentication. They require the dedicated bearer credential, accept JSON only, reject unsupported fields, enforce a 16 KiB request limit, and return private, non-cacheable responses. Browser-facing Tasks mutations remain subject to their ordinary browser security model.

## Projection schema

The projection schema identifier remains:

`goreecloud.tasks.calendar-projections.v1`

Schema version: `1`

Each task projection contains only the Calendar-required task subset:

- source application (`goreecloud-tasks`) and source API version;
- stable Tasks task ID;
- authoritative Tasks deep link;
- title;
- due date/time;
- priority value and label;
- workflow status value and label;
- recurrence value and label;
- project ID/name when present;
- revision timestamp;
- `updated_at` retained as the compatibility form of the same revision.

Descriptions, comments, labels, assignees, account data, reminder state, operational notes, blockers, related records, and other content are intentionally excluded from the Calendar projection.

## Routes

All routes are under the existing `/api/v1/` application API namespace.

### List scheduled task projections

`GET /api/v1/calendar/task-projections/`

Optional bounded window:

`GET /api/v1/calendar/task-projections/?start=<ISO-8601>&end=<ISO-8601>`

Rules:

- `start` and `end` must be supplied together.
- Both must be timezone-aware ISO 8601 timestamps.
- `end` must be later than `start`.
- The requested interval may not exceed 93 days.
- The window uses `due_at >= start` and `due_at < end` semantics.
- Omitting both parameters preserves the existing compatibility behavior and returns visible active scheduled tasks up to the configured maximum.
- Completed and cancelled tasks are excluded.

### Read one task projection

`GET /api/v1/calendar/task-projections/<task_id>/`

The task must still be visible to the configured Tasks principal, active, and scheduled. Loss of authorization is reflected immediately and returns a non-enumerating `404` response.

### Create a task from Calendar context

`POST /api/v1/calendar/tasks/`

Accepted JSON fields:

- `title` — required;
- `due_at` — required, timezone-aware ISO 8601;
- `priority` — optional GoreeCloud P0–P4 integer value, default P3;
- `project_id` — optional editable Tasks project ID, or `null` for personal Inbox scope.

The created task is a native Tasks record with the configured Tasks principal as creator and assignee, `Ready` status, and non-repeating recurrence. Calendar cannot use this endpoint to set descriptions, labels, assignees, recurrence, completion state, operational metadata, or arbitrary Tasks fields.

Project creation scope is checked at mutation time. A Viewer cannot create work in a shared project. A project owner or active Manager/Member may create work where the existing Tasks model allows it.

### Reschedule a task

`POST /api/v1/calendar/tasks/<task_id>/reschedule/`

Accepted JSON fields:

- `due_at` — required, timezone-aware ISO 8601;
- `expected_updated_at` — required optimistic source revision.

The task must be currently editable by the configured Tasks principal. The mutation locks the task row and compares the supplied revision with the authoritative Tasks `updated_at` value. A stale revision returns HTTP `409` with the current revision and does not overwrite the newer Tasks state.

Calendar cannot use this endpoint to complete, delete, assign, relabel, change recurrence, edit descriptions, or otherwise broaden its mutation authority.

## Attribution and minimization

Calendar-origin task creation and rescheduling are recorded through the existing Tasks material activity system. Activity metadata records the source (`goreecloud-calendar`) and the names of the affected fields, not copies of task descriptions, comments, labels, blocker text, or other private content.

The API performs no general-purpose usage analytics and does not create a parallel Calendar copy of task content. The projection is derived from the current authoritative Tasks record on each request.

## Conflict and deletion semantics

The v1 mutation surface uses Tasks `updated_at` as the first optimistic revision guard. This prevents a stale Calendar planning surface from silently overwriting a more recent Tasks reschedule.

No Calendar endpoint in this version deletes a task. Removing or hiding a projection in Calendar must not be interpreted as task deletion. Task completion and deletion remain Tasks-authoritative operations and will naturally remove the item from the active scheduled projection feed.

Recurrence remains Tasks-authoritative. Calendar receives recurrence state for display but cannot rewrite recurrence through this API version.

## Explicitly not implemented in this tranche

- task duration or time-block length;
- drag-and-drop duration-aware time blocking;
- Calendar busy/event context flowing into Tasks;
- task completion from Calendar;
- task deletion from Calendar;
- recurrence mutation from Calendar;
- arbitrary task editing from Calendar;
- multi-user delegated service identity through GoreeCloud Identity;
- production Wardveil security acceptance for this consumer path;
- production Privacy Shield adapter acceptance for this consumer path;
- production Everkeep continuity acceptance for this consumer path;
- deployed first-party Calendar consumer acceptance.

A due time is not treated as a duration. A true time-block planner remains gated on an explicit Tasks duration/scheduling model.

## Validation requirements

Before this source candidate can advance, the exact revision must pass the repository's existing CI and integration gates plus Calendar-specific tests covering at least:

- hidden/disabled behavior;
- bearer authentication and fail-closed configuration;
- minimized projection output;
- immediate membership-revocation effects;
- bounded date windows;
- single-projection authorization;
- Viewer mutation denial;
- Member/owner mutation authorization;
- JSON field allowlists;
- timezone-aware scheduling;
- bearer-authenticated service POST behavior;
- optimistic revision conflict handling;
- attributable minimized activity records;
- migration drift and ordinary Tasks regression coverage.

Source validation alone does not establish production readiness. The GoreeCloud Calendar consumer must be implemented and validated separately, followed by environment-specific service identity, privacy, security, continuity, deployment, failure-mode, and application acceptance evidence required by current GoreeCloud standards.