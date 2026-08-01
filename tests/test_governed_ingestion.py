import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "control-cloud/ingestion/governed_ingest.py"
spec = importlib.util.spec_from_file_location("governed_ingestion_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

gov = module.governance
admission = gov.admission
SHA = "1" * 40
WORKFLOW = "safal207/ProofPath/.github/workflows/proofpath-sigstore-admission.yml"


def admission_result():
    value = {
        "profile_id": admission.RESULT_PROFILE,
        "decision": "ACCEPT",
        "verified": True,
        "verification_mode": "GH_ATTESTATION_VERIFY",
        "subject_digest": "sha256:" + "2" * 64,
        "certificate_canonical_digest": "sha256:" + "3" * 64,
        "clearance_root": "sha256:" + "4" * 64,
        "repository": "safal207/ProofPath",
        "source_sha": "5" * 40,
        "artifact_digest": "sha256:" + "6" * 64,
        "signer_repository": "safal207/ProofPath",
        "signer_workflow": WORKFLOW,
        "signer_sha": SHA,
        "cert_oidc_issuer": admission.DEFAULT_ISSUER,
        "predicate_type": admission.DEFAULT_PREDICATE,
        "runner_environment": "github-hosted",
        "deny_self_hosted_runners": True,
        "github_attestation_verified": True,
        "transparency_timestamp_verified": True,
        "verified_attestation_count": 1,
        "verified_timestamp_count": 1,
        "verifier_identity": "proofpath-control-cloud-sigstore-admission-v0.1",
        "verified_at": "2026-08-02T00:00:00Z",
        "authority_granted": False,
        "deployment_performed": False,
        "payments_executed": False,
        "result_root": None,
    }
    value["result_root"] = admission.domain_hash(admission.RESULT_DOMAIN, admission._result_without_root(value))
    return value


def record():
    return {
        "record_id": "proofpath-sigstore-admission-v1",
        "status": "ACTIVE",
        "repository": "safal207/ProofPath",
        "owner_scope": "safal207",
        "workflow": WORKFLOW,
        "signer_sha": SHA,
        "workflow_file_digest": "sha256:" + "a" * 64,
        "allowed_event_types": ["pull_request"],
        "allowed_ref_prefixes": ["refs/pull/"],
        "reviewer_quorum": {"required": 2, "reviewers": ["alice", "bob"], "approvals": ["alice", "bob"]},
        "effective_at": "2026-08-01T00:00:00Z",
        "expires_at": "2026-09-01T00:00:00Z",
        "review_ticket": "SEC-214",
        "authority_granted": False,
    }


def registry():
    return {"profile_id": gov.REGISTRY_PROFILE, "generated_at": "2026-08-02T00:00:00Z", "records": [record()], "revocations": []}


def decision(result=None, observed="2026-08-02T00:01:00Z"):
    return gov.evaluate(
        admission_result=result or admission_result(),
        registry=registry(),
        observed_at=observed,
        workflow_file_digest="sha256:" + "a" * 64,
        event_type="pull_request",
        ref="refs/pull/214/merge",
    )


def admitted_receipt(result):
    value = {
        "profile_id": module.admitted.RECEIPT_PROFILE,
        "status": "ACCEPTED_WITH_CRYPTOGRAPHIC_PROVENANCE",
        "tenant_id": "proofpath-demo",
        "request_id": "req-001",
        "action_id": "act-001",
        "decision": "ACCEPT",
        "content_digest": "sha256:" + "7" * 64,
        "event_index": 1,
        "previous_event_root": module.admitted.ZERO_ROOT,
        "event_root": "sha256:" + "8" * 64,
        "admission_result_root": result["result_root"],
        "subject_digest": result["subject_digest"],
        "stored_at": "2026-08-02T00:02:00Z",
        "financial_status": "RECORDED_NOT_PAYABLE",
        "payments_executed": False,
        "insurance_provided": False,
        "deployment_performed": False,
        "authority_granted": False,
        "provenance_cryptographically_verified_by_api": True,
        "receipt_root": "sha256:" + "9" * 64,
    }
    return value


class GovernedIngestionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.admissions = self.root / "admissions"
        self.decisions = self.root / "decisions"
        self.admissions.mkdir()
        self.decisions.mkdir()
        self.result = admission_result()
        self.decision = decision(self.result)
        path = self.decisions / (self.result["result_root"].split(":", 1)[1] + ".json")
        path.write_bytes(gov.canonical_bytes(self.decision) + b"\n")

    def tearDown(self):
        self.temp.cleanup()

    def test_bound_governance_decision_loads(self):
        value = module.load_bound_governance_decision(
            admission_result=self.result,
            governance_dir=self.decisions,
            now=module.base.parse_utc("2026-08-02T00:02:00Z", "now"),
        )
        self.assertEqual(value["decision"], "ACCEPT")
        self.assertTrue(value["governance_trust_verified"])

    def test_missing_decision_fails_before_append(self):
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaises(module.GovernedIngestError) as ctx:
            module.load_bound_governance_decision(
                admission_result=self.result,
                governance_dir=empty,
                now=module.base.parse_utc("2026-08-02T00:02:00Z", "now"),
            )
        self.assertEqual(ctx.exception.code, "GOVERNANCE_DECISION_NOT_FOUND")

    def test_symlink_decision_rejected(self):
        path = self.decisions / (self.result["result_root"].split(":", 1)[1] + ".json")
        target = self.root / "target.json"
        target.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(target)
        with self.assertRaises(module.GovernedIngestError) as ctx:
            module.load_bound_governance_decision(
                admission_result=self.result,
                governance_dir=self.decisions,
                now=module.base.parse_utc("2026-08-02T00:02:00Z", "now"),
            )
        self.assertEqual(ctx.exception.code, "GOVERNANCE_DECISION_SYMLINK_REJECTED")

    def test_stale_decision_rejected(self):
        with self.assertRaises(module.GovernedIngestError) as ctx:
            module.load_bound_governance_decision(
                admission_result=self.result,
                governance_dir=self.decisions,
                now=module.base.parse_utc("2026-08-02T00:30:00Z", "now"),
            )
        self.assertEqual(ctx.exception.code, "GOVERNANCE_DECISION_STALE")

    def test_binding_conflict_rejected(self):
        altered = dict(self.result)
        altered["signer_sha"] = "f" * 40
        altered["result_root"] = admission.domain_hash(admission.RESULT_DOMAIN, admission._result_without_root(altered))
        path = self.decisions / (altered["result_root"].split(":", 1)[1] + ".json")
        path.write_bytes(gov.canonical_bytes(self.decision) + b"\n")
        with self.assertRaises(module.GovernedIngestError) as ctx:
            module.load_bound_governance_decision(
                admission_result=altered,
                governance_dir=self.decisions,
                now=module.base.parse_utc("2026-08-02T00:02:00Z", "now"),
            )
        self.assertEqual(ctx.exception.code, "GOVERNANCE_BINDING_CONFLICT")

    def test_governance_is_checked_before_append(self):
        request = {"request_id": "req-001", "assured_action": {"certificate": {}}}
        auth = SimpleNamespace()
        with patch.object(module.base, "validate_request", return_value=request), \
             patch.object(module.base, "strict_loads", return_value=request), \
             patch.object(module.base.AuthHeaders, "from_mapping", return_value=auth), \
             patch.object(module.base, "verify_authentication"), \
             patch.object(module.admitted, "load_bound_admission_result", return_value=self.result), \
             patch.object(module, "load_bound_governance_decision", side_effect=module.GovernedIngestError("WORKFLOW_GOVERNANCE_REQUIRED", "no", 422)), \
             patch.object(module.admitted, "ingest_admitted_request") as append:
            with self.assertRaises(module.GovernedIngestError):
                module.ingest_governed_request(
                    body=b"{}", headers={}, tenant_from_path="proofpath-demo", registry={},
                    store_root=self.root / "store", admissions_dir=self.admissions,
                    governance_dir=self.decisions,
                    now=module.base.parse_utc("2026-08-02T00:02:00Z", "now"),
                )
        append.assert_not_called()

    def test_success_emits_dual_verified_receipt(self):
        request = {"request_id": "req-001", "assured_action": {"certificate": {}}}
        auth = SimpleNamespace()
        admitted_value = admitted_receipt(self.result)
        with patch.object(module.base, "validate_request", return_value=request), \
             patch.object(module.base, "strict_loads", return_value=request), \
             patch.object(module.base.AuthHeaders, "from_mapping", return_value=auth), \
             patch.object(module.base, "verify_authentication"), \
             patch.object(module.admitted, "load_bound_admission_result", return_value=self.result), \
             patch.object(module.admitted, "ingest_admitted_request", return_value=(admitted_value, False)):
            receipt, replay = module.ingest_governed_request(
                body=b"{}", headers={}, tenant_from_path="proofpath-demo", registry={},
                store_root=self.root / "store", admissions_dir=self.admissions,
                governance_dir=self.decisions,
                now=module.base.parse_utc("2026-08-02T00:02:00Z", "now"),
            )
        self.assertFalse(replay)
        module.validate_receipt(receipt)
        self.assertTrue(receipt["provenance_cryptographically_verified_by_api"])
        self.assertTrue(receipt["governance_trust_verified_by_api"])
        self.assertEqual(receipt["governance_decision_root"], self.decision["decision_root"])
        self.assertFalse(receipt["repository_write_performed"])

    def test_receipt_root_detects_tamper(self):
        request = {"request_id": "req-001", "assured_action": {"certificate": {}}}
        auth = SimpleNamespace()
        with patch.object(module.base, "validate_request", return_value=request), \
             patch.object(module.base, "strict_loads", return_value=request), \
             patch.object(module.base.AuthHeaders, "from_mapping", return_value=auth), \
             patch.object(module.base, "verify_authentication"), \
             patch.object(module.admitted, "load_bound_admission_result", return_value=self.result), \
             patch.object(module.admitted, "ingest_admitted_request", return_value=(admitted_receipt(self.result), False)):
            receipt, _ = module.ingest_governed_request(
                body=b"{}", headers={}, tenant_from_path="proofpath-demo", registry={},
                store_root=self.root / "store", admissions_dir=self.admissions,
                governance_dir=self.decisions,
                now=module.base.parse_utc("2026-08-02T00:02:00Z", "now"),
            )
        receipt["tenant_id"] = "evil"
        with self.assertRaises(module.GovernedIngestError) as ctx:
            module.validate_receipt(receipt)
        self.assertEqual(ctx.exception.code, "GOVERNED_RECEIPT_ROOT_MISMATCH")


if __name__ == "__main__":
    unittest.main()
