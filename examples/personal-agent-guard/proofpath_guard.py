#!/usr/bin/env python3
"""ProofPath Personal Agent Guard.

Local hook example for AI coding tools.
Reads JSON from stdin, checks command text against policy.json,
writes .proofpath/audit.jsonl, and prints an allow/deny decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def read_payload() -> Dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {"input": raw}
    return value if isinstance(value, dict) else {"input": value}


def extract_command(payload: Dict[str, Any]) -> str:
    tool_input = payload.get("tool_input") or payload.get("toolInput") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    for value in [
        payload.get("command"),
        payload.get("cmd"),
        payload.get("input"),
        tool_input.get("command"),
        tool_input.get("cmd"),
        tool_input.get("input"),
    ]:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return json.dumps(payload, sort_keys=True)


def find_rule(command: str, policy: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    command_lower = command.lower()
    for rule in policy.get("rules", []):
        for pattern in rule.get("match_contains", []):
            if str(pattern).lower() in command_lower:
                return rule
    return None


def approval_valid(scope: Optional[str], path: Path) -> bool:
    if not scope:
        return False
    approvals = load_json(path, {})
    item = approvals.get(scope)
    if not isinstance(item, dict):
        return False
    expires_at = item.get("expires_at")
    if not isinstance(expires_at, str):
        return False
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return expiry > datetime.now(timezone.utc)


def append_audit(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    material = json.dumps(record, sort_keys=True).encode("utf-8")
    record["hash"] = "sha256:" + hashlib.sha256(material).hexdigest()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def response(mode: str, decision: str, reason: str) -> Dict[str, Any]:
    if mode == "claude":
        if decision == "BLOCK":
            return {"permissionDecision": "deny", "permissionDecisionReason": reason}
        return {"permissionDecision": "allow"}
    if mode == "codex":
        if decision == "BLOCK":
            return {"decision": "deny", "reason": reason}
        return {"decision": "allow"}
    return {"decision": decision, "reason": reason}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default="examples/personal-agent-guard/policy.json")
    parser.add_argument("--mode", choices=["generic", "claude", "codex"], default="generic")
    args = parser.parse_args()

    policy = load_json(Path(args.policy), {})
    payload = read_payload()
    command = extract_command(payload)
    rule = find_rule(command, policy)

    decision = policy.get("default_decision", "ALLOW")
    reason = "DEFAULT_ALLOW"
    scope = None
    rule_id = None

    if rule:
        rule_id = rule.get("id")
        scope = rule.get("approval_scope")
        reason = str(rule.get("reason", "RULE_MATCHED"))
        if rule.get("decision") == "BLOCK_UNLESS_APPROVED":
            if approval_valid(scope, Path(policy.get("approval_file", ".proofpath/approvals.json"))):
                decision = "ALLOW"
                reason = "APPROVAL_PRESENT"
            else:
                decision = "BLOCK"
        else:
            decision = str(rule.get("decision", "BLOCK"))

    append_audit(
        Path(policy.get("audit_log", ".proofpath/audit.jsonl")),
        {
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "command": command,
            "decision": decision,
            "reason": reason,
            "rule_id": rule_id,
            "approval_scope": scope,
            "mode": args.mode,
        },
    )

    print(json.dumps(response(args.mode, decision, reason), sort_keys=True))
    return 2 if args.mode == "generic" and decision == "BLOCK" else 0


if __name__ == "__main__":
    raise SystemExit(main())
