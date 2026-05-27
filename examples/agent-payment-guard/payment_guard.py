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

DEMO_SIGNATURE_SECRET = "proofpath-demo-secret-v0"
DEFAULT_REPLAY_STORE_PATH = Path(".proofpath/replay-store.json")


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def parse_ts(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_replay_store(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return {str(nonce): record for nonce, record in payload.items() if isinstance(record, dict)}


def save_replay_store(path: Path, store: Dict[str, Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(store, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def record_nonce(
    path: Path,
    nonce: str,
    *,
    human_intent_id: Optional[str],
    agent_id: Optional[str],
    decision_hash: Optional[str],
) -> None:
    if not nonce:
        return
    store = load_replay_store(path)
    store[nonce] = {
        "nonce": nonce,
        "human_intent_id": human_intent_id,
        "agent_id": agent_id,
        "used_at": utc_now(),
        "decision_hash": decision_hash,
        "status": "used",
    }
    save_replay_store(path, store)


def verify_intent_envelope(proposal: Dict[str, Any], envelope: Dict[str, Any], now: datetime) -> Tuple[bool, str]:
    if envelope.get("signature_alg") != "demo-sha256-v0":
        return False, "INVALID_INTENT_SIGNATURE"
    if envelope.get("envelope_type") != "signed_human_intent" or envelope.get("version") != "0.1":
        return False, "INVALID_INTENT_SIGNATURE"

    expected_payload = dict(envelope)
    signature = expected_payload.pop("signature", None)
    expected_sig = sha256((canonical_json(expected_payload) + DEMO_SIGNATURE_SECRET).encode("utf-8")).hexdigest()
    if signature != expected_sig:
        return False, "INVALID_INTENT_SIGNATURE"

    expires = parse_ts(str(envelope.get("expires_at", "")))
    if expires is None or expires <= now:
        return False, "INTENT_EXPIRED"

    if proposal.get("agent_id") != envelope.get("subject_agent_id"):
        return False, "INTENT_AGENT_MISMATCH"
    if proposal.get("purpose") != envelope.get("purpose"):
        return False, "INTENT_PURPOSE_MISMATCH"
    if proposal.get("causal_parent") != envelope.get("causal_parent"):
        return False, "INTENT_CAUSAL_PARENT_MISMATCH"
    if proposal.get("human_intent_id") != envelope.get("human_intent_id"):
        return False, "INTENT_ID_MISMATCH"
    if proposal.get("payment_mode") != envelope.get("payment_mode"):
        return False, "INTENT_PAYMENT_MODE_MISMATCH"
    if proposal.get("asset") != envelope.get("allowed_asset"):
        return False, "INTENT_ASSET_MISMATCH"
    if proposal.get("recipient") != envelope.get("allowed_recipient"):
        return False, "INTENT_RECIPIENT_MISMATCH"
    if proposal.get("budget_scope") != envelope.get("budget_scope"):
        return False, "INTENT_BUDGET_SCOPE_MISMATCH"

    try:
        amount = Decimal(str(proposal.get("amount")))
        max_amount = Decimal(str(envelope.get("max_amount")))
    except (InvalidOperation, TypeError):
        return False, "INVALID_AMOUNT"
    if amount > max_amount:
        return False, "INTENT_AMOUNT_EXCEEDED"

    return True, "PAYMENT_WITHIN_SIGNED_INTENT_ENVELOPE"


def nonce_replayed(audit_path: Path, nonce: str, replay_store_path: Optional[Path] = None) -> bool:
    if not nonce:
        return False

    if replay_store_path is not None and replay_store_path.exists():
        return nonce in load_replay_store(replay_store_path)

    if not audit_path.exists():
        return False
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("intent_verified") and record.get("intent_nonce") == nonce:
            return True
    return False


def intent_load_error_meta(load_error: str) -> Dict[str, Any]:
    return {
        "intent_verified": False,
        "intent_envelope_id": None,
        "intent_signature_alg": None,
        "intent_expires_at": None,
        "intent_nonce": None,
        "intent_load_error": load_error,
    }


def decide(
    proposal: Dict[str, Any],
    policy: Dict[str, Any],
    envelope: Optional[Dict[str, Any]],
    strict_mode: bool,
    audit_path: Path,
    replay_store_path: Optional[Path] = None,
) -> Tuple[str, str, Dict[str, Any]]:
    intent_meta: Dict[str, Any] = {
        "intent_verified": False,
        "intent_envelope_id": None,
        "intent_signature_alg": None,
        "intent_expires_at": None,
        "intent_nonce": None,
    }

    if proposal.get("action_type") != "agent_payment":
        return "BLOCK", "INVALID_ACTION_TYPE", intent_meta

    asset = proposal.get("asset")
    if asset not in policy.get("allowed_assets", []):
        return "BLOCK", "ASSET_NOT_ALLOWED", intent_meta

    try:
        amount = Decimal(str(proposal.get("amount")))
    except (InvalidOperation, TypeError):
        return "BLOCK", "INVALID_AMOUNT", intent_meta

    approved_budget = proposal.get("approved_budget", policy.get("default_approved_budget", "0"))
    try:
        budget = Decimal(str(approved_budget))
    except (InvalidOperation, TypeError):
        return "BLOCK", "INVALID_APPROVED_BUDGET", intent_meta

    if amount > budget:
        return "BLOCK", "OVER_BUDGET", intent_meta

    if not proposal.get("purpose") or not proposal.get("human_intent_id") or not proposal.get("causal_parent"):
        return "BLOCK", "MISSING_PAYMENT_INTENT", intent_meta

    recipient = proposal.get("recipient")
    if recipient not in policy.get("allowed_recipients", []):
        return "BLOCK", "RECIPIENT_NOT_ALLOWED", intent_meta

    approved_recipient = proposal.get("approved_recipient")
    if approved_recipient is not None and recipient != approved_recipient:
        return "BLOCK", "RECIPIENT_MISMATCH", intent_meta

    if (
        proposal.get("payment_mode") == "recurring"
        and policy.get("recurring_payments_require_approval", True)
        and not proposal.get("recurring_approval")
    ):
        return "HOLD", "RECURRING_PAYMENT_REQUIRES_APPROVAL", intent_meta

    if envelope is None and strict_mode:
        return "BLOCK", "MISSING_INTENT_ENVELOPE", intent_meta

    if envelope is not None:
        intent_meta.update(
            {
                "intent_envelope_id": envelope.get("human_intent_id"),
                "intent_signature_alg": envelope.get("signature_alg"),
                "intent_expires_at": envelope.get("expires_at"),
                "intent_nonce": envelope.get("nonce"),
            }
        )
        if nonce_replayed(audit_path, str(envelope.get("nonce", "")), replay_store_path):
            return "BLOCK", "INTENT_REPLAYED", intent_meta
        ok, reason = verify_intent_envelope(proposal, envelope, datetime.now(timezone.utc))
        if not ok:
            return "BLOCK", reason, intent_meta
        intent_meta["intent_verified"] = True
        return "ACCEPT", "PAYMENT_WITHIN_SIGNED_INTENT_ENVELOPE", intent_meta

    return "ACCEPT", "PAYMENT_WITHIN_SCOPE_AND_BUDGET", intent_meta


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


def append_audit(path: Path, proposal: Dict[str, Any], decision: str, reason: str, intent_meta: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    previous_hash = get_previous_hash(path)
    record = {
        "ts": utc_now(),
        "surface": "agent-payment-guard",
        "decision": decision,
        "reason": reason,
        "agent_id": proposal.get("agent_id"),
        "asset": proposal.get("asset"),
        "amount": proposal.get("amount"),
        "approved_budget": proposal.get("approved_budget"),
        "recipient": proposal.get("recipient"),
        "causal_parent": proposal.get("causal_parent"),
        "previous_hash": previous_hash,
        **intent_meta,
    }
    record["hash"] = compute_record_hash(record)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def persist_accepted_nonce_if_needed(
    replay_store_path: Path,
    proposal: Dict[str, Any],
    decision: str,
    intent_meta: Dict[str, Any],
    decision_hash: str,
) -> None:
    if decision != "ACCEPT" or not intent_meta.get("intent_verified"):
        return
    nonce = intent_meta.get("intent_nonce")
    if not isinstance(nonce, str) or not nonce:
        return
    record_nonce(
        replay_store_path,
        nonce,
        human_intent_id=intent_meta.get("intent_envelope_id"),
        agent_id=proposal.get("agent_id"),
        decision_hash=decision_hash,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("proposal")
    parser.add_argument("--policy")
    parser.add_argument("--intent-envelope")
    parser.add_argument("--require-intent-envelope", action="store_true")
    parser.add_argument("--replay-store-path", default=str(DEFAULT_REPLAY_STORE_PATH))
    args = parser.parse_args()

    proposal_path = Path(args.proposal)
    policy_path = Path(args.policy) if args.policy else proposal_path.parent / "payment_policy.json"

    proposal = load_json(proposal_path)
    policy = load_json(policy_path)
    audit_path = Path(".proofpath/audit.jsonl")
    replay_store_path = Path(args.replay_store_path)
    envelope_ref = args.intent_envelope or proposal.get("intent_envelope")
    envelope = None
    if envelope_ref:
        try:
            envelope = load_json(Path(envelope_ref))
        except FileNotFoundError:
            decision, reason = "BLOCK", "MISSING_INTENT_ENVELOPE"
            append_audit(audit_path, proposal, decision, reason, intent_load_error_meta("missing"))
            print(json.dumps({"decision": decision, "reason": reason}, separators=(",", ":")))
            return 2
        except (json.JSONDecodeError, OSError, ValueError):
            decision, reason = "BLOCK", "INVALID_INTENT_SIGNATURE"
            append_audit(audit_path, proposal, decision, reason, intent_load_error_meta("malformed"))
            print(json.dumps({"decision": decision, "reason": reason}, separators=(",", ":")))
            return 2

    decision, reason, intent_meta = decide(
        proposal,
        policy,
        envelope,
        args.require_intent_envelope,
        audit_path,
        replay_store_path,
    )
    append_audit(audit_path, proposal, decision, reason, intent_meta)
    audit_hash = get_previous_hash(audit_path)
    persist_accepted_nonce_if_needed(replay_store_path, proposal, decision, intent_meta, audit_hash)

    print(json.dumps({"decision": decision, "reason": reason}, separators=(",", ":")))
    return 0 if decision == "ACCEPT" else 2 if decision == "BLOCK" else 3


if __name__ == "__main__":
    raise SystemExit(main())