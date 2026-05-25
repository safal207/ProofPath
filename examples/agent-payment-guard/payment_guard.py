#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Tuple


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def decide(proposal: Dict[str, Any], policy: Dict[str, Any]) -> Tuple[str, str]:
    if proposal.get("action_type") != "agent_payment":
        return "BLOCK", "INVALID_ACTION_TYPE"

    asset = proposal.get("asset")
    if asset not in policy.get("allowed_assets", []):
        return "BLOCK", "ASSET_NOT_ALLOWED"

    try:
        amount = Decimal(str(proposal.get("amount")))
    except (InvalidOperation, TypeError):
        return "BLOCK", "INVALID_AMOUNT"

    approved_budget = proposal.get("approved_budget", policy.get("default_approved_budget", "0"))
    try:
        budget = Decimal(str(approved_budget))
    except (InvalidOperation, TypeError):
        return "BLOCK", "INVALID_APPROVED_BUDGET"

    if amount > budget:
        return "BLOCK", "OVER_BUDGET"

    if not proposal.get("purpose") or not proposal.get("human_intent_id") or not proposal.get("causal_parent"):
        return "BLOCK", "MISSING_PAYMENT_INTENT"

    recipient = proposal.get("recipient")
    if recipient not in policy.get("allowed_recipients", []):
        return "BLOCK", "RECIPIENT_NOT_ALLOWED"

    approved_recipient = proposal.get("approved_recipient")
    if approved_recipient is not None and recipient != approved_recipient:
        return "BLOCK", "RECIPIENT_MISMATCH"

    if (
        proposal.get("payment_mode") == "recurring"
        and policy.get("recurring_payments_require_approval", True)
        and not proposal.get("recurring_approval")
    ):
        return "HOLD", "RECURRING_PAYMENT_REQUIRES_APPROVAL"

    return "ACCEPT", "PAYMENT_WITHIN_SCOPE_AND_BUDGET"


def append_audit(path: Path, proposal: Dict[str, Any], decision: str, reason: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "surface": "agent-payment-guard",
        "decision": decision,
        "reason": reason,
        "agent_id": proposal.get("agent_id"),
        "asset": proposal.get("asset"),
        "amount": proposal.get("amount"),
        "approved_budget": proposal.get("approved_budget"),
        "recipient": proposal.get("recipient"),
        "causal_parent": proposal.get("causal_parent"),
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("proposal")
    parser.add_argument("--policy")
    args = parser.parse_args()

    proposal_path = Path(args.proposal)
    policy_path = Path(args.policy) if args.policy else proposal_path.parent / "payment_policy.json"

    proposal = load_json(proposal_path)
    policy = load_json(policy_path)

    decision, reason = decide(proposal, policy)
    append_audit(Path(".proofpath/audit.jsonl"), proposal, decision, reason)

    print(json.dumps({"decision": decision, "reason": reason}, separators=(",", ":")))
    return 0 if decision == "ACCEPT" else 2 if decision == "BLOCK" else 3


if __name__ == "__main__":
    raise SystemExit(main())
