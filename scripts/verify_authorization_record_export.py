#!/usr/bin/env python3
"""Independently verify ProofPath authorization export semantics."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

FIXTURE = Path("conformance/authorization-record-export-v0.1.json")
REPORT_CONTEXT = Path(
    "conformance/authorization-record-report-context-v0.1.json"
)
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
SHA256_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
DECISIONS = {"ACCEPT", "HOLD", "BLOCK", "REJECT"}
CONSUMPTION = {"UNCONSUMED", "CONSUMED", "UNKNOWN"}
CONTINUATIONS = {
    "NOT_REQUIRED", "AWAITING_APPROVAL",
    "REQUIRES_REVALIDATION", "RESOLVED",
}
INTRINSIC_STATES = {
    "ACTIVE", "PENDING_APPROVAL", "EXPIRED", "CONSUMED",
    "BLOCKED", "REJECTED", "INVALID",
}
EXECUTION_STATUSES = {"EXECUTED", "BLOCKED", "ERRORED", "REFUSED"}
JOINS = {"MATCH", "MATCH_WITH_INTEGRITY_FAILURE", "HISTORICAL_ONLY"}


class VerificationError(ValueError):
    pass


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot load {path}: {error}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"{path} must contain an object")
    return value


def exact(value: dict[str, Any], keys: set[str], label: str) -> None:
    if set(value) != keys:
        raise VerificationError(
            f"{label} must contain exactly {sorted(keys)}"
        )


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise VerificationError(f"{label} must be a non-empty string")
    return value


def strings(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
        or len(set(value)) != len(value)
    ):
        raise VerificationError(f"{label} must be a unique string array")
    return value


def sha(value: Any, label: str) -> str:
    value = text(value, label)
    if SHA256_REF.fullmatch(value) is None:
        raise VerificationError(f"{label} must be sha256:<64 lowercase hex>")
    return value


def time_value(value: Any, label: str) -> datetime:
    value = text(value, label)
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise VerificationError(f"{label} must be ISO-8601") from error
    if result.tzinfo is None:
        raise VerificationError(f"{label} must include a timezone")
    return result


def canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def build_record(case: dict[str, Any]) -> dict[str, Any]:
    case_id = text(case.get("case_id"), "case_id")
    exact(case, {"case_id", "input", "expected", "handoff"}, case_id)
    data = case.get("input")
    if not isinstance(data, dict):
        raise VerificationError(f"{case_id}.input must be an object")
    exact(
        data,
        {
            "transition_id", "subject_id", "action_context",
            "binding_context", "decision_context",
        },
        f"{case_id}.input",
    )
    action = data.get("action_context")
    binding = data.get("binding_context")
    decision = data.get("decision_context")
    if not all(isinstance(v, dict) for v in (action, binding, decision)):
        raise VerificationError(f"{case_id} contexts must be objects")
    exact(
        action,
        {"caller_id", "intent_id", "causal_parent", "scope", "reversibility"},
        f"{case_id}.action_context",
    )
    exact(
        binding,
        {
            "request_method", "request_target", "arguments_digest",
            "policy_ref", "recipient_scope", "budget_scope", "approval_ref",
        },
        f"{case_id}.binding_context",
    )
    exact(
        decision,
        {
            "decision", "reason_codes", "issued_at", "expires_at",
            "consumption_state", "continuation_state", "current_state",
            "policy_ref", "proofpath_evidence_refs",
        },
        f"{case_id}.decision_context",
    )
    for key in ("caller_id", "intent_id", "causal_parent", "scope"):
        text(action.get(key), f"{case_id}.{key}")
    if action.get("reversibility") not in {"reversible", "irreversible"}:
        raise VerificationError(f"{case_id}.reversibility is invalid")
    for key in (
        "request_method", "request_target", "policy_ref",
        "recipient_scope", "budget_scope",
    ):
        text(binding.get(key), f"{case_id}.{key}")
    sha(binding.get("arguments_digest"), f"{case_id}.arguments_digest")
    approval = binding.get("approval_ref")
    if approval is not None:
        text(approval, f"{case_id}.approval_ref")

    decision_value = decision.get("decision")
    if decision_value not in DECISIONS:
        raise VerificationError(f"{case_id}.decision is invalid")
    reasons = strings(decision.get("reason_codes"), f"{case_id}.reason_codes")
    time_value(decision.get("issued_at"), f"{case_id}.issued_at")
    if decision.get("expires_at") is not None:
        time_value(decision["expires_at"], f"{case_id}.expires_at")
    if decision.get("consumption_state") not in CONSUMPTION:
        raise VerificationError(f"{case_id}.consumption_state is invalid")
    if decision.get("continuation_state") not in CONTINUATIONS:
        raise VerificationError(f"{case_id}.continuation_state is invalid")
    if decision.get("current_state") not in INTRINSIC_STATES:
        raise VerificationError(f"{case_id}.current_state is not intrinsic")
    if binding["policy_ref"] != decision.get("policy_ref"):
        raise VerificationError(f"{case_id} policy_ref drift")
    if decision_value == "HOLD":
        if decision["continuation_state"] not in {
            "AWAITING_APPROVAL", "REQUIRES_REVALIDATION",
        }:
            raise VerificationError(f"{case_id} HOLD requires continuation")
    elif decision["continuation_state"] == "AWAITING_APPROVAL":
        raise VerificationError(f"{case_id} non-HOLD awaits approval")
    if (
        decision_value == "ACCEPT"
        and action["reversibility"] == "irreversible"
        and approval is None
    ):
        raise VerificationError(
            f"{case_id} irreversible ACCEPT lacks approval"
        )

    return {
        "schema": AUTH_SCHEMA,
        "profile": EXPORT_PROFILE,
        "transition_id": text(
            data.get("transition_id"), f"{case_id}.transition_id"
        ),
        "subject_id": text(
            data.get("subject_id"), f"{case_id}.subject_id"
        ),
        "action_identity_profile": ACTION_PROFILE,
        "action_identity_digest": digest(
            {"profile_id": ACTION_PROFILE, **action}
        ),
        "binding_profile": BINDING_PROFILE,
        "binding_digest": digest(
            {"profile_id": BINDING_PROFILE, **binding}
        ),
        "decision": decision_value,
        "reason_codes": reasons,
        "issued_at": decision["issued_at"],
        "expires_at": decision["expires_at"],
        "consumption_state": decision["consumption_state"],
        "continuation_state": decision["continuation_state"],
        "current_state": decision["current_state"],
        "policy_ref": decision["policy_ref"],
        "proofpath_evidence_refs": strings(
            decision.get("proofpath_evidence_refs"),
            f"{case_id}.proofpath_evidence_refs",
        ),
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
    expires = record.get("expires_at")
    if expires is not None and reported_at > time_value(
        expires, "expires_at"
    ):
        return "EXPIRED_AT_REPORT"
    return state


def verify_handoff(
    case_id: str,
    source: Any,
    record: dict[str, Any],
    authorization_ref: str,
    reported_at: datetime | None,
    evaluated_state: str,
) -> None:
    if source is None:
        if reported_at is not None:
            raise VerificationError(f"{case_id} has unused report context")
        return
    if not isinstance(source, dict):
        raise VerificationError(f"{case_id}.handoff must be an object")
    if not {"observation", "expected_join"}.issubset(source):
        raise VerificationError(f"{case_id}.handoff is incomplete")
    if not set(source).issubset(
        {"observation", "expected_join", "response_integrity"}
    ):
        raise VerificationError(f"{case_id}.handoff has unknown fields")
    if reported_at is None:
        raise VerificationError(f"{case_id} lacks report context")
    observed = source.get("observation")
    if not isinstance(observed, dict):
        raise VerificationError(f"{case_id}.observation must be an object")
    exact(
        observed,
        {"execution_status", "observed_at", "result_digest", "issuer"},
        f"{case_id}.observation",
    )
    if observed.get("execution_status") not in EXECUTION_STATUSES:
        raise VerificationError(f"{case_id}.execution_status is invalid")
    observed_at = time_value(
        observed.get("observed_at"), f"{case_id}.observed_at"
    )
    if observed_at > reported_at:
        raise VerificationError(f"{case_id} observation follows report")
    issued_at = time_value(record["issued_at"], f"{case_id}.issued_at")
    expires_at = (
        None
        if record["expires_at"] is None
        else time_value(record["expires_at"], f"{case_id}.expires_at")
    )
    if observed_at < issued_at:
        raise VerificationError(f"{case_id} observation predates authority")
    if observed["execution_status"] == "EXECUTED":
        if record["decision"] != "ACCEPT":
            raise VerificationError(f"{case_id} executed without ACCEPT")
        if expires_at is not None and observed_at > expires_at:
            raise VerificationError(f"{case_id} executed after expiry")

    observation = {
        "schema": OBS_SCHEMA,
        "transition_id": record["transition_id"],
        "subject_id": record["subject_id"],
        "authorization_ref": authorization_ref,
        "action_identity_digest": record["action_identity_digest"],
        "binding_digest": record["binding_digest"],
        "execution_status": observed["execution_status"],
        "observed_at": observed["observed_at"],
        "result_digest": sha(
            observed.get("result_digest"), f"{case_id}.result_digest"
        ),
        "issuer": text(observed.get("issuer"), f"{case_id}.issuer"),
    }
    observation_ref = digest(observation)

    integrity_source = source.get("response_integrity")
    integrity_verdict = None
    if integrity_source is not None:
        if not isinstance(integrity_source, dict):
            raise VerificationError(
                f"{case_id}.response_integrity must be an object"
            )
        exact(
            integrity_source,
            {"overall_verdict", "verifier", "claim_boundary"},
            f"{case_id}.response_integrity",
        )
        integrity = {
            "schema": INTEGRITY_SCHEMA,
            "transition_id": record["transition_id"],
            "subject_id": record["subject_id"],
            "authorization_ref": authorization_ref,
            "observation_refs": [observation_ref],
            "overall_verdict": text(
                integrity_source.get("overall_verdict"),
                f"{case_id}.overall_verdict",
            ),
            "verifier": text(
                integrity_source.get("verifier"), f"{case_id}.verifier"
            ),
            "claim_boundary": text(
                integrity_source.get("claim_boundary"),
                f"{case_id}.claim_boundary",
            ),
        }
        digest(integrity)
        integrity_verdict = integrity["overall_verdict"]

    if evaluated_state == "EXPIRED_AT_REPORT":
        derived_join = "HISTORICAL_ONLY"
    elif integrity_verdict is not None and integrity_verdict != "VERIFIED":
        derived_join = "MATCH_WITH_INTEGRITY_FAILURE"
    else:
        derived_join = "MATCH"
    if source.get("expected_join") not in JOINS:
        raise VerificationError(f"{case_id}.expected_join is invalid")
    if source["expected_join"] != derived_join:
        raise VerificationError(
            f"{case_id} expected_join mismatch: "
            f"{source['expected_join']} != {derived_join}"
        )


def verify_case(
    case: dict[str, Any], report_cases: dict[str, Any]
) -> None:
    case_id = text(case.get("case_id"), "case_id")
    record = build_record(case)
    authorization_ref = digest(record)
    expected = case.get("expected")
    if not isinstance(expected, dict):
        raise VerificationError(f"{case_id}.expected must be an object")
    exact(
        expected,
        {
            "execution_allowed", "current_state",
            "authority_state_at_report",
            "expected_additional_side_effects", "authorization_ref",
        },
        f"{case_id}.expected",
    )
    if sha(
        expected.get("authorization_ref"),
        f"{case_id}.expected.authorization_ref",
    ) != authorization_ref:
        raise VerificationError(
            f"{case_id} authorization_ref mismatch: {authorization_ref}"
        )

    report_entry = report_cases.get(case_id)
    reported_at = None
    if report_entry is not None:
        if not isinstance(report_entry, dict):
            raise VerificationError(
                f"{case_id} report context must be an object"
            )
        exact(report_entry, {"reported_at"}, f"{case_id}.report")
        reported_at = time_value(
            report_entry["reported_at"], f"{case_id}.reported_at"
        )

    intrinsic = intrinsic_state(record)
    if record["current_state"] != intrinsic:
        raise VerificationError(
            f"{case_id} exported current_state mismatch: "
            f"{record['current_state']} != {intrinsic}"
        )
    if expected.get("current_state") != intrinsic:
        raise VerificationError(f"{case_id} expected current_state mismatch")
    evaluated = report_state(record, reported_at)
    if expected.get("authority_state_at_report") != evaluated:
        raise VerificationError(
            f"{case_id} authority_state_at_report mismatch"
        )

    allowed = (
        record["decision"] == "ACCEPT"
        and evaluated == "ACTIVE"
        and record["consumption_state"] == "UNCONSUMED"
    )
    if expected.get("execution_allowed") is not allowed:
        raise VerificationError(f"{case_id} execution_allowed mismatch")
    if expected.get("expected_additional_side_effects") != (
        1 if allowed else 0
    ):
        raise VerificationError(
            f"{case_id} side-effect expectation mismatch"
        )
    verify_handoff(
        case_id, case.get("handoff"), record, authorization_ref,
        reported_at, evaluated,
    )


def main() -> int:
    try:
        fixture = load(FIXTURE)
        report = load(REPORT_CONTEXT)
        if fixture.get("profile") != EXPORT_PROFILE:
            raise VerificationError("fixture profile mismatch")
        if report.get("profile") != REPORT_PROFILE:
            raise VerificationError("report profile mismatch")
        cases = fixture.get("cases")
        report_cases = report.get("cases")
        if not isinstance(cases, list) or not isinstance(report_cases, dict):
            raise VerificationError("fixture shape mismatch")

        seen: set[str] = set()
        for case in cases:
            if not isinstance(case, dict):
                raise VerificationError("case entry must be an object")
            case_id = text(case.get("case_id"), "case_id")
            if case_id in seen:
                raise VerificationError(f"duplicate case_id: {case_id}")
            seen.add(case_id)
            verify_case(case, report_cases)
            print(f"PASS {case_id}")
        unknown = set(report_cases) - seen
        if unknown:
            raise VerificationError(
                "unknown report cases: " + ", ".join(sorted(unknown))
            )
        print(
            f"\nIndependent ProofPath authorization semantics passed: "
            f"{len(cases)}"
        )
        return 0
    except (VerificationError, KeyError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
