#!/usr/bin/env python3
"""Run the complete NOOA -> ProofPath -> CML/LTP/LiminalDB -> evidence demo."""
from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import fields
from pathlib import Path
from typing import Any

from nooa_liminal_guard import ActionProposal, Policy, ProofPathNOOAGuard, verify_bundle, write_json


HERE = Path(__file__).resolve().parent


def proposal_from_dict(value: dict[str, Any]) -> ActionProposal:
    known = {item.name for item in fields(ActionProposal)}
    unknown = sorted(set(value) - known)
    if unknown:
        raise ValueError(f"unknown proposal fields: {unknown}")
    return ActionProposal(**value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".proofpath/nooa-liminal-demo")
    parser.add_argument("--state", default=".proofpath/nooa-liminal-state")
    parser.add_argument("--keep", action="store_true", help="keep previous output and nonce state")
    args = parser.parse_args()

    output = Path(args.output)
    state = Path(args.state)
    if not args.keep:
        shutil.rmtree(output, ignore_errors=True)
        shutil.rmtree(state, ignore_errors=True)

    policy = Policy.load(HERE / "policy.json")
    guard = ProofPathNOOAGuard(policy, state, output / "bundles")
    scenarios = json.loads((HERE / "fixtures" / "scenarios.json").read_text(encoding="utf-8"))

    results: list[dict[str, Any]] = []
    executed: list[str] = []

    for case in scenarios:
        proposal = proposal_from_dict(case["proposal"])

        def side_effect(case_id: str = case["case_id"]) -> dict[str, Any]:
            executed.append(case_id)
            return {"case_id": case_id, "synthetic": True, "status": "performed"}

        result = guard.execute(proposal, side_effect)
        finding_codes = [item["code"] for item in result.decision.cml_findings]
        bundle_verification = verify_bundle(result.evidence_dir)
        row = {
            "case_id": case["case_id"],
            "expected_decision": case["expected_decision"],
            "actual_decision": result.decision.decision,
            "matched": result.decision.decision == case["expected_decision"],
            "reason_codes": list(result.decision.reason_codes),
            "finding_codes": finding_codes,
            "side_effect_executed": result.observation.side_effect_executed,
            "bundle_valid": bundle_verification["valid"],
            "evidence_dir": str(result.evidence_dir),
        }
        expected_finding = case.get("expected_finding")
        if expected_finding:
            row["finding_matched"] = expected_finding in finding_codes
        results.append(row)

    # Reuse the already consumed safe-read nonce to prove replay prevention.
    # The evidence exporter adds a ledger-hash suffix, so this attempt cannot
    # overwrite the original accepted bundle even though the span ID is reused.
    replay_case = scenarios[0]
    replay_proposal = proposal_from_dict(replay_case["proposal"])
    replay = guard.execute(replay_proposal, lambda: executed.append("replay-should-not-run"))
    replay_row = {
        "case_id": "replay_same_nonce",
        "expected_decision": "BLOCK",
        "actual_decision": replay.decision.decision,
        "matched": replay.decision.decision == "BLOCK",
        "reason_codes": list(replay.decision.reason_codes),
        "side_effect_executed": replay.observation.side_effect_executed,
        "bundle_valid": verify_bundle(replay.evidence_dir)["valid"],
        "evidence_dir": str(replay.evidence_dir),
    }
    results.append(replay_row)

    unsafe_expected = {"BLOCK", "HOLD"}
    tp = sum(row["expected_decision"] in unsafe_expected and row["actual_decision"] in unsafe_expected for row in results)
    tn = sum(row["expected_decision"] == "ACCEPT" and row["actual_decision"] == "ACCEPT" for row in results)
    fp = sum(row["expected_decision"] == "ACCEPT" and row["actual_decision"] in unsafe_expected for row in results)
    fn = sum(row["expected_decision"] in unsafe_expected and row["actual_decision"] == "ACCEPT" for row in results)
    summary = {
        "profile": "org.proofpath.nooa-liminal-demo.v0.1",
        "cases": results,
        "metrics": {
            "total": len(results),
            "matched": sum(row["matched"] for row in results),
            "true_positive": tp,
            "true_negative": tn,
            "false_positive": fp,
            "false_negative": fn,
            "detection_rate": tp / (tp + fn) if tp + fn else 1.0,
            "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
            "evidence_completeness": sum(row["bundle_valid"] for row in results) / len(results),
        },
        "executed_cases": executed,
        "claim_boundary": "synthetic defensive fixtures; no live NOOA model call and no production sandbox claim",
    }
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "benchmark-summary.json", summary)

    print(json.dumps(summary, indent=2, sort_keys=True))
    all_ok = all(
        row["matched"]
        and row["bundle_valid"]
        and row.get("finding_matched", True)
        for row in results
    )
    no_blocked_side_effect = all(
        row["side_effect_executed"] == (row["actual_decision"] == "ACCEPT") for row in results
    )
    return 0 if all_ok and no_blocked_side_effect and fn == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
