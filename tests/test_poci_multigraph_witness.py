from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_poci_multigraph import load_json  # noqa: E402
from run_poci_multigraph_witness import (  # noqa: E402
    build_witness_statement,
    compute_source_digest,
    compute_statement_root,
)
from verify_poci_multigraph_quorum import (  # noqa: E402
    CONFIG_PROFILE,
    run_witness_processes,
    verify_quorum,
)


class PociMultigraphWitnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config_path = (
            ROOT
            / "examples"
            / "poci-witness"
            / "multigraph"
            / "witnesses.json"
        )
        self.source_path = self.config_path.parent / "source.valid.json"
        self.config = load_json(self.config_path)
        self.source = load_json(self.source_path)
        self.source_digest = compute_source_digest(self.source)

    def make_statements(self) -> list[dict]:
        statements = []
        for spec in self.config["witnesses"]:
            statements.append(
                build_witness_statement(
                    self.source,
                    self.source_path,
                    round_id=self.config["round_id"],
                    witness_id=spec["witness_id"],
                    operator_id=spec["operator_id"],
                    nonce=spec["nonce"],
                )
            )
        return statements

    @staticmethod
    def mutate_vote(statement: dict, suffix: str) -> dict:
        changed = copy.deepcopy(statement)
        changed["graph_roots"]["causal"] = "sha256:" + suffix * 64
        changed["statement_root"] = compute_statement_root(changed)
        return changed

    def test_statement_is_deterministic(self) -> None:
        spec = self.config["witnesses"][0]
        first = build_witness_statement(
            self.source,
            self.source_path,
            round_id=self.config["round_id"],
            witness_id=spec["witness_id"],
            operator_id=spec["operator_id"],
            nonce=spec["nonce"],
        )
        second = build_witness_statement(
            self.source,
            self.source_path,
            round_id=self.config["round_id"],
            witness_id=spec["witness_id"],
            operator_id=spec["operator_id"],
            nonce=spec["nonce"],
        )
        self.assertEqual(first, second)
        self.assertEqual(first["decision"], "ACCEPT")
        self.assertEqual(len(first["graph_roots"]), 6)

    def test_three_matching_witnesses_accept(self) -> None:
        report = verify_quorum(
            self.config,
            self.make_statements(),
            expected_source_digest=self.source_digest,
        )
        self.assertEqual(report["decision"], "ACCEPT")
        self.assertEqual(len(report["agreeing_witnesses"]), 3)
        self.assertIsNotNone(report["consensus_root"])

    def test_two_of_three_accepts_with_dissent(self) -> None:
        statements = self.make_statements()
        statements[2] = self.mutate_vote(statements[2], "f")
        report = verify_quorum(
            self.config,
            statements,
            expected_source_digest=self.source_digest,
        )
        self.assertEqual(report["decision"], "ACCEPT")
        self.assertEqual(len(report["agreeing_witnesses"]), 2)
        self.assertEqual(report["dissenting_witnesses"], ["witness-gamma"])

    def test_three_different_roots_block(self) -> None:
        statements = self.make_statements()
        statements[0] = self.mutate_vote(statements[0], "a")
        statements[1] = self.mutate_vote(statements[1], "b")
        statements[2] = self.mutate_vote(statements[2], "c")
        report = verify_quorum(
            self.config,
            statements,
            expected_source_digest=self.source_digest,
        )
        self.assertEqual(report["decision"], "BLOCK")
        self.assertEqual(report["primary_reason_code"], "WITNESS_QUORUM_NOT_REACHED")

    def test_replayed_round_challenges_even_with_quorum(self) -> None:
        statements = self.make_statements()
        statements[2]["round_id"] = "round-old-000"
        statements[2]["statement_root"] = compute_statement_root(statements[2])
        report = verify_quorum(
            self.config,
            statements,
            expected_source_digest=self.source_digest,
        )
        self.assertEqual(report["decision"], "CHALLENGE")
        self.assertIn("WITNESS_ROUND_REPLAY", report["reason_codes"])

    def test_statement_tampering_challenges(self) -> None:
        statements = self.make_statements()
        statements[2]["graph_roots"]["causal"] = "sha256:" + "d" * 64
        report = verify_quorum(
            self.config,
            statements,
            expected_source_digest=self.source_digest,
        )
        self.assertEqual(report["decision"], "CHALLENGE")
        self.assertIn("WITNESS_STATEMENT_TAMPERED", report["reason_codes"])

    def test_duplicate_operator_blocks(self) -> None:
        config = copy.deepcopy(self.config)
        config["witnesses"][1]["operator_id"] = config["witnesses"][0]["operator_id"]
        statements = self.make_statements()
        statements[1]["operator_id"] = config["witnesses"][1]["operator_id"]
        statements[1]["statement_root"] = compute_statement_root(statements[1])
        report = verify_quorum(
            config,
            statements,
            expected_source_digest=self.source_digest,
        )
        self.assertEqual(report["decision"], "BLOCK")
        self.assertIn("WITNESS_OPERATOR_NOT_INDEPENDENT", report["reason_codes"])

    def test_equivocation_challenges(self) -> None:
        statements = self.make_statements()
        equivocation = self.mutate_vote(statements[0], "e")
        report = verify_quorum(
            self.config,
            statements + [equivocation],
            expected_source_digest=self.source_digest,
        )
        self.assertEqual(report["decision"], "CHALLENGE")
        self.assertIn("WITNESS_EQUIVOCATION", report["reason_codes"])

    def test_consensus_root_is_order_independent(self) -> None:
        statements = self.make_statements()
        first = verify_quorum(
            self.config,
            statements,
            expected_source_digest=self.source_digest,
        )
        second = verify_quorum(
            self.config,
            list(reversed(statements)),
            expected_source_digest=self.source_digest,
        )
        self.assertEqual(first["consensus_root"], second["consensus_root"])

    def test_subprocess_witnesses_reach_quorum(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            statements, source_digest, failures = run_witness_processes(
                self.config,
                self.config_path,
                Path(temp_dir),
            )
            report = verify_quorum(
                self.config,
                statements,
                expected_source_digest=source_digest,
                process_failures=failures,
            )
            self.assertEqual(failures, [])
            self.assertEqual(len(statements), 3)
            self.assertEqual(report["decision"], "ACCEPT")
            self.assertEqual(
                sorted(path.name for path in Path(temp_dir).glob("*.json")),
                ["witness-alpha.json", "witness-beta.json", "witness-gamma.json"],
            )

    def test_config_profile_is_explicit(self) -> None:
        self.assertEqual(self.config["profile_id"], CONFIG_PROFILE)
        self.assertEqual(self.config["quorum"], 2)
        self.assertEqual(len(self.config["witnesses"]), 3)


if __name__ == "__main__":
    unittest.main()
