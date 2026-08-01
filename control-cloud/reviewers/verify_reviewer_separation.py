#!/usr/bin/env python3
"""ProofPath reviewer identity and separation-of-duties verifier.

This layer consumes an already ACCEPTed workflow-governance decision, a
server-controlled reviewer identity registry, and an exact approval bundle.
It emits a tamper-evident ACCEPT/HOLD/BLOCK/CHALLENGE decision. It performs no
GitHub write, credential mutation, payment, deployment, or authority grant.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[2]
governance = _load_module(
    "proofpath_workflow_governance_for_reviewer_separation",
    REPO_ROOT / "control-cloud/governance/verify_workflow_governance.py",
)

REGISTRY_PROFILE = "proofpath.control-cloud.reviewer-identity-registry.v0.1"
APPROVAL_PROFILE = "proofpath.control-cloud.reviewer-approval-bundle.v0.1"
DECISION_PROFILE = "proofpath.control-cloud.reviewer-separation-decision.v0.1"
CHANGE_PROFILE = "proofpath.control-cloud.reviewer-identity-change-proposal.v0.1"
DECISION_DOMAIN = DECISION_PROFILE + ".root"
CHANGE_DOMAIN = CHANGE_PROFILE + ".root"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{2,127}$")
LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
SUBJECT_RE = re.compile(r"^[a-z][a-z0-9+.-]*://\S{3,500}$")
ROLE_RE = re.compile(r"^[a-z][a-z0-9-]{1,63}$")


class ReviewerSeparationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def raw_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def domain_hash(domain: str, value: Any) -> str:
    return raw_digest(domain.encode("utf-8") + b"\x00" + canonical_bytes(value))


def strict_loads(data: bytes | str) -> Any:
    text = data.decode("utf-8") if isinstance(data, bytes) else data

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ReviewerSeparationError("DUPLICATE_JSON_KEY", f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(text, object_pairs_hook=no_duplicates)


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise ReviewerSeparationError("INPUT_UNAVAILABLE", f"{path} must be a regular non-symlink file")
    value = strict_loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ReviewerSeparationError("INVALID_JSON_OBJECT", f"{path} must contain one JSON object")
    return value


def require_exact_keys(value: dict[str, Any], required: set[str], label: str) -> None:
    if set(value) != required:
        missing = sorted(required - set(value))
        extra = sorted(set(value) - required)
        raise ReviewerSeparationError(
            "INVALID_SHAPE",
            f"{label} keys mismatch; missing={missing}, extra={extra}",
        )


def require_text(value: Any, label: str, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value:
        raise ReviewerSeparationError("INVALID_TEXT", f"{label} must be non-empty text")
    if pattern is not None and not pattern.fullmatch(value):
        raise ReviewerSeparationError("INVALID_TEXT", f"{label} has invalid format")
    return value


def require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ReviewerSeparationError("INVALID_BOOLEAN", f"{label} must be boolean")
    return value


def require_int(value: Any, label: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ReviewerSeparationError("INVALID_INTEGER", f"{label} must be integer >= {minimum}")
    return value


def require_digest(value: Any, label: str) -> str:
    try:
        governance.require_digest(value, label)
    except governance.GovernanceError as exc:
        raise ReviewerSeparationError(exc.code, exc.message) from exc
    return value


def parse_utc(value: Any, label: str) -> dt.datetime:
    try:
        return governance.parse_utc(value, label)
    except governance.GovernanceError as exc:
        raise ReviewerSeparationError(exc.code, exc.message) from exc


def validate_registry(value: dict[str, Any]) -> dict[str, Any]:
    require_exact_keys(value, {"profile_id", "generated_at", "policy", "reviewers", "suspensions"}, "identity registry")
    if value["profile_id"] != REGISTRY_PROFILE:
        raise ReviewerSeparationError("UNSUPPORTED_REGISTRY", "unsupported reviewer identity registry")
    parse_utc(value["generated_at"], "registry.generated_at")

    policy = value["policy"]
    if not isinstance(policy, dict):
        raise ReviewerSeparationError("INVALID_POLICY", "registry.policy must be an object")
    require_exact_keys(
        policy,
        {
            "required_approvals",
            "required_distinct_organizations",
            "required_role",
            "allowed_identity_providers",
            "forbid_author_organization",
            "require_distinct_control_clusters",
            "require_distinct_payment_clusters",
            "max_approval_age_seconds",
        },
        "registry.policy",
    )
    require_int(policy["required_approvals"], "policy.required_approvals", 1)
    require_int(policy["required_distinct_organizations"], "policy.required_distinct_organizations", 1)
    require_text(policy["required_role"], "policy.required_role", ROLE_RE)
    if not isinstance(policy["allowed_identity_providers"], list) or not policy["allowed_identity_providers"]:
        raise ReviewerSeparationError("INVALID_POLICY", "allowed_identity_providers must be a non-empty list")
    if len(set(policy["allowed_identity_providers"])) != len(policy["allowed_identity_providers"]):
        raise ReviewerSeparationError("INVALID_POLICY", "allowed_identity_providers contains duplicates")
    for index, provider in enumerate(policy["allowed_identity_providers"]):
        require_text(provider, f"allowed_identity_providers[{index}]", ID_RE)
    for field in (
        "forbid_author_organization",
        "require_distinct_control_clusters",
        "require_distinct_payment_clusters",
    ):
        require_bool(policy[field], f"policy.{field}")
    require_int(policy["max_approval_age_seconds"], "policy.max_approval_age_seconds", 60)

    if not isinstance(value["reviewers"], list) or not value["reviewers"]:
        raise ReviewerSeparationError("INVALID_REVIEWERS", "registry.reviewers must be a non-empty list")
    reviewer_ids: set[str] = set()
    identity_subjects: set[str] = set()
    github_logins: set[str] = set()
    for index, reviewer in enumerate(value["reviewers"]):
        if not isinstance(reviewer, dict):
            raise ReviewerSeparationError("INVALID_REVIEWER", f"reviewer[{index}] must be an object")
        require_exact_keys(
            reviewer,
            {
                "reviewer_id",
                "status",
                "github_login",
                "identity_provider",
                "identity_subject",
                "organization_id",
                "control_cluster_id",
                "payment_cluster_id",
                "roles",
                "effective_at",
                "expires_at",
                "identity_evidence_digest",
                "independence_attested",
                "authority_granted",
            },
            f"reviewer[{index}]",
        )
        reviewer_id = require_text(reviewer["reviewer_id"], f"reviewer[{index}].reviewer_id", ID_RE)
        if reviewer_id in reviewer_ids:
            raise ReviewerSeparationError("DUPLICATE_REVIEWER_ID", "reviewer_id must be unique")
        reviewer_ids.add(reviewer_id)
        if reviewer["status"] not in {"ACTIVE", "SUSPENDED", "REVOKED"}:
            raise ReviewerSeparationError("INVALID_REVIEWER_STATUS", "reviewer status is unsupported")
        login = require_text(reviewer["github_login"], f"reviewer[{index}].github_login", LOGIN_RE).lower()
        if login in github_logins:
            raise ReviewerSeparationError("AMBIGUOUS_GITHUB_LOGIN", "github login maps to multiple reviewer identities")
        github_logins.add(login)
        require_text(reviewer["identity_provider"], f"reviewer[{index}].identity_provider", ID_RE)
        subject = require_text(reviewer["identity_subject"], f"reviewer[{index}].identity_subject", SUBJECT_RE)
        if subject in identity_subjects:
            raise ReviewerSeparationError("AMBIGUOUS_IDENTITY_SUBJECT", "identity subject maps to multiple reviewers")
        identity_subjects.add(subject)
        for field in ("organization_id", "control_cluster_id", "payment_cluster_id"):
            require_text(reviewer[field], f"reviewer[{index}].{field}", ID_RE)
        if not isinstance(reviewer["roles"], list) or not reviewer["roles"]:
            raise ReviewerSeparationError("INVALID_REVIEWER_ROLES", "reviewer roles must be non-empty")
        if len(set(reviewer["roles"])) != len(reviewer["roles"]):
            raise ReviewerSeparationError("INVALID_REVIEWER_ROLES", "reviewer roles contain duplicates")
        for role in reviewer["roles"]:
            require_text(role, "reviewer.role", ROLE_RE)
        effective = parse_utc(reviewer["effective_at"], "reviewer.effective_at")
        expires = parse_utc(reviewer["expires_at"], "reviewer.expires_at")
        if effective >= expires:
            raise ReviewerSeparationError("INVALID_REVIEWER_WINDOW", "reviewer effective_at must precede expires_at")
        require_digest(reviewer["identity_evidence_digest"], "reviewer.identity_evidence_digest")
        require_bool(reviewer["independence_attested"], "reviewer.independence_attested")
        if reviewer["authority_granted"] is not False:
            raise ReviewerSeparationError("BOUNDARY_VIOLATION", "reviewer.authority_granted must be false")

    if not isinstance(value["suspensions"], list):
        raise ReviewerSeparationError("INVALID_SUSPENSIONS", "registry.suspensions must be a list")
    suspension_ids: set[str] = set()
    for index, suspension in enumerate(value["suspensions"]):
        if not isinstance(suspension, dict):
            raise ReviewerSeparationError("INVALID_SUSPENSION", f"suspension[{index}] must be an object")
        require_exact_keys(
            suspension,
            {"suspension_id", "reviewer_id", "effective_at", "reason_code", "approved_by", "authority_granted"},
            f"suspension[{index}]",
        )
        suspension_id = require_text(suspension["suspension_id"], "suspension.suspension_id", ID_RE)
        if suspension_id in suspension_ids:
            raise ReviewerSeparationError("DUPLICATE_SUSPENSION_ID", "suspension_id must be unique")
        suspension_ids.add(suspension_id)
        reviewer_id = require_text(suspension["reviewer_id"], "suspension.reviewer_id", ID_RE)
        if reviewer_id not in reviewer_ids:
            raise ReviewerSeparationError("UNKNOWN_SUSPENDED_REVIEWER", "suspension references unknown reviewer")
        parse_utc(suspension["effective_at"], "suspension.effective_at")
        require_text(suspension["reason_code"], "suspension.reason_code", ID_RE)
        if not isinstance(suspension["approved_by"], list) or not suspension["approved_by"]:
            raise ReviewerSeparationError("INVALID_SUSPENSION_APPROVAL", "suspension approved_by must be non-empty")
        if suspension["authority_granted"] is not False:
            raise ReviewerSeparationError("BOUNDARY_VIOLATION", "suspension.authority_granted must be false")
    return value


def validate_approval_bundle(value: dict[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        value,
        {
            "profile_id",
            "governance_decision_root",
            "author_identity_subject",
            "author_organization_id",
            "author_control_cluster_id",
            "author_payment_cluster_id",
            "workflow",
            "signer_sha",
            "approvals",
        },
        "approval bundle",
    )
    if value["profile_id"] != APPROVAL_PROFILE:
        raise ReviewerSeparationError("UNSUPPORTED_APPROVAL_BUNDLE", "unsupported approval bundle")
    require_digest(value["governance_decision_root"], "bundle.governance_decision_root")
    require_text(value["author_identity_subject"], "bundle.author_identity_subject", SUBJECT_RE)
    for field in ("author_organization_id", "author_control_cluster_id", "author_payment_cluster_id"):
        require_text(value[field], f"bundle.{field}", ID_RE)
    require_text(value["workflow"], "bundle.workflow")
    governance.require_sha(value["signer_sha"], "bundle.signer_sha")
    if not isinstance(value["approvals"], list):
        raise ReviewerSeparationError("INVALID_APPROVALS", "bundle.approvals must be a list")
    approval_ids: set[str] = set()
    for index, approval in enumerate(value["approvals"]):
        if not isinstance(approval, dict):
            raise ReviewerSeparationError("INVALID_APPROVAL", f"approval[{index}] must be an object")
        require_exact_keys(
            approval,
            {
                "approval_id",
                "reviewer_id",
                "reviewer_identity_subject",
                "decision",
                "approved_at",
                "governance_decision_root",
                "workflow",
                "signer_sha",
                "statement_digest",
                "identity_evidence_digest",
                "conflict_of_interest_declared",
            },
            f"approval[{index}]",
        )
        approval_id = require_text(approval["approval_id"], "approval.approval_id", ID_RE)
        if approval_id in approval_ids:
            raise ReviewerSeparationError("DUPLICATE_APPROVAL_ID", "approval_id must be unique")
        approval_ids.add(approval_id)
        require_text(approval["reviewer_id"], "approval.reviewer_id", ID_RE)
        require_text(approval["reviewer_identity_subject"], "approval.reviewer_identity_subject", SUBJECT_RE)
        if approval["decision"] not in {"APPROVE", "REJECT"}:
            raise ReviewerSeparationError("INVALID_APPROVAL_DECISION", "approval decision is unsupported")
        parse_utc(approval["approved_at"], "approval.approved_at")
        require_digest(approval["governance_decision_root"], "approval.governance_decision_root")
        require_text(approval["workflow"], "approval.workflow")
        governance.require_sha(approval["signer_sha"], "approval.signer_sha")
        require_digest(approval["statement_digest"], "approval.statement_digest")
        require_digest(approval["identity_evidence_digest"], "approval.identity_evidence_digest")
        require_bool(approval["conflict_of_interest_declared"], "approval.conflict_of_interest_declared")
    return value


def _decision_without_root(value: dict[str, Any]) -> dict[str, Any]:
    copy = dict(value)
    copy["decision_root"] = None
    return copy


def _base_decision(
    *,
    governance_decision: dict[str, Any],
    registry: dict[str, Any],
    bundle: dict[str, Any],
    observed_at: str,
    decision: str,
    reason_code: str,
    reviewer_ids: list[str],
    organizations: list[str],
    checks: dict[str, bool],
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "profile_id": DECISION_PROFILE,
        "decision": decision,
        "reason_code": reason_code,
        "separation_of_duties_verified": decision == "ACCEPT",
        "governance_decision_root": governance_decision["decision_root"],
        "admission_result_root": governance_decision["admission_result_root"],
        "workflow": governance_decision["signer_workflow"],
        "signer_sha": governance_decision["signer_sha"],
        "identity_registry_digest": raw_digest(canonical_bytes(registry)),
        "approval_bundle_digest": raw_digest(canonical_bytes(bundle)),
        "verified_reviewer_ids": reviewer_ids,
        "verified_organization_ids": organizations,
        "verified_reviewer_count": len(reviewer_ids),
        "verified_organization_count": len(organizations),
        "identity_status_verified": checks["identity_status_verified"],
        "identity_evidence_verified": checks["identity_evidence_verified"],
        "reviewer_role_verified": checks["reviewer_role_verified"],
        "author_separation_verified": checks["author_separation_verified"],
        "organization_separation_verified": checks["organization_separation_verified"],
        "control_cluster_separation_verified": checks["control_cluster_separation_verified"],
        "payment_cluster_separation_verified": checks["payment_cluster_separation_verified"],
        "approval_freshness_verified": checks["approval_freshness_verified"],
        "suspension_checked": checks["suspension_checked"],
        "observed_at": observed_at,
        "identity_verifier_identity": "proofpath-reviewer-identity-separation-v0.1",
        "authority_granted": False,
        "repository_write_performed": False,
        "payments_executed": False,
        "decision_root": None,
    }
    value["decision_root"] = domain_hash(DECISION_DOMAIN, _decision_without_root(value))
    return value


def evaluate(
    *,
    governance_decision: dict[str, Any],
    registry: dict[str, Any],
    bundle: dict[str, Any],
    observed_at: str,
) -> dict[str, Any]:
    governance_decision = governance.validate_decision(governance_decision)
    if governance_decision["decision"] != "ACCEPT" or governance_decision["governance_trust_verified"] is not True:
        raise ReviewerSeparationError("WORKFLOW_GOVERNANCE_REQUIRED", "reviewer separation requires governance ACCEPT")
    registry = validate_registry(registry)
    bundle = validate_approval_bundle(bundle)
    observed = parse_utc(observed_at, "observed_at")

    if bundle["governance_decision_root"] != governance_decision["decision_root"]:
        raise ReviewerSeparationError("APPROVAL_BINDING_CONFLICT", "bundle governance root differs")
    if bundle["workflow"] != governance_decision["signer_workflow"]:
        raise ReviewerSeparationError("APPROVAL_BINDING_CONFLICT", "bundle workflow differs")
    if bundle["signer_sha"] != governance_decision["signer_sha"]:
        raise ReviewerSeparationError("APPROVAL_BINDING_CONFLICT", "bundle signer SHA differs")

    checks = {
        "identity_status_verified": True,
        "identity_evidence_verified": True,
        "reviewer_role_verified": True,
        "author_separation_verified": True,
        "organization_separation_verified": True,
        "control_cluster_separation_verified": True,
        "payment_cluster_separation_verified": True,
        "approval_freshness_verified": True,
        "suspension_checked": True,
    }
    reviewers = {item["reviewer_id"]: item for item in registry["reviewers"]}
    policy = registry["policy"]
    effective_suspensions = {
        item["reviewer_id"]
        for item in registry["suspensions"]
        if parse_utc(item["effective_at"], "suspension.effective_at") <= observed
    }

    seen_reviewers: set[str] = set()
    seen_subjects: set[str] = set()
    seen_control_clusters: set[str] = set()
    seen_payment_clusters: set[str] = set()
    verified_reviewer_ids: list[str] = []
    organizations: list[str] = []

    def finish(decision: str, reason: str) -> dict[str, Any]:
        return _base_decision(
            governance_decision=governance_decision,
            registry=registry,
            bundle=bundle,
            observed_at=governance.format_utc(observed),
            decision=decision,
            reason_code=reason,
            reviewer_ids=sorted(verified_reviewer_ids),
            organizations=sorted(set(organizations)),
            checks=checks,
        )

    for approval in bundle["approvals"]:
        reviewer_id = approval["reviewer_id"]
        if reviewer_id in seen_reviewers:
            return finish("BLOCK", "duplicate_reviewer_approval")
        seen_reviewers.add(reviewer_id)
        if approval["decision"] == "REJECT":
            return finish("BLOCK", "reviewer_rejected")
        reviewer = reviewers.get(reviewer_id)
        if reviewer is None:
            checks["identity_status_verified"] = False
            return finish("HOLD", "reviewer_identity_missing")
        if reviewer_id in effective_suspensions or reviewer["status"] in {"SUSPENDED", "REVOKED"}:
            checks["identity_status_verified"] = False
            return finish("BLOCK", "reviewer_identity_suspended")
        effective = parse_utc(reviewer["effective_at"], "reviewer.effective_at")
        expires = parse_utc(reviewer["expires_at"], "reviewer.expires_at")
        if not (effective <= observed < expires):
            checks["identity_status_verified"] = False
            return finish("HOLD", "reviewer_identity_window_inactive")
        if reviewer["identity_provider"] not in policy["allowed_identity_providers"]:
            checks["identity_status_verified"] = False
            return finish("BLOCK", "identity_provider_not_allowed")
        if approval["reviewer_identity_subject"] != reviewer["identity_subject"]:
            checks["identity_evidence_verified"] = False
            return finish("BLOCK", "reviewer_identity_subject_mismatch")
        if approval["identity_evidence_digest"] != reviewer["identity_evidence_digest"]:
            checks["identity_evidence_verified"] = False
            return finish("BLOCK", "identity_evidence_mismatch")
        if reviewer["independence_attested"] is not True:
            checks["identity_evidence_verified"] = False
            return finish("HOLD", "independence_attestation_missing")
        if policy["required_role"] not in reviewer["roles"]:
            checks["reviewer_role_verified"] = False
            return finish("BLOCK", "reviewer_role_not_allowed")
        if approval["conflict_of_interest_declared"] is True:
            checks["author_separation_verified"] = False
            return finish("BLOCK", "conflict_of_interest_declared")
        if approval["governance_decision_root"] != governance_decision["decision_root"]:
            return finish("BLOCK", "approval_governance_root_mismatch")
        if approval["workflow"] != governance_decision["signer_workflow"] or approval["signer_sha"] != governance_decision["signer_sha"]:
            return finish("BLOCK", "approval_workflow_binding_mismatch")
        approved_at = parse_utc(approval["approved_at"], "approval.approved_at")
        age = observed - approved_at
        if age < dt.timedelta(0) or age > dt.timedelta(seconds=policy["max_approval_age_seconds"]):
            checks["approval_freshness_verified"] = False
            return finish("HOLD", "approval_stale_or_future")
        subject = reviewer["identity_subject"]
        if subject == bundle["author_identity_subject"]:
            checks["author_separation_verified"] = False
            return finish("BLOCK", "author_self_approval")
        if subject in seen_subjects:
            return finish("CHALLENGE", "ambiguous_reviewer_identity")
        seen_subjects.add(subject)
        if policy["forbid_author_organization"] and reviewer["organization_id"] == bundle["author_organization_id"]:
            checks["organization_separation_verified"] = False
            return finish("BLOCK", "author_organization_conflict")
        if reviewer["control_cluster_id"] == bundle["author_control_cluster_id"]:
            checks["control_cluster_separation_verified"] = False
            return finish("BLOCK", "author_control_cluster_conflict")
        if reviewer["payment_cluster_id"] == bundle["author_payment_cluster_id"]:
            checks["payment_cluster_separation_verified"] = False
            return finish("BLOCK", "author_payment_cluster_conflict")
        if policy["require_distinct_control_clusters"] and reviewer["control_cluster_id"] in seen_control_clusters:
            checks["control_cluster_separation_verified"] = False
            return finish("BLOCK", "reviewer_control_cluster_collision")
        if policy["require_distinct_payment_clusters"] and reviewer["payment_cluster_id"] in seen_payment_clusters:
            checks["payment_cluster_separation_verified"] = False
            return finish("BLOCK", "reviewer_payment_cluster_collision")
        seen_control_clusters.add(reviewer["control_cluster_id"])
        seen_payment_clusters.add(reviewer["payment_cluster_id"])
        verified_reviewer_ids.append(reviewer_id)
        organizations.append(reviewer["organization_id"])

    if len(verified_reviewer_ids) < policy["required_approvals"]:
        return finish("HOLD", "reviewer_quorum_missing")
    if len(set(organizations)) < policy["required_distinct_organizations"]:
        checks["organization_separation_verified"] = False
        return finish("HOLD", "organization_diversity_missing")
    return finish("ACCEPT", "reviewer_separation_verified")


def validate_decision(value: dict[str, Any]) -> dict[str, Any]:
    required = {
        "profile_id",
        "decision",
        "reason_code",
        "separation_of_duties_verified",
        "governance_decision_root",
        "admission_result_root",
        "workflow",
        "signer_sha",
        "identity_registry_digest",
        "approval_bundle_digest",
        "verified_reviewer_ids",
        "verified_organization_ids",
        "verified_reviewer_count",
        "verified_organization_count",
        "identity_status_verified",
        "identity_evidence_verified",
        "reviewer_role_verified",
        "author_separation_verified",
        "organization_separation_verified",
        "control_cluster_separation_verified",
        "payment_cluster_separation_verified",
        "approval_freshness_verified",
        "suspension_checked",
        "observed_at",
        "identity_verifier_identity",
        "authority_granted",
        "repository_write_performed",
        "payments_executed",
        "decision_root",
    }
    require_exact_keys(value, required, "reviewer separation decision")
    if value["profile_id"] != DECISION_PROFILE:
        raise ReviewerSeparationError("UNSUPPORTED_DECISION", "unsupported reviewer separation decision")
    if value["decision"] not in {"ACCEPT", "HOLD", "BLOCK", "CHALLENGE"}:
        raise ReviewerSeparationError("INVALID_DECISION", "reviewer separation decision is unsupported")
    require_text(value["reason_code"], "decision.reason_code", ID_RE)
    if value["separation_of_duties_verified"] is not (value["decision"] == "ACCEPT"):
        raise ReviewerSeparationError("DECISION_STATE_CONFLICT", "verified flag conflicts with decision")
    for field in (
        "governance_decision_root",
        "admission_result_root",
        "identity_registry_digest",
        "approval_bundle_digest",
        "decision_root",
    ):
        require_digest(value[field], f"decision.{field}")
    require_text(value["workflow"], "decision.workflow")
    governance.require_sha(value["signer_sha"], "decision.signer_sha")
    for field in ("verified_reviewer_ids", "verified_organization_ids"):
        if not isinstance(value[field], list) or len(set(value[field])) != len(value[field]):
            raise ReviewerSeparationError("INVALID_DECISION_LIST", f"decision.{field} must be unique list")
        for item in value[field]:
            require_text(item, f"decision.{field}", ID_RE)
    if value["verified_reviewer_count"] != len(value["verified_reviewer_ids"]):
        raise ReviewerSeparationError("DECISION_COUNT_CONFLICT", "reviewer count conflicts")
    if value["verified_organization_count"] != len(value["verified_organization_ids"]):
        raise ReviewerSeparationError("DECISION_COUNT_CONFLICT", "organization count conflicts")
    for field in (
        "identity_status_verified",
        "identity_evidence_verified",
        "reviewer_role_verified",
        "author_separation_verified",
        "organization_separation_verified",
        "control_cluster_separation_verified",
        "payment_cluster_separation_verified",
        "approval_freshness_verified",
        "suspension_checked",
    ):
        require_bool(value[field], f"decision.{field}")
    parse_utc(value["observed_at"], "decision.observed_at")
    require_text(value["identity_verifier_identity"], "decision.identity_verifier_identity", ID_RE)
    for field in ("authority_granted", "repository_write_performed", "payments_executed"):
        if value[field] is not False:
            raise ReviewerSeparationError("BOUNDARY_VIOLATION", f"decision.{field} must be false")
    expected = domain_hash(DECISION_DOMAIN, _decision_without_root(value))
    if value["decision_root"] != expected:
        raise ReviewerSeparationError("DECISION_ROOT_MISMATCH", "reviewer separation decision root is invalid")
    return value


def check_identity_change(
    *,
    registry: dict[str, Any],
    reviewer_id: str,
    observed_identity_subject: str,
    observed_organization_id: str,
    observed_control_cluster_id: str,
    observed_payment_cluster_id: str,
    observed_identity_evidence_digest: str,
    observed_at: str,
) -> dict[str, Any]:
    registry = validate_registry(registry)
    require_text(reviewer_id, "reviewer_id", ID_RE)
    require_text(observed_identity_subject, "observed_identity_subject", SUBJECT_RE)
    for value, label in (
        (observed_organization_id, "observed_organization_id"),
        (observed_control_cluster_id, "observed_control_cluster_id"),
        (observed_payment_cluster_id, "observed_payment_cluster_id"),
    ):
        require_text(value, label, ID_RE)
    require_digest(observed_identity_evidence_digest, "observed_identity_evidence_digest")
    observed = parse_utc(observed_at, "observed_at")
    reviewer = next((item for item in registry["reviewers"] if item["reviewer_id"] == reviewer_id), None)
    reasons: list[str] = []
    if reviewer is None:
        reasons.append("reviewer_identity_missing")
    else:
        comparisons = (
            ("identity_subject_changed", reviewer["identity_subject"], observed_identity_subject),
            ("organization_changed", reviewer["organization_id"], observed_organization_id),
            ("control_cluster_changed", reviewer["control_cluster_id"], observed_control_cluster_id),
            ("payment_cluster_changed", reviewer["payment_cluster_id"], observed_payment_cluster_id),
            ("identity_evidence_changed", reviewer["identity_evidence_digest"], observed_identity_evidence_digest),
        )
        reasons.extend(code for code, expected, actual in comparisons if expected != actual)
    result: dict[str, Any] = {
        "profile_id": CHANGE_PROFILE,
        "decision": "PROPOSE_SUSPEND" if reasons else "NO_CHANGE",
        "reason_codes": sorted(reasons),
        "reviewer_id": reviewer_id,
        "observed_at": governance.format_utc(observed),
        "repository_write_performed": False,
        "credential_revocation_performed": False,
        "authority_granted": False,
        "proposal_root": None,
    }
    result["proposal_root"] = domain_hash(CHANGE_DOMAIN, {**result, "proposal_root": None})
    return result


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value) + b"\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("--governance-decision", required=True, type=Path)
    evaluate_parser.add_argument("--identity-registry", required=True, type=Path)
    evaluate_parser.add_argument("--approval-bundle", required=True, type=Path)
    evaluate_parser.add_argument("--observed-at", required=True)
    evaluate_parser.add_argument("--output", required=True, type=Path)

    validate_parser = subparsers.add_parser("validate-decision")
    validate_parser.add_argument("--decision", required=True, type=Path)

    change_parser = subparsers.add_parser("check-identity-change")
    change_parser.add_argument("--identity-registry", required=True, type=Path)
    change_parser.add_argument("--reviewer-id", required=True)
    change_parser.add_argument("--observed-identity-subject", required=True)
    change_parser.add_argument("--observed-organization-id", required=True)
    change_parser.add_argument("--observed-control-cluster-id", required=True)
    change_parser.add_argument("--observed-payment-cluster-id", required=True)
    change_parser.add_argument("--observed-identity-evidence-digest", required=True)
    change_parser.add_argument("--observed-at", required=True)
    change_parser.add_argument("--output", required=True, type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "evaluate":
            result = evaluate(
                governance_decision=load_json(args.governance_decision),
                registry=load_json(args.identity_registry),
                bundle=load_json(args.approval_bundle),
                observed_at=args.observed_at,
            )
            validate_decision(result)
            write_json(args.output, result)
            print(f"ProofPath reviewer separation: {result['decision']} / {result['decision_root']}", file=sys.stderr)
            return 0 if result["decision"] == "ACCEPT" else 3
        if args.command == "validate-decision":
            result = validate_decision(load_json(args.decision))
            print(f"ProofPath reviewer separation decision valid: {result['decision_root']}")
            return 0
        proposal = check_identity_change(
            registry=load_json(args.identity_registry),
            reviewer_id=args.reviewer_id,
            observed_identity_subject=args.observed_identity_subject,
            observed_organization_id=args.observed_organization_id,
            observed_control_cluster_id=args.observed_control_cluster_id,
            observed_payment_cluster_id=args.observed_payment_cluster_id,
            observed_identity_evidence_digest=args.observed_identity_evidence_digest,
            observed_at=args.observed_at,
        )
        write_json(args.output, proposal)
        print(f"ProofPath reviewer identity change check: {proposal['decision']} / {proposal['proposal_root']}", file=sys.stderr)
        return 0 if proposal["decision"] == "NO_CHANGE" else 3
    except (
        ReviewerSeparationError,
        governance.GovernanceError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        code = exc.code if hasattr(exc, "code") else "REVIEWER_SEPARATION_ERROR"
        message = exc.message if hasattr(exc, "message") else str(exc)
        print(f"ProofPath reviewer separation failed: {code}: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
