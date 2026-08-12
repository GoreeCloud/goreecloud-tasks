# Core Task Workflows — v0.1 Development Note

This development increment adds the first usable task-management workflows on top of the established multi-user authorization foundation.

## Implemented

- Quick Add for Inbox or an editable project.
- Full task creation and editing.
- Task completion and reopening.
- Task deletion through explicit POST actions.
- Today and Upcoming views derived from the current GoreeCloud local date.
- Project-aware assignment validation.
- Read-only task presentation for Viewer access.
- Responsive task workflow interface.
- Functional tests for privacy, project permissions, scheduling views, and mutation authorization.
- GitHub Actions Docker Compose validation that builds the application image, starts PostgreSQL, applies migrations, starts the web service, and verifies the live health endpoint.

## Production Boundary

This increment validates development behavior only. It does not approve production deployment or private-service publication. Backup, restoration, monitoring, upgrade, rollback, security, and multi-user acceptance requirements remain production-readiness gates.
