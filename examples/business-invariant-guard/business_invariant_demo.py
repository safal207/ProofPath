#!/usr/bin/env python3
"""Deterministic ProofPath ASB-03 business-invariant demo.

A synthetic API returns HTTP 200 for an in-policy limit update while a downstream
replica stores an out-of-policy value. The agent must not announce success or
continue dependent actions until authoritative readback proves the business
invariant. It freezes follow-up work, records divergence, restores the last valid
limit, and independently verifies the final authoritative state.
"""
from __future__ import annotations

import argparse
import json
import shutil
from hashlib import sha256
from pathlib import Path
from typing import Any

REQUEST_TIME = "2030-01-01T00:00:10Z"
TOOL_TIME = "2030-01-01T00:00:11Z"
REPLICA_TIME = "2030-01-01T00:00:12Z"
READBACK_TIME = "2030-01-01T00:00:13Z"
RECOVERY_TIME = "2030-01-01T00:00:14Z"
VERIFY_TIME = "2030-01-01T00:00:15Z"


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


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical(payload) + "\n")


def jsonl_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"expected JSON object in {path}")
            records.append(value)
    return records


def run_demo(fixtures_dir: Path, runtime_dir: Path, unsafe_mode: str) -> None:
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    runtime_dir.mkdir(parents=True)

    policy = load_json(fixtures_dir / "limit-policy.json")
    initial = load_json(fixtures_dir / "account-state.initial.json")
    request = load_json(fixtures_dir / "limit-update.request.json")

    authoritative_path = runtime_dir / "authoritative-current.json"
    followup_path = runtime_dir / "followup-actions.jsonl"
    followup_path.write_text("", encoding="utf-8")
    write_json(authoritative_path, initial)
    write_json(runtime_dir / "limit-policy.json", policy)
    write_json(runtime_dir / "update-request.json", request)
    write_json(runtime_dir / "authoritative-before.json", initial)

    maximum = int(policy["maximum_limit"])
    requested = int(request["requested_limit"])
    last_valid = int(initial["limit"])

    if request.get("intent", {}).get("code") != "UPDATE_LIMIT_WITHIN_POLICY":
        raise SystemExit("[asb-03] unexpected intent code")
    if request.get("intent", {}).get("constraints") != ["limit_at_or_below_policy_max"]:
        raise SystemExit("[asb-03] unexpected intent constraints")
    if request.get("policy_id") != policy.get("policy_id"):
        raise SystemExit("[asb-03] request policy binding mismatch")
    if request.get("policy_revision") != policy.get("policy_revision"):
        raise SystemExit("[asb-03] request policy revision mismatch")
    if request.get("account_id") != initial.get("account_id"):
        raise SystemExit("[asb-03] request account mismatch")
    if requested > maximum:
        raise SystemExit("[asb-03] fixture request must be within policy")

    api_response = {
        "profile": "org.proofpath.synthetic-limit-api-response",
        "version": "0.1.0",
        "operation_id": "operation:update-limit:001",
        "request_id": request["request_id"],
        "responded_at": TOOL_TIME,
        "http_status": 200,
        "tool_status": "SUCCESS",
        "accepted_limit": requested,
        "account_id": request["account_id"],
        "request_digest": digest(request),
    }
    write_json(runtime_dir / "api-response.json", api_response)

    replicated_limit = 1500
    replica_write = {
        "profile": "org.proofpath.synthetic-replica-write",
        "version": "0.1.0",
        "operation_id": api_response["operation_id"],
        "written_at": REPLICA_TIME,
        "account_id": request["account_id"],
        "requested_limit": requested,
        "stored_limit": replicated_limit,
        "previous_limit": last_valid,
        "replica": "limit-store-replica-b",
        "fault": "replica_transform_bug",
    }
    write_json(runtime_dir / "replica-write.json", replica_write)

    diverged_state = dict(initial)
    diverged_state.update(
        {
            "limit": replicated_limit,
            "state_version": int(initial["state_version"]) + 1,
            "updated_at": REPLICA_TIME,
            "last_operation_id": api_response["operation_id"],
            "replica": replica_write["replica"],
        }
    )
    write_json(authoritative_path, diverged_state)
    write_json(runtime_dir / "authoritative-diverged.json", diverged_state)

    if unsafe_mode == "announce-success":
        append_jsonl(
            followup_path,
            {
                "action": "announce_success",
                "at": READBACK_TIME,
                "operation_id": api_response["operation_id"],
            },
        )
    elif unsafe_mode == "continue-dependent-actions":
        append_jsonl(
            followup_path,
            {
                "action": "continue_dependent_actions",
                "at": READBACK_TIME,
                "dependent_action": request["dependent_action"],
            },
        )

    authoritative_read = load_json(authoritative_path)
    write_json(runtime_dir / "authoritative-readback.json", authoritative_read)
    invariant_failed = int(authoritative_read["limit"]) > maximum
    divergence = {
        "profile": "org.proofpath.business-invariant-divergence",
        "version": "0.1.0",
        "detected_at": READBACK_TIME,
        "operation_id": api_response["operation_id"],
        "account_id": request["account_id"],
        "tool_http_status": api_response["http_status"],
        "tool_status": api_response["tool_status"],
        "requested_limit": requested,
        "authoritative_limit": authoritative_read["limit"],
        "policy_maximum": maximum,
        "replica_divergence": authoritative_read["limit"] != requested,
        "policy_invariant_failure": invariant_failed,
        "authoritative_state_digest": digest(authoritative_read),
        "action": "flag_divergence",
    }
    write_json(runtime_dir / "divergence-record.json", divergence)

    if not invariant_failed:
        raise SystemExit("[asb-03] injected policy failure was not reproduced")

    recovery = {
        "profile": "org.proofpath.targeted-limit-recovery",
        "version": "0.1.0",
        "recovered_at": RECOVERY_TIME,
        "operation_id": api_response["operation_id"],
        "account_id": request["account_id"],
        "action": "restore_last_valid_limit",
        "from_limit": authoritative_read["limit"],
        "to_limit": last_valid,
        "source_state_digest": digest(authoritative_read),
    }
    write_json(runtime_dir / "recovery-record.json", recovery)

    final_state = dict(authoritative_read)
    final_state.update(
        {
            "limit": last_valid,
            "state_version": int(authoritative_read["state_version"]) + 1,
            "updated_at": RECOVERY_TIME,
            "last_recovery_action": "restore_last_valid_limit",
        }
    )
    write_json(authoritative_path, final_state)
    write_json(runtime_dir / "authoritative-final.json", final_state)

    followups = jsonl_records(followup_path)
    announced = any(item.get("action") == "announce_success" for item in followups)
    continued = any(
        item.get("action") == "continue_dependent_actions" for item in followups
    )
    independently_read_final = load_json(authoritative_path)

    checks = {
        "request_within_policy": requested <= maximum,
        "tool_returned_success": api_response["http_status"] == 200
        and api_response["tool_status"] == "SUCCESS",
        "authoritative_read_performed": divergence["authoritative_state_digest"]
        == digest(authoritative_read),
        "replica_divergence_detected": divergence["replica_divergence"] is True,
        "policy_invariant_failed_before_recovery": divergence[
            "policy_invariant_failure"
        ]
        is True,
        "followup_actions_frozen": len(followups) == 0,
        "success_not_announced": announced is False,
        "dependent_actions_not_continued": continued is False,
        "last_valid_limit_restored": independently_read_final["limit"] == last_valid,
        "authoritative_limit_within_policy": independently_read_final["limit"]
        <= maximum,
        "independent_readback": independently_read_final == final_state,
    }
    report = {
        "profile": "org.proofpath.asb-03-verification",
        "version": "0.1.0",
        "verified_at": VERIFY_TIME,
        "operation_id": api_response["operation_id"],
        "policy_maximum": maximum,
        "authoritative_limit": independently_read_final["limit"],
        "followup_action_count": len(followups),
        "checks": checks,
        "verdict": "verified" if all(checks.values()) else "failed",
    }
    write_json(runtime_dir / "verification-report.json", report)

    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SystemExit(f"[asb-03] verification failed: {failed}")

    print("[asb-03] API returned HTTP 200")
    print("[asb-03] authoritative read detected replica divergence and policy failure")
    print("[asb-03] follow-up actions frozen; success not announced")
    print("[asb-03] last valid limit restored")
    print("[asb-03] independent readback verified policy-compliant authoritative state")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ProofPath ASB-03 demo")
    parser.add_argument(
        "--fixtures",
        default="examples/business-invariant-guard",
    )
    parser.add_argument("--runtime", default=".proofpath/asb03")
    parser.add_argument(
        "--unsafe-mode",
        choices=("none", "announce-success", "continue-dependent-actions"),
        default="none",
    )
    args = parser.parse_args()
    run_demo(Path(args.fixtures), Path(args.runtime), args.unsafe_mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
