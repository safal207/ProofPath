#!/usr/bin/env python3
"""Reviewer-separation-gated ProofPath Control Cloud ingestion.

This highest-assurance reference entrypoint requires:
1. authenticated tenant request;
2. server-controlled Sigstore admission ACCEPT;
3. server-controlled workflow-governance ACCEPT;
4. server-controlled reviewer identity and separation-of-duties ACCEPT.

Only then does it delegate to the append-only governed ingestion runtime.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


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
base = _load_module("proofpath_ingestion_separated_base", REPO_ROOT / "control-cloud/ingestion/ingest.py")
admitted = _load_module("proofpath_admitted_ingestion_separated", REPO_ROOT / "control-cloud/ingestion/admitted_ingest.py")
governed = _load_module("proofpath_governed_ingestion_separated", REPO_ROOT / "control-cloud/ingestion/governed_ingest.py")
reviewers = _load_module(
    "proofpath_reviewer_identity_separation_ingestion",
    REPO_ROOT / "control-cloud/reviewers/verify_reviewer_separation.py",
)

RECEIPT_PROFILE = "proofpath.control-cloud.separated-ingest-receipt.v0.1"
RECEIPT_DOMAIN = RECEIPT_PROFILE + ".root"


class SeparatedIngestError(base.IngestError):
    """Reviewer-separation-gated ingestion error."""


def reviewer_decision_file(separation_dir: Path, governance_decision_root: str) -> Path:
    reviewers.require_digest(governance_decision_root, "governance_decision_root")
    root = separation_dir.resolve()
    candidate = root / (governance_decision_root.split(":", 1)[1] + ".json")
    if candidate.is_symlink():
        raise SeparatedIngestError("REVIEWER_DECISION_SYMLINK_REJECTED", "reviewer decision must not be a symlink", 500)
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SeparatedIngestError("REVIEWER_DECISION_PATH_ESCAPE", "reviewer decision escapes trusted directory", 500) from exc
    if not resolved.is_file():
        raise SeparatedIngestError("REVIEWER_DECISION_NOT_FOUND", "trusted reviewer separation decision is unavailable", 422)
    return resolved


def load_bound_reviewer_decision(
    *,
    governance_decision: dict[str, Any],
    separation_dir: Path,
    now: dt.datetime,
) -> dict[str, Any]:
    path = reviewer_decision_file(separation_dir, governance_decision["decision_root"])
    try:
        decision = reviewers.validate_decision(reviewers.load_json(path))
    except reviewers.ReviewerSeparationError as exc:
        raise SeparatedIngestError("REVIEWER_DECISION_INVALID", f"{exc.code}: {exc.message}", 422) from exc
    if decision["decision"] != "ACCEPT" or decision["separation_of_duties_verified"] is not True:
        raise SeparatedIngestError("REVIEWER_SEPARATION_REQUIRED", "reviewer separation decision is not ACCEPT", 422)
    checks = [
        (decision["governance_decision_root"], governance_decision["decision_root"], "governance decision root"),
        (decision["admission_result_root"], governance_decision["admission_result_root"], "admission result root"),
        (decision["workflow"], governance_decision["signer_workflow"], "workflow"),
        (decision["signer_sha"], governance_decision["signer_sha"], "signer SHA"),
    ]
    for actual, expected, label in checks:
        if actual != expected:
            raise SeparatedIngestError("REVIEWER_DECISION_BINDING_CONFLICT", f"reviewer {label} differs", 422)
    observed = reviewers.parse_utc(decision["observed_at"], "decision.observed_at")
    if observed > now or now - observed > dt.timedelta(minutes=15):
        raise SeparatedIngestError("REVIEWER_DECISION_STALE", "reviewer decision is future-dated or older than 15 minutes", 422)
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
        if decision[field] is not True:
            raise SeparatedIngestError("REVIEWER_ASSURANCE_INCOMPLETE", f"{field} is not verified", 422)
    if decision["verified_reviewer_count"] < 1 or decision["verified_organization_count"] < 1:
        raise SeparatedIngestError("REVIEWER_ASSURANCE_INCOMPLETE", "reviewer counts are empty", 422)
    return decision


def _receipt_without_root(value: dict[str, Any]) -> dict[str, Any]:
    copy = dict(value)
    copy["receipt_root"] = None
    return copy


def validate_receipt(value: dict[str, Any]) -> dict[str, Any]:
    required = {
        "profile_id",
        "status",
        "tenant_id",
        "request_id",
        "action_id",
        "decision",
        "content_digest",
        "admitted_event_root",
        "admission_result_root",
        "governance_decision_root",
        "reviewer_separation_decision_root",
        "trust_record_root",
        "identity_registry_digest",
        "approval_bundle_digest",
        "verified_reviewer_count",
        "verified_organization_count",
        "subject_digest",
        "stored_at",
        "governed_receipt_root",
        "provenance_cryptographically_verified_by_api",
        "governance_trust_verified_by_api",
        "reviewer_identity_verified_by_api",
        "separation_of_duties_verified_by_api",
        "financial_status",
        "payments_executed",
        "insurance_provided",
        "deployment_performed",
        "authority_granted",
        "repository_write_performed",
        "receipt_root",
    }
    if set(value) != required or value.get("profile_id") != RECEIPT_PROFILE:
        raise SeparatedIngestError("INVALID_SEPARATED_RECEIPT", "separated receipt shape is invalid", 500)
    if value["status"] != "ACCEPTED_WITH_PROVENANCE_GOVERNANCE_AND_REVIEWER_SEPARATION":
        raise SeparatedIngestError("INVALID_SEPARATED_RECEIPT", "separated receipt status is invalid", 500)
    for field in (
        "provenance_cryptographically_verified_by_api",
        "governance_trust_verified_by_api",
        "reviewer_identity_verified_by_api",
        "separation_of_duties_verified_by_api",
    ):
        if value[field] is not True:
            raise SeparatedIngestError("INVALID_SEPARATED_RECEIPT", f"{field} must be true", 500)
    for field in (
        "payments_executed",
        "insurance_provided",
        "deployment_performed",
        "authority_granted",
        "repository_write_performed",
    ):
        if value[field] is not False:
            raise SeparatedIngestError("BOUNDARY_VIOLATION", f"receipt.{field} must be false", 500)
    for field in (
        "content_digest",
        "admitted_event_root",
        "admission_result_root",
        "governance_decision_root",
        "reviewer_separation_decision_root",
        "trust_record_root",
        "identity_registry_digest",
        "approval_bundle_digest",
        "subject_digest",
        "governed_receipt_root",
        "receipt_root",
    ):
        reviewers.require_digest(value[field], f"receipt.{field}")
    for field in ("verified_reviewer_count", "verified_organization_count"):
        reviewers.require_int(value[field], f"receipt.{field}", 1)
    reviewers.parse_utc(value["stored_at"], "receipt.stored_at")
    expected = reviewers.domain_hash(RECEIPT_DOMAIN, _receipt_without_root(value))
    if value["receipt_root"] != expected:
        raise SeparatedIngestError("SEPARATED_RECEIPT_ROOT_MISMATCH", "separated receipt root is invalid", 500)
    return value


def ingest_separated_request(
    *,
    body: bytes,
    headers: Mapping[str, Any],
    tenant_from_path: str,
    registry: dict[str, Any],
    store_root: Path,
    admissions_dir: Path,
    governance_dir: Path,
    separation_dir: Path,
    now: dt.datetime,
) -> tuple[dict[str, Any], bool]:
    if now.tzinfo != dt.timezone.utc:
        raise SeparatedIngestError("INVALID_SERVER_TIME", "server time must be UTC", 500)
    request = base.validate_request(base.strict_loads(body))
    auth = base.AuthHeaders.from_mapping(headers)
    base.verify_authentication(
        body=body,
        request=request,
        tenant_from_path=tenant_from_path,
        auth=auth,
        registry=registry,
        now=now,
        clock_skew_seconds=base.DEFAULT_CLOCK_SKEW_SECONDS,
    )
    admission_result = admitted.load_bound_admission_result(request, admissions_dir)
    governance_decision = governed.load_bound_governance_decision(
        admission_result=admission_result,
        governance_dir=governance_dir,
        now=now,
    )
    reviewer_decision = load_bound_reviewer_decision(
        governance_decision=governance_decision,
        separation_dir=separation_dir,
        now=now,
    )
    governed_receipt, replay = governed.ingest_governed_request(
        body=body,
        headers=headers,
        tenant_from_path=tenant_from_path,
        registry=registry,
        store_root=store_root,
        admissions_dir=admissions_dir,
        governance_dir=governance_dir,
        now=now,
    )
    receipt: dict[str, Any] = {
        "profile_id": RECEIPT_PROFILE,
        "status": "ACCEPTED_WITH_PROVENANCE_GOVERNANCE_AND_REVIEWER_SEPARATION",
        "tenant_id": governed_receipt["tenant_id"],
        "request_id": governed_receipt["request_id"],
        "action_id": governed_receipt["action_id"],
        "decision": governed_receipt["decision"],
        "content_digest": governed_receipt["content_digest"],
        "admitted_event_root": governed_receipt["admitted_event_root"],
        "admission_result_root": governed_receipt["admission_result_root"],
        "governance_decision_root": governed_receipt["governance_decision_root"],
        "reviewer_separation_decision_root": reviewer_decision["decision_root"],
        "trust_record_root": governed_receipt["trust_record_root"],
        "identity_registry_digest": reviewer_decision["identity_registry_digest"],
        "approval_bundle_digest": reviewer_decision["approval_bundle_digest"],
        "verified_reviewer_count": reviewer_decision["verified_reviewer_count"],
        "verified_organization_count": reviewer_decision["verified_organization_count"],
        "subject_digest": governed_receipt["subject_digest"],
        "stored_at": governed_receipt["stored_at"],
        "governed_receipt_root": governed_receipt["receipt_root"],
        "provenance_cryptographically_verified_by_api": True,
        "governance_trust_verified_by_api": True,
        "reviewer_identity_verified_by_api": True,
        "separation_of_duties_verified_by_api": True,
        "financial_status": "RECORDED_NOT_PAYABLE",
        "payments_executed": False,
        "insurance_provided": False,
        "deployment_performed": False,
        "authority_granted": False,
        "repository_write_performed": False,
        "receipt_root": None,
    }
    receipt["receipt_root"] = reviewers.domain_hash(RECEIPT_DOMAIN, _receipt_without_root(receipt))
    return validate_receipt(receipt), replay


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(reviewers.canonical_bytes(value) + b"\n")


def load_headers(path: Path) -> dict[str, str]:
    value = base.strict_loads(path.read_bytes())
    if not isinstance(value, dict) or not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
        raise SeparatedIngestError("INVALID_HEADER_FILE", "header file must be a string map", 400)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body", required=True, type=Path)
    parser.add_argument("--headers", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--admissions-dir", required=True, type=Path)
    parser.add_argument("--governance-dir", required=True, type=Path)
    parser.add_argument("--separation-dir", required=True, type=Path)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--now", required=True)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        receipt, replay = ingest_separated_request(
            body=args.body.read_bytes(),
            headers=load_headers(args.headers),
            tenant_from_path=args.tenant,
            registry=base.load_registry(args.registry),
            store_root=args.store,
            admissions_dir=args.admissions_dir,
            governance_dir=args.governance_dir,
            separation_dir=args.separation_dir,
            now=base.parse_utc(args.now, "now"),
        )
        write_json(args.receipt, receipt)
        print(
            f"ProofPath separated ingestion: {'IDEMPOTENT_REPLAY' if replay else 'ACCEPTED'} / "
            f"{receipt['admitted_event_root']} / {receipt['reviewer_separation_decision_root']}",
            file=sys.stderr,
        )
        return 0
    except (
        base.IngestError,
        reviewers.ReviewerSeparationError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        code = exc.code if hasattr(exc, "code") else "SEPARATED_INGEST_ERROR"
        message = exc.message if hasattr(exc, "message") else str(exc)
        print(f"ProofPath separated ingestion failed: {code}: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
