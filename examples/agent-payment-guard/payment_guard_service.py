#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from payment_guard import append_audit, decide, get_previous_hash, load_json


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787
DEFAULT_MODE = "enforce"
DEFAULT_AUDIT_DEFAULT_LIMIT = 20
DEFAULT_AUDIT_MAX_LIMIT = 100


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(path: Path) -> Dict[str, Any]:
    """Load and validate JSON config. Raises SystemExit on invalid config."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _fail(f"Config file not found: {path}")
    except json.JSONDecodeError as exc:
        _fail(f"Config file is not valid JSON: {exc}")

    if not isinstance(raw, dict):
        _fail("Config must be a JSON object")

    mode = raw.get("mode", DEFAULT_MODE)
    if mode not in {"enforce", "shadow"}:
        _fail(f"Config 'mode' must be 'enforce' or 'shadow', got: {mode!r}")

    require_signed_intent = raw.get("require_signed_intent", False)
    if not isinstance(require_signed_intent, bool):
        _fail("Config 'require_signed_intent' must be a boolean")

    policy_path = raw.get("policy_path")
    if not isinstance(policy_path, str) or not policy_path:
        _fail("Config 'policy_path' must be a non-empty string")

    audit_path = raw.get("audit_path")
    if not isinstance(audit_path, str) or not audit_path:
        _fail("Config 'audit_path' must be a non-empty string")

    service = raw.get("service", {})
    if not isinstance(service, dict):
        _fail("Config 'service' must be an object")

    host = service.get("host", DEFAULT_HOST)
    if not isinstance(host, str) or not host:
        _fail("Config 'service.host' must be a non-empty string")

    port = service.get("port", DEFAULT_PORT)
    if not isinstance(port, int) or isinstance(port, bool) or not (1 <= port <= 65535):
        _fail(f"Config 'service.port' must be an integer between 1 and 65535, got: {port!r}")

    audit_cfg = raw.get("audit", {})
    if not isinstance(audit_cfg, dict):
        _fail("Config 'audit' must be an object")

    default_limit = audit_cfg.get("recent_records_default_limit", DEFAULT_AUDIT_DEFAULT_LIMIT)
    if not isinstance(default_limit, int) or isinstance(default_limit, bool) or default_limit < 1:
        _fail("Config 'audit.recent_records_default_limit' must be a positive integer")

    max_limit = audit_cfg.get("recent_records_max_limit", DEFAULT_AUDIT_MAX_LIMIT)
    if not isinstance(max_limit, int) or isinstance(max_limit, bool) or max_limit < 1:
        _fail("Config 'audit.recent_records_max_limit' must be a positive integer")

    if default_limit > max_limit:
        _fail(
            f"Config 'audit.recent_records_default_limit' ({default_limit}) "
            f"must not exceed 'audit.recent_records_max_limit' ({max_limit})"
        )

    return {
        "mode": mode,
        "require_signed_intent": require_signed_intent,
        "policy_path": policy_path,
        "audit_path": audit_path,
        "host": host,
        "port": port,
        "audit_default_limit": default_limit,
        "audit_max_limit": max_limit,
    }


def _fail(msg: str) -> None:
    print(f"[payment-guard-service] Config error: {msg}", file=sys.stderr)
    raise SystemExit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_mode(raw: Any) -> str:
    mode = str(raw or "").strip().lower()
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


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

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
            raw_limit = query.get("limit", [None])[0]
            default_limit: int = self.server.audit_default_limit  # type: ignore[attr-defined]
            max_limit: int = self.server.audit_max_limit  # type: ignore[attr-defined]

            if raw_limit is None:
                limit = default_limit
            else:
                try:
                    limit = int(raw_limit)
                except ValueError:
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {"error": "limit must be an integer"},
                    )
                    return
                if limit < 1:
                    self._send_json(
                        HTTPStatus.BAD_REQUEST,
                        {"error": "limit must be a positive integer"},
                    )
                    return
                limit = min(limit, max_limit)

            records = read_audit_records(self.server.audit_path, limit)  # type: ignore[attr-defined]
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

        # Mode: request body overrides config; omitting mode uses config default
        raw_mode = payload.get("mode")
        if raw_mode is None:
            mode = self.server.config_mode  # type: ignore[attr-defined]
        else:
            try:
                mode = parse_mode(raw_mode)
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

        # strict_mode: enforce mode OR config.require_signed_intent (strictest wins)
        config_strict: bool = self.server.require_signed_intent  # type: ignore[attr-defined]
        request_strict = mode == "enforce"
        strict_mode = config_strict or request_strict

        decision, reason, intent_meta = decide(
            proposal=proposal,
            policy=self.server.policy,  # type: ignore[attr-defined]
            envelope=envelope,
            strict_mode=strict_mode,
            audit_path=self.server.audit_path,  # type: ignore[attr-defined]
        )
        append_audit(self.server.audit_path, proposal, decision, reason, intent_meta)  # type: ignore[attr-defined]
        audit_hash = get_previous_hash(self.server.audit_path)  # type: ignore[attr-defined]
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Agent Payment Guard HTTP service")
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Path to JSON config file (recommended)",
    )
    # Legacy CLI overrides kept for backwards compatibility; config takes precedence
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--policy", default=None)
    parser.add_argument("--audit-path", default=None)
    args = parser.parse_args()

    # Build effective settings: start from hardcoded defaults, apply config, then CLI overrides
    host = DEFAULT_HOST
    port = DEFAULT_PORT
    policy_path = "examples/agent-payment-guard/payment_policy.json"
    audit_path_str = ".proofpath/audit.jsonl"
    config_mode = DEFAULT_MODE
    require_signed_intent = False
    audit_default_limit = DEFAULT_AUDIT_DEFAULT_LIMIT
    audit_max_limit = DEFAULT_AUDIT_MAX_LIMIT

    if args.config:
        cfg = load_config(Path(args.config))
        host = cfg["host"]
        port = cfg["port"]
        policy_path = cfg["policy_path"]
        audit_path_str = cfg["audit_path"]
        config_mode = cfg["mode"]
        require_signed_intent = cfg["require_signed_intent"]
        audit_default_limit = cfg["audit_default_limit"]
        audit_max_limit = cfg["audit_max_limit"]

    # CLI flags override config if explicitly passed
    if args.host is not None:
        host = args.host
    if args.port is not None:
        port = args.port
    if args.policy is not None:
        policy_path = args.policy
    if args.audit_path is not None:
        audit_path_str = args.audit_path

    policy = load_json(Path(policy_path))
    server = ThreadingHTTPServer((host, port), PaymentGuardServiceHandler)
    server.policy = policy
    server.audit_path = Path(audit_path_str)
    server.config_mode = config_mode
    server.require_signed_intent = require_signed_intent
    server.audit_default_limit = audit_default_limit
    server.audit_max_limit = audit_max_limit

    print(f"Agent Payment Guard service listening on http://{host}:{port}")
    if args.config:
        print(f"  config: {args.config}")
    print(f"  mode: {config_mode} | require_signed_intent: {require_signed_intent}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
