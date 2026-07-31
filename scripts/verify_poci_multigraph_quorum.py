#!/usr/bin/env python3
"""Run isolated PoCI multi-graph witnesses and verify an exact-root quorum."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from build_poci_multigraph import canonical_json_bytes, load_json
from run_poci_multigraph_witness import (
    PROFILE as STATEMENT_PROFILE,
    REQUIRED_GRAPHS,
    compute_source_digest,
    compute_statement_root,
)

PROFILE = "proofpath.poci.multigraph.witness-quorum.v0.1"
CONFIG_PROFILE = "proofpath.poci.multigraph.witness-set.v0.1"
CONSENSUS_DOMAIN = b"proofpath:poci:multigraph:witness:v0.1:consensus\n"
DECISION_RANK = {"ACCEPT": 0, "HOLD": 1, "BLOCK": 2, "CHALLENGE": 3}
EXIT_CODE = {"ACCEPT": 0, "HOLD": 2, "BLOCK": 3, "CHALLENGE": 4}
PRIORITY = {
    "WITNESS_SET_INVALID": 10,
    "WITNESS_OPERATOR_NOT_INDEPENDENT": 20,
    "WITNESS_UNKNOWN": 30,
    "WITNESS_PROCESS_FAILED": 40,
    "WITNESS_ROUND_REPLAY": 100,
    "WITNESS_SOURCE_MISMATCH": 110,
    "WITNESS_STATEMENT_TAMPERED": 120,
    "WITNESS_EQUIVOCATION": 130,
    "WITNESS_GRAPH_COVERAGE_INCOMPLETE": 200,
    "WITNESS_MISSING": 300,
    "WITNESS_QUORUM_NOT_REACHED": 400,
}


def _digest(domain: bytes, value: Any) -> str:
    return "sha256:" + hashlib.sha256(domain + canonical_json_bytes(value)).hexdigest()


def _text(value: dict[str, Any], key: str) -> str | None:
    item = value.get(key)
    return item if isinstance(item, str) and item else None


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _finding(code: str, decision: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "decision": decision, "path": path, "message": message}


def _statement_vote_key(statement: dict[str, Any]) -> str:
    payload = {
        "source_digest": statement.get("source_digest"),
        "graph_set_id": statement.get("graph_set_id"),
        "poci_envelope_id": statement.get("poci_envelope_id"),
        "builder_profile_id": statement.get("builder_profile_id"),
        "graph_roots": statement.get("graph_roots"),
        "transition_cells_root": statement.get("transition_cells_root"),
        "computed_multigraph_root": statement.get("computed_multigraph_root"),
    }
    return _digest(CONSENSUS_DOMAIN, payload)


def _sort_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[tuple[str, str, str], dict[str, str]] = {}
    for item in findings:
        unique[(item["code"], item["path"], item["message"])] = item
    return sorted(
        unique.values(),
        key=lambda item: (
            -DECISION_RANK[item["decision"]],
            PRIORITY.get(item["code"], 500),
            item["code"],
            item["path"],
        ),
    )


def verify_quorum(
    config: dict[str, Any],
    statements: list[dict[str, Any]],
    *,
    expected_source_digest: str | None = None,
    process_failures: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    process_failure_details = list(process_failures or [])
    findings: list[dict[str, str]] = []

    if config.get("profile_id") != CONFIG_PROFILE:
        findings.append(
            _finding(
                "WITNESS_SET_INVALID",
                "BLOCK",
                "$.profile_id",
                "unsupported witness-set profile",
            )
        )

    round_id = _text(config, "round_id")
    if round_id is None:
        findings.append(
            _finding("WITNESS_SET_INVALID", "BLOCK", "$.round_id", "round_id is required")
        )

    quorum = config.get("quorum")
    witness_specs = [item for item in _list(config.get("witnesses")) if isinstance(item, dict)]
    if not isinstance(quorum, int) or quorum < 1 or quorum > len(witness_specs):
        findings.append(
            _finding(
                "WITNESS_SET_INVALID",
                "BLOCK",
                "$.quorum",
                "quorum must be an integer between one and the witness count",
            )
        )
        quorum = 1

    expected: dict[str, dict[str, Any]] = {}
    operator_ids: list[str | None] = []
    for index, spec in enumerate(witness_specs):
        witness_id = _text(spec, "witness_id")
        operator_id = _text(spec, "operator_id")
        nonce = _text(spec, "nonce")
        if witness_id is None or operator_id is None or nonce is None:
            findings.append(
                _finding(
                    "WITNESS_SET_INVALID",
                    "BLOCK",
                    f"$.witnesses[{index}]",
                    "witness_id, operator_id, and nonce are required",
                )
            )
            continue
        if witness_id in expected:
            findings.append(
                _finding(
                    "WITNESS_SET_INVALID",
                    "BLOCK",
                    f"$.witnesses[{index}].witness_id",
                    "witness identifiers must be unique",
                )
            )
        expected[witness_id] = spec
        operator_ids.append(operator_id)

    present_operators = [item for item in operator_ids if item is not None]
    if len(present_operators) != len(set(present_operators)):
        findings.append(
            _finding(
                "WITNESS_OPERATOR_NOT_INDEPENDENT",
                "BLOCK",
                "$.witnesses",
                "every witness must declare a distinct operator_id",
            )
        )

    by_witness: dict[str, list[dict[str, Any]]] = defaultdict(list)
    valid_by_witness: dict[str, dict[str, Any]] = {}
    invalid_witnesses: set[str] = set()

    for index, statement in enumerate(statements):
        if not isinstance(statement, dict):
            findings.append(
                _finding(
                    "WITNESS_STATEMENT_TAMPERED",
                    "CHALLENGE",
                    f"$.statements[{index}]",
                    "witness statement must be a JSON object",
                )
            )
            continue
        witness_id = _text(statement, "witness_id")
        if witness_id is None or witness_id not in expected:
            findings.append(
                _finding(
                    "WITNESS_UNKNOWN",
                    "BLOCK",
                    f"$.statements[{index}].witness_id",
                    "statement came from an unknown witness",
                )
            )
            continue
        by_witness[witness_id].append(statement)

    for witness_id, spec in expected.items():
        candidates = by_witness.get(witness_id, [])
        if not candidates:
            continue

        roots = {repr(candidate.get("statement_root")) for candidate in candidates}
        vote_keys: set[str] = set()
        malformed_candidate = False
        for candidate in candidates:
            if not isinstance(candidate.get("graph_roots"), dict):
                continue
            try:
                vote_keys.add(_statement_vote_key(candidate))
            except (TypeError, ValueError):
                malformed_candidate = True
        if malformed_candidate:
            findings.append(
                _finding(
                    "WITNESS_STATEMENT_TAMPERED",
                    "CHALLENGE",
                    f"$.statements.{witness_id}",
                    "witness statement cannot be canonically committed",
                )
            )
            invalid_witnesses.add(witness_id)
            continue
        if len(roots) > 1 or len(vote_keys) > 1:
            findings.append(
                _finding(
                    "WITNESS_EQUIVOCATION",
                    "CHALLENGE",
                    f"$.statements.{witness_id}",
                    "one witness emitted different commitments for the same round",
                )
            )
            invalid_witnesses.add(witness_id)
            continue

        statement = candidates[0]
        valid = True

        if statement.get("profile_id") != STATEMENT_PROFILE:
            findings.append(
                _finding(
                    "WITNESS_STATEMENT_TAMPERED",
                    "CHALLENGE",
                    f"$.statements.{witness_id}.profile_id",
                    "unsupported witness-statement profile",
                )
            )
            valid = False

        if statement.get("round_id") != round_id:
            findings.append(
                _finding(
                    "WITNESS_ROUND_REPLAY",
                    "CHALLENGE",
                    f"$.statements.{witness_id}.round_id",
                    "statement belongs to another witness round",
                )
            )
            valid = False

        if statement.get("operator_id") != spec.get("operator_id"):
            findings.append(
                _finding(
                    "WITNESS_OPERATOR_NOT_INDEPENDENT",
                    "BLOCK",
                    f"$.statements.{witness_id}.operator_id",
                    "statement operator does not match witness configuration",
                )
            )
            valid = False

        if statement.get("nonce") != spec.get("nonce"):
            findings.append(
                _finding(
                    "WITNESS_ROUND_REPLAY",
                    "CHALLENGE",
                    f"$.statements.{witness_id}.nonce",
                    "statement nonce does not match the current round",
                )
            )
            valid = False

        if expected_source_digest and statement.get("source_digest") != expected_source_digest:
            findings.append(
                _finding(
                    "WITNESS_SOURCE_MISMATCH",
                    "CHALLENGE",
                    f"$.statements.{witness_id}.source_digest",
                    "statement was built from different source bytes",
                )
            )
            valid = False

        declared_root = statement.get("statement_root")
        try:
            computed_root = compute_statement_root(statement)
        except (TypeError, ValueError) as exc:
            findings.append(
                _finding(
                    "WITNESS_STATEMENT_TAMPERED",
                    "CHALLENGE",
                    f"$.statements.{witness_id}",
                    str(exc),
                )
            )
            valid = False
        else:
            if declared_root != computed_root:
                findings.append(
                    _finding(
                        "WITNESS_STATEMENT_TAMPERED",
                        "CHALLENGE",
                        f"$.statements.{witness_id}.statement_root",
                        "statement root does not match statement bytes",
                    )
                )
                valid = False

        graph_roots = statement.get("graph_roots")
        if not isinstance(graph_roots, dict) or set(graph_roots) != set(REQUIRED_GRAPHS):
            findings.append(
                _finding(
                    "WITNESS_GRAPH_COVERAGE_INCOMPLETE",
                    "BLOCK",
                    f"$.statements.{witness_id}.graph_roots",
                    "statement must commit exactly the six required graphs",
                )
            )
            valid = False
        elif any(not isinstance(graph_roots[name], str) for name in REQUIRED_GRAPHS):
            findings.append(
                _finding(
                    "WITNESS_GRAPH_COVERAGE_INCOMPLETE",
                    "BLOCK",
                    f"$.statements.{witness_id}.graph_roots",
                    "every required graph root must be a string",
                )
            )
            valid = False

        if valid:
            valid_by_witness[witness_id] = statement
        else:
            invalid_witnesses.add(witness_id)

    votes: dict[str, list[str]] = defaultdict(list)
    vote_statements: dict[str, dict[str, Any]] = {}
    non_accepting: list[str] = []
    for witness_id, statement in valid_by_witness.items():
        if statement.get("decision") != "ACCEPT":
            non_accepting.append(witness_id)
            continue
        vote_key = _statement_vote_key(statement)
        votes[vote_key].append(witness_id)
        vote_statements[vote_key] = statement

    winning_key: str | None = None
    agreeing: list[str] = []
    if votes:
        winning_key, agreeing = sorted(
            votes.items(), key=lambda item: (-len(item[1]), item[0])
        )[0]
        agreeing = sorted(agreeing)

    if winning_key is None or len(agreeing) < quorum:
        if len(valid_by_witness) < quorum:
            code = "WITNESS_PROCESS_FAILED" if process_failure_details else "WITNESS_MISSING"
            message = (
                "witness process failures left fewer valid statements than the configured quorum"
                if process_failure_details
                else "fewer valid witness statements than the configured quorum"
            )
            findings.append(_finding(code, "HOLD", "$.statements", message))
        else:
            findings.append(
                _finding(
                    "WITNESS_QUORUM_NOT_REACHED",
                    "BLOCK",
                    "$.statements",
                    "no exact graph-root vector reached the configured quorum",
                )
            )

    winning_statement = vote_statements.get(winning_key) if winning_key else None
    dissenting = sorted(
        witness_id
        for witness_id in valid_by_witness
        if witness_id not in set(agreeing)
    )

    findings = _sort_findings(findings)
    primary = findings[0] if findings else None
    decision = primary["decision"] if primary else "ACCEPT"

    consensus_payload = None
    consensus_root = None
    if winning_statement is not None and len(agreeing) >= quorum:
        consensus_payload = {
            "profile_id": PROFILE,
            "round_id": round_id,
            "quorum": quorum,
            "agreeing_witnesses": agreeing,
            "source_digest": winning_statement.get("source_digest"),
            "graph_set_id": winning_statement.get("graph_set_id"),
            "poci_envelope_id": winning_statement.get("poci_envelope_id"),
            "graph_roots": winning_statement.get("graph_roots"),
            "transition_cells_root": winning_statement.get("transition_cells_root"),
            "computed_multigraph_root": winning_statement.get("computed_multigraph_root"),
        }
        consensus_root = _digest(CONSENSUS_DOMAIN, consensus_payload)

    statement_summaries = []
    for statement in statements:
        if not isinstance(statement, dict):
            continue
        try:
            vote_key = (
                _statement_vote_key(statement)
                if isinstance(statement.get("graph_roots"), dict)
                else None
            )
        except (TypeError, ValueError):
            vote_key = None
        statement_summaries.append(
            {
                "witness_id": statement.get("witness_id"),
                "operator_id": statement.get("operator_id"),
                "decision": statement.get("decision"),
                "statement_root": statement.get("statement_root"),
                "vote_key": vote_key,
            }
        )

    return {
        "profile_id": PROFILE,
        "round_id": round_id,
        "decision": decision,
        "primary_reason_code": primary["code"] if primary else None,
        "reason_codes": sorted({item["code"] for item in findings}),
        "findings": findings,
        "quorum": quorum,
        "configured_witness_count": len(expected),
        "valid_statement_count": len(valid_by_witness),
        "agreeing_witnesses": agreeing,
        "dissenting_witnesses": dissenting,
        "invalid_witnesses": sorted(invalid_witnesses),
        "non_accepting_witnesses": sorted(non_accepting),
        "process_failures": process_failure_details,
        "statement_summaries": sorted(
            statement_summaries, key=lambda item: str(item.get("witness_id"))
        ),
        "consensus": consensus_payload,
        "consensus_root": consensus_root,
        "honest_limitations": [
            "process isolation is demonstrated inside one CI runner",
            "statement_root is a hash commitment, not an identity signature",
            "operator_id uniqueness is declared and checked, not externally proven",
        ],
        "valid": decision == "ACCEPT",
    }


def run_witness_processes(
    config: dict[str, Any],
    config_path: Path,
    statements_dir: Path,
) -> tuple[list[dict[str, Any]], str | None, list[dict[str, str]]]:
    raw_source_path = _text(config, "source_path")
    if raw_source_path is None:
        return (
            [],
            None,
            [
                _finding(
                    "WITNESS_SET_INVALID",
                    "BLOCK",
                    "$.source_path",
                    "source_path is required",
                )
            ],
        )

    source_path = (config_path.parent / raw_source_path).resolve()
    try:
        source = load_json(source_path)
        source_digest = compute_source_digest(source)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return (
            [],
            None,
            [
                _finding(
                    "WITNESS_PROCESS_FAILED",
                    "BLOCK",
                    "$.source_path",
                    str(exc),
                )
            ],
        )

    statements_dir.mkdir(parents=True, exist_ok=True)
    runner = Path(__file__).with_name("run_poci_multigraph_witness.py").resolve()
    statements: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for index, spec in enumerate(_list(config.get("witnesses"))):
        if not isinstance(spec, dict):
            failures.append(
                _finding(
                    "WITNESS_SET_INVALID",
                    "BLOCK",
                    f"$.witnesses[{index}]",
                    "witness configuration must be an object",
                )
            )
            continue
        witness_id = _text(spec, "witness_id")
        operator_id = _text(spec, "operator_id")
        nonce = _text(spec, "nonce")
        round_id = _text(config, "round_id")
        if None in (witness_id, operator_id, nonce, round_id):
            failures.append(
                _finding(
                    "WITNESS_SET_INVALID",
                    "BLOCK",
                    f"$.witnesses[{index}]",
                    "witness configuration is incomplete",
                )
            )
            continue

        output_path = statements_dir / f"{witness_id}.json"
        command = [
            sys.executable,
            str(runner),
            str(source_path),
            "--round-id",
            round_id,
            "--witness-id",
            witness_id,
            "--operator-id",
            operator_id,
            "--nonce",
            nonce,
            "--pretty",
            "--output",
            str(output_path),
            "--allow-non-accept",
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        if completed.returncode != 0:
            failures.append(
                _finding(
                    "WITNESS_PROCESS_FAILED",
                    "BLOCK",
                    f"$.witnesses[{index}]",
                    completed.stderr.strip()
                    or f"witness process exited with {completed.returncode}",
                )
            )
            continue
        try:
            statements.append(load_json(output_path))
        except (OSError, ValueError) as exc:
            failures.append(
                _finding(
                    "WITNESS_PROCESS_FAILED",
                    "BLOCK",
                    f"$.witnesses[{index}]",
                    str(exc),
                )
            )

    return statements, source_digest, failures


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run isolated PoCI multi-graph witnesses and verify quorum"
    )
    parser.add_argument("config", type=Path)
    parser.add_argument("--statements-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--allow-non-accept", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config_path = args.config.resolve()
        config = load_json(config_path)
        statements_dir = (
            args.statements_dir.resolve()
            if args.statements_dir
            else config_path.parent / ".witness-statements"
        )
        statements, source_digest, failures = run_witness_processes(
            config, config_path, statements_dir
        )
        report = verify_quorum(
            config,
            statements,
            expected_source_digest=source_digest,
            process_failures=failures,
        )
        code = EXIT_CODE[report["decision"]]
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        report = {
            "profile_id": PROFILE,
            "decision": "BLOCK",
            "primary_reason_code": "WITNESS_PROCESS_FAILED",
            "reason_codes": ["WITNESS_PROCESS_FAILED"],
            "findings": [
                _finding("WITNESS_PROCESS_FAILED", "BLOCK", "$", str(exc))
            ],
            "valid": False,
        }
        code = 1

    text = (
        json.dumps(report, indent=2, ensure_ascii=False)
        if args.pretty
        else json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    ) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)

    if args.allow_non_accept:
        return 0
    return code


if __name__ == "__main__":
    raise SystemExit(main())
