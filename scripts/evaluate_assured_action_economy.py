#!/usr/bin/env python3
"""Evaluate a funded Assured Action verification job without moving money."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BUNDLE_PROFILE = "proofpath.assured-action.economy-bundle.v0.1"
RECEIPT_PROFILE = "proofpath.assured-action.settlement-receipt.v0.1"
PRODUCT = "PROOFPATH_ASSURED_ACTION_ECONOMY"

JOB_DOMAIN = b"proofpath:assured-action-economy:v0.1:job\n"
COMMITMENT_DOMAIN = b"proofpath:assured-action-economy:v0.1:commitment\n"
BUNDLE_DOMAIN = b"proofpath:assured-action-economy:v0.1:bundle\n"
SETTLEMENT_DOMAIN = b"proofpath:assured-action-economy:v0.1:settlement\n"

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
DECISION_RANK = {"ACCEPT": 0, "HOLD": 1, "BLOCK": 2, "CHALLENGE": 3}
EXIT_CODE = {"ACCEPT": 0, "HOLD": 2, "BLOCK": 3, "CHALLENGE": 4}

RISK_REQUIREMENTS = {
    "L0_RECORD": (1, 1, 1),
    "L1_STANDARD": (1, 1, 1),
    "L2_SENSITIVE": (3, 3, 2),
    "L3_HIGH_RISK": (5, 5, 2),
    "L4_CRITICAL": (7, 7, 3),
}

PRIORITY = {
    "ECONOMY_BUNDLE_INVALID": 10,
    "ECONOMY_JOB_INVALID": 20,
    "ECONOMY_RISK_POLICY_UNSATISFIED": 30,
    "ECONOMY_BUDGET_NOT_CONSERVED": 40,
    "ECONOMY_ASSIGNMENT_INVALID": 50,
    "ECONOMY_CONTROL_DOMAIN_DIVERSITY_INSUFFICIENT": 60,
    "ECONOMY_IMPLEMENTATION_DIVERSITY_INSUFFICIENT": 70,
    "ECONOMY_JOB_ROOT_MISMATCH": 100,
    "ECONOMY_UNASSIGNED_COMMITMENT": 110,
    "ECONOMY_UNASSIGNED_REVEAL": 120,
    "ECONOMY_REVEAL_WITHOUT_COMMITMENT": 130,
    "ECONOMY_COMMITMENT_EQUIVOCATION": 140,
    "ECONOMY_REVEAL_EQUIVOCATION": 150,
    "ECONOMY_COMMITMENT_MISMATCH": 160,
    "ECONOMY_CLEARANCE_ROOT_MISMATCH": 170,
    "ECONOMY_ADMISSION_RECEIPT_MISMATCH": 180,
    "ECONOMY_WITNESS_CHALLENGE": 190,
    "ECONOMY_COMMITMENT_MISSING": 200,
    "ECONOMY_REVEAL_MISSING": 210,
    "ECONOMY_QUORUM_INSUFFICIENT": 220,
    "ECONOMY_WITNESS_DISSENT_REQUIRES_REVIEW": 230,
    "ECONOMY_OPEN_DISPUTE": 240,
    "ECONOMY_CHALLENGE_WINDOW_OPEN": 250,
}


class EconomyError(ValueError):
    """Raised when strict economy JSON cannot be parsed or canonicalized."""


def _reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise EconomyError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_float(raw: str) -> Any:
    raise EconomyError(f"floating-point values are forbidden: {raw}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate,
            parse_float=_reject_float,
        )
    except (OSError, json.JSONDecodeError, EconomyError) as exc:
        raise EconomyError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EconomyError(f"{path} must contain one JSON object")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    def normalize(item: Any) -> Any:
        if isinstance(item, float):
            raise EconomyError("floats are forbidden in canonical economy records")
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise EconomyError("canonical object keys must be strings")
            return {key: normalize(item[key]) for key in sorted(item)}
        if isinstance(item, list):
            return [normalize(entry) for entry in item]
        if item is None or isinstance(item, (str, int, bool)):
            return item
        raise EconomyError(f"unsupported canonical type: {type(item).__name__}")

    return json.dumps(
        normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest(domain: bytes, value: Any) -> str:
    return "sha256:" + hashlib.sha256(domain + canonical_json_bytes(value)).hexdigest()


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _uint(value: Any, *, positive: bool = False) -> int | None:
    minimum = 1 if positive else 0
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        return None
    return value


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _finding(code: str, decision: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "decision": decision, "path": path, "message": message}


def _sort_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[tuple[str, str, str], dict[str, str]] = {}
    for finding in findings:
        unique[(finding["code"], finding["path"], finding["message"])] = finding
    return sorted(
        unique.values(),
        key=lambda finding: (
            -DECISION_RANK[finding["decision"]],
            PRIORITY.get(finding["code"], 999),
            finding["code"],
            finding["path"],
        ),
    )


def _without_job_root(job: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(job)
    normalized["job_root"] = None
    return normalized


def compute_job_root(job: dict[str, Any]) -> str:
    return digest(JOB_DOMAIN, _without_job_root(job))


def commitment_payload(job_id: str, reveal: dict[str, Any]) -> dict[str, str | None]:
    return {
        "job_id": job_id,
        "witness_id": _text(reveal.get("witness_id")),
        "verdict": _text(reveal.get("verdict")),
        "action_clearance_root": _text(reveal.get("action_clearance_root")),
        "evidence_root": _text(reveal.get("evidence_root")),
        "admission_receipt_root": _text(reveal.get("admission_receipt_root")),
        "nonce": _text(reveal.get("nonce")),
    }


def compute_commitment(job_id: str, reveal: dict[str, Any]) -> str:
    return digest(COMMITMENT_DOMAIN, commitment_payload(job_id, reveal))


def normalized_bundle_for_root(bundle: dict[str, Any]) -> dict[str, Any]:
    """Normalize set-like protocol arrays before committing the bundle."""
    normalized = copy.deepcopy(bundle)
    sort_keys = {
        "assignments": ("witness_id", "control_domain", "implementation_id"),
        "commitments": ("witness_id", "commitment_root"),
        "reveals": ("witness_id", "verdict", "evidence_root"),
        "disputes": ("dispute_id", "status", "reason_code"),
    }
    for field, fields in sort_keys.items():
        entries = normalized.get(field)
        if isinstance(entries, list) and all(isinstance(entry, dict) for entry in entries):
            entries.sort(key=lambda entry: tuple(str(entry.get(key, "")) for key in fields))
    return normalized


def _validate_job(job: Any, findings: list[dict[str, str]]) -> dict[str, Any]:
    if not isinstance(job, dict):
        findings.append(_finding(
            "ECONOMY_JOB_INVALID", "BLOCK", "$.job", "job must be an object",
        ))
        return {}

    required_keys = {
        "job_id",
        "client_account_id",
        "action_clearance_root",
        "risk_class",
        "assurance_level",
        "pricing_model",
        "currency",
        "customer_charge_minor",
        "platform_fee_minor",
        "dispute_reserve_minor",
        "quorum_required",
        "minimum_control_domains",
        "minimum_implementations",
        "created_at",
        "challenge_window_ends_at",
        "coverage",
        "payment_rail",
        "job_root",
    }
    if set(job) != required_keys:
        findings.append(_finding(
            "ECONOMY_JOB_INVALID", "BLOCK", "$.job",
            "job fields do not match the v0.1 contract",
        ))

    job_id = _text(job.get("job_id"))
    client_account_id = _text(job.get("client_account_id"))
    clearance_root = _text(job.get("action_clearance_root"))
    risk_class = _text(job.get("risk_class"))
    assurance_level = _text(job.get("assurance_level"))
    pricing_model = _text(job.get("pricing_model"))
    currency = _text(job.get("currency"))
    charge = _uint(job.get("customer_charge_minor"), positive=True)
    platform_fee = _uint(job.get("platform_fee_minor"))
    dispute_reserve = _uint(job.get("dispute_reserve_minor"))
    quorum = _uint(job.get("quorum_required"), positive=True)
    minimum_domains = _uint(job.get("minimum_control_domains"), positive=True)
    minimum_implementations = _uint(job.get("minimum_implementations"), positive=True)
    created_at = _timestamp(job.get("created_at"))
    challenge_ends = _timestamp(job.get("challenge_window_ends_at"))
    coverage = _text(job.get("coverage"))
    payment_rail = _text(job.get("payment_rail"))
    declared_root = _text(job.get("job_root"))

    if (
        job_id is None
        or client_account_id is None
        or clearance_root is None
        or not DIGEST_RE.fullmatch(clearance_root)
        or risk_class not in RISK_REQUIREMENTS
        or assurance_level != "INDEPENDENT_QUORUM"
        or pricing_model != "FIXED_RATE_NO_AUCTION"
        or currency is None
        or not CURRENCY_RE.fullmatch(currency)
        or charge is None
        or platform_fee is None
        or dispute_reserve is None
        or quorum is None
        or minimum_domains is None
        or minimum_implementations is None
        or created_at is None
        or challenge_ends is None
        or challenge_ends <= created_at
        or coverage != "NOT_FINANCIALLY_COVERED"
        or payment_rail != "EXTERNAL_PROVIDER_REQUIRED"
        or declared_root is None
        or not DIGEST_RE.fullmatch(declared_root)
    ):
        findings.append(_finding(
            "ECONOMY_JOB_INVALID", "BLOCK", "$.job",
            "job contains an invalid value or unsupported assurance claim",
        ))
        return job

    minimum_quorum, risk_domains, risk_implementations = RISK_REQUIREMENTS[risk_class]
    if (
        quorum < minimum_quorum
        or minimum_domains < risk_domains
        or minimum_implementations < risk_implementations
        or minimum_domains < quorum
    ):
        findings.append(_finding(
            "ECONOMY_RISK_POLICY_UNSATISFIED", "BLOCK", "$.job",
            "risk class requires a stronger quorum or independence threshold",
        ))

    computed_root = compute_job_root(job)
    if declared_root != computed_root:
        findings.append(_finding(
            "ECONOMY_JOB_ROOT_MISMATCH", "CHALLENGE", "$.job.job_root",
            "declared job root does not match the canonical job contract",
        ))
    return job


def evaluate(bundle: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    expected_top_keys = {
        "profile_id",
        "evaluated_at",
        "job",
        "assignments",
        "commitments",
        "reveals",
        "disputes",
    }
    if bundle.get("profile_id") != BUNDLE_PROFILE or set(bundle) != expected_top_keys:
        findings.append(_finding(
            "ECONOMY_BUNDLE_INVALID", "BLOCK", "$",
            "bundle fields do not match the v0.1 economy profile",
        ))

    evaluated_at = _timestamp(bundle.get("evaluated_at"))
    if evaluated_at is None:
        findings.append(_finding(
            "ECONOMY_BUNDLE_INVALID", "BLOCK", "$.evaluated_at",
            "evaluated_at must be an offset-aware timestamp",
        ))

    job = _validate_job(bundle.get("job"), findings)
    job_id = _text(job.get("job_id")) or "UNKNOWN"
    expected_clearance_root = _text(job.get("action_clearance_root"))
    declared_job_root = _text(job.get("job_root"))
    currency = _text(job.get("currency")) or "XXX"
    charge = _uint(job.get("customer_charge_minor")) or 0
    platform_fee = _uint(job.get("platform_fee_minor")) or 0
    dispute_reserve = _uint(job.get("dispute_reserve_minor")) or 0
    quorum = _uint(job.get("quorum_required"), positive=True) or 1
    minimum_domains = _uint(job.get("minimum_control_domains"), positive=True) or 1
    minimum_implementations = _uint(job.get("minimum_implementations"), positive=True) or 1

    assignments_value = bundle.get("assignments")
    assignments = assignments_value if isinstance(assignments_value, list) else []
    if not isinstance(assignments_value, list) or len(assignments) != quorum:
        findings.append(_finding(
            "ECONOMY_ASSIGNMENT_INVALID", "BLOCK", "$.assignments",
            "the fixed-rate v0.1 contract requires exactly quorum_required assignments",
        ))

    assignment_by_witness: dict[str, dict[str, Any]] = {}
    control_domains: set[str] = set()
    implementations: set[str] = set()
    payouts: list[dict[str, Any]] = []
    assignment_keys = {
        "witness_id",
        "control_domain",
        "implementation_id",
        "payout_minor",
        "admission_receipt_root",
    }
    for index, assignment in enumerate(assignments):
        path = f"$.assignments[{index}]"
        if not isinstance(assignment, dict) or set(assignment) != assignment_keys:
            findings.append(_finding(
                "ECONOMY_ASSIGNMENT_INVALID", "BLOCK", path,
                "assignment fields do not match the v0.1 contract",
            ))
            continue
        witness_id = _text(assignment.get("witness_id"))
        control_domain = _text(assignment.get("control_domain"))
        implementation = _text(assignment.get("implementation_id"))
        payout = _uint(assignment.get("payout_minor"), positive=True)
        admission_root = _text(assignment.get("admission_receipt_root"))
        if (
            witness_id is None
            or control_domain is None
            or implementation is None
            or payout is None
            or admission_root is None
            or not DIGEST_RE.fullmatch(admission_root)
            or witness_id in assignment_by_witness
        ):
            findings.append(_finding(
                "ECONOMY_ASSIGNMENT_INVALID", "BLOCK", path,
                "assignment identity, payout, or admission root is invalid or duplicated",
            ))
            continue
        assignment_by_witness[witness_id] = assignment
        control_domains.add(control_domain)
        implementations.add(implementation)
        payouts.append({"witness_id": witness_id, "amount_minor": payout})

    if len(control_domains) < minimum_domains:
        findings.append(_finding(
            "ECONOMY_CONTROL_DOMAIN_DIVERSITY_INSUFFICIENT", "BLOCK", "$.assignments",
            "assigned witnesses do not satisfy control-domain independence",
        ))
    if len(implementations) < minimum_implementations:
        findings.append(_finding(
            "ECONOMY_IMPLEMENTATION_DIVERSITY_INSUFFICIENT", "BLOCK", "$.assignments",
            "assigned witnesses do not satisfy implementation diversity",
        ))

    payout_total = sum(item["amount_minor"] for item in payouts)
    allocation_total = payout_total + platform_fee + dispute_reserve
    if allocation_total != charge:
        findings.append(_finding(
            "ECONOMY_BUDGET_NOT_CONSERVED", "BLOCK", "$.job.customer_charge_minor",
            "witness payouts, platform fee, and dispute reserve must exactly conserve funding",
        ))

    commitments_value = bundle.get("commitments")
    commitments = commitments_value if isinstance(commitments_value, list) else []
    if not isinstance(commitments_value, list):
        findings.append(_finding(
            "ECONOMY_BUNDLE_INVALID", "BLOCK", "$.commitments",
            "commitments must be an array",
        ))
    commitment_by_witness: dict[str, str] = {}
    for index, commitment in enumerate(commitments):
        path = f"$.commitments[{index}]"
        if not isinstance(commitment, dict) or set(commitment) != {"witness_id", "commitment_root"}:
            findings.append(_finding(
                "ECONOMY_BUNDLE_INVALID", "BLOCK", path,
                "commitment fields do not match the v0.1 contract",
            ))
            continue
        witness_id = _text(commitment.get("witness_id"))
        commitment_root = _text(commitment.get("commitment_root"))
        if witness_id is None or commitment_root is None or not DIGEST_RE.fullmatch(commitment_root):
            findings.append(_finding(
                "ECONOMY_BUNDLE_INVALID", "BLOCK", path,
                "commitment identity or digest is invalid",
            ))
            continue
        if witness_id not in assignment_by_witness:
            findings.append(_finding(
                "ECONOMY_UNASSIGNED_COMMITMENT", "CHALLENGE", path,
                "an unassigned witness submitted a commitment",
            ))
            continue
        if witness_id in commitment_by_witness:
            findings.append(_finding(
                "ECONOMY_COMMITMENT_EQUIVOCATION", "CHALLENGE", path,
                "a witness submitted more than one commitment",
            ))
            continue
        commitment_by_witness[witness_id] = commitment_root

    reveals_value = bundle.get("reveals")
    reveals = reveals_value if isinstance(reveals_value, list) else []
    if not isinstance(reveals_value, list):
        findings.append(_finding(
            "ECONOMY_BUNDLE_INVALID", "BLOCK", "$.reveals", "reveals must be an array",
        ))
    reveal_by_witness: dict[str, dict[str, Any]] = {}
    reveal_keys = {
        "witness_id",
        "verdict",
        "action_clearance_root",
        "evidence_root",
        "admission_receipt_root",
        "nonce",
    }
    valid_reveals: list[dict[str, Any]] = []
    for index, reveal in enumerate(reveals):
        path = f"$.reveals[{index}]"
        if not isinstance(reveal, dict) or set(reveal) != reveal_keys:
            findings.append(_finding(
                "ECONOMY_BUNDLE_INVALID", "BLOCK", path,
                "reveal fields do not match the v0.1 contract",
            ))
            continue
        witness_id = _text(reveal.get("witness_id"))
        verdict = _text(reveal.get("verdict"))
        clearance_root = _text(reveal.get("action_clearance_root"))
        evidence_root = _text(reveal.get("evidence_root"))
        admission_root = _text(reveal.get("admission_receipt_root"))
        nonce = _text(reveal.get("nonce"))
        if (
            witness_id is None
            or verdict not in DECISION_RANK
            or clearance_root is None
            or not DIGEST_RE.fullmatch(clearance_root)
            or evidence_root is None
            or not DIGEST_RE.fullmatch(evidence_root)
            or admission_root is None
            or not DIGEST_RE.fullmatch(admission_root)
            or nonce is None
        ):
            findings.append(_finding(
                "ECONOMY_BUNDLE_INVALID", "BLOCK", path,
                "reveal identity, verdict, roots, or nonce is invalid",
            ))
            continue
        if witness_id not in assignment_by_witness:
            findings.append(_finding(
                "ECONOMY_UNASSIGNED_REVEAL", "CHALLENGE", path,
                "an unassigned witness submitted a reveal",
            ))
            continue
        if witness_id in reveal_by_witness:
            findings.append(_finding(
                "ECONOMY_REVEAL_EQUIVOCATION", "CHALLENGE", path,
                "a witness submitted more than one reveal",
            ))
            continue
        reveal_by_witness[witness_id] = reveal
        committed = commitment_by_witness.get(witness_id)
        if committed is None:
            findings.append(_finding(
                "ECONOMY_REVEAL_WITHOUT_COMMITMENT", "CHALLENGE", path,
                "a reveal was submitted without a prior commitment",
            ))
            continue
        if committed != compute_commitment(job_id, reveal):
            findings.append(_finding(
                "ECONOMY_COMMITMENT_MISMATCH", "CHALLENGE", path,
                "reveal bytes do not match the witness commitment",
            ))
            continue
        if expected_clearance_root is not None and clearance_root != expected_clearance_root:
            findings.append(_finding(
                "ECONOMY_CLEARANCE_ROOT_MISMATCH", "CHALLENGE", path,
                "witness reveal is bound to a different Assured Action clearance",
            ))
            continue
        assignment = assignment_by_witness[witness_id]
        if admission_root != assignment["admission_receipt_root"]:
            findings.append(_finding(
                "ECONOMY_ADMISSION_RECEIPT_MISMATCH", "CHALLENGE", path,
                "witness reveal is bound to a different operator admission receipt",
            ))
            continue
        if verdict == "CHALLENGE":
            findings.append(_finding(
                "ECONOMY_WITNESS_CHALLENGE", "CHALLENGE", path,
                "a witness reported conflicting action evidence",
            ))
        valid_reveals.append(reveal)

    for witness_id in sorted(assignment_by_witness):
        if witness_id not in commitment_by_witness:
            findings.append(_finding(
                "ECONOMY_COMMITMENT_MISSING", "HOLD", "$.commitments",
                f"assigned witness {witness_id} has not committed",
            ))
        if witness_id not in reveal_by_witness:
            findings.append(_finding(
                "ECONOMY_REVEAL_MISSING", "HOLD", "$.reveals",
                f"assigned witness {witness_id} has not revealed",
            ))

    consensus_keys = {
        (
            reveal["verdict"],
            reveal["action_clearance_root"],
            reveal["evidence_root"],
        )
        for reveal in valid_reveals
    }
    if len(consensus_keys) > 1:
        findings.append(_finding(
            "ECONOMY_WITNESS_DISSENT_REQUIRES_REVIEW", "HOLD", "$.reveals",
            "valid witnesses disagree; honest dissent is held for review, not slashed",
        ))
    if len(valid_reveals) < quorum:
        findings.append(_finding(
            "ECONOMY_QUORUM_INSUFFICIENT", "HOLD", "$.reveals",
            "the number of valid commit-reveal results is below quorum",
        ))

    disputes_value = bundle.get("disputes")
    disputes = disputes_value if isinstance(disputes_value, list) else []
    if not isinstance(disputes_value, list):
        findings.append(_finding(
            "ECONOMY_BUNDLE_INVALID", "BLOCK", "$.disputes", "disputes must be an array",
        ))
    for index, dispute in enumerate(disputes):
        path = f"$.disputes[{index}]"
        if (
            not isinstance(dispute, dict)
            or set(dispute) != {"dispute_id", "challenger_id", "status", "reason_code", "filed_at"}
            or _text(dispute.get("dispute_id")) is None
            or _text(dispute.get("challenger_id")) is None
            or dispute.get("status") not in {"OPEN", "RESOLVED", "REJECTED"}
            or _text(dispute.get("reason_code")) is None
            or _timestamp(dispute.get("filed_at")) is None
        ):
            findings.append(_finding(
                "ECONOMY_BUNDLE_INVALID", "BLOCK", path,
                "dispute fields do not match the v0.1 contract",
            ))
            continue
        if dispute["status"] == "OPEN":
            findings.append(_finding(
                "ECONOMY_OPEN_DISPUTE", "HOLD", path,
                "settlement remains locked while a dispute is open",
            ))

    challenge_ends = _timestamp(job.get("challenge_window_ends_at"))
    if evaluated_at is not None and challenge_ends is not None and evaluated_at < challenge_ends:
        findings.append(_finding(
            "ECONOMY_CHALLENGE_WINDOW_OPEN", "HOLD", "$.evaluated_at",
            "settlement remains locked until the challenge window closes",
        ))

    sorted_findings = _sort_findings(findings)
    decision = sorted_findings[0]["decision"] if sorted_findings else "ACCEPT"
    primary_reason = sorted_findings[0]["code"] if sorted_findings else "ECONOMY_JOB_FULFILLED"

    action_consensus: dict[str, Any] = {
        "verdict": None,
        "action_clearance_root": None,
        "evidence_root": None,
        "witness_count": len(valid_reveals),
    }
    if len(consensus_keys) == 1 and len(valid_reveals) >= quorum:
        verdict, clearance_root, evidence_root = next(iter(consensus_keys))
        action_consensus.update({
            "verdict": verdict,
            "action_clearance_root": clearance_root,
            "evidence_root": evidence_root,
        })

    settlement_state = {
        "ACCEPT": "READY_FOR_EXTERNAL_PAYMENT_REQUEST",
        "HOLD": "LOCKED",
        "BLOCK": "REJECTED",
        "CHALLENGE": "DISPUTED",
    }[decision]
    next_transition = {
        "ACCEPT": "SUBMIT_TO_EXTERNAL_PAYMENT_PROVIDER",
        "HOLD": "WAIT_FOR_REVEALS_WINDOW_OR_DISPUTE_RESOLUTION",
        "BLOCK": "REPAIR_JOB_CONTRACT",
        "CHALLENGE": "INVESTIGATE_COMMITMENT_OR_EVIDENCE_CONFLICT",
    }[decision]

    receipt: dict[str, Any] = {
        "profile_id": RECEIPT_PROFILE,
        "product": PRODUCT,
        "job_id": job_id,
        "job_root": declared_job_root,
        "bundle_root": digest(BUNDLE_DOMAIN, normalized_bundle_for_root(bundle)),
        "evaluated_at": bundle.get("evaluated_at"),
        "decision": decision,
        "primary_reason_code": primary_reason,
        "findings": sorted_findings,
        "action_consensus": action_consensus,
        "economics": {
            "currency": currency,
            "customer_charge_minor": charge,
            "witness_payouts": sorted(payouts, key=lambda item: item["witness_id"]),
            "witness_payout_total_minor": payout_total,
            "platform_fee_minor": platform_fee,
            "dispute_reserve_minor": dispute_reserve,
            "allocation_total_minor": allocation_total,
            "conservation_verified": allocation_total == charge,
        },
        "independence": {
            "required_control_domains": minimum_domains,
            "observed_control_domains": len(control_domains),
            "required_implementations": minimum_implementations,
            "observed_implementations": len(implementations),
            "selection_method": job.get("pricing_model"),
        },
        "settlement_state": settlement_state,
        "permitted_next_transition": next_transition,
        "payment_request_ready": decision == "ACCEPT",
        "external_payment_authority_granted": False,
        "payment_execution_performed": False,
        "slashing_performed": False,
        "coverage": "NOT_FINANCIALLY_COVERED",
        "assurance": {
            "level": "DETERMINISTIC_SETTLEMENT_PLAN",
            "identity_verification": "UPSTREAM_ADMISSION_RECEIPTS_REQUIRED",
            "money_movement": "OUT_OF_SCOPE",
            "insurance": "NOT_PROVIDED",
        },
        "settlement_root": None,
    }
    receipt["settlement_root"] = digest(SETTLEMENT_DOMAIN, receipt)
    return receipt


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("bundle", type=Path)
    value.add_argument("--output", type=Path)
    value.add_argument("--pretty", action="store_true")
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        bundle = load_json(args.bundle)
        receipt = evaluate(bundle)
    except (EconomyError, OSError, TypeError, KeyError) as exc:
        print(f"ProofPath economy input error: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(
        receipt,
        indent=2 if args.pretty else None,
        separators=None if args.pretty else (",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)
    return EXIT_CODE[receipt["decision"]]


if __name__ == "__main__":
    raise SystemExit(main())
