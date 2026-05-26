#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import parse_qs, urlparse

from payment_guard import append_audit, decide, get_previous_hash, load_json


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787


def parse_mode(raw: Any) -> str:
    mode = str(raw or "enforce").strip().lower()
    if mode not in {"enforce", "shadow"}:
        raise ValueError("mode must be 'enforce' or 'shadow'")
    return mode


def execution_flags(mode: str, decision: str) -> Tuple[bool, bool]:
    if mode == "enforce":
        allowed = decision == "ACCEPT"
        return allowed, not allowed

    # shadow mode
    would_block = decision in {"HOLD", "BLOCK"}
    return True, would_block


def read_audit_records(path: Path, limit: int) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    selected = lines[-limit:]
    return [json.loads(line) for line in selected]


class PaymentGuardServiceHandler(BaseHTTPRequestHandler):
    server_version = "AgentPaymentGuardService/0.1"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/v1/health":
            self._send_json(
                HTTPStatus.OK,
                {"status": "ok", "surface": "agent-payment-guard-service", "version": "0.1"},
            )
            return

        if parsed.path == "/v1/audit/records":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["20"])[0])
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "limit must be an integer"})
                return
            limit = min(max(limit, 1), 100)
            records = read_audit_records(self.server.audit_path, limit)
            self._send_json(HTTPStatus.OK, {"records": records, "count": len(records), "limit": limit})
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/v1/payment-proposals/evaluate":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        payload = self._read_json_body()
        if isinstance(payload, tuple):
            status, body = payload
            self._send_json(status, body)
            return

        try:
            mode = parse_mode(payload.get("mode"))
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        proposal = payload.get("proposal")
        if not isinstance(proposal, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "proposal must be an object"})
            return

        envelope = payload.get("intent_envelope")
        if envelope is not None and not isinstance(envelope, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "intent_envelope must be an object or null"})
            return

        decision, reason, intent_meta = decide(
            proposal=proposal,
            policy=self.server.policy,
            envelope=envelope,
            strict_mode=(mode == "enforce"),
            audit_path=self.server.audit_path,
        )
        append_audit(self.server.audit_path, proposal, decision, reason, intent_meta)
        audit_hash = get_previous_hash(self.server.audit_path)
        execution_allowed, would_block = execution_flags(mode, decision)

        self._send_json(
            HTTPStatus.OK,
            {
                "mode": mode,
                "decision": decision,
                "reason": reason,
                "execution_allowed": execution_allowed,
                "would_block": would_block,
                "audit_hash": audit_hash,
            },
        )

    def _read_json_body(self) -> Dict[str, Any] | Tuple[HTTPStatus, Dict[str, str]]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return HTTPStatus.BAD_REQUEST, {"error": "invalid content length"}

        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid JSON body"}

        if not isinstance(payload, dict):
            return HTTPStatus.BAD_REQUEST, {"error": "request body must be an object"}
        return payload

    def _send_json(self, status: HTTPStatus, payload: Dict[str, Any]) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--policy", default="examples/agent-payment-guard/payment_policy.json")
    parser.add_argument("--audit-path", default=".proofpath/audit.jsonl")
    args = parser.parse_args()

    policy = load_json(Path(args.policy))
    server = ThreadingHTTPServer((args.host, args.port), PaymentGuardServiceHandler)
    server.policy = policy
    server.audit_path = Path(args.audit_path)

    print(f"Agent Payment Guard service listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
