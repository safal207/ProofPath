from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "control-cloud" / "ingestion" / "ingest.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "proofpath-control-cloud-ingestion.yml").read_text(encoding="utf-8")
README = (ROOT / "control-cloud" / "ingestion" / "README.md").read_text(encoding="utf-8")
REGISTRY = json.loads((ROOT / "examples" / "control-cloud" / "ingestion" / "tenant-registry.json").read_text())
REQUEST_SCHEMA = json.loads((ROOT / "schemas" / "proofpath-control-cloud-ingest-request-v0.1.schema.json").read_text())
RECEIPT_SCHEMA = json.loads((ROOT / "schemas" / "proofpath-control-cloud-ingest-receipt-v0.1.schema.json").read_text())
REGISTRY_SCHEMA = json.loads((ROOT / "schemas" / "proofpath-control-cloud-tenant-registry-v0.1.schema.json").read_text())


class ControlCloudIngestionSecurityTests(unittest.TestCase):
    def test_hmac_uses_constant_time_comparison(self):
        self.assertIn("hmac.compare_digest", SOURCE)
        self.assertIn("hmac.new", SOURCE)
        self.assertIn("sha256=", SOURCE)

    def test_secret_material_is_loaded_only_from_environment_reference(self):
        self.assertIn('os.environ.get(key["secret_env"])', SOURCE)
        self.assertNotIn('"secret":', json.dumps(REGISTRY))
        key = REGISTRY["tenants"]["acme-demo"]["keys"]["demo-key-1"]
        self.assertEqual(key["secret_env"], "PROOFPATH_INGEST_DEMO_SECRET")

    def test_request_binds_exact_body_digest_timestamp_nonce_and_idempotency(self):
        for token in (
            "X-ProofPath-Timestamp",
            "X-ProofPath-Nonce",
            "X-ProofPath-Idempotency-Key",
            "X-ProofPath-Content-SHA256",
            "X-ProofPath-Signature",
        ):
            self.assertIn(token, SOURCE)
        self.assertIn("raw_sha256(body)", SOURCE)
        self.assertIn("AUTH_TIMESTAMP_OUT_OF_WINDOW", SOURCE)

    def test_event_store_uses_lock_append_no_follow_and_fsync(self):
        self.assertIn("fcntl.flock", SOURCE)
        self.assertIn("os.O_APPEND", SOURCE)
        self.assertIn("O_NOFOLLOW", SOURCE)
        self.assertIn("STORE_SYMLINK_REJECTED", SOURCE)
        self.assertIn("os.fsync", SOURCE)
        self.assertIn("verify_event_chain", SOURCE)

    def test_paths_are_tenant_scoped_and_confined(self):
        self.assertIn("confined_tenant_directory", SOURCE)
        self.assertIn("relative_to(root)", SOURCE)
        self.assertIn("TENANT_REPOSITORY_SCOPE_VIOLATION", SOURCE)

    def test_service_has_body_limit_and_safe_local_default(self):
        self.assertIn("MAX_BODY_BYTES = 1_048_576", SOURCE)
        self.assertIn('serve.add_argument("--host", default="127.0.0.1")', SOURCE)
        self.assertIn("Content-Length", SOURCE)
        self.assertIn("BODY_TOO_LARGE", SOURCE)

    def test_service_does_not_execute_payments_deployments_or_commands(self):
        forbidden = (
            "subprocess.", "os.system(", "shell=True", "eval(", "exec(",
            "stripe", "paypal", "web3", "boto3", "kubectl ", "terraform apply",
        )
        lowered = SOURCE.lower()
        for token in forbidden:
            self.assertNotIn(token.lower(), lowered)
        self.assertIn('"payments_executed": False', SOURCE)
        self.assertIn('"deployment_performed": False', SOURCE)
        self.assertIn('"authority_granted": False', SOURCE)

    def test_api_does_not_claim_sigstore_verification(self):
        self.assertIn('"provenance_cryptographically_verified_by_api": False', SOURCE)
        self.assertIn("does not independently verify Sigstore attestations", SOURCE)
        self.assertIn("EXTERNAL_RESULT_BOUND", SOURCE)

    def test_schemas_are_strict_and_preserve_boundaries(self):
        for schema in (REQUEST_SCHEMA, RECEIPT_SCHEMA, REGISTRY_SCHEMA):
            self.assertFalse(schema["additionalProperties"])
        self.assertEqual(RECEIPT_SCHEMA["properties"]["financial_status"]["const"], "RECORDED_NOT_PAYABLE")
        self.assertFalse(RECEIPT_SCHEMA["properties"]["payments_executed"]["const"])
        self.assertFalse(RECEIPT_SCHEMA["properties"]["authority_granted"]["const"])

    def test_workflow_has_only_read_and_attestation_permissions(self):
        permissions = re.search(r"permissions:\n(?P<body>(?:  .+\n)+)", WORKFLOW)
        self.assertIsNotNone(permissions)
        body = permissions.group("body")
        self.assertIn("contents: read", body)
        self.assertIn("id-token: write", body)
        self.assertIn("attestations: write", body)
        for permission in ("actions: write", "contents: write", "pull-requests: write", "deployments: write"):
            self.assertNotIn(permission, body)

    def test_workflow_runs_ingest_idempotent_retry_export_and_snapshot(self):
        for phrase in (
            "Sign exact request bytes",
            "Ingest authenticated Assured Action",
            "Verify idempotent retry",
            "Export tenant dataset",
            "Build Control Cloud snapshot from ingested event",
        ):
            self.assertIn(phrase, WORKFLOW)

    def test_workflow_does_not_upload_auth_headers_or_secret(self):
        upload_block = WORKFLOW.split("Upload ingestion evidence", 1)[1]
        self.assertNotIn("headers.json", upload_block)
        self.assertNotIn("PROOFPATH_INGEST_DEMO_SECRET", upload_block)
        self.assertIn("receipt.json", upload_block)
        self.assertIn("events.jsonl", upload_block)

    def test_workflow_attests_receipt_and_event_store(self):
        self.assertIn("Attest exact ingestion receipt", WORKFLOW)
        self.assertIn("Attest exact tenant event store", WORKFLOW)
        self.assertIn("actions/attest-build-provenance@v2", WORKFLOW)

    def test_documentation_states_operational_and_financial_limits(self):
        normalized = " ".join(README.split())
        for phrase in (
            "reference service, not a hosted production SaaS",
            "RECORDED_NOT_PAYABLE",
            "does not independently verify Sigstore",
            "does not execute a deployment",
            "does not grant authority",
            "TLS termination",
            "secret manager",
        ):
            self.assertIn(phrase, normalized)


if __name__ == "__main__":
    unittest.main()
