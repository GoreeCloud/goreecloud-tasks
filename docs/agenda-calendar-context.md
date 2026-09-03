# GoreeCloud Tasks Agenda and Calendar Busy Context

## Status

**Development Candidate / source implementation. Not production accepted.**

This document records the first native seven-day GoreeCloud Tasks Agenda and its optional read-only GoreeCloud Calendar busy-time context. The Agenda is a Tasks planning surface; it does not make GoreeCloud Calendar data authoritative inside Tasks and it does not establish Stable qualification, release approval, or production deployment acceptance.

## Current Glaze boundary

GoreeCloud Tasks currently implements the repository-local GLAZE UI V1.0 (`1.0.0`) migration baseline. Under Platform Contract v0.2, the current required Glaze UI baseline is `1.1.0`, so Tasks remains `applicable-migration-required` and overall `nonconformant`.

This Agenda is composed against the application's current implemented `glz1` semantic layer so it remains coherent with the rest of the existing Tasks UI. That is migration evidence only. The Agenda must be revalidated as part of the required Glaze UI 1.1.0 application migration and must not be represented as current Glaze conformance before that work is complete.

## Purpose

The Agenda provides one seven-day view of active scheduled Tasks while optionally adding privacy-minimized Calendar availability context. The design deliberately keeps task due times and Calendar busy intervals semantically separate.

A task due time is a point in time. It is not treated as a duration, reservation, or time block. A true time-block planner remains gated on an explicit Tasks duration/scheduling model.

## Tasks authority boundary

The Agenda obtains scheduled work through the normal Tasks authorization model:

- `Task.objects.visible_to(user)` remains the visibility boundary;
- completed and cancelled work is excluded;
- only tasks due inside the seven-day local-time window are displayed;
- editability is recalculated through `Task.objects.editable_by(user)`;
- read-only shared work remains visibly read-only;
- no Calendar response can create, edit, complete, delete, assign, relabel, or reschedule a task.

## Calendar context boundary

The Agenda depends on the source-forward-ported Calendar busy-time consumer in the stacked `agent/calendar-busy-planning-v1` candidate rather than duplicating that integration logic locally.

The consumer implements the versioned `goreecloud.calendar.tasks-busy.v1` contract and is cross-application validated against the pinned GoreeCloud Calendar provider candidate revision `c7e40faa1357cd6befe4c6afc2c564fa06f86724`.

The client sends only a bounded timezone-aware start/end window plus the configured peer bearer credential in the `Authorization` header. It sends no Calendar username, subject, calendar href, collection identifier, event identifier, or event-content selector.

The accepted response is restricted to schema/version/generation metadata, the exact requested range, the returned count, and merged busy interval start/end timestamps. Unexpected fields fail closed. Event titles, descriptions, locations, UIDs, attendees, Calendar subjects, collection names, and other event content are not accepted into trusted Tasks planning input.

## Local recipient authorization

The optional outgoing integration is disabled by default. When enabled, `TASKS_CALENDAR_BUSY_USERNAME` binds the configured Calendar context to exactly one local active authenticated Tasks username. This recipient binding is checked before any Calendar request is made.

The local username is not transmitted to Calendar and is not a Calendar authorization assertion. Calendar independently owns the credential-to-subject and collection authorization mapping.

This paired configured-principal approach is a transitional Development mechanism. It does not represent completed GoreeCloud Identity delegated-user or service-identity acceptance.

## Transport and failure behavior

The underlying consumer limits requests and responses, requires HTTPS outside disposable loopback validation, rejects credential/query/fragment-bearing base URLs, uses explicit timeouts, supports protected file secrets, and fails closed on malformed or unsupported Calendar data.

Calendar context is optional. Disabled configuration, recipient mismatch, invalid configuration, transport failure, timeout, provider rejection, malformed JSON, schema mismatch, or other validation failure must leave the Tasks Agenda usable. The UI must not treat missing Calendar context as free time.

## Presentation rules

The seven-day surface:

- renders each day as a durable reading surface;
- presents scheduled Tasks separately from Calendar context;
- labels Calendar data generically as busy context;
- surfaces explicit disconnected, unauthorized, and unavailable states;
- preserves the current 48 px implemented interaction target contract;
- supports compact reflow, reduced transparency, and forced colors through the existing semantic layer;
- keeps `glaze.css` as the final loaded stylesheet so product-specific Agenda composition cannot override the shared compatibility contract.

External task-manager screenshots remain workflow and quality references only. The Agenda does not copy proprietary source code, wording, assets, icons, animations, or application layouts.

## Validation

The candidate includes regression coverage for authentication, seven-day filtering, active/visible Tasks authorization, local Calendar-recipient gating, graceful Calendar failure, generic busy-only rendering with event-content non-disclosure, and task due-time point semantics.

The stacked Calendar planning candidate already carries strict consumer tests and a pinned live cross-application contract workflow. The complete repository workflow suite remains required on the exact Agenda candidate head. Source/CI success does not establish production Identity, Privacy Shield, Wardveil Security, Everkeep, Mesh, Glaze UI 1.1.0 application conformance, deployment, release, or Stable acceptance.

## Rollback

No database migration or persistent Calendar state is introduced. Reverting the Agenda source removes the route and presentation while leaving native Tasks records and the independently reviewed Calendar busy-planning integration candidate unchanged.
