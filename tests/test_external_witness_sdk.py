from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "sdk" / "proofpath_external_witness.py"
spec = importlib.util.spec_from_file_location("external_witness", MODULE_PATH)
assert spec and spec.loader
external_witness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(external_witness)


class ExternalWitnessSdkTests(unittest.TestCase):
    def make_case(self):
        source = {
            "profile_id": "proofpath.poci.multigraph.source.v0.1",
            "items": [1, 2, 3],
        }
        cells = [
            {"cell_id": "proposal"},
            {"cell_id": "execution"},
            {"cell_id": "observation"},
        ]
        roots = {
            name: "sha256:" + str(index + 1) * 64
            for index, name in enumerate(external_witness.REQUIRED_GRAPHS)
        }
        expected = {
            "round_id": "round-1",
            "consensus_root": "sha256:" + "a" * 64,
            "source_digest": external_witness.digest(
                external_witness.SOURCE_DOMAIN, source
            ),
            "graph_set_id": "graph-set-1",
            "poci_envelope_id": "envelope-1",
            "graph_roots": roots,
            "transition_cells_root": external_witness.digest(
                external_witness.CELLS_DOMAIN, cells
            ),
            "computed_multigraph_root": "sha256:" + "b" * 64,
        }
        challenge = {
            "profile_id": external_witness.CHALLENGE_PROFILE,
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
                "profile_id": external_witness.RESPONSE_PROFILE,
                "required_fields": [],
                "verification_steps": [],
            },
            "challenge_root": None,
        }
        challenge["challenge_root"] = external_witness.digest(
            external_witness.CHALLENGE_DOMAIN, challenge
        )
        report = {
            "profile_id": external_witness.MULTIGRAPH_PROFILE,
            "decision": "ACCEPT",
            "valid": True,
            "graph_set_id": expected["graph_set_id"],
            "poci_envelope_id": expected["poci_envelope_id"],
            "graphs": {
                name: {"root": root} for name, root in roots.items()
            },
            "transition_cells": cells,
            "computed_multigraph_root": expected["computed_multigraph_root"],
        }
        return challenge, report, source

    def create(self, challenge, report, source, **overrides):
        arguments = {
            "domain_id": "outside-witness",
            "repository": "outside-org/witness",
            "owner": "outside-org",
            "workflow": (
                "outside-org/witness/.github/workflows/"
                "proofpath-external-witness.yml"
            ),
            "producer_code_sha": "producer-code",
            "source_path": "source.valid.json",
            "source_document": source,
            "source_file_digest": "sha256:" + "c" * 64,
            "producer_attestation_verified": True,
            "producer_attestation_verification_digest": "sha256:" + "d" * 64,
        }
        arguments.update(overrides)
        return external_witness.create_response(
            challenge, report, **arguments
        )

    def test_valid_challenge(self):
        challenge, _, _ = self.make_case()
        self.assertEqual(external_witness.verify_challenge(challenge), [])

    def test_challenge_tamper_is_detected(self):
        challenge, _, _ = self.make_case()
        challenge["current"]["domain_count"] = 99
        self.assertIn(
            "CHALLENGE_ROOT_MISMATCH",
            external_witness.verify_challenge(challenge),
        )

    def test_external_owner_accepts(self):
        response = self.create(*self.make_case())
        self.assertEqual(response["decision"], "ACCEPT")
        self.assertTrue(response["claims_organizational_independence"])
        self.assertFalse(response["authority_granted"])
        self.assertTrue(external_witness.verify_response_root(response))

    def test_same_owner_holds(self):
        challenge, report, source = self.make_case()
        response = self.create(
            challenge,
            report,
            source,
            repository="safal207/another-repo",
            owner="safal207",
            workflow=(
                "safal207/another-repo/.github/workflows/"
                "proofpath-external-witness.yml"
            ),
        )
        self.assertEqual(response["decision"], "HOLD")
        self.assertIn("OPERATOR_OWNER_NOT_INDEPENDENT", response["reason_codes"])
        self.assertFalse(response["claims_organizational_independence"])

    def test_repository_owner_mismatch_blocks(self):
        response = self.create(
            *self.make_case(),
            repository="outside-org/witness",
            owner="different-org",
        )
        self.assertEqual(response["decision"], "BLOCK")

    def test_workflow_repository_mismatch_blocks(self):
        response = self.create(
            *self.make_case(),
            workflow="other/repo/.github/workflows/witness.yml",
        )
        self.assertEqual(response["decision"], "BLOCK")

    def test_source_mutation_challenges(self):
        challenge, report, source = self.make_case()
        source["items"].append(4)
        response = self.create(challenge, report, source)
        self.assertEqual(response["decision"], "CHALLENGE")
        self.assertIn("EXTERNAL_CONSENSUS_MISMATCH", response["reason_codes"])

    def test_graph_root_mutation_challenges(self):
        challenge, report, source = self.make_case()
        report["graphs"]["authority"]["root"] = "sha256:" + "e" * 64
        response = self.create(challenge, report, source)
        self.assertEqual(response["decision"], "CHALLENGE")

    def test_transition_cells_mutation_challenges(self):
        challenge, report, source = self.make_case()
        report["transition_cells"][1]["cell_id"] = "substituted"
        response = self.create(challenge, report, source)
        self.assertEqual(response["decision"], "CHALLENGE")

    def test_missing_producer_attestation_blocks(self):
        response = self.create(
            *self.make_case(),
            producer_attestation_verified=False,
        )
        self.assertEqual(response["decision"], "BLOCK")
        self.assertIn(
            "PRODUCER_ATTESTATION_UNVERIFIED", response["reason_codes"]
        )

    def test_response_root_is_deterministic(self):
        case = self.make_case()
        left = self.create(*copy.deepcopy(case))
        right = self.create(*copy.deepcopy(case))
        self.assertEqual(left["response_root"], right["response_root"])

    def test_finalize_submission_accepts_exact_response(self):
        response = self.create(*self.make_case())
        with tempfile.TemporaryDirectory() as directory:
            response_path = Path(directory) / "response.json"
            response_path.write_text(
                json.dumps(response, indent=2) + "\n", encoding="utf-8"
            )
            submission = external_witness.finalize_submission(
                response,
                response_subject_digest=external_witness.sha256_file(
                    response_path
                ),
                attestation_verification_digest="sha256:" + "f" * 64,
            )
        self.assertEqual(submission["decision"], "ACCEPT")
        self.assertFalse(submission["authority_granted"])

    def test_finalize_rejects_tampered_response(self):
        response = self.create(*self.make_case())
        response["owner"] = "tampered-org"
        submission = external_witness.finalize_submission(
            response,
            response_subject_digest="sha256:" + "e" * 64,
            attestation_verification_digest="sha256:" + "f" * 64,
        )
        self.assertEqual(submission["decision"], "BLOCK")
        self.assertIn("RESPONSE_ROOT_MISMATCH", submission["reason_codes"])


if __name__ == "__main__":
    unittest.main()
