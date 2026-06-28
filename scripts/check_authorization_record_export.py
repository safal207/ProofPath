#!/usr/bin/env python3
"""Verify and emit ProofPath provider-neutral authorization records.

The conformance vector has no floating-point values, so sorted minimal JSON is
equivalent to RFC 8785 JCS for the published input domain.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

AUTH_SCHEMA = "org.proofpath.authorization-record.v0.1"
EXPORT_PROFILE = "org.proofpath.authorization-export.v0.1"
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

DECISIONS = {"ACCEPT", "HOLD", "BLOCK", "REJECT"}
CONSUMPTION_STATES = {"UNCONSUMED", "CONSUMED", "UNKNOWN"}
CONTINUATION_STATES = {
    "NOT_REQUIRED",
    "AWAITING_APPROVAL",
    "REQUIRES_REVALIDATION",
    "RESOLVED",
}
CURRENT_STATES = {
    "ACTIVE",
    "PENDING_APPROVAL",
    "EXPIRED",
    "EXPIRED_AT_REPORT",
    "CONSUMED",
    "BLOCKED",
    "REJECTED",
    "INVALID",
}


class ExportVerificationError(ValueError):
    """Raised when a fixture or exported record violates the profile."""


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_uri(value: Any) -> str:
    canonical = canonical_json(value)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ExportVerificationError(f"cannot read {path}: {error}") from error
    except json.JSONDecodeError as error:
        raise ExportVerificationError(
            f"{path}: invalid JSON: {error.msg}"
        ) from error
    if not isinstance(payload, dict):
        raise ExportVerificationError(f"{path}: expected a JSON object")
    return payload


def require_non_empty_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ExportVerificationError(f"{label} must be a non-empty string")
    return value


def require_string_list(value: Any, *, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item for item in value)
        or len(set(value)) != len(value)
    ):
        raise ExportVerificationError(
            f"{label} must be a non-empty unique string array"
        )
    return value


def wrap_record(record: dict[str, Any]) -> dict[str, Any]:
    canonical = canonical_json(record)
    return {
        "record": record,
        "canonical_bytes_utf8": canonical,
        "record_ref": (
            "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        ),
    }


def build_export(case: dict[str, Any]) -> dict[str, Any]:
    case_id = require_non_empty_string(case.get("case_id"), label="case_id")
    input_data = case.get("input")
    if not isinstance(input_data, dict):
        raise ExportVerificationError(f"{case_id}.input must be an object")

    action = input_data.get("action_context")
    binding = input_data.get("binding_context")
    decision = input_data.get("decision_context")
    if not all(isinstance(value, dict) for value in (action, binding, decision)):
        raise ExportVerificationError(
            f"{case_id} requires action, binding, and decision contexts"
        )

    action_required = {
        "caller_id",
        "intent_id",
        "causal_parent",
        "scope",
        "reversibility",
    }
    binding_required = {
        "request_method",
        "request_target",
        "arguments_digest",
        "policy_ref",
        "recipient_scope",
        "budget_scope",
        "approval_ref",
    }
    if set(action) != action_required:
        raise ExportVerificationError(
            f"{case_id}.action_context must contain exactly "
            f"{sorted(action_required)}"
        )
    if set(binding) != binding_required:
        raise ExportVerificationError(
            f"{case_id}.binding_context must contain exactly "
            f"{sorted(binding_required)}"
        )

    decision_value = decision.get("decision")
    if decision_value not in DECISIONS:
        raise ExportVerificationError(
            f"{case_id}.decision must be one of {sorted(DECISIONS)}"
        )

    consumption_state = decision.get("consumption_state")
    continuation_state = decision.get("continuation_state")
    current_state = decision.get("current_state")
    if consumption_state not in CONSUMPTION_STATES:
        raise ExportVerificationError(
            f"{case_id}.consumption_state is invalid"
        )
    if continuation_state not in CONTINUATION_STATES:
        raise ExportVerificationError(
            f"{case_id}.continuation_state is invalid"
        )
    if current_state not in CURRENT_STATES:
        raise ExportVerificationError(f"{case_id}.current_state is invalid")

    action_preimage = {"profile_id": ACTION_PROFILE, **action}
    binding_preimage = {"profile_id": BINDING_PROFILE, **binding}
    record = {
        "schema": AUTH_SCHEMA,
        "profile": EXPORT_PROFILE,
        "transition_id": require_non_empty_string(
            input_data.get("transition_id"),
            label=f"{case_id}.transition_id",
        ),
        "subject_id": require_non_empty_string(
            input_data.get("subject_id"),
            label=f"{case_id}.subject_id",
        ),
        "action_identity_profile": ACTION_PROFILE,
        "action_identity_digest": sha256_uri(action_preimage),
        "binding_profile": BINDING_PROFILE,
        "binding_digest": sha256_uri(binding_preimage),
        "decision": decision_value,
        "reason_codes": require_string_list(
            decision.get("reason_codes"),
            label=f"{case_id}.reason_codes",
        ),
        "issued_at": require_non_empty_string(
            decision.get("issued_at"),
            label=f"{case_id}.issued_at",
        ),
        "expires_at": decision.get("expires_at"),
        "consumption_state": consumption_state,
        "continuation_state": continuation_state,
        "current_state": current_state,
        "policy_ref": require_non_empty_string(
            decision.get("policy_ref"),
            label=f"{case_id}.policy_ref",
        ),
        "proofpath_evidence_refs": require_string_list(
            decision.get("proofpath_evidence_refs"),
            label=f"{case_id}.proofpath_evidence_refs",
        ),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return wrap_record(record)


def build_handoff(
    case: dict[str, Any],
    exported: dict[str, Any],
) -> dict[str, Any] | None:
    handoff = case.get("handoff")
    if handoff is None:
        return None
    if not isinstance(handoff, dict):
        raise ExportVerificationError(
            f"{case['case_id']}.handoff must be an object or null"
        )

    observation_input = handoff.get("observation")
    if not isinstance(observation_input, dict):
        raise ExportVerificationError(
            f"{case['case_id']} handoff requires observation"
        )
    auth_record = exported["record"]
    observation = {
        "schema": OBS_SCHEMA,
        "transition_id": auth_record["transition_id"],
        "subject_id": auth_record["subject_id"],
        "authorization_ref": exported["record_ref"],
        "action_identity_digest": auth_record["action_identity_digest"],
        "binding_digest": auth_record["binding_digest"],
        "execution_status": require_non_empty_string(
            observation_input.get("execution_status"),
            label=f"{case['case_id']}.execution_status",
        ),
        "observed_at": require_non_empty_string(
            observation_input.get("observed_at"),
            label=f"{case['case_id']}.observed_at",
        ),
        "result_digest": require_non_empty_string(
            observation_input.get("result_digest"),
            label=f"{case['case_id']}.result_digest",
        ),
        "issuer": require_non_empty_string(
            observation_input.get("issuer"),
            label=f"{case['case_id']}.issuer",
        ),
    }
    observation_wrapper = {
        "record": observation,
        "record_ref": sha256_uri(observation),
    }
    derived: dict[str, Any] = {
        "observation_record": observation_wrapper,
        "expected_join": require_non_empty_string(
            handoff.get("expected_join"),
            label=f"{case['case_id']}.expected_join",
        ),
    }

    integrity_input = handoff.get("response_integrity")
    if integrity_input is not None:
        if not isinstance(integrity_input, dict):
            raise ExportVerificationError(
                f"{case['case_id']}.response_integrity must be an object"
            )
        integrity = {
            "schema": INTEGRITY_SCHEMA,
            "transition_id": auth_record["transition_id"],
            "subject_id": auth_record["subject_id"],
            "authorization_ref": exported["record_ref"],
            "observation_refs": [observation_wrapper["record_ref"]],
            "overall_verdict": require_non_empty_string(
                integrity_input.get("overall_verdict"),
                label=f"{case['case_id']}.overall_verdict",
            ),
            "verifier": require_non_empty_string(
                integrity_input.get("verifier"),
                label=f"{case['case_id']}.verifier",
            ),
            "claim_boundary": require_non_empty_string(
                integrity_input.get("claim_boundary"),
                label=f"{case['case_id']}.claim_boundary",
            ),
        }
        derived["response_integrity_record"] = {
            "record": integrity,
            "record_ref": sha256_uri(integrity),
        }

    return derived


def verify_case(case: dict[str, Any]) -> dict[str, Any]:
    case_id = require_non_empty_string(case.get("case_id"), label="case_id")
    expected = case.get("expected")
    if not isinstance(expected, dict):
        raise ExportVerificationError(
            f"{case_id}.expected must be an object"
        )

    exported = build_export(case)
    record = exported["record"]
    if exported["record_ref"] != expected.get("authorization_ref"):
        raise ExportVerificationError(
            f"{case_id} authorization_ref regression: "
            f"expected {expected.get('authorization_ref')}, "
            f"derived {exported['record_ref']}"
        )

    execution_allowed = expected.get("execution_allowed")
    if not isinstance(execution_allowed, bool):
        raise ExportVerificationError(
            f"{case_id}.expected.execution_allowed must be boolean"
        )
    should_allow = (
        record["decision"] == "ACCEPT"
        and record["current_state"] == "ACTIVE"
        and record["consumption_state"] == "UNCONSUMED"
    )
    if execution_allowed != should_allow:
        raise ExportVerificationError(
            f"{case_id} execution_allowed mismatch: "
            f"expected {execution_allowed}, derived {should_allow}"
        )

    expected_effects = expected.get("expected_additional_side_effects")
    if execution_allowed and expected_effects != 1:
        raise ExportVerificationError(
            f"{case_id} accepted live authority must expect one side effect"
        )
    if not execution_allowed and expected_effects != 0:
        raise ExportVerificationError(
            f"{case_id} non-executable authority must expect zero side effects"
        )
    if expected.get("current_state") != record["current_state"]:
        raise ExportVerificationError(
            f"{case_id} current-state expectation mismatch"
        )

    handoff = build_handoff(case, exported)
    if handoff is not None:
        observation = handoff["observation_record"]["record"]
        if observation["authorization_ref"] != exported["record_ref"]:
            raise ExportVerificationError(
                f"{case_id} observation authorization_ref mismatch"
            )
        for field in (
            "transition_id",
            "subject_id",
            "action_identity_digest",
            "binding_digest",
        ):
            if observation[field] != record[field]:
                raise ExportVerificationError(
                    f"{case_id} observation {field} mismatch"
                )

        integrity_wrapper = handoff.get("response_integrity_record")
        if integrity_wrapper is not None:
            integrity = integrity_wrapper["record"]
            if integrity["authorization_ref"] != exported["record_ref"]:
                raise ExportVerificationError(
                    f"{case_id} integrity authorization_ref mismatch"
                )
            if (
                handoff["observation_record"]["record_ref"]
                not in integrity["observation_refs"]
            ):
                raise ExportVerificationError(
                    f"{case_id} integrity missing observation reference"
                )

    return {
        "authorization_record": exported,
        "handoff": handoff,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "fixture",
        nargs="?",
        type=Path,
        default=Path("conformance/authorization-record-export-v0.1.json"),
    )
    parser.add_argument(
        "--emit-case",
        help="Print the deterministic export and handoff for one case_id",
    )
    args = parser.parse_args()

    try:
        fixture = load_json(args.fixture)
        if fixture.get("profile") != EXPORT_PROFILE:
            raise ExportVerificationError("fixture export profile mismatch")
        cases = fixture.get("cases")
        if not isinstance(cases, list) or not cases:
            raise ExportVerificationError("fixture cases must be non-empty")

        seen: set[str] = set()
        selected: dict[str, Any] | None = None
        selected_output: dict[str, Any] | None = None
        for case in cases:
            if not isinstance(case, dict):
                raise ExportVerificationError("case entry must be an object")
            case_id = require_non_empty_string(
                case.get("case_id"), label="case_id"
            )
            if case_id in seen:
                raise ExportVerificationError(f"duplicate case_id: {case_id}")
            seen.add(case_id)
            derived = verify_case(case)
            if case_id == args.emit_case:
                selected = case
                selected_output = derived
            record = derived["authorization_record"]["record"]
            print(
                f"PASS {case_id} -> "
                f"{record['decision']} / {record['current_state']}"
            )

        if args.emit_case:
            if selected is None or selected_output is None:
                raise ExportVerificationError(
                    f"unknown case_id for --emit-case: {args.emit_case}"
                )
            print(json.dumps(selected_output, ensure_ascii=False, indent=2))

        print(
            f"\nProofPath authorization export fixtures passed: {len(cases)}"
        )
        return 0
    except ExportVerificationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
