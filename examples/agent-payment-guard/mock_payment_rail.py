#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict

TRANSACTIONS_PATH = Path(".proofpath/mock-rail-transactions.jsonl")
TRANSACTIONS_LOCK = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_transactions_unlocked() -> list[Dict[str, Any]]:
    if not TRANSACTIONS_PATH.exists():
        return []
    return [
        json.loads(line)
        for line in TRANSACTIONS_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_transactions() -> list[Dict[str, Any]]:
    with TRANSACTIONS_LOCK:
        return _load_transactions_unlocked()


def _write_transactions_unlocked(transactions: list[Dict[str, Any]]) -> None:
    TRANSACTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(item, sort_keys=True) + "\n" for item in transactions)
    TRANSACTIONS_PATH.write_text(payload, encoding="utf-8")


def append_transaction(record: Dict[str, Any]) -> Dict[str, Any]:
    with TRANSACTIONS_LOCK:
        transactions = _load_transactions_unlocked()
        stored = dict(record)
        stored.setdefault("transaction_id", f"mock-tx-{len(transactions) + 1:04d}")
        transactions.append(stored)
        _write_transactions_unlocked(transactions)
        return stored


def cancel_transaction(transaction_id: str, reason: str) -> tuple[HTTPStatus, Dict[str, Any]]:
    with TRANSACTIONS_LOCK:
        transactions = _load_transactions_unlocked()
        for transaction in transactions:
            if transaction.get("transaction_id") != transaction_id:
                continue
            if transaction.get("status") != "MOCK_EXECUTED":
                return HTTPStatus.CONFLICT, {
                    "error": "transaction is not cancellable",
                    "transaction": transaction,
                }
            transaction["status"] = "MOCK_CANCELLED"
            transaction["cancelled_at"] = utc_now()
            transaction["cancellation_reason"] = reason
            _write_transactions_unlocked(transactions)
            return HTTPStatus.OK, {"status": "MOCK_CANCELLED", "transaction": transaction}
    return HTTPStatus.NOT_FOUND, {"error": "transaction not found"}


class MockRailHandler(BaseHTTPRequestHandler):
    server_version = "MockPaymentRail/0.2"

    def do_GET(self) -> None:
        if self.path == "/v1/mock-rail/health":
            self._send_json(
                HTTPStatus.OK,
                {"status": "ok", "surface": "mock-payment-rail", "version": "0.2"},
            )
        elif self.path == "/v1/mock-rail/transactions":
            transactions = load_transactions()
            successful_count = sum(
                transaction.get("status") == "MOCK_EXECUTED" for transaction in transactions
            )
            self._send_json(
                HTTPStatus.OK,
                {
                    "transactions": transactions,
                    "count": len(transactions),
                    "successful_count": successful_count,
                },
            )
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path == "/v1/mock-rail/execute":
            self._execute()
        elif self.path == "/v1/mock-rail/cancel":
            self._cancel()
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def _execute(self) -> None:
        payload = self._read_json_body()
        if isinstance(payload, tuple):
            status, body = payload
            self._send_json(status, body)
            return

        proofpath_decision = payload.get("proofpath_decision")
        record = {
            "ts": utc_now(),
            "surface": "mock-payment-rail",
            "status": "MOCK_EXECUTED",
            "origin": payload.get(
                "origin", "agent" if proofpath_decision == "ACCEPT" else "external"
            ),
            "agent_id": payload.get("agent_id"),
            "asset": payload.get("asset"),
            "amount": payload.get("amount"),
            "recipient": payload.get("recipient"),
            "intent_id": payload.get("intent_id"),
            "causal_parent": payload.get("causal_parent"),
            "proofpath_decision": proofpath_decision,
            "proofpath_audit_hash": payload.get("proofpath_audit_hash"),
        }
        stored = append_transaction(record)
        self._send_json(HTTPStatus.OK, {"status": "MOCK_EXECUTED", "transaction": stored})

    def _cancel(self) -> None:
        payload = self._read_json_body()
        if isinstance(payload, tuple):
            status, body = payload
            self._send_json(status, body)
            return
        transaction_id = payload.get("transaction_id")
        if not isinstance(transaction_id, str) or not transaction_id:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "transaction_id is required"})
            return
        reason = payload.get("reason", "targeted_containment")
        if not isinstance(reason, str) or not reason:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "reason must be a string"})
            return
        status, body = cancel_transaction(transaction_id, reason)
        self._send_json(status, body)

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
