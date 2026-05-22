#!/usr/bin/env python3
"""Run ProofPath v0.1 conformance fixtures.

This runner intentionally mirrors the minimal verifier rules in
crates/proofpath-verifier/src/lib.rs so reviewers can execute the JSON fixture
contract without starting external services.

It is a small reviewer/contributor tool, not a replacement for the Rust tests.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

HEADER_INTENT_ID = "x-proofpath-intent-id"
HEADER_CAUSAL_PARENT = "x-proofpath-causal-parent"
HEADER_SCOPE = "x-proofpath-scope"
HEADER_REVERSIBILITY = "x-proofpath-reversibility"
HEADER_HUMAN_APPROVAL = "x-proofpath-human-approval"

VALID_REVERSIBILITY = {"reversible", "compensatable", "irreversible"}


def is_blank(value: Optional[str]) -> bool:
    return value is None or str(value).strip() == ""


def normalize_headers(headers: Dict[str, Any]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for name, value in headers.items():
        normalized[str(name).lower()] = "" if value is None else str(value)
    return normalized


def verify(headers: Dict[str, str]) -> Tuple[str, Optional[str]]:
    if is_blank(headers.get(HEADER_INTENT_ID)):
        return "REJECT", "MISSING_INTENT"

    if is_blank(headers.get(HEADER_CAUSAL_PARENT)):
        return "REJECT", "MISSING_CAUSAL_PARENT"

    if is_blank(headers.get(HEADER_SCOPE)):
        return "REJECT", "MISSING_SCOPE"

    reversibility_raw = headers.get(HEADER_REVERSIBILITY)
    if reversibility_raw is None:
        return "REJECT", "MISSING_REVERSIBILITY"

    reversibility = reversibility_raw.strip().lower()
    if reversibility not in VALID_REVERSIBILITY:
        return "REJECT", "INVALID_REVERSIBILITY"

    if reversibility == "irreversible" and is_blank(headers.get(HEADER_HUMAN_APPROVAL)):
        return "BLOCK", "IRREVERSIBLE_ACTION_REQUIRES_APPROVAL"

    return "ACCEPT", None


def load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected JSON object")
    return payload


def fixture_expectation(manifest_item: Dict[str, Any], fixture: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    expected = fixture.get("expected")
    if not isinstance(expected, dict):
        raise ValueError("fixture is missing expected object")

    fixture_decision = expected.get("decision")
    fixture_reason = expected.get("reason")
    manifest_decision = manifest_item.get("expected_decision")
    manifest_reason = manifest_item.get("expected_reason")

    if manifest_decision != fixture_decision or manifest_reason != fixture_reason:
        raise ValueError(
            "manifest expectation does not match fixture expected object: "
            f"manifest=({manifest_decision!r}, {manifest_reason!r}) "
            f"fixture=({fixture_decision!r}, {fixture_reason!r})"
        )

    return str(fixture_decision), None if fixture_reason is None else str(fixture_reason)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "manifest",
        nargs="?",
        default="conformance/manifest.json",
        help="Path to conformance manifest JSON",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    manifest = load_json(manifest_path)
    fixtures = manifest.get("fixtures")
    if not isinstance(fixtures, list):
        print("ERROR manifest must contain a fixtures array", file=sys.stderr)
        return 1

    root = manifest_path.parent
    failures = []

    for item in fixtures:
        if not isinstance(item, dict):
            failures.append("manifest fixture item is not an object")
            continue

        relative_path = item.get("path")
        if not isinstance(relative_path, str):
            failures.append(f"{item.get('id', '<unknown>')}: missing fixture path")
            continue

        fixture_path = root / relative_path
        try:
            fixture = load_json(fixture_path)
            request = fixture.get("request", {})
            if not isinstance(request, dict):
                raise ValueError("request must be an object")
            headers_raw = request.get("headers", {})
            if not isinstance(headers_raw, dict):
                raise ValueError("request.headers must be an object")

            expected_decision, expected_reason = fixture_expectation(item, fixture)
            actual_decision, actual_reason = verify(normalize_headers(headers_raw))

            if (actual_decision, actual_reason) != (expected_decision, expected_reason):
                failures.append(
                    f"FAIL {relative_path}: expected {expected_decision} {expected_reason}, "
                    f"got {actual_decision} {actual_reason}"
                )
            else:
                reason_suffix = "" if actual_reason is None else f" {actual_reason}"
                print(f"PASS {relative_path} -> {actual_decision}{reason_suffix}")
        except Exception as exc:  # noqa: BLE001 - CLI should report all fixture problems.
            failures.append(f"FAIL {relative_path}: {exc}")

    if failures:
        print("\nProofPath conformance fixture check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"\nProofPath conformance fixtures passed: {len(fixtures)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
