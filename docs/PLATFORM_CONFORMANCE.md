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

Every system must be evaluated under the canonical repository-root `goreecloud.platform.yaml` declaration. An integration may be recorded as `implemented`, `partial`, `planned`, `not-applicable`, or `unknown` only when repository evidence supports that state. `not-applicable` requires a substantive explanation and must be reevaluated when the application role changes.

Repository-local management, privacy, security, continuity, interface, coordination, or identity behavior does not by itself establish acceptance by the corresponding Integral Platform System. Branding, prose, a badge, an implementation marker, or intended future integration cannot substitute for producer-system contracts and acceptance evidence.

## Current Glaze UI gating

GLAZE UI V1.0 (`1.0.0`) is the official and only current GoreeCloud design-system target. The canonical V1 source is an official reset baseline whose production acceptance remains pending. No pre-reset Glaze implementation or acceptance is automatically V1 evidence, and no downstream application is upgraded by declaration.

This Tasks candidate contains a repository-local V1 source mapping and automated rendered validator, but the consumer remains migration-in-progress and nonconformant until exact-head and application-level evidence is complete and the applicable upstream production-eligibility boundary permits promotion.

No release or service state may be classified or retained as Stable unless native application qualification and all applicable current Integral Platform System requirements are complete, validated, and accepted. Missing, materially incomplete, outdated, unknown, unverified, or reset-invalidated required integration remains a Stable blocker.

## Evidence and production boundary

Source conformance, exact-revision CI, target-environment acceptance, production deployment, backup/restore evidence, release authorization, and Stable qualification are separate gates. Passing Platform Contract validation proves that the declaration is structurally valid and internally governed; it does not manufacture missing runtime evidence or production approval.

Repository CI, release documentation, project specifications, and change logs must progressively enforce and record this contract. Where repository source, canonical GoreeCloud governance, and historical records differ, current canonical governance controls current behavior while immutable revision history remains audit evidence.
