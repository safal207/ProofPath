#!/usr/bin/env python3
"""Cryptographically verify a ProofPath Assured Action certificate with GitHub attestations.

The production path delegates signature, certificate-chain, OIDC identity, subject
integrity, and transparency-timestamp verification to `gh attestation verify`.
The returned JSON is then reduced to a strict, tenant-ingestion-safe admission result.

This module does not grant authority, deploy software, execute payments, or infer
facts that were not enforced by the verification policy.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

POLICY_PROFILE = "proofpath.control-cloud.sigstore-admission-policy.v0.1"
RESULT_PROFILE = "proofpath.control-cloud.sigstore-admission-result.v0.1"
CERTIFICATE_PROFILE = "proofpath.deploy.clearance-certificate.v0.1"
RESULT_DOMAIN = "proofpath:control-cloud:sigstore-admission-result:v0.1"
DEFAULT_ISSUER = "https://token.actions.githubusercontent.com"
DEFAULT_PREDICATE = "https://slsa.dev/provenance/v1"

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
WORKFLOW_RE = re.compile(
    r"^(?:github\.com/)?[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/\.github/workflows/[A-Za-z0-9_.-]+\.ya?ml$"
)
IDENTITY_RE = re.compile(r"^[^\x00\r\n]{3,256}$")


class AdmissionError(Exception):
    """Expected fail-closed admission error."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-integer JSON number is forbidden: {value}")


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_loads(data: bytes | str) -> Any:
    text = data.decode("utf-8") if isinstance(data, bytes) else data
    return json.loads(
        text,
        object_pairs_hook=_no_duplicate_keys,
        parse_float=_reject_constant,
        parse_constant=_reject_constant,
    )


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = strict_loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise AdmissionError("INVALID_JSON", f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AdmissionError("INVALID_JSON", f"{path} must contain one JSON object")
    return value


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
    return raw_digest(domain.encode("utf-8") + b"\0" + canonical_bytes(value))


def require_exact_keys(
    value: Mapping[str, Any],
    required: set[str],
    optional: set[str],
    field: str,
) -> None:
    missing = required - set(value)
    extra = set(value) - required - optional
    if missing:
        raise AdmissionError("MISSING_FIELD", f"{field} missing: {', '.join(sorted(missing))}")
    if extra:
        raise AdmissionError("UNKNOWN_FIELD", f"{field} unknown: {', '.join(sorted(extra))}")


def require_text(value: Any, field: str, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str) or not value or not IDENTITY_RE.fullmatch(value):
        raise AdmissionError("INVALID_FIELD", f"{field} must be a non-empty single-line string")
    if pattern is not None and not pattern.fullmatch(value):
        raise AdmissionError("INVALID_FIELD", f"{field} has invalid format")
    return value


def require_bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise AdmissionError("INVALID_FIELD", f"{field} must be boolean")
    return value


def parse_utc(value: Any, field: str) -> str:
    text = require_text(value, field)
    if not text.endswith("Z"):
        raise AdmissionError("INVALID_TIMESTAMP", f"{field} must be RFC3339 UTC with Z")
    try:
        parsed = dt.datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise AdmissionError("INVALID_TIMESTAMP", f"{field} is invalid") from exc
    if parsed.tzinfo != dt.timezone.utc:
        raise AdmissionError("INVALID_TIMESTAMP", f"{field} must be UTC")
    return text


def validate_digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
        raise AdmissionError("INVALID_DIGEST", f"{field} must be sha256:<64 lowercase hex>")
    return value


def validate_sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise AdmissionError("INVALID_SHA", f"{field} must be a 40-64 lowercase hex digest")
    return value


def validate_policy(value: dict[str, Any]) -> dict[str, Any]:
    required = {
        "profile_id",
        "repository",
        "signer_repository",
        "signer_workflow",
        "source_sha",
        "signer_sha",
        "cert_oidc_issuer",
        "predicate_type",
        "deny_self_hosted_runners",
        "required_runner_environment",
        "verifier_identity",
    }
    require_exact_keys(value, required, set(), "policy")
    if value["profile_id"] != POLICY_PROFILE:
        raise AdmissionError("UNSUPPORTED_POLICY", "unsupported admission policy profile")
    repository = require_text(value["repository"], "policy.repository", REPO_RE)
    signer_repository = require_text(value["signer_repository"], "policy.signer_repository", REPO_RE)
    signer_workflow = require_text(value["signer_workflow"], "policy.signer_workflow", WORKFLOW_RE)
    source_sha = validate_sha(value["source_sha"], "policy.source_sha")
    signer_sha = validate_sha(value["signer_sha"], "policy.signer_sha")
    issuer = require_text(value["cert_oidc_issuer"], "policy.cert_oidc_issuer")
    if issuer != DEFAULT_ISSUER:
        raise AdmissionError("UNTRUSTED_ISSUER_POLICY", "GitHub OIDC issuer must be pinned exactly")
    predicate = require_text(value["predicate_type"], "policy.predicate_type")
    if predicate != DEFAULT_PREDICATE:
        raise AdmissionError("UNSUPPORTED_PREDICATE", "only SLSA provenance v1 is supported")
    if require_bool(value["deny_self_hosted_runners"], "policy.deny_self_hosted_runners") is not True:
        raise AdmissionError("SELF_HOSTED_POLICY_FORBIDDEN", "self-hosted runners must be denied")
    if value["required_runner_environment"] != "github-hosted":
        raise AdmissionError("RUNNER_POLICY_INVALID", "required runner environment must be github-hosted")
    verifier_identity = require_text(value["verifier_identity"], "policy.verifier_identity")
    return {
        "profile_id": POLICY_PROFILE,
        "repository": repository,
        "signer_repository": signer_repository,
        "signer_workflow": signer_workflow,
        "source_sha": source_sha,
        "signer_sha": signer_sha,
        "cert_oidc_issuer": issuer,
        "predicate_type": predicate,
        "deny_self_hosted_runners": True,
        "required_runner_environment": "github-hosted",
        "verifier_identity": verifier_identity,
    }


def validate_certificate(value: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    required = {
        "profile_id",
        "product",
        "decision",
        "valid",
        "primary_reason_code",
        "action",
        "assurance",
        "policy_root",
        "evidence_root",
        "clearance_root",
        "execution_allowed",
        "authority_granted",
    }
    require_exact_keys(value, required, set(), "certificate")
    if value["profile_id"] != CERTIFICATE_PROFILE or value["product"] != "PROOFPATH_ASSURED_ACTION":
        raise AdmissionError("UNSUPPORTED_CERTIFICATE", "subject is not a supported Assured Action certificate")
    if value["authority_granted"] is not False:
        raise AdmissionError("AUTHORITY_BOUNDARY_VIOLATION", "certificate cannot grant authority")
    decision = value["decision"]
    if decision not in {"ACCEPT", "HOLD", "BLOCK", "CHALLENGE"}:
        raise AdmissionError("INVALID_DECISION", "certificate decision is unsupported")
    expected_allowed = decision == "ACCEPT"
    if value["valid"] is not expected_allowed or value["execution_allowed"] is not expected_allowed:
        raise AdmissionError("DECISION_CONFLICT", "certificate decision flags conflict")
    if decision == "ACCEPT":
        if value["primary_reason_code"] is not None:
            raise AdmissionError("DECISION_CONFLICT", "ACCEPT cannot have a reason code")
    elif not isinstance(value["primary_reason_code"], str) or not value["primary_reason_code"]:
        raise AdmissionError("DECISION_CONFLICT", "non-ACCEPT requires a reason code")
    for name in ("policy_root", "evidence_root", "clearance_root"):
        validate_digest(value[name], f"certificate.{name}")
    action = value["action"]
    if not isinstance(action, dict):
        raise AdmissionError("INVALID_ACTION", "certificate.action must be an object")
    action_required = {
        "action_id",
        "action_type",
        "agent_id",
        "repository",
        "branch",
        "commit_sha",
        "environment",
        "artifact_digest",
    }
    require_exact_keys(action, action_required, set(), "certificate.action")
    if action["action_type"] != "deploy":
        raise AdmissionError("UNSUPPORTED_ACTION", "only deploy actions are supported")
    if action["repository"] != policy["repository"]:
        raise AdmissionError("REPOSITORY_BINDING_CONFLICT", "certificate repository differs from verification policy")
    if action["commit_sha"] != policy["source_sha"]:
        raise AdmissionError("SOURCE_SHA_BINDING_CONFLICT", "certificate source SHA differs from verification policy")
    validate_digest(action["artifact_digest"], "certificate.action.artifact_digest")
    assurance = value["assurance"]
    if not isinstance(assurance, dict):
        raise AdmissionError("INVALID_ASSURANCE", "certificate.assurance must be an object")
    required_assurance = {
        "assurance_level",
        "witness_level",
        "coverage",
        "policy_id",
        "policy_version",
    }
    require_exact_keys(assurance, required_assurance, set(), "certificate.assurance")
    if assurance["assurance_level"] != "POLICY_VERIFIED":
        raise AdmissionError("INVALID_ASSURANCE", "unsupported assurance level")
    if assurance["coverage"] != "NOT_FINANCIALLY_COVERED":
        raise AdmissionError("COVERAGE_BOUNDARY_VIOLATION", "v0.1 accepts only uncovered certificates")
    return value


def build_gh_command(subject: Path, policy: dict[str, Any]) -> list[str]:
    return [
        "gh",
        "attestation",
        "verify",
        str(subject),
        "--repo",
        policy["repository"],
        "--signer-repo",
        policy["signer_repository"],
        "--signer-workflow",
        policy["signer_workflow"],
        "--source-digest",
        policy["source_sha"],
        "--signer-digest",
        policy["signer_sha"],
        "--cert-oidc-issuer",
        policy["cert_oidc_issuer"],
        "--predicate-type",
        policy["predicate_type"],
        "--deny-self-hosted-runners",
        "--format",
        "json",
    ]


def run_gh_verification(
    subject: Path,
    policy: dict[str, Any],
    *,
    runner: Any = subprocess.run,
) -> list[dict[str, Any]]:
    if shutil.which("gh") is None:
        raise AdmissionError("GH_UNAVAILABLE", "GitHub CLI is required for cryptographic verification")
    command = build_gh_command(subject, policy)
    env = dict(os.environ)
    env["GH_PAGER"] = "cat"
    try:
        completed = runner(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AdmissionError("GH_VERIFICATION_FAILED", f"gh attestation verify could not run: {exc}") from exc
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "gh attestation verify failed").strip()
        raise AdmissionError("GH_VERIFICATION_FAILED", message[:1000])
    try:
        payload = strict_loads(completed.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise AdmissionError("GH_OUTPUT_INVALID", f"gh verification output is invalid JSON: {exc}") from exc
    if not isinstance(payload, list) or not payload:
        raise AdmissionError("NO_VERIFIED_ATTESTATION", "gh returned no verified attestations")
    normalized: list[dict[str, Any]] = []
    for index, entry in enumerate(payload):
        if not isinstance(entry, dict):
            raise AdmissionError("GH_OUTPUT_INVALID", f"verification entry {index} is not an object")
        verification = entry.get("verificationResult")
        if not isinstance(verification, dict):
            raise AdmissionError("GH_OUTPUT_INVALID", f"verification entry {index} lacks verificationResult")
        timestamps = verification.get("verifiedTimestamps")
        if not isinstance(timestamps, list) or not timestamps:
            raise AdmissionError(
                "TRANSPARENCY_TIMESTAMP_MISSING",
                "verified attestation has no transparency-log or timestamp-authority evidence",
            )
        statement = verification.get("statement")
        if not isinstance(statement, dict) or statement.get("predicateType") != policy["predicate_type"]:
            raise AdmissionError("PREDICATE_BINDING_CONFLICT", "verified predicate type differs from policy")
        signature = verification.get("signature")
        if not isinstance(signature, dict) or not isinstance(signature.get("certificate"), dict):
            raise AdmissionError("CERTIFICATE_RESULT_MISSING", "verified result lacks parsed certificate")
        normalized.append(entry)
    return normalized


def _result_without_root(result: dict[str, Any]) -> dict[str, Any]:
    copy = dict(result)
    copy["result_root"] = None
    return copy


def verify_subject(
    *,
    subject: Path,
    policy: dict[str, Any],
    verified_at: str,
    runner: Any = subprocess.run,
) -> dict[str, Any]:
    verified_at = parse_utc(verified_at, "verified_at")
    if not subject.is_file() or subject.is_symlink():
        raise AdmissionError("SUBJECT_UNAVAILABLE", "subject must be a regular non-symlink file")
    subject_bytes = subject.read_bytes()
    certificate_value = strict_loads(subject_bytes)
    if not isinstance(certificate_value, dict):
        raise AdmissionError("INVALID_CERTIFICATE", "subject must contain one JSON certificate object")
    certificate = validate_certificate(certificate_value, policy)
    verified_entries = run_gh_verification(subject, policy, runner=runner)
    timestamp_count = sum(
        len(entry["verificationResult"]["verifiedTimestamps"])
        for entry in verified_entries
    )
    result: dict[str, Any] = {
        "profile_id": RESULT_PROFILE,
        "decision": "ACCEPT",
        "verified": True,
        "verification_mode": "GH_ATTESTATION_VERIFY",
        "subject_digest": raw_digest(subject_bytes),
        "certificate_canonical_digest": raw_digest(canonical_bytes(certificate)),
        "clearance_root": certificate["clearance_root"],
        "repository": certificate["action"]["repository"],
        "source_sha": certificate["action"]["commit_sha"],
        "artifact_digest": certificate["action"]["artifact_digest"],
        "signer_repository": policy["signer_repository"],
        "signer_workflow": policy["signer_workflow"],
        "signer_sha": policy["signer_sha"],
        "cert_oidc_issuer": policy["cert_oidc_issuer"],
        "predicate_type": policy["predicate_type"],
        "runner_environment": "github-hosted",
        "deny_self_hosted_runners": True,
        "github_attestation_verified": True,
        "transparency_timestamp_verified": True,
        "verified_attestation_count": len(verified_entries),
        "verified_timestamp_count": timestamp_count,
        "verifier_identity": policy["verifier_identity"],
        "verified_at": verified_at,
        "authority_granted": False,
        "deployment_performed": False,
        "payments_executed": False,
        "result_root": None,
    }
    result["result_root"] = domain_hash(RESULT_DOMAIN, _result_without_root(result))
    return result


def validate_result(value: dict[str, Any]) -> dict[str, Any]:
    required = {
        "profile_id",
        "decision",
        "verified",
        "verification_mode",
        "subject_digest",
        "certificate_canonical_digest",
        "clearance_root",
        "repository",
        "source_sha",
        "artifact_digest",
        "signer_repository",
        "signer_workflow",
        "signer_sha",
        "cert_oidc_issuer",
        "predicate_type",
        "runner_environment",
        "deny_self_hosted_runners",
        "github_attestation_verified",
        "transparency_timestamp_verified",
        "verified_attestation_count",
        "verified_timestamp_count",
        "verifier_identity",
        "verified_at",
        "authority_granted",
        "deployment_performed",
        "payments_executed",
        "result_root",
    }
    require_exact_keys(value, required, set(), "admission result")
    if value["profile_id"] != RESULT_PROFILE:
        raise AdmissionError("UNSUPPORTED_RESULT", "unsupported admission result profile")
    if value["decision"] != "ACCEPT" or value["verified"] is not True:
        raise AdmissionError("ADMISSION_NOT_ACCEPTED", "admission result is not verified ACCEPT")
    if value["verification_mode"] != "GH_ATTESTATION_VERIFY":
        raise AdmissionError("UNTRUSTED_VERIFICATION_MODE", "admission result was not produced by gh attestation verify")
    for field in (
        "subject_digest",
        "certificate_canonical_digest",
        "clearance_root",
        "artifact_digest",
        "result_root",
    ):
        validate_digest(value[field], f"result.{field}")
    validate_sha(value["source_sha"], "result.source_sha")
    validate_sha(value["signer_sha"], "result.signer_sha")
    require_text(value["repository"], "result.repository", REPO_RE)
    require_text(value["signer_repository"], "result.signer_repository", REPO_RE)
    require_text(value["signer_workflow"], "result.signer_workflow", WORKFLOW_RE)
    if value["cert_oidc_issuer"] != DEFAULT_ISSUER:
        raise AdmissionError("UNTRUSTED_ISSUER_RESULT", "admission result issuer is not GitHub OIDC")
    if value["predicate_type"] != DEFAULT_PREDICATE:
        raise AdmissionError("UNTRUSTED_PREDICATE_RESULT", "admission result predicate is unsupported")
    if value["runner_environment"] != "github-hosted" or value["deny_self_hosted_runners"] is not True:
        raise AdmissionError("UNTRUSTED_RUNNER_RESULT", "admission result does not enforce GitHub-hosted runner")
    for field in (
        "github_attestation_verified",
        "transparency_timestamp_verified",
    ):
        if value[field] is not True:
            raise AdmissionError("UNVERIFIED_RESULT", f"result.{field} must be true")
    for field in ("authority_granted", "deployment_performed", "payments_executed"):
        if value[field] is not False:
            raise AdmissionError("BOUNDARY_VIOLATION", f"result.{field} must be false")
    for field in ("verified_attestation_count", "verified_timestamp_count"):
        if isinstance(value[field], bool) or not isinstance(value[field], int) or value[field] < 1:
            raise AdmissionError("UNVERIFIED_RESULT", f"result.{field} must be an integer >= 1")
    require_text(value["verifier_identity"], "result.verifier_identity")
    parse_utc(value["verified_at"], "result.verified_at")
    expected = domain_hash(RESULT_DOMAIN, _result_without_root(value))
    if value["result_root"] != expected:
        raise AdmissionError("RESULT_ROOT_MISMATCH", "admission result root is invalid")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value) + b"\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify", help="cryptographically verify a subject and emit admission result")
    verify.add_argument("--subject", required=True, type=Path)
    verify.add_argument("--policy", required=True, type=Path)
    verify.add_argument("--verified-at", required=True)
    verify.add_argument("--output", required=True, type=Path)

    validate = subparsers.add_parser("validate-result", help="validate a previously emitted admission result")
    validate.add_argument("--result", required=True, type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            policy = validate_policy(load_json(args.policy))
            result = verify_subject(
                subject=args.subject,
                policy=policy,
                verified_at=args.verified_at,
            )
            validate_result(result)
            write_json(args.output, result)
            print(
                f"ProofPath Sigstore admission: ACCEPT / {result['subject_digest']} / {result['result_root']}",
                file=sys.stderr,
            )
            return 0
        result = validate_result(load_json(args.result))
        print(f"ProofPath Sigstore admission result valid: {result['result_root']}")
        return 0
    except (AdmissionError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        code = exc.code if isinstance(exc, AdmissionError) else "ADMISSION_INTERNAL_ERROR"
        message = exc.message if isinstance(exc, AdmissionError) else str(exc)
        print(f"ProofPath Sigstore admission failed: {code}: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
