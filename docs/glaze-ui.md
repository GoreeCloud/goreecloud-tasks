# GoreeCloud Tasks — Glaze UI Consumer Contract

## Status

- **Target:** Glaze UI 1.3.0 Stable semantic contract
- **Consumer status:** Adoption Candidate
- **Canonical Glaze UI source reviewed:** `GoreeCloud/glaze-ui` at `96cc27050c098a5f06f571923f0cb9be54989a92`
- **Product identity:** GoreeCloud Tasks / GoreeCloud Waypoint
- **Scope:** Django-rendered web interface in this repository

This record establishes a version-specific Glaze UI adoption contract for GoreeCloud Tasks. It does **not** claim that Tasks has completed production visual acceptance. Source-level conformance and application-level visual acceptance are separate gates.

## Adoption model

Tasks does not copy the canonical Glaze UI reference stylesheet wholesale. The existing Tasks interface remains product-specific and keeps its Waypoint task-management composition. `static/css/glaze.css` maps the existing interface onto Glaze UI 1.3 semantic roles and loads after the product styles so the shared contract can correct accessibility, theme, material, target, and resilience behavior without erasing product identity.

The repository-level contract is:

1. existing Django templates preserve semantic HTML and application workflows;
2. existing product CSS preserves task-specific composition;
3. `static/css/glaze.css` provides the shared Glaze semantic compatibility layer;
4. `scripts/validate_glaze_ui_consumer.py` fails closed if the contract regresses;
5. application-level visual acceptance remains required before the consumer can be promoted from Adoption Candidate to an aligned Stable consumer in the central Glaze registry.

## Stable semantic mapping

### Color and themes

Tasks maps the canonical Glaze UI 1.3 light and dark semantic colors into local CSS custom properties. The interface follows the operating-system/browser color-scheme preference and declares `light dark` support.

The compatibility layer includes semantic roles for:

- canvas and canvas accent;
- surface, strong surface, and muted surface;
- primary and muted text;
- line/border treatment;
- primary and secondary accent;
- on-accent text;
- information, success, warning, and danger;
- focus ring and text selection.

No remote font, icon, analytics, or presentation dependency is introduced by the Glaze layer.

### Surface hierarchy

Tasks uses the Glaze material hierarchy selectively:

- **Canvas** is the application background.
- **Functional Glass** is limited to top-level navigation chrome (`.topbar` and `.sidebar`).
- **Solid/Raised** surfaces remain the default for task editors, quick-add, project cards, notification cards, panels, authentication cards, and other ordinary content.
- A solid fallback replaces glass when backdrop filtering is unavailable or reduced transparency is requested.

Tasks does not use Clear Glass because the current product surfaces are not controls floating over visually rich media.

### Actionable targets

The compatibility layer enforces the Glaze UI 1.3 minimum actionable target of **44 CSS pixels** for ordinary buttons, text-like controls, inputs, selects, navigation items, and the task completion control.

Checkboxes and radio controls keep native control geometry, while their interactive label rows receive the minimum target size.

This specifically corrects pre-adoption Tasks controls that were smaller than the Stable Glaze minimum, including the previous 24-pixel completion control and 36–42-pixel navigation rows.

### Focus and selection

Keyboard focus uses the shared semantic focus-ring color, width, and offset through `:focus-visible` across links, buttons, form controls, and disclosure summaries. Text selection uses the shared semantic selection role.

Existing Django form labels and validation messages remain visible rather than becoming placeholder-only fields.

### Motion and resilience

The compatibility layer provides:

- reduced-motion handling that removes nonessential transition/animation duration;
- reduced-transparency solid-surface fallback;
- increased-contrast border reinforcement;
- forced-colors semantic remapping and visible focus/selection behavior;
- no-backdrop-filter solid navigation fallback.

These are fail-closed source requirements in the repository validator.

### Adaptive layout

Tasks retains its current Stable 1.3 adaptive-window behavior rather than adopting the separate Glaze UI 1.4 form-factor Candidate. Existing breakpoints transform the sidebar, quick-add composition, project/member layouts, collaboration panes, notification layouts, and other task-management surfaces for narrower windows.

This contract does **not** import or claim Glaze UI 1.4 Mobile/Tablet/Desktop/TV semantics.

## Candidate boundaries

The following remain outside this source-level adoption claim:

- final browser-rendered light/dark acceptance of representative Tasks workflows;
- 200% browser zoom/reflow acceptance;
- visual inspection of keyboard-focus sequences across representative workflows;
- application-specific forced-colors and reduced-motion visual review;
- native Mobile/Tablet/Desktop/TV acceptance from the Glaze UI 1.4 Candidate;
- production deployment or runtime migration.

Until the applicable visual acceptance evidence is completed, the repository must describe the Glaze consumer state as **Adoption Candidate** rather than Stable-aligned production acceptance.

## Promotion conditions

Tasks may be promoted to an aligned current-Stable consumer in the central Glaze registry only after:

1. this source contract passes on the exact final Tasks candidate SHA;
2. the normal Tasks CI suite passes on that exact SHA;
3. representative rendered Tasks workflows are accepted in light and dark appearances;
4. keyboard focus, 44-pixel targets, reflow, reduced motion, contrast/forced-colors, and no-backdrop-filter behavior are accepted where applicable;
5. no required visual gate is weakened to obtain a pass;
6. the final Tasks merge commit is recorded in the central Glaze consumer registry.

## Rollback

If this adoption layer causes a regression, revert the Tasks adoption commit/merge rather than changing the canonical Glaze UI 1.3 contract or weakening the consumer validator. The pre-adoption Tasks application remains the rollback baseline.
