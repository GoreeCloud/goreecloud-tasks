# GoreeCloud Tasks — Manager API Integration

## Purpose

GoreeCloud Tasks exposes a deliberately narrow read-only API for GoreeCloud Manager so Manager can display approved operational work without direct database access and without gaining a general application-administrator bypass around Tasks authorization.

The initial endpoint is:

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

The configured Tasks user is the authorization principal. The endpoint begins with:

```python
Task.objects.visible_to(identity)
```

before applying the Manager-specific operational filter. Manager cannot provide a username, user ID, project ID, or alternate principal to expand that scope.

The intended deployment pattern is a dedicated Tasks integration account that is given Viewer membership only in shared projects that Manager is explicitly allowed to observe. Removing or deactivating that membership immediately removes those project tasks from future API responses. Giving the account Django staff or superuser status does not expand the normal `visible_to()` query boundary.

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

## Failure behavior

- Disabled API: HTTP 404.
- Missing or invalid bearer token: HTTP 401 with `WWW-Authenticate: Bearer`.
- Enabled but invalid local integration configuration: HTTP 503 without exposing the specific secret/configuration error to the caller.
- Non-GET requests: HTTP 405.

Successful responses and authentication/configuration failures use `Cache-Control: private, no-store` so integration data is not treated as cacheable public content.

## Security boundary

This API is not a general public API and does not authorize Manager to modify Tasks data. It does not create user accounts, assign memberships, change tasks, complete work, post comments, alter reminders, or execute GoreeCloud infrastructure actions.

The bearer token is a reusable secret and must not be committed to Git, stored in task data, exposed in logs, or returned in API responses. Long-lived deployment should use the approved protected secret-file mechanism. Token rotation and production provisioning remain deployment responsibilities.

Transport security and network reachability remain separate deployment controls. A future production connection should use the approved private GoreeCloud service-publication and networking architecture rather than direct public backend exposure.

## Validation requirements

Regression coverage verifies that:

- the endpoint is hidden while disabled;
- missing and incorrect tokens are rejected;
- invalid enabled configuration fails closed;
- only currently authorized active GoreeCloud project tasks are returned;
- ordinary, private, personal, completed, and unrelated tasks remain excluded;
- sensitive task descriptions are not serialized;
- membership revocation removes future visibility;
- staff/superuser flags do not expand the integration scope; and
- the endpoint remains GET-only.

GoreeCloud Manager must independently validate the response schema and normalize only the fields it needs for display. A successful application-level integration test does not by itself approve production credentials, private publication, DNS/Caddy changes, or production deployment.
