#!/usr/bin/env python3
"""Tests for secret-free Gonka pilot routing summaries."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "gonka_pilot_summary.py"

SPEC = importlib.util.spec_from_file_location("gonka_pilot_summary", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def payload(ids: list[str | None], *, verdict: str = "CONSENSUS") -> dict:
    executions = []
    for index, request_id in enumerate(ids, start=1):
        executions.append(
            {
                "execution_id": f"run-r{index}",
                "status": "SUCCESS",
                "provider_request_id": request_id,
                "reasoning_markup": "closed",
                "endpoint_origin": "https://inference.dahl.global",
            }
        )
    return {
        "receipt": {
            "claim_id": "pilot",
            "verdict": verdict,
            "requested_replicas": len(ids),
            "successful_replicas": len(ids),
            "agreement_score": 1.0,
            "executions": executions,
            "receipt_hash": "sha256:test",
        }
    }


class GonkaPilotSummaryTests(unittest.TestCase):
    def test_duplicate_ids_do_not_prove_independent_routing(self) -> None:
        summary = MODULE.summarize_receipt(
            payload(["devshard-1", "devshard-1", "devshard-1"]),
            Path("/tmp/receipt.json"),
        )
        self.assertEqual(
            MODULE.ROUTING_DUPLICATE_IDS,
            summary["routing_evidence"],
        )
        self.assertEqual(1, summary["unique_provider_request_id_count"])
        self.assertFalse(summary["independent_routing_proven"])
        self.assertEqual(5, MODULE.validation_exit_code(summary))

    def test_distinct_ids_are_only_inconclusive_evidence(self) -> None:
        summary = MODULE.summarize_receipt(
            payload(["req-1", "req-2", "req-3"]),
            Path("/tmp/receipt.json"),
        )
        self.assertEqual(
            MODULE.ROUTING_DISTINCT_IDS,
            summary["routing_evidence"],
        )
        self.assertEqual(3, summary["unique_provider_request_id_count"])
        self.assertFalse(summary["independent_routing_proven"])
        self.assertEqual(0, MODULE.validation_exit_code(summary))

    def test_missing_id_is_detected(self) -> None:
        summary = MODULE.summarize_receipt(
            payload(["req-1", None, "req-3"]),
            Path("/tmp/receipt.json"),
        )
        self.assertEqual(
            MODULE.ROUTING_MISSING_IDS,
            summary["routing_evidence"],
        )
        self.assertEqual(6, MODULE.validation_exit_code(summary))

    def test_non_consensus_still_fails_before_routing_status(self) -> None:
        summary = MODULE.summarize_receipt(
            payload(["req-1", "req-2", "req-3"], verdict="DIVERGENT"),
            Path("/tmp/receipt.json"),
        )
        self.assertEqual(4, MODULE.validation_exit_code(summary))


if __name__ == "__main__":
    unittest.main(verbosity=2)
