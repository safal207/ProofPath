from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from verify_poci_organizational_independence import (  # noqa: E402
    CHALLENGE_PROFILE,
    DOMAINS_PROFILE,
    POLICY_PROFILE,
    REQUIRED_GRAPHS,
    verify,
)


class OrganizationalIndependenceTests(unittest.TestCase):
    def make_case(self):
        graph_roots = {
            name: f"sha256:{index + 1:064x}"
            for index, name in enumerate(REQUIRED_GRAPHS)
        }
        expected = {
            "round_id": "round-1",
            "consensus_root": "sha256:" + "a" * 64,
            "source_digest": "sha256:" + "b" * 64,
            "graph_set_id": "graph-set-1",
            "poci_envelope_id": "envelope-1",
            "graph_roots": graph_roots,
            "transition_cells_root": "sha256:" + "c" * 64,
            "computed_multigraph_root": "sha256:" + "d" * 64,
        }
        policy = {
            "profile_id": POLICY_PROFILE,
            "producer_owner": "producer",
            "minimum_domains": 3,
            "minimum_distinct_owners": 2,
            "minimum_external_owners": 1,
            "minimum_distinct_workflows": 3,
            "require_attestation_verified": True,
            "require_exact_consensus": True,
            "expected": expected,
        }

        def domain(domain_id, owner, repository, workflow, role, claim=False):
            return {
                "domain_id": domain_id,
                "repository": f"{owner}/{repository}",
                "owner": owner,
                "workflow": f"{owner}/{repository}/.github/workflows/{workflow}.yml",
                "role": role,
                "attestation_verified": True,
                "claims_organizational_independence": claim,
                "attestation_subject_digest": "sha256:" + "e" * 64,
                "attestation_verification_digest": "sha256:" + "f" * 64,
                "consensus": copy.deepcopy(expected),
            }

        current = {
            "profile_id": DOMAINS_PROFILE,
            "domains": [
                domain("producer", "producer", "ProofPath", "producer", "producer"),
                domain(
                    "consumer",
                    "producer",
                    "Ibex",
                    "consumer",
                    "external-consumer",
                ),
            ],
        }
        external = domain(
            "external-lab",
            "external-lab",
            "poci-witness",
            "witness",
            "independent-witness",
            True,
        )
        return policy, current, external

    def test_current_same_owner_federation_holds(self):
        policy, current, _ = self.make_case()
        report, challenge = verify(policy, current)
        self.assertEqual(report["decision"], "HOLD")
        self.assertIn("GOVERNANCE_DOMAIN_COUNT_INSUFFICIENT", report["reason_codes"])
        self.assertIn(
            "GOVERNANCE_OWNER_DIVERSITY_INSUFFICIENT", report["reason_codes"]
        )
        self.assertIn("GOVERNANCE_EXTERNAL_OWNER_MISSING", report["reason_codes"])
        self.assertIsNotNone(challenge)
        self.assertEqual(challenge["profile_id"], CHALLENGE_PROFILE)
        self.assertEqual(report["permitted_next_transition"], "AWAIT_EXTERNAL_OPERATOR")

    def test_external_owner_completes_organizational_quorum(self):
        policy, current, external = self.make_case()
        current["domains"].append(external)
        report, challenge = verify(policy, current)
        self.assertEqual(report["decision"], "ACCEPT")
        self.assertTrue(report["valid"])
        self.assertEqual(report["distinct_owner_count"], 2)
        self.assertEqual(report["external_owner_count"], 1)
        self.assertIsNone(challenge)

    def test_duplicate_repository_blocks(self):
        policy, current, external = self.make_case()
        external["repository"] = current["domains"][0]["repository"]
        external["owner"] = "producer"
        external["claims_organizational_independence"] = False
        current["domains"].append(external)
        report, _ = verify(policy, current)
        self.assertEqual(report["decision"], "BLOCK")
        self.assertIn("GOVERNANCE_REPOSITORY_DUPLICATE", report["reason_codes"])

    def test_duplicate_workflow_blocks(self):
        policy, current, external = self.make_case()
        external["workflow"] = current["domains"][0]["workflow"]
        current["domains"].append(external)
        report, _ = verify(policy, current)
        self.assertEqual(report["decision"], "BLOCK")
        self.assertIn("GOVERNANCE_WORKFLOW_DUPLICATE", report["reason_codes"])

    def test_unverified_attestation_blocks(self):
        policy, current, external = self.make_case()
        external["attestation_verified"] = False
        current["domains"].append(external)
        report, _ = verify(policy, current)
        self.assertEqual(report["decision"], "BLOCK")
        self.assertIn("GOVERNANCE_ATTESTATION_UNVERIFIED", report["reason_codes"])

    def test_consensus_substitution_challenges(self):
        policy, current, external = self.make_case()
        external["consensus"]["graph_roots"]["authority"] = "sha256:" + "9" * 64
        current["domains"].append(external)
        report, _ = verify(policy, current)
        self.assertEqual(report["decision"], "CHALLENGE")
        self.assertIn("GOVERNANCE_CONSENSUS_MISMATCH", report["reason_codes"])

    def test_owner_repository_mismatch_blocks(self):
        policy, current, external = self.make_case()
        external["owner"] = "different-owner"
        current["domains"].append(external)
        report, _ = verify(policy, current)
        self.assertEqual(report["decision"], "BLOCK")
        self.assertIn(
            "GOVERNANCE_OWNER_REPOSITORY_MISMATCH", report["reason_codes"]
        )

    def test_false_independence_claim_challenges(self):
        policy, current, _ = self.make_case()
        current["domains"][1]["claims_organizational_independence"] = True
        report, _ = verify(policy, current)
        self.assertEqual(report["decision"], "CHALLENGE")
        self.assertIn(
            "GOVERNANCE_FALSE_INDEPENDENCE_CLAIM", report["reason_codes"]
        )

    def test_incomplete_graph_coverage_blocks(self):
        policy, current, external = self.make_case()
        policy["require_exact_consensus"] = False
        del external["consensus"]["graph_roots"]["evidence"]
        current["domains"].append(external)
        report, _ = verify(policy, current)
        self.assertEqual(report["decision"], "BLOCK")
        self.assertIn(
            "GOVERNANCE_GRAPH_COVERAGE_INCOMPLETE", report["reason_codes"]
        )

    def test_challenge_root_is_deterministic(self):
        policy, current, _ = self.make_case()
        left_report, left = verify(copy.deepcopy(policy), copy.deepcopy(current))
        right_report, right = verify(copy.deepcopy(policy), copy.deepcopy(current))
        self.assertEqual(left_report["report_root"], right_report["report_root"])
        self.assertEqual(left["challenge_root"], right["challenge_root"])

    def test_no_external_domain_cannot_accept_with_lower_domain_threshold(self):
        policy, current, _ = self.make_case()
        policy["minimum_domains"] = 2
        policy["minimum_distinct_workflows"] = 2
        report, _ = verify(policy, current)
        self.assertEqual(report["decision"], "HOLD")
        self.assertIn("GOVERNANCE_EXTERNAL_OWNER_MISSING", report["reason_codes"])

    def test_external_domain_must_have_distinct_workflow(self):
        policy, current, external = self.make_case()
        external["workflow"] = current["domains"][1]["workflow"]
        current["domains"].append(external)
        report, _ = verify(policy, current)
        self.assertEqual(report["decision"], "BLOCK")
        self.assertIn("GOVERNANCE_WORKFLOW_DUPLICATE", report["reason_codes"])


if __name__ == "__main__":
    unittest.main()
