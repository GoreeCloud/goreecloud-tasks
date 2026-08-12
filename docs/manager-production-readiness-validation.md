# GoreeCloud Tasks — Manager Production-Readiness Validation Plan

## Purpose

I use this plan to define the evidence that must exist before I activate the GoreeCloud Tasks integration in GoreeCloud Manager in production.

The plan covers private inter-service reachability, the final protected bearer-token mount, authorization, data minimization, monitoring, recovery, rollback, private user-facing publication, and post-change verification. It does not deploy either application, create a production service identity, generate a production token, grant a project membership, create a Docker network, change DNS, change Caddy, change NetBird, change the firewall, or publish a service by itself.

GoreeCloud Tasks remains authoritative for task content, project membership, the integration identity, and whether a Manager request is authorized. GoreeCloud Manager remains a read-only consumer.

## Production Boundary

This document is a production-readiness plan, not production authorization.

I will not treat any of the following as approved merely because the plan documents them:

- a live `goreecloud-manager-integration` Tasks identity;
- a production bearer token;
- a Vaultwarden secret item containing the active token;
- a host-side runtime secret file;
- a production Docker secret mount;
- a production `manager-tasks` Docker network;
- a `tasks.goreecloud.com` private DNS rewrite;
- a Caddy route;
- a NetBird policy;
- a firewall rule;
- an Uptime Kuma or Healthchecks production monitor;
- a production Tasks deployment; or
- a production Manager-to-Tasks activation.

Each production mutation remains separately approval-controlled and must be recorded when performed.

## Governing Requirements

The production design must preserve these existing GoreeCloud requirements:

- private by default;
- no direct public backend-port exposure;
- least-privilege Docker network membership;
- individual or purpose-specific identities instead of shared administrator accounts;
- explicit Viewer-only project authorization for the Manager service identity;
- reusable secrets outside source control and ordinary documentation;
- file-backed secrets when supported and operationally appropriate;
- restrictive host and container file permissions;
- application authentication even when network access is private;
- monitoring before a critical integration is treated as operational;
- validated backup and recovery procedures before production reliance; and
- a documented rollback path for every material production change.

## Target Same-VM Architecture

The planned long-term placement for both applications is the GoreeCloud Infrastructure Services VM. For that same-VM design, I will prefer a dedicated cross-stack Docker network for the application-to-application API instead of routing Manager through the public-facing or private-client Caddy path.

The planned logical paths are separate.

### Human Tasks access

```text
Approved NetBird client
        |
        v
AdGuard Home private DNS
        |
        v
https://tasks.goreecloud.com
        |
        v
Caddy
        |
        v
approved proxy Docker network
        |
        v
GoreeCloud Tasks web container
```

This path provides the private user-facing Tasks application and must satisfy the GoreeCloud Private Web Service Publication Standard.

### Manager-to-Tasks API access

```text
GoreeCloud Manager container
        |
        v
manager-tasks dedicated Docker network
        |
        v
GoreeCloud Tasks network alias
        |
        v
HTTP :8000 inside Docker only
        |
        v
/api/v1/manager/operational-tasks/
```

The backend HTTP hop is acceptable only while it remains entirely inside the approved same-host Docker network. The Manager API bearer token and Tasks authorization remain mandatory.

## Dedicated Cross-Stack Network

The planned cross-stack network name is:

```text
manager-tasks
```

The production network should be created deliberately as a shared external Docker network with an internal-only design when the final Docker host supports the required communication pattern.

Only the containers that require the integration should join it:

- GoreeCloud Tasks web container;
- GoreeCloud Manager container.

The following must not join `manager-tasks` merely for convenience:

- the Tasks PostgreSQL container;
- unrelated Manager integrations;
- Caddy unless a separately documented design requires it;
- Healthchecks;
- Uptime Kuma;
- ntfy;
- databases from another stack;
- administrative tooling; or
- unrelated application containers.

Tasks must continue to keep PostgreSQL on its application-specific backend network. Manager must not gain Tasks database connectivity through this integration.

## Stable Network Alias

The production Tasks web service should receive a deliberate alias on `manager-tasks`, for example:

```text
goreecloud-tasks
```

The intended Manager configuration for the same-VM direct service path is therefore:

```text
TASKS_API_URL=http://goreecloud-tasks:8000
```

The exact alias must be validated for uniqueness before activation. I will not rely on an ambiguous generic service name such as `web` across multiple stacks.

If Tasks and Manager later move to different Docker hosts or virtual machines, this same-VM Docker design no longer applies. Cross-host transport requires a new or amended design using an approved private network path and transport-security review before use.

## No Production Host Port Requirement

The production Tasks web container should not require a published host port merely so Manager can reach it.

The production acceptance target is:

- Tasks PostgreSQL: no host port;
- Tasks web: no direct public host port;
- Manager backend: no direct public host port;
- Caddy remains the controlled HTTPS gateway for private human access; and
- Manager reaches the Tasks API through `manager-tasks`, not through a public backend binding.

Temporary loopback bindings used by development or controlled validation do not become production publication automatically.

## Protected Bearer-Token Source

The authoritative identity and credential lifecycle remains documented in `manager-integration-credential-lifecycle.md`.

The planned same-VM runtime source is:

```text
/srv/docker/secrets/goreecloud-tasks-manager/manager-api-token
```

The planned container path is:

```text
/run/secrets/goreecloud_tasks_manager_api_token
```

Tasks will use:

```text
TASKS_MANAGER_API_TOKEN_FILE=/run/secrets/goreecloud_tasks_manager_api_token
```

Manager will use:

```text
TASKS_ACCESS_TOKEN_FILE=/run/secrets/goreecloud_tasks_manager_api_token
```

I will not use the long-lived production token through `TASKS_MANAGER_API_TOKEN` or `TASKS_ACCESS_TOKEN` when the file-backed mechanism is available.

## Final Secret Permissions

The final host ownership and group must be selected on the target Docker host and validated rather than guessed in advance.

The acceptance model is:

- the source directory is not broadly writable;
- the source file is owned by an approved administrative owner;
- the file is not world-readable;
- the file is not writable by application containers;
- Tasks can read the mounted file;
- Manager can read the mounted file;
- unrelated containers do not receive the mount;
- the token does not appear in `docker inspect` environment output;
- the token does not appear in resolved Compose output;
- the token does not enter a Docker image layer or build context; and
- the token can be rotated without making the source broadly readable.

A likely implementation is an administrative owner plus a dedicated numeric supplementary group and a source-file mode such as `0640`, but the actual owner, group, and GID must be recorded only after the target runtime is inspected and the final Compose design is validated.

I will not weaken the file to `0644` or an equivalent broad-read mode merely to avoid container permission work.

## Secret-Mount Validation

Before activation, I must collect evidence that both application containers can read the expected path while the secret remains inaccessible elsewhere.

Validation must include, without printing the token value:

```text
container identity and supplementary groups
stat metadata for the mounted secret path
test -r on the mounted secret path
confirmation that the mount is read-only
confirmation that the direct environment token variables are empty
confirmation that unrelated containers do not have the mount
```

A checksum or token length may be used for controlled comparison only when the method does not expose the secret and the retained output cannot be reused to authenticate.

## Tasks Service Identity Validation

Before the Tasks Manager API is enabled in production, the dedicated identity must pass:

```bash
python manage.py validate_manager_integration_identity \
  --username goreecloud-manager-integration \
  --require-membership
```

The production validation record must show that the identity:

- is active;
- has no usable interactive password;
- has no email address;
- is not staff;
- is not a superuser;
- owns no project;
- owns no private personal task;
- has only active Viewer memberships;
- has no active membership in a Private project; and
- has no active membership in an archived project.

The validation record must not contain the bearer token.

## Authorization Acceptance Dataset

Production-representative validation requires deliberate positive and negative cases.

I will prepare or identify at least:

1. one Shared project explicitly approved for Manager visibility;
2. one Shared project to which the integration identity has no membership;
3. one Private project that must remain invisible;
4. one ordinary non-operational task inside an otherwise visible project;
5. one completed or cancelled operational task that must remain excluded by the current API contract;
6. one personal Inbox/private task owned by a normal user;
7. one operational task with approved Manager-visible fields; and
8. deliberately sensitive marker content in a description or comment that must never appear in the Manager response.

No real private user content needs to be copied merely to satisfy the acceptance test when synthetic or purpose-created production-representative records can prove the boundary.

## Authorization Acceptance Results

The production record must prove that:

- the authorized operational task appears;
- the unauthorized Shared project does not appear;
- the Private project does not appear;
- personal work does not appear;
- ordinary non-operational work does not appear;
- completed and cancelled work remain excluded under the current contract;
- descriptions do not appear;
- comments do not appear;
- labels do not appear;
- account details do not appear;
- reminder and notification state do not appear;
- the configured service identity is reported as expected;
- an invalid bearer token is rejected;
- deactivating the Viewer membership removes the task from the next request without changing the token; and
- restoring the Viewer membership restores only the intended project visibility.

## Read-Only Acceptance

I must confirm that Manager cannot use this integration to:

- create a task;
- edit a task;
- complete or reopen a task;
- create a project;
- add or modify a project membership;
- post a comment;
- change reminders;
- change notification preferences;
- select another Tasks identity;
- enumerate arbitrary users; or
- invoke infrastructure actions through Tasks.

The production API remains GET-only.

## User-Facing Private Publication Validation

The Manager-to-Tasks internal network does not replace the separate private publication requirements for `tasks.goreecloud.com`.

Before users rely on Tasks, the private hostname must independently pass all applicable GoreeCloud private-service checks:

- approved AdGuard Home private DNS rewrite;
- resolution to the approved private GoreeCloud endpoint;
- valid trusted TLS certificate for `tasks.goreecloud.com`;
- Caddy route to the Tasks web container over the approved proxy network;
- explicit Caddy private-source restriction;
- NetBird access policy for approved clients;
- denial from an unapproved source;
- no unnecessary Tasks host-port publication;
- application login required for task content; and
- no reusable secret values in Caddy or application logs.

These checks are a production-readiness gate but their actual configuration changes remain separate approval-controlled actions.

## Monitoring Plan

The production integration must have monitoring for both application availability and the integration path.

### Tasks application availability

A private Uptime Kuma or equivalent monitor should verify the approved `https://tasks.goreecloud.com` health or application path from a location that legitimately has private access.

A health check proves application reachability only. It does not prove Manager authorization.

### Manager integration state

A separate integration-specific check must exercise the read-only Manager-to-Tasks request path using the approved credential without exposing the token in output.

The long-term monitoring implementation may use an approved scheduled validation command or delegated health check that reports only a sanitized state such as healthy, unavailable, authentication rejected, authorization denied, or schema invalid.

The production integration must not be considered fully monitored until this integration-specific signal exists and has an alert path.

### Alert delivery

The selected monitor should integrate with an approved GoreeCloud alert path such as Healthchecks and/or ntfy. The alert must not contain the bearer token or private task content.

## Logging and Secret-Exposure Validation

Before acceptance I must inspect recent Tasks, Manager, Caddy, and relevant monitoring logs and confirm:

- no bearer token appears;
- no Authorization header is logged;
- no password or session value appears;
- no unexpected private task description/comment content appears;
- no repeated authentication failures remain unexplained;
- no repeated network or proxy errors remain; and
- timestamps and error messages are sufficient to troubleshoot without exposing secrets.

## Backup Requirements

Production activation must not proceed until backup treatment is defined for both applications and the integration dependency.

The backup plan must cover, as applicable:

- Tasks PostgreSQL data;
- Tasks deployment/configuration files that are not reproducible from Git;
- Manager persistent data;
- Manager deployment/configuration files that are not reproducible from Git;
- non-secret network and deployment documentation;
- private service publication configuration;
- monitoring configuration; and
- the protected credential recovery record through the approved secret-recovery method.

The active bearer token must not be copied into an ordinary backup set merely because the application files are backed up.

## Recovery Requirements

A production-representative recovery test must prove that the integration can be reconstructed without undocumented memory.

The recovery sequence must verify:

1. Tasks data is restored according to the approved Tasks recovery procedure.
2. Manager data/configuration is restored according to the approved Manager recovery procedure.
3. The `manager-tasks` network dependency is recreated from documentation.
4. The Tasks service alias is restored.
5. The integration identity and Viewer memberships restore correctly from Tasks data.
6. The bearer token is restored from the approved protected recovery source only if reuse remains appropriate; otherwise it is rotated.
7. Both containers receive the expected read-only file mount.
8. The identity validator passes before the API is enabled.
9. Manager reaches only the approved Tasks API path.
10. Unauthorized projects remain excluded.
11. Monitoring returns to the expected state.
12. User-facing private publication still satisfies DNS, TLS, Caddy, NetBird, and authentication requirements.

A source-level archive restore or isolated unit test is useful evidence but does not by itself satisfy this production-representative recovery gate.

## Rollback Design

The integration has independent rollback controls so one failure does not require destructive Tasks data changes.

### Manager-side kill switch

```text
TASKS_ENABLED=false
```

This stops Manager network requests to Tasks.

### Tasks-side API kill switch

```text
TASKS_MANAGER_API_ENABLED=false
```

This disables the Manager endpoint while preserving ordinary Tasks use.

### Authorization rollback

Deactivate the integration identity's Viewer membership for an affected project to remove only that project's visibility.

Deactivate the service identity to suspend all Tasks authorization while preserving historical records.

### Credential rollback

Replace or rotate the bearer token through the protected lifecycle. Deleting only a mounted file is not sufficient revocation if Tasks still accepts the old configured value somewhere else.

### Network rollback

After Manager and the Tasks API are disabled, remove the integration-specific network attachment or network if it is the source of a production fault and no other dependency uses it.

### Publication rollback

The user-facing `tasks.goreecloud.com` Caddy/DNS/NetBird path must have its own known-good configuration rollback. The internal Manager network and user-facing private publication are separate controls.

## Rollback Triggers

I will roll back or disable the integration when any of the following occurs and cannot be immediately explained and corrected safely:

- unauthorized project visibility;
- private task leakage;
- description/comment leakage;
- token exposure;
- unexpected write capability;
- Manager access to the Tasks database;
- an unnecessary public backend port;
- broader Docker network membership than approved;
- inability to revoke access promptly;
- repeated unexplained authentication failures;
- repeated schema failures after an upgrade;
- broken recovery evidence;
- monitoring that cannot distinguish healthy from failed integration state; or
- a production change that cannot be reproduced from documented configuration.

Privacy or authorization failures require disabling the integration before convenience or availability is prioritized.

## Upgrade Compatibility Validation

Before either application is upgraded in production, I must confirm that the selected Tasks and Manager revisions remain compatible.

The existing disposable cross-application CI gate provides regression evidence for the selected source revisions. Production change control must additionally verify:

- the actual deployed Tasks revision;
- the actual deployed Manager revision;
- the expected `goreecloud.tasks.manager.v1` schema and version;
- file-backed secret compatibility;
- Docker network compatibility;
- no new API fields that weaken data minimization;
- no new network or port requirement; and
- rollback to the previous known-good revisions.

Manager must continue to fail soft if the Tasks schema becomes unsupported.

## Validation Phases

### Phase 1 — Source and design validation

Required before any production mutation:

- this plan reviewed;
- identity/credential lifecycle reviewed;
- selected Tasks and Manager commits recorded;
- Docker topology reviewed;
- planned secret ownership/mount reviewed;
- monitoring design selected;
- backup and recovery prerequisites identified;
- rollback controls confirmed.

### Phase 2 — Disposable or staging topology validation

Before production activation, I should reproduce the final topology without production secrets or private user data and prove:

- dedicated cross-stack network behavior;
- stable Tasks alias;
- no Tasks database reachability from Manager;
- no direct public host port requirement;
- file-backed secret readability by only the two required containers;
- real Manager adapter success;
- invalid-token rejection;
- authorization and membership-revocation behavior;
- data minimization; and
- fail-soft behavior when Tasks is unavailable.

This phase may become a permanent CI or staging gate through a separate implementation increment. This plan does not create that artifact automatically.

### Phase 3 — Approved production preflight

Only after production activation is separately authorized:

- verify backup currency;
- create/validate the service identity;
- grant only approved Viewer memberships;
- create the protected token and Vaultwarden record;
- create the final network and secret mounts;
- configure Tasks with the API initially disabled or otherwise controlled;
- configure Manager disabled;
- start/recreate services in the approved sequence;
- enable Tasks API;
- validate Tasks-side identity/configuration;
- enable Manager;
- run positive and negative authorization tests;
- validate private user-facing publication;
- validate monitoring;
- inspect logs;
- record evidence.

### Phase 4 — Post-activation observation

After successful preflight, monitor the integration closely through the first normal operating period and confirm:

- Manager remains healthy or fail-soft as designed;
- task visibility matches the approved project list;
- no unexpected authentication failures occur;
- no secret appears in logs;
- monitoring alerts work;
- backups complete; and
- rollback controls remain immediately available.

## Required Evidence Record

The production change record must include at least:

```text
Tasks deployed revision:
Manager deployed revision:
Tasks image reference/digest:
Manager image reference/digest:
Target host/VM:
Tasks private hostname:
Manager-to-Tasks transport:
Cross-stack Docker network:
Tasks network alias:
Tasks API container port:
Tasks public host port present: Yes/No
Manager public host port present: Yes/No
Secret source path reference:
Secret container path:
Secret owner/group/mode recorded without value:
Tasks secret read test: Pass/Fail
Manager secret read test: Pass/Fail
Identity validator: Pass/Fail
Authorized project test: Pass/Fail
Unauthorized Shared project test: Pass/Fail
Private project test: Pass/Fail
Personal task test: Pass/Fail
Description/comment leakage test: Pass/Fail
Invalid token test: Pass/Fail
Membership revocation test: Pass/Fail
Read-only behavior test: Pass/Fail
Private DNS test: Pass/Fail
TLS test: Pass/Fail
Approved NetBird client test: Pass/Fail
Unapproved-source denial test: Pass/Fail
Monitoring test: Pass/Fail
Backup prerequisite check: Pass/Fail
Recovery test reference:
Rollback test: Pass/Fail
Logs reviewed: Yes/No
Production approval/change record:
Responsible administrator:
Validation date/time:
```

No token value belongs in this record.

## Go/No-Go Criteria

Production activation is **GO** only when every applicable required result is documented as passing and no unresolved privacy, authorization, secret-handling, public-exposure, backup, recovery, or rollback blocker remains.

Production activation is **NO-GO** when any required control is untested, failed, ambiguous, dependent on undocumented manual state, or requires weakening an existing GoreeCloud security boundary.

A partially working integration is not production-ready.

## Relationship to Existing Disposable CI

The existing `manager-cross-app` GitHub Actions job proves the versioned API contract, real Manager adapter behavior, Manager UI rendering, data minimization, invalid-credential handling, unsupported-schema handling, and immediate authorization revocation using disposable loopback applications.

That gate remains valuable and must continue to pass, but it does not prove the final Docker network, final secret-file mount, production private hostname, Caddy/NetBird behavior, production monitoring, backup treatment, or production-representative recovery. Those controls remain intentionally separate.

## Governing Principle

I will activate the Tasks-to-Manager production integration only after I can prove that Manager receives exactly the operational visibility I approved, over exactly the private path I approved, using exactly the least privilege required, with a protected and revocable credential, no unnecessary public exposure, independent monitoring, and a tested recovery and rollback path.
