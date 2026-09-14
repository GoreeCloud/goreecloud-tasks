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

The first Android client foundation exists under `clients/android/`, but it intentionally does not declare network authority. It models and validates the accepted API paths and response invariants locally while keeping remote list/detail reads blocked until a native GoreeCloud Identity/session exchange is defined and accepted. It does not copy browser cookies, embed reusable application-wide credentials, or invent a second authentication model.

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

## Android response acceptance contract

The Android client now contains a transport-neutral `NativeTaskResponseContract` for the two minimized schemas. This is a pure source-level consumer policy, not network implementation.

It requires:

- exact list/detail schema identifiers and version `1`;
- parseable offset-aware generation and task timestamps;
- exact expected authorization identity and exact list/detail scope strings;
- list filter echoes that match the request actually planned by the client;
- returned-count equality, requested-limit enforcement, and unique task ids;
- positive project/user/label/parent identifiers where present;
- current server priority values `0..4`;
- current status values `planned`, `ready`, `in_progress`, `blocked`, `delayed`, `waiting`, `completed`, and `cancelled`;
- current recurrence values `none`, `daily`, `weekly`, and `monthly`;
- recurring tasks to include `due_at`;
- `updated_at` not to precede `created_at`;
- completed tasks to contain `completed_at`, while non-completed tasks must not;
- detail responses to match the requested task id; and
- unique, positive label identifiers in detail responses.

The contract also defines exact field allowlists for top-level list/detail objects and their nested authorization, filter, task, project, user, choice, and label records. A future decoder must reject unknown fields before invoking the typed acceptance policy. This preserves the current minimization boundary and prevents comments, reminders, operational metadata, credentials, or other unrelated server fields from silently entering the trusted native model.

A successful response decision does not authenticate transport and does not cache authority. Server-side `visible_to(user)` and `editable_by(user)` remain authoritative on every request.

## Android client foundation

The Android Development client is intentionally bounded:

- it targets the current Stable GLAZE UI V1.4 / `1.4.0` contract and records adoption as in progress rather than accepted conformance;
- it constructs only the documented native list/detail endpoint family and validates client-side filter bounds before transport;
- it contains a source-ready response-acceptance layer but no JSON/network implementation;
- it does not currently hold network authority;
- it does not hold or synthesize native identity/session credentials;
- it does not create a parallel authoritative task database;
- it does not implement local cache, mutation queues, background sync, notifications, reminders, or widgets;
- its UI surfaces these boundaries explicitly instead of representing unavailable capabilities as accepted.

## Follow-on milestones

1. Implement and accept the GoreeCloud Identity/session exchange for native clients without reusable application-wide credentials.
2. Add an exact-field list/detail decoder that rejects unknown fields before typed response acceptance.
3. Add authenticated read-only Android transport while preserving server authorization and private/no-store behavior.
4. Render only accepted list/detail responses without broadening authorization.
5. Add conditional mutation APIs using the existing editability rules plus explicit conflict/version semantics.
6. Add incremental synchronization cursors and bounded local-cache reconciliation.
7. Add notification/reminder registration without exposing another user's notification state.
8. Establish offline mutation queues only after conflict, revocation, and recovery behavior is defined and tested.
9. Add representative-device, accessibility, background-work, Wardveil, Privacy Shield, Everkeep, signing/provenance, and release acceptance.

## Acceptance boundary

The read-only server endpoints, Android request/response contracts, and first Android shell are Development evidence only. They do not establish production publication, GoreeCloud Identity acceptance, authenticated Android remote reads, background synchronization, offline write authority, GLAZE UI consumer conformance, Privacy Shield acceptance, Wardveil acceptance, Everkeep recovery acceptance, Release Candidate status, or Stable status.
