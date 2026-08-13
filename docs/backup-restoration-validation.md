# GoreeCloud Tasks — PostgreSQL Backup and Restoration Validation

## Purpose

I use this validation to prove that the PostgreSQL-backed GoreeCloud Tasks application can be reconstructed from a real database backup without losing the application state or authorization relationships required for v0.1 recovery.

The validation is intentionally destructive only inside a disposable Docker Compose environment. It creates synthetic data, performs a real PostgreSQL `pg_dump`, replaces the disposable database with a clean empty database, restores the dump with `pg_restore`, and verifies the restored application state.

This closes an important gap between application-level JSON portability testing and database-level recovery testing.

## Production Boundary

This validation is production-representative evidence, not a production backup deployment.

It does not:

- configure a production backup destination;
- create a Kopia snapshot or repository;
- change the GoreeCloud VPS or future Infrastructure Services VM;
- create a production PostgreSQL dump;
- create a production scheduler;
- set retention rules;
- register Healthchecks, Uptime Kuma, or ntfy monitoring;
- configure off-site backup storage;
- create or expose production credentials;
- change Caddy, DNS, NetBird, Docker production networks, or firewall rules; or
- authorize production publication of GoreeCloud Tasks.

The eventual production backup must still satisfy the GoreeCloud Backup, Restore, and Recovery Policy and Standard, including protected storage, scheduling, retention, monitoring, independent recovery capability, and documented production restoration evidence.

## Validation Components

The permanent source-controlled validation consists of:

- `scripts/backup_restore_fixture.py` — creates deterministic synthetic application state, emits a normalized state snapshot, and validates restored application semantics;
- `scripts/validate_backup_restore.sh` — creates the isolated Compose environment and performs the PostgreSQL backup, destructive replacement, restoration, state comparison, and live health check; and
- the `backup-restore` GitHub Actions job — runs the complete destructive recovery exercise independently from the ordinary Docker Compose startup smoke test.

## Local Safety Boundary

The shell validation refuses to run when either of these already exists in the checkout:

- `.env`;
- `secrets/django_secret_key`; or
- `secrets/postgres_password`.

This prevents the destructive recovery exercise from silently reusing ordinary local development configuration.

The script creates its own CI-only configuration and synthetic secret files, uses a separate Compose project name, stores the temporary PostgreSQL dump and normalized snapshots under a temporary directory, and removes the disposable containers, volume, temporary dump, temporary snapshots, `.env`, and synthetic secret files during cleanup.

The validation must never be pointed at a production database.

## Synthetic Recovery Dataset

The fixture intentionally covers multiple application boundaries instead of restoring one trivial task.

It contains:

- three individual synthetic user accounts with restorable password hashes and user preferences;
- one Shared project;
- one Private project;
- one active Member membership;
- one historical inactive Viewer membership;
- a private personal task;
- a shared GoreeCloud operational task;
- a shared subtask;
- personal and project-scoped labels;
- task assignment relationships;
- a shared task comment;
- an attributable activity-history event with structured metadata;
- GoreeCloud operational metadata and recovery/validation flags;
- per-user notification preferences with non-identifying synthetic ntfy topics; and
- private user-specific reminder state including retry metadata.

All values are synthetic. No real GoreeCloud task content, usernames, passwords, notification tokens, or other reusable credentials are copied into the fixture.

## Backup Procedure Exercised

After migrations and fixture creation, the validation captures a normalized application snapshot and creates a PostgreSQL custom-format dump using:

```text
pg_dump --format=custom --no-owner --no-acl
```

The dump is required to be non-empty and parseable by `pg_restore --list` before destructive recovery begins.

The validation then stops the disposable web container and replaces the database with a newly created empty database. It explicitly verifies that the replacement database contains no public tables before restoration.

The backup is restored with:

```text
pg_restore --no-owner --no-acl --exit-on-error
```

Using `--no-owner` and `--no-acl` keeps the disposable validation focused on GoreeCloud Tasks database content and schema rather than GitHub runner-specific ownership or access-control metadata.

## Post-Restore Validation

After restoration, the gate verifies all of the following.

### Schema and startup

- Django system checks pass.
- No unapplied migration is required.
- The restored web application starts successfully.
- The live `/health/` endpoint responds successfully.

### Exact state preservation

The fixture creates one normalized JSON snapshot before backup and a second snapshot after restoration. The snapshots include primary keys, timestamps, user state, projects, memberships, labels, tasks, task relationships, comments, activity, notification preferences, and reminders.

The two normalized snapshots must match exactly. The temporary snapshots are not retained as workflow artifacts.

### Authentication and authorization

The semantic assertions additionally prove that:

- restored synthetic users can still validate their known synthetic passwords;
- the owner retains access to the private personal task;
- the active shared-project member retains access to the shared task;
- the active member does not gain access to the owner's private personal task;
- the inactive historical Viewer membership remains inactive;
- the revoked Viewer does not regain access to the shared task; and
- the Private project remains inaccessible to non-owners.

### Task and collaboration integrity

The assertions verify that:

- task creator and assignee relationships are preserved;
- task descriptions and operational fields are preserved;
- personal and project label relationships are preserved;
- the subtask parent relationship is preserved;
- the shared comment content and author are preserved; and
- attributable activity history and structured details are preserved.

### Notification and reminder integrity

The assertions verify that:

- notification preferences remain assigned to the correct users;
- generated-topic configuration is preserved exactly;
- reminder ownership remains assigned to the correct user and task;
- reminder schedule timestamps are preserved; and
- reminder retry metadata is preserved.

No ntfy access token is part of the database fixture or backup.

## Failure Behavior

The validation fails closed when any required step fails, including:

- Compose configuration or image build failure;
- PostgreSQL startup failure;
- migration failure;
- fixture creation or semantic-assertion failure;
- empty or unreadable PostgreSQL dump;
- failure to produce a truly empty replacement database;
- `pg_restore` failure;
- normalized state mismatch;
- authentication or authorization regression;
- reminder/history/relationship regression; or
- restored application health failure.

A failure in the independent `backup-restore` job blocks the same CI workflow that protects the other GoreeCloud Tasks development gates.

## What This Evidence Proves

This gate provides repeatable evidence that the current source revision, schema, PostgreSQL version, Compose database path, and application models can survive a database-level dump-and-restore cycle while preserving the synthetic state that represents the v0.1 recovery requirements.

It is materially stronger recovery evidence than an export/import unit test because it exercises the actual PostgreSQL database schema and PostgreSQL-native backup/restore tools.

## What This Evidence Does Not Prove

This gate does not by itself satisfy the final production backup acceptance gate.

It does not prove:

- that the eventual production PostgreSQL database is actually being backed up;
- that production backup jobs run on schedule;
- that a production backup is copied to an independent destination;
- that retention and expiration are correct;
- that backup encryption and repository access are correctly configured;
- that production monitoring receives backup success/failure heartbeats;
- that the production Docker host or VM can be rebuilt after total loss;
- that private DNS, Caddy, NetBird, Manager integration, or production ntfy dependencies are restored; or
- that the production recovery time and recovery-point objectives are acceptable.

Those controls require separately approved production deployment, backup, monitoring, and recovery work.

## Governing Principle

I will treat database recovery as proven only when restoration recreates the application state and the authorization behavior that gives that state meaning. A backup file existing is not sufficient evidence of recoverability.
