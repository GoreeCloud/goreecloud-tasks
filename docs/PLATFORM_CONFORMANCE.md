# Mandatory Native and Platform Conformance

Effective August 24, 2026, this GoreeCloud application must be built and maintained as original GoreeCloud-owned software from the ground up.

Small, technically necessary foundational dependencies remain permitted where independent reimplementation would reduce security, correctness, interoperability, standards compliance, or maintainability. Examples include cryptographic and protocol libraries, database engines, operating-system APIs, web frameworks, and comparable critical foundations. Such dependencies must not become the application shell or define the GoreeCloud product identity.

## Integral Platform Systems

Current GoreeCloud Platform Contract 0.3 conformance evaluates all eight Integral Platform Systems:

1. GoreeCloud Manager
2. Privacy Shield
3. Wardveil Security
4. Everkeep
5. GLAZE UI
6. GoreeCloud Mesh
7. GoreeCloud Identity
8. GoreeCloud Sync

Every system must be evaluated under the canonical repository-root `goreecloud.platform.yaml` declaration. Platform Contract 0.3 uses the governed result vocabulary `applicable-conformant`, `applicable-migration-required`, `applicable-blocked`, `applicable-nonconformant`, and `not-applicable-justified`. A positive or non-applicable result requires the evidence and justification required by the central contract; missing implementation must not be hidden behind a not-applicable classification.

Repository-local management, privacy, security, continuity, interface, coordination, identity, or synchronization behavior does not by itself establish acceptance by the corresponding Integral Platform System. Branding, prose, a badge, source implementation, or intended future integration cannot substitute for producer-system contracts and acceptance evidence.

## Current GLAZE UI gating

GoreeCloud Tasks currently has a deliberately mixed consumer state.

The existing web application still implements the repository-local GLAZE UI V1.0 (`1.0.0`) migration baseline. Its exact historical source revision is `70909bbdccad378fb7281ae1842e2f5beed64c38`. Its source mapping and rendered validation remain useful web migration evidence, but they do not establish acceptance against the current Stable consumer target.

The native Android Development client targets current Stable GLAZE UI V1.4 (`1.4.0`) at exact Stable source revision `84cb3db4884042f0fa25ed6d475a127fb110f596`. Android source adoption remains `ADOPTION_IN_PROGRESS`; it does not establish rendered, accessibility, representative-device, performance, release, production, or V1.4.1 human/manual/physical-device acceptance.

The current GoreeCloud Platform Contract 0.3 consumer requirement is GLAZE UI `1.4.0`. Because the web surface remains on the older V1.0 migration source and Android application acceptance is incomplete, the repository-wide GLAZE UI result correctly remains `applicable-migration-required` and global conformance remains `nonconformant`.

No release or service state may be classified or retained as Stable unless native application qualification and all applicable current Integral Platform System requirements are complete, validated, and accepted. Missing, materially incomplete, outdated, blocked, migration-required, nonconformant, or unverified required integration remains a Stable blocker.

## Identity and Sync separation

The Android Identity acceptance-proof seam is source-ready only. It does not establish deployed native application registration, credential exchange, protected credential storage, session runtime, server-side Identity migration, or production Identity acceptance.

GoreeCloud Sync is an independent Platform System. It must not be inferred from the Django data model, Calendar integration, offline cache plans, background work, or Everkeep backup/recovery. Accepted change tracking, version coordination, authorized replication, conflict reconciliation, offline resume, and cross-device continuity remain blocked.

## Evidence and production boundary

Source conformance, exact-revision CI, target-environment acceptance, production deployment, backup/restore evidence, release authorization, and Stable qualification are separate gates. Passing Platform Contract validation proves that the declaration is structurally valid and produces a bounded computed conformance result; it does not manufacture missing runtime evidence or production approval.

Repository CI, release documentation, project specifications, and change logs must progressively enforce and record this contract. Where repository source, canonical GoreeCloud governance, and historical records differ, current canonical governance controls current behavior while immutable revision history remains audit evidence.
