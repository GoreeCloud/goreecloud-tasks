#!/usr/bin/env python3
"""Fail-closed source validation for the GoreeCloud Tasks Glaze UI consumer contract."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_VERSION = "1.3.0"
GLAZE_REVISION = "96cc27050c098a5f06f571923f0cb9be54989a92"


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

    # Version and lifecycle boundary.
    require(f'data-glaze-ui="{TARGET_VERSION}"' in base, "base template must declare the Glaze UI target version")
    require('data-glaze-consumer-status="adoption-candidate"' in base, "base template must retain Adoption Candidate status")
    require(f"Glaze UI {TARGET_VERSION} Stable semantic contract" in contract, "consumer contract target version is missing")
    require("Consumer status:** Adoption Candidate" in contract, "consumer contract must not silently claim Stable production acceptance")
    require(GLAZE_REVISION in contract, "consumer contract must record the reviewed canonical Glaze revision")
    require("does **not** claim that Tasks has completed production visual acceptance" in contract, "visual-acceptance boundary is missing")
    require("does **not** import or claim Glaze UI 1.4" in contract, "1.4 Candidate boundary is missing")

    # The compatibility layer must be loaded last so it can enforce the semantic contract.
    css_links = re.findall(r"static 'css/([^']+)'", base)
    require(css_links, "base template contains no local CSS links")
    require(css_links[-1] == "glaze.css", "glaze.css must load after product-specific styles")
    require(all(not item.startswith(("http://", "https://", "//")) for item in css_links), "remote CSS dependency detected")
    require('<meta name="color-scheme" content="light dark">' in base, "light/dark color-scheme metadata is missing")

    # Canonical Stable 1.3 semantic values used by this consumer mapping.
    required_token_markers = (
        '--glaze-version: "1.3.0"',
        "--glaze-canvas: #0d1119",
        "--glaze-text: #f3f6fb",
        "--glaze-accent: #7aa2ff",
        "--glaze-focus-ring: #a9c2ff",
        "--glaze-target-min: 44px",
        "--glaze-radius-control: 16px",
        "--glaze-glass-blur: 24px",
        "--glaze-motion-fast: 160ms",
        "--glaze-canvas: #eef3f9",
        "--glaze-text: #172033",
        "--glaze-accent: #366cf6",
        "--glaze-focus-ring: #244fc6",
    )
    for marker in required_token_markers:
        require(marker in glaze, f"missing canonical semantic token marker: {marker}")

    # Themes, surface hierarchy, privacy, and fallback behavior.
    for marker in (
        "@media (prefers-color-scheme: light)",
        "Functional Glass: navigation and interactive chrome only.",
        ".topbar,\n.sidebar",
        "Solid/Raised remain the normal content surfaces.",
        "@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px)))",
        "@media (prefers-reduced-transparency: reduce)",
        "@media (prefers-reduced-motion: reduce)",
        "@media (prefers-contrast: more)",
        "@media (forced-colors: active)",
        "::selection",
    ):
        require(marker in glaze, f"missing theme/material/resilience contract: {marker}")

    # Actionable target and focus requirements.
    require("min-height: var(--glaze-target-min);" in glaze, "minimum target enforcement is missing")
    require(".complete-button {\n  width: var(--glaze-target-min);\n  height: var(--glaze-target-min);" in glaze, "task completion target must be at least 44px")
    require(".nav-item {\n  min-height: var(--glaze-target-min);" in glaze, "navigation target must be at least 44px")
    require("button:focus-visible" in glaze and "summary:focus-visible" in glaze, "shared focus-visible treatment is incomplete")
    require("outline: var(--glaze-focus-width) solid var(--glaze-focus-ring) !important;" in glaze, "semantic focus ring is missing")

    # Resilience must remove motion rather than merely accelerate ordinary motion.
    require("transition-duration: 0.01ms !important" in glaze, "reduced-motion transition suppression is missing")
    require("animation-duration: 0.01ms !important" in glaze, "reduced-motion animation suppression is missing")
    require("background: var(--glaze-surface-strong);" in glaze, "solid-surface fallback is missing")
    require("forced-color-adjust: none" in glaze, "forced-colors state protection is missing")

    # The rendered gate must exercise real Django surfaces and representative modes.
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
        "doc.documentElement.scrollWidth<=frame.clientWidth+1",
        "rect.height>=43.5",
    ):
        require(marker in rendered, f"rendered acceptance missing required coverage marker: {marker}")

    # CI must validate the exact candidate SHA, not GitHub's synthetic PR merge ref.
    require("Validate Glaze UI consumer source contract" in workflow, "CI is missing source-level Glaze validation")
    require("Validate rendered Glaze UI adoption" in workflow, "CI is missing rendered Glaze validation")
    exact_ref = "ref: ${{ github.event.pull_request.head.sha || github.sha }}"
    require(workflow.count(exact_ref) >= 7, "all Tasks CI jobs must check out the exact candidate revision")
    require(workflow.count("persist-credentials: false") >= 9, "Tasks and pinned cross-app checkouts must avoid persisted credentials")

    # The consumer layer itself must remain local and tracker-free.
    lowered = glaze.lower()
    for forbidden in ("https://", "http://", "@import", "analytics", "tracker", "googletagmanager", "fonts.googleapis"):
        require(forbidden not in lowered, f"forbidden remote/presentation dependency marker in glaze.css: {forbidden}")

    print(
        "GoreeCloud Tasks Glaze UI consumer source contract validated: "
        f"target {TARGET_VERSION}, status Adoption Candidate, reviewed Glaze revision {GLAZE_REVISION}; "
        "rendered acceptance and exact-head CI are fail-closed"
    )


if __name__ == "__main__":
    main()
