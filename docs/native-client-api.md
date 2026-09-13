# GoreeCloud Tasks Native Client API

**Status:** Development foundation  
**API family:** `/api/v1/client/`  
**Schemas:** `goreecloud.tasks.client-task-list.v1`, `goreecloud.tasks.client-task-detail.v1`

## Purpose

This API is the first bounded application contract intended to support first-party Android and Linux GoreeCloud Tasks clients.

The native client must remain a client of the existing GoreeCloud Tasks authorization and data model. It must not create a separate authoritative task database or bypass project membership, task visibility, editability, recurrence, assignment, collaboration, or recovery rules.

## Authentication boundary

Both initial endpoints use the currently authenticated GoreeCloud Tasks user session and recalculate authorization on every request through `Task.objects.visible_to(user)`. Per-task editability is derived through `Task.objects.editable_by(user)`.

This Development tranche deliberately does **not** introduce a mobile bearer-token database, device credential format, refresh-token protocol, GoreeCloud Identity acceptance claim, or background synchronization authority. Those are separate security and runtime milestones.

The first Android client foundation now exists under `clients/android/`, but it intentionally does not declare network authority. It models and validates the accepted API paths locally while keeping remote list/detail reads blocked until a native GoreeCloud Identity/session exchange is defined and accepted. It does not copy browser cookies, embed reusable application-wide credentials, or invent a second authentication model.

## Task list

`GET /api/v1/client/tasks/`

Supported query parameters:

- `state=active|completed|all` — defaults to `active`; active excludes Completed and Cancelled.
- `status=<task-status>` — optional exact current Tasks status value.
- `project=<positive-id>` — optional project filter; it never broadens the caller's visibility.
- `limit=1..200` — defaults to 100.

Unknown identity-selection parameters have no effect. The endpoint never accepts a username or user id as the authorization principal.

The list response includes only data needed to render native list/planning surfaces:

- task id and title;
- project id/name when present;
- parent task id;
- assignee id/username when present;
- priority and status value/label;
- due time;
- recurrence value/label;
- current editability;
- completion, creation, and update timestamps.

It intentionally omits descriptions, comments, labels, reminder state, notification preferences, operational notes, portability archives, activity history, and other detail-only or sensitive fields.

## Task detail

`GET /api/v1/client/tasks/<task-id>/`

The detail endpoint independently reapplies `visible_to(user)` for the requested task. A task outside the caller's scope and a nonexistent task both return the same `404 {"detail": "Not found."}` result so the native client cannot probe task existence beyond normal authorization.

The detail schema contains the list-safe task fields plus:

- description;
- creator id/username; and
- currently attached label ids/names.

It still omits comments, activity history, reminder state, notification settings, GoreeCloud operational metadata, portability/recovery records, and other unrelated private state. Viewer access remains represented as `editable: false`; detail visibility never upgrades mutation permission.

## Response controls

Responses use `Cache-Control: private, no-store` and vary on the authenticated session cookie. The initial endpoints are GET-only.

Authorization remains dynamic. A project-membership revocation removes both list and detail access to the associated shared task on subsequent requests. Project filters cannot reveal a project the user otherwise cannot read.

## Android client foundation

The first Android Development client is intentionally bounded:

- it targets the current Stable GLAZE UI V1.4 / `1.4.0` contract and records adoption as in progress rather than accepted conformance;
- it constructs only the documented native list/detail endpoint family and validates client-side filter bounds before transport;
- it does not currently hold network authority;
- it does not hold or synthesize native identity/session credentials;
- it does not create a parallel authoritative task database;
- it does not implement local cache, mutation queues, background sync, notifications, reminders, or widgets;
- its UI surfaces these boundaries explicitly instead of representing unavailable capabilities as accepted.

## Follow-on milestones

1. Define GoreeCloud Identity/session exchange for native clients without reusable application-wide credentials.
2. Add authenticated read-only Android transport while preserving server authorization and private/no-store behavior.
3. Parse and render the accepted list/detail schemas on Android without broadening authorization.
4. Add conditional mutation APIs using the existing editability rules plus explicit conflict/version semantics.
5. Add incremental synchronization cursors and bounded local-cache reconciliation.
6. Add notification/reminder registration without exposing another user's notification state.
7. Establish offline mutation queues only after conflict, revocation, and recovery behavior is defined and tested.
8. Add representative-device, accessibility, background-work, Wardveil, Privacy Shield, Everkeep, signing/provenance, and release acceptance.

## Acceptance boundary

The read-only server endpoints and first Android shell are Development evidence only. They do not establish production publication, GoreeCloud Identity acceptance, authenticated Android remote reads, background synchronization, offline write authority, GLAZE UI consumer conformance, Privacy Shield acceptance, Wardveil acceptance, Everkeep recovery acceptance, Release Candidate status, or Stable status.
