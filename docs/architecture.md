# GoreeCloud Tasks Architecture

## Purpose

I am building GoreeCloud Tasks as a privacy-first, self-hosted, multi-user task
and project-management platform for personal, family, collaborative, and
GoreeCloud operational work.

This document records the implementation shape of the current v0.1 foundation.
The formal GoreeCloud project specification remains the authoritative
project-level requirements record.

## Identity and Privacy Boundary

Every person uses an individual `accounts.User` identity.

Private personal tasks belong to their creator and have no project. Shared
content lives in an explicitly shared project. A deployment containing several
users does not make one user's private workspace visible to the others.

Project roles are:

- **Manager** — may manage project task content.
- **Member** — may create and edit project task content.
- **Viewer** — may read shared project task content but not edit it.

The project owner has implicit project authority and does not require a
membership row.

Task reads and writes should use `Task.objects.visible_to(user)` and
`Task.objects.editable_by(user)` rather than arbitrary object identifiers.
Future views and APIs must preserve this object-level authorization boundary.

Django staff or superuser status does not automatically broaden these normal
application query helpers. Server and database administrators remain capable of
backend access by virtue of infrastructure authority; that authority is
separate from ordinary application content permissions.

## Initial Data Model

The current foundation contains:

- **User** — individual identity, display name, and timezone.
- **Project** — owner, visibility, archive state, and explicit memberships.
- **ProjectMembership** — user, role, and revocable active state.
- **Task** — creator, optional assignee, optional project, priority, status,
  schedule, and completion metadata.

Personal tasks may only be assigned to their creator. A shared-project task may
only be assigned to the project owner or an active member.

## Priority and Status

GoreeCloud operational priority uses the authoritative five-level model:

1. P0 — Critical
2. P1 — Urgent
3. P2 — High
4. P3 — Standard
5. P4 — Low

Priority and lifecycle status remain separate. Initial statuses are Planned,
Ready, In Progress, Blocked, Delayed, Waiting, Completed, and Cancelled.

## Deployment Boundary

The repository includes a development Docker Compose stack with PostgreSQL.
The application container runs as an unprivileged user, secrets are supplied
through protected files, the database has no host-published port, and the web
port binds to loopback only.

This does **not** authorize production publication. Before production use I
will separately validate authentication, authorization, container security,
persistent storage, backup, restoration, monitoring, reverse-proxy
publication, and multi-user privacy boundaries.

## Next Feature Milestone

The next application milestone should add:

- Quick Add.
- Task create/edit/complete/reopen workflows.
- Today and Upcoming views.
- Project creation and membership management.
- Task assignment.
- Comments and material activity history.
- The first GoreeCloud operational metadata fields.
