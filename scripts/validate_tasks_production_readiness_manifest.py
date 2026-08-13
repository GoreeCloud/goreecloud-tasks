#!/usr/bin/env python3
"""Validate GoreeCloud Tasks production-readiness evidence inventory."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST = Path(__file__).with_name("tasks_production_readiness_manifest.json")
REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_PRODUCTION_STATES = {"not-approved", "approved"}
ALLOWED_EVIDENCE_STATES = {"outstanding", "satisfied"}
SENSITIVE_VALUE_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+\S+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"(?i)[?&](?:token|api[_-]?key|secret|password|passphrase)=[^&\s]+"),
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),
]


class ManifestError(ValueError):
    pass


def fail(message: str) -> None:
    raise ManifestError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"cannot read JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        fail(f"{path}: top-level value must be an object")
    return value


def parse_timestamp(value: str, label: str) -> datetime:
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ManifestError(f"{label}: invalid timestamp {value!r}") from exc
    if parsed.tzinfo is None:
        fail(f"{label}: timestamp must include an offset or Z")
    return parsed


def scan_sensitive(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            scan_sensitive(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_sensitive(child, f"{path}[{index}]")
    elif isinstance(value, str):
        for pattern in SENSITIVE_VALUE_PATTERNS:
            if pattern.search(value):
                fail(f"{path}: possible reusable sensitive value detected")


def parse_workflow(path: Path) -> tuple[str, set[str]]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"cannot read workflow {path}: {exc}") from exc

    workflow_name = None
    for line in text.splitlines():
        match = re.match(r"^name:\s*(.+?)\s*$", line)
        if match:
            workflow_name = match.group(1).strip('"\'')
            break
    if not workflow_name:
        fail(f"{path}: top-level workflow name is missing")

    lines = text.splitlines()
    try:
        jobs_index = next(index for index, line in enumerate(lines) if line.rstrip() == "jobs:")
    except StopIteration:
        fail(f"{path}: top-level jobs mapping is missing")

    jobs: set[str] = set()
    for line in lines[jobs_index + 1 :]:
        if line and not line.startswith((" ", "\t", "#")):
            break
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*(?:#.*)?$", line)
        if match:
            jobs.add(match.group(1))
    if not jobs:
        fail(f"{path}: no workflow jobs were discovered")
    return workflow_name, jobs


def validate_source_gates(manifest: dict[str, Any], repo_root: Path, check_repository: bool) -> int:
    gates = manifest.get("source_evidence_gates")
    if not isinstance(gates, list) or not gates:
        fail("source_evidence_gates must be a non-empty list")

    paths: list[str] = []
    total_jobs = 0
    for index, gate in enumerate(gates):
        label = f"source_evidence_gates[{index}]"
        if not isinstance(gate, dict):
            fail(f"{label} must be an object")
        expected_keys = {"workflow_path", "workflow_name", "required_jobs", "evidence_scope"}
        if set(gate) != expected_keys:
            fail(f"{label} fields drifted: {sorted(gate)}")
        path = gate["workflow_path"]
        name = gate["workflow_name"]
        jobs = gate["required_jobs"]
        scope = gate["evidence_scope"]
        if not all(isinstance(value, str) and value for value in (path, name, scope)):
            fail(f"{label}: workflow path, name, and scope must be non-empty strings")
        if not isinstance(jobs, list) or not jobs or not all(isinstance(job, str) and job for job in jobs):
            fail(f"{label}.required_jobs must be a non-empty string list")
        if len(jobs) != len(set(jobs)):
            fail(f"{label}.required_jobs contains duplicates")
        paths.append(path)
        total_jobs += len(jobs)

        if check_repository:
            workflow_path = repo_root / path
            if not workflow_path.is_file():
                fail(f"manifested workflow is missing: {path}")
            actual_name, actual_jobs = parse_workflow(workflow_path)
            if actual_name != name:
                fail(f"{path}: manifest name {name!r} does not match workflow name {actual_name!r}")
            if actual_jobs != set(jobs):
                fail(
                    f"{path}: job inventory drift; manifest={sorted(jobs)!r}, "
                    f"workflow={sorted(actual_jobs)!r}"
                )

    if len(paths) != len(set(paths)):
        fail("source_evidence_gates contains duplicate workflow paths")

    if check_repository:
        actual_paths = {
            str(path.relative_to(repo_root))
            for path in (repo_root / ".github" / "workflows").glob("*.yml")
        }
        manifested_paths = set(paths)
        if actual_paths != manifested_paths:
            missing = sorted(actual_paths - manifested_paths)
            stale = sorted(manifested_paths - actual_paths)
            fail(f"workflow inventory drift; unmanifested={missing!r}, missing_on_disk={stale!r}")

    declared = manifest.get("declared_effective_check_count")
    if not isinstance(declared, int) or isinstance(declared, bool):
        fail("declared_effective_check_count must be an integer")
    if declared != total_jobs:
        fail(f"declared_effective_check_count={declared} but manifested jobs total {total_jobs}")
    return total_jobs


def validate_target_evidence(manifest: dict[str, Any]) -> tuple[int, int]:
    evidence = manifest.get("target_environment_evidence")
    if not isinstance(evidence, list) or not evidence:
        fail("target_environment_evidence must be a non-empty list")

    ids: list[str] = []
    satisfied = 0
    outstanding = 0
    for index, item in enumerate(evidence):
        label = f"target_environment_evidence[{index}]"
        if not isinstance(item, dict):
            fail(f"{label} must be an object")
        expected = {"id", "status", "evidence_reference", "verified_at", "verified_by"}
        if set(item) != expected:
            fail(f"{label} fields drifted: {sorted(item)}")
        evidence_id = item["id"]
        status = item["status"]
        if not isinstance(evidence_id, str) or not evidence_id:
            fail(f"{label}.id must be a non-empty string")
        if status not in ALLOWED_EVIDENCE_STATES:
            fail(f"{label}.status must be one of {sorted(ALLOWED_EVIDENCE_STATES)}")
        ids.append(evidence_id)

        if status == "outstanding":
            outstanding += 1
            if any(item[field] is not None for field in ("evidence_reference", "verified_at", "verified_by")):
                fail(f"{label}: outstanding evidence must not claim verification metadata")
        else:
            satisfied += 1
            for field in ("evidence_reference", "verified_at", "verified_by"):
                if not isinstance(item[field], str) or not item[field]:
                    fail(f"{label}.{field} is required when evidence is satisfied")
            parse_timestamp(item["verified_at"], f"{label}.verified_at")

    if len(ids) != len(set(ids)):
        fail("target_environment_evidence contains duplicate ids")
    return satisfied, outstanding


def validate_production_state(manifest: dict[str, Any], outstanding: int) -> None:
    state = manifest.get("production_state")
    if not isinstance(state, dict):
        fail("production_state must be an object")
    if set(state) != {"status", "approval_reference", "approved_at"}:
        fail("production_state fields drifted")
    status = state["status"]
    if status not in ALLOWED_PRODUCTION_STATES:
        fail(f"production_state.status must be one of {sorted(ALLOWED_PRODUCTION_STATES)}")

    if status == "not-approved":
        if state["approval_reference"] is not None or state["approved_at"] is not None:
            fail("not-approved production state must not contain approval metadata")
        if outstanding == 0:
            fail("not-approved state with zero outstanding target evidence requires explicit review")
        return

    if outstanding:
        fail("production cannot be approved while target-environment evidence remains outstanding")
    if not isinstance(state["approval_reference"], str) or not state["approval_reference"]:
        fail("approved production state requires a non-empty approval_reference")
    if not isinstance(state["approved_at"], str) or not state["approved_at"]:
        fail("approved production state requires approved_at")
    parse_timestamp(state["approved_at"], "production_state.approved_at")


def validate_manifest(manifest: dict[str, Any], repo_root: Path = REPO_ROOT, check_repository: bool = True) -> dict[str, int]:
    expected_top = {
        "schema_version",
        "service",
        "production_state",
        "declared_effective_check_count",
        "source_evidence_gates",
        "target_environment_evidence",
    }
    if set(manifest) != expected_top:
        fail(f"top-level fields drifted: {sorted(manifest)}")
    if manifest["schema_version"] != 1:
        fail("schema_version must equal 1")
    if manifest["service"] != "GoreeCloud Tasks":
        fail("service must equal 'GoreeCloud Tasks'")

    scan_sensitive(manifest)
    checks = validate_source_gates(manifest, repo_root, check_repository)
    satisfied, outstanding = validate_target_evidence(manifest)
    validate_production_state(manifest, outstanding)
    return {"effective_checks": checks, "target_satisfied": satisfied, "target_outstanding": outstanding}


def expect_invalid(name: str, manifest: dict[str, Any], expected: str) -> None:
    try:
        validate_manifest(manifest, check_repository=False)
    except ManifestError as exc:
        if expected not in str(exc):
            raise AssertionError(f"{name}: wrong failure: {exc}") from exc
        print(f"PASS invalid fixture {name}: {exc}")
        return
    raise AssertionError(f"{name}: invalid fixture was accepted")


def self_test(manifest: dict[str, Any]) -> None:
    summary = validate_manifest(manifest, check_repository=False)
    if summary["target_outstanding"] == 0:
        raise AssertionError("baseline manifest unexpectedly has no outstanding target evidence")
    print("PASS current not-approved manifest semantics")

    drift = copy.deepcopy(manifest)
    drift["declared_effective_check_count"] += 1
    expect_invalid("effective-check-count-drift", drift, "manifested jobs total")

    duplicate = copy.deepcopy(manifest)
    duplicate["target_environment_evidence"].append(copy.deepcopy(duplicate["target_environment_evidence"][0]))
    expect_invalid("duplicate-target-id", duplicate, "duplicate ids")

    incomplete = copy.deepcopy(manifest)
    incomplete["target_environment_evidence"][0]["status"] = "satisfied"
    expect_invalid("satisfied-without-evidence", incomplete, "is required when evidence is satisfied")

    approved_early = copy.deepcopy(manifest)
    approved_early["production_state"] = {
        "status": "approved",
        "approval_reference": "synthetic approval reference",
        "approved_at": "2026-08-13T18:00:00-05:00",
    }
    expect_invalid("approved-with-outstanding-evidence", approved_early, "remains outstanding")

    stale_approval = copy.deepcopy(manifest)
    stale_approval["production_state"]["approval_reference"] = "synthetic stale reference"
    expect_invalid("not-approved-with-approval-metadata", stale_approval, "must not contain approval metadata")

    secret = copy.deepcopy(manifest)
    secret["source_evidence_gates"][0]["evidence_scope"] = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456"
    expect_invalid("sensitive-value", secret, "possible reusable sensitive value")

    print("Production readiness manifest semantic self-test passed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    try:
        manifest = load_json(args.manifest)
        summary = validate_manifest(manifest)
        print(
            "Production readiness manifest valid: "
            f"{summary['effective_checks']} effective source/disposable checks; "
            f"{summary['target_satisfied']} target evidence satisfied; "
            f"{summary['target_outstanding']} target evidence outstanding; "
            f"production={manifest['production_state']['status']}."
        )
        if args.self_test:
            self_test(manifest)
    except (ManifestError, AssertionError) as exc:
        print(f"production readiness manifest validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
