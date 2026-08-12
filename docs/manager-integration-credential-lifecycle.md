# GoreeCloud Tasks — Manager Integration Identity and Credential Lifecycle

## Purpose

I use this document to define the deployment-specific lifecycle for the dedicated GoreeCloud Tasks identity and bearer credential used by GoreeCloud Manager.

This procedure covers provisioning, authorization, protected storage, validation, rotation, emergency revocation, recovery, and retirement. It does not authorize production deployment by itself.

The integration remains read-only. GoreeCloud Tasks remains authoritative for task content, project membership, authorization, and whether the configured identity is active.

## Production Boundary

The source code and procedure are approved development artifacts only. I have not created a production Tasks integration account, Viewer membership, bearer token, Vaultwarden item, secret file, Docker secret mount, private Manager-to-Tasks network, DNS record, Caddy route, NetBird policy, firewall rule, or production Tasks deployment through this work.

Production activation requires a separate production-readiness approval and validation record.

## Dedicated Identity

The planned Tasks identity is:

```text
goreecloud-manager-integration
```

I will treat this as a non-human service identity rather than an administrator or ordinary user account.

The identity must satisfy all of the following conditions before I enable the Manager API:

- active in GoreeCloud Tasks;
- no usable interactive password;
- no email address;
- not Django staff;
- not a Django superuser;
- owns no Tasks project;
- owns no private personal task;
- has only explicit active Viewer memberships;
- every active membership belongs to a Shared, non-archived project; and
- each Viewer membership has been deliberately approved for Manager visibility.

The identity must never be promoted to Manager or Member merely to make the integration easier to configure. Manager receives visibility by the same Tasks membership model used by ordinary application readers.

## Identity Provisioning

I will create the service identity only after the target Tasks deployment exists and production integration has been separately approved.

I will use a controlled Django administrative session rather than creating an interactive password. An acceptable one-time provisioning pattern is:

```bash
python manage.py shell <<'PY'
from django.contrib.auth import get_user_model

username = "goreecloud-manager-integration"
User = get_user_model()

if User.objects.filter(username=username).exists():
    raise SystemExit(f"Refusing to overwrite existing Tasks identity: {username}")

user = User(username=username, is_active=True, is_staff=False, is_superuser=False)
user.set_unusable_password()
user.full_clean()
user.save()
print(f"Created dedicated Tasks integration identity: {username}")
PY
```

The command contains no bearer token or reusable secret.

After creation, I will verify the identity before adding project access:

```bash
python manage.py validate_manager_integration_identity \
  --username goreecloud-manager-integration
```

## Project Authorization

I will grant project access through the existing Tasks membership workflow rather than giving the service identity ownership or elevated application privileges.

For each project that Manager is allowed to observe:

1. I will confirm that the project is intentionally Shared.
2. I will confirm that Manager visibility is appropriate for the project's GoreeCloud operational work.
3. The project owner will add `goreecloud-manager-integration` by exact username.
4. The role will be Viewer.
5. I will not grant Manager or Member role.
6. I will verify the final identity posture with the validation command.

The final pre-activation check is:

```bash
python manage.py validate_manager_integration_identity \
  --username goreecloud-manager-integration \
  --require-membership
```

This command is intentionally non-mutating. It fails if the identity is interactive or privileged, owns projects or private personal tasks, has a non-Viewer active membership, has access to a Private project, or retains active access to an archived project.

Inactive historical memberships are preserved as history and do not authorize the integration.

## Bearer Credential Record

I will identify the credential through the non-secret administrative name:

```text
GoreeCloud Tasks — Manager API Bearer Token
```

The active token itself must never appear in this document, a change log, an issue, a pull request, source control, a screenshot, shell history, task data, application logs, or ordinary chat.

The planned administrative record is:

```text
Secret Record Name: GoreeCloud Tasks — Manager API Bearer Token
Secret Type: Application integration bearer token
Purpose: Authenticate GoreeCloud Manager to the read-only GoreeCloud Tasks Manager API
Responsible Administrator: GoreeCloud administrator
Assigned Services: GoreeCloud Tasks and GoreeCloud Manager
Authorized Scope: One configured Tasks service identity and its current Viewer-only project visibility
Authoritative Human Secret Store: Vaultwarden
Preferred Runtime Secret Source: /srv/docker/secrets/goreecloud-tasks-manager/manager-api-token
Tasks Container Path: /run/secrets/goreecloud_tasks_manager_api_token
Manager Container Path: /run/secrets/goreecloud_tasks_manager_api_token
Active Secret Included in This Record: No
```

The host-side path is the planned target for a same-VM deployment because both applications are planned for the GoreeCloud Infrastructure Services VM. It provides one shared runtime source instead of unnecessarily duplicating the same token across separate environment files.

If Tasks and Manager are later deployed on different hosts, each host may require its own protected runtime copy. That duplication must be treated as a technical deployment requirement, documented explicitly, and kept to the minimum number of copies.

## Secret Generation

I will generate the bearer token with a cryptographically secure generator. I will not invent, reuse, or derive the token from a password, username, project name, hostname, or other predictable value.

A suitable generation pattern is:

```bash
umask 077
mkdir -p /srv/docker/secrets/goreecloud-tasks-manager
python - <<'PY' > /srv/docker/secrets/goreecloud-tasks-manager/manager-api-token
import secrets
print(secrets.token_urlsafe(64))
PY
chmod 600 /srv/docker/secrets/goreecloud-tasks-manager/manager-api-token
```

This command sends generated output directly into the protected file rather than placing the token in the command line. The final owner and any required container-readable group must be selected and validated as part of the production Docker Compose override; I will not make the file broadly readable to solve a mount-permission problem.

I will store a protected recovery copy and lifecycle metadata in Vaultwarden under the non-secret item name above. The repository will contain only file-path references and placeholders.

## Application Configuration

Tasks will use:

```text
TASKS_MANAGER_API_ENABLED=true
TASKS_MANAGER_API_USERNAME=goreecloud-manager-integration
TASKS_MANAGER_API_TOKEN_FILE=/run/secrets/goreecloud_tasks_manager_api_token
```

Manager will use:

```text
TASKS_ENABLED=true
TASKS_API_URL=<approved private Tasks base URL>
TASKS_ACCESS_TOKEN_FILE=/run/secrets/goreecloud_tasks_manager_api_token
```

The direct environment-token variables remain development-only escape hatches. I will not use `TASKS_MANAGER_API_TOKEN` or `TASKS_ACCESS_TOKEN` for the long-lived production credential when the file-backed mechanism is available.

The production Compose definitions must mount the approved protected source only into the Tasks and Manager containers that require it. The token must not enter unrelated containers, image layers, Docker build contexts, resolved configuration retained as ordinary documentation, or general-purpose status artifacts.

## Initial Activation Sequence

When production activation is separately approved, I will use the following order:

1. Verify current backups and recovery prerequisites for both application stacks.
2. Confirm the dedicated Tasks identity exists and passes least-privilege validation.
3. Confirm each intended project membership is explicit Viewer-only access.
4. Create the Vaultwarden credential record without copying the token into ordinary documentation.
5. Create the protected runtime token file with restrictive permissions.
6. Prepare the production Compose secret mounts and file-reference variables.
7. Keep Manager requests disabled until Tasks-side identity and secret configuration are ready.
8. Start or recreate Tasks with the Manager API still reachable only through the approved private service path.
9. Validate Tasks configuration and the integration identity.
10. Start or recreate Manager with its matching file-backed credential.
11. Validate one authorized operational project and one deliberately unauthorized project.
12. Confirm descriptions, comments, labels, personal tasks, completed work, and unrelated project content remain absent.
13. Confirm an invalid bearer token is rejected.
14. Confirm Manager remains read-only.
15. Record the production validation evidence before treating the integration as operational.

## Routine Review

I will review the integration identity and credential when:

- a project is added to or removed from Manager visibility;
- the Tasks or Manager deployment changes;
- either application moves to another host or VM;
- the private network path changes;
- the token is rotated;
- the service identity is changed;
- a security incident affects either application or host;
- recovery restores configuration or secrets; or
- a periodic credential/access review is performed.

The identity validation command should be part of that review.

## Token Rotation

The current API intentionally accepts one configured token. I will not keep a second long-lived overlap token merely to avoid a short read-only integration interruption.

For planned rotation:

1. Confirm current backup and rollback state.
2. Temporarily disable or stop Manager's Tasks integration so it does not repeatedly present the retiring token during the change.
3. Generate the replacement token directly into a new protected file.
4. Update the protected Vaultwarden copy and rotation metadata.
5. Replace the approved runtime token source.
6. Recreate or restart Tasks and Manager as required by the final secret-mount implementation so both consumers see the same new value.
7. Run `validate_manager_integration_identity --require-membership`.
8. Validate a successful Manager API request through the real Manager adapter.
9. Validate that the previous token no longer authenticates.
10. Confirm no token value appeared in logs, shell history, screenshots, or retained temporary output.
11. Remove obsolete protected copies and temporary files.
12. Record the rotation date, reason, validation result, and current non-secret storage references.

A brief `unavailable` Manager integration state during controlled rotation is preferable to simultaneously accepting old and new long-lived tokens without a separately approved requirement.

## Emergency Credential Revocation

If the bearer token may be exposed or misused, I will treat deletion of a file as insufficient. I will revoke authorization by configuration.

The preferred emergency sequence is:

1. Disable the Manager integration request path in Manager or stop the Manager container.
2. Disable `TASKS_MANAGER_API_ENABLED` in Tasks if immediate API shutdown is required.
3. Preserve necessary incident evidence without copying the token into ordinary records.
4. Generate a new token through the protected method.
5. Replace the approved runtime source and protected recovery copy.
6. Restart or recreate affected application containers as required.
7. Re-enable Tasks and then Manager only after validation.
8. Confirm the retired token receives HTTP 401 or the endpoint remains disabled.
9. Review application and infrastructure logs for suspicious use without exposing authorization headers.
10. Record the incident, rotation, and corrective actions.

Because Tasks compares the request token against the configured value, replacing the configured value makes the old token invalid. There is no separate token database that must be purged.

## Project Access Revocation

Project visibility and bearer-token validity are separate controls.

To remove only one project's visibility, the project owner will deactivate the service identity's membership for that project. The bearer token does not need to change. The existing API and cross-application regression gate verify that subsequent requests lose that project immediately.

I will rotate the bearer token only when the credential lifecycle requires it or when exposure is suspected. I will not rotate a shared integration secret merely to remove one project membership.

## Identity Revocation

To revoke all Manager task visibility while preserving account and membership history:

1. Disable Manager requests.
2. Disable the Tasks Manager API if the integration is being globally suspended.
3. Deactivate all active project memberships for `goreecloud-manager-integration`.
4. Set the service identity inactive if the integration is no longer authorized.
5. Validate that the identity no longer passes active integration checks.
6. Rotate or remove the bearer credential if the integration is not immediately returning to service.

I will prefer deactivation over deleting the identity so historical membership and attribution records remain understandable.

## Recovery

The integration credential is part of the application dependency and recovery model, but a recovered credential must not silently re-authorize a retired integration.

During recovery I will:

1. Restore Tasks and Manager application data according to their approved recovery procedures.
2. Determine whether the integration was active and approved at the recovery point.
3. Restore the protected token only when reuse remains appropriate; otherwise generate a new token.
4. Restore the service identity and membership state from the authoritative Tasks database recovery path.
5. Run the identity validator before enabling the endpoint.
6. Validate private Manager-to-Tasks reachability and authentication.
7. Confirm unauthorized projects remain excluded.
8. Confirm monitoring and backup operation resume.
9. Record the recovery result.

A Vaultwarden copy is recovery material, not permission to reactivate an integration that had already been revoked.

## Retirement

When I permanently retire this integration:

1. Disable Manager's Tasks adapter.
2. Disable the Tasks Manager API.
3. Deactivate all active Viewer memberships held by the service identity.
4. Set the service identity inactive.
5. Remove the production token file and any technically required runtime copies.
6. Remove or retire the protected Vaultwarden secret value while preserving non-secret historical metadata when needed.
7. Remove production secret mounts and obsolete environment references.
8. Remove dedicated private network access that exists only for this integration after confirming no other dependency uses it.
9. Remove integration-specific monitoring after the endpoint is no longer expected to operate.
10. Preserve change history and relevant recovery evidence without retaining an active credential.
11. Verify the retired token no longer authenticates.

## Validation Evidence Required Before Production

This lifecycle document does not satisfy the separate production-readiness gate. Before activation I still require evidence for:

- least-privilege private network reachability between Manager and Tasks;
- the final protected secret-file mount and container-side permissions;
- the approved production Tasks hostname and HTTPS path;
- Caddy, DNS, NetBird, and firewall behavior where applicable;
- monitoring and alerting;
- backup treatment for the secret and application configuration;
- recovery and rollback;
- upgrade behavior;
- actual production-representative authorization tests; and
- confirmation that no backend port is directly exposed publicly.

## Governing Principle

I treat the Manager bearer token as a reusable service credential and the Tasks integration account as an authorization principal. The token proves which configured service is calling; the account's current Tasks membership determines what that service may read. I keep those controls separate, least-privileged, independently revocable, and fully recoverable without placing the active secret in ordinary documentation.
