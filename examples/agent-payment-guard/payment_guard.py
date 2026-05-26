#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from hashlib import sha256
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


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


def canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_record_hash(record: Dict[str, Any]) -> str:
    payload = dict(record)
    payload.pop("hash", None)
    return "sha256:" + sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def get_previous_hash(path: Path) -> str:
    if not path.exists():
        return "GENESIS"

    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return "GENESIS"

    last_record = json.loads(lines[-1])
    previous_hash = last_record.get("hash")
    if isinstance(previous_hash, str) and previous_hash:
        return previous_hash
    return "GENESIS"


def append_audit(
    path: Path,
    proposal: Dict[str, Any],
    decision: str,
    reason: str,
    *,
    intent_verified: Optional[bool] = None,
    intent_envelope_id: Optional[str] = None,
    intent_signature_alg: Optional[str] = None,
    intent_expires_at: Optional[str] = None,
    intent_nonce: Optional[str] = None,
    intent_load_error: Optional[str] = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    previous_hash = get_previous_hash(path)
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
        "intent_verified": intent_verified,
        "intent_envelope_id": intent_envelope_id,
        "intent_signature_alg": intent_signature_alg,
        "intent_expires_at": intent_expires_at,
        "intent_nonce": intent_nonce,
        "intent_load_error": intent_load_error,
        "previous_hash": previous_hash,
    }
    record["hash"] = compute_record_hash(record)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("proposal")
    parser.add_argument("--policy")
    parser.add_argument("--intent-envelope")
    args = parser.parse_args()

    proposal_path = Path(args.proposal)
    policy_path = Path(args.policy) if args.policy else proposal_path.parent / "payment_policy.json"

    proposal = load_json(proposal_path)
    policy = load_json(policy_path)

    if args.intent_envelope:
        intent_envelope_path = Path(args.intent_envelope)
        if not intent_envelope_path.exists():
            decision = "BLOCK"
            reason = "MISSING_INTENT_ENVELOPE"
            append_audit(
                Path(".proofpath/audit.jsonl"),
                proposal,
                decision,
                reason,
                intent_verified=False,
                intent_envelope_id=None,
                intent_signature_alg=None,
                intent_expires_at=None,
                intent_nonce=None,
                intent_load_error="missing",
            )
            print(json.dumps({"decision": decision, "reason": reason}, separators=(",", ":")))
            return 2
        try:
            envelope = load_json(intent_envelope_path)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            decision = "BLOCK"
            reason = "INVALID_INTENT_SIGNATURE"
            append_audit(
                Path(".proofpath/audit.jsonl"),
                proposal,
                decision,
                reason,
                intent_verified=False,
                intent_envelope_id=None,
                intent_signature_alg=None,
                intent_expires_at=None,
                intent_nonce=None,
                intent_load_error="malformed",
            )
            print(json.dumps({"decision": decision, "reason": reason}, separators=(",", ":")))
            return 2
    else:
        envelope = {}

    decision, reason = decide(proposal, policy)
    append_audit(
        Path(".proofpath/audit.jsonl"),
        proposal,
        decision,
        reason,
        intent_verified=bool(args.intent_envelope),
        intent_envelope_id=envelope.get("intent_envelope_id"),
        intent_signature_alg=envelope.get("signature_alg"),
        intent_expires_at=envelope.get("expires_at"),
        intent_nonce=envelope.get("nonce"),
        intent_load_error=None,
    )

    print(json.dumps({"decision": decision, "reason": reason}, separators=(",", ":")))
    return 0 if decision == "ACCEPT" else 2 if decision == "BLOCK" else 3


if __name__ == "__main__":
    raise SystemExit(main())
