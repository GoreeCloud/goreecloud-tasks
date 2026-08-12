# GoreeCloud Tasks — Disposable Manager Final-Topology Validation

## Purpose

I use this validation gate to exercise the GoreeCloud Tasks to GoreeCloud Manager integration in a disposable Docker topology that reproduces the planned same-VM production boundaries more closely than the existing loopback cross-application test.

This gate does not authorize or perform a production deployment. It uses only synthetic data and runtime-generated non-production credentials on an isolated GitHub Actions runner.

## Relationship to the Existing Cross-Application Gate

The existing `manager-cross-app` job remains a fast application-contract compatibility test. It starts both Django applications on runner loopback and verifies the real Tasks API, Manager adapter, Manager UI, data minimization, invalid credentials, schema rejection, and Viewer-membership revocation.

The new `manager-final-topology` job adds deployment-pattern evidence that the loopback test cannot provide. Both jobs are required and intentionally remain separate.

## Selected Manager Revision

The gate checks out GoreeCloud Manager at the immutable reviewed commit:

```text
6290203c6793cb4dd497b5d4481e226344c55eab
```

That revision contains the accepted read-only Tasks adapter and the Manager-side production-readiness plan. Updating the selected Manager revision requires normal review and must keep both integration gates green.

## Disposable Topology

The validation stack contains exactly three application/database containers:

```text
GoreeCloud Manager
      |
      | manager-tasks
      v
GoreeCloud Tasks web
      |
      | goreecloud-tasks-final-backend
      v
PostgreSQL
```

Manager also has its own isolated `goreecloud-manager-final-internal` network. PostgreSQL never joins `manager-tasks`, and Manager never joins the Tasks backend network.

The shared integration network is deliberately named:

```text
manager-tasks
```

The Tasks web container receives the stable alias:

```text
goreecloud-tasks
```

Manager therefore uses the planned production-pattern base URL:

```text
TASKS_API_URL=http://goreecloud-tasks:8000
```

The `manager-tasks` network is created with `internal: true` for the disposable test.

## Host-Port Boundary

The final-topology stack publishes no host ports for:

- PostgreSQL;
- GoreeCloud Tasks; or
- GoreeCloud Manager.

The gate inspects the running containers and fails if any effective host port binding exists.

This validates the application-to-application path only. It does not replace the separate future private user-facing `tasks.goreecloud.com` path through NetBird, AdGuard Home, Caddy, and application authentication.

## File-Backed Bearer Credential

The gate generates a random bearer token at runtime and writes it to a temporary host file. The token is never committed to Git and is not supplied through either application's direct-token environment variable.

Both application containers receive only the same read-only secret path:

```text
/run/secrets/goreecloud_tasks_manager_api_token
```

Tasks uses:

```text
TASKS_MANAGER_API_TOKEN_FILE=/run/secrets/goreecloud_tasks_manager_api_token
```

Manager uses:

```text
TASKS_ACCESS_TOKEN_FILE=/run/secrets/goreecloud_tasks_manager_api_token
```

The temporary source file uses mode `0640` and numeric group `20001`. Both application containers receive only that supplementary group for the validation. The gate confirms that the mounted file is readable by the intended runtime user, is not writable through the mount, retains the expected mode/group, and is not exposed through the direct token variables.

The numeric group is a CI validation value only. The production host owner, group, and GID remain subject to inspection and approval on the actual target runtime.

## Service Identity

The reusable synthetic fixture now hardens the disposable `goreecloud-manager-integration` identity so it matches the planned production identity requirements:

- active;
- no usable password;
- no email address;
- not staff;
- not superuser;
- no owned project;
- no private personal task; and
- Viewer-only access to the approved Shared project.

Both integration gates run `validate_manager_integration_identity --require-membership` before treating the fixture as valid.

## Authorization and Data-Minimization Evidence

The final-topology gate uses synthetic records for positive and negative cases. It proves that:

- one approved operational task is visible;
- an ordinary task in the same project is excluded;
- a Private-project task is excluded;
- normal-user personal work is excluded;
- completed operational work is excluded;
- unrelated personal work is excluded;
- the response reports the expected integration identity;
- description and comment markers do not appear;
- labels, creator details, and assignee details do not appear;
- invalid bearer credentials return HTTP 401;
- POST to the Manager API is rejected with HTTP 405; and
- Manager renders only the authorized operational record in its authenticated `/tasks/` page.

## Membership Revocation and Restoration

The gate deactivates the integration identity's Viewer membership without changing the token or Manager configuration. The next live Manager request and Manager UI must immediately lose the operational task.

The synthetic fixture is then reseeded, the identity validator must pass again, and the intended visibility must return. This proves both revocation and controlled restoration against the same running topology.

## Fail-Soft Evidence

The Manager container exercises its real adapter against these disposable failure cases:

- integration disabled;
- missing token file;
- empty token file;
- invalid bearer token;
- unreachable Tasks endpoint; and
- unsupported API schema version.

Manager must report a sanitized disabled, misconfigured, or unavailable integration state as appropriate while `/healthz/` remains healthy.

## Network-Isolation Evidence

The gate inspects live Docker state and fails unless:

- only the Tasks web container and Manager are attached to `manager-tasks`;
- PostgreSQL is attached only to the Tasks backend network;
- Manager is attached only to its own internal network and `manager-tasks`;
- the Tasks web container exposes the `goreecloud-tasks` alias on `manager-tasks`;
- Manager can resolve `goreecloud-tasks`; and
- Manager cannot resolve the Tasks `db` service.

This provides direct evidence that the integration does not grant Manager Tasks database reachability.

## Secret and Log Review

The gate fails if the runtime-generated bearer token appears in resolved Compose output or retained container logs. It also fails if the logs contain an apparent bearer Authorization value or the deliberately sensitive synthetic description/comment markers.

The checks are designed to retain useful CI evidence without retaining a reusable credential.

## What This Gate Does Not Prove

Passing `manager-final-topology` does not prove or authorize:

- the actual production `manager-tasks` Docker network;
- the actual production secret file, owner, group, or GID;
- a production `goreecloud-manager-integration` account;
- a production Viewer membership;
- a production bearer token or Vaultwarden item;
- the private `tasks.goreecloud.com` DNS/Caddy/NetBird path;
- production monitoring or alert delivery;
- production backup and restore;
- production rollback execution;
- production image security disposition; or
- production activation of either application.

Those remain separate approval-controlled gates in `manager-production-readiness-validation.md`.

## Files

The gate is implemented by:

```text
.github/workflows/ci.yml
scripts/manager_final_topology.compose.yml
scripts/manager_final_topology_assertions.py
scripts/validate_manager_final_topology.sh
scripts/manager_cross_app_fixture.py
scripts/validate_manager_cross_app.sh
```

## Acceptance Rule

This source-level topology increment is accepted only when all existing Tasks CI jobs and the new `manager-final-topology` job pass on the exact pull-request head and again on fresh `main` after merge.

A green final-topology gate advances production-readiness evidence. It does not change the production status from **Not approved; development and validation first**.
