# GoreeCloud Tasks — Disposable Manager Final-Topology Validation

## Purpose

I use this validation gate to exercise the GoreeCloud Tasks to GoreeCloud Manager integration in a disposable Docker topology that reproduces the planned same-VM production boundaries more closely than the existing loopback cross-application test.

This gate does not authorize or perform a production deployment. It uses only synthetic data and runtime-generated non-production credentials on an isolated GitHub Actions runner.

## Relationship to the Existing Cross-Application Gate

The existing `manager-cross-app` job remains a fast application-contract compatibility test. It starts both Django applications on runner loopback and verifies the real Tasks API, Manager adapter, Manager UI, data minimization, invalid credentials, schema rejection, and Viewer-membership revocation.

The `manager-final-topology` job adds deployment-pattern evidence that the loopback test cannot provide. Both jobs are required and intentionally remain separate.

## Selected Manager Revision

The gate checks out GoreeCloud Manager at the immutable reviewed commit:

```text
863716464f1cf0466ec2208df23d59f30febfa28
```

That revision contains the accepted read-only Tasks adapter, Manager-side production-readiness plan, and sanitized integration-specific Tasks monitoring endpoint. Updating the selected Manager revision requires normal review and must keep both integration gates green.

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

The final-topology stack publishes no host ports for PostgreSQL, GoreeCloud Tasks, or GoreeCloud Manager. The gate inspects the running containers and fails if any effective host port binding exists.

This validates the application-to-application path only. It does not replace the separate future private user-facing `tasks.goreecloud.com` path through NetBird, AdGuard Home, Caddy, and application authentication.

## File-Backed Bearer Credential

The gate generates a random bearer token at runtime and writes it to a temporary host file. The token is never committed to Git and is not supplied through either application's direct-token environment variable.

Both application containers receive only the same read-only secret path:

```text
/run/secrets/goreecloud_tasks_manager_api_token
```

Tasks uses `TASKS_MANAGER_API_TOKEN_FILE` and Manager uses `TASKS_ACCESS_TOKEN_FILE` for that path. The temporary source file uses mode `0640` and numeric group `20001`. Both application containers receive only that supplementary group for the validation.

The numeric group is a CI validation value only. The production host owner, group, and GID remain subject to inspection and approval on the actual target runtime.

## Service Identity

The reusable synthetic fixture hardens the disposable `goreecloud-manager-integration` identity so it is active, non-interactive, has no email, is not staff or superuser, owns no project or private personal task, and has Viewer-only access to the approved Shared project.

Both integration gates run `validate_manager_integration_identity --require-membership` before treating the fixture as valid.

## Authorization and Data-Minimization Evidence

The final-topology gate proves that one approved operational task is visible while ordinary work, Private-project work, personal work, completed operational work, descriptions, comments, labels, creator details, assignee details, and unrelated records remain excluded. Invalid bearer credentials are rejected, state-changing requests are rejected, and Manager renders only the authorized record in its authenticated `/tasks/` page.

## Membership Revocation and Restoration

The gate deactivates the integration identity's Viewer membership without changing the token or Manager configuration. The next live Manager request and Manager UI must immediately lose the operational task. The synthetic fixture is then reseeded, the identity validator must pass again, and the intended visibility must return.

## Integration-Specific Monitoring Evidence

The selected Manager revision implements:

```text
GET /healthz/integrations/tasks/
```

The final-topology gate exercises this endpoint through Manager's real `tasks_snapshot()` adapter with the disposable production-pattern network and credential configuration.

The monitoring response is accepted only when it remains data-minimized. It may contain only the Manager service label, the `goreecloud-tasks` integration label, the broad adapter state, the sanitized monitoring condition, and the top-level healthy/unhealthy result. It must not expose bearer-token values, configured Tasks usernames, task titles or counts, project names, descriptions, comments, adapter detail text, secret paths, Authorization values, or raw upstream response bodies.

The gate verifies HTTP 200 for `healthy` and HTTP 503 for synthetic non-healthy conditions including `disabled`, `misconfigured`, `unreachable`, `authentication-rejected`, `authorization-denied`, `endpoint-unavailable`, `upstream-error`, and `schema-invalid`.

Manager's generic `/healthz/` must remain HTTP 200 while these integration-specific failure conditions are exercised. This preserves the distinction between Manager liveness and Tasks integration health.

A successful disposable monitoring assertion proves the source-level sanitized signal and production-pattern adapter behavior. It does not create an actual Uptime Kuma monitor, Healthchecks check, ntfy alert route, or production notification path.

## Fail-Soft Evidence

The Manager container exercises its real adapter against disabled integration, missing/empty token files, invalid bearer token, unreachable Tasks, authorization denial, endpoint unavailability, upstream HTTP failure, and unsupported API schema. The integration-specific endpoint must report the matching sanitized condition while the generic Manager health endpoint remains healthy.

## Network-Isolation Evidence

The gate inspects live Docker state and fails unless only the Tasks web container and Manager are attached to `manager-tasks`, PostgreSQL remains only on the Tasks backend network, Manager stays outside that backend network, the Tasks alias resolves from Manager, and the Tasks database service does not resolve from Manager.

## Secret and Log Review

The gate fails if the runtime-generated bearer token appears in resolved Compose output or retained container logs. It also fails if logs contain an apparent bearer Authorization value or deliberately sensitive synthetic description/comment markers.

## What This Gate Does Not Prove

Passing `manager-final-topology` does not prove or authorize the actual production `manager-tasks` network, production secret ownership/GID, production integration account or Viewer membership, production bearer token/Vaultwarden item, private `tasks.goreecloud.com` publication path, registration of an integration-specific production monitor, production alert delivery, production backup/restore, production rollback execution, production image security disposition, or production activation.

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

This source-level topology and monitoring-validation increment is accepted only when all existing Tasks CI jobs and `manager-final-topology` pass on the exact pull-request head and again on fresh `main` after merge.

A green final-topology gate advances production-readiness evidence. It does not change the production status from **Not approved; development and validation first**.
