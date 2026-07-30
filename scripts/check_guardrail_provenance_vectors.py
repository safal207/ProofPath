#!/usr/bin/env python3
"""Independent stdlib-only checker for GuardrailDecision source provenance vectors."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SUPPORTED_REPRESENTATIONS = {
    "response-body-raw",
    "response-body-decompressed",
}


def sha256_uri(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def evaluate(decision: dict[str, Any], root: Path) -> dict[str, Any]:
    errors: list[str] = []
    signals: list[str] = []

    source_hash = decision.get("source_content_hash")
    if not isinstance(source_hash, str) or not HASH_RE.fullmatch(source_hash):
        errors.append("INVALID_SOURCE_HASH")

    source_ref = decision.get("knowledge_source_ref")
    if not isinstance(source_ref, str) or not source_ref:
        errors.append("MISSING_KNOWLEDGE_SOURCE_REF")

    snapshot_ref = decision.get("source_snapshot_ref")
    current_ref = decision.get("current_content_ref")
    profile = decision.get("retrieval_profile")

    if snapshot_ref is not None or current_ref is not None:
        if not isinstance(profile, dict):
            errors.append("MISSING_RETRIEVAL_PROFILE")
        elif profile.get("representation") not in SUPPORTED_REPRESENTATIONS:
            errors.append("UNSUPPORTED_REPRESENTATION")

    snapshot_valid = False
    if snapshot_ref is not None and "INVALID_SOURCE_HASH" not in errors:
        snapshot_path = root / str(snapshot_ref)
        if not snapshot_path.is_file():
            errors.append("SNAPSHOT_NOT_FOUND")
        elif sha256_uri(snapshot_path.read_bytes()) != source_hash:
            errors.append("SNAPSHOT_HASH_MISMATCH")
        else:
            snapshot_valid = True

    current_matches = False
    if current_ref is not None and "INVALID_SOURCE_HASH" not in errors:
        current_path = root / str(current_ref)
        if not current_path.is_file():
            errors.append("CURRENT_CONTENT_NOT_FOUND")
        elif sha256_uri(current_path.read_bytes()) == source_hash:
            current_matches = True
        else:
            signals.append("SOURCE_STALE")

    if decision.get("issued_at") and not decision.get("temporal_anchor_ref"):
        signals.append("TEMPORAL_PRECEDENCE_UNPROVEN")
    if decision.get("temporal_anchor_ref"):
        # The presence of a reference is not proof that an anchor verified.
        # A future profile may dispatch to an OTS or RFC 3161 verifier.
        signals.append("EXTERNAL_ANCHOR_UNVERIFIED")

    if errors:
        proof_level = "INVALID"
    elif snapshot_valid and current_ref is not None and current_matches:
        proof_level = "FRESH"
    elif snapshot_valid:
        proof_level = "REPRODUCIBLE"
    else:
        proof_level = "COMMITTED"

    return {
        "proof_level": proof_level,
        "signals": sorted(set(signals)),
        "errors": sorted(set(errors)),
    }


def main() -> int:
    manifest_path = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else "conformance/guardrail-decision-v1/manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent

    failures = 0
    for case in manifest["cases"]:
        actual = evaluate(case["decision"], root)
        expected = {
            "proof_level": case["expected"]["proof_level"],
            "signals": sorted(case["expected"].get("signals", [])),
            "errors": sorted(case["expected"].get("errors", [])),
        }
        if actual == expected:
            print(f"PASS {case['name']} -> {actual['proof_level']}")
        else:
            failures += 1
            print(f"FAIL {case['name']}")
            print(f"  expected: {expected}")
            print(f"  actual:   {actual}")

    if failures:
        print(f"\nGuardrail provenance conformance failed: {failures}")
        return 1

    print(f"\nGuardrail provenance conformance passed: {len(manifest['cases'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
