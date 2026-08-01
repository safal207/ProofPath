import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


reviewers = load(
    "test_reviewer_separation_runtime",
    ROOT / "control-cloud/reviewers/verify_reviewer_separation.py",
)
governance = reviewers.governance

NOW = "2026-08-02T00:00:00Z"


def governance_decision():
    value = {
        "profile_id": governance.DECISION_PROFILE,
        "decision": "ACCEPT",
        "reason_code": None,
        "governance_trust_verified": True,
        "observed_at": NOW,
        "repository": "safal207/ProofPath",
        "signer_repository": "safal207/ProofPath",
        "signer_workflow": "safal207/ProofPath/.github/workflows/proofpath-sigstore-admission.yml",
        "signer_sha": "a" * 40,
        "workflow_file_digest": "sha256:" + "b" * 64,
        "event_type": "pull_request",
        "ref": "refs/pull/215/merge",
        "admission_result_root": "sha256:" + "c" * 64,
        "subject_digest": "sha256:" + "d" * 64,
        "trust_record_id": "trusted-workflow-v1",
        "trust_record_root": "sha256:" + "e" * 64,
        "reviewer_quorum_verified": True,
        "trust_window_verified": True,
        "revocation_checked": True,
        "owner_scope_verified": True,
        "authority_granted": False,
        "repository_write_performed": False,
        "deployment_performed": False,
        "payments_executed": False,
        "decision_root": None,
    }
    value["decision_root"] = governance.domain_hash(
        governance.DECISION_DOMAIN,
        governance._decision_without_root(value),
    )
    return governance.validate_decision(value)


def identity_registry():
    return {
        "profile_id": reviewers.REGISTRY_PROFILE,
        "generated_at": NOW,
        "policy": {
            "required_approvals": 2,
            "required_distinct_organizations": 2,
            "required_role": "workflow-reviewer",
            "allowed_identity_providers": ["github-oidc"],
            "forbid_author_organization": True,
            "require_distinct_control_clusters": True,
            "require_distinct_payment_clusters": True,
            "max_approval_age_seconds": 86400,
        },
        "reviewers": [
            {
                "reviewer_id": "reviewer-a",
                "status": "ACTIVE",
                "github_login": "reviewer-a",
                "identity_provider": "github-oidc",
                "identity_subject": "https://github.com/reviewer-a",
                "organization_id": "org-a",
                "control_cluster_id": "control-a",
                "payment_cluster_id": "payment-a",
                "roles": ["workflow-reviewer"],
                "effective_at": "2025-01-01T00:00:00Z",
                "expires_at": "2099-01-01T00:00:00Z",
                "identity_evidence_digest": "sha256:" + "1" * 64,
                "independence_attested": True,
                "authority_granted": False,
            },
            {
                "reviewer_id": "reviewer-b",
                "status": "ACTIVE",
                "github_login": "reviewer-b",
                "identity_provider": "github-oidc",
                "identity_subject": "https://github.com/reviewer-b",
                "organization_id": "org-b",
                "control_cluster_id": "control-b",
                "payment_cluster_id": "payment-b",
                "roles": ["workflow-reviewer"],
                "effective_at": "2025-01-01T00:00:00Z",
                "expires_at": "2099-01-01T00:00:00Z",
                "identity_evidence_digest": "sha256:" + "2" * 64,
                "independence_attested": True,
                "authority_granted": False,
            },
            {
                "reviewer_id": "reviewer-c",
                "status": "ACTIVE",
                "github_login": "reviewer-c",
                "identity_provider": "github-oidc",
                "identity_subject": "https://github.com/reviewer-c",
                "organization_id": "org-c",
                "control_cluster_id": "control-c",
                "payment_cluster_id": "payment-c",
                "roles": ["workflow-reviewer"],
                "effective_at": "2025-01-01T00:00:00Z",
                "expires_at": "2099-01-01T00:00:00Z",
                "identity_evidence_digest": "sha256:" + "3" * 64,
                "independence_attested": True,
                "authority_granted": False,
            },
        ],
        "suspensions": [],
    }


def approval_bundle(gov=None, registry=None):
    gov = gov or governance_decision()
    registry = registry or identity_registry()
    approvals = []
    for index, reviewer in enumerate(registry["reviewers"][:2], 1):
        approvals.append(
            {
                "approval_id": f"approval-{index}",
                "reviewer_id": reviewer["reviewer_id"],
                "reviewer_identity_subject": reviewer["identity_subject"],
                "decision": "APPROVE",
                "approved_at": "2026-08-01T23:30:00Z",
                "governance_decision_root": gov["decision_root"],
                "workflow": gov["signer_workflow"],
                "signer_sha": gov["signer_sha"],
                "statement_digest": "sha256:" + str(index + 3) * 64,
                "identity_evidence_digest": reviewer["identity_evidence_digest"],
                "conflict_of_interest_declared": False,
            }
        )
    return {
        "profile_id": reviewers.APPROVAL_PROFILE,
        "governance_decision_root": gov["decision_root"],
        "author_identity_subject": "https://github.com/workflow-author",
        "author_organization_id": "author-org",
        "author_control_cluster_id": "author-control",
        "author_payment_cluster_id": "author-payment",
        "workflow": gov["signer_workflow"],
        "signer_sha": gov["signer_sha"],
        "approvals": approvals,
    }


class ReviewerSeparationTests(unittest.TestCase):
    def evaluate(self, registry=None, bundle=None):
        gov = governance_decision()
        registry = registry or identity_registry()
        bundle = bundle or approval_bundle(gov, registry)
        return reviewers.evaluate(
            governance_decision=gov,
            registry=registry,
            bundle=bundle,
            observed_at=NOW,
        )

    def test_two_independent_reviewers_accept(self):
        result = self.evaluate()
        self.assertEqual(result["decision"], "ACCEPT")
        self.assertEqual(result["reason_code"], "reviewer_separation_verified")
        self.assertEqual(result["verified_reviewer_count"], 2)
        self.assertEqual(result["verified_organization_count"], 2)
        reviewers.validate_decision(result)

    def test_author_self_approval_blocks(self):
        registry = identity_registry()
        bundle = approval_bundle(governance_decision(), registry)
        bundle["author_identity_subject"] = registry["reviewers"][0]["identity_subject"]
        result = self.evaluate(registry, bundle)
        self.assertEqual((result["decision"], result["reason_code"]), ("BLOCK", "author_self_approval"))

    def test_author_organization_conflict_blocks(self):
        registry = identity_registry()
        bundle = approval_bundle(governance_decision(), registry)
        bundle["author_organization_id"] = registry["reviewers"][0]["organization_id"]
        result = self.evaluate(registry, bundle)
        self.assertEqual(result["reason_code"], "author_organization_conflict")

    def test_control_cluster_collision_blocks(self):
        registry = identity_registry()
        registry["reviewers"][1]["control_cluster_id"] = registry["reviewers"][0]["control_cluster_id"]
        result = self.evaluate(registry, approval_bundle(governance_decision(), registry))
        self.assertEqual(result["reason_code"], "reviewer_control_cluster_collision")

    def test_payment_cluster_collision_blocks(self):
        registry = identity_registry()
        registry["reviewers"][1]["payment_cluster_id"] = registry["reviewers"][0]["payment_cluster_id"]
        result = self.evaluate(registry, approval_bundle(governance_decision(), registry))
        self.assertEqual(result["reason_code"], "reviewer_payment_cluster_collision")

    def test_suspended_identity_blocks(self):
        registry = identity_registry()
        registry["suspensions"].append(
            {
                "suspension_id": "suspend-reviewer-a",
                "reviewer_id": "reviewer-a",
                "effective_at": NOW,
                "reason_code": "identity-change",
                "approved_by": ["security-admin"],
                "authority_granted": False,
            }
        )
        result = self.evaluate(registry, approval_bundle(governance_decision(), registry))
        self.assertEqual(result["reason_code"], "reviewer_identity_suspended")

    def test_missing_quorum_holds(self):
        registry = identity_registry()
        bundle = approval_bundle(governance_decision(), registry)
        bundle["approvals"] = bundle["approvals"][:1]
        result = self.evaluate(registry, bundle)
        self.assertEqual((result["decision"], result["reason_code"]), ("HOLD", "reviewer_quorum_missing"))

    def test_organization_diversity_holds(self):
        registry = identity_registry()
        registry["reviewers"][1]["organization_id"] = registry["reviewers"][0]["organization_id"]
        result = self.evaluate(registry, approval_bundle(governance_decision(), registry))
        self.assertEqual((result["decision"], result["reason_code"]), ("HOLD", "organization_diversity_missing"))

    def test_stale_approval_holds(self):
        registry = identity_registry()
        bundle = approval_bundle(governance_decision(), registry)
        bundle["approvals"][0]["approved_at"] = "2020-01-01T00:00:00Z"
        result = self.evaluate(registry, bundle)
        self.assertEqual(result["reason_code"], "approval_stale_or_future")

    def test_identity_evidence_mismatch_blocks(self):
        registry = identity_registry()
        bundle = approval_bundle(governance_decision(), registry)
        bundle["approvals"][0]["identity_evidence_digest"] = "sha256:" + "f" * 64
        result = self.evaluate(registry, bundle)
        self.assertEqual(result["reason_code"], "identity_evidence_mismatch")

    def test_reviewer_reject_blocks(self):
        registry = identity_registry()
        bundle = approval_bundle(governance_decision(), registry)
        bundle["approvals"][0]["decision"] = "REJECT"
        result = self.evaluate(registry, bundle)
        self.assertEqual(result["reason_code"], "reviewer_rejected")

    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(reviewers.ReviewerSeparationError):
            reviewers.strict_loads('{"a":1,"a":2}')

    def test_decision_root_detects_tamper(self):
        result = self.evaluate()
        result["verified_reviewer_count"] = 99
        with self.assertRaises(reviewers.ReviewerSeparationError):
            reviewers.validate_decision(result)

    def test_identity_change_proposes_suspension(self):
        registry = identity_registry()
        proposal = reviewers.check_identity_change(
            registry=registry,
            reviewer_id="reviewer-a",
            observed_identity_subject="https://github.com/reviewer-a",
            observed_organization_id="other-org",
            observed_control_cluster_id="control-a",
            observed_payment_cluster_id="payment-a",
            observed_identity_evidence_digest=registry["reviewers"][0]["identity_evidence_digest"],
            observed_at=NOW,
        )
        self.assertEqual(proposal["decision"], "PROPOSE_SUSPEND")
        self.assertIn("organization_changed", proposal["reason_codes"])
        self.assertFalse(proposal["repository_write_performed"])


if __name__ == "__main__":
    unittest.main()
