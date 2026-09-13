#!/usr/bin/env python3
"""Fail-closed source validation for the GoreeCloud Tasks Android Development foundation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "clients" / "android"
MANIFEST = ANDROID / "app" / "src" / "main" / "AndroidManifest.xml"
CONTRACT = ANDROID / "app" / "src" / "main" / "java" / "com" / "goreecloud" / "tasks" / "android" / "NativeClientContract.kt"
README = ANDROID / "README.md"

EXPECTED_GLAZE_VERSION = "1.4.0"
EXPECTED_GLAZE_REVISION = "84cb3db4884042f0fa25ed6d475a127fb110f596"


def require(text: str, fragment: str, label: str) -> None:
    if fragment not in text:
        raise SystemExit(f"{label}: required fragment missing: {fragment!r}")


def forbid(text: str, fragment: str, label: str) -> None:
    if fragment in text:
        raise SystemExit(f"{label}: forbidden fragment present: {fragment!r}")


def main() -> None:
    manifest = MANIFEST.read_text(encoding="utf-8")
    contract = CONTRACT.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")

    forbid(manifest, 'android.permission.INTERNET', "manifest")
    require(manifest, 'android:allowBackup="false"', "manifest")

    require(contract, f'GLAZE_UI_VERSION = "{EXPECTED_GLAZE_VERSION}"', "contract")
    require(contract, f'GLAZE_UI_REFERENCE_REVISION = "{EXPECTED_GLAZE_REVISION}"', "contract")
    require(contract, 'identitySessionExchange = NativeCapabilityState.BLOCKED', "contract")
    require(contract, 'remoteListRead = NativeCapabilityState.BLOCKED', "contract")
    require(contract, 'remoteDetailRead = NativeCapabilityState.BLOCKED', "contract")
    require(contract, 'glazeUiV14 = NativeCapabilityState.ADOPTION_IN_PROGRESS', "contract")

    require(readme, "does **not** declare `INTERNET`", "README")
    require(readme, f"Glaze UI target:** `{EXPECTED_GLAZE_VERSION}` at `{EXPECTED_GLAZE_REVISION}`", "README")
    require(readme, "not** evidence that native V1.4 conformance has been accepted", "README")

    print(
        "Tasks Android Development boundary validated: "
        f"glaze={EXPECTED_GLAZE_VERSION}@{EXPECTED_GLAZE_REVISION} "
        "internet=false identity=false remoteReads=false production=false"
    )


if __name__ == "__main__":
    main()
