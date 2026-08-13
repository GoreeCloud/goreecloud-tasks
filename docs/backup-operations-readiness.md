# Backup Operations Readiness Validation

## Purpose

This document defines the source-controlled, non-activating GoreeCloud Tasks backup-operations readiness gate.

The gate exists to prove that the Tasks repository can execute a production-pattern PostgreSQL backup workflow with repeatable recovery points, integrity evidence, retention behavior, monitoring-state transitions, failure preservation, and restoration without creating or modifying a real production backup repository, production schedule, Healthchecks check, Kopia repository, production credential, or deployment.

Production remains **not approved** by this validation alone.

## Governing GoreeCloud Requirements

The validation follows the GoreeCloud Backup, Restore, and Recovery Policy and Standard and the GoreeCloud Kopia Strategy. Those records require, among other controls:

- database-safe backup creation rather than copying live database files blindly;
- at least one recovery copy independent from the protected primary system for critical information;
- multiple recovery points when delayed discovery of loss is reasonably possible;
- configured retention;
- automated backup execution where appropriate;
- monitoring of successful, failed, and missed backup jobs;
- actionable notifications that do not expose reusable secrets;
- repository and backup integrity verification;
- representative restoration and validation;
- recoverable credentials and recovery documentation;
- explicit documentation of scope, exclusions, schedule, retention, monitoring, limitations, and recovery dependencies.

A scheduled backup job alone is not considered sufficient recovery evidence.

## Source-Controlled Components

### `scripts/tasks_backup_job.sh`

This is a production-pattern backup wrapper, but it is not installed or scheduled by this change.

It requires explicit runtime configuration for:

- backup repository path;
- retained recovery-point count;
- monitoring heartbeat URL;
- optional Compose file, database service, database name, and lock path.

The wrapper:

1. refuses invalid retention values and non-HTTPS heartbeat endpoints outside disposable loopback validation;
2. prevents overlapping execution with `flock`;
3. sends a start heartbeat before backup work;
4. creates a PostgreSQL custom-format dump with `pg_dump`;
5. rejects an empty dump;
6. verifies dump readability with `pg_restore --list`;
7. writes a SHA-256 checksum and a data-minimized manifest;
8. atomically promotes a partial backup into a complete recovery point;
9. prunes only complete recovery points according to the explicitly configured retention count;
10. sends a success heartbeat after the finalized recovery point exists;
11. sends a failure heartbeat when PostgreSQL backup creation or dump validation fails;
12. removes incomplete partial recovery points on failure.

A successful backup whose success heartbeat cannot be delivered is treated as an operational failure instead of silently reporting complete success.

### `scripts/backup_operations_probe.py`

The disposable probe provides two test-only capabilities:

- a loopback heartbeat receiver that records only `start`, `success`, and `fail` events with receipt timestamps;
- a recovery-point age evaluator that classifies the repository as `healthy`, `late`, or `unavailable` using a caller-supplied maximum age.

The evaluator deliberately does not define the final production schedule or grace period. Those values must be selected from the actual production recovery objective and documented separately.

### `scripts/validate_backup_operations_readiness.sh`

The orchestrator creates only temporary CI state and performs the complete validation sequence.

## Validation Sequence

The gate performs the following checks:

1. refuses to overwrite an existing `.env` or development secret files;
2. creates synthetic CI-only secrets and an isolated temporary recovery repository;
3. validates shell and Python syntax plus the existing Docker Compose configuration;
4. starts a loopback-only disposable heartbeat receiver;
5. builds the candidate GoreeCloud Tasks image;
6. starts real disposable PostgreSQL;
7. applies real Django migrations;
8. seeds and validates the existing production-representative synthetic recovery fixture;
9. executes four successful PostgreSQL-native backups;
10. proves configured retention preserves exactly three complete recovery points;
11. verifies every retained SHA-256 checksum;
12. proves every retained custom-format dump is readable with `pg_restore --list`;
13. deliberately attempts a backup against a nonexistent disposable database;
14. requires that failure to return non-zero, send a failure heartbeat, remove the partial backup, and leave all previously valid recovery points unchanged;
15. proves a recent recovery point classifies healthy;
16. advances only the evaluator's logical clock and proves a missed-run condition classifies late;
17. performs a successful backup after the forced failure and proves retention remains correct;
18. requires the exact heartbeat sequence of healthy runs, forced failure, and recovery;
19. checks that synthetic Django and PostgreSQL secret values do not appear in backup metadata or heartbeat evidence;
20. restores the newest operational backup into the disposable database;
21. re-runs Django checks, migration checks, and semantic authentication/authorization recovery assertions;
22. starts the restored application and verifies the live `/health/` endpoint.

## What This Proves

This gate provides repeatable source-level and disposable-runtime evidence that GoreeCloud Tasks has a viable operational backup mechanism capable of:

- producing real PostgreSQL-native recovery artifacts;
- preserving multiple complete recovery points;
- applying an explicitly configured retention count;
- detecting a backup failure without destroying prior valid recovery points;
- distinguishing fresh and missed backup state;
- producing data-minimized start/success/failure monitoring signals;
- verifying dump checksums and PostgreSQL readability;
- restoring the resulting artifact into a clean application database;
- preserving the existing synthetic Tasks authorization and application semantics after recovery.

## What This Does Not Prove or Authorize

This increment intentionally does **not**:

- create a production GoreeCloud Tasks backup repository;
- select or configure the final production repository location;
- create a Kopia repository for Tasks;
- select a final production backup frequency;
- select final retention tiers or durations;
- create a systemd service or timer;
- create a cron job;
- register a production Healthchecks check;
- configure a production ntfy notification route;
- install production backup credentials;
- create or modify Vaultwarden items;
- modify production Docker, DNS, Caddy, NetBird, or firewall state;
- prove physical, host, provider, or geographic independence of a future production repository;
- prove repository-capacity monitoring;
- prove a production Kopia maintenance or integrity schedule;
- prove recovery of production secrets;
- prove recovery of the entire Infrastructure Services VM;
- prove production DNS, HTTPS, Manager, ntfy, monitoring, or networking recovery;
- deploy or activate GoreeCloud Tasks in production.

The temporary CI repository is separate from the disposable PostgreSQL Docker volume, which proves application-level repository separation inside the test runner. It does **not** represent an off-host, off-VM, off-provider, or off-site production copy.

## Production Go/No-Go Evidence Still Required

Before the production backup criterion can be marked satisfied, the target environment still requires explicit evidence for at least:

- final protected scope and exclusions;
- database-native production backup output path;
- final repository technology and physical/logical location;
- repository independence from the Tasks VM and primary data;
- approved encryption and credential-recovery method;
- production backup frequency based on acceptable data-loss objectives;
- production retention based on delayed-loss and corruption scenarios;
- multiple real recovery points;
- production automation and overlap protection;
- Healthchecks or other approved missed/failed-job monitoring;
- approved notification receipt;
- repository capacity monitoring;
- repository integrity verification;
- representative restore from the production repository;
- restored ownership, permissions, application state, authentication, authorization, networking, DNS, HTTPS, monitoring, and backup resumption as applicable;
- independent recovery documentation;
- any required off-host or off-site copy;
- rollback/removal procedure for backup automation and monitoring.

Until that target-environment evidence exists, GoreeCloud Tasks production backup storage, scheduling, retention, monitoring, and independent protection remain outstanding and separately approval-controlled.
