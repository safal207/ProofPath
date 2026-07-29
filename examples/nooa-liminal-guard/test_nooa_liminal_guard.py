#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from nooa_liminal_guard import (
    ActionProposal,
    Policy,
    ProofPathNOOAGuard,
    proposal_from_nooa_span,
    verify_bundle,
)


HERE = Path(__file__).resolve().parent


class GuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.guard = ProofPathNOOAGuard(Policy.load(HERE / "policy.json"), root / "state", root / "bundles")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def safe(self, nonce: str = "nonce-1") -> ActionProposal:
        return ActionProposal(
            trace_id="trace-1",
            span_id=f"span-{nonce}",
            parent_span_id="root-span",
            agent="TestAgent",
            method="read_public",
            intent_id="intent-1",
            parent_cause="task-1",
            action="read",
            scope="fs.read",
            target="README.md",
            nonce=nonce,
        )

    def test_exported_span_adapter_preserves_parent(self) -> None:
        proposal = proposal_from_nooa_span(
            {
                "trace_id": "trace-a",
                "id": "span-a",
                "parent_id": "span-root",
                "name": "send_report",
                "attributes": {"scope": "network.send", "destination": "api.example.test"},
            },
            defaults={"intent_id": "intent-a", "parent_cause": "task-a", "target": "/report"},
        )
        self.assertEqual(proposal.parent_span_id, "span-root")
        self.assertEqual(proposal.scope, "network.send")
        self.assertEqual(proposal.destination, "api.example.test")

    def test_safe_action_executes_and_bundle_verifies(self) -> None:
        calls: list[str] = []
        result = self.guard.execute(self.safe(), lambda: calls.append("executed") or {"ok": True})
        self.assertEqual(result.decision.decision, "ACCEPT")
        self.assertEqual(calls, ["executed"])
        self.assertTrue(verify_bundle(result.evidence_dir)["valid"])

    def test_irreversible_action_without_approval_is_held(self) -> None:
        proposal = ActionProposal(
            trace_id="trace-delete",
            span_id="span-delete",
            parent_span_id="root",
            agent="TestAgent",
            method="delete_data",
            intent_id="intent-delete",
            parent_cause="task-delete",
            action="delete",
            scope="system.delete",
            target="dataset",
            reversibility="irreversible",
            nonce="nonce-delete",
        )
        calls: list[str] = []
        result = self.guard.execute(proposal, lambda: calls.append("bad"))
        self.assertEqual(result.decision.decision, "HOLD")
        self.assertFalse(result.observation.side_effect_executed)
        self.assertEqual(calls, [])

    def test_secret_egress_is_blocked_with_cml_finding(self) -> None:
        proposal = ActionProposal(
            trace_id="trace-secret",
            span_id="span-secret",
            parent_span_id="secret-read",
            agent="TestAgent",
            method="upload",
            intent_id="intent-local",
            parent_cause="task-local",
            action="network_send",
            scope="network.send",
            target="/upload",
            contains_secret=True,
            destination="untrusted.example",
            nonce="nonce-secret",
        )
        result = self.guard.execute(proposal, lambda: {"sent": True})
        self.assertEqual(result.decision.decision, "BLOCK")
        self.assertIn(
            "CML-AUDIT-R3-SECRET_NET_MISSING_CHAIN",
            [item["code"] for item in result.decision.cml_findings],
        )
        self.assertFalse(result.observation.side_effect_executed)

    def test_nonce_replay_is_blocked(self) -> None:
        proposal = self.safe("nonce-replay")
        first = self.guard.execute(proposal, lambda: {"ok": 1})
        second = self.guard.execute(proposal, lambda: {"ok": 2})
        self.assertEqual(first.decision.decision, "ACCEPT")
        self.assertEqual(second.decision.decision, "BLOCK")
        self.assertIn("INTENT_REPLAYED", second.decision.reason_codes)
        self.assertFalse(second.observation.side_effect_executed)
        self.assertNotEqual(first.evidence_dir, second.evidence_dir)
        self.assertTrue(first.evidence_dir.exists())
        self.assertTrue(second.evidence_dir.exists())

    def test_cml_export_is_loadable_shape(self) -> None:
        result = self.guard.execute(self.safe("nonce-cml"), lambda: {"ok": True})
        rows = [
            json.loads(line)
            for line in (result.evidence_dir / "cml-trace.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertIsInstance(row["timestamp"], int)
            self.assertIn("pid", row["actor"])
            self.assertIn("uid", row["actor"])
            for key in ("id", "action", "object", "permitted_by", "parent_cause"):
                self.assertIn(key, row)

    def test_missing_nonce_is_blocked(self) -> None:
        proposal = ActionProposal(
            trace_id="trace-no-nonce",
            span_id="span-no-nonce",
            parent_span_id="root",
            agent="TestAgent",
            method="read_public",
            intent_id="intent-no-nonce",
            parent_cause="task-no-nonce",
            action="read",
            scope="fs.read",
            target="README.md",
        )
        result = self.guard.execute(proposal, lambda: {"bad": True})
        self.assertEqual(result.decision.decision, "BLOCK")
        self.assertIn("MISSING_NONCE", result.decision.reason_codes)
        self.assertFalse(result.observation.side_effect_executed)

    def test_real_alias_beats_primary_default(self) -> None:
        proposal = proposal_from_nooa_span(
            {"id": "span-alias", "resource": "/actual", "name": "read"},
            defaults={
                "target": "/default",
                "intent_id": "intent-alias",
                "parent_cause": "task-alias",
                "scope": "fs.read",
                "nonce": "nonce-alias",
            },
        )
        self.assertEqual(proposal.target, "/actual")

    def test_network_scope_triggers_secret_egress_check(self) -> None:
        proposal = ActionProposal(
            trace_id="trace-scope-egress",
            span_id="span-scope-egress",
            parent_span_id="secret-read",
            agent="TestAgent",
            method="send_report",
            intent_id="intent-scope-egress",
            parent_cause="task-scope-egress",
            action="send_report",
            scope="network.send",
            target="/upload",
            contains_secret=True,
            destination="untrusted.example",
            approval_ref="human_approval:ticket-99",
            nonce="nonce-scope-egress",
        )
        result = self.guard.execute(proposal, lambda: {"bad": True})
        self.assertEqual(result.decision.decision, "BLOCK")
        self.assertIn("SECRET_EGRESS_DENIED", result.decision.reason_codes)
        self.assertFalse(result.observation.side_effect_executed)

    def test_span_id_cannot_escape_evidence_root(self) -> None:
        proposal = ActionProposal(
            trace_id="trace-path",
            span_id="../../outside",
            parent_span_id="root",
            agent="TestAgent",
            method="read_public",
            intent_id="intent-path",
            parent_cause="task-path",
            action="read",
            scope="fs.read",
            target="README.md",
            nonce="nonce-path",
        )
        result = self.guard.execute(proposal, lambda: {"ok": True})
        root = self.guard.evidence_root.resolve()
        self.assertTrue(result.evidence_dir.resolve().is_relative_to(root))
        self.assertNotIn("..", result.evidence_dir.name)

    def test_bundle_tamper_is_detected(self) -> None:
        result = self.guard.execute(self.safe("nonce-tamper"), lambda: {"ok": True})
        action = result.evidence_dir / "evidence" / "action.json"
        value = json.loads(action.read_text(encoding="utf-8"))
        value["target"] = "changed"
        action.write_text(json.dumps(value), encoding="utf-8")
        verification = verify_bundle(result.evidence_dir)
        self.assertFalse(verification["valid"])
        self.assertTrue(any(item.startswith("digest:evidence/action.json") for item in verification["errors"]))


if __name__ == "__main__":
    unittest.main()
