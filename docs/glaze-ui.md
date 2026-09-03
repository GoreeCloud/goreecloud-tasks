# GoreeCloud Tasks — GLAZE UI V1.0 Consumer Contract

## Status

- **Target:** GLAZE UI V1.0 (`1.0.0`)
- **Upstream lifecycle:** Official reset baseline; production acceptance pending
- **Tasks consumer status:** **Migration in progress**
- **Canonical repository:** `GoreeCloud/goreecloud-glaze-ui`
- **Exact source authority:** `70909bbdccad378fb7281ae1842e2f5beed64c38`
- **Product identity:** GoreeCloud Tasks / GoreeCloud Waypoint
- **Scope:** Django-rendered web interface controlled by this repository

This record defines the repository-local GLAZE UI V1.0 mapping for GoreeCloud Tasks. It does **not establish production acceptance**, Production Stable status, or V1 consumer conformance. The V1 namespace is official, but upstream production eligibility and downstream application acceptance remain separately gated.

## Authority boundary

The V1 implementation-facing authority is the canonical Glaze repository at the exact source revision above, including `VERSION`, `GLAZE_UI_V1_0.md`, `registry/lifecycle.json`, `css/glaze-v1.0.0.css`, V1 component/System Shell contracts, `acceptance/v1.0-stable.md`, and `scripts/validate_glaze_v1.py`.

Tasks does not create a competing design system. `static/css/glaze.css` is a repository-local consumer mapping that mirrors the applicable canonical `glz1` semantic roles while preserving Tasks-specific workflows and composition. The local mapping is intentionally self-contained: no remote font, icon, stylesheet, analytics, tracking, or presentation dependency is introduced.

## Adoption model

The repository-level boundary is:

1. Django templates preserve semantic structure and task workflows.
2. Product CSS preserves Tasks/Waypoint composition.
3. `static/css/glaze.css` maps the controlled presentation onto V1 `glz1` semantics and loads after product CSS.
4. `scripts/validate_glaze_ui_consumer.py` fails closed on source-contract regressions.
5. `scripts/validate_glaze_ui_rendered.py` renders representative Django surfaces in Chromium and checks geometry, reflow, appearance, and accessibility modes.
6. Exact-head CI, application visual/accessibility acceptance, upstream production eligibility, release approval, deployment acceptance, and overall Platform Stable eligibility remain separate gates.

## V1 presentation rule

**Solid where users read or make explicit critical decisions. Glazed where users interact with transient navigation, command, search, control, or feedback chrome.**

Tasks therefore keeps durable task, project, collaboration, authentication, notification, data-portability, and critical-decision content on solid/raised surfaces. Top-level navigation and transient feedback chrome may use bounded Glaze material.

Tasks does not add Universal Search, Control Center, Signature, Intelligence, or other V1 features merely to claim coverage. Existing Tasks search remains application search unless it is intentionally implemented against the applicable V1 system contract.

## Semantic mapping

The local layer uses the canonical V1 namespace for applicable roles, including:

- `--glz1-canvas`, `--glz1-base`, and `--glz1-raised`;
- `--glz1-text-primary`, `--glz1-text-secondary`, and `--glz1-line`;
- `--glz1-focus`, `--glz1-success`, `--glz1-warning`, and `--glz1-critical`;
- `--glz1-overlay-bg`, `--glz1-overlay-blur`, and V1 surface geometry;
- `--glz1-target-shell: 48px` and `--glz1-target-assisted: 56px`;
- explicit Deep Dark, Reduced Transparency, Increased Contrast, Forced Colors, Reduced Motion, large-text, touch, and Touch Assistance host states.

The Tasks compatibility layer may contain product-specific selectors, but it must not redefine a competing GoreeCloud design-language authority.

## Material and critical-state boundaries

`.topbar` and `.sidebar` are treated as bounded System Overlay navigation chrome. Nested backdrop blur is suppressed. Durable reading and editing surfaces remain solid or raised.

Destructive actions, privacy warnings, authentication decisions, errors, and other critical decisions remain certainty-first and effects-free. Glaze presentation must never manufacture authorization, privacy, security, backup, recovery, identity, or trust state owned by another GoreeCloud system.

## Input and target geometry

V1 requires a 48 CSS-pixel reference floor for touch-oriented application controls and 56 CSS pixels for Touch Assistance or far-view contexts where applicable.

Tasks enforces those floors for buttons, text-like controls, navigation items, interactive label rows, and the task completion control. The explicit V1 host vocabulary includes `data-glz-input="touch"` and `data-glz-touch-assistance="true"` so target behavior is testable independently of pointer heuristics.

## Accessibility and resilience

The migration includes:

- a keyboard skip link and stable main-content focus target;
- visible deterministic focus and `:focus-visible` treatment;
- 200% text/reflow support without document-level horizontal overflow on the representative handheld gate;
- Reduced Motion;
- Reduced Transparency;
- Increased Contrast;
- Forced Colors;
- explicit touch and Touch Assistance geometry;
- no-backdrop-filter solid fallback;
- reduced-performance effects-free fallback;
- semantic status treatment that does not depend on color alone where the existing component structure permits non-color state.

Accessibility and capability outrank optical effects. Removing blur, shadow, or nonessential motion must not remove controls, state, target geometry, or authorization boundaries.

## Automated rendered evidence

`scripts/validate_glaze_ui_rendered.py` builds real Django snapshots for:

- dashboard;
- task detail;
- notification settings;
- data/portability;
- login.

It checks representative Light and Dark rendering at handheld and desktop sizes, plus Reduced Motion, Forced Colors, Touch Assistance, 200% text, Reduced Transparency, and Increased Contrast cases.

A green automated rendered gate is application-specific automated evidence only. It is not Human Visual Excellence approval, upstream V1 Production Stable acceptance, release approval, or production deployment acceptance.

## Platform Contract relationship

`goreecloud.platform.yaml` records the repository-local V1 source migration as `partial` and keeps overall conformance `nonconformant`. The Glaze entry may name version `1.0.0` because this branch implements the repository-local source mapping, but that version field is not a conformance or production-eligibility claim.

Documentation and source presence cannot satisfy unrelated Identity, Wardveil Security, Privacy Shield, Everkeep, Mesh, Manager, recovery, release, deployment, or platform-acceptance gates.

## Promotion conditions

Tasks may advance beyond migration-in-progress only when the applicable current requirements are satisfied against the exact final Tasks revision, including:

1. source-contract validation;
2. normal Tasks CI;
3. automated rendered browser validation;
4. application-specific accessibility and visual review where automation is insufficient;
5. upstream GLAZE UI V1.0 production eligibility when required for consumer promotion;
6. release and deployment approval;
7. evidence-backed Platform Contract updates.

No gate may be weakened to obtain a pass, and no pre-reset Glaze acceptance is inherited as V1 evidence.

## Rollback

If this V1 migration causes a regression, revert the exact Tasks migration commit or merge to the previously accepted Tasks revision rather than weakening the canonical V1 contract or its validators. The rollback reference is an exact known-good Tasks commit, not a retired Glaze product version.
