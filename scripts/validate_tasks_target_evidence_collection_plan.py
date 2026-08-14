#!/usr/bin/env python3
"""Validate the GoreeCloud Tasks target-environment evidence collection plan."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PLAN = Path(__file__).with_name("tasks_target_evidence_collection_plan.json")
ALLOWED_COLLECTION_CLASSES = {
    "read-only-inspection",
    "controlled-connectivity-validation",
    "controlled-monitoring-validation",
    "controlled-backup-validation",
    "controlled-recovery-validation",
    "controlled-integration-validation",
    "multi-user-acceptance",
    "documentation-review",
}
SENSITIVE_VALUE_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+\S+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(r"(?i)[?&](?:token|api[_-]?key|secret|password|passphrase)=[^&\s]+"),
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),
]


class PlanError(ValueError):
    pass


def fail(message: str) -> None:
    raise PlanError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise PlanError(f"cannot read JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        fail(f"{path}: top-level value must be an object")
    return value


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


def require_string_list(value: Any, label: str) -> None:
    if not isinstance(value, list) or not value:
        fail(f"{label} must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        fail(f"{label} must contain only non-empty strings")


def validate_plan(
    plan: dict[str, Any],
    repo_root: Path = REPO_ROOT,
    check_manifest: bool = True,
) -> dict[str, int]:
    expected_top = {
        "schema_version",
        "service",
        "manifest_path",
        "purpose",
        "authorization_boundary",
        "global_prohibited_actions_without_separate_approval",
        "evidence_items",
    }
    if set(plan) != expected_top:
        fail(f"top-level fields drifted: {sorted(plan)}")
    if plan["schema_version"] != 1:
        fail("schema_version must equal 1")
    if plan["service"] != "GoreeCloud Tasks":
        fail("service must equal 'GoreeCloud Tasks'")
    if plan["manifest_path"] != "scripts/tasks_production_readiness_manifest.json":
        fail("manifest_path must point to scripts/tasks_production_readiness_manifest.json")
    if not isinstance(plan["purpose"], str) or not plan["purpose"].strip():
        fail("purpose must be a non-empty string")

    boundary = plan["authorization_boundary"]
    expected_boundary = {
        "target_collection_requires_separate_authorization": True,
        "plan_grants_production_authority": False,
        "default_mode": "plan-only",
    }
    if boundary != expected_boundary:
        fail("authorization_boundary must preserve separate target authorization and plan-only behavior")

    require_string_list(
        plan["global_prohibited_actions_without_separate_approval"],
        "global_prohibited_actions_without_separate_approval",
    )
    scan_sensitive(plan)

    items = plan["evidence_items"]
    if not isinstance(items, list) or not items:
        fail("evidence_items must be a non-empty list")

    expected_item_fields = {
        "id",
        "phase",
        "collection_class",
        "evidence_sources",
        "success_criteria",
    }
    ids: list[str] = []
    phases: list[int] = []
    class_counts: dict[str, int] = {}
    for index, item in enumerate(items):
        label = f"evidence_items[{index}]"
        if not isinstance(item, dict):
            fail(f"{label} must be an object")
        if set(item) != expected_item_fields:
            fail(f"{label} fields drifted: {sorted(item)}")

        evidence_id = item["id"]
        if not isinstance(evidence_id, str) or not evidence_id:
            fail(f"{label}.id must be a non-empty string")
        ids.append(evidence_id)

        phase = item["phase"]
        if not isinstance(phase, int) or isinstance(phase, bool) or phase < 1 or phase > 5:
            fail(f"{label}.phase must be an integer from 1 through 5")
        phases.append(phase)

        collection_class = item["collection_class"]
        if collection_class not in ALLOWED_COLLECTION_CLASSES:
            fail(f"{label}.collection_class must be one of {sorted(ALLOWED_COLLECTION_CLASSES)}")
        class_counts[collection_class] = class_counts.get(collection_class, 0) + 1

        require_string_list(item["evidence_sources"], f"{label}.evidence_sources")
        require_string_list(item["success_criteria"], f"{label}.success_criteria")

    if len(ids) != len(set(ids)):
        fail("evidence_items contains duplicate ids")
    if phases != sorted(phases):
        fail("evidence_items must be ordered by nondecreasing collection phase")

    if check_manifest:
        manifest_path = repo_root / plan["manifest_path"]
        manifest = load_json(manifest_path)
        manifest_items = manifest.get("target_environment_evidence")
        if not isinstance(manifest_items, list):
            fail("manifest target_environment_evidence must be a list")
        manifest_ids = []
        for index, item in enumerate(manifest_items):
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                fail(f"manifest target_environment_evidence[{index}] has no valid id")
            manifest_ids.append(item["id"])
        if set(ids) != set(manifest_ids):
            missing = sorted(set(manifest_ids) - set(ids))
            extra = sorted(set(ids) - set(manifest_ids))
            fail(f"target evidence plan drift; missing={missing!r}, extra={extra!r}")
        if len(ids) != len(manifest_ids):
            fail("target evidence plan count does not match manifest count")
        production_state = manifest.get("production_state", {})
        if production_state.get("status") != "not-approved":
            fail("collection plan is intended only while the manifest production state is not-approved")

    return {
        "evidence_items": len(ids),
        "phases": len(set(phases)),
        "collection_classes": len(class_counts),
    }


def expect_invalid(name: str, plan: dict[str, Any], expected: str) -> None:
    try:
        validate_plan(plan, check_manifest=False)
    except PlanError as exc:
        if expected not in str(exc):
            raise AssertionError(f"{name}: wrong failure: {exc}") from exc
        print(f"PASS invalid fixture {name}: {exc}")
        return
    raise AssertionError(f"{name}: invalid fixture was accepted")


def self_test(plan: dict[str, Any]) -> None:
    summary = validate_plan(plan, check_manifest=False)
    if summary["evidence_items"] != 20:
        raise AssertionError("baseline collection plan must contain exactly 20 target-evidence items")
    print("PASS current target evidence collection plan semantics")

    duplicate = copy.deepcopy(plan)
    duplicate["evidence_items"].append(copy.deepcopy(duplicate["evidence_items"][0]))
    expect_invalid("duplicate-target-id", duplicate, "duplicate ids")

    unsafe_boundary = copy.deepcopy(plan)
    unsafe_boundary["authorization_boundary"]["target_collection_requires_separate_authorization"] = False
    expect_invalid("unsafe-authorization-boundary", unsafe_boundary, "authorization_boundary")

    grants_authority = copy.deepcopy(plan)
    grants_authority["authorization_boundary"]["plan_grants_production_authority"] = True
    expect_invalid("plan-grants-authority", grants_authority, "authorization_boundary")

    invalid_class = copy.deepcopy(plan)
    invalid_class["evidence_items"][0]["collection_class"] = "automatic-production-change"
    expect_invalid("unsupported-collection-class", invalid_class, "collection_class")

    empty_sources = copy.deepcopy(plan)
    empty_sources["evidence_items"][0]["evidence_sources"] = []
    expect_invalid("empty-evidence-sources", empty_sources, "must be a non-empty list")

    bad_phase_order = copy.deepcopy(plan)
    bad_phase_order["evidence_items"][0]["phase"] = 5
    expect_invalid("phase-order-drift", bad_phase_order, "ordered by nondecreasing")

    secret = copy.deepcopy(plan)
    secret["evidence_items"][0]["success_criteria"][0] = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456"
    expect_invalid("sensitive-value", secret, "possible reusable sensitive value")

    wrong_manifest = copy.deepcopy(plan)
    wrong_manifest["manifest_path"] = "scripts/other.json"
    expect_invalid("manifest-path-drift", wrong_manifest, "manifest_path")

    print("Target evidence collection plan semantic self-test passed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    try:
        plan = load_json(args.plan)
        summary = validate_plan(plan)
        print(
            "Target evidence collection plan valid: "
            f"{summary['evidence_items']} target categories; "
            f"{summary['phases']} phases; "
            f"{summary['collection_classes']} collection classes; "
            "separate target authorization required."
        )
        if args.self_test:
            self_test(plan)
    except (PlanError, AssertionError) as exc:
        print(f"target evidence collection plan validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
