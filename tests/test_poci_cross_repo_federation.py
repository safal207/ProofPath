from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from verify_poci_cross_repo_federation import (  # noqa: E402
    CONSUMER_PROFILE,
    POLICY_PROFILE,
    PRODUCER_PROFILE,
    REQUIRED_GRAPHS,
    compute_consumer_receipt_root,
    compute_federation_root,
    verify_federation,
)


class PoCICrossRepoFederationTests(unittest.TestCase):
    def make_case(self):
        roots = {
            name: "sha256:" + format(index + 1, "x") * 64
            for index, name in enumerate(REQUIRED_GRAPHS)
        }
        expected = {
            "round_id": "round-1",
            "consensus_root": "sha256:" + "a" * 64,
            "source_digest": "sha256:" + "b" * 64,
            "graph_set_id": "graph-set-1",
            "poci_envelope_id": "envelope-1",
            "graph_roots": roots,
            "transition_cells_root": "sha256:" + "c" * 64,
            "computed_multigraph_root": "sha256:" + "d" * 64,
            "required_domain_count": 2,
            "external_consumer_required": True,
        }
        producer_policy = {
            "repository": "example/producer",
            "workflow": "example/producer/.github/workflows/producer.yml",
            "attestation_source_sha": "producer-merge",
            "attestation_signer_sha": "producer-merge",
            "report_sha256": "sha256:producer-subject",
        }
        consumer_policy = {
            "repository": "example/consumer",
            "workflow": "example/consumer/.github/workflows/consumer.yml",
            "attestation_source_sha": "consumer-merge",
            "attestation_signer_sha": "consumer-merge",
            "receipt_sha256": "sha256:consumer-subject",
            "receipt_root": None,
        }
        policy = {
            "profile_id": POLICY_PROFILE,
            "producer": producer_policy,
            "external_consumer": consumer_policy,
            "expected": expected,
        }
        producer_report = {
            "profile_id": PRODUCER_PROFILE,
            "round_id": expected["round_id"],
            "decision": "ACCEPT",
            "valid": True,
            "consensus_root": expected["consensus_root"],
            "consensus": {
                key: expected[key]
                for key in (
                    "source_digest",
                    "graph_set_id",
                    "poci_envelope_id",
                    "graph_roots",
                    "transition_cells_root",
                    "computed_multigraph_root",
                )
            },
            "attestation_profile": "github-keyless-slsa-provenance",
            "verified_attestation_count": 3,
            "signer_workflow": producer_policy["workflow"],
            "source_digest": producer_policy["attestation_source_sha"],
            "signer_digest": producer_policy["attestation_signer_sha"],
            "self_hosted_runners_denied": True,
        }
        consumer_receipt = {
            "profile_id": CONSUMER_PROFILE,
            "decision": "ACCEPT",
            "primary_reason_code": None,
            "reason_codes": [],
            "findings": [],
            "consumer": {
                "consumer_id": "external-consumer",
                "repository": consumer_policy["repository"],
                "workflow": consumer_policy["workflow"],
                "commit_sha": consumer_policy["attestation_source_sha"],
            },
            "producer": {
                "repository": producer_policy["repository"],
                "workflow": producer_policy["workflow"],
                "attestation_source_sha": producer_policy["attestation_source_sha"],
                "attestation_signer_sha": producer_policy["attestation_signer_sha"],
                "report_sha256": producer_policy["report_sha256"],
            },
            "accepted_consensus": {
                key: expected[key]
                for key in (
                    "round_id",
                    "consensus_root",
                    "source_digest",
                    "graph_set_id",
                    "poci_envelope_id",
                    "graph_roots",
                    "transition_cells_root",
                    "computed_multigraph_root",
                )
            },
            "verification": {
                "producer_attestation_verified": True,
                "producer_report_digest_verified": True,
                "producer_code_sha_verified": True,
                "source_recomputed": True,
                "six_graph_roots_recomputed": True,
                "transition_cells_recomputed": True,
                "consumer_attestation_required": True,
            },
            "honest_limitations": [],
            "receipt_root": None,
            "valid": True,
        }
        consumer_receipt["receipt_root"] = compute_consumer_receipt_root(
            consumer_receipt
        )
        consumer_policy["receipt_root"] = consumer_receipt["receipt_root"]
        return policy, producer_report, consumer_receipt

    def run_case(self, policy, producer_report, consumer_receipt, **overrides):
        args = {
            "producer_report_digest": "sha256:producer-subject",
            "consumer_receipt_digest": "sha256:consumer-subject",
            "producer_attestation_result": [{"verified": "producer"}],
            "consumer_attestation_result": [{"verified": "consumer"}],
        }
        args.update(overrides)
        return verify_federation(
            policy, producer_report, consumer_receipt, **args
        )

    def test_valid_two_domain_federation_accepts(self):
        result = self.run_case(*self.make_case())
        self.assertEqual(result["decision"], "ACCEPT")
        self.assertTrue(result["valid"])
        self.assertEqual(result["domain_count"], 2)
        self.assertEqual(len(result["consensus"]["graph_roots"]), 6)
        self.assertEqual(result["federation_root"], compute_federation_root(result))

    def test_producer_subject_substitution_challenges(self):
        result = self.run_case(
            *self.make_case(), producer_report_digest="sha256:other"
        )
        self.assertEqual(result["decision"], "CHALLENGE")
        self.assertIn("FEDERATION_PRODUCER_SUBJECT_MISMATCH", result["reason_codes"])

    def test_consumer_subject_substitution_challenges(self):
        result = self.run_case(
            *self.make_case(), consumer_receipt_digest="sha256:other"
        )
        self.assertEqual(result["decision"], "CHALLENGE")
        self.assertIn("FEDERATION_CONSUMER_SUBJECT_MISMATCH", result["reason_codes"])

    def test_missing_producer_attestation_blocks(self):
        result = self.run_case(
            *self.make_case(), producer_attestation_result=None
        )
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("FEDERATION_PRODUCER_ATTESTATION_MISSING", result["reason_codes"])

    def test_missing_consumer_attestation_blocks(self):
        result = self.run_case(
            *self.make_case(), consumer_attestation_result=None
        )
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("FEDERATION_CONSUMER_ATTESTATION_MISSING", result["reason_codes"])

    def test_same_repository_domain_blocks(self):
        policy, producer, consumer = self.make_case()
        policy["external_consumer"]["repository"] = policy["producer"]["repository"]
        consumer["consumer"]["repository"] = policy["producer"]["repository"]
        consumer["receipt_root"] = compute_consumer_receipt_root(consumer)
        policy["external_consumer"]["receipt_root"] = consumer["receipt_root"]
        result = self.run_case(policy, producer, consumer)
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("FEDERATION_DOMAIN_NOT_DISTINCT", result["reason_codes"])

    def test_external_graph_substitution_challenges(self):
        policy, producer, consumer = self.make_case()
        consumer["accepted_consensus"]["graph_roots"] = dict(
            consumer["accepted_consensus"]["graph_roots"]
        )
        consumer["accepted_consensus"]["graph_roots"]["authority"] = (
            "sha256:" + "f" * 64
        )
        consumer["receipt_root"] = compute_consumer_receipt_root(consumer)
        policy["external_consumer"]["receipt_root"] = consumer["receipt_root"]
        result = self.run_case(policy, producer, consumer)
        self.assertEqual(result["decision"], "CHALLENGE")
        self.assertIn("FEDERATION_CROSS_DOMAIN_MISMATCH", result["reason_codes"])

    def test_external_receipt_root_tamper_challenges(self):
        policy, producer, consumer = self.make_case()
        consumer["receipt_root"] = "sha256:" + "0" * 64
        result = self.run_case(policy, producer, consumer)
        self.assertEqual(result["decision"], "CHALLENGE")
        self.assertIn(
            "FEDERATION_CONSUMER_RECEIPT_ROOT_MISMATCH", result["reason_codes"]
        )

    def test_external_workflow_substitution_blocks(self):
        policy, producer, consumer = self.make_case()
        consumer["consumer"]["workflow"] = (
            "example/consumer/.github/workflows/other.yml"
        )
        consumer["receipt_root"] = compute_consumer_receipt_root(consumer)
        policy["external_consumer"]["receipt_root"] = consumer["receipt_root"]
        result = self.run_case(policy, producer, consumer)
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("FEDERATION_CONSUMER_RECEIPT_INVALID", result["reason_codes"])

    def test_federation_root_is_deterministic(self):
        case = self.make_case()
        left = self.run_case(*copy.deepcopy(case))
        right = self.run_case(*copy.deepcopy(case))
        self.assertEqual(left["federation_root"], right["federation_root"])


if __name__ == "__main__":
    unittest.main()
