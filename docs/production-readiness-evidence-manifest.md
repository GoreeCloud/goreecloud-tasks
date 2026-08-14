# Production Readiness Evidence Manifest

## Purpose

This document describes the machine-readable GoreeCloud Tasks production-readiness evidence manifest and its target-environment evidence collection plan.

The manifest exists to prevent readiness status from drifting across individual workflows, recovery records, and project documentation. The collection plan exists to make later target-environment validation deliberate, ordered, non-secret, and approval-aware. Neither record approves production use, creates production evidence, or replaces the authoritative GoreeCloud policies and project specification.

The implementation consists of:

- `scripts/tasks_production_readiness_manifest.json`
- `scripts/validate_tasks_production_readiness_manifest.py`
- `scripts/tasks_target_evidence_collection_plan.json`
- `scripts/validate_tasks_target_evidence_collection_plan.py`
- `.github/workflows/production-readiness-evidence-manifest.yml`

## Current Production State

The manifest deliberately records:

`production_state.status = not-approved`

No approval reference or approval time is present.

The current manifest contains:

- 8 source/disposable workflow layers.
- 14 effective checks/jobs across those workflows.
- 20 target-environment evidence categories.
- 0 target-environment categories marked satisfied.
- 20 target-environment categories marked outstanding.

This reflects the current GoreeCloud Tasks readiness boundary rather than converting source/disposable evidence into production approval.

## Source and Disposable Evidence Inventory

Every `.github/workflows/*.yml` workflow in the repository must appear in the manifest. The manifest records the workflow path, workflow display name, expected job identifiers, and its evidence scope.

The current inventory contains:

### CI

Required jobs:

- `django`
- `ntfy-integration`
- `manager-cross-app`
- `manager-final-topology`
- `backup-restore`
- `upgrade-rollback`
- `docker-compose`

### Runtime Security Preflight

Required job:

- `runtime-security-preflight`

### Private Publication Validation

Required job:

- `private-publication`

### Monitoring Alert Readiness

Required job:

- `monitoring-alert-readiness`

### Backup Operations Readiness

Required job:

- `backup-operations-readiness`

### Full Environment Recovery Readiness

Required job:

- `full-environment-recovery-readiness`

### Production Recovery Evidence Contract

Required job:

- `production-recovery-evidence-contract`

### Production Readiness Evidence Manifest

Required job:

- `production-readiness-evidence-manifest`

The validator reads the workflow files directly with the Python standard library. It verifies:

- Every manifested workflow exists.
- Every actual `.github/workflows/*.yml` file is represented in the manifest.
- The workflow display name matches the manifest.
- The exact job identifiers match the manifest.
- The declared effective-check count equals the sum of all manifested jobs.

This means a new workflow, removed workflow, renamed workflow, or changed job inventory requires an intentional manifest update.

The target evidence collection plan is validated inside the existing `production-readiness-evidence-manifest` job. It does not add a ninth workflow layer or a fifteenth effective check.

## Target-Environment Evidence Inventory

The manifest separately tracks target-environment evidence that disposable CI does not prove.

Current categories are:

1. Infrastructure Services VM runtime inspection.
2. Production file ownership, permissions, and secret mounts.
3. Production Docker Engine, Compose, and running-container state.
4. Production AdGuard Home private DNS.
5. Production NetBird peer, group, policy, and source path.
6. Production Porkbun DNS-01 and publicly trusted TLS.
7. Production Caddy listeners and firewall behavior.
8. Production private publication and authentication.
9. Production multi-user authorization acceptance.
10. Production Uptime Kuma registration and administrative alert receipt.
11. Production backup repository, schedule, retention, and monitoring.
12. Independent off-host or off-site recovery copy.
13. Independently available production recovery credentials.
14. Proxmox VM backup and dedicated-backup-server recovery.
15. Production full-environment recovery test.
16. Production backup resumption after recovery.
17. Production capacity and recovery-time evidence.
18. Production Manager integration identity, network, and credential.
19. Production ntfy identity, ACL, schedule, and end-client delivery.
20. Production documentation and recovery records.

A target-evidence item has only two allowed states:

- `outstanding`
- `satisfied`

An outstanding item must not contain verification metadata.

A satisfied item must contain:

- A non-empty evidence reference.
- A timezone-aware verification timestamp.
- A verifier identity or role.

The evidence reference should point to the appropriate authoritative internal record. Reusable credentials must not be copied into the manifest.

## Target Evidence Collection Plan

`scripts/tasks_target_evidence_collection_plan.json` maps all 20 manifest target-evidence identifiers to a deliberate evidence-collection sequence. It is planning metadata only.

The plan enforces this authorization boundary:

- Target-environment collection requires separate authorization.
- The plan itself grants no production authority.
- The default operating mode is `plan-only`.

The plan also records global actions that remain prohibited without separate approval, including creating production identities or credentials, changing production Docker/DNS/Caddy/NetBird/firewall/monitoring/backup state, deploying or manipulating the Tasks service, performing destructive recovery exercises, or marking production evidence satisfied without authorized verification.

### Collection phases

The plan groups evidence into five phases:

1. **Target baseline inspection** — runtime identity, file/secret metadata, Docker state, DNS, NetBird, TLS ownership, Caddy listeners, and firewall state.
2. **Publication and user-facing validation** — real private publication/authentication, multi-user authorization acceptance, and Uptime Kuma/alert receipt.
3. **Backup and recovery validation** — repository/schedule/retention/monitoring, independent copies, independently available recovery credentials, Proxmox recovery where applicable, full-environment recovery, backup resumption, capacity, and recovery-time evidence.
4. **Production integrations** — Tasks-to-Manager identity/network/credential validation and ntfy identity/ACL/schedule/end-client validation.
5. **Documentation reconciliation** — final authoritative record consistency and evidence-reference review.

### Collection classes

Each category is assigned one explicit class:

- `read-only-inspection`
- `controlled-connectivity-validation`
- `controlled-monitoring-validation`
- `controlled-backup-validation`
- `controlled-recovery-validation`
- `controlled-integration-validation`
- `multi-user-acceptance`
- `documentation-review`

These classes describe the nature of the future evidence activity. They do not authorize it.

### Collection-plan validator

`scripts/validate_tasks_target_evidence_collection_plan.py` verifies that:

- The plan has the expected schema and service identity.
- The plan remains bound to `scripts/tasks_production_readiness_manifest.json`.
- Separate target authorization remains mandatory.
- The plan cannot claim that it grants production authority.
- The global prohibited-action list is present.
- Every collection item has exactly one ID, phase, collection class, evidence-source list, and success-criteria list.
- Collection phases remain ordered from 1 through 5.
- Collection classes remain within the approved vocabulary.
- The plan contains exactly the same target-evidence identifiers as the manifest, with no missing, extra, or duplicate categories.
- The manifest remains `not-approved` while this planning record is used.
- Common active-looking reusable secrets are rejected from plan strings.

The validator's semantic self-tests intentionally reject duplicate IDs, unsafe authorization-boundary changes, any plan that claims production authority, unsupported automatic-production-change classes, empty evidence-source lists, phase-order drift, manifest-path drift, and active-looking sensitive values.

## Production Approval Rule

The aggregate manifest validator permits only two production states:

- `not-approved`
- `approved`

### Not Approved

When production is not approved:

- `approval_reference` must be null.
- `approved_at` must be null.
- At least one target-environment evidence category must remain outstanding.

### Approved

The manifest cannot be marked approved while any target-environment evidence remains outstanding.

An approved state additionally requires:

- A non-empty approval reference.
- A timezone-aware approval timestamp.

The validator checks record consistency only. It does not grant authority. The approval reference must correspond to a separately authorized GoreeCloud production decision.

## Fail-Closed Drift Detection

The aggregate validator intentionally fails when:

- A workflow exists on disk but is absent from the manifest.
- The manifest references a workflow that no longer exists.
- A workflow name changes without updating the manifest.
- A workflow job is added, removed, or renamed without updating the manifest.
- The declared effective-check count does not equal the manifested job total.
- A target-evidence identifier is duplicated.
- An evidence item uses an unknown status.
- An outstanding evidence item incorrectly contains verification metadata.
- A satisfied evidence item lacks its evidence reference, verification time, or verifier.
- Production is marked approved while any target evidence is still outstanding.
- A not-approved state incorrectly contains approval metadata.
- Common active-looking sensitive values are found in manifest strings.

The collection-plan validator adds a second drift boundary by requiring exact target-ID parity with the manifest and preserving the separate-authorization rule.

## Semantic Self-Tests

The permanent manifest job exercises in-memory negative cases for both validators.

The manifest validator verifies rejection of:

- Effective-check count drift.
- Duplicate target-evidence identifiers.
- Satisfied evidence without verification metadata.
- Production approval while target evidence remains outstanding.
- Approval metadata attached to a not-approved state.
- Active-looking sensitive material.

The collection-plan validator verifies rejection of:

- Duplicate plan IDs.
- Unsafe authorization-boundary changes.
- A plan that claims production authority.
- Unsupported collection classes.
- Empty evidence-source lists.
- Phase-order drift.
- Active-looking sensitive material.
- Manifest-path drift.

No target-environment item is changed by these tests; all mutations occur only in memory.

## Relationship to the Production Recovery Evidence Contract

The Production Recovery Evidence Contract, Production Readiness Evidence Manifest, and Target Evidence Collection Plan solve different problems.

The recovery evidence contract validates the completeness and internal consistency of an individual material recovery or restore-test record.

The readiness manifest aggregates the larger GoreeCloud Tasks production-readiness state across all permanent source/disposable gates and all target-environment evidence categories.

The collection plan defines how those target categories should later be approached and what authoritative evidence sources and success criteria should be used without granting authority to perform the work.

A future production full-environment recovery test would therefore need to:

1. Receive separate authorization for the target recovery exercise.
2. Follow the relevant collection-plan boundary and authoritative recovery requirements.
3. Produce an approved internal recovery evidence record.
4. Pass the Production Recovery Evidence Contract validator.
5. Be referenced by the corresponding `production-full-environment-recovery-test` target-evidence item.
6. Leave the overall production state not approved until every other required target-evidence category is also satisfied and a separate production approval decision is recorded.

## Relationship to the Project Specification

The Project Specification remains the authoritative human-readable project record.

The readiness manifest is a source-controlled consistency and evidence-inventory mechanism. The collection plan is a source-controlled preparation aid for later authorized evidence work. Both are intentionally more compact and machine-verifiable than the specification.

When a target-environment readiness item is actually validated, the expected synchronization sequence is:

1. Receive the required separate target authorization.
2. Perform the authorized target-environment validation using the relevant collection-plan entry.
3. Store the detailed evidence in its approved authoritative location.
4. Update the relevant GoreeCloud inventory, configuration, policy, or change-log record as required.
5. Update the target-evidence item in the manifest with a non-secret evidence reference, timestamp, and verifier.
6. Run the aggregate manifest and collection-plan validators.
7. Update the Tasks Project Specification and Change Log.
8. Keep production marked `not-approved` until all requirements and a separate production approval are complete.

## Usage

Validate the current repository and manifest:

```bash
python3 scripts/validate_tasks_production_readiness_manifest.py
```

Run repository validation plus manifest semantic negative tests:

```bash
python3 scripts/validate_tasks_production_readiness_manifest.py --self-test
```

Validate the collection plan against the manifest:

```bash
python3 scripts/validate_tasks_target_evidence_collection_plan.py
```

Run collection-plan validation plus semantic negative tests:

```bash
python3 scripts/validate_tasks_target_evidence_collection_plan.py --self-test
```

A valid manifest prints the effective source/disposable check count, satisfied target-evidence count, outstanding target-evidence count, and production state. A valid collection plan prints the target category count, phase count, collection-class count, and the separate-authorization requirement.

## Production Boundary

Neither the manifest nor the collection plan inspects or changes the actual Infrastructure Services VM or any production service.

They do not create:

- Production users or integration identities.
- Viewer memberships.
- Bearer credentials.
- Vaultwarden items.
- Host secret files.
- Docker cross-stack production networks.
- DNS or Caddy configuration.
- NetBird policy.
- Firewall changes.
- Uptime Kuma monitors.
- ntfy routes.
- Backup repositories or schedules.
- Production Tasks data.
- Deployments or service activation.

The manifest remains a source-controlled statement that target-environment items are outstanding until separately authorized evidence demonstrates otherwise. The collection plan makes the future evidence sequence safer and more explicit without changing that state.
