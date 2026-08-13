# Production Recovery Evidence Contract

## Purpose

This document defines the source-controlled evidence contract for future material GoreeCloud Tasks production recovery tests.

The contract does **not** perform recovery, approve production deployment, or create a production recovery record. It defines the minimum non-secret evidence that a future recovery record must contain before a production recovery can be represented as complete or approved.

The implementation consists of:

- `scripts/production_recovery_evidence.schema.json` — machine-readable record structure.
- `scripts/validate_production_recovery_evidence.py` — standard-library validator, secret-content guard, cross-field consistency rules, and synthetic self-test.
- `.github/workflows/production-recovery-evidence-contract.yml` — permanent source-only CI gate.

## Governing GoreeCloud Requirements

The GoreeCloud Backup, Restore, and Recovery Policy requires a material recovery-validation record to capture the date, protected system or dataset, recovery point, recovery method, restore destination, restored services or information, validation performed, result, problems, corrective actions, administrator, and follow-up work.

The Backup, Restore, and Recovery Standard additionally requires critical implementations to address independent recovery copies, multiple recovery points, repository integrity, independently obtainable recovery credentials, monitoring and failure reporting, capacity, representative application recovery, ownership and permissions, databases, application services, network and DNS dependencies, backup resumption, independently available recovery documentation, and evidence of the restore test.

A recovery is not complete merely because the application becomes reachable. The documented GoreeCloud completion criteria include restored and validated information, operational applications and databases, correct ownership and permissions, required network/DNS/HTTPS and authentication, monitoring restoration, resumed backup protection, unambiguous authoritative state, current recovery documentation, and appropriate handling of temporary recovery resources.

The Sensitive Information Separation Standard requires ordinary documentation, logs, and source control to contain non-secret references rather than active passwords, tokens, private keys, recovery codes, backup passwords, or other reusable authentication material.

## Record Model

A conforming record contains ten top-level sections.

### Identity

`schema_version` and `record_type` identify the record format.

### Protected System

The record identifies:

- GoreeCloud Tasks.
- The Infrastructure Services VM environment.
- The recovery classification.
- The exact 40-character source revision recovered.

The source revision provides software-state traceability but does not replace evidence of restored data or infrastructure state.

### Test Metadata

The record includes:

- A non-secret test identifier.
- Start time.
- Completion time.
- Administrator.
- Reviewer.

All timestamps must include an explicit timezone or `Z` suffix. Completion cannot precede the test start.

### Recovery Point

The record must identify the recovery point without embedding its credential value. Required evidence includes:

- Backup technology.
- Recovery-point identifier.
- Non-secret repository-record reference.
- Reason the recovery point was selected.
- Trust assessment.
- Integrity result.
- Multiple-recovery-point availability.
- Independent-copy result.
- Explicit independence dimensions.
- Non-secret credential-record reference.
- Whether credentials can be obtained independently.
- An explicit assertion that no active credential value is recorded.

A future production **go** decision requires a trusted, integrity-verified recovery point, multiple recovery points, verified independent protection, and independently recoverable credentials.

The validator requires a production go decision to demonstrate recovery-copy independence from the protected virtual machine. When the record classifies the workload as `critical`, the recovery copy must additionally be independent from the source server.

### Recovery Method

The record identifies:

- Recovery method.
- Restore destination.
- Components restored.

A restore destination must be named clearly enough to distinguish a test environment from production and to preserve authoritative-state clarity.

### Material Validation Checks

The record must explicitly answer every material check rather than omit failed or unperformed checks:

- Restored information validated.
- Database operational.
- Application operational.
- Ownership and permissions validated.
- Network access validated.
- DNS validated.
- HTTPS validated.
- Authentication validated.
- Authorization and privacy validated.
- Monitoring restored.
- Notification receipt validated.
- Backup protection resumed.
- Repository integrity validated.
- Repository capacity safe.
- Recovery credentials accessible.
- Recovery documentation independently available.
- Temporary recovery resources handled.

For a `go` decision every check must be `true`. A missing check is a schema failure; an explicit false check makes a `go` decision invalid.

### Authoritative State

The record must state whether the recovered copy is:

- `production-promoted`
- `test-only-not-authoritative`
- `not-promoted`

It must also identify who made the decision, when it was made, and why.

A no-go record may not claim `production-promoted`. A go record must explicitly claim `production-promoted`. This prevents a technically successful alternate restore from silently becoming the source of truth.

### Result

The record captures:

- `passed`, `failed`, or `partial`.
- Problems encountered.
- Corrective actions.
- Follow-up requirements.
- Whether any material problem remains unresolved.

Failed and partial restore-test records are valid evidence records when they are complete and are correctly classified **no-go**. A failed restore should be recorded rather than hidden merely because it cannot approve production recovery.

### Decision

The final decision is either `go` or `no-go` and contains:

- Whether production recovery was separately approved.
- Decision maker.
- Review time.
- Rationale.

The validator checks internal consistency. It does **not** grant operational authority. A future `go` record may set `production_recovery_approved` to `true` only after the user or another separately authorized GoreeCloud authority has actually made that production decision.

## Fail-Closed Go Rules

A record cannot evaluate `GO` unless all of the following are true:

1. Schema and secret-content validation pass.
2. Test timestamps are ordered correctly.
3. The result is `passed`.
4. No material problem remains unresolved.
5. Every required validation check is true.
6. The recovery point is trusted.
7. Recovery-point integrity is verified.
8. Multiple recovery points are available.
9. Independent recovery-copy protection is verified.
10. Required independence dimensions are demonstrated.
11. Recovery credentials are independently recoverable.
12. The authoritative-state decision is `production-promoted`.
13. The record says the production recovery was separately approved.
14. The review occurs after recovery completion and the authoritative-state decision.

A passed technical test may still be recorded as `NO-GO` when production promotion has not been separately approved.

## Failed and Partial Recovery Records

The contract intentionally accepts complete `failed` and `partial` records when they use a no-go decision and do not identify the recovered copy as production-promoted.

This supports the GoreeCloud requirement that failed restores remain visible evidence requiring investigation and another restore test after corrective action.

The validator rejects a failed or partial record that attempts to declare `go`.

## Secret-Content Guard

Before structural validation, the validator recursively inspects field names and string values.

It rejects common secret-bearing field names such as:

- password
- passphrase
- token
- API key
- client secret
- private key
- credential value
- recovery code
- session token
- connection string

It also rejects string content that resembles:

- PEM private keys.
- `Authorization: Bearer` values.
- Bearer-token material.
- password/token/key assignments containing active-looking values.
- URLs containing embedded user/password credentials.
- secret-bearing URL query parameters.

This is a defensive control, not a general-purpose secret scanner. Operators must still review recovery evidence before storage or sharing.

The evidence record should reference a stable protected credential record, such as a Vaultwarden item name or approved credential record, without copying the active value.

## Storage Boundary

The schema and validator belong in source control.

Actual production recovery evidence should be stored in the approved internal recovery/validation record location selected for GoreeCloud documentation. A production record may contain internal infrastructure details that are inappropriate for a public repository even when they are not reusable secrets.

A real record should therefore be validated with this tool before being stored in its approved authoritative location; the record should not be committed to this repository merely because the schema lives here.

## Usage

Validate the contract itself and all built-in synthetic cases:

```bash
python3 scripts/validate_production_recovery_evidence.py --self-test
```

Validate a future recovery record:

```bash
python3 scripts/validate_production_recovery_evidence.py /path/to/recovery-evidence.json
```

Successful validation prints either:

- `Valid GoreeCloud Tasks recovery evidence record: GO`
- `Valid GoreeCloud Tasks recovery evidence record: NO-GO`

The second result can represent a complete and useful failed restore-test record. It is not a validator failure unless the record itself is malformed, unsafe, or internally inconsistent.

## Permanent Synthetic Test Matrix

The self-test proves that the validator:

- accepts a fully complete synthetic GO record;
- accepts a complete failed synthetic NO-GO record;
- rejects missing required evidence;
- rejects secret-looking content;
- rejects go with backup protection not resumed;
- rejects go with an uncertain recovery point;
- rejects go with unresolved material problems;
- rejects critical go without source-server independence;
- rejects no-go records marked production-approved;
- rejects no-go records that claim production promotion;
- rejects completion timestamps preceding the test start;
- rejects secret-bearing field names.

All fixtures are generated in memory and contain synthetic values only.

## Production Boundary

This contract does not prove that any production recovery evidence currently exists.

It does not create, inspect, or modify:

- production Tasks data;
- the Infrastructure Services VM;
- Proxmox backups;
- the planned dedicated backup server;
- a Kopia repository;
- Vaultwarden records;
- recovery credentials;
- AdGuard Home;
- NetBird;
- Porkbun DNS-01;
- Caddy listeners;
- firewall state;
- Uptime Kuma;
- ntfy;
- Manager integration state;
- production backup schedules or retention;
- independent off-site storage;
- deployment or service activation.

It provides a fail-closed record format so future target-environment evidence cannot be represented as complete while omitting a material GoreeCloud recovery requirement.
