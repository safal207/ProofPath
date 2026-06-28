#!/usr/bin/env python3
"""Reproduce ProofPath authorization exports and their evidence handoffs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

AUTH_SCHEMA = "org.proofpath.authorization-record.v0.1"
EXPORT_PROFILE = "org.proofpath.authorization-export.v0.1"
REPORT_PROFILE = "org.proofpath.authorization-report-context.v0.1"
ACTION_PROFILE = "org.liminal.trustworthy-transition.action-identity.v0.1"
BINDING_PROFILE = "org.liminal.trustworthy-transition.binding.v0.1"
OBS_SCHEMA = "org.liminal.trustworthy-transition.observation.v0.1"
INTEGRITY_SCHEMA = "org.liminal.trustworthy-transition.response-integrity.v0.1"
CLAIM_BOUNDARY = (
    "ProofPath proves its exported authorization decision and frozen context "
    "binding; it does not prove downstream execution, observation truth, or "
    "response honesty."
)
INTRINSIC_STATES = {
    "ACTIVE", "PENDING_APPROVAL", "EXPIRED", "CONSUMED",
    "BLOCKED", "REJECTED", "INVALID",
}


class ExportVerificationError(ValueError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExportVerificationError(f"cannot load {path}: {error}") from error
    if not isinstance(value, dict):
        raise ExportVerificationError(f"{path} must contain an object")
    return value


def timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ExportVerificationError(f"{label} must be a timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ExportVerificationError(f"{label} must be ISO-8601") from error
    if result.tzinfo is None:
        raise ExportVerificationError(f"{label} must include a timezone")
    return result


def record_for(case: dict[str, Any]) -> dict[str, Any]:
    case_id = case.get("case_id")
    data = case.get("input")
    if not isinstance(case_id, str) or not isinstance(data, dict):
        raise ExportVerificationError("invalid case")
    action = data.get("action_context")
    binding = data.get("binding_context")
    decision = data.get("decision_context")
    if not all(isinstance(v, dict) for v in (action, binding, decision)):
        raise ExportVerificationError(f"{case_id} contexts must be objects")
    current_state = decision.get("current_state")
    if current_state not in INTRINSIC_STATES:
        raise ExportVerificationError(
            f"{case_id}.current_state must be intrinsic"
        )
    return {
        "schema": AUTH_SCHEMA,
        "profile": EXPORT_PROFILE,
        "transition_id": data["transition_id"],
        "subject_id": data["subject_id"],
        "action_identity_profile": ACTION_PROFILE,
        "action_identity_digest": digest(
            {"profile_id": ACTION_PROFILE, **action}
        ),
        "binding_profile": BINDING_PROFILE,
        "binding_digest": digest(
            {"profile_id": BINDING_PROFILE, **binding}
        ),
        "decision": decision["decision"],
        "reason_codes": decision["reason_codes"],
        "issued_at": decision["issued_at"],
        "expires_at": decision["expires_at"],
        "consumption_state": decision["consumption_state"],
        "continuation_state": decision["continuation_state"],
        "current_state": current_state,
        "policy_ref": decision["policy_ref"],
        "proofpath_evidence_refs": decision["proofpath_evidence_refs"],
        "claim_boundary": CLAIM_BOUNDARY,
    }


def intrinsic_state(record: dict[str, Any]) -> str:
    if record["consumption_state"] == "CONSUMED":
        return "CONSUMED"
    if record["consumption_state"] == "UNKNOWN":
        return "INVALID"
    if record["decision"] == "HOLD":
        return "PENDING_APPROVAL"
    if record["decision"] == "REJECT":
        return "REJECTED"
    if record["decision"] == "BLOCK":
        return (
            "EXPIRED"
            if "INTENT_EXPIRED" in record["reason_codes"]
            else "BLOCKED"
        )
    return "ACTIVE"


def report_state(
    record: dict[str, Any], reported_at: datetime | None
) -> str:
    state = intrinsic_state(record)
    if state != "ACTIVE" or reported_at is None:
        return state
    expires_at = record.get("expires_at")
    if expires_at is not None and reported_at > timestamp(
        expires_at, "expires_at"
    ):
        return "EXPIRED_AT_REPORT"
    return state


def handoff_for(
    case: dict[str, Any],
    record: dict[str, Any],
    authorization_ref: str,
) -> dict[str, Any] | None:
    source = case.get("handoff")
    if source is None:
        return None
    if not isinstance(source, dict) or not isinstance(
        source.get("observation"), dict
    ):
        raise ExportVerificationError(
            f"{case['case_id']} handoff is invalid"
        )
    observed = source["observation"]
    observation = {
        "schema": OBS_SCHEMA,
        "transition_id": record["transition_id"],
        "subject_id": record["subject_id"],
        "authorization_ref": authorization_ref,
        "action_identity_digest": record["action_identity_digest"],
        "binding_digest": record["binding_digest"],
        "execution_status": observed["execution_status"],
        "observed_at": observed["observed_at"],
        "result_digest": observed["result_digest"],
        "issuer": observed["issuer"],
    }
    observation_ref = digest(observation)
    result: dict[str, Any] = {
        "observation_record": {
            "record": observation,
            "record_ref": observation_ref,
        },
        "expected_join": source["expected_join"],
    }
    integrity_source = source.get("response_integrity")
    if integrity_source is not None:
        integrity = {
            "schema": INTEGRITY_SCHEMA,
            "transition_id": record["transition_id"],
            "subject_id": record["subject_id"],
            "authorization_ref": authorization_ref,
            "observation_refs": [observation_ref],
            "overall_verdict": integrity_source["overall_verdict"],
            "verifier": integrity_source["verifier"],
            "claim_boundary": integrity_source["claim_boundary"],
        }
        result["response_integrity_record"] = {
            "record": integrity,
            "record_ref": digest(integrity),
        }
    return result


def verify_case(
    case: dict[str, Any], report_cases: dict[str, Any]
) -> dict[str, Any]:
    case_id = case["case_id"]
    expected = case.get("expected")
    if not isinstance(expected, dict):
        raise ExportVerificationError(f"{case_id}.expected is invalid")

    record = record_for(case)
    authorization_ref = digest(record)
    if authorization_ref != expected.get("authorization_ref"):
        raise ExportVerificationError(
            f"{case_id} authorization_ref mismatch: {authorization_ref}"
        )

    intrinsic = intrinsic_state(record)
    if record["current_state"] != intrinsic:
        raise ExportVerificationError(
            f"{case_id} intrinsic current_state mismatch"
        )
    if expected.get("current_state") != intrinsic:
        raise ExportVerificationError(
            f"{case_id} expected current_state mismatch"
        )

    entry = report_cases.get(case_id)
    reported_at = None
    if entry is not None:
        if not isinstance(entry, dict) or set(entry) != {"reported_at"}:
            raise ExportVerificationError(
                f"{case_id} report context is invalid"
            )
        reported_at = timestamp(
            entry["reported_at"], f"{case_id}.reported_at"
        )
    evaluated = report_state(record, reported_at)
    if expected.get("authority_state_at_report") != evaluated:
        raise ExportVerificationError(
            f"{case_id} authority_state_at_report mismatch"
        )

    allowed = (
        record["decision"] == "ACCEPT"
        and evaluated == "ACTIVE"
        and record["consumption_state"] == "UNCONSUMED"
    )
    if expected.get("execution_allowed") is not allowed:
        raise ExportVerificationError(
            f"{case_id} execution_allowed mismatch"
        )
    if expected.get("expected_additional_side_effects") != (
        1 if allowed else 0
    ):
        raise ExportVerificationError(
            f"{case_id} side-effect expectation mismatch"
        )

    handoff = handoff_for(case, record, authorization_ref)
    if handoff is not None and reported_at is None:
        raise ExportVerificationError(
            f"{case_id} handoff lacks report context"
        )
    return {
        "authorization_record": {
            "record": record,
            "canonical_bytes_utf8": canonical(record),
            "record_ref": authorization_ref,
        },
        "authority_state_at_report": evaluated,
        "handoff": handoff,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "fixture", nargs="?", type=Path,
        default=Path("conformance/authorization-record-export-v0.1.json"),
    )
    parser.add_argument(
        "--report-context", type=Path,
        default=Path(
            "conformance/authorization-record-report-context-v0.1.json"
        ),
    )
    parser.add_argument("--emit-case")
    args = parser.parse_args()
    try:
        fixture = load(args.fixture)
        report = load(args.report_context)
        if fixture.get("profile") != EXPORT_PROFILE:
            raise ExportVerificationError("fixture profile mismatch")
        if report.get("profile") != REPORT_PROFILE:
            raise ExportVerificationError("report profile mismatch")
        cases = fixture.get("cases")
        report_cases = report.get("cases")
        if not isinstance(cases, list) or not isinstance(report_cases, dict):
            raise ExportVerificationError("fixture shape mismatch")

        seen: set[str] = set()
        selected = None
        for case in cases:
            case_id = case.get("case_id")
            if not isinstance(case_id, str) or case_id in seen:
                raise ExportVerificationError(
                    f"invalid or duplicate case_id: {case_id}"
                )
            seen.add(case_id)
            derived = verify_case(case, report_cases)
            if args.emit_case == case_id:
                selected = derived
            record = derived["authorization_record"]["record"]
            print(
                f"PASS {case_id} -> {record['decision']} / "
                f"{record['current_state']} / "
                f"{derived['authority_state_at_report']}"
            )

        unknown = set(report_cases) - seen
        if unknown:
            raise ExportVerificationError(
                "unknown report cases: " + ", ".join(sorted(unknown))
            )
        if args.emit_case:
            if selected is None:
                raise ExportVerificationError(
                    f"unknown case_id: {args.emit_case}"
                )
            print(json.dumps(selected, ensure_ascii=False, indent=2))
        print(
            f"\nProofPath authorization export fixtures passed: {len(cases)}"
        )
        return 0
    except (ExportVerificationError, KeyError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
