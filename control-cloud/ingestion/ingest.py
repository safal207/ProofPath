#!/usr/bin/env python3
"""ProofPath Control Cloud authenticated ingestion reference service.

Dependency-free reference implementation. It authenticates tenant requests with
HMAC-SHA256, binds one Assured Action certificate to an append-only event chain,
and exports accepted events into the Control Cloud dataset format.

It does not independently verify Sigstore attestations, execute payments,
deploy software, grant authority, or provide financial coverage.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import hmac
import http.server
import json
import os
import re
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Mapping
from urllib.parse import urlsplit

REQUEST_PROFILE = "proofpath.control-cloud.ingest-request.v0.1"
RECEIPT_PROFILE = "proofpath.control-cloud.ingest-receipt.v0.1"
REGISTRY_PROFILE = "proofpath.control-cloud.tenant-registry.v0.1"
DATASET_PROFILE = "proofpath.control-cloud.dataset.v0.1"
SIGNING_PROFILE = "proofpath.control-cloud.ingest-signing.v0.1"
EVENT_PROFILE = "proofpath.control-cloud.ingest-event.v0.1"

DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._~-]{2,127}$")
TENANT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,62}$")
KEY_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{2,63}$")
DECISIONS = {"ACCEPT", "HOLD", "BLOCK", "CHALLENGE"}
RISK_TIERS = {"low", "medium", "high", "critical"}
DISPUTE_STATES = {"none", "open", "resolved"}
MAX_BODY_BYTES = 1_048_576
DEFAULT_CLOCK_SKEW_SECONDS = 300
ZERO_ROOT = "sha256:" + ("0" * 64)


class IngestError(Exception):
    """Expected fail-closed ingestion error."""

    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def _reject_constant(_: str) -> None:
    raise ValueError("floating-point JSON values are not allowed")


def _object_pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_loads(data: bytes | str) -> Any:
    if isinstance(data, bytes):
        if len(data) > MAX_BODY_BYTES:
            raise IngestError("BODY_TOO_LARGE", "request body exceeds maximum size", 413)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise IngestError("INVALID_UTF8", "request body must be UTF-8", 400) from exc
    else:
        text = data
    try:
        return json.loads(
            text,
            object_pairs_hook=_object_pairs_no_duplicates,
            parse_float=_reject_constant,
            parse_constant=_reject_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        raise IngestError("INVALID_JSON", str(exc), 400) from exc


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def domain_hash(domain: str, value: Any) -> str:
    payload = domain.encode("utf-8") + b"\0" + canonical_bytes(value)
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def raw_sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def parse_utc(value: str, field: str) -> dt.datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise IngestError("INVALID_TIMESTAMP", f"{field} must be RFC3339 UTC with Z", 422)
    try:
        parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise IngestError("INVALID_TIMESTAMP", f"{field} is not valid RFC3339", 422) from exc
    if parsed.tzinfo != dt.timezone.utc:
        raise IngestError("INVALID_TIMESTAMP", f"{field} must be UTC", 422)
    if parsed.microsecond:
        raise IngestError("INVALID_TIMESTAMP", f"{field} must use whole seconds", 422)
    return parsed


def format_utc(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def require_dict(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IngestError("INVALID_FIELD", f"{field} must be an object", 422)
    return value


def require_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise IngestError("INVALID_FIELD", f"{field} must be an array", 422)
    return value


def require_exact_keys(value: Mapping[str, Any], required: set[str], optional: set[str], field: str) -> None:
    keys = set(value)
    missing = required - keys
    extra = keys - required - optional
    if missing:
        raise IngestError("MISSING_FIELD", f"{field} missing: {', '.join(sorted(missing))}", 422)
    if extra:
        raise IngestError("UNKNOWN_FIELD", f"{field} unknown: {', '.join(sorted(extra))}", 422)


def require_identifier(value: Any, field: str, pattern: re.Pattern[str] = IDENTIFIER_RE) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise IngestError("INVALID_IDENTIFIER", f"{field} has invalid format", 422)
    return value


def validate_digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not DIGEST_RE.fullmatch(value):
        raise IngestError("INVALID_DIGEST", f"{field} must be sha256:<64 lowercase hex>", 422)
    return value


def validate_certificate(certificate: Any) -> dict[str, Any]:
    cert = require_dict(certificate, "assured_action.certificate")
    required = {
        "profile_id", "product", "decision", "valid", "primary_reason_code",
        "action", "assurance", "policy_root", "evidence_root", "clearance_root",
        "execution_allowed", "authority_granted",
    }
    require_exact_keys(cert, required, set(), "assured_action.certificate")
    if cert["profile_id"] != "proofpath.deploy.clearance-certificate.v0.1":
        raise IngestError("UNSUPPORTED_CERTIFICATE", "unsupported certificate profile", 422)
    if cert["product"] != "PROOFPATH_ASSURED_ACTION":
        raise IngestError("UNSUPPORTED_CERTIFICATE", "certificate product mismatch", 422)
    decision = cert["decision"]
    if decision not in DECISIONS:
        raise IngestError("INVALID_DECISION", "unsupported certificate decision", 422)
    if cert["authority_granted"] is not False:
        raise IngestError("AUTHORITY_BOUNDARY_VIOLATION", "certificate cannot grant authority", 422)
    expected_allowed = decision == "ACCEPT"
    if cert["execution_allowed"] is not expected_allowed:
        raise IngestError("DECISION_CONFLICT", "execution_allowed conflicts with decision", 422)
    if cert["valid"] is not expected_allowed:
        raise IngestError("DECISION_CONFLICT", "valid conflicts with decision", 422)
    if decision == "ACCEPT":
        if cert["primary_reason_code"] is not None:
            raise IngestError("DECISION_CONFLICT", "ACCEPT cannot have a primary reason", 422)
    elif not isinstance(cert["primary_reason_code"], str) or not cert["primary_reason_code"]:
        raise IngestError("DECISION_CONFLICT", "non-ACCEPT requires a primary reason", 422)
    for name in ("policy_root", "evidence_root", "clearance_root"):
        validate_digest(cert[name], f"certificate.{name}")

    action = require_dict(cert["action"], "certificate.action")
    action_required = {
        "action_id", "action_type", "agent_id", "repository", "branch",
        "commit_sha", "environment", "artifact_digest",
    }
    require_exact_keys(action, action_required, set(), "certificate.action")
    require_identifier(action["action_id"], "certificate.action.action_id")
    require_identifier(action["agent_id"], "certificate.action.agent_id")
    if action["action_type"] != "deploy":
        raise IngestError("UNSUPPORTED_ACTION", "only deploy actions are supported in v0.1", 422)
    repository = action["repository"]
    if not isinstance(repository, str) or repository.count("/") != 1 or any(not part for part in repository.split("/")):
        raise IngestError("INVALID_REPOSITORY", "repository must be owner/name", 422)
    for field in ("branch", "environment"):
        if not isinstance(action[field], str) or not action[field] or "\n" in action[field] or "\r" in action[field]:
            raise IngestError("INVALID_FIELD", f"certificate.action.{field} is invalid", 422)
    if not isinstance(action["commit_sha"], str) or not SHA_RE.fullmatch(action["commit_sha"]):
        raise IngestError("INVALID_SHA", "certificate.action.commit_sha is invalid", 422)
    validate_digest(action["artifact_digest"], "certificate.action.artifact_digest")

    assurance = require_dict(cert["assurance"], "certificate.assurance")
    assurance_required = {
        "assurance_level", "witness_level", "coverage", "policy_id", "policy_version",
    }
    require_exact_keys(assurance, assurance_required, set(), "certificate.assurance")
    if assurance["assurance_level"] != "POLICY_VERIFIED":
        raise IngestError("INVALID_ASSURANCE", "assurance level is unsupported", 422)
    if assurance["coverage"] != "NOT_FINANCIALLY_COVERED":
        raise IngestError("COVERAGE_BOUNDARY_VIOLATION", "v0.1 accepts only uncovered certificates", 422)
    for field in ("witness_level", "policy_id", "policy_version"):
        if not isinstance(assurance[field], str) or not assurance[field]:
            raise IngestError("INVALID_ASSURANCE", f"certificate.assurance.{field} is invalid", 422)
    return cert


def validate_assured_action(value: Any) -> dict[str, Any]:
    action_record = require_dict(value, "assured_action")
    required = {
        "base_price_minor", "certificate", "dispute_state",
        "observed_at", "operator_assignments", "risk_tier",
    }
    require_exact_keys(action_record, required, set(), "assured_action")
    price = action_record["base_price_minor"]
    if isinstance(price, bool) or not isinstance(price, int) or not (0 <= price <= 10**12):
        raise IngestError("INVALID_PRICE", "base_price_minor must be a non-negative integer", 422)
    if action_record["risk_tier"] not in RISK_TIERS:
        raise IngestError("INVALID_RISK_TIER", "risk_tier is invalid", 422)
    if action_record["dispute_state"] not in DISPUTE_STATES:
        raise IngestError("INVALID_DISPUTE_STATE", "dispute_state is invalid", 422)
    parse_utc(action_record["observed_at"], "assured_action.observed_at")
    validate_certificate(action_record["certificate"])

    assignments = require_list(action_record["operator_assignments"], "assured_action.operator_assignments")
    if not assignments:
        raise IngestError("INVALID_OPERATORS", "at least one operator assignment is required", 422)
    seen: set[str] = set()
    for index, raw in enumerate(assignments):
        assignment = require_dict(raw, f"operator_assignments[{index}]")
        require_exact_keys(assignment, {"operator_id", "role", "weight"}, set(), f"operator_assignments[{index}]")
        operator_id = require_identifier(assignment["operator_id"], f"operator_assignments[{index}].operator_id")
        if operator_id in seen:
            raise IngestError("DUPLICATE_OPERATOR", "operator assignments must be unique", 422)
        seen.add(operator_id)
        if not isinstance(assignment["role"], str) or not assignment["role"]:
            raise IngestError("INVALID_OPERATORS", "operator role is invalid", 422)
        weight = assignment["weight"]
        if isinstance(weight, bool) or not isinstance(weight, int) or not (1 <= weight <= 10_000):
            raise IngestError("INVALID_OPERATORS", "operator weight is invalid", 422)
    return action_record


def validate_request(value: Any) -> dict[str, Any]:
    request = require_dict(value, "request")
    required = {
        "profile_id", "tenant_id", "request_id", "submitted_at",
        "assured_action", "provenance_binding",
    }
    require_exact_keys(request, required, set(), "request")
    if request["profile_id"] != REQUEST_PROFILE:
        raise IngestError("UNSUPPORTED_REQUEST", "unsupported ingest request profile", 422)
    require_identifier(request["tenant_id"], "tenant_id", TENANT_RE)
    require_identifier(request["request_id"], "request_id")
    parse_utc(request["submitted_at"], "submitted_at")
    validate_assured_action(request["assured_action"])

    binding = require_dict(request["provenance_binding"], "provenance_binding")
    require_exact_keys(
        binding,
        {"status", "subject_digest", "verifier_identity", "verified_at"},
        set(),
        "provenance_binding",
    )
    status = binding["status"]
    if status == "NOT_PROVIDED":
        if any(binding[name] is not None for name in ("subject_digest", "verifier_identity", "verified_at")):
            raise IngestError("PROVENANCE_CONFLICT", "NOT_PROVIDED provenance must have null details", 422)
    elif status == "EXTERNAL_RESULT_BOUND":
        validate_digest(binding["subject_digest"], "provenance_binding.subject_digest")
        if not isinstance(binding["verifier_identity"], str) or not binding["verifier_identity"]:
            raise IngestError("PROVENANCE_CONFLICT", "verifier_identity is required", 422)
        parse_utc(binding["verified_at"], "provenance_binding.verified_at")
    else:
        raise IngestError("PROVENANCE_CONFLICT", "unsupported provenance binding status", 422)
    return request


def load_registry(path: Path) -> dict[str, Any]:
    registry = strict_loads(path.read_bytes())
    registry = require_dict(registry, "tenant registry")
    require_exact_keys(registry, {"profile_id", "tenants"}, set(), "tenant registry")
    if registry["profile_id"] != REGISTRY_PROFILE:
        raise IngestError("UNSUPPORTED_REGISTRY", "unsupported tenant registry", 500)
    tenants = require_dict(registry["tenants"], "tenant registry.tenants")
    for tenant_id, raw_tenant in tenants.items():
        require_identifier(tenant_id, "registry tenant id", TENANT_RE)
        tenant = require_dict(raw_tenant, f"tenant {tenant_id}")
        require_exact_keys(tenant, {"active", "repository_prefixes", "keys"}, set(), f"tenant {tenant_id}")
        if not isinstance(tenant["active"], bool):
            raise IngestError("INVALID_REGISTRY", "tenant active must be boolean", 500)
        prefixes = require_list(tenant["repository_prefixes"], f"tenant {tenant_id}.repository_prefixes")
        if not prefixes or any(not isinstance(prefix, str) or not prefix.endswith("/") for prefix in prefixes):
            raise IngestError("INVALID_REGISTRY", "repository prefixes must be non-empty owner/ prefixes", 500)
        keys = require_dict(tenant["keys"], f"tenant {tenant_id}.keys")
        if not keys:
            raise IngestError("INVALID_REGISTRY", "tenant must define at least one key", 500)
        for key_id, raw_key in keys.items():
            require_identifier(key_id, "registry key id", KEY_RE)
            key = require_dict(raw_key, f"key {key_id}")
            require_exact_keys(key, {"active", "secret_env"}, set(), f"key {key_id}")
            if not isinstance(key["active"], bool):
                raise IngestError("INVALID_REGISTRY", "key active must be boolean", 500)
            secret_env = key["secret_env"]
            if not isinstance(secret_env, str) or not re.fullmatch(r"^[A-Z][A-Z0-9_]{2,127}$", secret_env):
                raise IngestError("INVALID_REGISTRY", "secret_env must name an environment variable", 500)
    return registry


@dataclass(frozen=True)
class AuthHeaders:
    key_id: str
    timestamp: str
    nonce: str
    idempotency_key: str
    content_digest: str
    signature: str

    @classmethod
    def from_mapping(cls, headers: Mapping[str, Any]) -> "AuthHeaders":
        lowered = {str(key).lower(): value for key, value in headers.items()}
        names = {
            "key_id": "x-proofpath-key-id",
            "timestamp": "x-proofpath-timestamp",
            "nonce": "x-proofpath-nonce",
            "idempotency_key": "x-proofpath-idempotency-key",
            "content_digest": "x-proofpath-content-sha256",
            "signature": "x-proofpath-signature",
        }
        missing = [header for header in names.values() if header not in lowered]
        if missing:
            raise IngestError("MISSING_AUTH_HEADER", f"missing authentication header: {missing[0]}", 401)
        key_id = require_identifier(lowered[names["key_id"]], "key id", KEY_RE)
        timestamp = lowered[names["timestamp"]]
        nonce = require_identifier(lowered[names["nonce"]], "nonce")
        idem = require_identifier(lowered[names["idempotency_key"]], "idempotency key")
        content_digest = validate_digest(lowered[names["content_digest"]], "content digest")
        signature = lowered[names["signature"]]
        if not isinstance(timestamp, str):
            raise IngestError("INVALID_AUTH_HEADER", "timestamp header is invalid", 401)
        if not isinstance(signature, str) or not re.fullmatch(r"^sha256=[0-9a-f]{64}$", signature):
            raise IngestError("INVALID_SIGNATURE", "signature header is invalid", 401)
        return cls(key_id, timestamp, nonce, idem, content_digest, signature)


def signing_string(
    method: str,
    path: str,
    tenant_id: str,
    auth: AuthHeaders,
) -> bytes:
    parts = [
        SIGNING_PROFILE,
        method.upper(),
        path,
        tenant_id,
        auth.key_id,
        auth.timestamp,
        auth.nonce,
        auth.idempotency_key,
        auth.content_digest,
    ]
    return ("\n".join(parts)).encode("utf-8")


def sign_headers(
    *,
    body: bytes,
    tenant_id: str,
    key_id: str,
    secret: str,
    timestamp: str,
    nonce: str,
    idempotency_key: str,
) -> dict[str, str]:
    require_identifier(tenant_id, "tenant_id", TENANT_RE)
    require_identifier(key_id, "key_id", KEY_RE)
    require_identifier(nonce, "nonce")
    require_identifier(idempotency_key, "idempotency_key")
    parse_utc(timestamp, "timestamp")
    if len(secret.encode("utf-8")) < 32:
        raise IngestError("WEAK_SECRET", "HMAC secret must be at least 32 bytes", 500)
    path = f"/v1/tenants/{tenant_id}/assured-actions"
    digest = raw_sha256(body)
    partial = AuthHeaders(key_id, timestamp, nonce, idempotency_key, digest, "sha256=" + ("0" * 64))
    signature = hmac.new(secret.encode("utf-8"), signing_string("POST", path, tenant_id, partial), hashlib.sha256)
    return {
        "X-ProofPath-Key-Id": key_id,
        "X-ProofPath-Timestamp": timestamp,
        "X-ProofPath-Nonce": nonce,
        "X-ProofPath-Idempotency-Key": idempotency_key,
        "X-ProofPath-Content-SHA256": digest,
        "X-ProofPath-Signature": "sha256=" + signature.hexdigest(),
    }


def resolve_tenant_key(
    registry: dict[str, Any],
    tenant_id: str,
    key_id: str,
) -> tuple[dict[str, Any], str]:
    tenants = registry["tenants"]
    if tenant_id not in tenants:
        raise IngestError("UNKNOWN_TENANT", "tenant is not registered", 403)
    tenant = tenants[tenant_id]
    if tenant["active"] is not True:
        raise IngestError("TENANT_DISABLED", "tenant is disabled", 403)
    if key_id not in tenant["keys"]:
        raise IngestError("UNKNOWN_KEY", "key is not registered for tenant", 403)
    key = tenant["keys"][key_id]
    if key["active"] is not True:
        raise IngestError("KEY_DISABLED", "key is disabled", 403)
    secret = os.environ.get(key["secret_env"])
    if secret is None:
        raise IngestError("KEY_MATERIAL_UNAVAILABLE", "tenant key material is unavailable", 500)
    if len(secret.encode("utf-8")) < 32:
        raise IngestError("WEAK_SECRET", "tenant key material is too short", 500)
    return tenant, secret


def verify_authentication(
    *,
    body: bytes,
    request: dict[str, Any],
    tenant_from_path: str,
    auth: AuthHeaders,
    registry: dict[str, Any],
    now: dt.datetime,
    clock_skew_seconds: int,
) -> dict[str, Any]:
    tenant_id = request["tenant_id"]
    if tenant_id != tenant_from_path:
        raise IngestError("TENANT_BINDING_CONFLICT", "path tenant differs from request tenant", 403)
    if raw_sha256(body) != auth.content_digest:
        raise IngestError("CONTENT_DIGEST_MISMATCH", "content digest does not match exact request bytes", 401)
    timestamp = parse_utc(auth.timestamp, "authentication timestamp")
    if abs((now - timestamp).total_seconds()) > clock_skew_seconds:
        raise IngestError("AUTH_TIMESTAMP_OUT_OF_WINDOW", "authentication timestamp is outside allowed window", 401)
    submitted = parse_utc(request["submitted_at"], "submitted_at")
    if abs((submitted - timestamp).total_seconds()) > clock_skew_seconds:
        raise IngestError("SUBMISSION_TIMESTAMP_CONFLICT", "submitted_at differs from signed timestamp", 422)

    tenant, secret = resolve_tenant_key(registry, tenant_id, auth.key_id)
    path = f"/v1/tenants/{tenant_id}/assured-actions"
    expected = hmac.new(secret.encode("utf-8"), signing_string("POST", path, tenant_id, auth), hashlib.sha256)
    provided = bytes.fromhex(auth.signature.split("=", 1)[1])
    if not hmac.compare_digest(expected.digest(), provided):
        raise IngestError("INVALID_SIGNATURE", "HMAC signature verification failed", 401)

    repository = request["assured_action"]["certificate"]["action"]["repository"]
    if not any(repository.startswith(prefix) for prefix in tenant["repository_prefixes"]):
        raise IngestError("TENANT_REPOSITORY_SCOPE_VIOLATION", "repository is outside tenant scope", 403)
    return tenant


def confined_tenant_directory(store_root: Path, tenant_id: str) -> Path:
    require_identifier(tenant_id, "tenant id", TENANT_RE)
    root = store_root.resolve()
    tenant_dir = (root / "tenants" / tenant_id).resolve()
    try:
        tenant_dir.relative_to(root)
    except ValueError as exc:
        raise IngestError("STORE_PATH_ESCAPE", "tenant store path escapes root", 500) from exc
    return tenant_dir


def safe_store_file(tenant_dir: Path, filename: str) -> Path:
    if filename not in {"events.jsonl", ".ingest.lock"}:
        raise IngestError("INVALID_STORE_FILE", "unsupported tenant store filename", 500)
    path = tenant_dir / filename
    if path.is_symlink():
        raise IngestError("STORE_SYMLINK_REJECTED", f"{filename} must not be a symlink", 500)
    resolved_parent = path.parent.resolve()
    if resolved_parent != tenant_dir.resolve():
        raise IngestError("STORE_PATH_ESCAPE", f"{filename} escapes tenant directory", 500)
    return path


def _load_events_unlocked(events_path: Path) -> list[dict[str, Any]]:
    if not events_path.exists():
        return []
    events: list[dict[str, Any]] = []
    with events_path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            if not raw_line.strip():
                raise IngestError("CORRUPT_EVENT_STORE", f"blank event line {line_number}", 500)
            event = strict_loads(raw_line)
            if not isinstance(event, dict):
                raise IngestError("CORRUPT_EVENT_STORE", f"event line {line_number} is not an object", 500)
            events.append(event)
    verify_event_chain(events)
    return events


def _receipt_without_root(receipt: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in receipt.items() if key != "receipt_root"}


def _event_subject_for_root(event: dict[str, Any]) -> dict[str, Any]:
    receipt = require_dict(event["receipt"], "stored receipt")
    receipt_subject = {
        "profile_id": receipt["profile_id"],
        "tenant_id": receipt["tenant_id"],
        "request_id": receipt["request_id"],
        "action_id": receipt["action_id"],
        "decision": receipt["decision"],
        "content_digest": receipt["content_digest"],
        "event_index": receipt["event_index"],
        "previous_event_root": receipt["previous_event_root"],
        "stored_at": receipt["stored_at"],
    }
    return {
        "profile_id": event["profile_id"],
        "event_index": event["event_index"],
        "tenant_id": event["tenant_id"],
        "request_id": event["request_id"],
        "idempotency_key": event["idempotency_key"],
        "key_id": event["key_id"],
        "nonce": event["nonce"],
        "authentication_timestamp": event["authentication_timestamp"],
        "content_digest": event["content_digest"],
        "request": event["request"],
        "previous_event_root": event["previous_event_root"],
        "receipt": receipt_subject,
    }


def verify_receipt(receipt: dict[str, Any]) -> None:
    required = {
        "profile_id", "status", "tenant_id", "request_id", "action_id", "decision",
        "content_digest", "event_index", "previous_event_root", "event_root",
        "stored_at", "receipt_root", "financial_status", "payments_executed",
        "insurance_provided", "deployment_performed", "authority_granted",
        "provenance_cryptographically_verified_by_api",
    }
    if set(receipt) != required:
        raise IngestError("CORRUPT_EVENT_STORE", "receipt keys are invalid", 500)
    expected = domain_hash(RECEIPT_PROFILE, _receipt_without_root(receipt))
    if receipt["receipt_root"] != expected:
        raise IngestError("CORRUPT_EVENT_STORE", "receipt root mismatch", 500)


def verify_event_chain(events: list[dict[str, Any]]) -> None:
    previous = ZERO_ROOT
    seen_idempotency: set[str] = set()
    seen_nonce_pairs: set[tuple[str, str]] = set()
    for expected_index, event in enumerate(events, 1):
        required = {
            "profile_id", "event_index", "tenant_id", "request_id", "idempotency_key",
            "key_id", "nonce", "authentication_timestamp", "content_digest",
            "request", "previous_event_root", "receipt", "event_root",
        }
        if set(event) != required or event.get("profile_id") != EVENT_PROFILE:
            raise IngestError("CORRUPT_EVENT_STORE", "event shape is invalid", 500)
        if event["event_index"] != expected_index:
            raise IngestError("CORRUPT_EVENT_STORE", "event index is not contiguous", 500)
        if event["previous_event_root"] != previous:
            raise IngestError("CORRUPT_EVENT_STORE", "event chain previous root mismatch", 500)
        if event["idempotency_key"] in seen_idempotency:
            raise IngestError("CORRUPT_EVENT_STORE", "duplicate idempotency key in event store", 500)
        nonce_pair = (event["key_id"], event["nonce"])
        if nonce_pair in seen_nonce_pairs:
            raise IngestError("CORRUPT_EVENT_STORE", "duplicate nonce in event store", 500)
        seen_idempotency.add(event["idempotency_key"])
        seen_nonce_pairs.add(nonce_pair)
        if raw_sha256(canonical_bytes(event["request"])) != event["content_digest"]:
            # The stored request is canonicalized. The event content digest deliberately binds
            # the exact submitted bytes, so it cannot be recomputed from the object here.
            if not DIGEST_RE.fullmatch(str(event["content_digest"])):
                raise IngestError("CORRUPT_EVENT_STORE", "event content digest is invalid", 500)
        receipt = require_dict(event["receipt"], "stored receipt")
        verify_receipt(receipt)
        if receipt["event_index"] != expected_index or receipt["event_root"] != event["event_root"]:
            raise IngestError("CORRUPT_EVENT_STORE", "receipt does not bind event", 500)
        expected_root = domain_hash(EVENT_PROFILE + ".subject", _event_subject_for_root(event))
        if event["event_root"] != expected_root:
            raise IngestError("CORRUPT_EVENT_STORE", "event root mismatch", 500)
        previous = event["event_root"]


def ingest_request(
    *,
    body: bytes,
    headers: Mapping[str, Any],
    tenant_from_path: str,
    registry: dict[str, Any],
    store_root: Path,
    now: dt.datetime,
    clock_skew_seconds: int = DEFAULT_CLOCK_SKEW_SECONDS,
) -> tuple[dict[str, Any], bool]:
    if now.tzinfo != dt.timezone.utc:
        raise IngestError("INVALID_SERVER_TIME", "server time must be UTC", 500)
    request = validate_request(strict_loads(body))
    auth = AuthHeaders.from_mapping(headers)
    verify_authentication(
        body=body,
        request=request,
        tenant_from_path=tenant_from_path,
        auth=auth,
        registry=registry,
        now=now,
        clock_skew_seconds=clock_skew_seconds,
    )

    tenant_dir = confined_tenant_directory(store_root, tenant_from_path)
    tenant_dir.mkdir(parents=True, exist_ok=True)
    lock_path = safe_store_file(tenant_dir, ".ingest.lock")
    events_path = safe_store_file(tenant_dir, "events.jsonl")

    nofollow = getattr(os, "O_NOFOLLOW", 0)
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | nofollow, 0o600)
    with os.fdopen(lock_fd, "a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        events = _load_events_unlocked(events_path)
        for event in events:
            if event["idempotency_key"] == auth.idempotency_key:
                if event["content_digest"] != auth.content_digest:
                    raise IngestError(
                        "IDEMPOTENCY_CONFLICT",
                        "idempotency key was already used with different content",
                        409,
                    )
                return event["receipt"], True
        for event in events:
            if event["key_id"] == auth.key_id and event["nonce"] == auth.nonce:
                raise IngestError("NONCE_REPLAY", "nonce has already been used", 409)

        index = len(events) + 1
        previous_root = events[-1]["event_root"] if events else ZERO_ROOT
        stored_at = format_utc(now)
        cert = request["assured_action"]["certificate"]
        provisional_event = {
            "profile_id": EVENT_PROFILE,
            "event_index": index,
            "tenant_id": tenant_from_path,
            "request_id": request["request_id"],
            "idempotency_key": auth.idempotency_key,
            "key_id": auth.key_id,
            "nonce": auth.nonce,
            "authentication_timestamp": auth.timestamp,
            "content_digest": auth.content_digest,
            "request": request,
            "previous_event_root": previous_root,
            "receipt": None,
        }
        event_subject = dict(provisional_event)
        event_subject["receipt"] = {
            "profile_id": RECEIPT_PROFILE,
            "tenant_id": tenant_from_path,
            "request_id": request["request_id"],
            "action_id": cert["action"]["action_id"],
            "decision": cert["decision"],
            "content_digest": auth.content_digest,
            "event_index": index,
            "previous_event_root": previous_root,
            "stored_at": stored_at,
        }
        event_root = domain_hash(EVENT_PROFILE + ".subject", event_subject)
        receipt = {
            "profile_id": RECEIPT_PROFILE,
            "status": "ACCEPTED",
            "tenant_id": tenant_from_path,
            "request_id": request["request_id"],
            "action_id": cert["action"]["action_id"],
            "decision": cert["decision"],
            "content_digest": auth.content_digest,
            "event_index": index,
            "previous_event_root": previous_root,
            "event_root": event_root,
            "stored_at": stored_at,
            "financial_status": "RECORDED_NOT_PAYABLE",
            "payments_executed": False,
            "insurance_provided": False,
            "deployment_performed": False,
            "authority_granted": False,
            "provenance_cryptographically_verified_by_api": False,
        }
        receipt["receipt_root"] = domain_hash(RECEIPT_PROFILE, receipt)
        event = {
            **provisional_event,
            "receipt": receipt,
            "event_root": event_root,
        }
        verify_receipt(receipt)
        expected_subject = dict(provisional_event)
        expected_subject["receipt"] = event_subject["receipt"]
        if event_root != domain_hash(EVENT_PROFILE + ".subject", expected_subject):
            raise IngestError("INTERNAL_ROOT_ERROR", "event subject root mismatch", 500)

        line = canonical_bytes(event) + b"\n"
        fd = os.open(events_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | nofollow, 0o600)
        try:
            os.write(fd, line)
            os.fsync(fd)
        finally:
            os.close(fd)
        stored_events = _load_events_unlocked(events_path)
        if len(stored_events) != index:
            raise IngestError("EVENT_APPEND_CONFLICT", "event store length mismatch after append", 500)
        return receipt, False


def export_dataset(
    *,
    store_root: Path,
    tenant_id: str,
    generated_at: str,
) -> dict[str, Any]:
    parse_utc(generated_at, "generated_at")
    tenant_dir = confined_tenant_directory(store_root, tenant_id)
    events_path = safe_store_file(tenant_dir, "events.jsonl")
    events = _load_events_unlocked(events_path)
    actions = [event["request"]["assured_action"] for event in events]
    return {
        "profile_id": DATASET_PROFILE,
        "tenant_id": tenant_id,
        "generated_at": generated_at,
        "financial_mode": "SIMULATION_ONLY",
        "actions": actions,
    }


def headers_to_json(headers: Mapping[str, str]) -> str:
    return json.dumps(dict(sorted(headers.items())), indent=2, sort_keys=True) + "\n"


def load_header_file(path: Path) -> dict[str, str]:
    value = strict_loads(path.read_bytes())
    if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        raise IngestError("INVALID_HEADER_FILE", "header file must be a string map", 400)
    return value


class IngestionHandler(http.server.BaseHTTPRequestHandler):
    server_version = "ProofPathIngestion/0.1"

    def _json_response(self, status: int, payload: dict[str, Any], extra_headers: Mapping[str, str] | None = None) -> None:
        data = canonical_bytes(payload) + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if urlsplit(self.path).path == "/healthz":
            self._json_response(200, {"status": "ok", "profile_id": REQUEST_PROFILE})
        else:
            self._json_response(404, {"error": {"code": "NOT_FOUND", "message": "route not found"}})

    def do_POST(self) -> None:  # noqa: N802
        try:
            path = urlsplit(self.path).path
            match = re.fullmatch(r"/v1/tenants/([a-z0-9][a-z0-9-]{2,62})/assured-actions", path)
            if not match:
                raise IngestError("NOT_FOUND", "route not found", 404)
            length_text = self.headers.get("Content-Length")
            if length_text is None or not length_text.isdigit():
                raise IngestError("INVALID_CONTENT_LENGTH", "Content-Length is required", 411)
            length = int(length_text)
            if length > self.server.max_body_bytes:  # type: ignore[attr-defined]
                raise IngestError("BODY_TOO_LARGE", "request body exceeds maximum size", 413)
            body = self.rfile.read(length)
            if len(body) != length:
                raise IngestError("INCOMPLETE_BODY", "request body is incomplete", 400)
            now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
            receipt, replay = ingest_request(
                body=body,
                headers=self.headers,
                tenant_from_path=match.group(1),
                registry=self.server.registry,  # type: ignore[attr-defined]
                store_root=self.server.store_root,  # type: ignore[attr-defined]
                now=now,
                clock_skew_seconds=self.server.clock_skew_seconds,  # type: ignore[attr-defined]
            )
            self._json_response(
                200 if replay else 201,
                receipt,
                {"X-ProofPath-Idempotent-Replay": "true" if replay else "false"},
            )
        except IngestError as exc:
            self._json_response(exc.http_status, {"error": {"code": exc.code, "message": exc.message}})
        except Exception:
            self._json_response(500, {"error": {"code": "INTERNAL_ERROR", "message": "internal ingestion error"}})

    def log_message(self, format_string: str, *args: Any) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format_string % args))


class IngestionHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        registry: dict[str, Any],
        store_root: Path,
        clock_skew_seconds: int,
        max_body_bytes: int,
    ):
        super().__init__(server_address, IngestionHandler)
        self.registry = registry
        self.store_root = store_root
        self.clock_skew_seconds = clock_skew_seconds
        self.max_body_bytes = max_body_bytes


def command_sign(args: argparse.Namespace) -> int:
    body = Path(args.body).read_bytes()
    request = validate_request(strict_loads(body))
    if request["tenant_id"] != args.tenant:
        raise IngestError("TENANT_BINDING_CONFLICT", "body tenant differs from --tenant", 400)
    secret = os.environ.get(args.secret_env)
    if secret is None:
        raise IngestError("KEY_MATERIAL_UNAVAILABLE", f"environment variable {args.secret_env} is not set", 500)
    headers = sign_headers(
        body=body,
        tenant_id=args.tenant,
        key_id=args.key_id,
        secret=secret,
        timestamp=args.timestamp,
        nonce=args.nonce,
        idempotency_key=args.idempotency_key,
    )
    Path(args.headers_out).write_text(headers_to_json(headers), encoding="utf-8")
    return 0


def command_ingest(args: argparse.Namespace) -> int:
    body = Path(args.body).read_bytes()
    headers = load_header_file(Path(args.headers))
    registry = load_registry(Path(args.registry))
    now = parse_utc(args.now, "now")
    receipt, replay = ingest_request(
        body=body,
        headers=headers,
        tenant_from_path=args.tenant,
        registry=registry,
        store_root=Path(args.store),
        now=now,
        clock_skew_seconds=args.clock_skew_seconds,
    )
    output = Path(args.receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(receipt) + b"\n")
    sys.stdout.write(f"ProofPath ingestion: {'IDEMPOTENT_REPLAY' if replay else 'ACCEPTED'} / {receipt['event_root']}\n")
    return 0


def command_export(args: argparse.Namespace) -> int:
    dataset = export_dataset(
        store_root=Path(args.store),
        tenant_id=args.tenant,
        generated_at=args.generated_at,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical_bytes(dataset) + b"\n")
    sys.stdout.write(f"ProofPath ingestion export: actions={len(dataset['actions'])}\n")
    return 0


def command_serve(args: argparse.Namespace) -> int:
    registry = load_registry(Path(args.registry))
    server = IngestionHTTPServer(
        (args.host, args.port),
        registry,
        Path(args.store),
        args.clock_skew_seconds,
        args.max_body_bytes,
    )
    sys.stderr.write(f"ProofPath ingestion listening on http://{args.host}:{args.port}\n")
    server.serve_forever()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ProofPath Control Cloud authenticated ingestion")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sign = subparsers.add_parser("sign", help="sign exact request bytes")
    sign.add_argument("--body", required=True)
    sign.add_argument("--tenant", required=True)
    sign.add_argument("--key-id", required=True)
    sign.add_argument("--secret-env", required=True)
    sign.add_argument("--timestamp", required=True)
    sign.add_argument("--nonce", default=None)
    sign.add_argument("--idempotency-key", default=None)
    sign.add_argument("--headers-out", required=True)
    sign.set_defaults(func=command_sign)

    ingest = subparsers.add_parser("ingest", help="authenticate and append one request")
    ingest.add_argument("--body", required=True)
    ingest.add_argument("--headers", required=True)
    ingest.add_argument("--registry", required=True)
    ingest.add_argument("--store", required=True)
    ingest.add_argument("--tenant", required=True)
    ingest.add_argument("--now", required=True)
    ingest.add_argument("--receipt", required=True)
    ingest.add_argument("--clock-skew-seconds", type=int, default=DEFAULT_CLOCK_SKEW_SECONDS)
    ingest.set_defaults(func=command_ingest)

    export = subparsers.add_parser("export", help="export tenant events as Control Cloud dataset")
    export.add_argument("--store", required=True)
    export.add_argument("--tenant", required=True)
    export.add_argument("--generated-at", required=True)
    export.add_argument("--output", required=True)
    export.set_defaults(func=command_export)

    serve = subparsers.add_parser("serve", help="run the reference HTTP service")
    serve.add_argument("--registry", required=True)
    serve.add_argument("--store", required=True)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--clock-skew-seconds", type=int, default=DEFAULT_CLOCK_SKEW_SECONDS)
    serve.add_argument("--max-body-bytes", type=int, default=MAX_BODY_BYTES)
    serve.set_defaults(func=command_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "sign":
        if args.nonce is None:
            args.nonce = secrets.token_urlsafe(24)
        if args.idempotency_key is None:
            args.idempotency_key = "idem-" + secrets.token_urlsafe(20)
    try:
        return int(args.func(args))
    except IngestError as exc:
        sys.stderr.write(f"ProofPath ingestion error [{exc.code}]: {exc.message}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
