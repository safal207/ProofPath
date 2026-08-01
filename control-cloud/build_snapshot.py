#!/usr/bin/env python3
"""Build a deterministic ProofPath Control Cloud snapshot from Assured Action records."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

DATASET_PROFILE = "proofpath.control-cloud.dataset.v0.1"
POLICY_PROFILE = "proofpath.control-cloud.settlement-policy.v0.1"
SNAPSHOT_PROFILE = "proofpath.control-cloud.snapshot.v0.1"
CERTIFICATE_PROFILE = "proofpath.deploy.clearance-certificate.v0.1"
SNAPSHOT_DOMAIN = b"proofpath:control-cloud:v0.1:snapshot\n"
DECISIONS = ("ACCEPT", "HOLD", "BLOCK", "CHALLENGE")
RISK_TIERS = ("low", "medium", "high", "critical")
DISPUTE_STATES = ("none", "open", "resolved")
HEX_ROOT_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
SAFE_TEXT_RE = re.compile(r"^[^\x00\r\n]+$")


class ControlCloudError(ValueError):
    """Raised when a Control Cloud input cannot be processed safely."""


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ControlCloudError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_float(value: str) -> None:
    raise ControlCloudError(f"floating-point numbers are forbidden: {value}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_float=reject_float,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ControlCloudError) as exc:
        raise ControlCloudError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ControlCloudError(f"{path} must contain one JSON object")
    return value


def canonical_bytes(value: Any) -> bytes:
    def normalize(item: Any) -> Any:
        if isinstance(item, float):
            raise ControlCloudError("floating-point values are forbidden in canonical output")
        if isinstance(item, dict):
            return {key: normalize(item[key]) for key in sorted(item)}
        if isinstance(item, list):
            return [normalize(entry) for entry in item]
        if item is None or isinstance(item, (str, int, bool)):
            return item
        raise ControlCloudError(f"unsupported canonical type: {type(item).__name__}")

    return json.dumps(
        normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def compute_snapshot_root(snapshot: dict[str, Any]) -> str:
    root_input = dict(snapshot)
    root_input["snapshot_root"] = None
    return "sha256:" + hashlib.sha256(SNAPSHOT_DOMAIN + canonical_bytes(root_input)).hexdigest()


def require_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or not SAFE_TEXT_RE.fullmatch(value):
        raise ControlCloudError(f"{name} must be a non-empty single-line string")
    return value


def require_int(value: Any, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ControlCloudError(f"{name} must be an integer >= {minimum}")
    return value


def require_exact_keys(value: dict[str, Any], required: set[str], optional: set[str], name: str) -> None:
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required - optional)
    if missing:
        raise ControlCloudError(f"{name} is missing required fields: {', '.join(missing)}")
    if unknown:
        raise ControlCloudError(f"{name} contains unsupported fields: {', '.join(unknown)}")


def parse_timestamp(value: Any, name: str) -> str:
    text = require_text(value, name)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ControlCloudError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ControlCloudError(f"{name} must include a timezone")
    return text


def workspace_path(raw: str, name: str, *, must_exist: bool = False) -> Path:
    root = Path(os.environ.get("GITHUB_WORKSPACE", os.getcwd())).resolve()
    path = Path(raw)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ControlCloudError(f"{name} must remain inside the workspace") from exc
    if must_exist and not path.is_file():
        raise ControlCloudError(f"{name} does not exist: {path}")
    return path


def validate_policy(policy: dict[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        policy,
        {
            "profile_id",
            "policy_id",
            "policy_version",
            "currency",
            "financial_mode",
            "allocations_bps",
            "decision_multipliers_bps",
            "risk_multipliers_bps",
        },
        set(),
        "settlement policy",
    )
    if policy["profile_id"] != POLICY_PROFILE:
        raise ControlCloudError("unsupported settlement policy profile")
    policy_id = require_text(policy["policy_id"], "policy_id")
    policy_version = require_text(policy["policy_version"], "policy_version")
    currency = require_text(policy["currency"], "currency")
    if not CURRENCY_RE.fullmatch(currency):
        raise ControlCloudError("currency must be a three-letter uppercase code")
    if policy["financial_mode"] != "SIMULATION_ONLY":
        raise ControlCloudError("financial_mode must be SIMULATION_ONLY")

    allocations = policy["allocations_bps"]
    if not isinstance(allocations, dict):
        raise ControlCloudError("allocations_bps must be an object")
    expected_allocations = {"operator_pool", "dispute_reserve", "infrastructure", "platform"}
    require_exact_keys(allocations, expected_allocations, set(), "allocations_bps")
    normalized_allocations = {
        key: require_int(allocations[key], f"allocations_bps.{key}")
        for key in sorted(expected_allocations)
    }
    if sum(normalized_allocations.values()) != 10_000:
        raise ControlCloudError("allocations_bps must sum to exactly 10000")

    decision_multipliers = policy["decision_multipliers_bps"]
    if not isinstance(decision_multipliers, dict):
        raise ControlCloudError("decision_multipliers_bps must be an object")
    require_exact_keys(decision_multipliers, set(DECISIONS), set(), "decision_multipliers_bps")
    normalized_decisions = {
        decision: require_int(decision_multipliers[decision], f"decision_multipliers_bps.{decision}")
        for decision in DECISIONS
    }

    risk_multipliers = policy["risk_multipliers_bps"]
    if not isinstance(risk_multipliers, dict):
        raise ControlCloudError("risk_multipliers_bps must be an object")
    require_exact_keys(risk_multipliers, set(RISK_TIERS), set(), "risk_multipliers_bps")
    normalized_risks = {
        risk: require_int(risk_multipliers[risk], f"risk_multipliers_bps.{risk}", 1)
        for risk in RISK_TIERS
    }
    return {
        "profile_id": POLICY_PROFILE,
        "policy_id": policy_id,
        "policy_version": policy_version,
        "currency": currency,
        "financial_mode": "SIMULATION_ONLY",
        "allocations_bps": normalized_allocations,
        "decision_multipliers_bps": normalized_decisions,
        "risk_multipliers_bps": normalized_risks,
    }


def validate_certificate(certificate: Any, index: int) -> dict[str, Any]:
    if not isinstance(certificate, dict):
        raise ControlCloudError(f"actions[{index}].certificate must be an object")
    required = {
        "profile_id", "product", "decision", "valid", "primary_reason_code", "action",
        "assurance", "policy_root", "evidence_root", "clearance_root", "execution_allowed",
        "authority_granted",
    }
    missing = sorted(required - certificate.keys())
    if missing:
        raise ControlCloudError(f"actions[{index}].certificate is missing: {', '.join(missing)}")
    if certificate["profile_id"] != CERTIFICATE_PROFILE:
        raise ControlCloudError(f"actions[{index}] has an unsupported certificate profile")
    if certificate["product"] != "PROOFPATH_ASSURED_ACTION":
        raise ControlCloudError(f"actions[{index}] is not a ProofPath Assured Action")
    decision = require_text(certificate["decision"], f"actions[{index}].certificate.decision")
    if decision not in DECISIONS:
        raise ControlCloudError(f"actions[{index}] has an unsupported decision")
    if not isinstance(certificate["valid"], bool) or not isinstance(certificate["execution_allowed"], bool):
        raise ControlCloudError(f"actions[{index}] certificate booleans are malformed")
    if certificate["authority_granted"] is not False:
        raise ControlCloudError(f"actions[{index}] attempts to grant authority")
    if decision == "ACCEPT":
        if certificate["valid"] is not True or certificate["execution_allowed"] is not True:
            raise ControlCloudError(f"actions[{index}] ACCEPT must be valid and execution_allowed")
        if certificate["primary_reason_code"] is not None:
            raise ControlCloudError(f"actions[{index}] ACCEPT must not have a primary reason")
    else:
        if certificate["valid"] is not False or certificate["execution_allowed"] is not False:
            raise ControlCloudError(f"actions[{index}] non-ACCEPT must be invalid and execution denied")
        require_text(certificate["primary_reason_code"], f"actions[{index}].certificate.primary_reason_code")

    action = certificate["action"]
    if not isinstance(action, dict):
        raise ControlCloudError(f"actions[{index}].certificate.action must be an object")
    for field in ("action_id", "agent_id", "repository", "branch", "commit_sha", "environment", "artifact_digest"):
        require_text(action.get(field), f"actions[{index}].certificate.action.{field}")
    if action.get("action_type") != "deploy":
        raise ControlCloudError(f"actions[{index}] action_type must be deploy")
    if not SHA_RE.fullmatch(action["commit_sha"]):
        raise ControlCloudError(f"actions[{index}] commit_sha is malformed")
    if not HEX_ROOT_RE.fullmatch(action["artifact_digest"]):
        raise ControlCloudError(f"actions[{index}] artifact_digest is malformed")

    assurance = certificate["assurance"]
    if not isinstance(assurance, dict):
        raise ControlCloudError(f"actions[{index}].certificate.assurance must be an object")
    for field in ("assurance_level", "witness_level", "coverage", "policy_id", "policy_version"):
        require_text(assurance.get(field), f"actions[{index}].certificate.assurance.{field}")
    if assurance["coverage"] not in {"NOT_FINANCIALLY_COVERED", "PARTNER_COVERED"}:
        raise ControlCloudError(f"actions[{index}] has an unsupported coverage label")

    for field in ("policy_root", "evidence_root", "clearance_root"):
        value = require_text(certificate[field], f"actions[{index}].certificate.{field}")
        if not HEX_ROOT_RE.fullmatch(value):
            raise ControlCloudError(f"actions[{index}].certificate.{field} is malformed")
    return certificate


def validate_dataset(dataset: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        dataset,
        {"profile_id", "tenant_id", "generated_at", "financial_mode", "actions"},
        set(),
        "dataset",
    )
    if dataset["profile_id"] != DATASET_PROFILE:
        raise ControlCloudError("unsupported dataset profile")
    if dataset["financial_mode"] != "SIMULATION_ONLY":
        raise ControlCloudError("dataset financial_mode must be SIMULATION_ONLY")
    tenant_id = require_text(dataset["tenant_id"], "tenant_id")
    generated_at = parse_timestamp(dataset["generated_at"], "generated_at")
    actions = dataset["actions"]
    if not isinstance(actions, list) or not actions:
        raise ControlCloudError("actions must be a non-empty array")

    normalized: list[dict[str, Any]] = []
    action_ids: set[str] = set()
    clearance_roots: set[str] = set()
    for index, record in enumerate(actions):
        if not isinstance(record, dict):
            raise ControlCloudError(f"actions[{index}] must be an object")
        require_exact_keys(
            record,
            {"certificate", "observed_at", "risk_tier", "base_price_minor", "operator_assignments", "dispute_state"},
            set(),
            f"actions[{index}]",
        )
        certificate = validate_certificate(record["certificate"], index)
        action_id = certificate["action"]["action_id"]
        clearance_root = certificate["clearance_root"]
        if action_id in action_ids:
            raise ControlCloudError(f"duplicate action_id: {action_id}")
        if clearance_root in clearance_roots:
            raise ControlCloudError(f"duplicate clearance_root: {clearance_root}")
        action_ids.add(action_id)
        clearance_roots.add(clearance_root)

        observed_at = parse_timestamp(record["observed_at"], f"actions[{index}].observed_at")
        risk_tier = require_text(record["risk_tier"], f"actions[{index}].risk_tier")
        if risk_tier not in RISK_TIERS:
            raise ControlCloudError(f"actions[{index}] risk_tier is unsupported")
        base_price = require_int(record["base_price_minor"], f"actions[{index}].base_price_minor")
        dispute_state = require_text(record["dispute_state"], f"actions[{index}].dispute_state")
        if dispute_state not in DISPUTE_STATES:
            raise ControlCloudError(f"actions[{index}] dispute_state is unsupported")

        assignments = record["operator_assignments"]
        if not isinstance(assignments, list) or not assignments:
            raise ControlCloudError(f"actions[{index}].operator_assignments must be non-empty")
        seen_operators: set[str] = set()
        normalized_assignments: list[dict[str, Any]] = []
        for assignment_index, assignment in enumerate(assignments):
            if not isinstance(assignment, dict):
                raise ControlCloudError(f"actions[{index}].operator_assignments[{assignment_index}] must be an object")
            require_exact_keys(
                assignment,
                {"operator_id", "role", "weight"},
                set(),
                f"actions[{index}].operator_assignments[{assignment_index}]",
            )
            operator_id = require_text(assignment["operator_id"], f"actions[{index}].operator_assignments[{assignment_index}].operator_id")
            if operator_id in seen_operators:
                raise ControlCloudError(f"actions[{index}] contains duplicate operator_id {operator_id}")
            seen_operators.add(operator_id)
            role = require_text(assignment["role"], f"actions[{index}].operator_assignments[{assignment_index}].role")
            weight = require_int(assignment["weight"], f"actions[{index}].operator_assignments[{assignment_index}].weight", 1)
            normalized_assignments.append({"operator_id": operator_id, "role": role, "weight": weight})

        normalized.append(
            {
                "certificate": certificate,
                "observed_at": observed_at,
                "risk_tier": risk_tier,
                "base_price_minor": base_price,
                "operator_assignments": sorted(normalized_assignments, key=lambda item: item["operator_id"]),
                "dispute_state": dispute_state,
            }
        )
    return {
        "profile_id": DATASET_PROFILE,
        "tenant_id": tenant_id,
        "generated_at": generated_at,
        "financial_mode": "SIMULATION_ONLY",
        "actions": sorted(normalized, key=lambda item: (item["observed_at"], item["certificate"]["action"]["action_id"])),
    }


def allocate_operator_pool(pool: int, assignments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total_weight = sum(item["weight"] for item in assignments)
    payouts = [
        {
            "operator_id": item["operator_id"],
            "role": item["role"],
            "weight": item["weight"],
            "amount_minor": (pool * item["weight"]) // total_weight,
        }
        for item in assignments
    ]
    remainder = pool - sum(item["amount_minor"] for item in payouts)
    for index in range(remainder):
        payouts[index % len(payouts)]["amount_minor"] += 1
    return payouts


def build_snapshot(dataset: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    normalized_policy = validate_policy(policy)
    normalized_dataset = validate_dataset(dataset, normalized_policy)
    decision_counts = {decision: 0 for decision in DECISIONS}
    risk_counts = {risk: 0 for risk in RISK_TIERS}
    totals = {
        "gross_revenue_minor": 0,
        "operator_pool_minor": 0,
        "dispute_reserve_minor": 0,
        "infrastructure_minor": 0,
        "platform_revenue_minor": 0,
    }
    operator_totals: dict[str, dict[str, Any]] = {}
    action_summaries: list[dict[str, Any]] = []

    for record in normalized_dataset["actions"]:
        certificate = record["certificate"]
        action = certificate["action"]
        assurance = certificate["assurance"]
        decision = certificate["decision"]
        risk = record["risk_tier"]
        decision_counts[decision] += 1
        risk_counts[risk] += 1

        risk_scaled = (record["base_price_minor"] * normalized_policy["risk_multipliers_bps"][risk]) // 10_000
        gross = (risk_scaled * normalized_policy["decision_multipliers_bps"][decision]) // 10_000
        allocations = normalized_policy["allocations_bps"]
        operator_pool = (gross * allocations["operator_pool"]) // 10_000
        reserve = (gross * allocations["dispute_reserve"]) // 10_000
        infrastructure = (gross * allocations["infrastructure"]) // 10_000
        platform = gross - operator_pool - reserve - infrastructure
        payouts = allocate_operator_pool(operator_pool, record["operator_assignments"])

        totals["gross_revenue_minor"] += gross
        totals["operator_pool_minor"] += operator_pool
        totals["dispute_reserve_minor"] += reserve
        totals["infrastructure_minor"] += infrastructure
        totals["platform_revenue_minor"] += platform

        for payout in payouts:
            current = operator_totals.setdefault(
                payout["operator_id"],
                {"operator_id": payout["operator_id"], "roles": set(), "action_count": 0, "earnings_minor": 0},
            )
            current["roles"].add(payout["role"])
            current["action_count"] += 1
            current["earnings_minor"] += payout["amount_minor"]

        action_summaries.append(
            {
                "action_id": action["action_id"],
                "observed_at": record["observed_at"],
                "decision": decision,
                "primary_reason_code": certificate["primary_reason_code"],
                "risk_tier": risk,
                "repository": action["repository"],
                "branch": action["branch"],
                "commit_sha": action["commit_sha"],
                "environment": action["environment"],
                "agent_id": action["agent_id"],
                "artifact_digest": action["artifact_digest"],
                "assurance_level": assurance["assurance_level"],
                "witness_level": assurance["witness_level"],
                "coverage": assurance["coverage"],
                "policy_id": assurance["policy_id"],
                "policy_version": assurance["policy_version"],
                "policy_root": certificate["policy_root"],
                "evidence_root": certificate["evidence_root"],
                "clearance_root": certificate["clearance_root"],
                "execution_allowed": certificate["execution_allowed"],
                "authority_granted": False,
                "dispute_state": record["dispute_state"],
                "base_price_minor": record["base_price_minor"],
                "gross_price_minor": gross,
                "operator_pool_minor": operator_pool,
                "dispute_reserve_minor": reserve,
                "infrastructure_minor": infrastructure,
                "platform_revenue_minor": platform,
                "operator_payouts": payouts,
                "financial_status": "SIMULATION_ONLY_NOT_PAYABLE",
            }
        )

    operator_earnings = [
        {
            "operator_id": item["operator_id"],
            "roles": sorted(item["roles"]),
            "action_count": item["action_count"],
            "earnings_minor": item["earnings_minor"],
            "financial_status": "SIMULATION_ONLY_NOT_PAYABLE",
        }
        for item in sorted(operator_totals.values(), key=lambda item: item["operator_id"])
    ]

    if totals["gross_revenue_minor"] != (
        totals["operator_pool_minor"]
        + totals["dispute_reserve_minor"]
        + totals["infrastructure_minor"]
        + totals["platform_revenue_minor"]
    ):
        raise ControlCloudError("settlement conservation invariant failed")
    if totals["operator_pool_minor"] != sum(item["earnings_minor"] for item in operator_earnings):
        raise ControlCloudError("operator payout conservation invariant failed")

    snapshot: dict[str, Any] = {
        "profile_id": SNAPSHOT_PROFILE,
        "tenant_id": normalized_dataset["tenant_id"],
        "generated_at": normalized_dataset["generated_at"],
        "currency": normalized_policy["currency"],
        "financial_mode": "SIMULATION_ONLY",
        "settlement_policy": {
            "policy_id": normalized_policy["policy_id"],
            "policy_version": normalized_policy["policy_version"],
            "allocations_bps": normalized_policy["allocations_bps"],
            "decision_multipliers_bps": normalized_policy["decision_multipliers_bps"],
            "risk_multipliers_bps": normalized_policy["risk_multipliers_bps"],
        },
        "action_count": len(action_summaries),
        "decision_counts": decision_counts,
        "risk_counts": risk_counts,
        "financial_summary": totals,
        "operator_earnings": operator_earnings,
        "actions": action_summaries,
        "assurance_boundary": {
            "financial_status": "SIMULATION_ONLY_NOT_PAYABLE",
            "payments_executed": False,
            "insurance_provided": False,
            "deployment_performed": False,
            "authority_granted": False,
            "external_quorum_claimed": False,
        },
        "limitations": [
            "This snapshot is a deterministic simulation and is not an invoice, balance, payout, insurance policy, or financial guarantee.",
            "Operator earnings are preview allocations only; no payment processor, bank, wallet, or ledger is called.",
            "The dashboard summarizes supplied Assured Action certificates and does not independently re-run their underlying policies.",
            "Coverage labels are copied from certificates; this reference dataset remains NOT_FINANCIALLY_COVERED.",
            "Control Cloud does not deploy, merge, grant authority, or modify customer infrastructure.",
        ],
        "snapshot_root": None,
    }
    snapshot["snapshot_root"] = compute_snapshot_root(snapshot)
    return snapshot


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_audit_export(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for action in snapshot["actions"]:
        event = {
            "profile_id": "proofpath.control-cloud.audit-event.v0.1",
            "tenant_id": snapshot["tenant_id"],
            "generated_at": snapshot["generated_at"],
            "snapshot_root": snapshot["snapshot_root"],
            "currency": snapshot["currency"],
            "financial_mode": snapshot["financial_mode"],
            "action": action,
        }
        lines.append(canonical_bytes(event).decode("utf-8"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--audit-export", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(sys.argv[1:] if argv is None else argv)
        dataset_path = workspace_path(args.dataset, "dataset", must_exist=True)
        policy_path = workspace_path(args.policy, "policy", must_exist=True)
        output_path = workspace_path(args.output, "output")
        audit_path = workspace_path(args.audit_export, "audit-export")
        if len({dataset_path, policy_path, output_path, audit_path}) != 4:
            raise ControlCloudError("dataset, policy, output, and audit-export paths must differ")
        snapshot = build_snapshot(load_json(dataset_path), load_json(policy_path))
        write_json(output_path, snapshot)
        write_audit_export(audit_path, snapshot)
        print(
            "ProofPath Control Cloud: "
            f"actions={snapshot['action_count']} "
            f"gross={snapshot['financial_summary']['gross_revenue_minor']} "
            f"operators={len(snapshot['operator_earnings'])} "
            f"root={snapshot['snapshot_root']}"
        )
        return 0
    except (ControlCloudError, OSError, KeyError, TypeError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
