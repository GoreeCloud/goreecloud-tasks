#!/usr/bin/env python3
"""Fail-closed source validation for the GoreeCloud Tasks Glaze UI 2.2 consumer contract."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_VERSION = "2.2.0"
GLAZE_RELEASE_REVISION = "6731098b28dd0393faa878c70d989a221d714a20"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"Tasks Glaze UI consumer validation failed: {message}")


def read(path: str) -> str:
    candidate = ROOT / path
    require(candidate.is_file(), f"missing required file: {path}")
    return candidate.read_text(encoding="utf-8")


def main() -> None:
    base = read("templates/base.html")
    glaze = read("static/css/glaze.css")
    contract = read("docs/glaze-ui.md")
    rendered = read("scripts/validate_glaze_ui_rendered.py")
    workflow = read(".github/workflows/ci.yml")

    # Exact Stable target and downstream lifecycle boundary.
    require(f'data-glaze-ui="{TARGET_VERSION}"' in base, "base template must declare Glaze UI 2.2.0")
    require(
        f'data-glaze-release-revision="{GLAZE_RELEASE_REVISION}"' in base,
        "base template must pin the canonical Glaze UI 2.2 Stable release revision",
    )
    require(
        'data-glaze-consumer-status="migration-in-progress"' in base,
        "base template must not claim completed production acceptance",
    )
    require("viewport-fit=cover" in base, "viewport-fit=cover is required for bounded handheld rendering")
    require('name="referrer" content="same-origin"' in base, "same-origin referrer boundary is missing")
    require('href="#main-content"' in base and 'id="main-content" tabindex="-1"' in base, "skip-link/main focus target is missing")
    require('data-glz-shell="application"' in base, "Application shell classification is missing")
    require('data-glz-surface="system-overlay"' in base, "System Overlay classification is missing")

    require("Glaze UI 2.2.0 Stable" in contract, "consumer contract target version is missing")
    require(GLAZE_RELEASE_REVISION in contract, "consumer contract must record the canonical Stable release revision")
    require("Migration in progress" in contract, "consumer contract must retain the downstream migration boundary")
    require("does **not** establish production acceptance" in contract, "production-acceptance non-claim is missing")
    require("2.1.0" in contract, "2.2 rollback baseline must remain documented")

    # The compatibility layer remains local and last so product CSS cannot silently override the contract.
    css_links = re.findall(r"static 'css/([^']+)'", base)
    require(css_links, "base template contains no local CSS links")
    require(css_links[-1] == "glaze.css", "glaze.css must load after product-specific styles")
    require(all(not item.startswith(("http://", "https://", "//")) for item in css_links), "remote CSS dependency detected")
    require('<meta name="color-scheme" content="light dark">' in base, "light/dark color-scheme metadata is missing")

    # Exact 2.2 source identity and product-local semantic mapping.
    required_token_markers = (
        '--glaze-version: "2.2.0"',
        f'--glaze-release-revision: "{GLAZE_RELEASE_REVISION}"',
        "--glaze-canvas: #0d1119",
        "--glaze-canvas: #eef3f9",
        "--glaze-text: #f3f6fb",
        "--glaze-text: #172033",
        "--glaze-accent: #7aa2ff",
        "--glaze-accent: #366cf6",
        "--glaze-focus-ring: #a9c2ff",
        "--glaze-focus-ring: #244fc6",
        "--glaze-target-min: 48px",
        "--glaze-target-assisted: 56px",
        "--glaze-system-panel-budget: 1",
        "--glaze-floating-control-budget: 3",
    )
    for marker in required_token_markers:
        require(marker in glaze, f"missing 2.2 semantic token marker: {marker}")

    # 2.2 System Shell/material hierarchy and accessibility precedence.
    for marker in (
        "System Overlay navigation chrome",
        "Solid/Raised remain the normal content and durable reading surfaces",
        "Critical and destructive decisions are certainty-first Solid surfaces",
        "2.2 forbids nested backdrop blur",
        '[data-glz-appearance="deep-dark"]',
        '[data-glz-input="touch"]',
        '[data-glz-touch-assistance="true"]',
        '[data-glz-text-scale="200"]',
        '[data-glz-transparency="reduced"]',
        '[data-glz-performance="reduced"]',
        'html[data-mode="increased-contrast"]',
        'html[data-mode="large-text"]',
        "@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)))",
        "@media (prefers-reduced-transparency: reduce)",
        "@media (prefers-reduced-motion: reduce)",
        "@media (prefers-contrast: more)",
        "@media (forced-colors: active)",
        "::selection",
    ):
        require(marker in glaze, f"missing 2.2 material/adaptive/resilience contract: {marker}")

    # Target geometry, focus, and critical-state requirements.
    require("min-height: var(--glaze-target-min);" in glaze, "48px target enforcement is missing")
    require(
        ".complete-button {\n  width: var(--glaze-target-min);\n  height: var(--glaze-target-min);" in glaze,
        "task completion control must use the normal 48px floor",
    )
    require(
        '[data-glz-touch-assistance="true"] .complete-button' in glaze
        and "width: var(--glaze-target-assisted);" in glaze,
        "task completion control must grow to the 56px assisted floor",
    )
    require("button:focus-visible" in glaze and "summary:focus-visible" in glaze, "focus-visible treatment is incomplete")
    require("button:focus," in glaze and "summary:focus," in glaze, "deterministic focus fallback is incomplete")
    require("outline: var(--glaze-focus-width) solid var(--glaze-focus-ring) !important;" in glaze, "semantic focus ring is missing")
    require(".danger-button," in glaze and "backdrop-filter: none;" in glaze, "critical surfaces must remain effects-free")

    # Reduced effects must preserve capability, not merely make ordinary effects slightly faster.
    require("transition-duration: 0.01ms !important" in glaze, "reduced-motion transition suppression is missing")
    require("animation-duration: 0.01ms !important" in glaze, "reduced-motion animation suppression is missing")
    require("background: var(--glaze-surface-strong);" in glaze, "solid-surface fallback is missing")
    require("forced-color-adjust: none" in glaze, "forced-colors selected-state protection is missing")

    # The rendered gate must exercise real Django surfaces and the new 2.2 modes.
    for marker in (
        '"dashboard"',
        '"task-detail"',
        '"notifications"',
        '"data"',
        '"login"',
        "(390, 844)",
        "(1280, 900)",
        'for theme in ("light", "dark")',
        'mode="reduced-motion"',
        'mode="forced-colors"',
        'mode="touch-assistance"',
        'mode="text-200"',
        'mode="reduced-transparency"',
        'mode="increased-contrast"',
        "doc.documentElement.scrollWidth<=frame.clientWidth+1",
        "55.5:47.5",
        "root.dataset.glzTouchAssistance='true'",
        "root.dataset.glzTextScale='200'",
        "root.dataset.glzTransparency='reduced'",
        "root.dataset.mode='increased-contrast'",
    ):
        require(marker in rendered, f"rendered acceptance missing required 2.2 coverage marker: {marker}")

    # CI must validate the exact candidate SHA, not GitHub's synthetic PR merge ref.
    require("Validate Glaze UI consumer source contract" in workflow, "CI is missing source-level Glaze validation")
    require("Validate rendered Glaze UI adoption" in workflow, "CI is missing rendered Glaze validation")
    exact_ref = "ref: ${{ github.event.pull_request.head.sha || github.sha }}"
    require(workflow.count(exact_ref) >= 7, "all Tasks CI jobs must check out the exact candidate revision")
    require(workflow.count("persist-credentials: false") >= 9, "Tasks and pinned cross-app checkouts must avoid persisted credentials")

    # No Candidate production alias, remote presentation dependency, or tracking dependency is allowed.
    lowered = glaze.lower()
    for forbidden in (
        "https://",
        "http://",
        "@import",
        ".candidate.css",
        ".candidate.mjs",
        "analytics",
        "tracker",
        "googletagmanager",
        "fonts.googleapis",
    ):
        require(forbidden not in lowered, f"forbidden presentation/dependency marker in glaze.css: {forbidden}")

    print(
        "GoreeCloud Tasks Glaze UI source contract validated: "
        f"target {TARGET_VERSION}, migration in progress, Stable release {GLAZE_RELEASE_REVISION}; "
        "rendered, application-acceptance, release, and production gates remain separate"
    )


if __name__ == "__main__":
    main()
