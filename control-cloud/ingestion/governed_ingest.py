#!/usr/bin/env python3
"""Governance-gated ProofPath Control Cloud ingestion.

This is the v0.1 high-assurance entrypoint. It authenticates the tenant request,
validates the server-controlled Sigstore admission result, requires a separate
server-controlled ACCEPT governance decision for that exact admission root, and
only then delegates to the append-only admitted ingestion runtime.
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
base = _load_module("proofpath_ingestion_governed_base", REPO_ROOT / "control-cloud/ingestion/ingest.py")
admitted = _load_module("proofpath_admitted_ingestion_governed", REPO_ROOT / "control-cloud/ingestion/admitted_ingest.py")
governance = _load_module(
    "proofpath_workflow_governance_ingestion",
    REPO_ROOT / "control-cloud/governance/verify_workflow_governance.py",
)

RECEIPT_PROFILE = "proofpath.control-cloud.governed-ingest-receipt.v0.1"
RECEIPT_DOMAIN = RECEIPT_PROFILE + ".root"


class GovernedIngestError(base.IngestError):
    """Governance-gated ingestion error."""


def governance_file_for_admission(governance_dir: Path, admission_result_root: str) -> Path:
    governance.require_digest(admission_result_root, "admission_result_root")
    root = governance_dir.resolve()
    candidate = root / (admission_result_root.split(":", 1)[1] + ".json")
    if candidate.is_symlink():
        raise GovernedIngestError("GOVERNANCE_DECISION_SYMLINK_REJECTED", "governance decision must not be a symlink", 500)
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise GovernedIngestError("GOVERNANCE_DECISION_PATH_ESCAPE", "governance decision escapes trusted directory", 500) from exc
    if not resolved.is_file():
        raise GovernedIngestError("GOVERNANCE_DECISION_NOT_FOUND", "trusted workflow governance decision is unavailable", 422)
    return resolved


def load_bound_governance_decision(*, admission_result: dict[str, Any], governance_dir: Path,
                                   now: dt.datetime) -> dict[str, Any]:
    path = governance_file_for_admission(governance_dir, admission_result["result_root"])
    try:
        decision = governance.validate_decision(governance.load_json(path))
    except governance.GovernanceError as exc:
        raise GovernedIngestError("GOVERNANCE_DECISION_INVALID", f"{exc.code}: {exc.message}", 422) from exc
    if decision["decision"] != "ACCEPT" or decision["governance_trust_verified"] is not True:
        raise GovernedIngestError("WORKFLOW_GOVERNANCE_REQUIRED", "workflow governance decision is not ACCEPT", 422)
    checks = [
        (decision["admission_result_root"], admission_result["result_root"], "admission root"),
        (decision["subject_digest"], admission_result["subject_digest"], "subject digest"),
        (decision["repository"], admission_result["repository"], "repository"),
        (decision["signer_repository"], admission_result["signer_repository"], "signer repository"),
        (decision["signer_workflow"], admission_result["signer_workflow"], "signer workflow"),
        (decision["signer_sha"], admission_result["signer_sha"], "signer SHA"),
    ]
    for actual, expected, label in checks:
        if actual != expected:
            raise GovernedIngestError("GOVERNANCE_BINDING_CONFLICT", f"governance {label} differs from admission result", 422)
    observed = governance.parse_utc(decision["observed_at"], "decision.observed_at")
    if observed > now or now - observed > dt.timedelta(minutes=15):
        raise GovernedIngestError("GOVERNANCE_DECISION_STALE", "governance decision is future-dated or older than 15 minutes", 422)
    for field in ("reviewer_quorum_verified", "trust_window_verified", "revocation_checked", "owner_scope_verified"):
        if decision[field] is not True:
            raise GovernedIngestError("GOVERNANCE_ASSURANCE_INCOMPLETE", f"{field} is not verified", 422)
    return decision


def _receipt_without_root(value: dict[str, Any]) -> dict[str, Any]:
    copy = dict(value)
    copy["receipt_root"] = None
    return copy


def validate_receipt(value: dict[str, Any]) -> dict[str, Any]:
    required = {
        "profile_id", "status", "tenant_id", "request_id", "action_id", "decision",
        "content_digest", "admitted_event_root", "admission_result_root", "governance_decision_root",
        "trust_record_root", "subject_digest", "stored_at", "admitted_receipt_root",
        "provenance_cryptographically_verified_by_api", "governance_trust_verified_by_api",
        "financial_status", "payments_executed", "insurance_provided", "deployment_performed",
        "authority_granted", "repository_write_performed", "receipt_root",
    }
    if set(value) != required or value.get("profile_id") != RECEIPT_PROFILE:
        raise GovernedIngestError("INVALID_GOVERNED_RECEIPT", "governed receipt shape is invalid", 500)
    if value["status"] != "ACCEPTED_WITH_CRYPTOGRAPHIC_PROVENANCE_AND_WORKFLOW_GOVERNANCE":
        raise GovernedIngestError("INVALID_GOVERNED_RECEIPT", "governed receipt status is invalid", 500)
    if value["provenance_cryptographically_verified_by_api"] is not True or value["governance_trust_verified_by_api"] is not True:
        raise GovernedIngestError("INVALID_GOVERNED_RECEIPT", "governed receipt lost required verification", 500)
    for field in ("payments_executed", "insurance_provided", "deployment_performed", "authority_granted", "repository_write_performed"):
        if value[field] is not False:
            raise GovernedIngestError("BOUNDARY_VIOLATION", f"receipt.{field} must be false", 500)
    for field in ("admitted_event_root", "admission_result_root", "governance_decision_root", "trust_record_root", "subject_digest", "content_digest", "admitted_receipt_root", "receipt_root"):
        governance.require_digest(value[field], f"receipt.{field}")
    governance.parse_utc(value["stored_at"], "receipt.stored_at")
    expected = governance.domain_hash(RECEIPT_DOMAIN, _receipt_without_root(value))
    if value["receipt_root"] != expected:
        raise GovernedIngestError("GOVERNED_RECEIPT_ROOT_MISMATCH", "governed receipt root is invalid", 500)
    return value


def ingest_governed_request(*, body: bytes, headers: Mapping[str, Any], tenant_from_path: str,
                            registry: dict[str, Any], store_root: Path, admissions_dir: Path,
                            governance_dir: Path, now: dt.datetime) -> tuple[dict[str, Any], bool]:
    if now.tzinfo != dt.timezone.utc:
        raise GovernedIngestError("INVALID_SERVER_TIME", "server time must be UTC", 500)
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
    governance_decision = load_bound_governance_decision(
        admission_result=admission_result,
        governance_dir=governance_dir,
        now=now,
    )
    admitted_receipt, replay = admitted.ingest_admitted_request(
        body=body,
        headers=headers,
        tenant_from_path=tenant_from_path,
        registry=registry,
        store_root=store_root,
        admissions_dir=admissions_dir,
        now=now,
    )
    receipt: dict[str, Any] = {
        "profile_id": RECEIPT_PROFILE,
        "status": "ACCEPTED_WITH_CRYPTOGRAPHIC_PROVENANCE_AND_WORKFLOW_GOVERNANCE",
        "tenant_id": admitted_receipt["tenant_id"],
        "request_id": admitted_receipt["request_id"],
        "action_id": admitted_receipt["action_id"],
        "decision": admitted_receipt["decision"],
        "content_digest": admitted_receipt["content_digest"],
        "admitted_event_root": admitted_receipt["event_root"],
        "admission_result_root": admitted_receipt["admission_result_root"],
        "governance_decision_root": governance_decision["decision_root"],
        "trust_record_root": governance_decision["trust_record_root"],
        "subject_digest": admitted_receipt["subject_digest"],
        "stored_at": admitted_receipt["stored_at"],
        "admitted_receipt_root": admitted_receipt["receipt_root"],
        "provenance_cryptographically_verified_by_api": True,
        "governance_trust_verified_by_api": True,
        "financial_status": "RECORDED_NOT_PAYABLE",
        "payments_executed": False,
        "insurance_provided": False,
        "deployment_performed": False,
        "authority_granted": False,
        "repository_write_performed": False,
        "receipt_root": None,
    }
    receipt["receipt_root"] = governance.domain_hash(RECEIPT_DOMAIN, _receipt_without_root(receipt))
    return validate_receipt(receipt), replay


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(governance.canonical_bytes(value) + b"\n")


def load_headers(path: Path) -> dict[str, str]:
    value = base.strict_loads(path.read_bytes())
    if not isinstance(value, dict) or not all(isinstance(key, str) and isinstance(item, str) for key, item in value.items()):
        raise GovernedIngestError("INVALID_HEADER_FILE", "header file must be a string map", 400)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--body", required=True, type=Path)
    parser.add_argument("--headers", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--store", required=True, type=Path)
    parser.add_argument("--admissions-dir", required=True, type=Path)
    parser.add_argument("--governance-dir", required=True, type=Path)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--now", required=True)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        receipt, replay = ingest_governed_request(
            body=args.body.read_bytes(),
            headers=load_headers(args.headers),
            tenant_from_path=args.tenant,
            registry=base.load_registry(args.registry),
            store_root=args.store,
            admissions_dir=args.admissions_dir,
            governance_dir=args.governance_dir,
            now=base.parse_utc(args.now, "now"),
        )
        write_json(args.receipt, receipt)
        print(
            f"ProofPath governed ingestion: {'IDEMPOTENT_REPLAY' if replay else 'ACCEPTED'} / "
            f"{receipt['admitted_event_root']} / {receipt['governance_decision_root']}",
            file=sys.stderr,
        )
        return 0
    except (base.IngestError, governance.GovernanceError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        code = exc.code if hasattr(exc, "code") else "GOVERNED_INGEST_ERROR"
        message = exc.message if hasattr(exc, "message") else str(exc)
        print(f"ProofPath governed ingestion failed: {code}: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
