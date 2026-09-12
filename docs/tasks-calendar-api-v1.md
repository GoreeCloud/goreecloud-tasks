# GoreeCloud Tasks ↔ Calendar API v1

## Status

**Development Candidate / source implementation. Not production accepted.**

This document records the current versioned first-party GoreeCloud Tasks ↔ GoreeCloud Calendar integration candidate. It covers the Tasks-owned projection/create/reschedule API plus the Tasks-side strict consumer for privacy-minimized Calendar busy-time context. It does not establish deployed runtime acceptance, Stable application conformance, GoreeCloud Identity production service identity/delegation, Privacy Shield runtime acceptance, Wardveil Security production coverage, Everkeep production continuity acceptance, GoreeCloud Mesh integration acceptance, or production deployment.

GoreeCloud Tasks remains authoritative for task content, workflow, assignment, project membership, completion, recurrence, due scheduling, and task authorization. GoreeCloud Calendar remains authoritative for native calendar events, calendar membership, event authorization, event scheduling semantics, Calendar-specific metadata, and busy-time derivation. Neither application may read or mutate the other's database directly.

## 1. Tasks provider authentication boundary

The current v1 Tasks provider transport uses:

- `TASKS_CALENDAR_API_ENABLED`
- `TASKS_CALENDAR_API_USERNAME`
- `TASKS_CALENDAR_API_TOKEN` or `TASKS_CALENDAR_API_TOKEN_FILE`
- `TASKS_CALENDAR_API_MAX_TASKS`

One deployment-scoped bearer credential maps to exactly one configured active Tasks account. The request cannot select or impersonate another account. Every object read is re-evaluated through the Tasks authorization model, and every mutation is re-evaluated through the Tasks edit boundary.

This is an intentionally bounded development/service integration mechanism. It is **not** represented as the final GoreeCloud Identity service-identity or delegated-user authorization architecture. A future production integration must adopt the applicable current GoreeCloud Identity contract and complete application-specific runtime acceptance without weakening Tasks authorization.

The two service-to-service POST routes are CSRF-exempt because they do not use browser session authentication. They require the dedicated bearer credential, accept JSON only, reject unsupported fields, enforce a 16 KiB request limit, and return private, non-cacheable responses. Browser-facing Tasks mutations remain subject to their ordinary browser security model.

## 2. Tasks projection schema

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

## 3. Tasks provider routes used by Calendar

All provider routes are under the Tasks `/api/v1/` namespace.

### 3.1 List scheduled task projections

`GET /api/v1/calendar/task-projections/`

Optional bounded window:

`GET /api/v1/calendar/task-projections/?start=<ISO-8601>&end=<ISO-8601>`

Rules:

- `start` and `end` must be supplied together.
- Both must be timezone-aware ISO-8601 timestamps.
- `end` must be later than `start`.
- The requested interval may not exceed 93 days.
- The window uses `due_at >= start` and `due_at < end` semantics.
- Omitting both parameters preserves the existing compatibility behavior and returns visible active scheduled tasks up to the configured maximum.
- Completed and cancelled tasks are excluded.

### 3.2 Read one task projection

`GET /api/v1/calendar/task-projections/<task_id>/`

The task must still be visible to the configured Tasks principal, active, and scheduled. Loss of authorization is reflected immediately and returns a non-enumerating `404` response.

### 3.3 Create a task from Calendar context

`POST /api/v1/calendar/tasks/`

Accepted JSON fields:

- `title` — required;
- `due_at` — required, timezone-aware ISO-8601;
- `priority` — optional GoreeCloud P0–P4 integer value, default P3;
- `project_id` — optional editable Tasks project ID, or `null` for personal Inbox scope.

The created task is a native Tasks record with the configured Tasks principal as creator and assignee, `Ready` status, and non-repeating recurrence. Calendar cannot use this endpoint to set descriptions, labels, assignees, recurrence, completion state, operational metadata, or arbitrary Tasks fields.

Project creation scope is checked at mutation time. A Viewer cannot create work in a shared project. A project owner or active Manager/Member may create work where the existing Tasks model allows it.

### 3.4 Reschedule a task

`POST /api/v1/calendar/tasks/<task_id>/reschedule/`

Accepted JSON fields:

- `due_at` — required, timezone-aware ISO-8601;
- `expected_updated_at` — required optimistic source revision.

The task must be currently editable by the configured Tasks principal. The mutation locks the task row and compares the supplied revision with the authoritative Tasks `updated_at` value. A stale revision returns HTTP `409` with the current revision and does not overwrite the newer Tasks state.

Calendar cannot use this endpoint to complete, delete, assign, relabel, change recurrence, edit descriptions, or otherwise broaden its mutation authority.

## 4. Calendar busy-time context consumed by Tasks

The next planning increment introduces a strict Tasks-side consumer for the Calendar provider candidate in GoreeCloud Calendar PR #17. The Calendar provider contract is conceptually bound to:

`GET /api/v1/tasks/busy-time?starts_at=<ISO-8601>&ends_at=<ISO-8601>`

Provider schema:

`goreecloud.calendar.tasks-busy.v1`

Schema version: `1`

The Tasks client is implemented in `api/calendar_busy_client.py`. It sends only a bounded requested time window plus the deployment-provided peer-service credential. It sends no Calendar subject, username, calendar href, or collection selector. Calendar independently owns the credential-to-Calendar-subject and collection authorization mapping.

Because GoreeCloud Tasks is multi-user, the consumer configuration separately binds that peer credential's returned context to exactly one local Tasks username. This local recipient binding is not sent to Calendar and cannot select Calendar scope. It prevents a single-principal development credential from accidentally becoming a shared availability feed for every Tasks user. A future GoreeCloud Identity delegated-user model should replace the duplicated provider/consumer principal mapping rather than weakening either side.

### 4.1 Data minimization

The Tasks client accepts exactly the v1 response field set:

- `schema`;
- `version`;
- `generated_at`;
- `range` containing only `starts_at` and `ends_at`;
- `returned`;
- `busy`, containing only merged interval `starts_at` and `ends_at` values.

The strict v1 parser rejects unexpected root, range, or interval fields. This prevents event titles, descriptions, locations, UIDs, Calendar subjects, collection identifiers, attendee data, or other Calendar metadata from silently becoming trusted Tasks planning data. A broader response requires an explicit contract revision rather than an undocumented additive field.

Busy intervals must be timezone-aware, positive-duration, inside the response range, strictly chronological, non-overlapping, and fully merged. The returned count must exactly match the interval array. When the client performs the HTTP request, the response range must exactly match the requested range.

### 4.2 Window and transport bounds

The Tasks client:

- permits a maximum 31-day request window;
- limits the response body to 512 KiB;
- uses an explicit timeout between greater than zero and 30 seconds;
- sends the credential only in the `Authorization: Bearer` header;
- sends no credential in the URL;
- requires HTTPS for non-loopback Calendar endpoints;
- permits plain HTTP only for `localhost`, `127.0.0.1`, or `::1` disposable validation;
- rejects credential-bearing, query-bearing, or fragment-bearing base URLs;
- emits low-detail errors for upstream HTTP and transport failure;
- performs no automatic retry in this first interactive read-only client.

A Calendar outage must degrade Tasks planning context safely. It must not permit fabrication of Calendar event state, conversion of busy intervals into authoritative Tasks records, direct CalDAV access, or authorization broadening.

### 4.3 Tasks-side configuration and local recipient authorization

The outgoing client is disabled by default and uses:

- `TASKS_CALENDAR_BUSY_ENABLED`;
- `TASKS_CALENDAR_BUSY_USERNAME`;
- `TASKS_CALENDAR_BUSY_BASE_URL`;
- `TASKS_CALENDAR_BUSY_TOKEN` or `TASKS_CALENDAR_BUSY_TOKEN_FILE`;
- `TASKS_CALENDAR_BUSY_TIMEOUT_SECONDS`.

`TASKS_CALENDAR_BUSY_USERNAME` identifies the one local Tasks account permitted to receive busy context associated with this configured peer credential. `CalendarBusyClientConfiguration.allows_user()` requires an enabled, error-free configuration plus an authenticated active Tasks user whose username exactly matches that binding. It fails closed for another username, an inactive user, an unauthenticated user, or invalid configuration.

The two token sources are mutually exclusive. File-backed token configuration rejects non-regular files and files granting group or other permissions. Enabled configuration fails closed when the local username, URL, token, or timeout is invalid.

There remains deliberately no Tasks-side Calendar subject or calendar-collection selector. Calendar authorization decisions remain provider-side and cannot be widened by the consumer request. The local Tasks username is a recipient boundary, not a Calendar identity assertion.

This paired single-principal model remains a transitional development mechanism and is not production GoreeCloud Identity acceptance.

## 5. Attribution, conflict, and deletion semantics

Calendar-origin task creation and rescheduling are recorded through the existing Tasks material activity system. Activity metadata records the source (`goreecloud-calendar`) and the names of the affected fields, not copies of task descriptions, comments, labels, blocker text, or other private content.

The Tasks API performs no general-purpose usage analytics and does not create a parallel Calendar copy of task content. Task projections are derived from the current authoritative Tasks record on each request.

The v1 mutation surface uses Tasks `updated_at` as the first optimistic revision guard. This prevents a stale Calendar planning surface from silently overwriting a more recent Tasks reschedule.

No Calendar endpoint in this version deletes a task. Removing or hiding a projection in Calendar must not be interpreted as task deletion. Task completion and deletion remain Tasks-authoritative operations and naturally remove the item from the active scheduled projection feed.

Recurrence remains Tasks-authoritative. Calendar receives recurrence state for display but cannot rewrite recurrence through this API version.

Calendar busy intervals are advisory planning context only. They are not Tasks records, do not gain task lifecycle state, and are not exported as task content.

## 6. Integral Platform System boundary

This source tranche does not change the current platform-acceptance status of the application:

- **GoreeCloud Manager:** existing read-only Manager integration and validation remain unchanged.
- **Privacy Shield:** Calendar busy data is structurally minimized to merged intervals and the local recipient binding prevents cross-user reuse of one configured context; production Privacy Shield acceptance remains pending.
- **Wardveil Security:** HTTPS requirements, protected secret-file handling, bounded inputs/responses, low-detail failures, local recipient gating, and provider-side fixed authorization scope are represented in source; production security acceptance remains pending.
- **Everkeep:** no Tasks or Calendar persistent schema is changed by the busy-time client; rollback is source-only. Production continuity acceptance remains pending.
- **Glaze UI:** no user-facing interface change is introduced in this client tranche; current mandatory Glaze UI acceptance remains a separate gate.
- **GoreeCloud Mesh:** no Mesh transport, discovery, or event behavior is introduced; the candidate remains an explicit versioned HTTP contract.
- **GoreeCloud Identity:** the paired local/provider configured principal bindings and bearer transport are transitional and do not establish production service-identity/delegation conformance.

## 7. Explicitly not implemented in this tranche

- Tasks Agenda/UI presentation of Calendar busy intervals;
- combined task-and-busy planning suggestions;
- task duration or time-block length;
- drag-and-drop duration-aware time blocking;
- task completion from Calendar;
- task deletion from Calendar;
- recurrence mutation from Calendar;
- arbitrary task editing from Calendar;
- production multi-user delegated service identity through GoreeCloud Identity;
- production network/TLS/reverse-proxy activation of the Calendar peer endpoint;
- production rate-limiter integration for the peer endpoint;
- production Wardveil Security acceptance for this consumer path;
- production Privacy Shield adapter acceptance for this consumer path;
- production Everkeep continuity acceptance for this consumer path;
- GoreeCloud Mesh integration acceptance;
- deployment or Stable qualification.

A due time is not treated as a duration. A true time-block planner remains gated on an explicit Tasks duration/scheduling model.

## 8. Validation requirements

The Tasks provider/mutation candidate must continue to pass the repository's existing CI and integration gates plus Calendar-specific tests covering at least:

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

The outgoing Calendar busy-time consumer adds contract coverage for:

- exact schema/version and field allowlists;
- timezone-aware and bounded response ranges;
- returned-count consistency;
- interval ordering, merging, and range containment;
- exact request/response range agreement;
- HTTPS except loopback validation;
- bearer-header construction without URL credentials;
- malformed, oversized, HTTP-error, and transport-error fail-closed behavior;
- disabled/invalid client configuration;
- exact local Tasks recipient gating;
- mutually exclusive token sources;
- protected file-secret permission checks; and
- absence of Tasks-controlled Calendar subject/collection selectors.

Before Calendar busy context may be described as integrated into the Tasks product, the exact consumer candidate must pass Tasks CI and a disposable live cross-application wire test against the exact Calendar provider candidate. UI consumption must additionally enforce the local Tasks recipient binding. Production authorization, representative deployment, and application acceptance remain separate gates.
