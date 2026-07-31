from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from verify_poci_external_operator_admission import (  # noqa: E402
    CHALLENGE_DOMAIN,
    CHALLENGE_PROFILE,
    DOMAINS_PROFILE,
    PROVENANCE_PROFILE,
    RESPONSE_DOMAIN,
    RESPONSE_PROFILE,
    SUBMISSION_DOMAIN,
    SUBMISSION_PROFILE,
    REQUIRED_GRAPHS,
    digest,
    verify_admission,
)

SHA = "a" * 40
SIGNER_SHA = "b" * 40
HEAD_SHA = "c" * 40
ATT_RESULT_DIGEST = "sha256:" + "9" * 64


def subject_digest(response):
    import json

    raw = (json.dumps(response, indent=2) + "\n").encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


class ExternalOperatorAdmissionTests(unittest.TestCase):
    def make_case(self):
        roots = {
            name: "sha256:" + str(index + 1) * 64
            for index, name in enumerate(REQUIRED_GRAPHS)
        }
        expected = {
            "round_id": "round-1",
            "consensus_root": "sha256:" + "7" * 64,
            "source_digest": "sha256:" + "8" * 64,
            "graph_set_id": "graph-set-1",
            "poci_envelope_id": "envelope-1",
            "graph_roots": roots,
            "transition_cells_root": "sha256:" + "6" * 64,
            "computed_multigraph_root": "sha256:" + "5" * 64,
        }
        challenge = {
            "profile_id": CHALLENGE_PROFILE,
            "challenge_version": "0.1",
            "producer_owner": "safal207",
            "status": "AWAITING_INDEPENDENT_OPERATOR",
            "current": {
                "domain_count": 2,
                "distinct_owner_count": 1,
                "external_owner_count": 0,
                "distinct_workflow_count": 2,
            },
            "required": {
                "minimum_domains": 3,
                "minimum_distinct_owners": 2,
                "minimum_external_owners": 1,
                "minimum_distinct_workflows": 3,
                "repository_owner_must_differ_from": "safal207",
                "keyless_attestation_required": True,
                "exact_consensus_required": True,
            },
            "expected_consensus": expected,
            "response_contract": {
                "profile_id": RESPONSE_PROFILE,
                "required_fields": [],
                "verification_steps": [],
            },
            "challenge_root": None,
        }
        challenge["challenge_root"] = digest(CHALLENGE_DOMAIN, challenge)

        response = {
            "profile_id": RESPONSE_PROFILE,
            "challenge_root": challenge["challenge_root"],
            "decision": "ACCEPT",
            "valid": True,
            "reason_codes": [],
            "domain_id": "external-operator-1",
            "repository": "outside-org/poci-witness",
            "owner": "outside-org",
            "workflow": (
                "outside-org/poci-witness/.github/workflows/"
                "proofpath-external-witness.yml"
            ),
            "role": "independent-external-witness",
            "claims_organizational_independence": True,
            "producer": {
                "owner": "safal207",
                "code_sha": SHA,
                "source_path": "examples/poci-witness/multigraph/source.valid.json",
                "source_file_digest": "sha256:" + "4" * 64,
                "attestation_verified": True,
                "attestation_verification_digest": "sha256:" + "3" * 64,
            },
            "attestation_status": "PENDING_KEYLESS_ATTESTATION",
            "consensus": copy.deepcopy(expected),
            "transition_cell_count": 3,
            "response_root": None,
            "permitted_next_transition": "KEYLESS_ATTEST_RESPONSE",
            "authority_granted": False,
        }
        response["response_root"] = digest(RESPONSE_DOMAIN, response)
        response_digest = subject_digest(response)

        submission = {
            "profile_id": SUBMISSION_PROFILE,
            "decision": "ACCEPT",
            "valid": True,
            "reason_codes": [],
            "response_subject_digest": response_digest,
            "response_attestation_claimed_verified": True,
            "response_attestation_verification_digest": "sha256:" + "2" * 64,
            "response": copy.deepcopy(response),
            "submission_root": None,
            "authority_granted": False,
            "permitted_next_transition": "SUBMIT_TO_PROOFPATH_ADMISSION",
        }
        submission["submission_root"] = digest(SUBMISSION_DOMAIN, submission)

        provenance = {
            "profile_id": PROVENANCE_PROFILE,
            "repository": response["repository"],
            "owner": response["owner"],
            "workflow": response["workflow"],
            "source_sha": SHA,
            "signer_sha": SIGNER_SHA,
            "oidc_issuer": "https://token.actions.githubusercontent.com",
            "deny_self_hosted_runners": True,
            "response_subject_digest": response_digest,
        }

        domains = {
            "profile_id": DOMAINS_PROFILE,
            "federation_root": "sha256:" + "1" * 64,
            "domains": [
                {
                    "domain_id": "proofpath-producer",
                    "repository": "safal207/ProofPath",
                    "owner": "safal207",
                    "workflow": (
                        "safal207/ProofPath/.github/workflows/"
                        "poci-signed-witness-network.yml"
                    ),
                },
                {
                    "domain_id": "ibex-consumer",
                    "repository": "safal207/ibex-agent-verification",
                    "owner": "safal207",
                    "workflow": (
                        "safal207/ibex-agent-verification/.github/workflows/"
                        "proofpath-poci-consumer.yml"
                    ),
                },
            ],
        }
        return challenge, response, submission, provenance, domains, response_digest

    def run_case(self, case, **overrides):
        challenge, response, submission, provenance, domains, response_digest = case
        args = {
            "pr_head_repository": "outside-org/poci-witness",
            "pr_head_owner": "outside-org",
            "pr_head_sha": HEAD_SHA,
            "response_subject_digest": response_digest,
            "attestation_result_digest": ATT_RESULT_DIGEST,
            "attestation_verified": True,
            "source_ancestry_verified": True,
        }
        args.update(overrides)
        return verify_admission(
            challenge,
            response,
            submission,
            provenance,
            domains,
            **args,
        )

    def test_valid_external_submission_is_admitted(self):
        result = self.run_case(self.make_case())
        self.assertEqual(result["decision"], "ACCEPT")
        self.assertTrue(result["valid"])
        self.assertEqual(result["domain_entry"]["owner"], "outside-org")
        self.assertEqual(len(result["domain_entry"]["consensus"]["graph_roots"]), 6)
        self.assertEqual(len(result["updated_domains_document"]["domains"]), 3)

    def test_same_owner_is_blocked(self):
        case = list(self.make_case())
        case[1]["repository"] = "safal207/external-witness"
        case[1]["owner"] = "safal207"
        case[1]["workflow"] = (
            "safal207/external-witness/.github/workflows/"
            "proofpath-external-witness.yml"
        )
        case[1]["response_root"] = None
        case[1]["response_root"] = digest(RESPONSE_DOMAIN, case[1])
        case[5] = subject_digest(case[1])
        case[2]["response"] = copy.deepcopy(case[1])
        case[2]["response_subject_digest"] = case[5]
        case[2]["submission_root"] = None
        case[2]["submission_root"] = digest(SUBMISSION_DOMAIN, case[2])
        case[3].update(
            {
                "repository": case[1]["repository"],
                "owner": "safal207",
                "workflow": case[1]["workflow"],
                "response_subject_digest": case[5],
            }
        )
        result = self.run_case(
            tuple(case),
            pr_head_repository="safal207/external-witness",
            pr_head_owner="safal207",
            response_subject_digest=case[5],
        )
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("OPERATOR_NOT_INDEPENDENT", result["reason_codes"])

    def test_challenge_root_substitution_challenges(self):
        case = list(self.make_case())
        case[0]["challenge_root"] = "sha256:" + "f" * 64
        result = self.run_case(tuple(case))
        self.assertEqual(result["decision"], "CHALLENGE")
        self.assertIn("CHALLENGE_ROOT_MISMATCH", result["reason_codes"])

    def test_response_root_substitution_challenges(self):
        case = list(self.make_case())
        case[1]["response_root"] = "sha256:" + "f" * 64
        result = self.run_case(tuple(case))
        self.assertEqual(result["decision"], "CHALLENGE")
        self.assertIn("RESPONSE_ROOT_MISMATCH", result["reason_codes"])

    def test_submission_root_substitution_challenges(self):
        case = list(self.make_case())
        case[2]["submission_root"] = "sha256:" + "f" * 64
        result = self.run_case(tuple(case))
        self.assertEqual(result["decision"], "CHALLENGE")
        self.assertIn("SUBMISSION_ROOT_MISMATCH", result["reason_codes"])

    def test_subject_digest_substitution_challenges(self):
        result = self.run_case(
            self.make_case(),
            response_subject_digest="sha256:" + "e" * 64,
        )
        self.assertEqual(result["decision"], "CHALLENGE")
        self.assertIn("RESPONSE_SUBJECT_DIGEST_MISMATCH", result["reason_codes"])

    def test_consensus_substitution_challenges(self):
        case = list(self.make_case())
        case[1]["consensus"]["graph_roots"]["authority"] = "sha256:" + "f" * 64
        case[1]["response_root"] = None
        case[1]["response_root"] = digest(RESPONSE_DOMAIN, case[1])
        case[5] = subject_digest(case[1])
        case[2]["response"] = copy.deepcopy(case[1])
        case[2]["response_subject_digest"] = case[5]
        case[2]["submission_root"] = None
        case[2]["submission_root"] = digest(SUBMISSION_DOMAIN, case[2])
        case[3]["response_subject_digest"] = case[5]
        result = self.run_case(tuple(case), response_subject_digest=case[5])
        self.assertEqual(result["decision"], "CHALLENGE")
        self.assertIn("CONSENSUS_MISMATCH", result["reason_codes"])

    def test_repository_identity_mismatch_blocks(self):
        result = self.run_case(self.make_case(), pr_head_repository="other/repo")
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("REPOSITORY_IDENTITY_MISMATCH", result["reason_codes"])

    def test_workflow_identity_mismatch_blocks(self):
        case = list(self.make_case())
        case[3]["workflow"] = "outside-org/poci-witness/.github/workflows/other.yml"
        result = self.run_case(tuple(case))
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("WORKFLOW_IDENTITY_MISMATCH", result["reason_codes"])

    def test_unverified_attestation_blocks(self):
        result = self.run_case(self.make_case(), attestation_verified=False)
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("ATTESTATION_UNVERIFIED", result["reason_codes"])

    def test_unverified_source_ancestry_blocks(self):
        result = self.run_case(self.make_case(), source_ancestry_verified=False)
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("SOURCE_ANCESTRY_UNVERIFIED", result["reason_codes"])

    def test_duplicate_repository_blocks(self):
        case = list(self.make_case())
        case[4]["domains"][0]["repository"] = "outside-org/poci-witness"
        result = self.run_case(tuple(case))
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("REPOSITORY_DUPLICATE", result["reason_codes"])

    def test_authority_claim_blocks(self):
        case = list(self.make_case())
        case[1]["authority_granted"] = True
        case[1]["response_root"] = None
        case[1]["response_root"] = digest(RESPONSE_DOMAIN, case[1])
        case[5] = subject_digest(case[1])
        case[2]["response"] = copy.deepcopy(case[1])
        case[2]["response_subject_digest"] = case[5]
        case[2]["submission_root"] = None
        case[2]["submission_root"] = digest(SUBMISSION_DOMAIN, case[2])
        case[3]["response_subject_digest"] = case[5]
        result = self.run_case(tuple(case), response_subject_digest=case[5])
        self.assertEqual(result["decision"], "BLOCK")
        self.assertIn("AUTHORITY_CLAIM_FORBIDDEN", result["reason_codes"])

    def test_admission_root_is_deterministic(self):
        left = self.run_case(copy.deepcopy(self.make_case()))
        right = self.run_case(copy.deepcopy(self.make_case()))
        self.assertEqual(left["admission_root"], right["admission_root"])


if __name__ == "__main__":
    unittest.main()
