#!/usr/bin/env python3
"""Collect ProofPath action-boundary metrics from an audit JSONL file.

This script is intentionally small and fixture-oriented. It parses ProofPath audit
records and emits a reviewer-facing JSON metrics report.

It does not claim production benchmark coverage.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


DEFAULT_EXPECTED_BLOCK_INTENT = "intent_inspect_account_001"
DEFAULT_EXPECTED_ACCEPT_INTENT = "intent_delete_account_approved_001"


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_no}: {exc}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"Line {line_no} must be a JSON object")
            records.append(value)
    return records


def count_by(records: Iterable[Dict[str, Any]], key: str) -> Counter:
    return Counter(str(record.get(key)) for record in records)


def collect_metrics(
    records: List[Dict[str, Any]],
    *,
    source: str,
    run_id: str,
    observed_at: str,
    expected_block_intent: str,
    expected_accept_intent: str,
) -> Dict[str, Any]:
    decisions = count_by(records, "decision")
    forwarded_true = sum(1 for record in records if record.get("forwarded") is True)
    forwarded_false = sum(1 for record in records if record.get("forwarded") is False)

    block_records = [record for record in records if record.get("decision") == "BLOCK"]
    accept_records = [record for record in records if record.get("decision") == "ACCEPT"]

    expected_block_records = [
        record for record in records if record.get("intent_id") == expected_block_intent
    ]
    expected_accept_records = [
        record for record in records if record.get("intent_id") == expected_accept_intent
    ]

    unsafe_without_approval_blocked = sum(
        1
        for record in expected_block_records
        if record.get("decision") == "BLOCK" and record.get("forwarded") is False
    )
    unsafe_without_approval_false_accepts = sum(
        1
        for record in expected_block_records
        if record.get("decision") == "ACCEPT" or record.get("forwarded") is True
    )
    safe_with_approval_false_blocks = sum(
        1
        for record in expected_accept_records
        if record.get("decision") == "BLOCK" or record.get("forwarded") is False
    )

    accepted_forwarded_count = sum(
        1 for record in accept_records if record.get("forwarded") is True
    )
    blocked_forwarded_count = sum(
        1 for record in block_records if record.get("forwarded") is True
    )

    hash_chain_present = bool(records) and records[0].get("previous_hash") == "GENESIS"
    if len(records) > 1:
        for previous, current in zip(records, records[1:]):
            hash_chain_present = hash_chain_present and (
                current.get("previous_hash") == previous.get("hash")
            )

    return {
        "schema_name": "proofpath_action_boundary_metrics_v0_1",
        "schema_version": "0.1",
        "status": "measured_fixture_baseline",
        "run_id": run_id,
        "observed_at": observed_at,
        "source": source,
        "claim_boundary": "Fixture baseline only. This is not a production benchmark.",
        "metrics": {
            "actions_total": {
                "status": "measured",
                "value": len(records),
                "unit": "count",
                "source": source,
            },
            "actions_accepted": {
                "status": "measured",
                "value": decisions.get("ACCEPT", 0),
                "unit": "count",
                "source": source,
            },
            "actions_blocked": {
                "status": "measured",
                "value": decisions.get("BLOCK", 0),
                "unit": "count",
                "source": source,
            },
            "actions_audited": {
                "status": "measured",
                "value": len(records),
                "unit": "count",
                "source": source,
            },
            "unsafe_without_approval_blocked": {
                "status": "measured",
                "value": unsafe_without_approval_blocked,
                "unit": "count",
                "source": source,
            },
            "unsafe_without_approval_false_accepts": {
                "status": "measured",
                "value": unsafe_without_approval_false_accepts,
                "unit": "count",
                "source": source,
            },
            "safe_with_approval_false_blocks": {
                "status": "measured",
                "value": safe_with_approval_false_blocks,
                "unit": "count",
                "source": source,
            },
            "audit_records_written": {
                "status": "measured",
                "value": len(records),
                "unit": "count",
                "source": source,
            },
            "blocked_forwarded_count": {
                "status": "measured",
                "value": blocked_forwarded_count,
                "unit": "count",
                "source": source,
            },
            "accepted_forwarded_count": {
                "status": "measured",
                "value": accepted_forwarded_count,
                "unit": "count",
                "source": source,
            },
            "audit_hash_chain_present": {
                "status": "measured",
                "value": hash_chain_present,
                "unit": "boolean",
                "source": source,
            },
            "decision_latency_ms_p50": {
                "status": "planned",
                "value": None,
                "unit": "milliseconds",
                "source": None,
            },
            "decision_latency_ms_p95": {
                "status": "planned",
                "value": None,
                "unit": "milliseconds",
                "source": None,
            },
        },
        "non_claims": [
            "This fixture does not measure production traffic.",
            "This fixture does not measure latency.",
            "This fixture does not prove all unsafe actions are blocked.",
            "This fixture does not claim production security or compliance.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to audit JSONL fixture")
    parser.add_argument("--output", required=True, help="Path to write metrics JSON")
    parser.add_argument("--run-id", default="action-boundary-fixture-v0.1")
    parser.add_argument("--observed-at", default=None)
    parser.add_argument("--expected-block-intent", default=DEFAULT_EXPECTED_BLOCK_INTENT)
    parser.add_argument("--expected-accept-intent", default=DEFAULT_EXPECTED_ACCEPT_INTENT)
    args = parser.parse_args()

    observed_at = args.observed_at or datetime.now(timezone.utc).isoformat()
    input_path = Path(args.input)
    output_path = Path(args.output)
    records = load_jsonl(input_path)
    metrics = collect_metrics(
        records,
        source=str(input_path),
        run_id=args.run_id,
        observed_at=observed_at,
        expected_block_intent=args.expected_block_intent,
        expected_accept_intent=args.expected_accept_intent,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
