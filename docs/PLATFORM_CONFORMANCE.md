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

Every system must be evaluated under the canonical repository-root `goreecloud.platform.yaml` declaration. An integration may be recorded as `implemented`, `partial`, `planned`, `not-applicable`, or `unknown` only when the repository evidence supports that state. `not-applicable` requires a substantive explanation and must be reevaluated when the application role changes.

Repository-local management, privacy, security, continuity, interface, coordination, or identity behavior does not by itself establish acceptance by the corresponding Integral Platform System. Branding, prose, a badge, or an intended future integration cannot substitute for producer-system contracts and acceptance evidence.

## Current Stable gating

Glaze UI 2.2.0 Stable is the current mandatory design-system target. Earlier accepted or candidate consumer contracts remain historical/source evidence but do not satisfy current Stable qualification unless the application completes its own 2.2 migration and acceptance.

No release or service state may be classified or retained as Stable unless native application qualification and all applicable current Integral Platform System requirements are complete, validated, and accepted. Missing, materially incomplete, superseded, outdated, unknown, or unverified required integration remains a Stable blocker.

The current Tasks source has a partial GoreeCloud Manager integration and an older Glaze UI 1.3 adoption candidate. Other current platform-system requirements remain separately evidence-gated by `goreecloud.platform.yaml`; this document does not upgrade those statuses.

## Evidence and production boundary

Source conformance, exact-revision CI, target-environment acceptance, production deployment, backup/restore evidence, release authorization, and Stable qualification are separate gates. Passing Platform Contract validation proves that the declaration is structurally valid and internally governed; it does not manufacture missing runtime evidence or production approval.

Repository CI, release documentation, project specifications, and change logs must progressively enforce and record this contract. Where repository source, canonical GoreeCloud governance, and historical documentation differ, current canonical governance controls and the discrepancy must be corrected without rewriting historical evidence.
