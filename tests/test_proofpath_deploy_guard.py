from __future__ import annotations

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_proofpath_deploy_guard.py"
SPEC = importlib.util.spec_from_file_location("deploy_guard", SCRIPT)
assert SPEC and SPEC.loader
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)

POLICY_PATH = ROOT / "examples" / "deploy-guard" / "deploy-policy.json"
ACCEPT_PATH = ROOT / "examples" / "deploy-guard" / "deploy.accept.json"


class DeployGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = guard.load_json(POLICY_PATH)
        self.evidence = guard.load_json(ACCEPT_PATH)

    def evaluate(self, mutate=None):
        policy = copy.deepcopy(self.policy)
        evidence = copy.deepcopy(self.evidence)
        if mutate:
            mutate(policy, evidence)
        return guard.evaluate(policy, evidence)

    def assert_decision(self, expected, mutate=None, code=None):
        result = self.evaluate(mutate)
        self.assertEqual(expected, result["decision"])
        if code:
            self.assertIn(code, result["reason_codes"])
        self.assertFalse(result["authority_granted"])
        return result

    def test_accept_fixture(self):
        result = self.assert_decision("ACCEPT")
        self.assertTrue(result["execution_allowed"])
        self.assertEqual("POLICY_VERIFIED", result["assurance"]["assurance_level"])
        self.assertEqual("SINGLE_WORKFLOW_REFERENCE", result["assurance"]["witness_level"])
        self.assertEqual("NOT_FINANCIALLY_COVERED", result["assurance"]["coverage"])

    def test_hold_missing_approval(self):
        def mutate(_p, e): e["approvals"] = e["approvals"][:1]
        self.assert_decision("HOLD", mutate, "DEPLOY_APPROVAL_COUNT_INSUFFICIENT")

    def test_hold_missing_role(self):
        def mutate(_p, e): e["approvals"][1]["role"] = "service-owner"
        self.assert_decision("HOLD", mutate, "DEPLOY_APPROVAL_ROLE_MISSING")

    def test_hold_missing_check(self):
        def mutate(_p, e): e["checks"] = e["checks"][:-1]
        self.assert_decision("HOLD", mutate, "DEPLOY_REQUIRED_CHECK_MISSING")

    def test_hold_pending_check(self):
        def mutate(_p, e): e["checks"][0]["status"] = "queued"
        self.assert_decision("HOLD", mutate, "DEPLOY_CHECK_PENDING")

    def test_hold_pending_ticket(self):
        def mutate(_p, e): e["change_ticket"]["status"] = "pending"
        self.assert_decision("HOLD", mutate, "DEPLOY_CHANGE_TICKET_PENDING")

    def test_block_failed_check(self):
        def mutate(_p, e): e["checks"][0]["status"] = "failure"
        self.assert_decision("BLOCK", mutate, "DEPLOY_CHECK_FAILED")

    def test_block_critical_vulnerability(self):
        def mutate(_p, e): e["security"]["critical_vulnerabilities"] = 1
        self.assert_decision("BLOCK", mutate, "DEPLOY_CRITICAL_VULNERABILITY")

    def test_block_inactive_authority(self):
        def mutate(_p, e): e["authority"]["active"] = False
        self.assert_decision("BLOCK", mutate, "DEPLOY_AUTHORITY_INACTIVE")

    def test_block_expired_authority(self):
        def mutate(_p, e): e["authority"]["expires_at"] = "2025-01-01T00:00:00Z"
        self.assert_decision("BLOCK", mutate, "DEPLOY_AUTHORITY_EXPIRED")

    def test_block_authority_scope(self):
        def mutate(_p, e): e["authority"]["scope"]["environments"] = ["staging"]
        self.assert_decision("BLOCK", mutate, "DEPLOY_AUTHORITY_SCOPE_MISMATCH")

    def test_block_branch_not_allowed(self):
        def mutate(_p, e): e["branch"] = "feature/demo"
        self.assert_decision("BLOCK", mutate, "DEPLOY_BRANCH_NOT_ALLOWED")

    def test_block_unverified_attestation(self):
        def mutate(_p, e): e["build_provenance"]["attestation_verified"] = False
        self.assert_decision("BLOCK", mutate, "DEPLOY_ATTESTATION_UNVERIFIED")

    def test_block_self_hosted_runner(self):
        def mutate(_p, e): e["build_provenance"]["runner_environment"] = "self-hosted"
        self.assert_decision("BLOCK", mutate, "DEPLOY_RUNNER_NOT_TRUSTED")

    def test_block_already_executed(self):
        def mutate(_p, e): e["execution"]["performed"] = True
        self.assert_decision("BLOCK", mutate, "DEPLOY_ALREADY_EXECUTED")

    def test_challenge_artifact_mismatch(self):
        def mutate(_p, e): e["build_provenance"]["artifact_digest"] = "sha256:" + "b" * 64
        self.assert_decision("CHALLENGE", mutate, "DEPLOY_PROVENANCE_ARTIFACT_MISMATCH")

    def test_challenge_commit_mismatch(self):
        def mutate(_p, e): e["build_provenance"]["commit_sha"] = "9" * 40
        self.assert_decision("CHALLENGE", mutate, "DEPLOY_PROVENANCE_COMMIT_MISMATCH")

    def test_challenge_approval_commit_mismatch(self):
        def mutate(_p, e): e["approvals"][0]["commit_sha"] = "9" * 40
        self.assert_decision("CHALLENGE", mutate, "DEPLOY_APPROVAL_COMMIT_MISMATCH")

    def test_challenge_check_commit_mismatch(self):
        def mutate(_p, e): e["checks"][0]["commit_sha"] = "9" * 40
        self.assert_decision("CHALLENGE", mutate, "DEPLOY_CHECK_COMMIT_MISMATCH")

    def test_challenge_policy_version_mismatch(self):
        def mutate(_p, e): e["policy"]["policy_version"] = "0.9.0"
        self.assert_decision("CHALLENGE", mutate, "DEPLOY_POLICY_VERSION_MISMATCH")

    def test_challenge_precedes_block_and_hold(self):
        def mutate(_p, e):
            e["build_provenance"]["artifact_digest"] = "sha256:" + "b" * 64
            e["checks"][0]["status"] = "failure"
            e["approvals"] = []
        result = self.assert_decision("CHALLENGE", mutate)
        self.assertIn("DEPLOY_CHECK_FAILED", result["reason_codes"])
        self.assertIn("DEPLOY_APPROVAL_COUNT_INSUFFICIENT", result["reason_codes"])

    def test_clearance_root_is_deterministic(self):
        first = self.evaluate()
        second = self.evaluate()
        self.assertEqual(first["clearance_root"], second["clearance_root"])
        normalized = copy.deepcopy(first)
        normalized["clearance_root"] = None
        self.assertEqual(first["clearance_root"], guard.digest(guard.CLEARANCE_DOMAIN, normalized))

    def test_policy_and_evidence_roots_change_on_mutation(self):
        base = self.evaluate()
        def mutate(_p, e):
            e["action_id"] = "deploy-demo-002"
        changed = self.evaluate(mutate)
        self.assertEqual(base["policy_root"], changed["policy_root"])
        self.assertNotEqual(base["evidence_root"], changed["evidence_root"])
        self.assertNotEqual(base["clearance_root"], changed["clearance_root"])

    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"profile_id":"a","profile_id":"b"}', encoding="utf-8")
            with self.assertRaises(guard.EvidenceError):
                guard.load_json(path)

    def test_float_rejected(self):
        evidence = copy.deepcopy(self.evidence)
        evidence["risk_score"] = 0.5
        with self.assertRaises(guard.EvidenceError):
            guard.canonical_json_bytes(evidence)


if __name__ == "__main__":
    unittest.main()
