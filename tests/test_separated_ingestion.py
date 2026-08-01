import datetime as dt
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


separated = load(
    "test_separated_ingestion_runtime",
    ROOT / "control-cloud/ingestion/separated_ingest.py",
)
reviewers = separated.reviewers

NOW = dt.datetime(2026, 8, 2, 0, 0, 0, tzinfo=dt.timezone.utc)


def governance_decision():
    return {
        "decision": "ACCEPT",
        "governance_trust_verified": True,
        "decision_root": "sha256:" + "1" * 64,
        "admission_result_root": "sha256:" + "2" * 64,
        "signer_workflow": "safal207/ProofPath/.github/workflows/proofpath-sigstore-admission.yml",
        "signer_sha": "a" * 40,
        "trust_record_root": "sha256:" + "3" * 64,
    }


def reviewer_decision():
    checks = {
        "identity_status_verified": True,
        "identity_evidence_verified": True,
        "reviewer_role_verified": True,
        "author_separation_verified": True,
        "organization_separation_verified": True,
        "control_cluster_separation_verified": True,
        "payment_cluster_separation_verified": True,
        "approval_freshness_verified": True,
        "suspension_checked": True,
    }
    value = {
        "profile_id": reviewers.DECISION_PROFILE,
        "decision": "ACCEPT",
        "reason_code": "reviewer_separation_verified",
        "separation_of_duties_verified": True,
        "governance_decision_root": "sha256:" + "1" * 64,
        "admission_result_root": "sha256:" + "2" * 64,
        "workflow": "safal207/ProofPath/.github/workflows/proofpath-sigstore-admission.yml",
        "signer_sha": "a" * 40,
        "identity_registry_digest": "sha256:" + "4" * 64,
        "approval_bundle_digest": "sha256:" + "5" * 64,
        "verified_reviewer_ids": ["reviewer-a", "reviewer-b"],
        "verified_organization_ids": ["org-a", "org-b"],
        "verified_reviewer_count": 2,
        "verified_organization_count": 2,
        **checks,
        "observed_at": "2026-08-02T00:00:00Z",
        "identity_verifier_identity": "proofpath-reviewer-identity-separation-v0.1",
        "authority_granted": False,
        "repository_write_performed": False,
        "payments_executed": False,
        "decision_root": None,
    }
    value["decision_root"] = reviewers.domain_hash(
        reviewers.DECISION_DOMAIN,
        reviewers._decision_without_root(value),
    )
    return reviewers.validate_decision(value)


class FakeAuthHeaders:
    @classmethod
    def from_mapping(cls, headers):
        return object()


class SeparatedIngestionTests(unittest.TestCase):
    def test_server_derived_decision_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            decision = reviewer_decision()
            path = root / (decision["governance_decision_root"].split(":", 1)[1] + ".json")
            path.write_bytes(reviewers.canonical_bytes(decision) + b"\n")
            resolved = separated.reviewer_decision_file(root, decision["governance_decision_root"])
            self.assertEqual(resolved, path.resolve())

    def test_missing_decision_fails_before_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(separated.SeparatedIngestError) as context:
                separated.load_bound_reviewer_decision(
                    governance_decision=governance_decision(),
                    separation_dir=Path(tmp),
                    now=NOW,
                )
            self.assertEqual(context.exception.code, "REVIEWER_DECISION_NOT_FOUND")

    def test_stale_decision_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            decision = reviewer_decision()
            decision["observed_at"] = "2026-08-01T00:00:00Z"
            decision["decision_root"] = reviewers.domain_hash(
                reviewers.DECISION_DOMAIN,
                reviewers._decision_without_root(decision),
            )
            path = root / (decision["governance_decision_root"].split(":", 1)[1] + ".json")
            path.write_bytes(reviewers.canonical_bytes(decision) + b"\n")
            with self.assertRaises(separated.SeparatedIngestError) as context:
                separated.load_bound_reviewer_decision(
                    governance_decision=governance_decision(),
                    separation_dir=root,
                    now=NOW,
                )
            self.assertEqual(context.exception.code, "REVIEWER_DECISION_STALE")

    def test_symlink_decision_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.json"
            target.write_text("{}")
            digest_name = governance_decision()["decision_root"].split(":", 1)[1] + ".json"
            (root / digest_name).symlink_to(target)
            with self.assertRaises(separated.SeparatedIngestError) as context:
                separated.reviewer_decision_file(root, governance_decision()["decision_root"])
            self.assertEqual(context.exception.code, "REVIEWER_DECISION_SYMLINK_REJECTED")

    def test_reviewer_gate_precedes_append(self):
        order = []
        request = {
            "assured_action": {"certificate": {"action": {"action_id": "act-1"}}},
        }
        admitted_result = {"result_root": "sha256:" + "2" * 64}
        gov = governance_decision()
        review = reviewer_decision()
        governed_receipt = {
            "tenant_id": "tenant-a",
            "request_id": "request-a",
            "action_id": "act-1",
            "decision": "ACCEPT",
            "content_digest": "sha256:" + "6" * 64,
            "admitted_event_root": "sha256:" + "7" * 64,
            "admission_result_root": "sha256:" + "2" * 64,
            "governance_decision_root": "sha256:" + "1" * 64,
            "trust_record_root": "sha256:" + "3" * 64,
            "subject_digest": "sha256:" + "8" * 64,
            "stored_at": "2026-08-02T00:00:00Z",
            "receipt_root": "sha256:" + "9" * 64,
        }

        def verify_authentication(**kwargs):
            order.append("auth")

        def load_admission(*args, **kwargs):
            order.append("admission")
            return admitted_result

        def load_governance(*args, **kwargs):
            order.append("governance")
            return gov

        def load_review(*args, **kwargs):
            order.append("reviewers")
            return review

        def append(*args, **kwargs):
            order.append("append")
            return governed_receipt, False

        with mock.patch.object(separated.base, "validate_request", return_value=request), \
             mock.patch.object(separated.base, "strict_loads", return_value=request), \
             mock.patch.object(separated.base, "AuthHeaders", FakeAuthHeaders), \
             mock.patch.object(separated.base, "verify_authentication", side_effect=verify_authentication), \
             mock.patch.object(separated.admitted, "load_bound_admission_result", side_effect=load_admission), \
             mock.patch.object(separated.governed, "load_bound_governance_decision", side_effect=load_governance), \
             mock.patch.object(separated, "load_bound_reviewer_decision", side_effect=load_review), \
             mock.patch.object(separated.governed, "ingest_governed_request", side_effect=append):
            receipt, replay = separated.ingest_separated_request(
                body=b"{}",
                headers={},
                tenant_from_path="tenant-a",
                registry={},
                store_root=Path("."),
                admissions_dir=Path("."),
                governance_dir=Path("."),
                separation_dir=Path("."),
                now=NOW,
            )
        self.assertEqual(order, ["auth", "admission", "governance", "reviewers", "append"])
        self.assertFalse(replay)
        self.assertTrue(receipt["reviewer_identity_verified_by_api"])
        self.assertTrue(receipt["separation_of_duties_verified_by_api"])
        self.assertEqual(receipt["verified_reviewer_count"], 2)
        separated.validate_receipt(receipt)

    def test_receipt_root_detects_tamper(self):
        receipt = {
            "profile_id": separated.RECEIPT_PROFILE,
            "status": "ACCEPTED_WITH_PROVENANCE_GOVERNANCE_AND_REVIEWER_SEPARATION",
            "tenant_id": "tenant-a",
            "request_id": "request-a",
            "action_id": "act-1",
            "decision": "ACCEPT",
            "content_digest": "sha256:" + "1" * 64,
            "admitted_event_root": "sha256:" + "2" * 64,
            "admission_result_root": "sha256:" + "3" * 64,
            "governance_decision_root": "sha256:" + "4" * 64,
            "reviewer_separation_decision_root": "sha256:" + "5" * 64,
            "trust_record_root": "sha256:" + "6" * 64,
            "identity_registry_digest": "sha256:" + "7" * 64,
            "approval_bundle_digest": "sha256:" + "8" * 64,
            "verified_reviewer_count": 2,
            "verified_organization_count": 2,
            "subject_digest": "sha256:" + "9" * 64,
            "stored_at": "2026-08-02T00:00:00Z",
            "governed_receipt_root": "sha256:" + "a" * 64,
            "provenance_cryptographically_verified_by_api": True,
            "governance_trust_verified_by_api": True,
            "reviewer_identity_verified_by_api": True,
            "separation_of_duties_verified_by_api": True,
            "financial_status": "RECORDED_NOT_PAYABLE",
            "payments_executed": False,
            "insurance_provided": False,
            "deployment_performed": False,
            "authority_granted": False,
            "repository_write_performed": False,
            "receipt_root": None,
        }
        receipt["receipt_root"] = reviewers.domain_hash(
            separated.RECEIPT_DOMAIN,
            separated._receipt_without_root(receipt),
        )
        separated.validate_receipt(receipt)
        receipt["verified_reviewer_count"] = 3
        with self.assertRaises(separated.SeparatedIngestError):
            separated.validate_receipt(receipt)


if __name__ == "__main__":
    unittest.main()
