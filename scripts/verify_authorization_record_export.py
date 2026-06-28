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
INTEGRITY_SCHEMA = (
    "org.liminal.trustworthy-transition.response-integrity.v0.1"
)
CLAIM_BOUNDARY = (
    "ProofPath proves its exported authorization decision and frozen context "
    "binding; it does not prove downstream execution, observation truth, or "
    "response honesty."
)
SHA256_REF = re.compile(r"^sha256:[0-9a-f]{64}$")
DECISIONS = {"ACCEPT", "HOLD", "BLOCK", "REJECT"}
CONSUMPTION_STATES = {"UNCONSUMED", "CONSUMED", "UNKNOWN"}
CONTINUATION_STATES = {
    "NOT_REQUIRED",
    "AWAITING_APPROVAL",
    "REQUIRES_REVALIDATION",
    "RESOLVED",
}
EXECUTION_STATUSES = {"EXECUTED", "BLOCKED", "ERRORED", "REFUSED"}
JOIN_RESULTS = {
    "MATCH",
    "MATCH_WITH_INTEGRITY_FAILURE",
    "HISTORICAL_ONLY",
}


class VerificationError(ValueError):
    pass


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VerificationError(f"cannot load {path}: {error}") from error
    if not isinstance(value, dict):
        raise VerificationError(f"{path} must contain a JSON object")
    return value


def exact_keys(value: dict[str, Any], keys: set[str], label: str) -> None:
    if set(value) != keys:
        raise VerificationError(f"{label} must contain exactly {sorted(keys)}")


def non_empty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise VerificationError(f"{label} must be a non-empty string")
    return value


def string_list(value: Any, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
        or len(set(value)) != len(value)
    ):
        raise VerificationError(f"{label} must be a unique string array")
    return value


def sha_ref(value: Any, label: str) -> str:
    value = non_empty(value, label)
    if SHA256_REF.fullmatch(value) is None:
        raise VerificationError(f"{label} must be sha256:<64 lowercase hex>")
    return value


def timestamp(value: Any, label: str) -> datetime:
    value = non_empty(value, label)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise VerificationError(f"{label} must be ISO-8601") from error
    if parsed.tzinfo is None:
        raise VerificationError(f"{label} must include a timezone")
    return parsed


def canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value).encode()).hexdigest()


def build_record(case: dict[str, Any]) -> dict[str, Any]:
    case_id = non_empty(case.get("case_id"), "case_id")
    exact_keys(case, {"case_id", "input", "expected", "handoff"}, case_id)

    data = case.get("input")
    if not isinstance(data, dict):
        raise VerificationError(f"{case_id}.input must be an object")
    exact_keys(
        data,
        {
            "transition_id",
            "subject_id",
            "action_context",
            "binding_context",
            "decision_context",
        },
        f"{case_id}.input",
    )

    action = data.get("action_context")
    binding = data.get("binding_context")
    decision = data.get("decision_context")
    if not all(isinstance(value, dict) for value in (action, binding, decision)):
        raise VerificationError(f"{case_id} contexts must be objects")

    exact_keys(
        action,
        {"caller_id", "intent_id", "causal_parent", "scope", "reversibility"},
        f"{case_id}.action_context",
    )
    exact_keys(
        binding,
        {
            "request_method",
            "request_target",
            "arguments_digest",
            "policy_ref",
            "recipient_scope",
            "budget_scope",
            "approval_ref",
        },
        f"{case_id}.binding_context",
    )
    exact_keys(
        decision,
        {
            "decision",
            "reason_codes",
            "issued_at",
            "expires_at",
            "consumption_state",
            "continuation_state",
            "current_state",
            "policy_ref",
            "proofpath_evidence_refs",
        },
        f"{case_id}.decision_context",
    )

    for key in ("caller_id", "intent_id", "causal_parent", "scope"):
        non_empty(action.get(key), f"{case_id}.{key}")
    if action.get("reversibility") not in {"reversible", "irreversible"}:
        raise VerificationError(f"{case_id}.reversibility is invalid")

    for key in (
        "request_method",
        "request_target",
        "policy_ref",
        "recipient_scope",
        "budget_scope",
    ):
        non_empty(binding.get(key), f"{case_id}.{key}")
    sha_ref(binding.get("arguments_digest"), f"{case_id}.arguments_digest")
    approval_ref = binding.get("approval_ref")
    if approval_ref is not None:
        non_empty(approval_ref, f"{case_id}.approval_ref")

    decision_value = decision.get("decision")
    if decision_value not in DECISIONS:
        raise VerificationError(f"{case_id}.decision is invalid")
    reason_codes = string_list(
        decision.get("reason_codes"), f"{case_id}.reason_codes"
    )
    issued_at = timestamp(decision.get("issued_at"), f"{case_id}.issued_at")
    expires_at = (
        None
        if decision.get("expires_at") is None
        else timestamp(decision.get("expires_at"), f"{case_id}.expires_at")
    )
    consumption = decision.get("consumption_state")
    continuation = decision.get("continuation_state")
    if consumption not in CONSUMPTION_STATES:
        raise VerificationError(f"{case_id}.consumption_state is invalid")
    if continuation not in CONTINUATION_STATES:
        raise VerificationError(f"{case_id}.continuation_state is invalid")
    if binding["policy_ref"] != decision.get("policy_ref"):
        raise VerificationError(f"{case_id} policy_ref drift")

    if decision_value == "HOLD":
        if continuation not in {"AWAITING_APPROVAL", "REQUIRES_REVALIDATION"}:
            raise VerificationError(f"{case_id} HOLD requires continuation")
    elif continuation == "AWAITING_APPROVAL":
        raise VerificationError(f"{case_id} non-HOLD awaits approval")

    if (
        decision_value == "ACCEPT"
        and action["reversibility"] == "irreversible"
        and approval_ref is None
    ):
        raise VerificationError(
            f"{case_id} irreversible ACCEPT lacks approval"
        )

    del reason_codes, issued_at, expires_at
    return {
        "schema": AUTH_SCHEMA,
        "profile": EXPORT_PROFILE,
        "transition_id": non_empty(
            data.get("transition_id"), f"{case_id}.transition_id"
        ),
        "subject_id": non_empty(
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
        "reason_codes": decision["reason_codes"],
        "issued_at": decision["issued_at"],
        "expires_at": decision["expires_at"],
        "consumption_state": consumption,
        "continuation_state": continuation,
        "current_state": non_empty(
            decision.get("current_state"), f"{case_id}.current_state"
        ),
        "policy_ref": decision["policy_ref"],
        "proofpath_evidence_refs": string_list(
            decision.get("proofpath_evidence_refs"),
            f"{case_id}.proofpath_evidence_refs",
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def derive_state(
    record: dict[str, Any], reported_at: datetime | None
) -> str:
    if record["consumption_state"] == "CONSUMED":
        return "CONSUMED"
    if record["consumption_state"] == "UNKNOWN":
        return "INVALID"
    if record["decision"] == "HOLD":
        return "PENDING_APPROVAL"
    if record["decision"] == "REJECT":
        return "REJECTED"
    if record["decision"] == "BLOCK":
        if "INTENT_EXPIRED" in record["reason_codes"]:
            return "EXPIRED"
        return "BLOCKED"

    expires_at = (
        None
        if record["expires_at"] is None
        else timestamp(record["expires_at"], "expires_at")
    )
    if reported_at is not None and expires_at is not None:
        if reported_at > expires_at:
            return "EXPIRED_AT_REPORT"
    return "ACTIVE"


def verify_handoff(
    case_id: str,
    handoff: Any,
    record: dict[str, Any],
    auth_ref: str,
    reported_at: datetime | None,
    state: str,
) -> None:
    if handoff is None:
        if reported_at is not None:
            raise VerificationError(f"{case_id} has unused report context")
        return
    if not isinstance(handoff, dict):
        raise VerificationError(f"{case_id}.handoff must be an object")
    allowed = {"observation", "expected_join", "response_integrity"}
    if not {"observation", "expected_join"}.issubset(handoff):
        raise VerificationError(f"{case_id}.handoff is incomplete")
    if not set(handoff).issubset(allowed):
        raise VerificationError(f"{case_id}.handoff has unknown fields")
    if reported_at is None:
        raise VerificationError(f"{case_id} lacks report context")

    observation_input = handoff.get("observation")
    if not isinstance(observation_input, dict):
        raise VerificationError(f"{case_id}.observation must be an object")
    exact_keys(
        observation_input,
        {"execution_status", "observed_at", "result_digest", "issuer"},
        f"{case_id}.observation",
    )
    execution_status = observation_input.get("execution_status")
    if execution_status not in EXECUTION_STATUSES:
        raise VerificationError(f"{case_id}.execution_status is invalid")
    observed_at = timestamp(
        observation_input.get("observed_at"), f"{case_id}.observed_at"
    )
    if observed_at > reported_at:
        raise VerificationError(f"{case_id} observation follows report")
    issued_at = timestamp(record["issued_at"], f"{case_id}.issued_at")
    expires_at = (
        None
        if record["expires_at"] is None
        else timestamp(record["expires_at"], f"{case_id}.expires_at")
    )
    if observed_at < issued_at:
        raise VerificationError(f"{case_id} observation predates authority")
    if execution_status == "EXECUTED":
        if record["decision"] != "ACCEPT":
            raise VerificationError(f"{case_id} executed without ACCEPT")
        if expires_at is not None and observed_at > expires_at:
            raise VerificationError(f"{case_id} executed after expiry")

    observation = {
        "schema": OBS_SCHEMA,
        "transition_id": record["transition_id"],
        "subject_id": record["subject_id"],
        "authorization_ref": auth_ref,
        "action_identity_digest": record["action_identity_digest"],
        "binding_digest": record["binding_digest"],
        "execution_status": execution_status,
        "observed_at": observation_input["observed_at"],
        "result_digest": sha_ref(
            observation_input.get("result_digest"),
            f"{case_id}.result_digest",
        ),
        "issuer": non_empty(
            observation_input.get("issuer"), f"{case_id}.issuer"
        ),
    }
    observation_ref = digest(observation)

    integrity_input = handoff.get("response_integrity")
    integrity_verdict = None
    if integrity_input is not None:
        if not isinstance(integrity_input, dict):
            raise VerificationError(
                f"{case_id}.response_integrity must be an object"
            )
        exact_keys(
            integrity_input,
            {"overall_verdict", "verifier", "claim_boundary"},
            f"{case_id}.response_integrity",
        )
        integrity = {
            "schema": INTEGRITY_SCHEMA,
            "transition_id": record["transition_id"],
            "subject_id": record["subject_id"],
            "authorization_ref": auth_ref,
            "observation_refs": [observation_ref],
            "overall_verdict": non_empty(
                integrity_input.get("overall_verdict"),
                f"{case_id}.overall_verdict",
            ),
            "verifier": non_empty(
                integrity_input.get("verifier"), f"{case_id}.verifier"
            ),
            "claim_boundary": non_empty(
                integrity_input.get("claim_boundary"),
                f"{case_id}.claim_boundary",
            ),
        }
        digest(integrity)
        integrity_verdict = integrity["overall_verdict"]

    if state == "EXPIRED_AT_REPORT":
        derived_join = "HISTORICAL_ONLY"
    elif integrity_verdict is not None and integrity_verdict != "VERIFIED":
        derived_join = "MATCH_WITH_INTEGRITY_FAILURE"
    else:
        derived_join = "MATCH"

    expected_join = handoff.get("expected_join")
    if expected_join not in JOIN_RESULTS:
        raise VerificationError(f"{case_id}.expected_join is invalid")
    if expected_join != derived_join:
        raise VerificationError(
            f"{case_id} expected_join mismatch: "
            f"{expected_join} != {derived_join}"
        )


def verify_case(
    case: dict[str, Any],
    report_cases: dict[str, Any],
) -> None:
    case_id = non_empty(case.get("case_id"), "case_id")
    record = build_record(case)
    auth_ref = digest(record)

    expected = case.get("expected")
    if not isinstance(expected, dict):
        raise VerificationError(f"{case_id}.expected must be an object")
    exact_keys(
        expected,
        {
            "execution_allowed",
            "current_state",
            "expected_additional_side_effects",
            "authorization_ref",
        },
        f"{case_id}.expected",
    )
    expected_ref = sha_ref(
        expected.get("authorization_ref"),
        f"{case_id}.expected.authorization_ref",
    )
    if auth_ref != expected_ref:
        raise VerificationError(
            f"{case_id} authorization_ref mismatch: {auth_ref}"
        )

    report_entry = report_cases.get(case_id)
    if report_entry is None:
        reported_at = None
    else:
        if not isinstance(report_entry, dict):
            raise VerificationError(
                f"{case_id} report context must be an object"
            )
        exact_keys(report_entry, {"reported_at"}, f"{case_id}.report")
        reported_at = timestamp(
            report_entry.get("reported_at"), f"{case_id}.reported_at"
        )

    state = derive_state(record, reported_at)
    if record["current_state"] != state:
        raise VerificationError(
            f"{case_id} exported current_state mismatch: "
            f"{record['current_state']} != {state}"
        )
    if expected.get("current_state") != state:
        raise VerificationError(
            f"{case_id} expected current_state mismatch"
        )

    execution_allowed = (
        record["decision"] == "ACCEPT"
        and state == "ACTIVE"
        and record["consumption_state"] == "UNCONSUMED"
    )
    if expected.get("execution_allowed") is not execution_allowed:
        raise VerificationError(
            f"{case_id} execution_allowed mismatch"
        )
    expected_effects = 1 if execution_allowed else 0
    if expected.get("expected_additional_side_effects") != expected_effects:
        raise VerificationError(
            f"{case_id} side-effect expectation mismatch"
        )

    verify_handoff(
        case_id,
        case.get("handoff"),
        record,
        auth_ref,
        reported_at,
        state,
    )


def main() -> int:
    try:
        fixture = load_object(FIXTURE)
        if fixture.get("profile") != EXPORT_PROFILE:
            raise VerificationError("fixture profile mismatch")
        cases = fixture.get("cases")
        if not isinstance(cases, list) or not cases:
            raise VerificationError("fixture cases must be non-empty")

        report_context = load_object(REPORT_CONTEXT)
        if report_context.get("profile") != REPORT_PROFILE:
            raise VerificationError("report context profile mismatch")
        report_cases = report_context.get("cases")
        if not isinstance(report_cases, dict):
            raise VerificationError("report context cases must be an object")

        seen: set[str] = set()
        for case in cases:
            if not isinstance(case, dict):
                raise VerificationError("case entry must be an object")
            case_id = non_empty(case.get("case_id"), "case_id")
            if case_id in seen:
                raise VerificationError(f"duplicate case_id: {case_id}")
            seen.add(case_id)
            verify_case(case, report_cases)
            print(f"PASS {case_id}")

        unknown_report_cases = set(report_cases) - seen
        if unknown_report_cases:
            raise VerificationError(
                "unknown report-context cases: "
                + ", ".join(sorted(unknown_report_cases))
            )

        print(
            f"\nIndependent ProofPath authorization semantics passed: "
            f"{len(cases)}"
        )
        return 0
    except VerificationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
