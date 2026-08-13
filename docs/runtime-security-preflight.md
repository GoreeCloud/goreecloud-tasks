# GoreeCloud Tasks — Runtime Security Preflight

## Purpose

This document defines the non-activating runtime-security evidence required before GoreeCloud Tasks can be approved for production deployment.

The preflight deliberately separates disposable CI evidence from target-host evidence. CI proves that the source-controlled container and file-permission model behaves as designed. The future Infrastructure Services VM must still be inspected directly before any production owner, group, or numeric GID is recorded as authoritative.

## Production Boundary

This work does not deploy Tasks, create production identities or credentials, change `/srv/docker`, create networks, publish ports, configure DNS/Caddy/NetBird/firewall rules, alter Manager or ntfy, configure backups, or authorize production activation.

## Target-Host Metadata Checker

`scripts/check_target_runtime_preflight.sh` is read-only. It validates metadata only and does not read or print configuration or credential contents.

The operator supplies the already-inspected target paths plus the expected administrative owner UID, service-readable GID, and intended application secret GID. The checker requires:

- protected environment-file ownership and mode;
- a private secret directory;
- required service-readable files with restrictive ownership, group, and mode;
- no symbolic-link substitution for the inspected files;
- a host account matching the expected owner UID;
- a host group matching the expected GID;
- exact agreement between the file GID and the intended application supplementary GID; and
- reachable Docker Engine and Docker Compose installations.

The checker fails closed when required metadata is missing or inconsistent. It does not create or repair accounts, groups, files, ownership, or permissions.

## Disposable CI Gate

`scripts/validate_runtime_security_preflight.sh` creates synthetic CI-only files and proves both the accepted state and important negative cases. It requires the metadata checker to reject world-readable service files and GID drift.

The gate then validates the current source and live disposable runtime. It requires:

- `.env` and `secrets/` to remain excluded from the Docker build context;
- a digest-pinned application base image;
- a non-root application image user;
- `no-new-privileges` on the web container;
- all Linux capabilities dropped from the web container;
- an internal PostgreSQL network;
- no privileged web or database container;
- no host networking, host PID namespace, host IPC namespace, or Docker-socket access;
- no PostgreSQL host-port binding;
- only loopback development publication for the web service;
- the application process running with UID 10001 and the expected supplementary service group;
- required mounted files readable but not writable by the application;
- read-only mounted-file behavior with the expected restrictive mode and GID;
- successful real migrations and live health; and
- no synthetic CI credential marker in rendered Compose or `docker inspect` output.

## Development Versus Production

The ordinary repository Compose stack remains a development stack and uses a loopback-only host port for controlled local access. Passing this gate does not convert that binding into an approved production publication model.

Production still requires separate private-publication validation, target-host runtime inspection, monitoring and alert delivery, approved backup coverage, and final multi-user acceptance.

## Target Runtime Evidence Still Outstanding

Before production deployment, the actual target host must provide authoritative evidence for:

- the final administrative owner UID;
- the final service-readable group and GID;
- the active Tasks stack and protected-file locations;
- actual ownership, group, mode, ACL, link, and mount-boundary state;
- the final application supplementary GID;
- current Docker Engine and Compose versions; and
- the final running-container security properties.

The CI-only numeric GID proves the mechanism works. It must not be treated as the future production GID unless direct target-host inspection independently establishes that value.

## Governing Principle

I will not weaken host permissions to make a container start, and I will not guess a production UID or GID from CI. Production values must come from the inspected target runtime and remain limited to the approved administrative owner and explicitly authorized service readers.
