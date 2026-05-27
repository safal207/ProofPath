#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

TRANSACTIONS_PATH = Path(".proofpath/mock-rail-transactions.jsonl")


def load_transactions() -> list[Dict[str, Any]]:
    if not TRANSACTIONS_PATH.exists():
        return []
    return [
        json.loads(line)
        for line in TRANSACTIONS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def append_transaction(record: Dict[str, Any]) -> None:
    TRANSACTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRANSACTIONS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


class MockRailHandler(BaseHTTPRequestHandler):
    server_version = "MockPaymentRail/0.1"

    def do_GET(self) -> None:
        if self.path == "/v1/mock-rail/health":
            self._send_json(
                HTTPStatus.OK,
                {"status": "ok", "surface": "mock-payment-rail", "version": "0.1"},
            )
        elif self.path == "/v1/mock-rail/transactions":
            txs = load_transactions()
            self._send_json(HTTPStatus.OK, {"transactions": txs, "count": len(txs)})
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/v1/mock-rail/execute":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        payload = self._read_json_body()
        if isinstance(payload, tuple):
            status, body = payload
            self._send_json(status, body)
            return

        record = {
            "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "surface": "mock-payment-rail",
            "status": "MOCK_EXECUTED",
            "agent_id": payload.get("agent_id"),
            "asset": payload.get("asset"),
            "amount": payload.get("amount"),
            "recipient": payload.get("recipient"),
            "proofpath_decision": payload.get("proofpath_decision"),
            "proofpath_audit_hash": payload.get("proofpath_audit_hash"),
        }
        append_transaction(record)
        self._send_json(HTTPStatus.OK, {"status": "MOCK_EXECUTED", "transaction": record})

    def _read_json_body(self) -> Dict[str, Any] | tuple:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return HTTPStatus.BAD_REQUEST, {"error": "invalid content length"}
        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return HTTPStatus.BAD_REQUEST, {"error": "invalid JSON body"}

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
    parser = argparse.ArgumentParser(description="Mock Payment Rail HTTP server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18791)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), MockRailHandler)
    print(f"Mock Payment Rail listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
