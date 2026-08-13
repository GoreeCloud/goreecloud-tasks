# Production Readiness Evidence Manifest

## Purpose

This document describes the machine-readable GoreeCloud Tasks production-readiness evidence manifest.

The manifest exists to prevent readiness status from drifting across individual workflows, recovery records, and project documentation. It does **not** approve production use, create production evidence, or replace the authoritative GoreeCloud policies and project specification.

The implementation consists of:

- `scripts/tasks_production_readiness_manifest.json`
- `scripts/validate_tasks_production_readiness_manifest.py`
- `.github/workflows/production-readiness-evidence-manifest.yml`

## Current Production State

The manifest deliberately records:

`production_state.status = not-approved`

No approval reference or approval time is present.

The current manifest contains:

- 7 source/disposable workflow layers.
- 13 effective checks/jobs across those workflows.
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

The validator reads the workflow files directly with the Python standard library. It verifies:

- Every manifested workflow exists.
- Every actual `.github/workflows/*.yml` file is represented in the manifest.
- The workflow display name matches the manifest.
- The exact job identifiers match the manifest.
- The declared effective-check count equals the sum of all manifested jobs.

This means a new workflow, removed workflow, renamed workflow, or changed job inventory requires an intentional manifest update.

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

## Production Approval Rule

The aggregate validator permits only two production states:

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

The validator intentionally fails when:

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

## Semantic Self-Test

The permanent CI gate also exercises in-memory negative cases. It verifies rejection of:

- Effective-check count drift.
- Duplicate target-evidence identifiers.
- Satisfied evidence without verification metadata.
- Production approval while target evidence remains outstanding.
- Approval metadata attached to a not-approved state.
- Active-looking sensitive material.

No target-environment item is changed by these tests; all mutations occur only in memory.

## Relationship to the Production Recovery Evidence Contract

The Production Recovery Evidence Contract and Production Readiness Evidence Manifest solve different problems.

The recovery evidence contract validates the completeness and internal consistency of an individual material recovery or restore-test record.

The readiness manifest aggregates the larger GoreeCloud Tasks production-readiness state across all permanent source/disposable gates and all target-environment evidence categories.

A future production full-environment recovery test would therefore need to:

1. Produce an approved internal recovery evidence record.
2. Pass the Production Recovery Evidence Contract validator.
3. Be referenced by the corresponding `production-full-environment-recovery-test` target-evidence item.
4. Leave the overall production state not approved until every other required target-evidence category is also satisfied and a separate production approval decision is recorded.

## Relationship to the Project Specification

The Project Specification remains the authoritative human-readable project record.

The readiness manifest is a source-controlled consistency and evidence-inventory mechanism. It is intentionally more compact and machine-verifiable than the specification.

When a target-environment readiness item is actually validated, the expected synchronization sequence is:

1. Perform the separately authorized target-environment validation.
2. Store the detailed evidence in its approved authoritative location.
3. Update the relevant GoreeCloud inventory, configuration, policy, or change-log record as required.
4. Update the target-evidence item in this manifest with a non-secret evidence reference, timestamp, and verifier.
5. Run the aggregate manifest validator.
6. Update the Tasks Project Specification and Change Log.
7. Keep production marked `not-approved` until all requirements and a separate production approval are complete.

## Usage

Validate the current repository and manifest:

```bash
python3 scripts/validate_tasks_production_readiness_manifest.py
```

Run repository validation plus semantic negative tests:

```bash
python3 scripts/validate_tasks_production_readiness_manifest.py --self-test
```

A valid current record prints the effective source/disposable check count, satisfied target-evidence count, outstanding target-evidence count, and production state.

## Production Boundary

This manifest does not inspect or change the actual Infrastructure Services VM or any production service.

It does not create:

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

The manifest is intentionally a source-controlled statement that those target-environment items remain outstanding until separately authorized evidence demonstrates otherwise.
