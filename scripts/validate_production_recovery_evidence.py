#!/usr/bin/env python3
"""Validate non-secret GoreeCloud Tasks production recovery evidence records."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_SCHEMA = Path(__file__).with_name("production_recovery_evidence.schema.json")


class EvidenceError(ValueError):
    """Raised when a recovery evidence record is invalid or unsafe."""


def fail(path: str, message: str) -> None:
    raise EvidenceError(f"{path}: {message}")


def parse_datetime(value: str, path: str) -> datetime:
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        fail(path, f"invalid RFC 3339 date-time: {value!r}")
        raise AssertionError from exc
    if parsed.tzinfo is None:
        fail(path, "date-time must include a UTC offset or Z suffix")
    return parsed


def json_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    raise EvidenceError(f"schema uses unsupported type {expected!r}")


def resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise EvidenceError(f"schema uses unsupported non-local reference {ref!r}")
    node: Any = root
    for raw_part in ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            raise EvidenceError(f"schema reference cannot be resolved: {ref!r}")
        node = node[part]
    if not isinstance(node, dict):
        raise EvidenceError(f"schema reference does not resolve to an object: {ref!r}")
    return node


def validate_schema(value: Any, schema: dict[str, Any], root: dict[str, Any], path: str = "$") -> None:
    if "$ref" in schema:
        validate_schema(value, resolve_ref(root, schema["$ref"]), root, path)
        return

    if "const" in schema:
        expected = schema["const"]
        if type(value) is not type(expected) or value != expected:  # noqa: E721 - deliberate exact type check
            fail(path, f"must equal {expected!r}")

    if "enum" in schema:
        if not any(type(value) is type(option) and value == option for option in schema["enum"]):
            fail(path, f"must be one of {schema['enum']!r}")

    expected_type = schema.get("type")
    if expected_type is not None and not json_type_matches(value, expected_type):
        fail(path, f"must be of JSON type {expected_type}")

    if isinstance(value, dict):
        required = schema.get("required", [])
        missing = [name for name in required if name not in value]
        if missing:
            fail(path, f"missing required fields: {', '.join(sorted(missing))}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                fail(path, f"unknown fields are not allowed: {', '.join(unknown)}")
        for key, child in value.items():
            child_schema = properties.get(key)
            if child_schema is not None:
                validate_schema(child, child_schema, root, f"{path}.{key}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            fail(path, f"must contain at least {schema['minItems']} item(s)")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in value]
            if len(encoded) != len(set(encoded)):
                fail(path, "must not contain duplicate items")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, child in enumerate(value):
                validate_schema(child, item_schema, root, f"{path}[{index}]")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            fail(path, f"must contain at least {schema['minLength']} character(s)")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            fail(path, f"does not match required pattern {schema['pattern']!r}")
        if schema.get("format") == "date-time":
            parse_datetime(value, path)


FORBIDDEN_KEY = re.compile(
    r"(?:^|_)(?:password|passphrase|token|api_key|access_token|refresh_token|client_secret|"
    r"private_key|secret_value|credential_value|recovery_code|mfa_seed|authorization_header|"
    r"cookie_value|session_token|connection_string)(?:$|_)",
    re.IGNORECASE,
)

SECRET_VALUE_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+\S+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{16,}"),
    re.compile(
        r"(?i)\b(?:password|passphrase|api[_ -]?key|api[_ -]?token|access[_ -]?token|"
        r"refresh[_ -]?token|client[_ -]?secret|private[_ -]?key|recovery[_ -]?code|"
        r"session[_ -]?token)\s*[:=]\s*[^<\s][^\s]{5,}"
    ),
    re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@"),
    re.compile(r"(?i)[?&](?:token|api[_-]?key|secret|password|passphrase)=[^&\s]+"),
]


def scan_for_secrets(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
            if FORBIDDEN_KEY.search(normalized):
                fail(f"{path}.{key}", "secret-bearing field names are prohibited in recovery evidence")
            scan_for_secrets(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            scan_for_secrets(child, f"{path}[{index}]")
        return
    if isinstance(value, str):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(value):
                fail(path, "possible reusable secret value detected; record only a non-secret reference")


def semantic_validation(record: dict[str, Any]) -> str:
    started = parse_datetime(record["test"]["started_at"], "$.test.started_at")
    completed = parse_datetime(record["test"]["completed_at"], "$.test.completed_at")
    authoritative_at = parse_datetime(
        record["authoritative_state"]["decided_at"], "$.authoritative_state.decided_at"
    )
    reviewed_at = parse_datetime(record["decision"]["reviewed_at"], "$.decision.reviewed_at")

    if completed < started:
        fail("$.test", "completed_at must not precede started_at")
    if authoritative_at < completed:
        fail("$.authoritative_state.decided_at", "authoritative-state decision must follow recovery completion")
    if reviewed_at < authoritative_at:
        fail("$.decision.reviewed_at", "review must not precede the authoritative-state decision")

    point = record["recovery_point"]
    checks = record["validation"]
    result = record["result"]
    decision = record["decision"]
    authoritative = record["authoritative_state"]
    go = decision["go_no_go"] == "go"

    if result["status"] in {"failed", "partial"} and go:
        fail("$.decision.go_no_go", "failed or partial recovery evidence must be no-go")

    if decision["production_recovery_approved"] != go:
        fail(
            "$.decision.production_recovery_approved",
            "production_recovery_approved must be true only for a go decision",
        )

    if not go:
        if authoritative["decision"] == "production-promoted":
            fail(
                "$.authoritative_state.decision",
                "a no-go record must not identify the recovered dataset as production-promoted",
            )
        return "NO-GO"

    if result["status"] != "passed":
        fail("$.result.status", "go requires a passed recovery result")
    if result["unresolved_material_problems"]:
        fail("$.result.unresolved_material_problems", "go requires no unresolved material problems")
    if result["problems_encountered"] and not result["corrective_actions"]:
        fail("$.result.corrective_actions", "go requires corrective actions for every recorded problem set")

    false_checks = sorted(key for key, value in checks.items() if value is not True)
    if false_checks:
        fail("$.validation", f"go requires every material validation check to be true: {', '.join(false_checks)}")

    if point["trust_assessment"] != "trusted":
        fail("$.recovery_point.trust_assessment", "go requires a trusted recovery point")
    for field in (
        "integrity_verified",
        "multiple_recovery_points_available",
        "independent_copy_verified",
        "credentials_recoverable_independently",
    ):
        if point[field] is not True:
            fail(f"$.recovery_point.{field}", "go requires this recovery control to be true")

    dimensions = set(point["independence_dimensions"])
    if "virtual_machine" not in dimensions:
        fail(
            "$.recovery_point.independence_dimensions",
            "go requires recovery-copy independence from the protected virtual machine",
        )
    if record["protected_system"]["recovery_classification"] == "critical" and "server" not in dimensions:
        fail(
            "$.recovery_point.independence_dimensions",
            "critical production recovery requires recovery-copy independence from the source server",
        )

    if authoritative["decision"] != "production-promoted":
        fail(
            "$.authoritative_state.decision",
            "go requires an explicit production-promoted authoritative-state decision",
        )

    return "GO"


def validate_record(record: dict[str, Any], schema: dict[str, Any]) -> str:
    scan_for_secrets(record)
    validate_schema(record, schema, schema)
    return semantic_validation(record)


def base_record() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "record_type": "goreecloud-tasks-production-recovery-evidence",
        "protected_system": {
            "name": "GoreeCloud Tasks",
            "environment": "Infrastructure Services VM",
            "recovery_classification": "critical",
            "source_revision": "0123456789abcdef0123456789abcdef01234567",
        },
        "test": {
            "test_id": "tasks-recovery-synthetic-001",
            "started_at": "2026-08-13T17:00:00-05:00",
            "completed_at": "2026-08-13T17:30:00-05:00",
            "administrator": "GoreeCloud administrator",
            "reviewer": "GoreeCloud recovery reviewer",
        },
        "recovery_point": {
            "backup_technology": "combined",
            "recovery_point_id": "synthetic-recovery-point-001",
            "repository_record_reference": "GoreeCloud backup repository record — synthetic fixture",
            "selection_reason": "Synthetic trusted recovery point selected for contract validation.",
            "trust_assessment": "trusted",
            "integrity_verified": True,
            "multiple_recovery_points_available": True,
            "independent_copy_verified": True,
            "independence_dimensions": ["virtual_machine", "server"],
            "credential_record_reference": "Vaultwarden item reference — synthetic fixture only",
            "credentials_recoverable_independently": True,
            "active_credential_value_recorded": False,
        },
        "recovery": {
            "method": "Synthetic production-pattern recovery evidence fixture",
            "restore_destination": "Synthetic isolated Infrastructure Services VM recovery target",
            "components_restored": ["PostgreSQL database", "Tasks application", "private publication"],
        },
        "validation": {
            "restored_information_validated": True,
            "database_operational": True,
            "application_operational": True,
            "ownership_and_permissions_validated": True,
            "network_access_validated": True,
            "dns_validated": True,
            "https_validated": True,
            "authentication_validated": True,
            "authorization_and_privacy_validated": True,
            "monitoring_restored": True,
            "notification_receipt_validated": True,
            "backup_protection_resumed": True,
            "repository_integrity_validated": True,
            "repository_capacity_safe": True,
            "recovery_credentials_accessible": True,
            "recovery_documentation_available_independently": True,
            "temporary_recovery_resources_handled": True,
        },
        "authoritative_state": {
            "decision": "production-promoted",
            "decided_by": "GoreeCloud recovery authority",
            "decided_at": "2026-08-13T17:35:00-05:00",
            "rationale": "Synthetic fixture satisfies every required production recovery control.",
        },
        "result": {
            "status": "passed",
            "problems_encountered": [],
            "corrective_actions": [],
            "follow_up_requirements": [],
            "unresolved_material_problems": False,
        },
        "decision": {
            "go_no_go": "go",
            "production_recovery_approved": True,
            "decided_by": "GoreeCloud recovery reviewer",
            "reviewed_at": "2026-08-13T17:40:00-05:00",
            "rationale": "Synthetic complete record is expected to evaluate GO.",
        },
    }


def expect_invalid(name: str, record: dict[str, Any], schema: dict[str, Any], expected: str) -> None:
    try:
        validate_record(record, schema)
    except EvidenceError as exc:
        if expected not in str(exc):
            raise AssertionError(f"{name}: wrong failure: {exc}") from exc
        print(f"PASS invalid fixture {name}: {exc}")
        return
    raise AssertionError(f"{name}: invalid fixture was accepted")


def self_test(schema: dict[str, Any]) -> None:
    valid_go = base_record()
    if validate_record(valid_go, schema) != "GO":
        raise AssertionError("complete synthetic go fixture did not evaluate GO")
    print("PASS complete synthetic GO evidence")

    valid_no_go = copy.deepcopy(valid_go)
    valid_no_go["validation"]["dns_validated"] = False
    valid_no_go["result"].update(
        {
            "status": "failed",
            "problems_encountered": ["Synthetic DNS validation failed."],
            "corrective_actions": [],
            "follow_up_requirements": ["Correct DNS and repeat the recovery test."],
            "unresolved_material_problems": True,
        }
    )
    valid_no_go["authoritative_state"].update(
        {
            "decision": "not-promoted",
            "rationale": "Synthetic failed recovery must not become authoritative.",
        }
    )
    valid_no_go["decision"].update(
        {
            "go_no_go": "no-go",
            "production_recovery_approved": False,
            "rationale": "Synthetic DNS failure requires a no-go decision.",
        }
    )
    if validate_record(valid_no_go, schema) != "NO-GO":
        raise AssertionError("complete synthetic failed fixture did not evaluate NO-GO")
    print("PASS complete synthetic NO-GO evidence")

    missing = copy.deepcopy(valid_go)
    del missing["recovery"]["restore_destination"]
    expect_invalid("missing-required-field", missing, schema, "missing required fields")

    secret = copy.deepcopy(valid_go)
    secret["decision"]["rationale"] = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz123456"
    expect_invalid("secret-value", secret, schema, "possible reusable secret value")

    false_go = copy.deepcopy(valid_go)
    false_go["validation"]["backup_protection_resumed"] = False
    expect_invalid("go-with-failed-control", false_go, schema, "go requires every material validation check")

    uncertain = copy.deepcopy(valid_go)
    uncertain["recovery_point"]["trust_assessment"] = "uncertain"
    expect_invalid("go-with-uncertain-recovery-point", uncertain, schema, "go requires a trusted recovery point")

    unresolved = copy.deepcopy(valid_go)
    unresolved["result"]["unresolved_material_problems"] = True
    expect_invalid("go-with-unresolved-problem", unresolved, schema, "go requires no unresolved material problems")

    not_independent = copy.deepcopy(valid_go)
    not_independent["recovery_point"]["independence_dimensions"] = ["virtual_machine"]
    expect_invalid("critical-go-without-server-independence", not_independent, schema, "source server")

    no_go_approved = copy.deepcopy(valid_no_go)
    no_go_approved["decision"]["production_recovery_approved"] = True
    expect_invalid("no-go-marked-approved", no_go_approved, schema, "must be true only for a go decision")

    promoted_no_go = copy.deepcopy(valid_no_go)
    promoted_no_go["authoritative_state"]["decision"] = "production-promoted"
    expect_invalid("no-go-production-promoted", promoted_no_go, schema, "must not identify")

    bad_time = copy.deepcopy(valid_go)
    bad_time["test"]["completed_at"] = "2026-08-13T16:30:00-05:00"
    expect_invalid("completion-before-start", bad_time, schema, "must not precede")

    unknown_secret_field = copy.deepcopy(valid_go)
    unknown_secret_field["recovery_point"]["api_token"] = "synthetic-value"
    expect_invalid("secret-bearing-field-name", unknown_secret_field, schema, "secret-bearing field names")

    print("Production recovery evidence contract self-test passed.")


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"cannot read JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"{path}: top-level JSON value must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", nargs="?", type=Path, help="recovery evidence JSON record to validate")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="schema file to use")
    parser.add_argument("--self-test", action="store_true", help="run synthetic contract acceptance tests")
    args = parser.parse_args()

    try:
        schema = load_json(args.schema)
        if args.self_test:
            self_test(schema)
        if args.record is not None:
            record = load_json(args.record)
            outcome = validate_record(record, schema)
            print(f"Valid GoreeCloud Tasks recovery evidence record: {outcome}")
        if not args.self_test and args.record is None:
            parser.error("provide a recovery evidence record or --self-test")
    except (EvidenceError, AssertionError) as exc:
        print(f"production recovery evidence validation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
