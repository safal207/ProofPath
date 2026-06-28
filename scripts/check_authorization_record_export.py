#!/usr/bin/env python3
"""Verify and export ProofPath provider-neutral authorization records.

The fixture is intentionally dependency-free. It covers the published input
domain without floating-point values, so sorted minimal JSON is equivalent to
RFC 8785 JCS for this conformance vector.
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

    canonical = canonical_json(record)
    return {
        "record": record,
        "canonical_bytes_utf8": canonical,
        "record_ref": (
            "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        ),
    }


def verify_record_shape(record: dict[str, Any], *, label: str) -> None:
    expected_keys = {
        "schema",
        "profile",
        "transition_id",
        "subject_id",
        "action_identity_profile",
        "action_identity_digest",
        "binding_profile",
        "binding_digest",
        "decision",
        "reason_codes",
        "issued_at",
        "expires_at",
        "consumption_state",
        "continuation_state",
        "current_state",
        "policy_ref",
        "proofpath_evidence_refs",
        "claim_boundary",
    }
    if set(record) != expected_keys:
        missing = sorted(expected_keys - set(record))
        extra = sorted(set(record) - expected_keys)
        raise ExportVerificationError(
            f"{label} key mismatch: missing={missing}, extra={extra}"
        )
    if record["schema"] != AUTH_SCHEMA or record["profile"] != EXPORT_PROFILE:
        raise ExportVerificationError(f"{label} schema/profile mismatch")
    if record["decision"] not in DECISIONS:
        raise ExportVerificationError(f"{label} invalid decision")
    if record["consumption_state"] not in CONSUMPTION_STATES:
        raise ExportVerificationError(f"{label} invalid consumption state")
    if record["continuation_state"] not in CONTINUATION_STATES:
        raise ExportVerificationError(f"{label} invalid continuation state")
    if record["current_state"] not in CURRENT_STATES:
        raise ExportVerificationError(f"{label} invalid current state")
    for digest_field in ("action_identity_digest", "binding_digest"):
        value = record[digest_field]
        if (
            not isinstance(value, str)
            or not value.startswith("sha256:")
            or len(value) != 71
        ):
            raise ExportVerificationError(
                f"{label}.{digest_field} must be a sha256 URI"
            )


def verify_wrapper(wrapper: dict[str, Any], *, label: str) -> None:
    if set(wrapper) != {"record", "canonical_bytes_utf8", "record_ref"}:
        raise ExportVerificationError(
            f"{label} must contain record, canonical_bytes_utf8, record_ref"
        )
    record = wrapper.get("record")
    if not isinstance(record, dict):
        raise ExportVerificationError(f"{label}.record must be an object")
    verify_record_shape(record, label=f"{label}.record")
    canonical = canonical_json(record)
    if wrapper.get("canonical_bytes_utf8") != canonical:
        raise ExportVerificationError(f"{label} canonical bytes mismatch")
    if wrapper.get("record_ref") != sha256_uri(record):
        raise ExportVerificationError(f"{label} record reference mismatch")


def verify_handoff(case: dict[str, Any], exported: dict[str, Any]) -> None:
    handoff = case.get("handoff")
    if handoff is None:
        return
    if not isinstance(handoff, dict):
        raise ExportVerificationError(
            f"{case['case_id']}.handoff must be an object or null"
        )

    observation_wrapper = handoff.get("observation_record")
    if not isinstance(observation_wrapper, dict):
        raise ExportVerificationError(
            f"{case['case_id']} handoff requires observation_record"
        )
    observation = observation_wrapper.get("record")
    if not isinstance(observation, dict):
        raise ExportVerificationError(
            f"{case['case_id']} observation record must be an object"
        )
    if observation_wrapper.get("record_ref") != sha256_uri(observation):
        raise ExportVerificationError(
            f"{case['case_id']} observation record_ref mismatch"
        )
    auth_record = exported["record"]
    for field in (
        "transition_id",
        "subject_id",
        "action_identity_digest",
        "binding_digest",
    ):
        if observation.get(field) != auth_record.get(field):
            raise ExportVerificationError(
                f"{case['case_id']} observation {field} mismatch"
            )
    if observation.get("authorization_ref") != exported["record_ref"]:
        raise ExportVerificationError(
            f"{case['case_id']} observation authorization_ref mismatch"
        )

    integrity_wrapper = handoff.get("response_integrity_record")
    if integrity_wrapper is not None:
        if not isinstance(integrity_wrapper, dict):
            raise ExportVerificationError(
                f"{case['case_id']} integrity wrapper must be an object"
            )
        integrity = integrity_wrapper.get("record")
        if not isinstance(integrity, dict):
            raise ExportVerificationError(
                f"{case['case_id']} integrity record must be an object"
            )
        if integrity_wrapper.get("record_ref") != sha256_uri(integrity):
            raise ExportVerificationError(
                f"{case['case_id']} integrity record_ref mismatch"
            )
        if integrity.get("authorization_ref") != exported["record_ref"]:
            raise ExportVerificationError(
                f"{case['case_id']} integrity authorization_ref mismatch"
            )
        if observation_wrapper["record_ref"] not in integrity.get(
            "observation_refs", []
        ):
            raise ExportVerificationError(
                f"{case['case_id']} integrity missing observation reference"
            )


def verify_case(case: dict[str, Any]) -> None:
    case_id = require_non_empty_string(case.get("case_id"), label="case_id")
    exported = case.get("exported")
    expected = case.get("expected")
    if not isinstance(exported, dict) or not isinstance(expected, dict):
        raise ExportVerificationError(
            f"{case_id} requires exported and expected objects"
        )

    recomputed = build_export(case)
    verify_wrapper(exported, label=f"{case_id}.exported")
    if exported != recomputed:
        raise ExportVerificationError(
            f"{case_id} exported record differs from deterministic export"
        )

    execution_allowed = expected.get("execution_allowed")
    if not isinstance(execution_allowed, bool):
        raise ExportVerificationError(
            f"{case_id}.expected.execution_allowed must be boolean"
        )
    record = exported["record"]
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

    verify_handoff(case, exported)


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
        help="Print the deterministic exported wrapper for one case_id",
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
        for case in cases:
            if not isinstance(case, dict):
                raise ExportVerificationError("case entry must be an object")
            case_id = require_non_empty_string(
                case.get("case_id"), label="case_id"
            )
            if case_id in seen:
                raise ExportVerificationError(f"duplicate case_id: {case_id}")
            seen.add(case_id)
            verify_case(case)
            if case_id == args.emit_case:
                selected = case
            print(
                f"PASS {case_id} -> "
                f"{case['exported']['record']['decision']} / "
                f"{case['exported']['record']['current_state']}"
            )

        if args.emit_case:
            if selected is None:
                raise ExportVerificationError(
                    f"unknown case_id for --emit-case: {args.emit_case}"
                )
            print(json.dumps(build_export(selected), ensure_ascii=False, indent=2))

        print(
            f"\nProofPath authorization export fixtures passed: {len(cases)}"
        )
        return 0
    except ExportVerificationError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
