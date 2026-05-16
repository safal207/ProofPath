#!/usr/bin/env python3
"""Validate ProofPath Compute Witness conformance fixtures.

This validator intentionally stays small and dependency-free. It checks the
reviewer-facing fixture contract introduced by the Compute Witness Environment:

- conformance manifest is valid JSON;
- referenced job manifests, receipts, and audit entries exist;
- required manifest fields are present and non-empty;
- receipt decision/reason matches the expected conformance entry;
- identity and commitment fields are stable between manifest and receipt;
- receipt.audit_hash equals the canonical SHA-256 hash of the audit entry;
- optional causal chain fixtures link child inputs to parent outputs;
- optional challenge fixtures prove expected failures are caught.

It does not claim to prove GPU execution, zkML correctness, hardware identity,
or distributed settlement. It only validates the v0.1 fixture contract.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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

AUDIT_RECEIPT_FIELDS = (
    "receipt_id",
    "job_id",
    "agent_id",
    "intent_id",
    "decision",
    "reason",
)

VALID_DECISIONS = {"ACCEPT", "HOLD", "REJECT", "BLOCK", "AUDIT"}
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


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


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_canonical_json(value: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    return f"sha256:{digest}"


def assert_sha256_value(entry_name: str, field_name: str, value: Any) -> None:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise AssertionError(
            f"{entry_name}: `{field_name}` must use lowercase sha256:<64 hex>"
        )


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

    assert_sha256_value(entry_name, "audit_hash", receipt.get("audit_hash"))

    if is_blank(receipt.get("verified_at")):
        raise AssertionError(f"{entry_name}: verified_at is required")

    if receipt.get("decision") == "ACCEPT" and is_blank(receipt.get("output_hash")):
        raise AssertionError(f"{entry_name}: ACCEPT receipt requires output_hash")


def assert_audit_log_matches_receipt(
    entry_name: str,
    receipt: dict[str, Any],
    audit_entry: dict[str, Any],
    seen_audit_hashes: set[str],
) -> str:
    if audit_entry.get("profile") != "proofpath.compute-witness.audit-entry.v0.1":
        raise AssertionError(f"{entry_name}: invalid audit entry profile")

    if is_blank(audit_entry.get("audit_id")):
        raise AssertionError(f"{entry_name}: audit_id is required")

    for field in AUDIT_RECEIPT_FIELDS:
        if audit_entry.get(field) != receipt.get(field):
            raise AssertionError(
                f"{entry_name}: audit `{field}` mismatch with receipt: "
                f"audit={audit_entry.get(field)!r}, receipt={receipt.get(field)!r}"
            )

    previous_audit_hash = audit_entry.get("previous_audit_hash")
    if previous_audit_hash is not None:
        assert_sha256_value(entry_name, "previous_audit_hash", previous_audit_hash)
        if previous_audit_hash not in seen_audit_hashes:
            raise AssertionError(
                f"{entry_name}: previous_audit_hash does not point to an earlier audit entry"
            )

    computed_audit_hash = sha256_canonical_json(audit_entry)
    receipt_audit_hash = receipt.get("audit_hash")

    if receipt_audit_hash != computed_audit_hash:
        raise AssertionError(
            f"{entry_name}: audit_hash mismatch: "
            f"receipt={receipt_audit_hash!r}, computed={computed_audit_hash!r}"
        )

    return computed_audit_hash


def assert_causal_parent_receipt(
    entry_name: str,
    manifest: dict[str, Any],
    receipt: dict[str, Any],
    expected_parent_receipt_id: str,
    accepted_receipts: dict[str, dict[str, Any]],
) -> None:
    parent = accepted_receipts.get(expected_parent_receipt_id)
    if parent is None:
        raise AssertionError(
            f"{entry_name}: causal_parent_receipt `{expected_parent_receipt_id}` was not previously accepted"
        )

    expected_parent_ref = f"receipt:{expected_parent_receipt_id}"
    if manifest.get("causal_parent") != expected_parent_ref:
        raise AssertionError(
            f"{entry_name}: manifest causal_parent must be `{expected_parent_ref}`"
        )

    if receipt.get("causal_parent") != expected_parent_ref:
        raise AssertionError(
            f"{entry_name}: receipt causal_parent must be `{expected_parent_ref}`"
        )

    parent_output_hash = parent.get("output_hash")
    if is_blank(parent_output_hash):
        raise AssertionError(
            f"{entry_name}: parent receipt `{expected_parent_receipt_id}` has no output_hash"
        )

    if manifest.get("input_hash") != parent_output_hash:
        raise AssertionError(
            f"{entry_name}: manifest input_hash must equal parent output_hash"
        )

    if receipt.get("input_hash") != parent_output_hash:
        raise AssertionError(
            f"{entry_name}: receipt input_hash must equal parent output_hash"
        )


def validate_fixture_entry(
    entry: dict[str, Any],
    index: int,
    seen_audit_hashes: set[str],
    accepted_receipts: dict[str, dict[str, Any]],
) -> tuple[str, bool]:
    name = str(entry.get("name") or f"fixture #{index}")
    manifest_path = resolve_fixture_path(str(entry.get("manifest", "")))
    receipt_path = resolve_fixture_path(str(entry.get("receipt", "")))
    audit_path = resolve_fixture_path(str(entry.get("audit", "")))

    expected_decision = entry.get("expected_decision")
    expected_reason = entry.get("expected_reason")
    required_fields = entry.get("required_fields", [])

    if expected_decision not in VALID_DECISIONS:
        raise AssertionError(f"{name}: invalid expected_decision `{expected_decision}`")

    if is_blank(entry.get("audit")):
        raise AssertionError(f"{name}: audit fixture path is required")

    if not isinstance(required_fields, list) or not all(
        isinstance(item, str) for item in required_fields
    ):
        raise AssertionError(f"{name}: required_fields must be a list of strings")

    causal_parent_receipt = entry.get("causal_parent_receipt")
    if causal_parent_receipt is not None and not isinstance(causal_parent_receipt, str):
        raise AssertionError(f"{name}: causal_parent_receipt must be a string when provided")

    manifest = load_json(manifest_path)
    receipt = load_json(receipt_path)
    audit_entry = load_json(audit_path)

    assert_required_fields(name, manifest, required_fields)
    assert_receipt_expectations(name, receipt, expected_decision, expected_reason)
    assert_manifest_receipt_stability(name, manifest, receipt)
    if causal_parent_receipt is not None:
        assert_causal_parent_receipt(
            name,
            manifest,
            receipt,
            causal_parent_receipt,
            accepted_receipts,
        )
    audit_hash = assert_audit_log_matches_receipt(name, receipt, audit_entry, seen_audit_hashes)
    seen_audit_hashes.add(audit_hash)

    if receipt.get("decision") == "ACCEPT":
        accepted_receipts[str(receipt["receipt_id"])] = receipt

    return name, False


def validate_conformance_manifest(path: Path) -> list[str]:
    conformance = load_json(path)
    fixtures = conformance.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise AssertionError("conformance manifest must contain a non-empty `fixtures` list")

    results: list[str] = []
    seen_audit_hashes: set[str] = set()
    accepted_receipts: dict[str, dict[str, Any]] = {}

    for index, entry in enumerate(fixtures, start=1):
        if not isinstance(entry, dict):
            raise AssertionError(f"fixture entry #{index} must be an object")

        name = str(entry.get("name") or f"fixture #{index}")
        expected_failure = entry.get("expected_failure")
        if expected_failure is not None and not isinstance(expected_failure, str):
            raise AssertionError(f"{name}: expected_failure must be a string when provided")

        try:
            validate_fixture_entry(entry, index, seen_audit_hashes, accepted_receipts)
        except AssertionError as exc:
            if expected_failure is None:
                raise
            message = str(exc)
            if expected_failure not in message:
                raise AssertionError(
                    f"{name}: expected failure containing {expected_failure!r}, got {message!r}"
                ) from exc
            results.append(f"PASS {name} expected failure: {expected_failure}")
            continue

        if expected_failure is not None:
            raise AssertionError(f"{name}: expected failure did not occur: {expected_failure}")

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
