import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "control-cloud/governance/verify_workflow_governance.py"
spec = importlib.util.spec_from_file_location("workflow_governance_test", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

SHA = "1" * 40
FILE_DIGEST = "sha256:" + "a" * 64
WORKFLOW = "safal207/ProofPath/.github/workflows/proofpath-sigstore-admission.yml"


def admission_result(signer_sha=SHA, workflow=WORKFLOW):
    value = {
        "profile_id": module.admission.RESULT_PROFILE,
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
        "signer_workflow": workflow,
        "signer_sha": signer_sha,
        "cert_oidc_issuer": module.admission.DEFAULT_ISSUER,
        "predicate_type": module.admission.DEFAULT_PREDICATE,
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
    value["result_root"] = module.admission.domain_hash(
        module.admission.RESULT_DOMAIN,
        module.admission._result_without_root(value),
    )
    return value


def record(**overrides):
    value = {
        "record_id": "proofpath-sigstore-admission-v1",
        "status": "ACTIVE",
        "repository": "safal207/ProofPath",
        "owner_scope": "safal207",
        "workflow": WORKFLOW,
        "signer_sha": SHA,
        "workflow_file_digest": FILE_DIGEST,
        "allowed_event_types": ["pull_request"],
        "allowed_ref_prefixes": ["refs/pull/"],
        "reviewer_quorum": {
            "required": 2,
            "reviewers": ["alice", "bob", "carol"],
            "approvals": ["alice", "bob"],
        },
        "effective_at": "2026-08-01T00:00:00Z",
        "expires_at": "2026-09-01T00:00:00Z",
        "review_ticket": "SEC-214",
        "authority_granted": False,
    }
    value.update(overrides)
    return value


def registry(records=None, revocations=None):
    return {
        "profile_id": module.REGISTRY_PROFILE,
        "generated_at": "2026-08-02T00:00:00Z",
        "records": records if records is not None else [record()],
        "revocations": revocations if revocations is not None else [],
    }


def evaluate(reg=None, result=None, digest=FILE_DIGEST, event="pull_request", ref="refs/pull/214/merge", observed="2026-08-02T00:01:00Z"):
    return module.evaluate(
        admission_result=result or admission_result(),
        registry=reg or registry(),
        observed_at=observed,
        workflow_file_digest=digest,
        event_type=event,
        ref=ref,
    )


class WorkflowGovernanceTests(unittest.TestCase):
    def test_active_exact_record_accepts(self):
        result = evaluate()
        module.validate_decision(result)
        self.assertEqual(result["decision"], "ACCEPT")
        self.assertTrue(result["governance_trust_verified"])
        self.assertTrue(result["reviewer_quorum_verified"])
        self.assertFalse(result["authority_granted"])
        self.assertFalse(result["repository_write_performed"])

    def test_missing_record_holds(self):
        other = record(workflow="safal207/ProofPath/.github/workflows/other.yml")
        result = evaluate(reg=registry(records=[other]))
        self.assertEqual((result["decision"], result["reason_code"]), ("HOLD", "missing_trust_record"))

    def test_unpinned_signer_sha_blocks(self):
        result = evaluate(result=admission_result(signer_sha="9" * 40))
        self.assertEqual((result["decision"], result["reason_code"]), ("BLOCK", "signer_sha_not_pinned"))

    def test_mutated_workflow_digest_blocks(self):
        result = evaluate(digest="sha256:" + "f" * 64)
        self.assertEqual((result["decision"], result["reason_code"]), ("BLOCK", "workflow_digest_mutated"))

    def test_expired_record_holds(self):
        result = evaluate(observed="2026-10-01T00:00:00Z")
        self.assertEqual((result["decision"], result["reason_code"]), ("HOLD", "trust_window_inactive"))

    def test_revocation_blocks(self):
        revoked = {
            "revocation_id": "revoke-proofpath-workflow-v1",
            "record_id": "proofpath-sigstore-admission-v1",
            "effective_at": "2026-08-02T00:00:30Z",
            "reason_code": "dangerous_workflow_change",
            "approved_by": ["alice", "bob"],
            "authority_granted": False,
        }
        result = evaluate(reg=registry(revocations=[revoked]))
        self.assertEqual((result["decision"], result["reason_code"]), ("BLOCK", "trust_record_revoked"))

    def test_suspended_record_blocks(self):
        result = evaluate(reg=registry(records=[record(status="SUSPENDED")]))
        self.assertEqual((result["decision"], result["reason_code"]), ("BLOCK", "trust_record_not_active"))

    def test_reviewer_quorum_missing_holds(self):
        weak = record(reviewer_quorum={"required": 2, "reviewers": ["alice", "bob"], "approvals": ["alice"]})
        result = evaluate(reg=registry(records=[weak]))
        self.assertEqual((result["decision"], result["reason_code"]), ("HOLD", "reviewer_quorum_missing"))

    def test_event_and_ref_scope_fail_closed(self):
        event_result = evaluate(event="workflow_dispatch")
        ref_result = evaluate(ref="refs/heads/main")
        self.assertEqual(event_result["reason_code"], "event_type_not_allowed")
        self.assertEqual(ref_result["reason_code"], "ref_not_allowed")

    def test_ambiguous_exact_records_challenge(self):
        second = copy.deepcopy(record())
        second["record_id"] = "proofpath-sigstore-admission-v2"
        result = evaluate(reg=registry(records=[record(), second]))
        self.assertEqual((result["decision"], result["reason_code"]), ("CHALLENGE", "ambiguous_trust_record"))

    def test_decision_root_detects_tamper(self):
        result = evaluate()
        result["signer_sha"] = "8" * 40
        with self.assertRaises(module.GovernanceError) as ctx:
            module.validate_decision(result)
        self.assertEqual(ctx.exception.code, "DECISION_ROOT_MISMATCH")

    def test_registry_rejects_owner_scope_conflict(self):
        bad = record(owner_scope="evil")
        with self.assertRaises(module.GovernanceError) as ctx:
            module.validate_registry(registry(records=[bad]))
        self.assertEqual(ctx.exception.code, "OWNER_SCOPE_CONFLICT")

    def test_change_check_proposes_revocation_for_path_change(self):
        proposal = module.check_change(
            registry=registry(),
            workflow=WORKFLOW,
            observed_signer_sha=SHA,
            observed_file_digest=FILE_DIGEST,
            changed_paths=[".github/workflows/proofpath-sigstore-admission.yml"],
            observed_at="2026-08-02T00:02:00Z",
        )
        self.assertEqual(proposal["decision"], "PROPOSE_REVOKE")
        self.assertEqual(proposal["reason_code"], "trusted_workflow_changed")
        self.assertFalse(proposal["repository_write_performed"])

    def test_change_check_no_change(self):
        proposal = module.check_change(
            registry=registry(),
            workflow=WORKFLOW,
            observed_signer_sha=SHA,
            observed_file_digest=FILE_DIGEST,
            changed_paths=["README.md"],
            observed_at="2026-08-02T00:02:00Z",
        )
        self.assertEqual(proposal["decision"], "NO_CHANGE")
        self.assertIsNone(proposal["reason_code"])

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(ValueError):
            module.strict_loads('{"x":1,"x":2}')


if __name__ == "__main__":
    unittest.main()
