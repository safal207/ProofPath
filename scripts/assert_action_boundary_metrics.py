#!/usr/bin/env python3
"""Assert ProofPath action-boundary metrics against expected values.

This script is used by the reusable GitHub Action product surface.
It validates a metrics JSON file produced by collect_action_boundary_metrics.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


def parse_optional_bool(value: Optional[str]) -> Optional[bool]:
    if value is None or value == "":
        return None
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"Expected boolean-like value, got: {value!r}")


def parse_optional_int(value: Optional[str]) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def metric_value(payload: Dict[str, Any], name: str) -> Any:
    try:
        return payload["metrics"][name]["value"]
    except KeyError as exc:
        raise KeyError(f"Missing metric: {name}") from exc


def assert_expected(payload: Dict[str, Any], name: str, expected: Any) -> None:
    if expected is None:
        return
    actual = metric_value(payload, name)
    if actual != expected:
        raise AssertionError(f"{name}: expected {expected!r}, got {actual!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", required=True, help="Path to metrics JSON")
    parser.add_argument("--expected-actions-total")
    parser.add_argument("--expected-actions-blocked")
    parser.add_argument("--expected-actions-accepted")
    parser.add_argument("--expected-unsafe-without-approval-blocked")
    parser.add_argument("--expected-unsafe-without-approval-false-accepts")
    parser.add_argument("--expected-safe-with-approval-false-blocks")
    parser.add_argument("--expected-audit-records-written")
    parser.add_argument("--expected-blocked-forwarded-count")
    parser.add_argument("--expected-accepted-forwarded-count")
    parser.add_argument("--expected-audit-hash-chain-present")
    args = parser.parse_args()

    payload = json.loads(Path(args.metrics).read_text(encoding="utf-8"))

    checks = {
        "actions_total": parse_optional_int(args.expected_actions_total),
        "actions_blocked": parse_optional_int(args.expected_actions_blocked),
        "actions_accepted": parse_optional_int(args.expected_actions_accepted),
        "unsafe_without_approval_blocked": parse_optional_int(
            args.expected_unsafe_without_approval_blocked
        ),
        "unsafe_without_approval_false_accepts": parse_optional_int(
            args.expected_unsafe_without_approval_false_accepts
        ),
        "safe_with_approval_false_blocks": parse_optional_int(
            args.expected_safe_with_approval_false_blocks
        ),
        "audit_records_written": parse_optional_int(args.expected_audit_records_written),
        "blocked_forwarded_count": parse_optional_int(args.expected_blocked_forwarded_count),
        "accepted_forwarded_count": parse_optional_int(args.expected_accepted_forwarded_count),
        "audit_hash_chain_present": parse_optional_bool(
            args.expected_audit_hash_chain_present
        ),
    }

    failures = []
    for name, expected in checks.items():
        try:
            assert_expected(payload, name, expected)
        except Exception as exc:  # noqa: BLE001 - CLI should collect all mismatches.
            failures.append(str(exc))

    if failures:
        print("ProofPath action-boundary metrics failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("ProofPath action-boundary metrics passed.")
    for name, expected in checks.items():
        if expected is not None:
            print(f"- {name} == {expected!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
