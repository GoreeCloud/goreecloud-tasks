# GoreeCloud Tasks Native Client API

**Status:** Development foundation  
**API family:** `/api/v1/client/`  
**Initial schema:** `goreecloud.tasks.client-task-list.v1`

## Purpose

This API is the first bounded application contract intended to support future first-party Android and Linux GoreeCloud Tasks clients.

The native client must remain a client of the existing GoreeCloud Tasks authorization and data model. It must not create a separate authoritative task database or bypass project membership, task visibility, editability, recurrence, assignment, collaboration, or recovery rules.

## Initial endpoint

`GET /api/v1/client/tasks/`

The endpoint uses the currently authenticated GoreeCloud Tasks user session and recalculates authorization on every request through `Task.objects.visible_to(user)`. The response also derives an `editable` flag through `Task.objects.editable_by(user)`.

This initial Development tranche deliberately does **not** introduce a mobile bearer-token database, device credential format, refresh-token protocol, GoreeCloud Identity acceptance claim, or background synchronization authority. Those are separate security and runtime milestones.

## Query parameters

- `state=active|completed|all` — defaults to `active`; active excludes Completed and Cancelled.
- `status=<task-status>` — optional exact current Tasks status value.
- `project=<positive-id>` — optional project filter; it never broadens the caller's visibility.
- `limit=1..200` — defaults to 100.

Unknown identity-selection parameters have no effect. The endpoint never accepts a username or user id as the authorization principal.

## List response boundary

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

Responses use `Cache-Control: private, no-store` and vary on the authenticated session cookie.

## Authorization behavior

Authorization remains dynamic. A project-membership revocation must remove the associated shared task from subsequent client responses immediately. Project filters cannot reveal a project the user otherwise cannot read. Read-only Viewer membership remains read-only in the native response through `editable: false`.

## Follow-on milestones

1. Add one-task detail retrieval with an independently minimized schema.
2. Define GoreeCloud Identity/session exchange for native clients without reusable application-wide credentials.
3. Add conditional mutation APIs using the existing editability rules plus explicit conflict/version semantics.
4. Add incremental synchronization cursors and bounded local-cache reconciliation.
5. Add notification/reminder registration without exposing another user's notification state.
6. Establish offline mutation queues only after conflict, revocation, and recovery behavior is defined and tested.
7. Build the Android client against these accepted APIs.
8. Add representative-device, accessibility, background-work, Wardveil, Privacy Shield, Everkeep, signing/provenance, and release acceptance.

## Acceptance boundary

This file and the initial read-only endpoint are source-level Development evidence only. They do not establish production publication, GoreeCloud Identity acceptance, Android client acceptance, background synchronization, offline write authority, Privacy Shield acceptance, Wardveil acceptance, Everkeep recovery acceptance, Release Candidate status, or Stable status.
