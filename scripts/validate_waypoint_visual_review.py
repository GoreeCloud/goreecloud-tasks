#!/usr/bin/env python3
"""Fail-closed validation for unapproved GoreeCloud Waypoint visual-review rounds."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
ROUND = ROOT / "docs" / "identity" / "waypoint" / "round-01"
MANIFEST = ROUND / "manifest.json"


def fail(message: str) -> None:
    print(f"Waypoint visual review validation failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if not MANIFEST.is_file():
        fail("manifest.json is missing")

    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("schema") != "goreecloud.tasks.waypoint.visual-review":
        fail("unexpected manifest schema")
    if data.get("version") != 1:
        fail("unexpected manifest version")
    if data.get("status") != "unapproved-review-only":
        fail("review round must remain unapproved-review-only")
    if data.get("canonical_identity") is not None:
        fail("canonical_identity must remain null until explicit approval")
    if data.get("public_integration") is not False or data.get("runtime_integration") is not False:
        fail("review candidates must not be marked for public or runtime integration")

    candidates = data.get("candidates")
    if not isinstance(candidates, list) or len(candidates) < 3:
        fail("at least three materially different candidates are required")

    ids: set[str] = set()
    for candidate in candidates:
        cid = candidate.get("id")
        filename = candidate.get("source")
        expected = candidate.get("sha256")
        if not isinstance(cid, str) or not cid or cid in ids:
            fail("candidate IDs must be unique non-empty strings")
        ids.add(cid)
        if not isinstance(filename, str) or not filename.endswith(".svg"):
            fail(f"{cid}: source must be an SVG")
        path = ROUND / filename
        if not path.is_file():
            fail(f"{cid}: source file is missing")
        raw = path.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected:
            fail(f"{cid}: SHA-256 drift: expected {expected}, got {actual}")
        text = raw.decode("utf-8")
        lowered = text.lower()
        if "<script" in lowered or "javascript:" in lowered or "<foreignobject" in lowered:
            fail(f"{cid}: unsafe active SVG content")
        if re.search(r"(?:href|xlink:href)\s*=\s*[\"'](?:https?:|//|data:)", text, re.I):
            fail(f"{cid}: external or embedded resource reference is not allowed")
        if "<title" not in lowered or "<desc" not in lowered:
            fail(f"{cid}: accessible title and description are required")

    approval = data.get("approval", {})
    if approval.get("required") is not True:
        fail("explicit approval must be required")
    if approval.get("approved_candidate") is not None or approval.get("approved_source_sha256") is not None:
        fail("approval fields must remain null in review-only state")

    print(f"Validated {len(candidates)} unapproved Waypoint visual candidates with exact source hashes.")


if __name__ == "__main__":
    main()
