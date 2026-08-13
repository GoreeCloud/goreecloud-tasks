# GoreeCloud Tasks — Upgrade and Rollback Validation

## Purpose

I use this validation to prove that a previously accepted GoreeCloud Tasks revision can be upgraded to the candidate revision against existing PostgreSQL application state and, if the candidate must be abandoned, returned to the previous accepted revision by restoring the pre-upgrade PostgreSQL backup and previous application image.

The gate is destructive only inside a disposable Docker Compose environment. It does not modify a production database, production backup repository, production deployment, DNS, Caddy, NetBird, Manager, ntfy, Vaultwarden, or any production credential.

## Rollback Model

The approved validation model is backup-backed rollback rather than blind reverse migration.

Before applying the candidate revision, the gate creates a real PostgreSQL custom-format dump from the previous accepted revision. That dump is the database rollback point. The previous accepted application image is also retained locally for the duration of the gate.

If rollback is required, the validation:

1. stops the candidate web application;
2. replaces the disposable database with a clean database;
3. restores the exact pre-upgrade PostgreSQL dump;
4. returns the Compose web image to the previous accepted application image;
5. verifies the previous revision has no pending migrations;
6. re-runs the previous revision's application-level recovery assertions;
7. compares the rolled-back normalized state exactly with the pre-upgrade state; and
8. starts the previous revision and requires the live health endpoint to succeed.

This intentionally avoids assuming that every future schema change can or should be reversed by running Django migrations backward. A deployment rollback must protect application data first.

## Revision Selection

The CI job checks out full Git history and passes explicit baseline and target revisions to the validation script.

For a pull request:

- the target is the exact pull-request head SHA; and
- the baseline is the pull request's base SHA.

For a push:

- the target is the pushed commit; and
- the baseline is the event's previous commit.

When a branch-creation push supplies an all-zero previous SHA, the script falls back to the target commit's first parent.

The baseline and target must resolve to different commits, and both must be present in the checkout.

## Synthetic Upgrade Dataset

The gate reuses the previous accepted revision's `scripts/backup_restore_fixture.py` as the compatibility contract for persisted v0.1 data.

The baseline fixture covers:

- individual accounts and password hashes;
- user preferences;
- Shared and Private projects;
- active and revoked memberships;
- private personal and shared operational tasks;
- assignments;
- personal and project-scoped labels;
- subtasks;
- shared comments and attributable activity;
- GoreeCloud operational metadata;
- notification preferences; and
- reminder schedule and retry state.

Using the baseline fixture during candidate validation is deliberate. It proves that the candidate can still interpret the application state accepted by the previous revision instead of validating only newly generated candidate data.

## Upgrade Sequence

The validation performs the following sequence.

### 1. Baseline preparation

The previous accepted revision is checked out into a detached temporary Git worktree.

The gate creates CI-only `.env` and file-backed secret sources in both the baseline and target checkouts. It refuses to run when the target checkout already contains the ordinary `.env`, `secrets/django_secret_key`, or `secrets/postgres_password` files.

The baseline Compose configuration is validated, the baseline web image is built and retained under a temporary rollback-only image tag, PostgreSQL is started, migrations are applied, and the synthetic recovery fixture is created.

### 2. Pre-upgrade evidence

Before the candidate is applied, the gate:

- runs the baseline semantic assertions;
- captures a normalized baseline snapshot;
- creates a non-empty PostgreSQL `pg_dump --format=custom --no-owner --no-acl` backup;
- verifies the dump is parseable by `pg_restore --list`;
- records the rollback artifact's SHA-256 digest; and
- starts the baseline application and verifies live `/health/` behavior.

### 3. Candidate upgrade

The baseline web container is stopped while the PostgreSQL database remains intact.

The candidate image is built and then run against the existing baseline database. The candidate must:

- apply all forward migrations successfully;
- pass Django system checks;
- report no remaining unapplied migration;
- satisfy the previous revision's application semantic assertions;
- reproduce the previous revision's normalized application snapshot exactly for the baseline data contract;
- satisfy the candidate revision's current recovery semantic assertions; and
- start successfully with a healthy live `/health/` endpoint.

A candidate that cannot read or preserve the previously accepted state fails the gate.

### 4. Rollback

After candidate validation, the gate confirms that the pre-upgrade dump's SHA-256 digest has not changed.

It then replaces the disposable database, restores the pre-upgrade dump with `pg_restore --no-owner --no-acl --exit-on-error`, returns the Compose web image to the retained baseline image, and verifies:

- baseline Django system checks;
- no pending baseline migrations;
- baseline authentication and authorization semantics;
- exact normalized state equality with the original pre-upgrade snapshot; and
- live baseline application health.

## CI Gate

The independent `upgrade-rollback` GitHub Actions job performs this complete sequence.

The checkout uses full Git history because the previous accepted revision is part of the test input. On pull requests, the checkout is pinned to the exact pull-request head rather than relying on an implicit synthetic merge checkout.

A failure in this job blocks the same CI workflow as the Django, ntfy integration, Manager cross-application, Manager final-topology, PostgreSQL backup/restoration, and Docker Compose gates.

## Safety Boundary

This validation uses only disposable CI data and CI-only secrets.

It does not:

- run against a production PostgreSQL database;
- use production task or user data;
- create a production backup;
- write to a production Kopia repository;
- provision production secrets;
- alter a production Docker stack;
- create a production DNS or Caddy route;
- alter NetBird or firewall policy;
- provision a Manager integration identity or token;
- alter ntfy production configuration;
- perform a production application upgrade; or
- authorize production deployment.

The temporary Compose project, PostgreSQL volume, worktree, snapshots, dump, CI `.env`, CI secret files, and retained rollback image tag are removed during cleanup.

## What This Evidence Proves

This gate provides repeatable source-controlled evidence that:

- the candidate revision can be applied to the previous accepted revision's persisted PostgreSQL application state;
- forward migrations can run before candidate startup;
- previously accepted v0.1 user/task state remains readable and semantically intact after upgrade;
- a real pre-upgrade PostgreSQL dump is usable as a rollback point;
- rollback can restore that database state and restart the previous accepted application revision; and
- rollback reproduces the normalized pre-upgrade application state exactly for the covered data contract.

## What This Evidence Does Not Prove

This disposable gate does not by itself prove that an eventual production upgrade or rollback is ready to execute.

It does not prove:

- the production database has a current approved backup;
- the production backup is independently stored and monitored;
- the production host has enough disk space for upgrade and rollback artifacts;
- the production image-retention policy preserves the exact rollback image;
- the final production secret owner/group/GID and file permissions are correct;
- production DNS, Caddy, NetBird, Manager, ntfy, or monitoring dependencies will remain available through an upgrade;
- production maintenance-window communication is complete;
- a production rollback meets an approved recovery-time objective; or
- a future intentionally destructive schema migration is acceptable merely because it can be represented in source control.

Those requirements remain part of separately approved target-runtime preflight and production change control.

## Governing Principle

I will not treat an application image rollback as sufficient when the database schema or data may have changed. The safe rollback unit is the compatible application revision plus the protected pre-upgrade data state required by that revision.
