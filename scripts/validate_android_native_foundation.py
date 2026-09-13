#!/usr/bin/env python3
"""Fail-closed source validation for the GoreeCloud Tasks Android Development foundation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "clients" / "android"
MANIFEST = ANDROID / "app" / "src" / "main" / "AndroidManifest.xml"
CONTRACT = ANDROID / "app" / "src" / "main" / "java" / "com" / "goreecloud" / "tasks" / "android" / "NativeClientContract.kt"
IDENTITY_BINDING = ANDROID / "app" / "src" / "main" / "java" / "com" / "goreecloud" / "tasks" / "android" / "TasksIdentityBinding.kt"
README = ANDROID / "README.md"

EXPECTED_GLAZE_VERSION = "1.4.0"
EXPECTED_GLAZE_REVISION = "84cb3db4884042f0fa25ed6d475a127fb110f596"
EXPECTED_IDENTITY_SCHEMA = "goreecloud.identity.native-application-session/v1"
EXPECTED_IDENTITY_CANDIDATE_REVISION = "62ad109809f2e479cf71a6327ffd0d4537a6b3df"
EXPECTED_TASKS_AUDIENCE = "goreecloud-tasks-android"


def require(text: str, fragment: str, label: str) -> None:
    if fragment not in text:
        raise SystemExit(f"{label}: required fragment missing: {fragment!r}")


def forbid(text: str, fragment: str, label: str) -> None:
    if fragment in text:
        raise SystemExit(f"{label}: forbidden fragment present: {fragment!r}")


def main() -> None:
    manifest = MANIFEST.read_text(encoding="utf-8")
    contract = CONTRACT.read_text(encoding="utf-8")
    identity_binding = IDENTITY_BINDING.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")

    forbid(manifest, 'android.permission.INTERNET', "manifest")
    require(manifest, 'android:allowBackup="false"', "manifest")

    require(contract, f'GLAZE_UI_VERSION = "{EXPECTED_GLAZE_VERSION}"', "contract")
    require(contract, f'GLAZE_UI_REFERENCE_REVISION = "{EXPECTED_GLAZE_REVISION}"', "contract")
    require(contract, f'IDENTITY_NATIVE_SESSION_SCHEMA = "{EXPECTED_IDENTITY_SCHEMA}"', "contract")
    require(contract, EXPECTED_IDENTITY_CANDIDATE_REVISION, "contract")
    require(
        contract,
        'identityAcceptanceProofContract = NativeCapabilityState.SOURCE_READY',
        "contract",
    )
    require(contract, 'identitySessionExchange = NativeCapabilityState.BLOCKED', "contract")
    require(contract, 'remoteListRead = NativeCapabilityState.BLOCKED', "contract")
    require(contract, 'remoteDetailRead = NativeCapabilityState.BLOCKED', "contract")
    require(contract, 'glazeUiV14 = NativeCapabilityState.ADOPTION_IN_PROGRESS', "contract")

    require(identity_binding, f'ANDROID_TASKS_AUDIENCE = "{EXPECTED_TASKS_AUDIENCE}"', "identity binding")
    require(identity_binding, "val principalId: String", "identity binding")
    require(identity_binding, "val audience: String", "identity binding")
    require(identity_binding, "val issuedAt: Instant", "identity binding")
    require(identity_binding, "val expiresAt: Instant", "identity binding")
    require(identity_binding, "value == value.trim()", "identity binding")
    require(identity_binding, "value.none(Char::isISOControl)", "identity binding")
    require(identity_binding, "now.isBefore(proof.issuedAt)", "identity binding")
    require(identity_binding, "!now.isBefore(proof.expiresAt)", "identity binding")
    require(identity_binding, "PrincipalMismatch", "identity binding")
    require(identity_binding, "AudienceMismatch", "identity binding")

    require(readme, "does **not** declare `INTERNET`", "README")
    require(readme, f"Glaze UI target:** `{EXPECTED_GLAZE_VERSION}` at `{EXPECTED_GLAZE_REVISION}`", "README")
    require(readme, EXPECTED_IDENTITY_SCHEMA, "README")
    require(readme, EXPECTED_IDENTITY_CANDIDATE_REVISION, "README")
    require(readme, "not** evidence that native V1.4 conformance has been accepted", "README")

    print(
        "Tasks Android Development boundary validated: "
        f"glaze={EXPECTED_GLAZE_VERSION}@{EXPECTED_GLAZE_REVISION} "
        f"identityContract={EXPECTED_IDENTITY_SCHEMA}@{EXPECTED_IDENTITY_CANDIDATE_REVISION} "
        "identityProof=source-ready internet=false identitySession=false "
        "remoteReads=false production=false"
    )


if __name__ == "__main__":
    main()
