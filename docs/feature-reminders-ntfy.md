# User reminders and ntfy notification boundary

## Purpose

This feature adds private, user-specific task reminders and the first GoreeCloud Tasks notification-delivery integration without making ntfy an authorization boundary, permanent system of record, or substitute for task history.

The application owns reminder scheduling state. ntfy is used only as an approved delivery channel after GoreeCloud Tasks has re-checked the current user's task authorization.

## User-specific reminder model

Each reminder belongs to exactly one GoreeCloud Tasks user and one task. A reminder stores its scheduled time, delivery state, retry metadata, and cancellation state. Other project members do not receive access to that reminder merely because they can read the same task.

Reminder ownership is intentionally separate from task edit permission. A Viewer may schedule a private reminder for a shared task the Viewer is currently authorized to read. That action does not grant edit access to the task and does not modify shared task content.

New reminders cannot be created for completed or cancelled tasks. Closing a task cancels its pending reminders. A user may cancel only that user's own reminder.

## Per-user preferences and time zone

Each user has independent notification preferences for:

- whether task reminders are enabled;
- the default reminder lead time used by the scheduling interface;
- whether ntfy delivery is enabled; and
- the user's existing GoreeCloud Tasks IANA time-zone setting.

The application activates the authenticated user's stored time zone for each request so due times and reminder input are interpreted in the user's local context while database timestamps remain timezone-aware.

## Topic design

Each user receives an application-generated topic such as:

```text
goreecloud-tasks-<random-suffix>
```

The topic does not contain the user's username, email address, IP address, or another personal identifier. The topic string is not treated as a credential. Authentication and server-side ntfy access control remain required.

The intended server-side least-privilege model is:

```text
GoreeCloud Tasks service identity
  -> goreecloud-tasks-* topic namespace
  -> write-only publication permission

Individual ntfy user identity
  -> that user's exact generated GoreeCloud Tasks topic
  -> read-only subscription permission
```

The application does not create ntfy users, tokens, or ACLs. Those remain external service-administration actions and must be provisioned through the approved ntfy identity and access process.

## Publisher credential boundary

GoreeCloud Tasks uses one dedicated ntfy service access token for publication. The token is deployment configuration, not application user data.

Supported configuration is:

```text
NTFY_BASE_URL
NTFY_ACCESS_TOKEN or NTFY_ACCESS_TOKEN_FILE
NTFY_TIMEOUT_SECONDS
NTFY_TOPIC_PREFIX
TASKS_BASE_URL (optional)
```

The direct token value and token-file setting are mutually exclusive. No ntfy publisher token is committed to Git, stored in the Tasks database, included in exports, or displayed in the user interface.

Long-lived and production deployment should use a protected file-backed secret according to the approved GoreeCloud secret-storage process. The current development repository does not contain a real ntfy credential.

## Authorization re-check at delivery time

A stored reminder is not permanent permission to receive task content.

Immediately before publication, the dispatcher verifies that:

1. the reminder is still pending;
2. the task is not completed or cancelled;
3. the user still has normal application visibility to the task; and
4. the user's reminder and ntfy preferences are enabled.

If shared-project membership was revoked after the reminder was created, the dispatcher cancels the reminder instead of publishing task information. ntfy is therefore downstream of the current GoreeCloud Tasks authorization decision rather than a replacement for it.

## Data minimization

An ntfy reminder contains only the information needed to identify the scheduled work:

- task title;
- due time when present; and
- project name when present.

The publisher intentionally excludes task descriptions, comments, labels, blockers, recovery notes, validation notes, documentation references, related change records, and other detailed or operational task content.

When `TASKS_BASE_URL` is configured for an actually deployed environment, the notification may include a click target back to the authenticated task-detail page. Leaving that setting blank prevents development from claiming an undeployed address.

## Priority mapping

The current message-priority mapping is:

| GoreeCloud Tasks | ntfy |
| --- | --- |
| P0 — Critical | urgent |
| P1 — Urgent | high |
| P2 — High | default |
| P3 — Standard | low |
| P4 — Low | min |

This keeps the highest notification urgency reserved for P0 critical operational work and avoids marking routine P3/P4 work as urgent.

## Dispatch command

Due reminders are processed by:

```bash
python manage.py send_due_reminders
```

An optional bounded batch size may be supplied:

```bash
python manage.py send_due_reminders --limit 100
```

The command is a scheduler boundary, not a production scheduler. No cron job, systemd timer, Celery worker, external automation, or production service schedule is created by this development increment.

The dispatcher records send attempts and a sanitized failure message. Failed publications remain pending for a later retry. On PostgreSQL, candidate rows are locked while their delivery state changes to reduce duplicate publication when scheduler processes overlap.

## User interface

Authenticated users receive a Notifications area for:

- enabling or disabling reminders;
- selecting their default lead time;
- setting their IANA time zone;
- enabling ntfy delivery;
- viewing their generated ntfy topic;
- scheduling a reminder for any currently readable open task; and
- cancelling their own pending reminders.

Task lists provide a `Remind me` shortcut that opens the Notifications page with the selected task prefilled. The default reminder time uses the user's configured lead time before the task due time, or a short future fallback when a useful pre-due time cannot be selected.

## Data portability

The current `goreecloud.tasks.export` schema version is 2.

Schema-v2 user archives preserve the user's notification preferences and reminders only when the referenced task is already inside that user's existing user-archive ownership scope. A reminder attached only to another owner's shared project is excluded rather than widening the archive to include content the user does not own. Project archives do not contain private user notification state.

The generated ntfy topic may be preserved as application configuration, but publisher credentials and other reusable secrets are never exported. Schema-v1 user archives remain restorable for their original core-data scope and contain no reminder/notification state.

## Testing boundary

Regression coverage verifies:

- authentication for notification settings;
- non-identifying generated topics;
- time-zone validation;
- authorization-scoped task choices;
- Viewer-owned private reminders for readable shared tasks without edit escalation;
- rejection of inaccessible tasks and past reminder times;
- reminder ownership on cancellation;
- cancellation when a task closes;
- successful due-reminder state transitions;
- re-checking shared-task authorization immediately before dispatch;
- disabled delivery preferences;
- authenticated ntfy publication;
- message data minimization;
- safe retry state after publication failure; and
- schema-v2 notification/reminder export and guarded restoration.

GitHub Actions additionally runs an isolated live integration test against a disposable authenticated ntfy server. That test exercises the real GoreeCloud Tasks HTTP publisher and verifies the intended write-only publisher/read-only exact-subscriber ACL boundary, unauthorized denial, namespace isolation, and delivered-message minimization.

See `docs/ntfy-provisioning-validation.md` for the reviewed production provisioning workflow, token rotation/revocation procedure, and exact isolated validation design.

## Current limitations and production boundary

This development state does **not**:

- create the real GoreeCloud Tasks ntfy service identity or token;
- create production ntfy ACLs for `goreecloud-tasks-*`;
- subscribe a production user or device to a generated topic;
- create or modify Vaultwarden credentials;
- create a production scheduler;
- deploy GoreeCloud Tasks;
- modify Caddy, DNS, NetBird, or the production Docker stack;
- prove that a mobile operating system displayed a published message;
- make ntfy a permanent reminder history or audit record; or
- satisfy the production backup, restoration, monitoring, upgrade, rollback, or multi-user acceptance gates.

The repository now continuously validates the application-to-ntfy publisher and ACL model against a disposable ntfy instance. That evidence does not authorize or replace the separate production provisioning and end-client validation steps.

Production enablement requires a separate approved provisioning and validation step for the dedicated ntfy publisher identity, per-user subscriber ACLs, protected token storage, scheduler execution, end-to-end delivery, failure handling, monitoring, backup/recovery implications, and documentation.
