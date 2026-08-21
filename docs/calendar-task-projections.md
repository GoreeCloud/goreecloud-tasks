# GoreeCloud Calendar Task Projection Contract

## Purpose

GoreeCloud Tasks exposes a first-party read-only projection of scheduled tasks for GoreeCloud Calendar. Tasks remains authoritative for task content, authorization, project membership, completion, due scheduling, and recurrence. Calendar consumes projections and must not treat them as independent authoritative calendar events.

## Endpoint

`GET /api/v1/calendar/task-projections/`

Schema: `goreecloud.tasks.calendar-projections.v1`

Version: `1`

## Authorization foundation

The initial source-level implementation maps one bearer credential to one configured existing active Tasks account. The request cannot provide or override a username or user ID. Every request recalculates task visibility using `Task.objects.visible_to(identity)`.

This single-principal configuration is a development foundation. It is not the final GoreeCloud multi-user identity/credential design and is not approved for production activation. A later multi-user implementation may use individually scoped credentials or GoreeCloud Identity, but it must preserve exact principal binding, revocation behavior, and least privilege.

## Projection scope

Only tasks that satisfy all of the following are returned:

- visible to the configured Tasks principal;
- have a due date/time;
- are not Completed;
- are not Cancelled.

A project membership revocation therefore removes that project's task projections on the next request without changing or rotating the integration credential.

## Projected fields

Calendar receives only fields necessary to render and classify scheduled work:

- task ID;
- title;
- due timestamp;
- priority value and label;
- status value and label;
- recurrence value and label;
- project ID and name when project-scoped;
- task update timestamp.

Descriptions, comments, labels, reminders, creator/assignee account details, GoreeCloud operational notes, credentials, and other task content are deliberately excluded from this projection.

## Authority rule

Calendar must retain the projection's Tasks task ID as the source reference. It must not create a second authoritative event record merely to display the task. Future Calendar-to-Tasks creation, rescheduling, or completion actions must use separately versioned Tasks write contracts and server-side authorization.

## Failure behavior

- disabled integration: HTTP 404;
- invalid enabled configuration: HTTP 503;
- missing/incorrect bearer credential: HTTP 401;
- non-GET request: HTTP 405.

Successful responses use `Cache-Control: private, no-store` and `Vary: Authorization`.

## Production boundary

This contract does not provision a production integration account, token, secret file, Calendar deployment, Tasks deployment, network path, DNS/Caddy/NetBird/firewall configuration, monitoring, or backup behavior. Those remain separately validated and approval-controlled.
