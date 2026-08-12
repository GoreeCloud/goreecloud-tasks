# GoreeCloud Tasks

Privacy-first, self-hosted, multi-user task and project management for personal,
family, collaborative, and GoreeCloud operational work.

## Status

**v0.1 development. Production deployment is not yet approved.**

The current implementation establishes the multi-user security boundary, usable
task and project workflows, explicit collaboration, labels, subtasks, scoped
search, the first GoreeCloud operational metadata, authorization-aware portable
JSON export, safe provider-neutral import execution, guarded user-archive
restoration, verified-format Todoist project CSV migration, a private
user-reminder/ntfy delivery foundation, schema-v2 notification/reminder
portability for user archives, disposable least-privilege ntfy integration
validation, and the approved open-source license. Production publication remains
blocked on the broader v0.1 acceptance requirements, including approved backup
and isolated restoration validation for the eventual production environment.

## Implemented Foundation

- Custom Django user model created before the first application migration.
- Individual accounts and private personal task boundaries.
- Private and explicitly shared projects.
- Project list, project creation, project detail, and owner-controlled settings.
- Explicit project membership administration by exact username.
- Project Manager, Member, and Viewer roles.
- Membership revocation without deleting membership history.
- Automatic membership revocation when a shared project becomes private.
- Authorization-aware task and label query helpers for read and edit access.
- Server-side mutation checks that prevent ordinary users from editing work they
  are not authorized to change.
- Historical task creator and assignee retention after project access is revoked,
  while new relationships still require current authorization.
- GoreeCloud P0 through P4 priorities with lifecycle status kept separate.
- Task creation through Quick Add and the full task editor.
- Task editing, completion, reopening, and deletion.
- Inbox, Today, Upcoming, and authorization-scoped Search views.
- Project-aware Quick Add limited to projects the current user may edit.
- Project-aware full task creation with authorized project preselection.
- Personal and project-scoped labels with server-side scope enforcement.
- Subtasks implemented as normal task records inside the parent's authorization
  scope.
- Initial GoreeCloud operational metadata for systems, services, environments,
  workload categories, blockers, resume conditions, operational prerequisites,
  and related records.
- Read-only presentation for tasks visible through Viewer membership.
- Authorized task detail pages with labels, subtasks, comments, activity, and
  optional operational metadata.
- User-attributed comments for users with task edit access.
- Material task and project activity events with the acting user recorded.
- Project activity history for sharing and membership changes.
- Data-minimized task edit history that records changed field keys instead of
  duplicating task descriptions, label names, blockers, or related-record text.
- Private user-specific reminder records with independent reminder preferences,
  lead time, local time-zone handling, delivery state, cancellation, and retry
  metadata.
- Reminder scheduling for any open task the current user may read, including a
  Viewer-owned personal reminder that does not expand the Viewer role into task
  edit permission.
- Delivery-time authorization re-checks that cancel a pending reminder instead
  of publishing task information after shared-project access is revoked.
- Pending-reminder cancellation when the source task is completed or cancelled.
- Non-identifying generated per-user ntfy topics under the
  `goreecloud-tasks-*` namespace.
- A dedicated ntfy publication boundary using environment/file-backed service
  credentials rather than user credentials stored in the application database.
- Data-minimized ntfy reminder messages containing only task title, due time when
  present, and project name when present.
- A `send_due_reminders` management command as a scheduler boundary without
  claiming that a production scheduler has been deployed.
- Disposable CI validation against a real authenticated ntfy instance with a
  write-only Tasks publisher, exact-topic read-only subscriber, deny-all default,
  namespace isolation, and live application-to-ntfy delivery verification.
- Versioned, authenticated JSON exports for user-owned data and owner-only
  project archives.
- Schema-v2 user archives that preserve notification preferences and reminders
  only when the reminder's task is already inside the user-owned archive scope.
- Backward-compatible schema-v1 user-archive restoration for core application
  data that predates reminder portability.
- Export scope that does not turn ordinary shared-project visibility into a
  bulk-export permission over another user's project.
- Source-neutral external-import records and an atomic executor that validates
  relationships before creating only private data owned by the importing user.
- Full-fidelity user-archive restoration with exact username resolution,
  collaborator-account requirements, clean-target enforcement, relationship
  validation, historical membership preservation, and atomic reconstruction.
- Authenticated Data portability recovery controls with explicit confirmation,
  UTF-8 JSON parsing, a 25 MiB upload limit, and private/no-store responses.
- Verified-format Todoist project CSV migration for tasks, subtasks, project
  labels, task notes/comments, priorities, and conservative schedule metadata.
- Todoist author/responsible values are preserved as source metadata and never
  create or assign GoreeCloud user identities.
- Django admin limited to account administration; private task/project/label
  content is not registered there.
- PostgreSQL-ready application configuration with SQLite for isolated tests.
- File-based secret support for the non-root application container.
- Dockerfile and Docker Compose development stack.
- Loopback-only development web-port publication and no published database port.
- Non-sensitive `/health/` endpoint.
- GitHub Actions checks for Django configuration, migration drift, application
  tests, Docker image build, PostgreSQL-backed migrations, Compose startup, live
  health verification, and disposable ntfy integration validation.
- GNU Affero General Public License v3.0 only (`AGPL-3.0-only`) selected for the
  original GoreeCloud Tasks application.

## Technology

- Python 3.13
- Django 5.2 LTS
- PostgreSQL 17 for multi-user Docker development and planned production use
- SQLite for isolated local development and automated tests
- Gunicorn
- Docker and Docker Compose
- GitHub Actions

Dependencies and container base images are deliberately version-pinned. Image
digests are included for the current development images so recreation does not
silently select different image content.

## Local Python Development

Create and activate an isolated Python environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --requirement requirements.txt
```

Set development-only configuration in the current shell:

```bash
export DJANGO_SECRET_KEY='replace-with-a-development-only-secret'
export DJANGO_DEBUG='true'
```

Initialize the database and create the first local administrative account:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

The default development address is `http://127.0.0.1:8000/`.

## Docker Development

Create the protected local configuration from the sanitized template:

```bash
cp .env.example .env
mkdir -p secrets
python -c "import secrets; print(secrets.token_urlsafe(64))" > secrets/django_secret_key
python -c "import secrets; print(secrets.token_urlsafe(48))" > secrets/postgres_password
chmod 600 .env
sudo chgrp 20001 secrets/django_secret_key secrets/postgres_password
chmod 640 secrets/django_secret_key secrets/postgres_password
```

The numeric group must match `APP_SECRET_GID` in `.env`. Docker Compose grants
that supplementary group to the non-root web process, allowing it to read the
mounted secret files without making those files world-readable or running the
application as root.

Validate, build, migrate, and start the stack:

```bash
docker compose config --quiet
docker compose build
docker compose up -d db
docker compose run --rm web python manage.py migrate --noinput
docker compose up -d web
docker compose ps
curl --fail http://127.0.0.1:8000/health/
```

The development database is reachable only on the internal Compose network.
The web service is published only on host loopback by default.

Do not commit `.env` or files under `secrets/`.

## Task Workflows

After signing in, the application provides:

- **Inbox** for active private personal tasks.
- **Today** for active accessible tasks due on the current GoreeCloud local date.
- **Upcoming** for active accessible tasks due after the current local date.
- **Search** across accessible active and completed task content, project names,
  labels, and the implemented GoreeCloud operational fields.
- **Quick Add** for low-friction capture into Inbox or an editable project.
- **Full editor** for title, description, project, assignee, priority, status,
  due date/time, labels, and optional GoreeCloud operational metadata.
- **Completion controls** for completing and reopening editable tasks.
- **Task detail** for authorized readers, with labels, subtasks, discussion,
  operational metadata when relevant, and activity history.
- **Remind me** shortcuts for scheduling private user-owned reminders without
  changing shared task content.

Shared-project Viewer membership remains read-only. Manager and Member roles may
modify shared project work according to the project authorization boundary.

## Labels

Labels are deliberately scoped instead of being globally shared across the
installation:

- **Personal labels** belong to one user and remain private to that user's
  personal task context.
- **Project labels** belong to one project and are visible only to users who can
  already read that project.
- Project Managers and Members can create project labels; Viewers remain
  read-only.
- Task forms expose only labels valid for the selected task scope.
- Labels that are still assigned to tasks cannot be deleted, preventing one
  label-management action from silently rewriting many task records.

## Subtasks

Subtasks use the same Task model and authorization engine as ordinary tasks.
Creation requires edit permission on the parent task. The new subtask inherits
the parent's project scope, and the model rejects cross-project, cross-user
private, self-parent, and cyclic relationships.

Because a subtask remains a normal task record, it can use the existing task
detail, completion, comment, activity, label, scheduling, and assignment
workflows.

## Search

Search begins with `Task.objects.visible_to(user)` and only then applies the
search expression. It therefore cannot be used to enumerate another user's
private task content or a project that the current user cannot access.

The initial search covers task title and description, project and label names,
creator/assignee usernames, assigned system and service, environment, workload
category, blocker, resume condition, and related change/document references.
Completed and cancelled accessible tasks remain searchable for later retrieval.

## GoreeCloud Operational Metadata

Ordinary personal, family, and collaborative tasks can leave all operational
fields empty. When a task represents GoreeCloud work, the optional advanced
section can record:

- assigned system;
- assigned service;
- environment or virtual machine;
- workload category;
- blocker;
- resume condition;
- backup prerequisite;
- recovery requirement;
- validation requirement;
- documentation requirement;
- related change record; and
- related GoreeCloud documentation.

The operational editor is separated from the core task form so infrastructure
terminology does not slow ordinary task capture.

## Project Workflows

The Projects area provides:

- **Project list** containing only projects the current user owns or may access
  through an active explicit membership.
- **Private-by-default project creation** with no automatic sharing.
- **Owner-controlled settings** for project name and Private/Shared visibility.
- **Project detail** with open tasks, ownership, visibility, task count, and the
  current user's effective access level.
- **Explicit membership administration** by exact username without presenting a
  directory of all user accounts.
- **Manager, Member, and Viewer roles** with owner-only membership and project
  settings administration.
- **Immediate access revocation** by deactivating membership records instead of
  deleting them, preserving the historical relationship.
- **Privacy-preserving unsharing** where changing a shared project to Private
  deactivates all active collaborator memberships.

Membership revocation removes future project visibility and edit authorization.
Existing tasks may retain a removed collaborator as their historical creator or
assignee so ordinary task updates and completion do not fail after access is
revoked. New assignments still require the project owner or an active member.

## Comments and Activity

Collaboration is deliberately scoped to content the user can already access:

- **Task comments** are visible with the task and are attributed to the author.
- **Comment creation** requires task edit access. Viewer membership remains
  read-only and cannot post comments.
- **Task activity** records creation, material edits, completion, reopening,
  deletion, and comment creation.
- **Project activity** records project creation/settings changes, sharing
  revocation, membership additions, role changes, removals, and project-scoped
  task events.
- **Material history only** is recorded; page views and low-value interaction
  telemetry are not written to the activity stream.
- **Sensitive-data minimization** keeps task descriptions, comment bodies, label
  names, blockers, and operational field content out of edit-event metadata.
- **Access revocation applies to history**. A removed project member loses future
  access to the project's task comments and activity along with the underlying
  project/task content.

The v0.1 interface creates comments but does not yet provide comment edit/delete
controls. Activity events are attributable history, not a general-purpose
analytics or surveillance log.

## Reminders and ntfy

The Notifications area provides a private reminder layer owned by each individual
user. Users can enable or disable reminders, choose a default lead time, maintain
their IANA time zone, enable ntfy delivery, schedule reminders for readable open
tasks, and cancel their own pending reminders.

Reminder ownership is deliberately independent from shared-task edit rights. A
Viewer may schedule a private reminder for a shared task the Viewer is currently
authorized to read; the reminder is not shared with the project and does not
allow that Viewer to edit the task.

Every user receives a generated `goreecloud-tasks-<random-suffix>` ntfy topic
that contains no username or email address. The topic is not a credential. The
external ntfy server must still grant the dedicated GoreeCloud Tasks service
identity write-only access to the approved Tasks topic namespace and the
individual ntfy subscriber read-only access to that user's exact topic.
GoreeCloud Tasks does not provision those ntfy identities, ACLs, tokens, or
subscriptions itself.

Immediately before a due reminder is published, the dispatcher checks the
current task authorization again. If the user has lost access after scheduling
the reminder, the reminder is cancelled rather than publishing content through a
downstream notification service. Completed and cancelled tasks also cancel their
pending reminders.

The ntfy message is data-minimized to task title, due time when present, and
project name when present. Task descriptions, comments, labels, blockers,
recovery notes, related records, and other detailed task content are excluded.
The publication token is deployment configuration and is never stored as user
data or shown in the interface.

Development exposes the dispatch boundary as:

```bash
python manage.py send_due_reminders
```

No production scheduler, ntfy service identity, real access token, server ACL,
user subscription, Vaultwarden record, or production deployment is created by
this repository feature. See `docs/feature-reminders-ntfy.md` and
`docs/ntfy-provisioning-validation.md` for the complete security, validation, and
future production-provisioning boundary.

## Data Portability

Authenticated users can open the Data area and download a machine-readable JSON
archive using the versioned `goreecloud.tasks.export` format. The current schema
version is `2`.

A user archive contains that user's private personal tasks and labels plus
projects the user owns and the application-owned records contained by those
projects. Projects owned by another user are excluded even when the exporter has
active shared-project access. This prevents normal collaboration permissions
from silently becoming bulk-export permissions.

Schema version 2 also preserves the user's persisted notification preferences and
reminders whose referenced tasks are already inside the same user-owned archive
scope. A personal reminder attached only to another owner's shared project is
not exported because the corresponding task is not part of the user's bulk
archive. The archive records only how many such reminder records were excluded,
without exporting the excluded task content. Project archives never include
private user notification preferences or reminder schedules.

The generated ntfy topic may be preserved as user configuration, but no ntfy
access token, publisher credential, password, session, or other reusable secret
is included. Transient reminder `last_error` delivery text is also excluded from
portable archives. Reminder scheduling state, delivery/cancellation timestamps,
attempt count, last-attempt timestamp, and historical timestamps are preserved.

Project archives are owner-only in v0.1. They preserve the selected project's
memberships, labels, tasks, task relationships, comments, activity history,
timestamps, and implemented GoreeCloud operational metadata. Compact user
references include only local user IDs and usernames; exports do not include
email addresses, password data, sessions, authentication tokens, or unrelated
account fields. Downloads are served as private, non-cacheable attachments.

The `imports` package provides a provider-independent normalization layer plus an
atomic execution boundary. Provider-normalized projects, labels, tasks, parent
relationships, priorities, statuses, due timestamps, and comments are validated
before persistence. The executor creates only private data owned by the importing
user, never creates accounts or memberships, and refuses project or personal-label
name collisions instead of silently merging records.

The Data portability area also provides guarded full-user-archive recovery.
Schema-v1 and schema-v2 `user_archive` files can be restored only to an
authenticated account whose username exactly matches the archive and whose owned
Tasks data set is clean. Every archived collaborator username must already exist
locally. Schema-v2 restoration additionally requires that the target user have no
existing Tasks reminders so private reminder state is not silently merged.
Restoration validates application relationships before reconstructing projects,
historical memberships, labels, tasks, subtasks, comments, activity, timestamps,
operational metadata, notification preferences, and eligible reminders inside one
outer transaction. An archived ntfy topic is rejected if another local account is
already using it. The restore path never creates user accounts and does not
overwrite or merge existing owned Tasks data. Legacy schema-v1 archives remain
restorable for the core data model but do not contain notification state.

The same area accepts a Todoist project CSV and imports it into a new private
GoreeCloud project. The verified mapping supports `task`, `section`, and `note`
rows; Todoist p1-p4; INDENT-based task hierarchy; task-content `@label` tokens;
and task notes as GoreeCloud comments. Provider author/responsible identity text,
section context, natural-language or recurring schedule expressions, deadlines,
duration values, and unknown source columns are preserved as source metadata when
there is no safe current native field. Only an explicit timezone-aware
ISO-8601/RFC3339 date is promoted to the native due timestamp. The provider file
never creates GoreeCloud identities, memberships, or shared projects.

## Tests

Run the local checks with:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Multi-user authorization tests are launch-blocking. The suite verifies private
user boundaries, explicit shared membership, Viewer read-only behavior,
deactivated memberships, administrator separation, assignment constraints,
Quick Add authorization, task mutation authorization, Today/Upcoming visibility,
project-list boundaries, owner-only project settings, explicit sharing, role
changes, membership revocation, historical task behavior after access is
revoked, comment authorization, comment output escaping, activity attribution,
project-history visibility, history isolation after access revocation, personal
and project-label boundaries, invalid cross-scope labels, protected used-label
deletion, subtask authorization and scope, search isolation, completed-task
retrieval, optional operational metadata, data-minimized label-change activity,
user-reminder authentication and ownership, non-identifying ntfy topics,
time-zone validation, authorization-scoped reminder task choices, Viewer-owned
reminders without edit escalation, inaccessible-task refusal, closed-task
cancellation, delivery-time authorization re-checks, disabled notification
preferences, authenticated data-minimized ntfy publication, failed-delivery
retry state, schema-v2 export behavior, notification-preference and owned-task
reminder portability, exclusion of reminder state tied only to another owner's
shared task, project-archive notification privacy, schema-v2 reminder
restoration, schema-v1 restoration compatibility, ntfy-topic collision refusal,
user/archive scope isolation, owner-only project export, relationship and
operational-field preservation, sensitive account-field omission,
provider-neutral private import execution, normalized comment persistence,
invalid-import rollback, import collision refusal, full user-archive
reconstruction, historical role and membership restoration, identity remapping,
restore target isolation, missing collaborator refusal, restore
confirmation/authentication, Todoist CSV delimiter/header validation, Todoist
section/label/priority/indent/note mapping, conservative due-date handling,
unknown-column preservation, authenticated Todoist web import, and Todoist
project-name collision refusal.

GitHub Actions additionally builds and starts the Docker Compose development
stack with PostgreSQL, applies migrations, verifies the live health endpoint, and
runs a disposable real-ntfy integration test against the application's actual
publisher path and intended least-privilege ACL model.

## Repository Structure

```text
goreecloud-tasks/
├── goreecloud_tasks/   # Django project configuration
├── accounts/           # Individual user identity, preferences, and request time zone
├── projects/           # Project ownership, memberships, roles, forms, and views
├── labels/             # Personal/project label scope and management
├── tasks/              # Core task models, forms, views, search, and authorization
├── collaboration/      # Task comments and attributable material activity
├── notifications/      # Private reminders, preferences, ntfy delivery, and dispatch command
├── portability/        # Versioned export and guarded archive restoration
├── imports/            # Source-neutral migration records, execution, and adapters
├── templates/          # Server-rendered application templates
├── static/             # CSS and future client-side assets
├── tests/              # Functional and authorization tests
├── docs/               # Architecture, feature, operating, and licensing documentation
├── .github/workflows/  # Continuous integration
├── LICENSE
├── LICENSE-NOTICE.md
├── compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
└── manage.py
```

Remaining milestone work includes production ntfy identity/ACL provisioning,
protected token installation, production scheduling and monitoring, end-client
notification validation, project-archive restore semantics if required,
additional GoreeCloud operational relationships, other integrations,
administrative disaster-recovery export, and the public application API when
those milestones require them.

## Production Boundary

This repository does not yet authorize production publication. Production use
still requires the project specification's security, authorization, persistent
storage, backup, restore, monitoring, reverse-proxy, upgrade, rollback, and
multi-user acceptance requirements to be completed and documented. The presence
of a user-archive restore function, provider CSV migration, application-side
ntfy reminder publisher, disposable ntfy integration test, or open-source
license is not by itself proof of a production backup, disaster-recovery process,
production scheduler, validated end-client delivery path, or production-ready
release.

## License

GoreeCloud Tasks is licensed under the **GNU Affero General Public License v3.0
only** (`AGPL-3.0-only`). Copyright (C) 2026 LaDamian Goree.

See `LICENSE` for the verbatim GNU AGPLv3 license text,
`LICENSE-NOTICE.md` for the project-specific license selection and copyright
notice, and `docs/licensing.md` for the licensing rationale, dependency boundary,
and public-release compliance requirements.

The repository remains private during development. Selecting the open-source
license does not authorize production deployment, public repository visibility,
or public service publication.
