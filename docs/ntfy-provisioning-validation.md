# ntfy service identity provisioning and end-to-end validation

## Purpose

This document defines the GoreeCloud Tasks ntfy publisher identity, topic ACL model, protected-token handling, isolated validation workflow, rotation/revocation process, and production-enablement gates.

This increment prepares and continuously tests the required boundary. It does **not** provision the production GoreeCloud ntfy instance, modify its authentication database, create a Vaultwarden record, deploy a reminder scheduler, change Caddy/DNS/NetBird, or enable production GoreeCloud Tasks notifications.

## Governing boundary

GoreeCloud Tasks remains the authorization system for task content. ntfy is only a downstream delivery channel.

The intended production model is:

```text
GoreeCloud Tasks application
  -> dedicated regular ntfy service identity
  -> dedicated service access token
  -> write-only ACL for goreecloud-tasks-*
  -> exact generated per-user topic
  -> individual ntfy subscriber identity
  -> read-only ACL for that exact topic
```

The publisher must **not** be an ntfy administrator. The service identity receives only the write permission required for the GoreeCloud Tasks topic namespace. Individual subscribers receive only read access to their exact generated topic.

The topic name is routing metadata, not a credential. Authentication and ACL enforcement remain mandatory even though GoreeCloud Tasks generates random, non-identifying topic suffixes.

## Verified ntfy behavior used by this design

The design follows ntfy's documented authentication and authorization model:

- `auth-default-access: deny-all` is the private-instance fallback.
- regular users receive topic permissions through `ntfy access` or equivalent declarative ACLs;
- ACL values distinguish read-only, write-only, read-write, and deny-all;
- service access tokens inherit the permissions of the associated ntfy user account; and
- Bearer access tokens can authenticate publishing and subscription API requests.

Because ntfy access tokens inherit the associated user's permissions, least privilege is enforced at the **service-user ACL**. A broadly privileged service user would make a dedicated token broad as well.

Current upstream references used for the validation design:

- ntfy configuration and access control: `https://docs.ntfy.sh/config/`
- ntfy publishing authentication: `https://docs.ntfy.sh/publish/`
- ntfy subscription API and polling: `https://docs.ntfy.sh/subscribe/api/`
- ntfy v2.26.3 release: `https://github.com/binwiederhier/ntfy/releases/tag/v2.26.3`
- container image: `binwiederhier/ntfy:v2.26.3`

The disposable CI validation pins the v2.26.3 multi-platform image digest rather than using `latest`.

## Production provisioning workflow

These commands are a reviewed **future production procedure**. They are not executed by this repository or GitHub Actions.

### 1. Preflight

On the approved ntfy host, inspect the current identity and ACL state before changing anything:

```bash
sudo docker exec ntfy ntfy user list
sudo docker exec ntfy ntfy access
sudo docker exec ntfy ntfy token list
```

Confirm that:

- authentication remains required;
- anonymous/default access remains deny-all;
- no existing user already owns the intended service identity name;
- no existing ACL grants broader `goreecloud-tasks-*` access than intended; and
- the current ntfy authentication database is covered by the approved backup process.

### 2. Create the publisher identity

Create a regular non-admin service identity:

```bash
sudo docker exec -it ntfy ntfy user add goreecloud-tasks-publisher
```

The generated/bootstrap password is protected as a credential. It must not be copied into repository files, ordinary documentation, screenshots, or change logs.

### 3. Grant only write access to the Tasks topic namespace

```bash
sudo docker exec ntfy \
  ntfy access \
  goreecloud-tasks-publisher \
  'goreecloud-tasks-*' \
  write-only
```

Review the result:

```bash
sudo docker exec ntfy ntfy access goreecloud-tasks-publisher
```

The service identity must not receive read access to the namespace and must not receive permissions on unrelated GoreeCloud topics.

### 4. Create the service access token

```bash
sudo docker exec ntfy \
  ntfy token add \
  --label='GoreeCloud Tasks publisher' \
  goreecloud-tasks-publisher
```

Treat the complete token value as a reusable secret.

The production process is:

1. capture the token only in a protected administrative session;
2. store the credential record in the approved GoreeCloud secret store;
3. install the token into a protected file readable only by the GoreeCloud Tasks runtime;
4. configure `NTFY_ACCESS_TOKEN_FILE` to reference that mounted file;
5. do not configure `NTFY_ACCESS_TOKEN` simultaneously; and
6. never write the token into Git, Docker Compose YAML, project documentation, or application data.

### 5. Grant each subscriber only its exact topic

For each approved user, the ntfy identity is separate from the GoreeCloud Tasks application identity. After confirming the intended user and the exact generated topic shown in Tasks, grant read-only access to that one topic:

```bash
sudo docker exec ntfy \
  ntfy access \
  <ntfy-user> \
  <exact-goreecloud-tasks-topic> \
  read-only
```

Do not grant a family member or ordinary user read access to `goreecloud-tasks-*` as a wildcard. Topic-by-topic authorization preserves per-user isolation.

### 6. Validate before scheduling is enabled

Before any recurring reminder scheduler is deployed, verify:

- anonymous subscription to the topic is denied;
- anonymous publication is denied;
- the publisher token can publish to the intended Tasks topic;
- the publisher token cannot subscribe/read the Tasks topic;
- the publisher token cannot publish outside `goreecloud-tasks-*`;
- the intended subscriber can read the exact topic;
- the intended subscriber cannot publish to that topic;
- another ordinary subscriber cannot read the topic;
- the GoreeCloud Tasks message contains only the approved minimized fields;
- revoking project access still cancels a due reminder before publication;
- a failed delivery remains pending/retryable; and
- the production credential is loaded through the protected file path.

Only after those checks pass may scheduler deployment be considered separately.

## Disposable CI validation

The repository contains `scripts/validate_ntfy_integration.sh` and `tests/test_ntfy_live_integration.py`.

The CI test starts an ephemeral ntfy v2.26.3 container bound only to host loopback. It creates only disposable, test-only users and runtime-random access tokens. The server uses deny-all fallback ACLs.

The isolated ACL is:

```text
tasks-ci-publisher
  goreecloud-tasks-* -> write-only

tasks-ci-subscriber
  goreecloud-tasks-validation-user -> read-only

tasks-ci-outsider
  goreecloud-tasks-validation-other -> read-only
```

The live Django integration test then:

1. creates an ordinary GoreeCloud Tasks user, project, task, notification preference, and reminder in the test database;
2. calls the real `publish_ntfy_reminder()` HTTP publisher without mocking `urlopen`;
3. polls the exact ntfy topic as the read-only subscriber;
4. verifies the delivered title, priority, tag, task title, due context, and project name;
5. verifies the sensitive task description and publisher token are absent;
6. verifies the publisher cannot read the topic;
7. verifies the subscriber cannot publish;
8. verifies the unrelated subscriber cannot read the topic;
9. verifies anonymous reading is denied; and
10. verifies the publisher cannot write outside the GoreeCloud Tasks namespace.

The disposable server and runtime tokens are removed at the end of the CI step.

This is an application-to-real-ntfy integration test. It is not proof that a phone or desktop operating system displayed a push notification, and it is not a production service validation.

## Credential rotation

Production rotation should use an overlap-safe sequence:

1. create a replacement token for the same least-privilege service identity;
2. store the replacement in the approved secret store;
3. atomically replace the protected token file used by GoreeCloud Tasks;
4. restart/reload only the component required to consume the new value;
5. validate one minimized publication to an approved validation topic;
6. confirm the subscriber receives it;
7. remove the old token from ntfy;
8. remove/retire the old credential record; and
9. record the change without reproducing either token.

A token should be revoked immediately after suspected disclosure, device loss involving copied credentials, unexpected publication activity, or service retirement.

## Rollback and deprovisioning

If validation fails before production use:

1. keep the scheduler disabled;
2. remove the new service token;
3. reset the service identity's ACL entries;
4. remove the service identity if no approved dependency remains;
5. remove any temporary subscriber ACLs;
6. preserve diagnostic information without exposing credentials; and
7. document the failed validation and corrective work.

If GoreeCloud Tasks is retired, identify and revoke every Tasks publisher token and subscriber ACL before removing the service identity.

## Production gate

This increment does not approve production notification delivery.

Production enablement still requires separate authorization for:

- the real ntfy service identity and ACL changes;
- protected Vaultwarden/token-file handling;
- the actual GoreeCloud Tasks deployment;
- the reminder scheduler;
- monitoring of scheduler execution and delivery failures;
- backup and restore implications;
- token rotation and service-identity retirement procedures;
- end-client web/mobile notification validation; and
- the remaining GoreeCloud Tasks production-readiness gates.
