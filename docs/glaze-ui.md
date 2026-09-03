# GoreeCloud Tasks — Glaze UI 2.2 Consumer Contract

## Status

- **Target:** Glaze UI 2.2.0 Stable
- **Consumer status:** **Migration in progress**
- **Canonical Stable release revision:** `6731098b28dd0393faa878c70d989a221d714a20`
- **Accepted central visual source:** `0411b0f6dd877aea30e2c5674e1acde0105fd97b`
- **Historical rollback baseline:** Glaze UI 2.1.0
- **Product identity:** GoreeCloud Tasks / GoreeCloud Waypoint
- **Scope:** Django-rendered web interface controlled by this repository

This record defines the repository-local Glaze UI 2.2 implementation contract for GoreeCloud Tasks. The central Glaze UI release makes 2.2.0 the current Stable design-system target, but it does not auto-promote Tasks. This change **does not establish production acceptance** merely because the source declares 2.2 or automated checks pass.

## Adoption model

Tasks preserves its Waypoint task-management workflows and product-specific layout. It does not copy the canonical reference stylesheet wholesale and it does not import Candidate-named production aliases. The local `static/css/glaze.css` compatibility layer loads after product CSS and maps the existing interface onto the current Stable semantic contract.

The implementation boundary is:

1. Django templates preserve semantic structure and task workflows.
2. Product styles preserve Tasks/Waypoint composition.
3. `static/css/glaze.css` supplies the repository-local Glaze UI 2.2 semantic mapping.
4. `scripts/validate_glaze_ui_consumer.py` fails closed on source-contract regressions.
5. `scripts/validate_glaze_ui_rendered.py` renders representative authenticated and anonymous Django surfaces in Chromium and fails closed on geometry, reflow, theme, and accessibility-mode regressions.
6. Human visual review, release approval, deployment acceptance, and overall GoreeCloud Platform Stable eligibility remain separate gates.

## 2.2 presentation rule

Tasks follows the Stable rule:

**Solid where users read or make explicit critical decisions. Glazed where users interact with transient navigation or feedback chrome.**

The mapping therefore keeps durable task, project, collaboration, notification, authentication, status, and portability content on solid/raised surfaces. Top-level navigation chrome (`.topbar` and `.sidebar`) may use bounded Glaze material. Destructive/error/privacy-warning presentation remains certainty-first and effects-free.

Tasks does not add Signature, Intelligence, Universal Search, or Control Center surfaces merely to demonstrate design-system coverage. Existing local task search remains application search unless and until it is intentionally implemented against the separate Universal Search system contract.

## System Shell and Glaze budget

The shared page is classified as the **Application** surface. Top-level navigation and transient message chrome map to **System Overlay** semantics. Tasks currently has no separate dominant System Panel or Critical System shell surface.

The local layer records the ordinary 2.2 budget of at most one dominant Glaze panel and one to three small floating Glaze controls. Nested backdrop blur is explicitly suppressed. Adding a future drawer, command surface, or system panel must preserve this budget rather than stacking translucent surfaces by default.

## Appearance and semantic color

Tasks retains its product-specific semantic palette while implementing the current Stable role model:

- canvas and canvas accent;
- solid/raised and muted surfaces;
- primary and muted text;
- line/border treatment;
- accent and on-accent roles;
- information, success, warning, and danger;
- focus and selection.

Light and Dark follow browser/OS color-scheme behavior. An explicit `data-glz-appearance="deep-dark"` state provides the Deep Dark semantic fallback without deriving appearance from task or security status.

No remote font, icon, analytics, tracking, or presentation dependency is introduced by the compatibility layer.

## Input and target geometry

Glaze UI 2.2 requires a **48 CSS pixel** floor for touch-oriented shell/application controls and **56 CSS pixels** for Touch Assistance/far-view contexts where applicable.

Tasks therefore enforces:

- `--glaze-target-min: 48px` for buttons, inputs, selects, navigation items, task completion, and interactive label rows;
- `--glaze-target-assisted: 56px` when `data-glz-touch-assistance="true"` is active;
- explicit `data-glz-input="touch"` host semantics without relying only on pointer heuristics;
- native checkbox/radio control geometry wrapped in sufficiently large interactive rows.

The task-completion control grows in both dimensions under Touch Assistance rather than increasing only visual padding.

## Focus, state, and critical decisions

Visible focus is stronger than hover decoration and is supplied for both deterministic `:focus` fallback and `:focus-visible`. Selected navigation remains contained and non-color state is preserved by shape/border treatment.

Destructive actions, privacy warnings, and errors are kept on solid/certainty-first presentation. Glaze material must never imply that a visual status establishes authorization, privacy, security, backup, or recovery truth.

## 200% text, reflow, and adaptive layout

The repository supports explicit `data-glz-text-scale="200"` and large-text host states. Controls are allowed to grow vertically, labels may wrap, and layout containers must remain within the viewport instead of preserving compact fixed geometry.

The existing narrow-window Tasks layout remains authoritative for product composition. The 2.2 migration preserves DOM and keyboard order while improving reachable geometry; it does not rewrite task workflows for visual novelty.

Automated rendered acceptance exercises a 390×844 handheld viewport and a 1280×900 desktop viewport, and separately checks 200% text at the handheld width for document-level horizontal overflow.

## Accessibility and resilience

The compatibility layer includes:

- Reduced Motion;
- Reduced Transparency through both platform media behavior and explicit `data-glz-transparency="reduced"` state;
- Increased Contrast through browser preference and explicit `data-mode="increased-contrast"` state;
- Forced Colors with system color authority;
- Touch Assistance;
- 200% text/reflow;
- no-backdrop-filter solid fallback;
- reduced-performance effects-free fallback through `data-glz-performance="reduced"`;
- visible keyboard focus and semantic text selection.

Accessibility and capability outrank optical effects. Removing blur, shadows, or spatial motion must not remove controls, state, target geometry, or authorization boundaries.

## Automated rendered evidence

`scripts/validate_glaze_ui_rendered.py` builds real Django snapshots for:

- dashboard;
- task detail;
- notification settings;
- data/portability;
- login.

It checks representative Light/Dark handheld and desktop rendering plus Reduced Motion, Forced Colors, Touch Assistance, 200% text, Reduced Transparency, and Increased Contrast cases. The gate verifies the exact 2.2 release marker, last-loaded local compatibility layer, 48/56 target tokens, interactive control geometry, and document-level horizontal reflow.

A green automated rendered gate is application-specific automated evidence. It is not equivalent to Human Visual Excellence approval or production deployment acceptance.

## Platform-contract relationship

`goreecloud.platform.yaml` may record `implemented_version: "2.2.0"` once the repository-local 2.2 source implementation exists. While application acceptance is incomplete, the Glaze platform-system status remains migration-required/in-progress and overall `stable_eligible` remains false.

Documentation alone cannot satisfy the Glaze implementation gate, and source/rendered Glaze evidence cannot satisfy unrelated Identity, Wardveil Security, Privacy Shield, Everkeep, Mesh, Manager, recovery, release, or platform-acceptance gates.

## Promotion conditions

Tasks may advance beyond this migration state only when the applicable evidence is bound to the exact final Tasks revision, including:

1. source-contract validation;
2. normal Tasks CI;
3. automated rendered browser validation;
4. application-specific accessibility review where automation is insufficient;
5. Human Visual Excellence/visual acceptance when required by the current GoreeCloud release process;
6. release and deployment approval;
7. platform-contract conformance updates supported by verified evidence.

No gate may be weakened to obtain a pass, and no previous 1.x/2.1 acceptance may be inherited as 2.2 acceptance.

## Rollback

The Glaze UI design-system rollback reference is **2.1.0**. A Tasks application rollback must use an exact known-good Tasks revision and its corresponding evidence; it must not rewrite historical adoption records or relabel an older consumer as current-Stable conformant.
