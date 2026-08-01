from __future__ import annotations

import copy
import datetime as dt
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "control-cloud" / "ingestion" / "ingest.py"
SPEC = importlib.util.spec_from_file_location("proofpath_ingest", MODULE_PATH)
assert SPEC and SPEC.loader
INGEST = importlib.util.module_from_spec(SPEC)
sys.modules["proofpath_ingest"] = INGEST
SPEC.loader.exec_module(INGEST)

FIXTURES = ROOT / "examples" / "control-cloud" / "ingestion"
SECRET = "demo-secret-material-0123456789-abcdefghijklmnopqrstuvwxyz"
NOW = dt.datetime(2026, 8, 2, 0, 0, 0, tzinfo=dt.timezone.utc)


class ControlCloudIngestionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = Path(self.temp.name)
        self.body = (FIXTURES / "request.accept.json").read_bytes()
        self.request = json.loads(self.body)
        self.registry = json.loads((FIXTURES / "tenant-registry.json").read_text())
        os.environ["PROOFPATH_INGEST_DEMO_SECRET"] = SECRET
        self.headers = INGEST.sign_headers(
            body=self.body,
            tenant_id="acme-demo",
            key_id="demo-key-1",
            secret=SECRET,
            timestamp="2026-08-02T00:00:00Z",
            nonce="nonce-demo-00000001",
            idempotency_key="idem-demo-00000001",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()
        os.environ.pop("PROOFPATH_INGEST_DEMO_SECRET", None)

    def ingest(self, *, body=None, headers=None, tenant="acme-demo", registry=None, now=NOW):
        return INGEST.ingest_request(
            body=self.body if body is None else body,
            headers=self.headers if headers is None else headers,
            tenant_from_path=tenant,
            registry=self.registry if registry is None else registry,
            store_root=self.store,
            now=now,
        )

    def mutated_body(self, mutator) -> bytes:
        value = copy.deepcopy(self.request)
        mutator(value)
        return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()

    def signed(self, body: bytes, *, nonce="nonce-demo-00000002", idem="idem-demo-00000002", timestamp="2026-08-02T00:00:00Z"):
        return INGEST.sign_headers(
            body=body,
            tenant_id="acme-demo",
            key_id="demo-key-1",
            secret=SECRET,
            timestamp=timestamp,
            nonce=nonce,
            idempotency_key=idem,
        )

    def assert_error(self, code: str, fn) -> None:
        with self.assertRaises(INGEST.IngestError) as captured:
            fn()
        self.assertEqual(captured.exception.code, code)

    def test_valid_request_creates_receipt_and_event(self):
        receipt, replay = self.ingest()
        self.assertFalse(replay)
        self.assertEqual(receipt["status"], "ACCEPTED")
        self.assertEqual(receipt["decision"], "ACCEPT")
        self.assertFalse(receipt["payments_executed"])
        self.assertFalse(receipt["authority_granted"])
        events = (self.store / "tenants" / "acme-demo" / "events.jsonl").read_text().splitlines()
        self.assertEqual(len(events), 1)
        self.assertEqual(json.loads(events[0])["event_root"], receipt["event_root"])

    def test_identical_idempotent_retry_returns_exact_receipt(self):
        first, first_replay = self.ingest()
        second, second_replay = self.ingest()
        self.assertFalse(first_replay)
        self.assertTrue(second_replay)
        self.assertEqual(first, second)
        events = (self.store / "tenants" / "acme-demo" / "events.jsonl").read_text().splitlines()
        self.assertEqual(len(events), 1)

    def test_idempotency_conflict_fails(self):
        self.ingest()
        body = self.mutated_body(lambda value: value["assured_action"].update({"base_price_minor": 1001}))
        headers = self.signed(body, nonce="nonce-demo-00000003", idem="idem-demo-00000001")
        self.assert_error("IDEMPOTENCY_CONFLICT", lambda: self.ingest(body=body, headers=headers))

    def test_nonce_replay_with_new_idempotency_key_fails(self):
        self.ingest()
        headers = self.signed(self.body, nonce="nonce-demo-00000001", idem="idem-demo-00000003")
        self.assert_error("NONCE_REPLAY", lambda: self.ingest(headers=headers))

    def test_bad_signature_fails(self):
        headers = dict(self.headers)
        headers["X-ProofPath-Signature"] = "sha256:" + "0" * 64
        self.assert_error("INVALID_SIGNATURE", lambda: self.ingest(headers=headers))

    def test_content_digest_mismatch_fails(self):
        headers = dict(self.headers)
        headers["X-ProofPath-Content-SHA256"] = "sha256:" + "0" * 64
        self.assert_error("CONTENT_DIGEST_MISMATCH", lambda: self.ingest(headers=headers))

    def test_stale_timestamp_fails(self):
        headers = self.signed(self.body, timestamp="2026-08-01T23:00:00Z")
        self.assert_error("AUTH_TIMESTAMP_OUT_OF_WINDOW", lambda: self.ingest(headers=headers))

    def test_future_timestamp_fails(self):
        headers = self.signed(self.body, timestamp="2026-08-02T01:00:00Z")
        self.assert_error("AUTH_TIMESTAMP_OUT_OF_WINDOW", lambda: self.ingest(headers=headers))

    def test_path_tenant_must_match_body_tenant(self):
        self.assert_error("TENANT_BINDING_CONFLICT", lambda: self.ingest(tenant="other-demo"))

    def test_disabled_tenant_fails(self):
        registry = copy.deepcopy(self.registry)
        registry["tenants"]["acme-demo"]["active"] = False
        self.assert_error("TENANT_DISABLED", lambda: self.ingest(registry=registry))

    def test_disabled_key_fails(self):
        registry = copy.deepcopy(self.registry)
        registry["tenants"]["acme-demo"]["keys"]["demo-key-1"]["active"] = False
        self.assert_error("KEY_DISABLED", lambda: self.ingest(registry=registry))

    def test_repository_scope_is_tenant_bound(self):
        body = self.mutated_body(
            lambda value: value["assured_action"]["certificate"]["action"].update({"repository": "other/payments"})
        )
        headers = self.signed(body)
        self.assert_error("TENANT_REPOSITORY_SCOPE_VIOLATION", lambda: self.ingest(body=body, headers=headers))

    def test_certificate_cannot_grant_authority(self):
        body = self.mutated_body(
            lambda value: value["assured_action"]["certificate"].update({"authority_granted": True})
        )
        headers = self.signed(body)
        self.assert_error("AUTHORITY_BOUNDARY_VIOLATION", lambda: self.ingest(body=body, headers=headers))

    def test_accept_decision_must_allow_execution(self):
        body = self.mutated_body(
            lambda value: value["assured_action"]["certificate"].update({"execution_allowed": False})
        )
        headers = self.signed(body)
        self.assert_error("DECISION_CONFLICT", lambda: self.ingest(body=body, headers=headers))

    def test_duplicate_operator_assignment_fails(self):
        def mutate(value):
            value["assured_action"]["operator_assignments"].append(
                copy.deepcopy(value["assured_action"]["operator_assignments"][0])
            )
        body = self.mutated_body(mutate)
        headers = self.signed(body)
        self.assert_error("DUPLICATE_OPERATOR", lambda: self.ingest(body=body, headers=headers))

    def test_provenance_not_provided_cannot_claim_details(self):
        body = self.mutated_body(
            lambda value: value["provenance_binding"].update({"verifier_identity": "fake-verifier"})
        )
        headers = self.signed(body)
        self.assert_error("PROVENANCE_CONFLICT", lambda: self.ingest(body=body, headers=headers))

    def test_symlinked_event_store_is_rejected(self):
        tenant_dir = self.store / "tenants" / "acme-demo"
        tenant_dir.mkdir(parents=True)
        target = self.store / "outside-events.jsonl"
        target.write_text("")
        (tenant_dir / "events.jsonl").symlink_to(target)
        self.assert_error("STORE_SYMLINK_REJECTED", lambda: self.ingest())

    def test_event_chain_tamper_fails_closed(self):
        self.ingest()
        path = self.store / "tenants" / "acme-demo" / "events.jsonl"
        event = json.loads(path.read_text())
        event["request"]["assured_action"]["base_price_minor"] = 9999
        path.write_text(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
        self.assert_error(
            "CORRUPT_EVENT_STORE",
            lambda: INGEST.export_dataset(
                store_root=self.store,
                tenant_id="acme-demo",
                generated_at="2026-08-02T00:05:00Z",
            ),
        )

    def test_export_builds_control_cloud_dataset(self):
        self.ingest()
        dataset = INGEST.export_dataset(
            store_root=self.store,
            tenant_id="acme-demo",
            generated_at="2026-08-02T00:05:00Z",
        )
        self.assertEqual(dataset["profile_id"], "proofpath.control-cloud.dataset.v0.1")
        self.assertEqual(dataset["tenant_id"], "acme-demo")
        self.assertEqual(dataset["financial_mode"], "SIMULATION_ONLY")
        self.assertEqual(len(dataset["actions"]), 1)
        self.assertEqual(dataset["actions"][0]["certificate"]["action"]["action_id"], "act-ingest-001")

    def test_receipt_is_byte_deterministic_for_same_clean_store(self):
        first, _ = self.ingest()
        with tempfile.TemporaryDirectory() as second_store:
            second, _ = INGEST.ingest_request(
                body=self.body,
                headers=self.headers,
                tenant_from_path="acme-demo",
                registry=self.registry,
                store_root=Path(second_store),
                now=NOW,
            )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
