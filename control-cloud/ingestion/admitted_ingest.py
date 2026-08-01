#!/usr/bin/env python3
"""Admission-gated ProofPath Control Cloud ingestion.

This runtime accepts a tenant request only when a server-side Sigstore admission
result exists for the exact attested certificate bytes and matches the certificate
semantics embedded in the signed request.

It reuses authentication and request validation from ingestion v0.1, but stores
admission-gated events in a separate append-only chain and emits a v0.2 receipt.
"""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import http.server
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit


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
base = _load_module("proofpath_ingestion_v01", REPO_ROOT / "control-cloud/ingestion/ingest.py")
admission = _load_module(
    "proofpath_sigstore_admission_v01",
    REPO_ROOT / "control-cloud/admission/verify_sigstore.py",
)

RECEIPT_PROFILE = "proofpath.control-cloud.admitted-ingest-receipt.v0.1"
EVENT_PROFILE = "proofpath.control-cloud.admitted-ingest-event.v0.1"
RESULT_PROFILE = admission.RESULT_PROFILE
ZERO_ROOT = "sha256:" + ("0" * 64)
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class AdmittedIngestError(base.IngestError):
    """Admission-gated ingestion error."""


def _receipt_without_root(receipt: dict[str, Any]) -> dict[str, Any]:
    copy = dict(receipt)
    copy.pop("receipt_root", None)
    return copy


def safe_admitted_store_file(tenant_dir: Path, filename: str) -> Path:
    if filename not in {"admitted-events.jsonl", ".admitted-ingest.lock"}:
        raise AdmittedIngestError("INVALID_STORE_FILE", "unsupported admitted store filename", 500)
    path = tenant_dir / filename
    if path.is_symlink():
        raise AdmittedIngestError("STORE_SYMLINK_REJECTED", f"{filename} must not be a symlink", 500)
    if path.parent.resolve() != tenant_dir.resolve():
        raise AdmittedIngestError("STORE_PATH_ESCAPE", f"{filename} escapes tenant directory", 500)
    return path


def result_file_for_subject(admissions_dir: Path, subject_digest: str) -> Path:
    if not isinstance(subject_digest, str) or not DIGEST_RE.fullmatch(subject_digest):
        raise AdmittedIngestError("INVALID_PROVENANCE_DIGEST", "subject digest is malformed", 422)
    root = admissions_dir.resolve()
    filename = subject_digest.split(":", 1)[1] + ".json"
    candidate = root / filename
    if candidate.is_symlink():
        raise AdmittedIngestError("ADMISSION_RESULT_SYMLINK_REJECTED", "admission result must not be a symlink", 500)
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise AdmittedIngestError("ADMISSION_RESULT_PATH_ESCAPE", "admission result path escapes directory", 500) from exc
    if not resolved.is_file():
        raise AdmittedIngestError("ADMISSION_RESULT_NOT_FOUND", "trusted admission result is unavailable", 422)
    return resolved


def load_bound_admission_result(
    request: dict[str, Any],
    admissions_dir: Path,
) -> dict[str, Any]:
    binding = request["provenance_binding"]
    if binding["status"] != "EXTERNAL_RESULT_BOUND":
        raise AdmittedIngestError(
            "CRYPTOGRAPHIC_PROVENANCE_REQUIRED",
            "admission-gated ingestion requires EXTERNAL_RESULT_BOUND provenance",
            422,
        )
    path = result_file_for_subject(admissions_dir, binding["subject_digest"])
    try:
        result = admission.validate_result(admission.load_json(path))
    except admission.AdmissionError as exc:
        raise AdmittedIngestError("ADMISSION_RESULT_INVALID", f"{exc.code}: {exc.message}", 422) from exc

    certificate = request["assured_action"]["certificate"]
    certificate_canonical_digest = base.raw_sha256(base.canonical_bytes(certificate))
    action = certificate["action"]
    checks = [
        (result["subject_digest"], binding["subject_digest"], "subject digest"),
        (result["verifier_identity"], binding["verifier_identity"], "verifier identity"),
        (result["verified_at"], binding["verified_at"], "verification time"),
        (result["certificate_canonical_digest"], certificate_canonical_digest, "certificate canonical digest"),
        (result["clearance_root"], certificate["clearance_root"], "clearance root"),
        (result["repository"], action["repository"], "repository"),
        (result["source_sha"], action["commit_sha"], "source SHA"),
        (result["artifact_digest"], action["artifact_digest"], "artifact digest"),
    ]
    for actual, expected, name in checks:
        if actual != expected:
            raise AdmittedIngestError(
                "ADMISSION_BINDING_CONFLICT",
                f"admission {name} differs from signed request certificate",
                422,
            )
    if result["runner_environment"] != "github-hosted" or result["deny_self_hosted_runners"] is not True:
        raise AdmittedIngestError("ADMISSION_RUNNER_CONFLICT", "admission did not enforce GitHub-hosted runner", 422)
    if result["cert_oidc_issuer"] != admission.DEFAULT_ISSUER:
        raise AdmittedIngestError("ADMISSION_ISSUER_CONFLICT", "admission issuer is not exact GitHub OIDC", 422)
    if result["github_attestation_verified"] is not True or result["transparency_timestamp_verified"] is not True:
        raise AdmittedIngestError("ADMISSION_CRYPTOGRAPHY_UNVERIFIED", "admission cryptography is incomplete", 422)
    return result


def _event_subject_for_root(event: dict[str, Any]) -> dict[str, Any]:
    receipt = event["receipt"]
    receipt_subject = {
        "profile_id": receipt["profile_id"],
        "tenant_id": receipt["tenant_id"],
        "request_id": receipt["request_id"],
        "action_id": receipt["action_id"],
        "decision": receipt["decision"],
        "content_digest": receipt["content_digest"],
        "event_index": receipt["event_index"],
        "previous_event_root": receipt["previous_event_root"],
        "admission_result_root": receipt["admission_result_root"],
        "subject_digest": receipt["subject_digest"],
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
        "admission_result_root": event["admission_result_root"],
        "request": event["request"],
        "previous_event_root": event["previous_event_root"],
        "receipt": receipt_subject,
    }


def verify_receipt(receipt: dict[str, Any]) -> None:
    required = {
        "profile_id",
        "status",
        "tenant_id",
        "request_id",
        "action_id",
        "decision",
        "content_digest",
        "event_index",
        "previous_event_root",
        "event_root",
        "admission_result_root",
        "subject_digest",
        "stored_at",
        "receipt_root",
        "financial_status",
        "payments_executed",
        "insurance_provided",
        "deployment_performed",
        "authority_granted",
        "provenance_cryptographically_verified_by_api",
    }
    if set(receipt) != required or receipt.get("profile_id") != RECEIPT_PROFILE:
        raise AdmittedIngestError("CORRUPT_ADMITTED_STORE", "admitted receipt shape is invalid", 500)
    if receipt["status"] != "ACCEPTED_WITH_CRYPTOGRAPHIC_PROVENANCE":
        raise AdmittedIngestError("CORRUPT_ADMITTED_STORE", "admitted receipt status is invalid", 500)
    if receipt["provenance_cryptographically_verified_by_api"] is not True:
        raise AdmittedIngestError("CORRUPT_ADMITTED_STORE", "admitted receipt lost provenance verification", 500)
    for field in ("payments_executed", "insurance_provided", "deployment_performed", "authority_granted"):
        if receipt[field] is not False:
            raise AdmittedIngestError("CORRUPT_ADMITTED_STORE", f"receipt {field} violates boundary", 500)
    for field in ("event_root", "previous_event_root", "admission_result_root", "subject_digest", "content_digest"):
        if not isinstance(receipt[field], str) or not DIGEST_RE.fullmatch(receipt[field]):
            raise AdmittedIngestError("CORRUPT_ADMITTED_STORE", f"receipt {field} is invalid", 500)
    expected = base.domain_hash(RECEIPT_PROFILE, _receipt_without_root(receipt))
    if receipt["receipt_root"] != expected:
        raise AdmittedIngestError("CORRUPT_ADMITTED_STORE", "admitted receipt root mismatch", 500)


def verify_event_chain(events: list[dict[str, Any]]) -> None:
    previous = ZERO_ROOT
    seen_idempotency: set[str] = set()
    seen_nonce_pairs: set[tuple[str, str]] = set()
    for expected_index, event in enumerate(events, 1):
        required = {
            "profile_id",
            "event_index",
            "tenant_id",
            "request_id",
            "idempotency_key",
            "key_id",
            "nonce",
            "authentication_timestamp",
            "content_digest",
            "admission_result_root",
            "request",
            "previous_event_root",
            "receipt",
            "event_root",
        }
        if set(event) != required or event.get("profile_id") != EVENT_PROFILE:
            raise AdmittedIngestError("CORRUPT_ADMITTED_STORE", "admitted event shape is invalid", 500)
        if event["event_index"] != expected_index or event["previous_event_root"] != previous:
            raise AdmittedIngestError("CORRUPT_ADMITTED_STORE", "admitted event chain is not contiguous", 500)
        if event["idempotency_key"] in seen_idempotency:
            raise AdmittedIngestError("CORRUPT_ADMITTED_STORE", "duplicate idempotency key", 500)
        nonce_pair = (event["key_id"], event["nonce"])
        if nonce_pair in seen_nonce_pairs:
            raise AdmittedIngestError("CORRUPT_ADMITTED_STORE", "duplicate nonce", 500)
        seen_idempotency.add(event["idempotency_key"])
        seen_nonce_pairs.add(nonce_pair)
        receipt = event["receipt"]
        if not isinstance(receipt, dict):
            raise AdmittedIngestError("CORRUPT_ADMITTED_STORE", "receipt is not an object", 500)
        verify_receipt(receipt)
        if receipt["event_root"] != event["event_root"] or receipt["event_index"] != expected_index:
            raise AdmittedIngestError("CORRUPT_ADMITTED_STORE", "receipt does not bind event", 500)
        if receipt["admission_result_root"] != event["admission_result_root"]:
            raise AdmittedIngestError("CORRUPT_ADMITTED_STORE", "receipt admission root mismatch", 500)
        expected_root = base.domain_hash(EVENT_PROFILE + ".subject", _event_subject_for_root(event))
        if event["event_root"] != expected_root:
            raise AdmittedIngestError("CORRUPT_ADMITTED_STORE", "admitted event root mismatch", 500)
        previous = event["event_root"]


def load_events_unlocked(events_path: Path) -> list[dict[str, Any]]:
    if not events_path.exists():
        return []
    if events_path.is_symlink():
        raise AdmittedIngestError("STORE_SYMLINK_REJECTED", "admitted event store must not be a symlink", 500)
    events: list[dict[str, Any]] = []
    with events_path.open("rb") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise AdmittedIngestError("CORRUPT_ADMITTED_STORE", f"blank line {line_number}", 500)
            value = base.strict_loads(line)
            if not isinstance(value, dict):
                raise AdmittedIngestError("CORRUPT_ADMITTED_STORE", f"line {line_number} is not an object", 500)
            events.append(value)
    verify_event_chain(events)
    return events


def ingest_admitted_request(
    *,
    body: bytes,
    headers: Mapping[str, Any],
    tenant_from_path: str,
    registry: dict[str, Any],
    store_root: Path,
    admissions_dir: Path,
    now: dt.datetime,
    clock_skew_seconds: int = base.DEFAULT_CLOCK_SKEW_SECONDS,
) -> tuple[dict[str, Any], bool]:
    if now.tzinfo != dt.timezone.utc:
        raise AdmittedIngestError("INVALID_SERVER_TIME", "server time must be UTC", 500)
    request = base.validate_request(base.strict_loads(body))
    auth = base.AuthHeaders.from_mapping(headers)
    base.verify_authentication(
        body=body,
        request=request,
        tenant_from_path=tenant_from_path,
        auth=auth,
        registry=registry,
        now=now,
        clock_skew_seconds=clock_skew_seconds,
    )
    result = load_bound_admission_result(request, admissions_dir)

    tenant_dir = base.confined_tenant_directory(store_root, tenant_from_path)
    tenant_dir.mkdir(parents=True, exist_ok=True)
    lock_path = safe_admitted_store_file(tenant_dir, ".admitted-ingest.lock")
    events_path = safe_admitted_store_file(tenant_dir, "admitted-events.jsonl")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | nofollow, 0o600)

    with os.fdopen(lock_fd, "a+b") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        events = load_events_unlocked(events_path)
        for event in events:
            if event["idempotency_key"] == auth.idempotency_key:
                if event["content_digest"] != auth.content_digest:
                    raise AdmittedIngestError(
                        "IDEMPOTENCY_CONFLICT",
                        "idempotency key was already used with different content",
                        409,
                    )
                return event["receipt"], True
        for event in events:
            if event["key_id"] == auth.key_id and event["nonce"] == auth.nonce:
                raise AdmittedIngestError("NONCE_REPLAY", "nonce has already been used", 409)

        index = len(events) + 1
        previous_root = events[-1]["event_root"] if events else ZERO_ROOT
        stored_at = base.format_utc(now)
        cert = request["assured_action"]["certificate"]
        provisional_event: dict[str, Any] = {
            "profile_id": EVENT_PROFILE,
            "event_index": index,
            "tenant_id": tenant_from_path,
            "request_id": request["request_id"],
            "idempotency_key": auth.idempotency_key,
            "key_id": auth.key_id,
            "nonce": auth.nonce,
            "authentication_timestamp": auth.timestamp,
            "content_digest": auth.content_digest,
            "admission_result_root": result["result_root"],
            "request": request,
            "previous_event_root": previous_root,
            "receipt": None,
        }
        receipt_subject = {
            "profile_id": RECEIPT_PROFILE,
            "tenant_id": tenant_from_path,
            "request_id": request["request_id"],
            "action_id": cert["action"]["action_id"],
            "decision": cert["decision"],
            "content_digest": auth.content_digest,
            "event_index": index,
            "previous_event_root": previous_root,
            "admission_result_root": result["result_root"],
            "subject_digest": result["subject_digest"],
            "stored_at": stored_at,
        }
        event_subject = dict(provisional_event)
        event_subject["receipt"] = receipt_subject
        event_root = base.domain_hash(EVENT_PROFILE + ".subject", event_subject)
        receipt: dict[str, Any] = {
            "profile_id": RECEIPT_PROFILE,
            "status": "ACCEPTED_WITH_CRYPTOGRAPHIC_PROVENANCE",
            "tenant_id": tenant_from_path,
            "request_id": request["request_id"],
            "action_id": cert["action"]["action_id"],
            "decision": cert["decision"],
            "content_digest": auth.content_digest,
            "event_index": index,
            "previous_event_root": previous_root,
            "event_root": event_root,
            "admission_result_root": result["result_root"],
            "subject_digest": result["subject_digest"],
            "stored_at": stored_at,
            "financial_status": "RECORDED_NOT_PAYABLE",
            "payments_executed": False,
            "insurance_provided": False,
            "deployment_performed": False,
            "authority_granted": False,
            "provenance_cryptographically_verified_by_api": True,
        }
        receipt["receipt_root"] = base.domain_hash(RECEIPT_PROFILE, receipt)
        event = {**provisional_event, "receipt": receipt, "event_root": event_root}
        verify_receipt(receipt)
        if event_root != base.domain_hash(EVENT_PROFILE + ".subject", _event_subject_for_root(event)):
            raise AdmittedIngestError("INTERNAL_ROOT_ERROR", "admitted event root mismatch", 500)

        line = base.canonical_bytes(event) + b"\n"
        fd = os.open(events_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | nofollow, 0o600)
        try:
            os.write(fd, line)
            os.fsync(fd)
        finally:
            os.close(fd)
        if len(load_events_unlocked(events_path)) != index:
            raise AdmittedIngestError("EVENT_APPEND_CONFLICT", "admitted store length mismatch", 500)
        return receipt, False


def export_dataset(*, store_root: Path, tenant_id: str, generated_at: str) -> dict[str, Any]:
    base.parse_utc(generated_at, "generated_at")
    tenant_dir = base.confined_tenant_directory(store_root, tenant_id)
    events_path = safe_admitted_store_file(tenant_dir, "admitted-events.jsonl")
    events = load_events_unlocked(events_path)
    return {
        "profile_id": base.DATASET_PROFILE,
        "tenant_id": tenant_id,
        "generated_at": generated_at,
        "financial_mode": "SIMULATION_ONLY",
        "actions": [event["request"]["assured_action"] for event in events],
    }


class AdmittedHandler(http.server.BaseHTTPRequestHandler):
    server_version = "ProofPathAdmittedIngestion/0.1"

    def _respond(self, status: int, payload: dict[str, Any], headers: Mapping[str, str] | None = None) -> None:
        data = base.canonical_bytes(payload) + b"\n"
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if urlsplit(self.path).path == "/healthz":
            self._respond(200, {"status": "ok", "profile_id": RECEIPT_PROFILE})
        else:
            self._respond(404, {"error": {"code": "NOT_FOUND", "message": "route not found"}})

    def do_POST(self) -> None:  # noqa: N802
        try:
            path = urlsplit(self.path).path
            match = re.fullmatch(r"/v1/tenants/([a-z0-9][a-z0-9-]{2,62})/assured-actions", path)
            if not match:
                raise AdmittedIngestError("NOT_FOUND", "route not found", 404)
            length_text = self.headers.get("Content-Length")
            if length_text is None or not length_text.isdigit():
                raise AdmittedIngestError("INVALID_CONTENT_LENGTH", "Content-Length is required", 411)
            length = int(length_text)
            if length > self.server.max_body_bytes:  # type: ignore[attr-defined]
                raise AdmittedIngestError("BODY_TOO_LARGE", "request body exceeds maximum size", 413)
            body = self.rfile.read(length)
            if len(body) != length:
                raise AdmittedIngestError("INCOMPLETE_BODY", "request body is incomplete", 400)
            receipt, replay = ingest_admitted_request(
                body=body,
                headers=self.headers,
                tenant_from_path=match.group(1),
                registry=self.server.registry,  # type: ignore[attr-defined]
                store_root=self.server.store_root,  # type: ignore[attr-defined]
                admissions_dir=self.server.admissions_dir,  # type: ignore[attr-defined]
                now=dt.datetime.now(dt.timezone.utc).replace(microsecond=0),
                clock_skew_seconds=self.server.clock_skew_seconds,  # type: ignore[attr-defined]
            )
            self._respond(
                200 if replay else 201,
                receipt,
                {"X-ProofPath-Idempotent-Replay": "true" if replay else "false"},
            )
        except base.IngestError as exc:
            self._respond(exc.http_status, {"error": {"code": exc.code, "message": exc.message}})
        except Exception:
            self._respond(500, {"error": {"code": "INTERNAL_ERROR", "message": "internal admitted ingestion error"}})

    def log_message(self, format_string: str, *args: Any) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format_string % args))


class AdmittedHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base.canonical_bytes(value) + b"\n")


def load_headers(path: Path) -> dict[str, str]:
    value = base.strict_loads(path.read_bytes())
    if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        raise AdmittedIngestError("INVALID_HEADER_FILE", "header file must be a string map", 400)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest = subparsers.add_parser("ingest")
    ingest.add_argument("--body", required=True, type=Path)
    ingest.add_argument("--headers", required=True, type=Path)
    ingest.add_argument("--registry", required=True, type=Path)
    ingest.add_argument("--store", required=True, type=Path)
    ingest.add_argument("--admissions-dir", required=True, type=Path)
    ingest.add_argument("--tenant", required=True)
    ingest.add_argument("--now", required=True)
    ingest.add_argument("--receipt", required=True, type=Path)

    export = subparsers.add_parser("export")
    export.add_argument("--store", required=True, type=Path)
    export.add_argument("--tenant", required=True)
    export.add_argument("--generated-at", required=True)
    export.add_argument("--output", required=True, type=Path)

    serve = subparsers.add_parser("serve")
    serve.add_argument("--registry", required=True, type=Path)
    serve.add_argument("--store", required=True, type=Path)
    serve.add_argument("--admissions-dir", required=True, type=Path)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--clock-skew-seconds", type=int, default=base.DEFAULT_CLOCK_SKEW_SECONDS)

    args = parser.parse_args(argv)
    try:
        if args.command == "ingest":
            body = args.body.read_bytes()
            registry = base.load_registry(args.registry)
            receipt, replay = ingest_admitted_request(
                body=body,
                headers=load_headers(args.headers),
                tenant_from_path=args.tenant,
                registry=registry,
                store_root=args.store,
                admissions_dir=args.admissions_dir,
                now=base.parse_utc(args.now, "now"),
            )
            write_json(args.receipt, receipt)
            print(
                f"ProofPath admitted ingestion: {'IDEMPOTENT_REPLAY' if replay else 'ACCEPTED'} / "
                f"{receipt['event_root']} / {receipt['admission_result_root']}",
                file=sys.stderr,
            )
            return 0
        if args.command == "export":
            dataset = export_dataset(
                store_root=args.store,
                tenant_id=args.tenant,
                generated_at=args.generated_at,
            )
            write_json(args.output, dataset)
            print(f"ProofPath admitted export: actions={len(dataset['actions'])}", file=sys.stderr)
            return 0

        registry = base.load_registry(args.registry)
        server = AdmittedHTTPServer((args.host, args.port), AdmittedHandler)
        server.registry = registry  # type: ignore[attr-defined]
        server.store_root = args.store  # type: ignore[attr-defined]
        server.admissions_dir = args.admissions_dir  # type: ignore[attr-defined]
        server.max_body_bytes = base.MAX_BODY_BYTES  # type: ignore[attr-defined]
        server.clock_skew_seconds = args.clock_skew_seconds  # type: ignore[attr-defined]
        print(f"ProofPath admitted ingestion listening on http://{args.host}:{args.port}", file=sys.stderr)
        server.serve_forever()
        return 0
    except (base.IngestError, admission.AdmissionError, OSError, ValueError, json.JSONDecodeError) as exc:
        code = exc.code if isinstance(exc, base.IngestError) else "ADMITTED_INGEST_ERROR"
        message = exc.message if isinstance(exc, base.IngestError) else str(exc)
        print(f"ProofPath admitted ingestion failed: {code}: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
