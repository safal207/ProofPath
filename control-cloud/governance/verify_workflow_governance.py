#!/usr/bin/env python3
"""Trusted Workflow Governance v0.1 for ProofPath Control Cloud.

Cryptographic provenance answers who signed exact bytes. Governance answers whether
that exact workflow identity and signer commit are trusted at the observation time.
This module is read-only: it emits decisions and revocation proposals, never mutates
repositories, branch protection, IAM, deployments, or payments.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[2]


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


admission = _load_module(
    "proofpath_sigstore_admission_governance",
    REPO_ROOT / "control-cloud/admission/verify_sigstore.py",
)

REGISTRY_PROFILE = "proofpath.control-cloud.workflow-governance-registry.v0.1"
DECISION_PROFILE = "proofpath.control-cloud.workflow-governance-decision.v0.1"
PROPOSAL_PROFILE = "proofpath.control-cloud.workflow-revocation-proposal.v0.1"
DECISION_DOMAIN = DECISION_PROFILE + ".root"
PROPOSAL_DOMAIN = PROPOSAL_PROFILE + ".root"
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
WORKFLOW_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml$")


class GovernanceError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_loads(data: bytes | str) -> Any:
    text = data.decode("utf-8") if isinstance(data, bytes) else data
    return json.loads(text, object_pairs_hook=_reject_duplicate, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise GovernanceError("FILE_UNAVAILABLE", f"{path} must be a regular non-symlink file")
    value = strict_loads(path.read_bytes())
    if not isinstance(value, dict):
        raise GovernanceError("INVALID_JSON_OBJECT", f"{path} must contain one object")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def domain_hash(domain: str, value: Any) -> str:
    payload = domain.encode("utf-8") + b"\x00" + canonical_bytes(value)
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def raw_digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def parse_utc(value: Any, field: str) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise GovernanceError("INVALID_TIME", f"{field} must be RFC3339 UTC")
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise GovernanceError("INVALID_TIME", f"{field} must be RFC3339 UTC") from exc
    if parsed.tzinfo != dt.timezone.utc or parsed.microsecond:
        raise GovernanceError("INVALID_TIME", f"{field} must be second-precision UTC")
    return parsed


def format_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def exact_keys(value: dict[str, Any], required: set[str], field: str) -> None:
    if set(value) != required:
        missing = sorted(required - set(value))
        extra = sorted(set(value) - required)
        raise GovernanceError("INVALID_SHAPE", f"{field} keys differ; missing={missing}, extra={extra}")


def require_text(value: Any, field: str, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value or (pattern and not pattern.fullmatch(value)):
        raise GovernanceError("INVALID_FIELD", f"{field} is invalid")
    return value


def require_digest(value: Any, field: str) -> str:
    return require_text(value, field, DIGEST_RE)


def require_sha(value: Any, field: str) -> str:
    return require_text(value, field, SHA_RE)


def require_string_list(value: Any, field: str, *, min_items: int = 1) -> list[str]:
    if not isinstance(value, list) or len(value) < min_items or not all(isinstance(item, str) and item for item in value):
        raise GovernanceError("INVALID_FIELD", f"{field} must be a non-empty string array")
    if len(set(value)) != len(value):
        raise GovernanceError("INVALID_FIELD", f"{field} must not contain duplicates")
    return value


def validate_record(value: dict[str, Any]) -> dict[str, Any]:
    required = {
        "record_id", "status", "repository", "owner_scope", "workflow", "signer_sha",
        "workflow_file_digest", "allowed_event_types", "allowed_ref_prefixes", "reviewer_quorum",
        "effective_at", "expires_at", "review_ticket", "authority_granted",
    }
    exact_keys(value, required, "governance record")
    require_text(value["record_id"], "record.record_id", ID_RE)
    if value["status"] not in {"ACTIVE", "SUSPENDED", "REVOKED"}:
        raise GovernanceError("INVALID_STATUS", "record.status is unsupported")
    repository = require_text(value["repository"], "record.repository", REPO_RE)
    owner, _ = repository.split("/", 1)
    if value["owner_scope"] != owner:
        raise GovernanceError("OWNER_SCOPE_CONFLICT", "owner_scope must equal repository owner")
    workflow = require_text(value["workflow"], "record.workflow", WORKFLOW_RE)
    if not workflow.startswith(repository + "/.github/workflows/"):
        raise GovernanceError("WORKFLOW_REPOSITORY_CONFLICT", "workflow must belong to repository")
    require_sha(value["signer_sha"], "record.signer_sha")
    require_digest(value["workflow_file_digest"], "record.workflow_file_digest")
    require_string_list(value["allowed_event_types"], "record.allowed_event_types")
    require_string_list(value["allowed_ref_prefixes"], "record.allowed_ref_prefixes")
    quorum = value["reviewer_quorum"]
    if not isinstance(quorum, dict):
        raise GovernanceError("INVALID_QUORUM", "reviewer_quorum must be an object")
    exact_keys(quorum, {"required", "reviewers", "approvals"}, "reviewer_quorum")
    required_count = quorum["required"]
    if isinstance(required_count, bool) or not isinstance(required_count, int) or required_count < 1:
        raise GovernanceError("INVALID_QUORUM", "reviewer_quorum.required must be >= 1")
    reviewers = require_string_list(quorum["reviewers"], "reviewer_quorum.reviewers")
    approvals = require_string_list(quorum["approvals"], "reviewer_quorum.approvals", min_items=0)
    if not set(approvals).issubset(reviewers) or required_count > len(reviewers):
        raise GovernanceError("INVALID_QUORUM", "approvals must be reviewers and required cannot exceed reviewer count")
    effective = parse_utc(value["effective_at"], "record.effective_at")
    expires = parse_utc(value["expires_at"], "record.expires_at")
    if effective >= expires:
        raise GovernanceError("INVALID_WINDOW", "record trust window is empty")
    require_text(value["review_ticket"], "record.review_ticket")
    if value["authority_granted"] is not False:
        raise GovernanceError("AUTHORITY_BOUNDARY_VIOLATION", "governance record cannot grant authority")
    return value


def validate_revocation(value: dict[str, Any]) -> dict[str, Any]:
    required = {"revocation_id", "record_id", "effective_at", "reason_code", "approved_by", "authority_granted"}
    exact_keys(value, required, "revocation")
    require_text(value["revocation_id"], "revocation.revocation_id", ID_RE)
    require_text(value["record_id"], "revocation.record_id", ID_RE)
    parse_utc(value["effective_at"], "revocation.effective_at")
    require_text(value["reason_code"], "revocation.reason_code", ID_RE)
    require_string_list(value["approved_by"], "revocation.approved_by")
    if value["authority_granted"] is not False:
        raise GovernanceError("AUTHORITY_BOUNDARY_VIOLATION", "revocation cannot grant authority")
    return value


def validate_registry(value: dict[str, Any]) -> dict[str, Any]:
    exact_keys(value, {"profile_id", "generated_at", "records", "revocations"}, "registry")
    if value["profile_id"] != REGISTRY_PROFILE:
        raise GovernanceError("UNSUPPORTED_REGISTRY", "unsupported governance registry profile")
    parse_utc(value["generated_at"], "registry.generated_at")
    if not isinstance(value["records"], list) or not value["records"]:
        raise GovernanceError("EMPTY_REGISTRY", "registry.records must be non-empty")
    if not isinstance(value["revocations"], list):
        raise GovernanceError("INVALID_REGISTRY", "registry.revocations must be an array")
    records = [validate_record(record) if isinstance(record, dict) else (_ for _ in ()).throw(GovernanceError("INVALID_RECORD", "record must be an object")) for record in value["records"]]
    revocations = [validate_revocation(item) if isinstance(item, dict) else (_ for _ in ()).throw(GovernanceError("INVALID_REVOCATION", "revocation must be an object")) for item in value["revocations"]]
    record_ids = [record["record_id"] for record in records]
    if len(set(record_ids)) != len(record_ids):
        raise GovernanceError("DUPLICATE_RECORD", "record_id values must be unique")
    known = set(record_ids)
    if any(item["record_id"] not in known for item in revocations):
        raise GovernanceError("ORPHAN_REVOCATION", "revocation references unknown record")
    return value


def _decision_without_root(value: dict[str, Any]) -> dict[str, Any]:
    copy = dict(value)
    copy["decision_root"] = None
    return copy


def validate_decision(value: dict[str, Any]) -> dict[str, Any]:
    required = {
        "profile_id", "decision", "reason_code", "governance_trust_verified", "observed_at",
        "repository", "signer_repository", "signer_workflow", "signer_sha", "workflow_file_digest",
        "event_type", "ref", "admission_result_root", "subject_digest", "trust_record_id",
        "trust_record_root", "reviewer_quorum_verified", "trust_window_verified", "revocation_checked",
        "owner_scope_verified", "authority_granted", "repository_write_performed", "deployment_performed",
        "payments_executed", "decision_root",
    }
    exact_keys(value, required, "governance decision")
    if value["profile_id"] != DECISION_PROFILE or value["decision"] not in {"ACCEPT", "HOLD", "BLOCK", "CHALLENGE"}:
        raise GovernanceError("INVALID_DECISION", "governance decision is unsupported")
    accepted = value["decision"] == "ACCEPT"
    if value["governance_trust_verified"] is not accepted:
        raise GovernanceError("DECISION_CONFLICT", "trust flag conflicts with decision")
    if accepted and value["reason_code"] is not None:
        raise GovernanceError("DECISION_CONFLICT", "ACCEPT cannot carry reason_code")
    if not accepted:
        require_text(value["reason_code"], "decision.reason_code", ID_RE)
    parse_utc(value["observed_at"], "decision.observed_at")
    require_text(value["repository"], "decision.repository", REPO_RE)
    require_text(value["signer_repository"], "decision.signer_repository", REPO_RE)
    require_text(value["signer_workflow"], "decision.signer_workflow", WORKFLOW_RE)
    require_sha(value["signer_sha"], "decision.signer_sha")
    require_digest(value["workflow_file_digest"], "decision.workflow_file_digest")
    require_text(value["event_type"], "decision.event_type")
    require_text(value["ref"], "decision.ref")
    require_digest(value["admission_result_root"], "decision.admission_result_root")
    require_digest(value["subject_digest"], "decision.subject_digest")
    if accepted:
        require_text(value["trust_record_id"], "decision.trust_record_id", ID_RE)
        require_digest(value["trust_record_root"], "decision.trust_record_root")
        for field in ("reviewer_quorum_verified", "trust_window_verified", "revocation_checked", "owner_scope_verified"):
            if value[field] is not True:
                raise GovernanceError("DECISION_CONFLICT", f"{field} must be true for ACCEPT")
    else:
        if value["trust_record_id"] is not None or value["trust_record_root"] is not None:
            require_text(value["trust_record_id"], "decision.trust_record_id", ID_RE)
            require_digest(value["trust_record_root"], "decision.trust_record_root")
    for field in ("authority_granted", "repository_write_performed", "deployment_performed", "payments_executed"):
        if value[field] is not False:
            raise GovernanceError("BOUNDARY_VIOLATION", f"decision.{field} must be false")
    expected = domain_hash(DECISION_DOMAIN, _decision_without_root(value))
    if value["decision_root"] != expected:
        raise GovernanceError("DECISION_ROOT_MISMATCH", "governance decision root is invalid")
    return value


def _make_decision(*, admission_result: dict[str, Any], observed_at: str, workflow_file_digest: str,
                   event_type: str, ref: str, decision: str, reason_code: str | None,
                   record: dict[str, Any] | None, reviewer_ok: bool, window_ok: bool,
                   revocation_ok: bool, owner_ok: bool) -> dict[str, Any]:
    trust_root = domain_hash(REGISTRY_PROFILE + ".record", record) if record else None
    value: dict[str, Any] = {
        "profile_id": DECISION_PROFILE,
        "decision": decision,
        "reason_code": reason_code,
        "governance_trust_verified": decision == "ACCEPT",
        "observed_at": observed_at,
        "repository": admission_result["repository"],
        "signer_repository": admission_result["signer_repository"],
        "signer_workflow": admission_result["signer_workflow"],
        "signer_sha": admission_result["signer_sha"],
        "workflow_file_digest": workflow_file_digest,
        "event_type": event_type,
        "ref": ref,
        "admission_result_root": admission_result["result_root"],
        "subject_digest": admission_result["subject_digest"],
        "trust_record_id": record["record_id"] if record else None,
        "trust_record_root": trust_root,
        "reviewer_quorum_verified": reviewer_ok,
        "trust_window_verified": window_ok,
        "revocation_checked": revocation_ok,
        "owner_scope_verified": owner_ok,
        "authority_granted": False,
        "repository_write_performed": False,
        "deployment_performed": False,
        "payments_executed": False,
        "decision_root": None,
    }
    value["decision_root"] = domain_hash(DECISION_DOMAIN, _decision_without_root(value))
    return value


def evaluate(*, admission_result: dict[str, Any], registry: dict[str, Any], observed_at: str,
             workflow_file_digest: str, event_type: str, ref: str) -> dict[str, Any]:
    admission_result = admission.validate_result(admission_result)
    registry = validate_registry(registry)
    now = parse_utc(observed_at, "observed_at")
    require_digest(workflow_file_digest, "workflow_file_digest")
    require_text(event_type, "event_type")
    require_text(ref, "ref")

    candidates = [record for record in registry["records"] if record["repository"] == admission_result["repository"] and record["workflow"] == admission_result["signer_workflow"]]
    if not candidates:
        return _make_decision(admission_result=admission_result, observed_at=observed_at, workflow_file_digest=workflow_file_digest, event_type=event_type, ref=ref, decision="HOLD", reason_code="missing_trust_record", record=None, reviewer_ok=False, window_ok=False, revocation_ok=False, owner_ok=False)
    exact = [record for record in candidates if record["signer_sha"] == admission_result["signer_sha"]]
    if not exact:
        record = candidates[0]
        return _make_decision(admission_result=admission_result, observed_at=observed_at, workflow_file_digest=workflow_file_digest, event_type=event_type, ref=ref, decision="BLOCK", reason_code="signer_sha_not_pinned", record=record, reviewer_ok=False, window_ok=False, revocation_ok=False, owner_ok=True)
    if len(exact) != 1:
        return _make_decision(admission_result=admission_result, observed_at=observed_at, workflow_file_digest=workflow_file_digest, event_type=event_type, ref=ref, decision="CHALLENGE", reason_code="ambiguous_trust_record", record=exact[0], reviewer_ok=False, window_ok=False, revocation_ok=False, owner_ok=True)
    record = exact[0]
    owner_ok = record["owner_scope"] == admission_result["repository"].split("/", 1)[0] and admission_result["signer_repository"] == record["repository"]
    if not owner_ok:
        return _make_decision(admission_result=admission_result, observed_at=observed_at, workflow_file_digest=workflow_file_digest, event_type=event_type, ref=ref, decision="BLOCK", reason_code="owner_scope_conflict", record=record, reviewer_ok=False, window_ok=False, revocation_ok=False, owner_ok=False)
    if record["status"] != "ACTIVE":
        return _make_decision(admission_result=admission_result, observed_at=observed_at, workflow_file_digest=workflow_file_digest, event_type=event_type, ref=ref, decision="BLOCK", reason_code="trust_record_not_active", record=record, reviewer_ok=False, window_ok=False, revocation_ok=False, owner_ok=True)
    window_ok = parse_utc(record["effective_at"], "effective_at") <= now < parse_utc(record["expires_at"], "expires_at")
    if not window_ok:
        return _make_decision(admission_result=admission_result, observed_at=observed_at, workflow_file_digest=workflow_file_digest, event_type=event_type, ref=ref, decision="HOLD", reason_code="trust_window_inactive", record=record, reviewer_ok=False, window_ok=False, revocation_ok=False, owner_ok=True)
    active_revocations = [item for item in registry["revocations"] if item["record_id"] == record["record_id"] and parse_utc(item["effective_at"], "revocation.effective_at") <= now]
    if active_revocations:
        return _make_decision(admission_result=admission_result, observed_at=observed_at, workflow_file_digest=workflow_file_digest, event_type=event_type, ref=ref, decision="BLOCK", reason_code="trust_record_revoked", record=record, reviewer_ok=False, window_ok=True, revocation_ok=False, owner_ok=True)
    if workflow_file_digest != record["workflow_file_digest"]:
        return _make_decision(admission_result=admission_result, observed_at=observed_at, workflow_file_digest=workflow_file_digest, event_type=event_type, ref=ref, decision="BLOCK", reason_code="workflow_digest_mutated", record=record, reviewer_ok=False, window_ok=True, revocation_ok=True, owner_ok=True)
    if event_type not in record["allowed_event_types"]:
        return _make_decision(admission_result=admission_result, observed_at=observed_at, workflow_file_digest=workflow_file_digest, event_type=event_type, ref=ref, decision="BLOCK", reason_code="event_type_not_allowed", record=record, reviewer_ok=False, window_ok=True, revocation_ok=True, owner_ok=True)
    if not any(ref.startswith(prefix) for prefix in record["allowed_ref_prefixes"]):
        return _make_decision(admission_result=admission_result, observed_at=observed_at, workflow_file_digest=workflow_file_digest, event_type=event_type, ref=ref, decision="BLOCK", reason_code="ref_not_allowed", record=record, reviewer_ok=False, window_ok=True, revocation_ok=True, owner_ok=True)
    quorum = record["reviewer_quorum"]
    reviewer_ok = len(set(quorum["approvals"])) >= quorum["required"]
    if not reviewer_ok:
        return _make_decision(admission_result=admission_result, observed_at=observed_at, workflow_file_digest=workflow_file_digest, event_type=event_type, ref=ref, decision="HOLD", reason_code="reviewer_quorum_missing", record=record, reviewer_ok=False, window_ok=True, revocation_ok=True, owner_ok=True)
    result = _make_decision(admission_result=admission_result, observed_at=observed_at, workflow_file_digest=workflow_file_digest, event_type=event_type, ref=ref, decision="ACCEPT", reason_code=None, record=record, reviewer_ok=True, window_ok=True, revocation_ok=True, owner_ok=True)
    return validate_decision(result)


def _proposal_without_root(value: dict[str, Any]) -> dict[str, Any]:
    copy = dict(value)
    copy["proposal_root"] = None
    return copy


def check_change(*, registry: dict[str, Any], workflow: str, observed_signer_sha: str,
                 observed_file_digest: str, changed_paths: list[str], observed_at: str) -> dict[str, Any]:
    registry = validate_registry(registry)
    require_text(workflow, "workflow", WORKFLOW_RE)
    require_sha(observed_signer_sha, "observed_signer_sha")
    require_digest(observed_file_digest, "observed_file_digest")
    parse_utc(observed_at, "observed_at")
    if not isinstance(changed_paths, list) or not all(isinstance(path, str) and path for path in changed_paths):
        raise GovernanceError("INVALID_CHANGED_PATHS", "changed_paths must be a string array")
    records = [record for record in registry["records"] if record["workflow"] == workflow and record["status"] == "ACTIVE"]
    record = records[0] if len(records) == 1 else None
    path = str(PurePosixPath(*workflow.split("/")[2:]))
    changed = path in changed_paths
    mismatch = record is None or record["signer_sha"] != observed_signer_sha or record["workflow_file_digest"] != observed_file_digest
    proposal = {
        "profile_id": PROPOSAL_PROFILE,
        "decision": "PROPOSE_REVOKE" if changed or mismatch else "NO_CHANGE",
        "reason_code": "trusted_workflow_changed" if changed else ("trusted_workflow_identity_mismatch" if mismatch else None),
        "observed_at": observed_at,
        "workflow": workflow,
        "record_id": record["record_id"] if record else None,
        "observed_signer_sha": observed_signer_sha,
        "observed_file_digest": observed_file_digest,
        "changed_paths": sorted(changed_paths),
        "repository_write_performed": False,
        "authority_granted": False,
        "proposal_root": None,
    }
    proposal["proposal_root"] = domain_hash(PROPOSAL_DOMAIN, _proposal_without_root(proposal))
    return proposal


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value) + b"\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    evaluate_parser = commands.add_parser("evaluate")
    evaluate_parser.add_argument("--admission-result", required=True, type=Path)
    evaluate_parser.add_argument("--registry", required=True, type=Path)
    evaluate_parser.add_argument("--observed-at", required=True)
    evaluate_parser.add_argument("--workflow-file-digest", required=True)
    evaluate_parser.add_argument("--event-type", required=True)
    evaluate_parser.add_argument("--ref", required=True)
    evaluate_parser.add_argument("--output", required=True, type=Path)
    validate_parser = commands.add_parser("validate-decision")
    validate_parser.add_argument("--decision", required=True, type=Path)
    change_parser = commands.add_parser("check-change")
    change_parser.add_argument("--registry", required=True, type=Path)
    change_parser.add_argument("--workflow", required=True)
    change_parser.add_argument("--observed-signer-sha", required=True)
    change_parser.add_argument("--observed-file-digest", required=True)
    change_parser.add_argument("--changed-paths", required=True, type=Path)
    change_parser.add_argument("--observed-at", required=True)
    change_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "evaluate":
            result = evaluate(
                admission_result=load_json(args.admission_result),
                registry=load_json(args.registry),
                observed_at=args.observed_at,
                workflow_file_digest=args.workflow_file_digest,
                event_type=args.event_type,
                ref=args.ref,
            )
            validate_decision(result)
            write_json(args.output, result)
            print(f"ProofPath workflow governance: {result['decision']} / {result['decision_root']}", file=sys.stderr)
            return 0 if result["decision"] == "ACCEPT" else 2
        if args.command == "validate-decision":
            result = validate_decision(load_json(args.decision))
            print(f"ProofPath governance decision valid: {result['decision_root']}")
            return 0
        changed = strict_loads(args.changed_paths.read_bytes())
        proposal = check_change(
            registry=load_json(args.registry),
            workflow=args.workflow,
            observed_signer_sha=args.observed_signer_sha,
            observed_file_digest=args.observed_file_digest,
            changed_paths=changed,
            observed_at=args.observed_at,
        )
        write_json(args.output, proposal)
        print(f"ProofPath governance change check: {proposal['decision']} / {proposal['proposal_root']}", file=sys.stderr)
        return 2 if proposal["decision"] == "PROPOSE_REVOKE" else 0
    except (GovernanceError, admission.AdmissionError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        code = exc.code if hasattr(exc, "code") else "GOVERNANCE_INTERNAL_ERROR"
        message = exc.message if hasattr(exc, "message") else str(exc)
        print(f"ProofPath workflow governance failed: {code}: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
