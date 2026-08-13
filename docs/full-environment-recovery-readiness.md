# Full-Environment Recovery Readiness Validation

## Purpose

This document defines the source-controlled, non-activating GoreeCloud Tasks full-environment recovery-readiness gate.

The gate exists to prove that the application can be reconstructed after loss of its disposable primary runtime rather than proving only that a PostgreSQL dump can be restored into an otherwise intact environment.

Production remains **not approved** by this validation alone.

## Governing GoreeCloud Recovery Model

The validation follows the GoreeCloud Backup, Restore, and Recovery Policy and Standard and the documented three-layer recovery model.

The governing records distinguish among:

1. Proxmox snapshots for rapid local rollback while the primary virtualization environment remains healthy.
2. Proxmox virtual-machine backups on the dedicated backup server for complete VM or host-loss recovery.
3. Kopia plus application/database-aware backups for granular recovery of files, configuration, application state, and databases.

Those recovery layers are complementary rather than interchangeable.

For application-level recovery, the GoreeCloud recovery policy considers recovery complete only after required information is restored and validated, applications and databases operate correctly, ownership and permissions remain usable where applicable, required network and DNS behavior works, authentication works, monitoring is restored, backup protection resumes, the recovered dataset has a clear authoritative state, recovery documentation is current, and temporary recovery resources are appropriately handled.

The policy also permits temporary recovery environments only when they are sufficiently isolated to prevent accidental production overwrite, duplicate application activity, conflicting network identities or DNS, duplicate notifications or scheduled jobs, unintended outbound communication, and exposure of private restored information.

## Source-Controlled Components

### `scripts/tasks_full_environment_recovery_contract.json`

The contract records the required recovery stages and the target-environment evidence that this CI gate intentionally does not claim to prove.

Required stages are:

1. Source availability.
2. Recovery-documentation availability.
3. Configuration recreation.
4. Secret recreation.
5. Clean database creation.
6. Database restoration.
7. Application-semantic validation.
8. Private-publication restoration.
9. Authentication-boundary validation.
10. Monitoring-health restoration.
11. Backup-protection resumption.
12. Temporary recovery-resource cleanup.

The contract contains no credential values.

### `scripts/full_environment_recovery.compose.yml`

This Compose topology models only the application-level recovery environment:

- PostgreSQL on an internal backend network.
- GoreeCloud Tasks on the backend and internal reverse-proxy networks.
- Caddy on the reverse-proxy network and a synthetic approved NetBird-range ingress network.
- An approved private client with a source address inside `100.64.0.0/10`.

No service publishes a host port. The web application retains the established non-root, no-new-privileges, all-capabilities-dropped, file-backed-secret, secure-cookie, HTTPS-redirect, and Docker-only backend model.

The topology deliberately reuses the already validated CI-only `private_publication.Caddyfile` and `private_publication_client.py`. Caddy uses its internal CA only for disposable testing; this is not the production Porkbun DNS-01 certificate model.

### `scripts/validate_full_environment_recovery_readiness.sh`

The orchestrator performs the destructive-rebuild validation sequence and cleans all temporary runtime state afterward.

## Recovery Sequence Exercised by CI

The gate performs the following sequence:

1. Refuses to overwrite any existing repository `.env` or protected secret files.
2. Creates an isolated synthetic recovery bundle outside Docker volumes containing a recovery environment template and synthetic credential material.
3. Validates the recovery contract and the rendered Compose topology.
4. Starts a loopback-only disposable backup heartbeat receiver.
5. Builds the exact candidate source revision.
6. Creates a first disposable PostgreSQL environment.
7. Applies real Django migrations.
8. Seeds the production-representative synthetic Tasks recovery fixture.
9. Captures normalized application state and validates authentication/authorization semantics.
10. Uses the production-pattern `tasks_backup_job.sh` wrapper to create a PostgreSQL custom-format recovery point outside the disposable primary volumes.
11. Verifies the dump checksum and `pg_restore --list` readability.
12. Records a data-minimized recovery-evidence manifest containing only the source revision and recovery-point identifier, not secret values.
13. Destroys the entire disposable Compose environment **including volumes**.
14. Deletes the working `.env` and protected secret files to simulate loss of local runtime configuration.
15. Recreates the working configuration and secret files from the separate synthetic recovery bundle.
16. Starts a newly created PostgreSQL volume and proves the target public schema contains zero tables before restoration.
17. Restores the verified custom-format PostgreSQL recovery point into that clean target.
18. Runs Django system checks and migration checks.
19. Compares normalized pre-loss and post-restore application state exactly.
20. Re-runs semantic authentication and authorization recovery assertions.
21. Starts the recovered Tasks service, Caddy, and approved private client.
22. Revalidates the exact `https://tasks.goreecloud.com` private publication path, TLS hostname/SAN, login/CSRF boundary, and direct client isolation from the backend and database.
23. Uses the recovered private health path as the monitoring-restoration checkpoint.
24. Runs the production-pattern backup wrapper again against the **recovered** database.
25. Requires a distinct new post-recovery recovery point, valid checksum, readable PostgreSQL dump, healthy recovery-point age state, and the expected backup heartbeat transitions.
26. Verifies exact runtime network membership and absence of host-published ports.
27. Checks recovery evidence, runtime inspection, logs, and heartbeat records for synthetic secret leakage.
28. Ensures no partial backup artifacts remain.
29. Removes the disposable recovery runtime and temporary recovery bundle.

## Why This Is Stronger Than the Existing Database Restore Gate

The existing PostgreSQL backup/restore validation proves that database state can survive a dump-and-restore cycle while preserving Tasks application semantics.

This full-environment gate adds evidence for failure of the surrounding disposable runtime as well:

- Docker volumes are destroyed before recovery.
- Working application configuration is removed before recovery.
- Protected service secret files are removed and recreated through a separate recovery-bundle path.
- The database is proven empty before restoration.
- The application is rebuilt from source rather than reused from a still-running container.
- The private HTTPS publication path is re-established after restoration.
- Monitoring health is re-established after restoration.
- Backup protection is proven to resume **after** restoration by creating another valid recovery point.

This therefore exercises the application-level reconstruction order rather than only database recovery.

## Authoritative-State Rule

During the recovery test, the pre-loss environment is authoritative until it is intentionally destroyed.

The restored environment is treated as the candidate recovered state only after the database restore has completed. It is not treated as successfully recovered until exact state, application semantics, publication, health, and backup resumption all pass.

Production authority decisions during a real incident remain operator-controlled and must account for the actual failure scenario, recovery-point trustworthiness, and any security-incident considerations.

## What This Gate Does Not Prove

This CI exercise intentionally does **not** prove or authorize:

- restoration of the real Infrastructure Services VM from Proxmox backup;
- availability or health of the planned dedicated backup server;
- a real production Kopia repository;
- final production backup schedules or retention;
- final production backup encryption or credential-recovery procedures;
- independent physical, host, provider, or geographic recovery-copy placement;
- recovery of real Vaultwarden entries or other production credential stores;
- real AdGuard Home private DNS recovery;
- real NetBird peer, group, nameserver, or access-policy recovery;
- real Porkbun DNS-01 certificate issuance or a publicly trusted production certificate;
- real production Caddy listener restoration or host firewall restoration;
- real Uptime Kuma registration, retry/timeout settings, notification routing, or administrative receipt;
- recovery of a production GoreeCloud Manager integration identity, Viewer membership, bearer credential, or cross-stack network;
- recovery of a production ntfy publisher identity, ACL, token, subscriber setup, or end-client delivery;
- production repository-capacity monitoring;
- production host capacity or recovery-time-objective evidence;
- production Tasks deployment or activation.

The synthetic recovery bundle is independent from the disposable Docker volumes within one CI runner. It is **not** evidence of off-host, off-VM, off-provider, or off-site production independence.

## Relationship to the Three GoreeCloud Recovery Layers

This gate primarily validates the application/database portion of **Layer 3 — Kopia, Application, and Database Backups** by proving that source-controlled application artifacts, recreated configuration, recreated credential files, and a database-native recovery point can reconstruct a working Tasks application environment.

It does not replace:

- **Layer 1 — Proxmox snapshots**, which remain the rapid rollback mechanism for recent VM-level problems while the primary host/storage is healthy.
- **Layer 2 — Proxmox VM backups**, which remain the whole-VM recovery mechanism for loss of the Infrastructure Services VM, its storage, or its Proxmox host.

A real disaster may require Layer 2 first and Layer 3 afterward when a newer or more granular Tasks recovery point is required.

## Production Go/No-Go Evidence Still Required

Before a real full-environment recovery capability can be marked complete, target-environment evidence still needs to demonstrate at least:

- an approved production backup repository and multiple current recovery points;
- independent recovery-copy placement appropriate to the failure model;
- recoverable encryption and repository credentials;
- current Proxmox VM backup availability and tested VM-level restore as applicable;
- production Tasks database restoration from the approved repository;
- production file ownership and permissions after restoration;
- production AdGuard Home/private DNS recovery;
- production NetBird connectivity and access-policy recovery;
- production Porkbun DNS-01/public TLS and Caddy listener recovery;
- production firewall behavior;
- production application authentication and multi-user authorization after recovery;
- production Uptime Kuma monitoring and approved notification receipt after recovery;
- production backup automation, monitoring, integrity checks, capacity monitoring, and backup resumption;
- production Manager and ntfy integrations where enabled;
- recovery-critical documentation available independently from the system being recovered;
- cleanup or isolation of temporary recovery resources;
- a recovery-validation record with the actual recovery point, destination, results, problems, corrective actions, and follow-up work.

Until those controls are demonstrated, this gate provides strong disposable application-level recovery evidence but does not approve production activation or claim that a real Infrastructure Services VM disaster-recovery exercise has occurred.
