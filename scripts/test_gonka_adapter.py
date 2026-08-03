#!/usr/bin/env python3
"""Dependency-free tests for the Gonka Compute Witness adapter."""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
import unittest
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "examples" / "compute-witness" / "gonka_adapter.py"

SPEC = importlib.util.spec_from_file_location("gonka_adapter", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ScriptedTransport:
    def __init__(self, scripted: list[Any]) -> None:
        self.scripted = list(scripted)
        self.calls: list[dict[str, Any]] = []

    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> tuple[int, dict[str, Any], dict[str, str]]:
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        if not self.scripted:
            raise AssertionError("unexpected transport call")
        item = self.scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def response(text: str, response_id: str) -> tuple[int, dict[str, Any], dict[str, str]]:
    return (
        200,
        {
            "id": response_id,
            "choices": [{"message": {"content": text}}],
        },
        {"x-request-id": response_id},
    )


class GonkaAdapterTests(unittest.TestCase):
    def config(self, fallback: bool = False) -> Any:
        fallback_provider = None
        if fallback:
            fallback_provider = MODULE.ProviderConfig(
                name="fallback",
                base_url="https://fallback.example/v1",
                api_key="fallback-secret",
                model="fallback-model",
            )
        return MODULE.GonkaConfig(
            primary=MODULE.ProviderConfig(
                name="gonka",
                base_url="https://broker.example/v1",
                api_key="primary-secret",
                model="gonka-model",
            ),
            replicas=3,
            timeout_seconds=7.0,
            agreement_threshold=0.85,
            fallback=fallback_provider,
        )

    def adapter(self, transport: Any, fallback: bool = False) -> Any:
        times = iter(
            [
                dt.datetime(2026, 8, 3, 18, 0, index, tzinfo=dt.timezone.utc)
                for index in range(30)
            ]
        )
        return MODULE.GonkaComputeWitnessAdapter(
            self.config(fallback=fallback),
            transport=transport,
            now=lambda: next(times),
            uuid_factory=lambda: uuid.UUID("12345678-1234-5678-1234-567812345678"),
        )

    def test_consensus_receipt_is_hashed_and_secret_free(self) -> None:
        transport = ScriptedTransport(
            [
                response("Supported with limitations.", "req-1"),
                response("Supported with limitations.", "req-2"),
                response("Supported with limitations.", "req-3"),
            ]
        )
        result = self.adapter(transport).run(
            "trace-001",
            "Assess this claim.",
            metadata={"source": "unit-test"},
        )

        receipt = result["receipt"]
        self.assertEqual("CONSENSUS", receipt["verdict"])
        self.assertEqual(3, receipt["successful_replicas"])
        self.assertEqual(1.0, receipt["agreement_score"])
        self.assertTrue(receipt["receipt_hash"].startswith("sha256:"))
        serialized_receipt = json.dumps(receipt)
        self.assertNotIn("primary-secret", serialized_receipt)
        self.assertNotIn("Assess this claim.", serialized_receipt)
        self.assertEqual(3, len(result["outputs"]))
        self.assertEqual(
            "https://broker.example/v1/chat/completions",
            transport.calls[0]["url"],
        )

    def test_primary_error_uses_explicit_fallback(self) -> None:
        transport = ScriptedTransport(
            [
                RuntimeError("primary timeout"),
                response("fallback answer", "fallback-1"),
            ]
        )
        result = self.adapter(transport, fallback=True).run(
            "trace-fallback",
            "Assess.",
            replicas=1,
        )

        execution = result["receipt"]["executions"][0]
        self.assertEqual("fallback", execution["provider"])
        self.assertTrue(execution["fallback_used"])
        self.assertEqual("primary timeout", execution["primary_error"])
        self.assertEqual("CONSENSUS", result["receipt"]["verdict"])
        self.assertEqual(2, len(transport.calls))
        self.assertNotEqual(
            transport.calls[0]["headers"]["Authorization"],
            transport.calls[1]["headers"]["Authorization"],
        )

    def test_partial_failure_is_degraded(self) -> None:
        transport = ScriptedTransport(
            [
                response("same answer", "req-1"),
                RuntimeError("timeout"),
                response("same answer", "req-3"),
            ]
        )
        result = self.adapter(transport).run("trace-degraded", "Assess.")
        self.assertEqual("DEGRADED", result["receipt"]["verdict"])
        self.assertEqual(2, result["receipt"]["successful_replicas"])
        self.assertEqual("ERROR", result["receipt"]["executions"][1]["status"])

    def test_divergent_outputs_are_detected(self) -> None:
        transport = ScriptedTransport(
            [
                response("Alpha result.", "req-1"),
                response("Completely unrelated beta conclusion.", "req-2"),
                response("Third conflicting gamma answer.", "req-3"),
            ]
        )
        result = self.adapter(transport).run("trace-divergent", "Assess.")
        self.assertEqual("DIVERGENT", result["receipt"]["verdict"])
        self.assertLess(result["receipt"]["agreement_score"], 0.85)

    def test_external_plain_http_is_rejected(self) -> None:
        config = MODULE.GonkaConfig(
            primary=MODULE.ProviderConfig(
                name="gonka",
                base_url="http://broker.example",
                api_key="secret",
                model="model",
            )
        )
        with self.assertRaisesRegex(ValueError, "must use HTTPS"):
            MODULE.GonkaComputeWitnessAdapter(config, transport=ScriptedTransport([]))

    def test_local_http_is_allowed_for_mock_broker(self) -> None:
        config = MODULE.GonkaConfig(
            primary=MODULE.ProviderConfig(
                name="gonka",
                base_url="http://127.0.0.1:8080/v1",
                api_key="secret",
                model="model",
            ),
            replicas=1,
        )
        adapter = MODULE.GonkaComputeWitnessAdapter(
            config,
            transport=ScriptedTransport([response("ok", "local-1")]),
        )
        result = adapter.run("local", "test")
        self.assertEqual("CONSENSUS", result["receipt"]["verdict"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
