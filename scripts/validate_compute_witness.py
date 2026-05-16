#!/usr/bin/env python3
"""Validate ProofPath Compute Witness conformance fixtures.

This validator intentionally stays small and dependency-free. It checks the
reviewer-facing fixture contract introduced by the Compute Witness Environment:

- conformance manifest is valid JSON;
- referenced job manifests and receipts exist;
- required manifest fields are present and non-empty;
- receipt decision/reason matches the expected conformance entry;
- identity and commitment fields are stable between manifest and receipt.

It does not claim to prove GPU execution, zkML correctness, hardware identity,
or distributed settlement. It only validates the v0.1 fixture contract.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFORMANCE_MANIFEST = REPO_ROOT / "conformance" / "compute-witness" / "manifest.json"

IDENTITY_FIELDS = (
    "job_id",
    "agent_id",
    "intent_id",
    "causal_parent",
    "scope",
)

COMMITMENT_FIELDS = (
    "model_hash",
    "runtime_hash",
    "input_hash",
)

VALID_DECISIONS = {"ACCEPT", "HOLD", "REJECT", "BLOCK", "AUDIT"}


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise AssertionError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AssertionError(f"invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise AssertionError(f"expected JSON object in {path}")
    return data


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def resolve_fixture_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def assert_required_fields(entry_name: str, fixture: dict[str, Any], required_fields: list[str]) -> None:
    for field in required_fields:
        if field not in fixture:
            raise AssertionError(f"{entry_name}: missing required manifest field `{field}`")
        if is_blank(fixture[field]):
            raise AssertionError(f"{entry_name}: required manifest field `{field}` is blank")


def assert_receipt_expectations(
    entry_name: str,
    receipt: dict[str, Any],
    expected_decision: str,
    expected_reason: Any,
) -> None:
    decision = receipt.get("decision")
    reason = receipt.get("reason")

    if decision not in VALID_DECISIONS:
        raise AssertionError(f"{entry_name}: invalid receipt decision `{decision}`")

    if decision != expected_decision:
        raise AssertionError(
            f"{entry_name}: decision mismatch: expected {expected_decision}, got {decision}"
        )

    if reason != expected_reason:
        raise AssertionError(
            f"{entry_name}: reason mismatch: expected {expected_reason!r}, got {reason!r}"
        )

    if decision == "ACCEPT" and reason is not None:
        raise AssertionError(f"{entry_name}: ACCEPT receipt must have null reason")

    if decision in {"REJECT", "BLOCK"} and is_blank(reason):
        raise AssertionError(f"{entry_name}: {decision} receipt must explain a reason")


def assert_manifest_receipt_stability(
    entry_name: str,
    manifest: dict[str, Any],
    receipt: dict[str, Any],
) -> None:
    for field in (*IDENTITY_FIELDS, *COMMITMENT_FIELDS):
        if manifest.get(field) != receipt.get(field):
            raise AssertionError(
                f"{entry_name}: `{field}` mismatch between manifest and receipt: "
                f"manifest={manifest.get(field)!r}, receipt={receipt.get(field)!r}"
            )

    if is_blank(receipt.get("receipt_id")):
        raise AssertionError(f"{entry_name}: receipt_id is required")

    if is_blank(receipt.get("audit_hash")):
        raise AssertionError(f"{entry_name}: audit_hash is required")

    if is_blank(receipt.get("verified_at")):
        raise AssertionError(f"{entry_name}: verified_at is required")

    if receipt.get("decision") == "ACCEPT" and is_blank(receipt.get("output_hash")):
        raise AssertionError(f"{entry_name}: ACCEPT receipt requires output_hash")


def validate_conformance_manifest(path: Path) -> list[str]:
    conformance = load_json(path)
    fixtures = conformance.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise AssertionError("conformance manifest must contain a non-empty `fixtures` list")

    results: list[str] = []

    for index, entry in enumerate(fixtures, start=1):
        if not isinstance(entry, dict):
            raise AssertionError(f"fixture entry #{index} must be an object")

        name = str(entry.get("name") or f"fixture #{index}")
        manifest_path = resolve_fixture_path(str(entry.get("manifest", "")))
        receipt_path = resolve_fixture_path(str(entry.get("receipt", "")))

        expected_decision = entry.get("expected_decision")
        expected_reason = entry.get("expected_reason")
        required_fields = entry.get("required_fields", [])

        if expected_decision not in VALID_DECISIONS:
            raise AssertionError(f"{name}: invalid expected_decision `{expected_decision}`")

        if not isinstance(required_fields, list) or not all(
            isinstance(item, str) for item in required_fields
        ):
            raise AssertionError(f"{name}: required_fields must be a list of strings")

        manifest = load_json(manifest_path)
        receipt = load_json(receipt_path)

        assert_required_fields(name, manifest, required_fields)
        assert_receipt_expectations(name, receipt, expected_decision, expected_reason)
        assert_manifest_receipt_stability(name, manifest, receipt)

        results.append(f"PASS {name}")

    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ProofPath Compute Witness fixtures")
    parser.add_argument(
        "manifest",
        nargs="?",
        default=str(DEFAULT_CONFORMANCE_MANIFEST),
        help="Path to conformance manifest JSON",
    )
    args = parser.parse_args()

    try:
        results = validate_conformance_manifest(Path(args.manifest).resolve())
    except AssertionError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1

    for result in results:
        print(result)
    print(f"PASS compute witness conformance ({len(results)} fixtures)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
