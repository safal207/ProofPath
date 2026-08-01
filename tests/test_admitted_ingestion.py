
import datetime as dt
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "control-cloud/ingestion/admitted_ingest.py"
spec = importlib.util.spec_from_file_location("admitted_ingest_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
base = module.base
admission = module.admission

SECRET = "test-only-proofpath-admission-ingestion-secret-00000001"


def certificate():
    return {
        "profile_id": "proofpath.deploy.clearance-certificate.v0.1",
        "product": "PROOFPATH_ASSURED_ACTION",
        "decision": "ACCEPT",
        "valid": True,
        "primary_reason_code": None,
        "action": {
            "action_id": "act-admitted-001",
            "action_type": "deploy",
            "agent_id": "agent-ci",
            "repository": "acme/payments",
            "branch": "main",
            "commit_sha": "1" * 40,
            "environment": "production",
            "artifact_digest": "sha256:" + "a" * 64,
        },
        "assurance": {
            "assurance_level": "POLICY_VERIFIED",
            "witness_level": "SINGLE_WORKFLOW_REFERENCE",
            "coverage": "NOT_FINANCIALLY_COVERED",
            "policy_id": "prod-deploy",
            "policy_version": "0.1.0",
        },
        "policy_root": "sha256:" + "b" * 64,
        "evidence_root": "sha256:" + "c" * 64,
        "clearance_root": "sha256:" + "d" * 64,
        "execution_allowed": True,
        "authority_granted": False,
    }


def admission_result(cert=None, subject_digest=None):
    cert = certificate() if cert is None else cert
    subject_digest = subject_digest or ("sha256:" + "e" * 64)
    value = {
        "profile_id": admission.RESULT_PROFILE,
        "decision": "ACCEPT",
        "verified": True,
        "verification_mode": "GH_ATTESTATION_VERIFY",
        "subject_digest": subject_digest,
        "certificate_canonical_digest": base.raw_sha256(base.canonical_bytes(cert)),
        "clearance_root": cert["clearance_root"],
        "repository": cert["action"]["repository"],
        "source_sha": cert["action"]["commit_sha"],
        "artifact_digest": cert["action"]["artifact_digest"],
        "signer_repository": "acme/payments",
        "signer_workflow": "acme/payments/.github/workflows/deploy.yml",
        "signer_sha": "2" * 40,
        "cert_oidc_issuer": admission.DEFAULT_ISSUER,
        "predicate_type": admission.DEFAULT_PREDICATE,
        "runner_environment": "github-hosted",
        "deny_self_hosted_runners": True,
        "github_attestation_verified": True,
        "transparency_timestamp_verified": True,
        "verified_attestation_count": 1,
        "verified_timestamp_count": 1,
        "verifier_identity": "proofpath-control-cloud-admission",
        "verified_at": "2026-08-02T00:00:00Z",
        "authority_granted": False,
        "deployment_performed": False,
        "payments_executed": False,
        "result_root": None,
    }
    value["result_root"] = admission.domain_hash(admission.RESULT_DOMAIN, admission._result_without_root(value))
    return value


def request(cert=None, result=None):
    cert = certificate() if cert is None else cert
    result = admission_result(cert) if result is None else result
    return {
        "profile_id": "proofpath.control-cloud.ingest-request.v0.1",
        "tenant_id": "acme-demo",
        "request_id": "req-admitted-001",
        "submitted_at": "2026-08-02T00:00:00Z",
        "assured_action": {
            "base_price_minor": 1000,
            "certificate": cert,
            "dispute_state": "none",
            "observed_at": "2026-08-02T00:00:00Z",
            "operator_assignments": [
                {"operator_id": "witness-eu-1", "role": "reference-witness", "weight": 1}
            ],
            "risk_tier": "low",
        },
        "provenance_binding": {
            "status": "EXTERNAL_RESULT_BOUND",
            "subject_digest": result["subject_digest"],
            "verifier_identity": result["verifier_identity"],
            "verified_at": result["verified_at"],
        },
    }


class AdmittedIngestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = self.root / "store"
        self.admissions = self.root / "admissions"
        self.admissions.mkdir()
        os.environ["PROOFPATH_TEST_ADMITTED_SECRET"] = SECRET
        self.registry = {
            "profile_id": "proofpath.control-cloud.tenant-registry.v0.1",
            "tenants": {
                "acme-demo": {
                    "active": True,
                    "repository_prefixes": ["acme/"],
                    "keys": {
                        "demo-key-1": {
                            "active": True,
                            "secret_env": "PROOFPATH_TEST_ADMITTED_SECRET",
                        }
                    },
                }
            },
        }
        self.cert = certificate()
        self.result = admission_result(self.cert)
        self.write_result(self.result)
        self.request = request(self.cert, self.result)
        self.body = base.canonical_bytes(self.request)
        self.headers = base.sign_headers(
            body=self.body,
            tenant_id="acme-demo",
            key_id="demo-key-1",
            secret=SECRET,
            timestamp="2026-08-02T00:00:00Z",
            nonce="nonce-admitted-0001",
            idempotency_key="idem-admitted-0001",
        )
        self.now = dt.datetime(2026, 8, 2, 0, 0, tzinfo=dt.timezone.utc)

    def tearDown(self):
        os.environ.pop("PROOFPATH_TEST_ADMITTED_SECRET", None)
        self.temp.cleanup()

    def write_result(self, value):
        path = self.admissions / (value["subject_digest"].split(":", 1)[1] + ".json")
        path.write_bytes(admission.canonical_bytes(value) + b"\n")
        return path

    def ingest(self, body=None, headers=None):
        return module.ingest_admitted_request(
            body=self.body if body is None else body,
            headers=self.headers if headers is None else headers,
            tenant_from_path="acme-demo",
            registry=self.registry,
            store_root=self.store,
            admissions_dir=self.admissions,
            now=self.now,
        )

    def test_valid_admission_sets_provenance_true(self):
        receipt, replay = self.ingest()
        self.assertFalse(replay)
        self.assertTrue(receipt["provenance_cryptographically_verified_by_api"])
        self.assertEqual(receipt["admission_result_root"], self.result["result_root"])
        self.assertFalse(receipt["authority_granted"])
        self.assertFalse(receipt["payments_executed"])
        module.verify_receipt(receipt)

    def test_idempotent_retry_returns_exact_receipt(self):
        first, first_replay = self.ingest()
        second, second_replay = self.ingest()
        self.assertFalse(first_replay)
        self.assertTrue(second_replay)
        self.assertEqual(first, second)
        path = self.store / "tenants/acme-demo/admitted-events.jsonl"
        self.assertEqual(len(path.read_text().splitlines()), 1)

    def test_missing_admission_result_fails(self):
        for path in self.admissions.iterdir():
            path.unlink()
        with self.assertRaises(base.IngestError) as ctx:
            self.ingest()
        self.assertEqual(ctx.exception.code, "ADMISSION_RESULT_NOT_FOUND")

    def test_not_provided_binding_fails(self):
        value = json.loads(json.dumps(self.request))
        value["provenance_binding"] = {
            "status": "NOT_PROVIDED",
            "subject_digest": None,
            "verifier_identity": None,
            "verified_at": None,
        }
        body = base.canonical_bytes(value)
        headers = base.sign_headers(
            body=body,
            tenant_id="acme-demo",
            key_id="demo-key-1",
            secret=SECRET,
            timestamp="2026-08-02T00:00:00Z",
            nonce="nonce-admitted-0002",
            idempotency_key="idem-admitted-0002",
        )
        with self.assertRaises(base.IngestError) as ctx:
            self.ingest(body, headers)
        self.assertEqual(ctx.exception.code, "CRYPTOGRAPHIC_PROVENANCE_REQUIRED")

    def test_tampered_result_root_fails(self):
        value = dict(self.result)
        value["repository"] = "evil/repo"
        self.write_result(value)
        with self.assertRaises(base.IngestError) as ctx:
            self.ingest()
        self.assertEqual(ctx.exception.code, "ADMISSION_RESULT_INVALID")

    def test_certificate_binding_conflict_fails(self):
        value = dict(self.result)
        value["certificate_canonical_digest"] = "sha256:" + "f" * 64
        value["result_root"] = admission.domain_hash(admission.RESULT_DOMAIN, admission._result_without_root(value))
        self.write_result(value)
        with self.assertRaises(base.IngestError) as ctx:
            self.ingest()
        self.assertEqual(ctx.exception.code, "ADMISSION_BINDING_CONFLICT")

    def test_source_sha_binding_conflict_fails(self):
        value = dict(self.result)
        value["source_sha"] = "9" * 40
        value["result_root"] = admission.domain_hash(admission.RESULT_DOMAIN, admission._result_without_root(value))
        self.write_result(value)
        with self.assertRaises(base.IngestError) as ctx:
            self.ingest()
        self.assertEqual(ctx.exception.code, "ADMISSION_BINDING_CONFLICT")

    def test_admission_result_symlink_rejected(self):
        path = next(self.admissions.iterdir())
        target = self.root / "outside.json"
        target.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(target)
        with self.assertRaises(base.IngestError) as ctx:
            self.ingest()
        self.assertEqual(ctx.exception.code, "ADMISSION_RESULT_SYMLINK_REJECTED")

    def test_event_chain_tamper_fails_closed(self):
        self.ingest()
        path = self.store / "tenants/acme-demo/admitted-events.jsonl"
        event = json.loads(path.read_text())
        event["admission_result_root"] = "sha256:" + "0" * 64
        path.write_bytes(base.canonical_bytes(event) + b"\n")
        with self.assertRaises(base.IngestError) as ctx:
            self.ingest()
        self.assertEqual(ctx.exception.code, "CORRUPT_ADMITTED_STORE")

    def test_export_builds_control_cloud_dataset(self):
        self.ingest()
        dataset = module.export_dataset(
            store_root=self.store,
            tenant_id="acme-demo",
            generated_at="2026-08-02T00:05:00Z",
        )
        self.assertEqual(dataset["tenant_id"], "acme-demo")
        self.assertEqual(len(dataset["actions"]), 1)
        self.assertEqual(dataset["actions"][0]["certificate"]["clearance_root"], self.cert["clearance_root"])

    def test_receipt_tamper_detected(self):
        receipt, _ = self.ingest()
        receipt["provenance_cryptographically_verified_by_api"] = False
        with self.assertRaises(base.IngestError):
            module.verify_receipt(receipt)

    def test_result_path_is_digest_derived(self):
        path = module.result_file_for_subject(self.admissions, self.result["subject_digest"])
        self.assertEqual(path.name, "e" * 64 + ".json")


if __name__ == "__main__":
    unittest.main()
