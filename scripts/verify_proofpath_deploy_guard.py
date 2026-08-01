#!/usr/bin/env python3
"""Evaluate an AI production-deploy proposal and emit a ProofPath clearance certificate."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

POLICY_PROFILE = "proofpath.deploy.guard-policy.v0.1"
EVIDENCE_PROFILE = "proofpath.deploy.action-evidence.v0.1"
CERTIFICATE_PROFILE = "proofpath.deploy.clearance-certificate.v0.1"
PRODUCT = "PROOFPATH_ASSURED_ACTION"

POLICY_DOMAIN = b"proofpath:deploy-guard:v0.1:policy\n"
EVIDENCE_DOMAIN = b"proofpath:deploy-guard:v0.1:evidence\n"
CLEARANCE_DOMAIN = b"proofpath:deploy-guard:v0.1:clearance\n"

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
DECISION_RANK = {"ACCEPT": 0, "HOLD": 1, "BLOCK": 2, "CHALLENGE": 3}
EXIT_CODE = {"ACCEPT": 0, "HOLD": 2, "BLOCK": 3, "CHALLENGE": 4}

PRIORITY = {
    "DEPLOY_POLICY_INVALID": 10,
    "DEPLOY_EVIDENCE_INVALID": 20,
    "DEPLOY_ALREADY_EXECUTED": 30,
    "DEPLOY_REPOSITORY_NOT_ALLOWED": 40,
    "DEPLOY_ENVIRONMENT_NOT_ALLOWED": 50,
    "DEPLOY_BRANCH_NOT_ALLOWED": 60,
    "DEPLOY_ACTION_NOT_ALLOWED": 70,
    "DEPLOY_AUTHORITY_INACTIVE": 80,
    "DEPLOY_AUTHORITY_EXPIRED": 90,
    "DEPLOY_AUTHORITY_SCOPE_MISMATCH": 100,
    "DEPLOY_RUNNER_NOT_TRUSTED": 110,
    "DEPLOY_ATTESTATION_UNVERIFIED": 120,
    "DEPLOY_CHECK_FAILED": 130,
    "DEPLOY_CRITICAL_VULNERABILITY": 140,
    "DEPLOY_REQUIRED_CHECK_MISSING": 200,
    "DEPLOY_CHECK_PENDING": 210,
    "DEPLOY_APPROVAL_COUNT_INSUFFICIENT": 220,
    "DEPLOY_APPROVAL_ROLE_MISSING": 230,
    "DEPLOY_CHANGE_TICKET_MISSING": 240,
    "DEPLOY_CHANGE_TICKET_PENDING": 250,
    "DEPLOY_POLICY_ID_MISMATCH": 300,
    "DEPLOY_POLICY_VERSION_MISMATCH": 310,
    "DEPLOY_PROVENANCE_COMMIT_MISMATCH": 400,
    "DEPLOY_PROVENANCE_ARTIFACT_MISMATCH": 410,
    "DEPLOY_APPROVAL_COMMIT_MISMATCH": 420,
    "DEPLOY_CHECK_COMMIT_MISMATCH": 430,
    "DEPLOY_CHANGE_TICKET_COMMIT_MISMATCH": 440,
}


class EvidenceError(ValueError):
    """Raised when canonical deployment evidence is malformed."""


def _reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate,
        )
    except (OSError, json.JSONDecodeError, EvidenceError) as exc:
        raise EvidenceError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"{path} must contain one JSON object")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    def normalize(item: Any) -> Any:
        if isinstance(item, float):
            raise EvidenceError("floats are forbidden in canonical deployment evidence")
        if isinstance(item, dict):
            return {key: normalize(item[key]) for key in sorted(item)}
        if isinstance(item, list):
            return [normalize(entry) for entry in item]
        if item is None or isinstance(item, (str, int, bool)):
            return item
        raise EvidenceError(f"unsupported canonical type: {type(item).__name__}")

    return json.dumps(
        normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest(domain: bytes, value: Any) -> str:
    return "sha256:" + hashlib.sha256(domain + canonical_json_bytes(value)).hexdigest()


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _list_of_text(value: Any) -> list[str] | None:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        return None
    return value


def _positive_int(value: Any, *, allow_zero: bool = False) -> int | None:
    minimum = 0 if allow_zero else 1
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        return None
    return value


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _finding(code: str, decision: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "decision": decision, "path": path, "message": message}


def _sort_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[tuple[str, str, str], dict[str, str]] = {}
    for finding in findings:
        unique[(finding["code"], finding["path"], finding["message"])] = finding
    return sorted(
        unique.values(),
        key=lambda finding: (
            -DECISION_RANK[finding["decision"]],
            PRIORITY.get(finding["code"], 999),
            finding["code"],
            finding["path"],
        ),
    )


def evaluate(policy: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []

    if policy.get("profile_id") != POLICY_PROFILE:
        findings.append(_finding(
            "DEPLOY_POLICY_INVALID", "BLOCK", "$.policy.profile_id",
            "unsupported deploy-guard policy profile",
        ))
    if evidence.get("profile_id") != EVIDENCE_PROFILE:
        findings.append(_finding(
            "DEPLOY_EVIDENCE_INVALID", "BLOCK", "$.evidence.profile_id",
            "unsupported deploy-action evidence profile",
        ))

    policy_id = _text(policy.get("policy_id"))
    policy_version = _text(policy.get("policy_version"))
    allowed_repositories = _list_of_text(policy.get("allowed_repositories"))
    allowed_environments = _list_of_text(policy.get("allowed_environments"))
    allowed_branches = _list_of_text(policy.get("allowed_branches"))
    allowed_actions = _list_of_text(policy.get("allowed_actions"))
    minimum_approvals = _positive_int(policy.get("minimum_approvals"), allow_zero=True)
    required_roles = _list_of_text(policy.get("required_approval_roles"))
    required_checks = _list_of_text(policy.get("required_checks"))
    maximum_critical = _positive_int(
        policy.get("maximum_critical_vulnerabilities"), allow_zero=True
    )
    require_ticket = policy.get("require_change_ticket")
    require_attestation = policy.get("require_artifact_attestation")
    require_hosted = policy.get("require_github_hosted_runner")

    if (
        policy_id is None
        or policy_version is None
        or allowed_repositories is None
        or allowed_environments is None
        or allowed_branches is None
        or allowed_actions is None
        or minimum_approvals is None
        or required_roles is None
        or required_checks is None
        or maximum_critical is None
        or not isinstance(require_ticket, bool)
        or not isinstance(require_attestation, bool)
        or not isinstance(require_hosted, bool)
    ):
        findings.append(_finding(
            "DEPLOY_POLICY_INVALID", "BLOCK", "$.policy",
            "policy requires explicit allowlists, thresholds, and boolean controls",
        ))

    action_id = _text(evidence.get("action_id"))
    action_type = _text(evidence.get("action_type"))
    agent_id = _text(evidence.get("agent_id"))
    repository = _text(evidence.get("repository"))
    branch = _text(evidence.get("branch"))
    commit_sha = _text(evidence.get("commit_sha"))
    environment = _text(evidence.get("environment"))
    artifact_digest = _text(evidence.get("artifact_digest"))
    evaluated_at = _timestamp(evidence.get("evaluated_at"))

    if (
        None in (action_id, action_type, agent_id, repository, branch, commit_sha,
                 environment, artifact_digest)
        or evaluated_at is None
        or not SHA_RE.fullmatch(commit_sha or "")
        or not DIGEST_RE.fullmatch(artifact_digest or "")
    ):
        findings.append(_finding(
            "DEPLOY_EVIDENCE_INVALID", "BLOCK", "$.evidence",
            "action identity, repository, commit, environment, artifact, and evaluated_at are required",
        ))

    if allowed_repositories is not None and repository not in allowed_repositories:
        findings.append(_finding(
            "DEPLOY_REPOSITORY_NOT_ALLOWED", "BLOCK", "$.evidence.repository",
            "repository is outside the deploy policy allowlist",
        ))
    if allowed_environments is not None and environment not in allowed_environments:
        findings.append(_finding(
            "DEPLOY_ENVIRONMENT_NOT_ALLOWED", "BLOCK", "$.evidence.environment",
            "environment is outside the deploy policy allowlist",
        ))
    if allowed_branches is not None and branch not in allowed_branches:
        findings.append(_finding(
            "DEPLOY_BRANCH_NOT_ALLOWED", "BLOCK", "$.evidence.branch",
            "branch is outside the deploy policy allowlist",
        ))
    if allowed_actions is not None and action_type not in allowed_actions:
        findings.append(_finding(
            "DEPLOY_ACTION_NOT_ALLOWED", "BLOCK", "$.evidence.action_type",
            "action type is outside the deploy policy allowlist",
        ))

    execution = evidence.get("execution")
    if not isinstance(execution, dict) or not isinstance(execution.get("performed"), bool):
        findings.append(_finding(
            "DEPLOY_EVIDENCE_INVALID", "BLOCK", "$.evidence.execution",
            "execution.performed must be an explicit boolean",
        ))
    elif execution.get("performed") is True:
        findings.append(_finding(
            "DEPLOY_ALREADY_EXECUTED", "BLOCK", "$.evidence.execution.performed",
            "Deploy Guard evaluates a proposal before execution and cannot retroactively authorize it",
        ))

    policy_ref = evidence.get("policy")
    if not isinstance(policy_ref, dict):
        findings.append(_finding(
            "DEPLOY_EVIDENCE_INVALID", "BLOCK", "$.evidence.policy",
            "evidence must identify the applied policy",
        ))
    else:
        if policy_ref.get("policy_id") != policy_id:
            findings.append(_finding(
                "DEPLOY_POLICY_ID_MISMATCH", "CHALLENGE", "$.evidence.policy.policy_id",
                "claimed policy id differs from the evaluated policy",
            ))
        if policy_ref.get("policy_version") != policy_version:
            findings.append(_finding(
                "DEPLOY_POLICY_VERSION_MISMATCH", "CHALLENGE", "$.evidence.policy.policy_version",
                "claimed policy version differs from the evaluated policy",
            ))

    authority = evidence.get("authority")
    if not isinstance(authority, dict):
        findings.append(_finding(
            "DEPLOY_EVIDENCE_INVALID", "BLOCK", "$.evidence.authority",
            "authority evidence is required",
        ))
    else:
        if authority.get("active") is not True:
            findings.append(_finding(
                "DEPLOY_AUTHORITY_INACTIVE", "BLOCK", "$.evidence.authority.active",
                "agent authority is not active",
            ))
        expires_at = _timestamp(authority.get("expires_at"))
        if expires_at is None or evaluated_at is None:
            findings.append(_finding(
                "DEPLOY_EVIDENCE_INVALID", "BLOCK", "$.evidence.authority.expires_at",
                "authority expiry must be timezone-aware ISO-8601",
            ))
        elif evaluated_at > expires_at:
            findings.append(_finding(
                "DEPLOY_AUTHORITY_EXPIRED", "BLOCK", "$.evidence.authority.expires_at",
                "agent authority expired before evaluation",
            ))
        scope = authority.get("scope")
        if not isinstance(scope, dict):
            findings.append(_finding(
                "DEPLOY_EVIDENCE_INVALID", "BLOCK", "$.evidence.authority.scope",
                "authority scope is required",
            ))
        else:
            scoped_repositories = _list_of_text(scope.get("repositories")) or []
            scoped_environments = _list_of_text(scope.get("environments")) or []
            scoped_actions = _list_of_text(scope.get("actions")) or []
            if (
                repository not in scoped_repositories
                or environment not in scoped_environments
                or action_type not in scoped_actions
            ):
                findings.append(_finding(
                    "DEPLOY_AUTHORITY_SCOPE_MISMATCH", "BLOCK", "$.evidence.authority.scope",
                    "authority does not cover this repository, environment, and action",
                ))

    provenance = evidence.get("build_provenance")
    if not isinstance(provenance, dict):
        findings.append(_finding(
            "DEPLOY_EVIDENCE_INVALID", "BLOCK", "$.evidence.build_provenance",
            "build provenance is required",
        ))
    else:
        if provenance.get("commit_sha") != commit_sha:
            findings.append(_finding(
                "DEPLOY_PROVENANCE_COMMIT_MISMATCH", "CHALLENGE",
                "$.evidence.build_provenance.commit_sha",
                "build provenance commit differs from the proposed commit",
            ))
        if provenance.get("artifact_digest") != artifact_digest:
            findings.append(_finding(
                "DEPLOY_PROVENANCE_ARTIFACT_MISMATCH", "CHALLENGE",
                "$.evidence.build_provenance.artifact_digest",
                "build provenance artifact differs from the proposed artifact",
            ))
        if require_attestation is True and provenance.get("attestation_verified") is not True:
            findings.append(_finding(
                "DEPLOY_ATTESTATION_UNVERIFIED", "BLOCK",
                "$.evidence.build_provenance.attestation_verified",
                "artifact provenance requires a verified attestation",
            ))
        if require_hosted is True and provenance.get("runner_environment") != "github-hosted":
            findings.append(_finding(
                "DEPLOY_RUNNER_NOT_TRUSTED", "BLOCK",
                "$.evidence.build_provenance.runner_environment",
                "policy requires a GitHub-hosted build runner",
            ))
        for key in ("workflow", "source_sha", "signer_sha"):
            if _text(provenance.get(key)) is None:
                findings.append(_finding(
                    "DEPLOY_EVIDENCE_INVALID", "BLOCK",
                    f"$.evidence.build_provenance.{key}",
                    "workflow, source_sha, and signer_sha must be explicit",
                ))

    checks = evidence.get("checks")
    checks_by_name: dict[str, dict[str, Any]] = {}
    if not isinstance(checks, list):
        findings.append(_finding(
            "DEPLOY_EVIDENCE_INVALID", "BLOCK", "$.evidence.checks",
            "checks must be an array",
        ))
        checks = []
    for index, check in enumerate(checks):
        if not isinstance(check, dict) or _text(check.get("name")) is None:
            findings.append(_finding(
                "DEPLOY_EVIDENCE_INVALID", "BLOCK", f"$.evidence.checks[{index}]",
                "each check requires a name, status, and commit",
            ))
            continue
        name = check["name"]
        if name in checks_by_name:
            findings.append(_finding(
                "DEPLOY_EVIDENCE_INVALID", "BLOCK", f"$.evidence.checks[{index}].name",
                "check names must be unique",
            ))
            continue
        checks_by_name[name] = check
        if check.get("commit_sha") != commit_sha:
            findings.append(_finding(
                "DEPLOY_CHECK_COMMIT_MISMATCH", "CHALLENGE",
                f"$.evidence.checks[{index}].commit_sha",
                "check result is bound to a different commit",
            ))
        status = check.get("status")
        if status in {"failure", "cancelled", "timed_out"}:
            findings.append(_finding(
                "DEPLOY_CHECK_FAILED", "BLOCK", f"$.evidence.checks[{index}].status",
                f"required check {name!r} did not pass",
            ))
        elif status != "success":
            findings.append(_finding(
                "DEPLOY_CHECK_PENDING", "HOLD", f"$.evidence.checks[{index}].status",
                f"check {name!r} has not completed successfully",
            ))

    if required_checks is not None:
        for name in required_checks:
            if name not in checks_by_name:
                findings.append(_finding(
                    "DEPLOY_REQUIRED_CHECK_MISSING", "HOLD", "$.evidence.checks",
                    f"required check {name!r} is missing",
                ))

    security = evidence.get("security")
    if not isinstance(security, dict):
        findings.append(_finding(
            "DEPLOY_EVIDENCE_INVALID", "BLOCK", "$.evidence.security",
            "security evidence is required",
        ))
    else:
        critical = _positive_int(
            security.get("critical_vulnerabilities"), allow_zero=True
        )
        if critical is None:
            findings.append(_finding(
                "DEPLOY_EVIDENCE_INVALID", "BLOCK",
                "$.evidence.security.critical_vulnerabilities",
                "critical vulnerability count must be a non-negative integer",
            ))
        elif maximum_critical is not None and critical > maximum_critical:
            findings.append(_finding(
                "DEPLOY_CRITICAL_VULNERABILITY", "BLOCK",
                "$.evidence.security.critical_vulnerabilities",
                "critical vulnerability threshold is exceeded",
            ))

    approvals = evidence.get("approvals")
    valid_approvals: list[dict[str, Any]] = []
    if not isinstance(approvals, list):
        findings.append(_finding(
            "DEPLOY_EVIDENCE_INVALID", "BLOCK", "$.evidence.approvals",
            "approvals must be an array",
        ))
        approvals = []
    seen_actors: set[str] = set()
    for index, approval in enumerate(approvals):
        if not isinstance(approval, dict):
            findings.append(_finding(
                "DEPLOY_EVIDENCE_INVALID", "BLOCK", f"$.evidence.approvals[{index}]",
                "approval must be an object",
            ))
            continue
        actor = _text(approval.get("actor"))
        role = _text(approval.get("role"))
        if actor is None or role is None or actor in seen_actors:
            findings.append(_finding(
                "DEPLOY_EVIDENCE_INVALID", "BLOCK", f"$.evidence.approvals[{index}]",
                "approval actors must be present and unique and each approval needs a role",
            ))
            continue
        seen_actors.add(actor)
        if approval.get("commit_sha") != commit_sha:
            findings.append(_finding(
                "DEPLOY_APPROVAL_COMMIT_MISMATCH", "CHALLENGE",
                f"$.evidence.approvals[{index}].commit_sha",
                "approval is bound to a different commit",
            ))
        if approval.get("approved") is True:
            valid_approvals.append(approval)

    if minimum_approvals is not None and len(valid_approvals) < minimum_approvals:
        findings.append(_finding(
            "DEPLOY_APPROVAL_COUNT_INSUFFICIENT", "HOLD", "$.evidence.approvals",
            f"{len(valid_approvals)} valid approvals available; {minimum_approvals} required",
        ))
    approved_roles = {approval["role"] for approval in valid_approvals}
    if required_roles is not None:
        for role in required_roles:
            if role not in approved_roles:
                findings.append(_finding(
                    "DEPLOY_APPROVAL_ROLE_MISSING", "HOLD", "$.evidence.approvals",
                    f"required approval role {role!r} is missing",
                ))

    ticket = evidence.get("change_ticket")
    if require_ticket is True:
        if not isinstance(ticket, dict) or _text(ticket.get("id")) is None:
            findings.append(_finding(
                "DEPLOY_CHANGE_TICKET_MISSING", "HOLD", "$.evidence.change_ticket",
                "an approved change ticket is required",
            ))
        else:
            if ticket.get("commit_sha") != commit_sha:
                findings.append(_finding(
                    "DEPLOY_CHANGE_TICKET_COMMIT_MISMATCH", "CHALLENGE",
                    "$.evidence.change_ticket.commit_sha",
                    "change ticket is bound to a different commit",
                ))
            if ticket.get("status") != "approved":
                findings.append(_finding(
                    "DEPLOY_CHANGE_TICKET_PENDING", "HOLD",
                    "$.evidence.change_ticket.status",
                    "change ticket is not approved",
                ))

    findings = _sort_findings(findings)
    primary = findings[0] if findings else None
    decision = primary["decision"] if primary else "ACCEPT"

    certificate: dict[str, Any] = {
        "profile_id": CERTIFICATE_PROFILE,
        "product": PRODUCT,
        "certificate_version": "0.1",
        "decision": decision,
        "valid": decision == "ACCEPT",
        "primary_reason_code": primary["code"] if primary else None,
        "reason_codes": sorted({finding["code"] for finding in findings}),
        "findings": findings,
        "action": {
            "action_id": action_id,
            "action_type": action_type,
            "agent_id": agent_id,
            "repository": repository,
            "branch": branch,
            "commit_sha": commit_sha,
            "environment": environment,
            "artifact_digest": artifact_digest,
        },
        "assurance": {
            "assurance_level": "POLICY_VERIFIED",
            "witness_level": "SINGLE_WORKFLOW_REFERENCE",
            "coverage": "NOT_FINANCIALLY_COVERED",
            "policy_id": policy_id,
            "policy_version": policy_version,
            "approved_witness_count": 1,
            "external_quorum_verified": False,
        },
        "facts": {
            "authority_active": (
                authority.get("active") is True if isinstance(authority, dict) else False
            ),
            "artifact_attestation_verified": (
                provenance.get("attestation_verified") is True
                if isinstance(provenance, dict) else False
            ),
            "successful_check_count": sum(
                1 for check in checks_by_name.values() if check.get("status") == "success"
            ),
            "valid_approval_count": len(valid_approvals),
            "approved_change_ticket": (
                ticket.get("status") == "approved" if isinstance(ticket, dict) else False
            ),
            "execution_observed": (
                execution.get("performed") is True if isinstance(execution, dict) else False
            ),
        },
        "policy_root": digest(POLICY_DOMAIN, policy),
        "evidence_root": digest(EVIDENCE_DOMAIN, evidence),
        "clearance_root": None,
        "execution_allowed": decision == "ACCEPT",
        "authority_granted": False,
        "permitted_next_transition": {
            "ACCEPT": "DEPLOY_TO_PRODUCTION",
            "HOLD": "WAIT_FOR_REQUIRED_EVIDENCE",
            "BLOCK": "REPAIR_POLICY_OR_SAFETY_FAILURE",
            "CHALLENGE": "INVESTIGATE_CONFLICTING_EVIDENCE",
        }[decision],
        "limitations": [
            "this certificate evaluates supplied observable evidence and does not expose model thoughts",
            "this reference demo uses one signer workflow and does not claim an external witness quorum",
            "this certificate provides no financial guarantee or insurance coverage",
            "this certificate does not execute the deployment or grant authority beyond the evaluated action",
        ],
    }
    certificate["clearance_root"] = digest(CLEARANCE_DOMAIN, certificate)
    return certificate


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", type=Path)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        certificate = evaluate(load_json(args.policy), load_json(args.evidence))
        code = EXIT_CODE[certificate["decision"]]
    except (EvidenceError, OSError, TypeError, KeyError) as exc:
        certificate = {
            "profile_id": CERTIFICATE_PROFILE,
            "product": PRODUCT,
            "decision": "BLOCK",
            "valid": False,
            "primary_reason_code": "DEPLOY_EVIDENCE_INVALID",
            "reason_codes": ["DEPLOY_EVIDENCE_INVALID"],
            "error": str(exc),
            "execution_allowed": False,
            "authority_granted": False,
            "permitted_next_transition": "REPAIR_POLICY_OR_SAFETY_FAILURE",
        }
        code = 3

    text = (
        json.dumps(certificate, indent=2, ensure_ascii=False)
        if args.pretty
        else json.dumps(certificate, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
