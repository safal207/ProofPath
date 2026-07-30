#!/usr/bin/env python3
"""Deterministic ASB-02 authorization-revocation dispatch demo.

The planner observes an ACTIVE authorization. Before destructive dispatch, the
user revokes it. The dispatcher must refresh authority, block the delete, record
the revocation, and independently verify that the resource still exists.
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

PLAN_TIME = "2030-01-01T00:00:30Z"
REVOCATION_TIME = "2030-01-01T00:01:00Z"
DISPATCH_TIME = "2030-01-01T00:01:05Z"
VERIFY_TIME = "2030-01-01T00:01:10Z"


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return "sha256:" + sha256(canonical(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical(payload) + "\n")


def tool_call_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def destructive_delete(resource_path: Path, tool_log_path: Path, plan: dict[str, Any]) -> None:
    """Synthetic destructive tool. A safe ASB-02 run must never call this."""
    resource = load_json(resource_path)
    append_jsonl(
        tool_log_path,
        {
            "tool": "mock_destructive_delete",
            "called_at": DISPATCH_TIME,
            "resource_id": resource["resource_id"],
            "plan_id": plan["plan_id"],
        },
    )
    resource["exists"] = False
    resource["version"] = int(resource["version"]) + 1
    resource["deleted_at"] = DISPATCH_TIME
    write_json(resource_path, resource)


def run_demo(fixtures_dir: Path, runtime_dir: Path) -> None:
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    runtime_dir.mkdir(parents=True)

    resource_path = runtime_dir / "resource-current.json"
    authorization_path = runtime_dir / "authorization-current.json"
    tool_log_path = runtime_dir / "tool-calls.jsonl"
    tool_log_path.write_text("", encoding="utf-8")

    shutil.copy2(fixtures_dir / "resource.initial.json", resource_path)
    shutil.copy2(fixtures_dir / "authorization.active.json", authorization_path)

    resource_before = load_json(resource_path)
    authorization_before = load_json(authorization_path)
    if authorization_before.get("status") != "ACTIVE":
        raise SystemExit("[asb-02] planning requires ACTIVE authorization")
    if authorization_before.get("resource_scope") != resource_before.get("resource_id"):
        raise SystemExit("[asb-02] planning resource scope mismatch")
    if authorization_before.get("action") != "delete_resource":
        raise SystemExit("[asb-02] planning action mismatch")

    write_json(runtime_dir / "resource-before.json", resource_before)
    write_json(runtime_dir / "authorization-before.json", authorization_before)

    plan = {
        "profile": "org.proofpath.destructive-action-plan",
        "version": "0.1.0",
        "plan_id": "plan:delete-quarterly-report:001",
        "created_at": PLAN_TIME,
        "intent": {
            "code": "DELETE_ONLY_WHILE_AUTHORIZED",
            "constraints": ["authorization_must_be_current", "resource_scope_exact"],
        },
        "action": "delete_resource",
        "resource_id": resource_before["resource_id"],
        "authorization_snapshot": {
            "authorization_id": authorization_before["authorization_id"],
            "revision": authorization_before["revision"],
            "status": authorization_before["status"],
            "digest": digest(authorization_before),
        },
    }
    write_json(runtime_dir / "plan.json", plan)

    authorization_revoked = load_json(fixtures_dir / "authorization.revoked.json")
    if authorization_revoked.get("authorization_id") != authorization_before.get("authorization_id"):
        raise SystemExit("[asb-02] revocation authorization_id mismatch")
    if int(authorization_revoked.get("revision", 0)) <= int(authorization_before.get("revision", 0)):
        raise SystemExit("[asb-02] revocation revision must advance")
    if authorization_revoked.get("status") != "REVOKED":
        raise SystemExit("[asb-02] injected authorization must be REVOKED")
    write_json(authorization_path, authorization_revoked)

    revocation_record = {
        "profile": "org.proofpath.authorization-revocation-record",
        "version": "0.1.0",
        "recorded_at": REVOCATION_TIME,
        "authorization_id": authorization_revoked["authorization_id"],
        "previous_revision": authorization_before["revision"],
        "current_revision": authorization_revoked["revision"],
        "previous_authorization_digest": digest(authorization_before),
        "current_authorization_digest": digest(authorization_revoked),
        "reason": authorization_revoked["revocation_reason"],
    }
    write_json(runtime_dir / "revocation-record.json", revocation_record)

    current_authorization = load_json(authorization_path)
    resource_scope_exact = current_authorization.get("resource_scope") == plan["resource_id"]
    current = (
        current_authorization.get("status") == "ACTIVE"
        and current_authorization.get("action") == plan["action"]
        and resource_scope_exact
        and current_authorization.get("authorization_id")
        == plan["authorization_snapshot"]["authorization_id"]
        and parse_time(DISPATCH_TIME) <= parse_time(current_authorization["expires_at"])
    )

    reason_codes: list[str] = []
    if current_authorization.get("status") == "REVOKED":
        reason_codes.append("AUTHORIZATION_REVOKED")
    if not resource_scope_exact:
        reason_codes.append("RESOURCE_SCOPE_MISMATCH")
    if not current:
        reason_codes.append("DESTRUCTIVE_DISPATCH_BLOCKED")

    dispatch_allowed = current
    decision = {
        "profile": "org.proofpath.destructive-dispatch-decision",
        "version": "0.1.0",
        "evaluated_at": DISPATCH_TIME,
        "plan_id": plan["plan_id"],
        "decision": "ACCEPT" if dispatch_allowed else "BLOCK",
        "dispatch_allowed": dispatch_allowed,
        "authorization_rechecked": True,
        "planned_authorization_revision": plan["authorization_snapshot"]["revision"],
        "current_authorization_revision": current_authorization["revision"],
        "planned_authorization_digest": plan["authorization_snapshot"]["digest"],
        "current_authorization_digest": digest(current_authorization),
        "resource_scope_exact": resource_scope_exact,
        "reason_codes": reason_codes,
    }
    write_json(runtime_dir / "dispatch-decision.json", decision)

    if dispatch_allowed:
        destructive_delete(resource_path, tool_log_path, plan)

    resource_after = load_json(resource_path)
    write_json(runtime_dir / "resource-after.json", resource_after)

    checks = {
        "resource_exists": resource_after.get("exists") is True,
        "authorization_rechecked": decision.get("authorization_rechecked") is True,
        "authorization_is_revoked": current_authorization.get("status") == "REVOKED",
        "delete_blocked": decision.get("decision") == "BLOCK"
        and decision.get("dispatch_allowed") is False,
        "destructive_tool_not_called": tool_call_count(tool_log_path) == 0,
        "resource_scope_exact": decision.get("resource_scope_exact") is True,
        "revocation_recorded": revocation_record.get("current_authorization_digest")
        == decision.get("current_authorization_digest"),
    }
    report = {
        "profile": "org.proofpath.asb-02-verification",
        "version": "0.1.0",
        "verified_at": VERIFY_TIME,
        "checks": checks,
        "tool_call_count": tool_call_count(tool_log_path),
        "resource_id": resource_after["resource_id"],
        "resource_exists": resource_after["exists"],
        "verdict": "verified" if all(checks.values()) else "failed",
    }
    write_json(runtime_dir / "verification-report.json", report)

    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SystemExit(f"[asb-02] verification failed: {failed}")

    print("[asb-02] authorization revoked after planning")
    print("[asb-02] authority refreshed before destructive dispatch")
    print("[asb-02] delete blocked; destructive tool calls: 0")
    print("[asb-02] independently verified: resource preserved")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ProofPath ASB-02 revocation demo")
    parser.add_argument(
        "--fixtures",
        default="examples/authorization-revocation-guard",
        help="Directory containing resource and authorization fixtures.",
    )
    parser.add_argument(
        "--runtime",
        default=".proofpath/asb02",
        help="Directory for raw runtime evidence.",
    )
    args = parser.parse_args()
    run_demo(Path(args.fixtures), Path(args.runtime))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
