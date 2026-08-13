# GoreeCloud Tasks — Manager API Integration

## Purpose

GoreeCloud Tasks exposes a deliberately narrow read-only API for GoreeCloud Manager so Manager can display approved operational work without direct database access and without gaining a general application-administrator bypass around Tasks authorization.

The endpoint is:

```text
GET /api/v1/manager/operational-tasks/
```

The response schema identifier is `goreecloud.tasks.manager.v1` with schema version `1`.

## Authorization model

The integration uses one deployment-configured bearer token mapped to one existing active GoreeCloud Tasks account.

Configuration:

```text
TASKS_MANAGER_API_ENABLED=true
TASKS_MANAGER_API_USERNAME=goreecloud-manager-integration
TASKS_MANAGER_API_TOKEN=<development-only token>
# or, for protected long-lived deployment configuration:
TASKS_MANAGER_API_TOKEN_FILE=/run/secrets/goreecloud_tasks_manager_api_token
TASKS_MANAGER_API_MAX_TASKS=100
```

The direct token and token-file settings are mutually exclusive. An enabled integration requires a token of at least 32 characters. The API remains disabled by default.

The configured Tasks user is the authorization principal. After bearer authentication and service-identity validation, the endpoint begins task selection with:

```python
Task.objects.visible_to(identity)
```

before applying the Manager-specific operational filter. Manager cannot provide a username, user ID, project ID, or alternate principal to expand that scope.

The intended deployment pattern is a dedicated non-interactive Tasks integration account that is given Viewer membership only in Shared projects that Manager is explicitly allowed to observe.

## Runtime least-privilege guard

A valid bearer token is necessary but is not sufficient for authorization. The live API validates the configured service identity on every authenticated request using the same reusable least-privilege rules as the pre-deployment validation command.

While the integration is active, the identity must remain:

- active;
- non-interactive with no usable password;
- without an email address;
- not Django staff;
- not a Django superuser;
- without owned projects;
- without private personal tasks;
- limited to active Viewer memberships;
- limited to Shared, non-archived projects; and
- assigned at least one active approved Viewer membership.

If the authenticated identity no longer satisfies this posture, the API fails closed with HTTP 403 and the generic response:

```json
{"detail":"Integration identity is not authorized."}
```

The API does not reveal which least-privilege rule failed. Detailed diagnostics remain available to the administrator through the non-mutating validation command.

Before deployment and after authorization changes, validate the dedicated identity with:

```bash
python manage.py validate_manager_integration_identity \
  --username goreecloud-manager-integration \
  --require-membership
```

The command and the live API intentionally share the same validator so the preflight and runtime authorization rules cannot silently drift apart.

## Project-scope revocation versus final authorization loss

Project authorization remains membership-driven.

If the identity has multiple approved Viewer memberships and one membership is removed, tasks from that project disappear from future API responses. The API may remain healthy because the identity still has another approved Viewer scope.

If the final active approved Viewer membership is removed, the service identity no longer satisfies the required integration posture. The API returns HTTP 403 instead of treating a completely deauthorized service identity as a healthy empty integration.

This distinction separates two different events:

- **Scoped revocation:** one project's visibility is removed while another approved Viewer scope remains; and
- **Authorization loss:** no approved Viewer scope remains, or the service identity otherwise becomes interactive, privileged, ownership-bearing, or non-Viewer.

## Data scope

Only active project-scoped tasks marked as GoreeCloud operational work are returned.

The endpoint excludes:

- private personal Inbox tasks;
- ordinary non-GoreeCloud tasks;
- tasks outside the configured identity's current Tasks authorization scope;
- tasks in archived projects;
- completed or cancelled tasks;
- task descriptions;
- comments;
- labels;
- assignee and creator account details;
- notification preferences and reminders;
- authentication data, sessions, tokens, email addresses, or other account data.

The approved response fields are task identity/title, project identity/name, priority, status, due timestamp, the implemented operational system/service/environment/workload fields, blocker and resume condition, backup/recovery/validation/documentation requirement flags, related change/documentation references, and the task update timestamp.

## Response shape

Example structure:

```json
{
  "schema": "goreecloud.tasks.manager.v1",
  "version": 1,
  "generated_at": "2026-08-12T11:00:00-05:00",
  "authorization": {
    "identity": "goreecloud-manager-integration",
    "scope": "visible operational project tasks only"
  },
  "summary": {
    "total_open": 3,
    "blocked": 1,
    "p0": 0,
    "p1": 1,
    "returned": 3
  },
  "tasks": []
}
```

`TASKS_MANAGER_API_MAX_TASKS` limits the number of detailed task records returned in one response to between 1 and 500. Summary counts represent the full authorized active operational scope even when detailed records are capped.

A successful authorized response may legitimately contain zero matching operational tasks. That is different from a service identity with no approved Viewer authorization, which is rejected with HTTP 403.

## Failure behavior

- Disabled API: HTTP 404.
- Missing or invalid bearer token: HTTP 401 with `WWW-Authenticate: Bearer`.
- Authenticated bearer token mapped to an identity that no longer satisfies the approved runtime service-account posture: HTTP 403 with `Integration identity is not authorized.`.
- Enabled but invalid local integration configuration: HTTP 503 without exposing the specific secret/configuration error to the caller.
- Non-GET requests: HTTP 405 at the view boundary. In a complete middleware stack, CSRF middleware may reject an unsafe request earlier with HTTP 403.

Successful responses and authentication, authorization, and configuration failures use `Cache-Control: private, no-store` at the corresponding protected response boundary. Authorization failures also vary on `Authorization`.

## Security boundary

This API is not a general public API and does not authorize Manager to modify Tasks data. It does not create user accounts, assign memberships, change tasks, complete work, post comments, alter reminders, or execute GoreeCloud infrastructure actions.

The bearer token is a reusable secret and must not be committed to Git, stored in task data, exposed in logs, or returned in API responses. Long-lived deployment should use the approved protected secret-file mechanism.

The complete service-identity and bearer-token procedure is documented in [`manager-integration-credential-lifecycle.md`](manager-integration-credential-lifecycle.md). That procedure defines the planned non-human identity posture, Viewer-only project authorization, protected runtime source, Vaultwarden recovery record, rotation, emergency revocation, recovery, and retirement controls without creating or authorizing production credentials.

The separate production-readiness evidence gate is documented in [`manager-production-readiness-validation.md`](manager-production-readiness-validation.md). That plan defines the preferred same-VM `manager-tasks` Docker network, stable Tasks service alias, final file-backed secret validation, authorization acceptance dataset, private user-facing publication checks, monitoring, recovery, rollback, upgrade compatibility, and explicit go/no-go criteria without activating production.

GoreeCloud Manager provides the sanitized integration-specific monitoring endpoint:

```text
GET /healthz/integrations/tasks/
```

Manager maps Tasks HTTP 403 to its sanitized `authorization-denied` condition without exposing the bearer credential, configured identity, task data, or upstream error body. The disposable final-topology gate validates that monitoring boundary independently from generic Manager liveness.

Transport security and network reachability remain separate deployment controls. A future production connection should use the approved private GoreeCloud service-publication and networking architecture rather than direct public backend exposure.

## Validation requirements

Regression coverage verifies that:

- the endpoint is hidden while disabled;
- missing and incorrect tokens are rejected;
- invalid enabled configuration fails closed;
- only currently authorized active GoreeCloud project tasks are returned;
- ordinary, private, personal, completed, and unrelated tasks remain excluded;
- sensitive task descriptions are not serialized;
- revoking one project scope removes its work while another approved Viewer scope can keep the integration authorized;
- revoking the final approved Viewer membership produces HTTP 403;
- staff/superuser drift is rejected at runtime;
- non-Viewer membership drift is rejected at runtime;
- an unexpected interactive password is rejected at runtime; and
- the endpoint remains GET-only.

Identity-lifecycle regression coverage additionally verifies that the dedicated service identity can be validated as non-interactive and Viewer-only before activation.

The disposable cross-application and final-topology fixtures retain a separate empty approved Viewer authorization-anchor project. This lets those gates prove per-project revocation without accidentally turning that phase into total service-identity deauthorization. Final authorization loss is proven separately by the API regression suite, while Manager's monitoring validation independently proves the `authorization-denied` classification for Tasks HTTP 403.

A successful application-level integration or CI validation does not by itself approve production credentials, private publication, DNS/Caddy/NetBird changes, monitoring registration, alert delivery, or production deployment.
