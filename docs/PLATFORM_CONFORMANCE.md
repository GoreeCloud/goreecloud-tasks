# Mandatory Native and Platform Conformance

Effective August 24, 2026, this GoreeCloud application must be built and maintained as original GoreeCloud-owned software from the ground up.

Small, technically necessary foundational dependencies remain permitted where independent reimplementation would reduce security, correctness, interoperability, standards compliance, or maintainability. Examples include cryptographic and protocol libraries, database engines, operating-system APIs, web frameworks, and comparable critical foundations. Such dependencies must not become the application shell or define the GoreeCloud product identity.

## Integral Platform Systems

Current GoreeCloud platform conformance evaluates all seven Integral Platform Systems:

1. GoreeCloud Manager
2. Privacy Shield
3. Wardveil Security
4. Everkeep
5. Glaze UI
6. GoreeCloud Mesh
7. GoreeCloud Identity

Every system must be evaluated under the canonical repository-root `goreecloud.platform.yaml` declaration. Platform Contract v0.2 uses the governed result vocabulary `applicable-conformant`, `applicable-migration-required`, `applicable-blocked`, `applicable-nonconformant`, and `not-applicable-justified`. A positive or non-applicable result requires the evidence and justification required by the central contract; missing implementation must not be hidden behind a not-applicable classification.

Repository-local management, privacy, security, continuity, interface, coordination, or identity behavior does not by itself establish acceptance by the corresponding Integral Platform System. Branding, prose, a badge, source implementation, or intended future integration cannot substitute for producer-system contracts and acceptance evidence.

## Current Glaze UI gating

GoreeCloud Tasks currently implements the repository-local GLAZE UI V1.0 (`1.0.0`) migration baseline. The current GoreeCloud Platform Contract v0.2 consumer requirement is Glaze UI `1.1.0`. The existing 1.0.0 implementation therefore remains `applicable-migration-required`; its source mapping and rendered validation are useful migration evidence but do not establish current Glaze UI conformance.

This Tasks candidate remains migration-in-progress and nonconformant until the application is migrated to the current required baseline and the exact-head, application-level, accessibility, release, and applicable production-eligibility gates are satisfied.

No release or service state may be classified or retained as Stable unless native application qualification and all applicable current Integral Platform System requirements are complete, validated, and accepted. Missing, materially incomplete, outdated, blocked, migration-required, nonconformant, or unverified required integration remains a Stable blocker.

## Evidence and production boundary

Source conformance, exact-revision CI, target-environment acceptance, production deployment, backup/restore evidence, release authorization, and Stable qualification are separate gates. Passing Platform Contract validation proves that the declaration is structurally valid and produces a bounded computed conformance result; it does not manufacture missing runtime evidence or production approval.

Repository CI, release documentation, project specifications, and change logs must progressively enforce and record this contract. Where repository source, canonical GoreeCloud governance, and historical records differ, current canonical governance controls current behavior while immutable revision history remains audit evidence.
