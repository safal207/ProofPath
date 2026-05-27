#!/usr/bin/env python3
"""Adapter: ProofPath Agent Payment Guard -> Mock Payment Rail.

Calls the ProofPath guard service with a payment proposal, then only forwards
to the mock payment rail if execution_allowed=true AND decision=ACCEPT.

Usage:
    python3 examples/agent-payment-guard/payment_guard_to_mock_rail_adapter.py \
        --guard-url http://127.0.0.1:18790 \
        --rail-url http://127.0.0.1:18791 \
        --proposal examples/agent-payment-guard/payment_proposal.valid_micro_payment.json \
        --intent-envelope examples/agent-payment-guard/intent_envelopes/intent.valid.json
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, Optional


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise SystemExit(f"HTTP {exc.code} from {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Connection failed to {url}: {exc.reason}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="ProofPath -> Mock Rail adapter")
    parser.add_argument("--guard-url", default="http://127.0.0.1:18790")
    parser.add_argument("--rail-url", default="http://127.0.0.1:18791")
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--intent-envelope", default=None)
    parser.add_argument("--mode", default="enforce")
    args = parser.parse_args()

    proposal = load_json(Path(args.proposal))
    envelope = load_json(Path(args.intent_envelope)) if args.intent_envelope else None

    eval_url = f"{args.guard_url.rstrip('/')}/v1/payment-proposals/evaluate"
    body: Dict[str, Any] = {"mode": args.mode, "proposal": proposal}
    if envelope is not None:
        body["intent_envelope"] = envelope

    print(f"[adapter] evaluating at {eval_url} ...")
    guard_resp = post_json(eval_url, body)
    print(f"[adapter] guard decision: {guard_resp['decision']} / {guard_resp.get('reason', '')}")
    print(f"[adapter] execution_allowed: {guard_resp['execution_allowed']}")

    if guard_resp["execution_allowed"] is True and guard_resp["decision"] == "ACCEPT":
        rail_url = f"{args.rail_url.rstrip('/')}/v1/mock-rail/execute"
        rail_body = {
            "agent_id": proposal.get("agent_id"),
            "asset": proposal.get("asset"),
            "amount": proposal.get("amount"),
            "recipient": proposal.get("recipient"),
            "proofpath_decision": guard_resp["decision"],
            "proofpath_audit_hash": guard_resp["audit_hash"],
        }
        print(f"[adapter] forwarding to mock rail at {rail_url} ...")
        rail_resp = post_json(rail_url, rail_body)
        print(f"[adapter] mock rail status: {rail_resp['status']}")
    else:
        print("[adapter] decision is not ACCEPT — did NOT call mock rail")

    print(json.dumps(guard_resp, separators=(",", ":")))
    return 0 if guard_resp["decision"] == "ACCEPT" else 2


if __name__ == "__main__":
    raise SystemExit(main())
