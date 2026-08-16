# GoreeCloud Tasks and Manager Cross-Application Validation

## Purpose

This document defines the disposable integration-validation boundary between GoreeCloud Tasks and GoreeCloud Manager.

The goal is to prove the real application-to-application contract without creating or modifying production infrastructure, production credentials, NetBird policy, DNS, Caddy routes, Vaultwarden records, ntfy configuration, or a production GoreeCloud Tasks deployment.

## Integration Boundary

GoreeCloud Manager consumes the dedicated Tasks endpoint:

`GET /api/v1/manager/operational-tasks/`

The Tasks endpoint maps one deployment-configured bearer token to one existing Tasks user. That user remains the authorization principal. Every returned task is selected through the normal `Task.objects.visible_to(identity)` boundary before the Manager-specific operational filter is applied.

The integration does not create a privileged bypass around Tasks authorization. Staff or superuser state does not expand the integration scope, and project membership revocation removes future task visibility without requiring the bearer token itself to change.

## Disposable CI Architecture

The `manager-cross-app` GitHub Actions job:

1. Checks out GoreeCloud Tasks from the commit being validated.
2. Checks out a deliberately pinned GoreeCloud Manager commit into an isolated subdirectory.
3. Creates separate Python virtual environments for Tasks and Manager so their independently pinned dependency sets do not overwrite one another.
4. Initializes a disposable SQLite Tasks database and creates synthetic users, projects, memberships, operational tasks, ordinary/private/completed tasks, and sensitive test content.
5. Starts a real GoreeCloud Tasks development server on runner loopback only.
6. Initializes a disposable GoreeCloud Manager SQLite database and local authentication account.
7. Starts a real GoreeCloud Manager development server on runner loopback only.
8. Exercises the Manager adapter over HTTP against the live Tasks API.
9. Authenticates to the live Manager web application and verifies the Tasks page renders the authorization-scoped operational task.
10. Revokes the synthetic integration user's Viewer membership in Tasks and verifies that both the live API and Manager UI immediately lose the task.
11. Destroys the disposable databases and processes when validation completes.

No CI server is published beyond runner loopback.

## Validated Security and Contract Properties

The cross-application validation proves that:

- the configured bearer token resolves to the expected Tasks integration identity;
- a valid credential returns only active GoreeCloud operational tasks inside projects the integration identity can currently read;
- ordinary shared tasks, private owner tasks, personal tasks, completed operational tasks, and unrelated users' tasks are excluded;
- task descriptions and comments containing synthetic sensitive markers do not appear in the Manager API response or Manager Tasks page;
- labels, creator/assignee account details, comments, and descriptions are absent from the approved Manager task object;
- invalid bearer credentials receive HTTP 401 and Manager reports the credential rejection through its fail-soft integration state;
- the response uses the expected `goreecloud.tasks.manager.v1` schema and version;
- Manager rejects an unsupported schema and reports a fail-soft unavailable state instead of consuming ambiguous data;
- Manager's normalized summary and task data match the live Tasks response;
- revoking the integration user's project membership removes future visibility immediately while leaving the integration token unchanged;
- both applications remain independently startable and health-checkable during the integration test.

## Data Minimization

The Manager API intentionally exposes only the operational fields approved for central visibility. It does not expose a complete Tasks record or database representation.

Synthetic CI fixtures place unique marker text in a task description and task comment. The integration test fails if either marker appears in the API payload or Manager UI. This creates an explicit regression gate against accidental expansion of the data surface.

## Credential Handling

The disposable validation token is a fixed CI-only nonproduction value committed only as test configuration. It has no authority outside the disposable runner database because the corresponding synthetic Tasks account exists only during the job.

Production credentials must remain outside source control and must use the protected environment/file-backed configuration described by the Tasks Manager API and Manager integration documentation.

## Pinned Manager Reference

The cross-application job pins the Manager repository to a reviewed commit rather than following `main` implicitly. This keeps the Tasks build reproducible and prevents unrelated future Manager changes from silently changing the software under test.

The current reviewed Manager baseline is:

```text
b4bc055aa6b4143a61a8073442fc9ba311b3e53e
```

That revision is the accepted Manager `main` state after the bounded runtime and integration-fault-isolation stabilization work. Both the direct application-to-application validation and the disposable final-topology validation use the same reviewed Manager revision so the two evidence paths cannot silently diverge.

When the Manager integration contract or accepted Manager runtime changes intentionally, the pinned Manager commit must be advanced through a reviewed GoreeCloud Tasks change after compatibility is verified. An unmerged Manager feature or stabilization branch must not become the Tasks validation baseline merely because it exists.

## CI Execution Baseline

The primary Tasks CI workflow uses Ubuntu 24.04 explicitly instead of floating `ubuntu-latest`. Python application jobs use CPython 3.13.14, matching the Python release named by the digest-pinned Tasks application image. Jobs use bounded timeouts, and dependency installation paths run `pip check` where Python packages are installed directly.

This keeps routine Tasks validation, ntfy integration validation, and the live Tasks/Manager contract closer to the reviewed runtime baseline while leaving the more specialized Docker/recovery workflows responsible for their own production-pattern evidence.

## Production Boundary

Passing this job proves compatibility between the selected Tasks and Manager revisions in a disposable environment. It does **not** approve or perform:

- production GoreeCloud Tasks deployment;
- production GoreeCloud Manager reconfiguration;
- a real integration service account or project membership;
- production bearer-token creation or installation;
- Vaultwarden secret creation;
- cross-stack Docker networking;
- DNS, Caddy, NetBird, firewall, or port changes;
- production monitoring or scheduling;
- production backup, restoration, upgrade, rollback, or disaster-recovery validation.

Those remain separate approval-controlled production-readiness activities.
