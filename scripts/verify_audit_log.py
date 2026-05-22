#!/usr/bin/env python3
"""Verify a ProofPath gateway audit JSONL hash chain.

The current gateway writes JSONL records with:
- previous_hash: GENESIS for the first record, then the previous record hash;
- hash: sha256 over the record payload excluding the hash field.

This checker detects broken links and modified records for the current local demo
format. It does not replace signed logs, append-only storage, key management, or
external timestamping.
"""

from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterable, List

HASH_FIELD = "hash"
PREVIOUS_HASH_FIELD = "previous_hash"
GENESIS = "GENESIS"


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"line {line_no}: invalid JSON: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"line {line_no}: expected JSON object")
            records.append(payload)
    return records


def canonical_json(payload: Dict[str, Any]) -> str:
    # The Rust gateway currently hashes serde_json::Value::to_string() for a
    # constructed object. For the current flat demo records, compact sorted JSON
    # gives reviewers a stable independent check and avoids depending on field
    # order in the JSONL file itself.
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_record_hash(record: Dict[str, Any]) -> str:
    payload = dict(record)
    payload.pop(HASH_FIELD, None)
    return "sha256:" + sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def verify_chain(records: Iterable[Dict[str, Any]]) -> List[str]:
    failures: List[str] = []
    previous_hash = GENESIS

    for index, record in enumerate(records, start=1):
        expected_previous = previous_hash
        actual_previous = record.get(PREVIOUS_HASH_FIELD)
        if actual_previous != expected_previous:
            failures.append(
                f"record {index}: previous_hash expected {expected_previous!r}, got {actual_previous!r}"
            )

        actual_hash = record.get(HASH_FIELD)
        if not isinstance(actual_hash, str) or not actual_hash.startswith("sha256:"):
            failures.append(f"record {index}: missing or invalid hash field")
        else:
            computed_hash = compute_record_hash(record)
            if computed_hash != actual_hash:
                failures.append(
                    f"record {index}: hash mismatch expected {computed_hash}, got {actual_hash}"
                )
            previous_hash = actual_hash

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "audit_log",
        nargs="?",
        default="proofpath-audit.jsonl",
        help="Path to ProofPath gateway audit JSONL file",
    )
    args = parser.parse_args()

    path = Path(args.audit_log)
    if not path.exists():
        print(f"ERROR audit log not found: {path}", file=sys.stderr)
        return 1

    try:
        records = load_jsonl(path)
    except Exception as exc:  # noqa: BLE001 - CLI should report parse errors.
        print(f"ERROR {path}: {exc}", file=sys.stderr)
        return 1

    if not records:
        print(f"ERROR audit log is empty: {path}", file=sys.stderr)
        return 1

    failures = verify_chain(records)
    if failures:
        print("ProofPath audit log verification failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"ProofPath audit log verification passed: {len(records)} records")
    print(f"first_previous_hash={records[0].get(PREVIOUS_HASH_FIELD)}")
    print(f"last_hash={records[-1].get(HASH_FIELD)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
