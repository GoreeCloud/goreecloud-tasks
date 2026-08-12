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

## Docker Validation Finding and Correction

The first full Compose runtime validation successfully built the application image and started a healthy PostgreSQL container, but the migration container could not read `/run/secrets/django_secret_key` while running as the non-root GoreeCloud application user. The source secret files were intentionally protected with owner-only permissions, and those permissions remained too restrictive for the mounted file inside the web container.

The development stack now preserves the non-root application boundary while granting only group-read access to the secret files. The host-side secret files use numeric group `20001` by default with mode `0640`, and the web service receives that same supplementary group through Docker Compose. The files remain non-world-readable and the application continues to run without root privileges.

## Production Boundary

This increment validates development behavior only. It does not approve production deployment or private-service publication. Backup, restoration, monitoring, upgrade, rollback, security, and multi-user acceptance requirements remain production-readiness gates.
