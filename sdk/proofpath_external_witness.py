#!/usr/bin/env python3
"""Dependency-free helper for an independently owned PoCI witness operator."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

CHALLENGE_PROFILE = "proofpath.poci.external-operator-challenge.v0.1"
RESPONSE_PROFILE = "proofpath.poci.external-operator-response.v0.1"
MULTIGRAPH_PROFILE = "proofpath.poci.multigraph.v0.1"
SUBMISSION_PROFILE = "proofpath.poci.external-operator-submission.v0.1"
CHALLENGE_DOMAIN = b"proofpath:poci:organizational-independence:v0.1:challenge\n"
RESPONSE_DOMAIN = b"proofpath:poci:external-operator:v0.1:response\n"
SUBMISSION_DOMAIN = b"proofpath:poci:external-operator:v0.1:submission\n"
SOURCE_DOMAIN = b"proofpath:poci:multigraph:witness:v0.1:source\n"
CELLS_DOMAIN = b"proofpath:poci:multigraph:witness:v0.1:cells\n"
REQUIRED_GRAPHS = (
    "causal",
    "intent",
    "authority",
    "state_transition",
    "evidence",
    "time_continuity",
)
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
EXIT_CODE = {"ACCEPT": 0, "HOLD": 2, "BLOCK": 3, "CHALLENGE": 4}


class EvidenceError(ValueError):
    """Raised when external witness evidence is malformed."""


def _reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise EvidenceError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate,
        )
    except (OSError, json.JSONDecodeError, EvidenceError) as exc:
        raise EvidenceError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"{path} must contain one JSON object")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    def normalize(item: Any) -> Any:
        if isinstance(item, float):
            raise EvidenceError("floats are forbidden in canonical evidence")
        if isinstance(item, dict):
            return {key: normalize(item[key]) for key in sorted(item)}
        if isinstance(item, list):
            return [normalize(entry) for entry in item]
        if item is None or isinstance(item, (str, int, bool)):
            return item
        raise EvidenceError(f"unsupported canonical type: {type(item).__name__}")

    return json.dumps(
        normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def digest(domain: bytes, value: Any) -> str:
    return "sha256:" + hashlib.sha256(domain + canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def consensus_projection(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "round_id": value.get("round_id"),
        "consensus_root": value.get("consensus_root"),
        "source_digest": value.get("source_digest"),
        "graph_set_id": value.get("graph_set_id"),
        "poci_envelope_id": value.get("poci_envelope_id"),
        "graph_roots": value.get("graph_roots"),
        "transition_cells_root": value.get("transition_cells_root"),
        "computed_multigraph_root": value.get("computed_multigraph_root"),
    }


def verify_challenge(challenge: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if challenge.get("profile_id") != CHALLENGE_PROFILE:
        errors.append("CHALLENGE_PROFILE_INVALID")
    if challenge.get("status") != "AWAITING_INDEPENDENT_OPERATOR":
        errors.append("CHALLENGE_STATUS_INVALID")
    expected_root = challenge.get("challenge_root")
    if not isinstance(expected_root, str) or not DIGEST_RE.fullmatch(expected_root):
        errors.append("CHALLENGE_ROOT_INVALID")
    else:
        normalized = copy.deepcopy(challenge)
        normalized["challenge_root"] = None
        if digest(CHALLENGE_DOMAIN, normalized) != expected_root:
            errors.append("CHALLENGE_ROOT_MISMATCH")
    expected = challenge.get("expected_consensus")
    if not isinstance(expected, dict):
        errors.append("CHALLENGE_CONSENSUS_INVALID")
    else:
        roots = expected.get("graph_roots")
        if not isinstance(roots, dict) or set(roots) != set(REQUIRED_GRAPHS):
            errors.append("CHALLENGE_GRAPH_COVERAGE_INCOMPLETE")
        elif any(
            not isinstance(root, str) or not DIGEST_RE.fullmatch(root)
            for root in roots.values()
        ):
            errors.append("CHALLENGE_GRAPH_ROOT_INVALID")
    required = challenge.get("required")
    if not isinstance(required, dict):
        errors.append("CHALLENGE_REQUIREMENTS_INVALID")
    elif required.get("repository_owner_must_differ_from") != challenge.get("producer_owner"):
        errors.append("CHALLENGE_OWNER_BOUNDARY_INVALID")
    return sorted(set(errors))


def recomputed_consensus(
    challenge: dict[str, Any],
    report: dict[str, Any],
    source_document: dict[str, Any],
) -> dict[str, Any]:
    graphs = report.get("graphs")
    roots: dict[str, Any] = {}
    if isinstance(graphs, dict):
        for name in REQUIRED_GRAPHS:
            graph = graphs.get(name)
            roots[name] = graph.get("root") if isinstance(graph, dict) else None
    expected = challenge.get("expected_consensus")
    expected = expected if isinstance(expected, dict) else {}
    cells = report.get("transition_cells")
    if not isinstance(cells, list):
        cells = []
    return {
        "round_id": expected.get("round_id"),
        "consensus_root": expected.get("consensus_root"),
        "source_digest": digest(SOURCE_DOMAIN, source_document),
        "graph_set_id": report.get("graph_set_id"),
        "poci_envelope_id": report.get("poci_envelope_id"),
        "graph_roots": roots,
        "transition_cells_root": digest(CELLS_DOMAIN, cells),
        "computed_multigraph_root": report.get("computed_multigraph_root"),
        "transition_cell_count": len(cells),
    }


def create_response(
    challenge: dict[str, Any],
    report: dict[str, Any],
    *,
    domain_id: str,
    repository: str,
    owner: str,
    workflow: str,
    producer_code_sha: str,
    source_path: str,
    source_document: dict[str, Any],
    source_file_digest: str,
    producer_attestation_verified: bool,
    producer_attestation_verification_digest: str,
) -> dict[str, Any]:
    findings: list[str] = list(verify_challenge(challenge))
    producer_owner = challenge.get("producer_owner")
    repository_owner = repository.split("/", 1)[0] if "/" in repository else None
    if repository_owner != owner:
        findings.append("OPERATOR_OWNER_REPOSITORY_MISMATCH")
    if owner == producer_owner:
        findings.append("OPERATOR_OWNER_NOT_INDEPENDENT")
    if not workflow.startswith(repository + "/.github/workflows/"):
        findings.append("OPERATOR_WORKFLOW_REPOSITORY_MISMATCH")
    if not domain_id:
        findings.append("OPERATOR_DOMAIN_ID_MISSING")
    if report.get("profile_id") != MULTIGRAPH_PROFILE:
        findings.append("RECOMPUTED_PROFILE_INVALID")
    if report.get("decision") != "ACCEPT" or report.get("valid") is not True:
        findings.append("RECOMPUTED_REPORT_NOT_ACCEPTED")
    if producer_attestation_verified is not True:
        findings.append("PRODUCER_ATTESTATION_UNVERIFIED")
    if not DIGEST_RE.fullmatch(source_file_digest):
        findings.append("SOURCE_FILE_DIGEST_INVALID")
    if not DIGEST_RE.fullmatch(producer_attestation_verification_digest):
        findings.append("PRODUCER_ATTESTATION_DIGEST_INVALID")
    actual = recomputed_consensus(challenge, report, source_document)
    expected = challenge.get("expected_consensus")
    expected = expected if isinstance(expected, dict) else {}
    actual_projection = consensus_projection(actual)
    if actual_projection != consensus_projection(expected):
        findings.append("EXTERNAL_CONSENSUS_MISMATCH")
    if actual.get("transition_cell_count") != 3:
        findings.append("EXTERNAL_TRANSITION_CELL_COUNT_INVALID")
    findings = sorted(set(findings))
    challenge_codes = {"CHALLENGE_ROOT_MISMATCH", "EXTERNAL_CONSENSUS_MISMATCH"}
    hold_codes = {"OPERATOR_OWNER_NOT_INDEPENDENT"}
    if any(code in challenge_codes for code in findings):
        decision = "CHALLENGE"
    elif findings and set(findings).issubset(hold_codes):
        decision = "HOLD"
    elif findings:
        decision = "BLOCK"
    else:
        decision = "ACCEPT"
    response: dict[str, Any] = {
        "profile_id": RESPONSE_PROFILE,
        "challenge_root": challenge.get("challenge_root"),
        "decision": decision,
        "valid": decision == "ACCEPT",
        "reason_codes": findings,
        "domain_id": domain_id,
        "repository": repository,
        "owner": owner,
        "workflow": workflow,
        "role": "independent-external-witness",
        "claims_organizational_independence": decision == "ACCEPT",
        "producer": {
            "owner": producer_owner,
            "code_sha": producer_code_sha,
            "source_path": source_path,
            "source_file_digest": source_file_digest,
            "attestation_verified": producer_attestation_verified,
            "attestation_verification_digest": producer_attestation_verification_digest,
        },
        "attestation_status": "PENDING_KEYLESS_ATTESTATION",
        "consensus": actual_projection,
        "transition_cell_count": actual.get("transition_cell_count"),
        "response_root": None,
        "permitted_next_transition": (
            "KEYLESS_ATTEST_RESPONSE"
            if decision == "ACCEPT"
            else "USE_DIFFERENT_OWNER_OR_REPAIR_EVIDENCE"
        ),
        "authority_granted": False,
    }
    response["response_root"] = digest(RESPONSE_DOMAIN, response)
    return response


def verify_response_root(response: dict[str, Any]) -> bool:
    expected = response.get("response_root")
    if not isinstance(expected, str) or not DIGEST_RE.fullmatch(expected):
        return False
    normalized = copy.deepcopy(response)
    normalized["response_root"] = None
    return digest(RESPONSE_DOMAIN, normalized) == expected


def finalize_submission(
    response: dict[str, Any],
    *,
    response_subject_digest: str,
    attestation_verification_digest: str,
) -> dict[str, Any]:
    findings: list[str] = []
    if response.get("profile_id") != RESPONSE_PROFILE:
        findings.append("RESPONSE_PROFILE_INVALID")
    if not verify_response_root(response):
        findings.append("RESPONSE_ROOT_MISMATCH")
    if response.get("decision") != "ACCEPT" or response.get("valid") is not True:
        findings.append("RESPONSE_NOT_ACCEPTED")
    if not DIGEST_RE.fullmatch(response_subject_digest):
        findings.append("RESPONSE_SUBJECT_DIGEST_INVALID")
    if not DIGEST_RE.fullmatch(attestation_verification_digest):
        findings.append("RESPONSE_ATTESTATION_DIGEST_INVALID")
    findings = sorted(set(findings))
    submission: dict[str, Any] = {
        "profile_id": SUBMISSION_PROFILE,
        "decision": "ACCEPT" if not findings else "BLOCK",
        "valid": not findings,
        "reason_codes": findings,
        "response_subject_digest": response_subject_digest,
        "response_attestation_claimed_verified": not findings,
        "response_attestation_verification_digest": attestation_verification_digest,
        "response": response,
        "submission_root": None,
        "authority_granted": False,
        "permitted_next_transition": (
            "SUBMIT_TO_PROOFPATH_ADMISSION"
            if not findings
            else "REPAIR_EXTERNAL_SUBMISSION"
        ),
    }
    submission["submission_root"] = digest(SUBMISSION_DOMAIN, submission)
    return submission


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify_parser = subparsers.add_parser("verify-challenge")
    verify_parser.add_argument("challenge", type=Path)
    create_parser = subparsers.add_parser("create-response")
    create_parser.add_argument("challenge", type=Path)
    create_parser.add_argument("report", type=Path)
    create_parser.add_argument("--domain-id", required=True)
    create_parser.add_argument("--repository", required=True)
    create_parser.add_argument("--owner", required=True)
    create_parser.add_argument("--workflow", required=True)
    create_parser.add_argument("--producer-code-sha", required=True)
    create_parser.add_argument("--source-path", required=True)
    create_parser.add_argument("--source-file", type=Path, required=True)
    create_parser.add_argument("--producer-attestation-result", type=Path, required=True)
    create_parser.add_argument("--producer-attestation-verified", action="store_true")
    create_parser.add_argument("--output", type=Path, required=True)
    finalize_parser = subparsers.add_parser("finalize-submission")
    finalize_parser.add_argument("response", type=Path)
    finalize_parser.add_argument("--attestation-result", type=Path, required=True)
    finalize_parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        challenge = load_json(args.challenge) if hasattr(args, "challenge") else None
        if args.command == "verify-challenge":
            errors = verify_challenge(challenge)
            result = {
                "profile_id": "proofpath.poci.external-witness-sdk-check.v0.1",
                "decision": "ACCEPT" if not errors else "BLOCK",
                "reason_codes": errors,
                "challenge_root": challenge.get("challenge_root"),
                "valid": not errors,
            }
            print(json.dumps(result, indent=2) + "\n", end="")
            return 0 if not errors else 3
        if args.command == "finalize-submission":
            response = load_json(args.response)
            submission = finalize_submission(
                response,
                response_subject_digest=sha256_file(args.response),
                attestation_verification_digest=sha256_file(args.attestation_result),
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(submission, indent=2) + "\n", end="")
            return 0 if submission["decision"] == "ACCEPT" else 3
        report = load_json(args.report)
        source_document = load_json(args.source_file)
        response = create_response(
            challenge,
            report,
            domain_id=args.domain_id,
            repository=args.repository,
            owner=args.owner,
            workflow=args.workflow,
            producer_code_sha=args.producer_code_sha,
            source_path=args.source_path,
            source_document=source_document,
            source_file_digest=sha256_file(args.source_file),
            producer_attestation_verified=args.producer_attestation_verified,
            producer_attestation_verification_digest=sha256_file(
                args.producer_attestation_result
            ),
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(response, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(response, indent=2) + "\n", end="")
        return EXIT_CODE[response["decision"]]
    except (EvidenceError, OSError) as exc:
        print(json.dumps({"decision": "BLOCK", "error": str(exc)}, indent=2))
        return 3


if __name__ == "__main__":
    sys.exit(main())
