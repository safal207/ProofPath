#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sys


def decide(action, policy):
    if action.get("action_type") != "agent_payment":
        return "BLOCK", "INVALID_ACTION_TYPE"
    if action.get("asset") not in policy.get("allowed_assets", []):
        return "BLOCK", "ASSET_NOT_ALLOWED"
    try:
        amount = Decimal(str(action.get("amount", "")))
    except InvalidOperation:
        return "BLOCK", "INVALID_AMOUNT"

    approved_budget = action.get("approved_budget", policy.get("default_approved_budget", "0"))
    try:
        budget = Decimal(str(approved_budget))
    except InvalidOperation:
        return "BLOCK", "INVALID_BUDGET"

    if amount > budget:
        return "BLOCK", "OVER_BUDGET"

    if not action.get("purpose"):
        return "BLOCK", "MISSING_PAYMENT_INTENT"
    if not action.get("human_intent_id"):
        return "BLOCK", "MISSING_PAYMENT_INTENT"
    if not action.get("causal_parent"):
        return "BLOCK", "MISSING_PAYMENT_INTENT"

    recipient = action.get("recipient")
    if recipient not in policy.get("allowed_recipients", []):
        return "BLOCK", "RECIPIENT_NOT_ALLOWED"

    approved_recipient = action.get("approved_recipient")
    if approved_recipient is not None and recipient != approved_recipient:
        return "BLOCK", "RECIPIENT_MISMATCH"

    if (
        action.get("payment_mode") == "recurring"
        and policy.get("recurring_payments_require_approval", True)
        and not action.get("recurring_approval")
    ):
        return "HOLD", "RECURRING_PAYMENT_REQUIRES_APPROVAL"

    return "ACCEPT", "PAYMENT_WITHIN_SCOPE_AND_BUDGET"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("proposal")
    parser.add_argument("--policy")
    args = parser.parse_args()

    proposal_path = Path(args.proposal)
    policy_path = Path(args.policy) if args.policy else proposal_path.parent / "payment_policy.json"

    action = json.loads(proposal_path.read_text())
    policy = json.loads(policy_path.read_text())

    decision, reason = decide(action, policy)
    result = {"decision": decision, "reason": reason}
    print(json.dumps(result, separators=(",", ":")))

    audit_dir = Path(".proofpath")
    audit_dir.mkdir(exist_ok=True)
    audit_path = audit_dir / "audit.jsonl"
    record = {
        "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "surface": "agent-payment-guard",
        "decision": decision,
        "reason": reason,
        "agent_id": action.get("agent_id"),
        "asset": action.get("asset"),
        "amount": action.get("amount"),
        "approved_budget": action.get("approved_budget", policy.get("default_approved_budget")),
        "recipient": action.get("recipient"),
        "causal_parent": action.get("causal_parent"),
    }
    with audit_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")

    code = {"ACCEPT": 0, "BLOCK": 2, "HOLD": 3}[decision]
    sys.exit(code)


if __name__ == "__main__":
    main()
