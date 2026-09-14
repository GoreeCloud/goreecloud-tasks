#!/usr/bin/env python3
"""Fail-closed source validation for Tasks mixed-surface GLAZE UI adoption under Platform Contract 0.3."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_TARGET_VERSION = "1.0.0"
PLATFORM_REQUIRED_VERSION = "1.4.0"
WEB_GLAZE_SOURCE_REVISION = "70909bbdccad378fb7281ae1842e2f5beed64c38"
ANDROID_GLAZE_SOURCE_REVISION = "84cb3db4884042f0fa25ed6d475a127fb110f596"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"Tasks GLAZE UI mixed-surface source validation failed: {message}")


def read(path: str) -> str:
    candidate = ROOT / path
    require(candidate.is_file(), f"missing required file: {path}")
    return candidate.read_text(encoding="utf-8")


def main() -> None:
    base = read("templates/base.html")
    glaze = read("static/css/glaze.css")
    contract = read("docs/glaze-ui.md")
    platform = read("goreecloud.platform.yaml")
    conformance = read("docs/PLATFORM_CONFORMANCE.md")
    rendered = read("scripts/validate_glaze_ui_rendered.py")
    workflow = read(".github/workflows/ci.yml")
    android_theme = read(
        "clients/android/app/src/main/java/com/goreecloud/tasks/android/GlazeTasksTheme.kt"
    )

    # Exact web V1 implementation identity and fail-closed downstream lifecycle boundary.
    require(f'data-glaze-ui="{WEB_TARGET_VERSION}"' in base, "base template must declare web GLAZE UI V1.0")
    require(
        f'data-glaze-source-revision="{WEB_GLAZE_SOURCE_REVISION}"' in base,
        "base template must pin the exact canonical web V1 source revision",
    )
    require(
        'data-glaze-consumer-status="migration-in-progress"' in base,
        "base template must not claim completed consumer acceptance",
    )
    require('class="glz1-workspace"' in base, "base template must use the V1 workspace semantic class")
    require("viewport-fit=cover" in base, "viewport-fit=cover is required for bounded handheld rendering")
    require('name="referrer" content="same-origin"' in base, "same-origin referrer boundary is missing")
    require(
        'href="#main-content"' in base and 'id="main-content" tabindex="-1"' in base,
        "skip-link/main focus target is missing",
    )
    require('data-glz-shell="application"' in base, "Application shell classification is missing")
    require('data-glz-surface="system-overlay"' in base, "System Overlay classification is missing")

    contract_plain = contract.replace("**", "")
    require("GLAZE UI V1.0 (`1.0.0`)" in contract, "web consumer contract target version is missing")
    require(WEB_GLAZE_SOURCE_REVISION in contract, "web consumer contract must record the exact V1 source revision")
    require("Official reset baseline; production acceptance pending" in contract, "upstream reset lifecycle boundary is missing")
    require("Migration in progress" in contract, "downstream migration boundary is missing")
    require("does not establish production acceptance" in contract_plain, "production-acceptance non-claim is missing")
    require("not a retired Glaze product version" in contract, "rollback must use an exact Tasks revision, not a retired Glaze version")

    # Current controlled records must preserve the historical web V1 identity while
    # separately representing Android V1.4 and current Platform Contract 0.3 authority.
    active_records = {
        "base template": base,
        "consumer contract": contract,
        "platform manifest": platform,
        "platform conformance": conformance,
        "consumer CSS": glaze,
        "rendered validator": rendered,
        "Android theme": android_theme,
    }
    for name, content in active_records.items():
        require("Glaze UI 2.2" not in content and "GLAZE UI 2.2" not in content, f"{name} retains retired 2.2 identity")
        require('data-glaze-ui="1.3.0"' not in content, f"{name} retains retired 1.3 active marker")

    require(
        'schema_version: "0.3"' in platform or "schema_version: '0.3'" in platform,
        "Platform Contract must use schema 0.3",
    )
    require(
        'platform_contract: "0.3"' in platform or "platform_contract: '0.3'" in platform,
        "Platform compatibility must use contract 0.3",
    )
    require(
        re.search(r"^\s*glaze_ui_required:\s*['\"]?1\.4\.0['\"]?\s*$", platform, re.MULTILINE) is not None,
        "Platform Contract must record current Stable GLAZE UI 1.4.0",
    )
    require("glaze-ui==1.4.0" in platform, "Platform compatibility must require current Stable GLAZE UI 1.4.0")
    require(
        re.search(r"^\s*version:\s*['\"]?1\.4\.0['\"]?\s*$", platform, re.MULTILINE) is not None,
        "Platform GLAZE UI system entry must record the current Android target version",
    )
    require("result: applicable-migration-required" in platform, "Platform Contract must keep repository-wide GLAZE UI migration-required")
    require("status: nonconformant" in platform, "Platform Contract must remain nonconformant")
    require(ANDROID_GLAZE_SOURCE_REVISION in platform, "Platform Contract must record the exact Android V1.4 Stable revision")
    require(
        "existing web application still carries older repository-local Glaze mapping/evidence" in platform,
        "Platform Contract must preserve the mixed web/Android GLAZE UI boundary",
    )
    require("\n  sync:\n" not in platform, "GoreeCloud Sync must not be represented as an eighth Integral Platform System")
    require(
        "GoreeCloud Sync change tracking, authorized replication, version/conflict reconciliation" in platform,
        "Platform Contract must preserve the separate blocked GoreeCloud Sync capability",
    )

    require("GLAZE UI V1.4 / 1.4.0" in android_theme, "Android theme must identify the current V1.4 target")
    require(
        "does not claim native Optical Engine acceptance" in android_theme,
        "Android theme must preserve the V1.4 optical-acceptance non-claim",
    )
    require(
        "The existing web application still implements the repository-local GLAZE UI V1.0 (`1.0.0`) migration baseline." in conformance,
        "platform conformance must preserve the implemented web V1 source truth",
    )
    require(
        "The native Android Development client targets current Stable GLAZE UI V1.4 (`1.4.0`)" in conformance,
        "platform conformance must record Android V1.4 source adoption",
    )
    require(
        "The current GoreeCloud Platform Contract 0.3 consumer requirement is GLAZE UI `1.4.0`." in conformance,
        "platform conformance must identify the current Contract 0.3 GLAZE UI baseline",
    )
    require(
        "seven Integral Platform Systems" in conformance,
        "platform conformance must identify the seven-system Contract 0.3 model",
    )
    require(
        "GoreeCloud Sync is a separately governed application/service capability, not an Integral Platform System." in conformance,
        "platform conformance must keep Sync separate from the seven Integral Platform Systems",
    )

    # The compatibility layer remains local and last so product CSS cannot silently override it.
    css_links = re.findall(r"static 'css/([^']+)'", base)
    require(css_links, "base template contains no local CSS links")
    require(css_links[-1] == "glaze.css", "glaze.css must load after product-specific styles")
    require('<meta name="color-scheme" content="light dark">' in base, "light/dark color-scheme metadata is missing")

    # Exact source provenance and canonical glz1 semantic namespace for the current web implementation.
    required_token_markers = (
        '--tasks-glaze-version: "1.0.0"',
        f'--tasks-glaze-source-revision: "{WEB_GLAZE_SOURCE_REVISION}"',
        "--glz1-canvas: #f5f7fa",
        "--glz1-canvas: #0b0d11",
        "--glz1-base: #ffffff",
        "--glz1-base: #12151b",
        "--glz1-text-primary: #151a23",
        "--glz1-text-primary: #f5f7fa",
        "--glz1-focus: #3478f6",
        "--glz1-focus: #8db5ff",
        "--glz1-target-shell: 48px",
        "--glz1-target-assisted: 56px",
        "--glz1-overlay-blur: 22px",
        "--glz1-panel-blur: 28px",
    )
    for marker in required_token_markers:
        require(marker in glaze, f"missing web V1 semantic marker: {marker}")

    for marker in (
        "System Overlay navigation chrome",
        "Solid/Raised remain the normal content and durable reading surfaces",
        "Critical and destructive decisions are certainty-first Solid surfaces",
        "nested backdrop blur is suppressed",
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
        require(marker in glaze, f"missing web V1 material/adaptive/resilience contract: {marker}")

    require("min-block-size: var(--glz1-target-shell);" in glaze, "48px V1 target enforcement is missing")
    require(
        ".complete-button {\n  inline-size: var(--glz1-target-shell);\n  block-size: var(--glz1-target-shell);" in glaze,
        "task completion control must use the normal 48px floor",
    )
    require(
        '[data-glz-touch-assistance="true"] .complete-button' in glaze
        and "inline-size: var(--glz1-target-assisted);" in glaze,
        "task completion control must grow to the 56px assisted floor",
    )
    require("button:focus-visible" in glaze and "summary:focus-visible" in glaze, "focus-visible treatment is incomplete")
    require("button:focus," in glaze and "summary:focus," in glaze, "deterministic focus fallback is incomplete")
    require("outline: var(--glz1-focus-width) solid var(--glz1-focus) !important;" in glaze, "semantic focus ring is missing")
    require("transition-duration: 0.01ms !important" in glaze, "reduced-motion transition suppression is missing")
    require("animation-duration: 0.01ms !important" in glaze, "reduced-motion animation suppression is missing")
    require("forced-color-adjust: none" in glaze, "forced-colors selected-state protection is missing")

    # Rendered acceptance continues to exercise representative real Django web surfaces and V1 modes.
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
        require(marker in rendered, f"rendered acceptance missing required web V1 coverage marker: {marker}")

    # CI validates the exact candidate SHA, not GitHub's synthetic merge ref.
    require("Validate Glaze UI consumer source contract" in workflow, "CI is missing source-level Glaze validation")
    require("Validate rendered Glaze UI adoption" in workflow, "CI is missing rendered Glaze validation")
    exact_ref = "ref: ${{ github.event.pull_request.head.sha || github.sha }}"
    require(workflow.count(exact_ref) >= 7, "all Tasks CI jobs must check out the exact candidate revision")
    require(workflow.count("persist-credentials: false") >= 9, "Tasks and pinned cross-app checkouts must avoid persisted credentials")

    # No remote presentation, retired active namespace, or tracking dependency.
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
        "GoreeCloud Tasks GLAZE UI mixed-surface source contract validated: "
        f"web implementation {WEB_TARGET_VERSION} at {WEB_GLAZE_SOURCE_REVISION}; "
        f"Android target {PLATFORM_REQUIRED_VERSION} at {ANDROID_GLAZE_SOURCE_REVISION}; "
        "Platform Contract 0.3 migration-required under seven-system governance; "
        "GoreeCloud Sync remains separately blocked; rendered, application acceptance, V1.4.1, "
        "release, and production gates remain separate"
    )


if __name__ == "__main__":
    main()
