#!/usr/bin/env python3
"""Emit one deterministic PoCI multi-graph witness statement.

The statement root is a tamper-evident commitment. It is not an identity
signature and does not prove that operators are organizationally independent.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from build_poci_multigraph import (
    EXIT_CODE,
    build_multigraph,
    canonical_json_bytes,
    load_json,
)

PROFILE = "proofpath.poci.multigraph.witness-statement.v0.1"
SOURCE_DOMAIN = b"proofpath:poci:multigraph:witness:v0.1:source\n"
CELLS_DOMAIN = b"proofpath:poci:multigraph:witness:v0.1:cells\n"
STATEMENT_DOMAIN = b"proofpath:poci:multigraph:witness:v0.1:statement\n"
REQUIRED_GRAPHS = (
    "causal",
    "intent",
    "authority",
    "state_transition",
    "evidence",
    "time_continuity",
)


def _digest(domain: bytes, value: Any) -> str:
    return "sha256:" + hashlib.sha256(domain + canonical_json_bytes(value)).hexdigest()


def compute_source_digest(source: dict[str, Any]) -> str:
    return _digest(SOURCE_DOMAIN, source)


def compute_statement_root(statement: dict[str, Any]) -> str:
    normalized = copy.deepcopy(statement)
    normalized["statement_root"] = None
    return _digest(STATEMENT_DOMAIN, normalized)


def build_witness_statement(
    source: dict[str, Any],
    source_path: Path,
    *,
    round_id: str,
    witness_id: str,
    operator_id: str,
    nonce: str,
) -> dict[str, Any]:
    if not all(isinstance(item, str) and item for item in (round_id, witness_id, operator_id, nonce)):
        raise ValueError("round_id, witness_id, operator_id, and nonce must be non-empty strings")

    report = build_multigraph(source, source_path)
    graphs = report.get("graphs")
    if not isinstance(graphs, dict):
        graphs = {}

    graph_roots: dict[str, str | None] = {}
    for graph_name in REQUIRED_GRAPHS:
        graph = graphs.get(graph_name)
        graph_roots[graph_name] = graph.get("root") if isinstance(graph, dict) else None

    statement: dict[str, Any] = {
        "profile_id": PROFILE,
        "round_id": round_id,
        "witness_id": witness_id,
        "operator_id": operator_id,
        "nonce": nonce,
        "source_digest": compute_source_digest(source),
        "graph_set_id": report.get("graph_set_id"),
        "poci_envelope_id": report.get("poci_envelope_id"),
        "builder_profile_id": report.get("profile_id"),
        "decision": report.get("decision"),
        "primary_reason_code": report.get("primary_reason_code"),
        "reason_codes": report.get("reason_codes", []),
        "graph_roots": graph_roots,
        "transition_cells_root": _digest(CELLS_DOMAIN, report.get("transition_cells", [])),
        "computed_multigraph_root": report.get("computed_multigraph_root"),
        "statement_root": None,
    }
    statement["statement_root"] = compute_statement_root(statement)
    return statement


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit one PoCI multi-graph witness statement")
    parser.add_argument("source", type=Path)
    parser.add_argument("--round-id", required=True)
    parser.add_argument("--witness-id", required=True)
    parser.add_argument("--operator-id", required=True)
    parser.add_argument("--nonce", required=True)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-non-accept", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        source_path = args.source.resolve()
        statement = build_witness_statement(
            load_json(source_path),
            source_path,
            round_id=args.round_id,
            witness_id=args.witness_id,
            operator_id=args.operator_id,
            nonce=args.nonce,
        )
        decision = statement.get("decision")
        code = EXIT_CODE.get(decision, 1)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        statement = {
            "profile_id": PROFILE,
            "round_id": args.round_id,
            "witness_id": args.witness_id,
            "operator_id": args.operator_id,
            "nonce": args.nonce,
            "decision": "BLOCK",
            "primary_reason_code": "WITNESS_INTERNAL_FAIL_CLOSED",
            "reason_codes": ["WITNESS_INTERNAL_FAIL_CLOSED"],
            "error": str(exc),
            "statement_root": None,
        }
        statement["statement_root"] = compute_statement_root(statement)
        code = 1

    text = (
        json.dumps(statement, indent=2, ensure_ascii=False)
        if args.pretty
        else json.dumps(statement, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
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
