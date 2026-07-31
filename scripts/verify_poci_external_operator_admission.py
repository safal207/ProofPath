#!/usr/bin/env python3
"""Admit an independently owned, attested PoCI witness submission as data."""

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
SUBMISSION_PROFILE = "proofpath.poci.external-operator-submission.v0.1"
PROVENANCE_PROFILE = "proofpath.poci.external-operator-provenance.v0.1"
DOMAINS_PROFILE = "proofpath.poci.governance-domains.v0.1"
ADMISSION_PROFILE = "proofpath.poci.external-operator-admission.v0.1"

CHALLENGE_DOMAIN = b"proofpath:poci:organizational-independence:v0.1:challenge\n"
RESPONSE_DOMAIN = b"proofpath:poci:external-operator:v0.1:response\n"
SUBMISSION_DOMAIN = b"proofpath:poci:external-operator:v0.1:submission\n"
ADMISSION_DOMAIN = b"proofpath:poci:external-operator:v0.1:admission\n"

REQUIRED_GRAPHS = (
    "causal",
    "intent",
    "authority",
    "state_transition",
    "evidence",
    "time_continuity",
)
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
WORKFLOW_RE = re.compile(r"^[^/]+/[^/]+/\.github/workflows/[^/]+\.ya?ml$")
EXIT_CODE = {"ACCEPT": 0, "BLOCK": 3, "CHALLENGE": 4}

CHALLENGE_CODES = {
    "CHALLENGE_ROOT_MISMATCH",
    "RESPONSE_ROOT_MISMATCH",
    "SUBMISSION_ROOT_MISMATCH",
    "RESPONSE_SUBJECT_DIGEST_MISMATCH",
    "SUBMISSION_RESPONSE_MISMATCH",
    "CONSENSUS_MISMATCH",
    "ATTESTATION_SUBJECT_MISMATCH",
}


class EvidenceError(ValueError):
    """Raised when evidence is malformed."""


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


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and DIGEST_RE.fullmatch(value) is not None


def _is_git_sha(value: Any) -> bool:
    return isinstance(value, str) and GIT_SHA_RE.fullmatch(value) is not None


def _self_root_valid(value: dict[str, Any], field: str, domain: bytes) -> bool:
    expected = value.get(field)
    if not _is_digest(expected):
        return False
    normalized = copy.deepcopy(value)
    normalized[field] = None
    return digest(domain, normalized) == expected


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


def _decision(reason_codes: list[str]) -> str:
    if any(code in CHALLENGE_CODES for code in reason_codes):
        return "CHALLENGE"
    if reason_codes:
        return "BLOCK"
    return "ACCEPT"


def _validate_challenge(challenge: dict[str, Any], reasons: list[str]) -> None:
    if challenge.get("profile_id") != CHALLENGE_PROFILE:
        reasons.append("CHALLENGE_INVALID")
    if challenge.get("status") != "AWAITING_INDEPENDENT_OPERATOR":
        reasons.append("CHALLENGE_INVALID")
    if not _self_root_valid(challenge, "challenge_root", CHALLENGE_DOMAIN):
        reasons.append("CHALLENGE_ROOT_MISMATCH")
    expected = challenge.get("expected_consensus")
    if not isinstance(expected, dict):
        reasons.append("CHALLENGE_INVALID")
        return
    roots = expected.get("graph_roots")
    if not isinstance(roots, dict) or set(roots) != set(REQUIRED_GRAPHS):
        reasons.append("GRAPH_COVERAGE_INCOMPLETE")


def _validate_response(
    challenge: dict[str, Any],
    response: dict[str, Any],
    response_subject_digest: str,
    reasons: list[str],
) -> None:
    if response.get("profile_id") != RESPONSE_PROFILE:
        reasons.append("RESPONSE_INVALID")
    if not _self_root_valid(response, "response_root", RESPONSE_DOMAIN):
        reasons.append("RESPONSE_ROOT_MISMATCH")
    if response.get("challenge_root") != challenge.get("challenge_root"):
        reasons.append("CHALLENGE_ROOT_MISMATCH")
    if response.get("decision") != "ACCEPT" or response.get("valid") is not True:
        reasons.append("RESPONSE_INVALID")
    if response.get("role") != "independent-external-witness":
        reasons.append("RESPONSE_INVALID")
    if response.get("claims_organizational_independence") is not True:
        reasons.append("RESPONSE_INVALID")
    if response.get("authority_granted") is not False:
        reasons.append("AUTHORITY_CLAIM_FORBIDDEN")
    if response.get("attestation_status") != "PENDING_KEYLESS_ATTESTATION":
        reasons.append("RESPONSE_INVALID")
    if response.get("permitted_next_transition") != "KEYLESS_ATTEST_RESPONSE":
        reasons.append("RESPONSE_INVALID")
    if response.get("transition_cell_count") != 3:
        reasons.append("TRANSITION_CELL_COUNT_INVALID")
    consensus = response.get("consensus")
    expected = challenge.get("expected_consensus")
    if not isinstance(consensus, dict) or not isinstance(expected, dict):
        reasons.append("RESPONSE_INVALID")
    else:
        roots = consensus.get("graph_roots")
        if not isinstance(roots, dict) or set(roots) != set(REQUIRED_GRAPHS):
            reasons.append("GRAPH_COVERAGE_INCOMPLETE")
        if consensus_projection(consensus) != consensus_projection(expected):
            reasons.append("CONSENSUS_MISMATCH")
    if not _is_digest(response_subject_digest):
        reasons.append("RESPONSE_SUBJECT_DIGEST_MISMATCH")


def _validate_submission(
    response: dict[str, Any],
    submission: dict[str, Any],
    response_subject_digest: str,
    reasons: list[str],
) -> None:
    if submission.get("profile_id") != SUBMISSION_PROFILE:
        reasons.append("SUBMISSION_INVALID")
    if not _self_root_valid(submission, "submission_root", SUBMISSION_DOMAIN):
        reasons.append("SUBMISSION_ROOT_MISMATCH")
    if submission.get("decision") != "ACCEPT" or submission.get("valid") is not True:
        reasons.append("SUBMISSION_INVALID")
    if submission.get("authority_granted") is not False:
        reasons.append("AUTHORITY_CLAIM_FORBIDDEN")
    if submission.get("permitted_next_transition") != "SUBMIT_TO_PROOFPATH_ADMISSION":
        reasons.append("SUBMISSION_INVALID")
    if submission.get("response_attestation_claimed_verified") is not True:
        reasons.append("SUBMISSION_INVALID")
    if not _is_digest(submission.get("response_attestation_verification_digest")):
        reasons.append("SUBMISSION_INVALID")
    if submission.get("response_subject_digest") != response_subject_digest:
        reasons.append("RESPONSE_SUBJECT_DIGEST_MISMATCH")
    if submission.get("response") != response:
        reasons.append("SUBMISSION_RESPONSE_MISMATCH")


def _validate_provenance(
    challenge: dict[str, Any],
    response: dict[str, Any],
    provenance: dict[str, Any],
    *,
    pr_head_repository: str,
    pr_head_owner: str,
    pr_head_sha: str,
    response_subject_digest: str,
    attestation_verified: bool,
    source_ancestry_verified: bool,
    reasons: list[str],
) -> None:
    if provenance.get("profile_id") != PROVENANCE_PROFILE:
        reasons.append("PROVENANCE_INVALID")
    repository = provenance.get("repository")
    owner = provenance.get("owner")
    workflow = provenance.get("workflow")
    source_sha = provenance.get("source_sha")
    signer_sha = provenance.get("signer_sha")
    if repository != pr_head_repository or repository != response.get("repository"):
        reasons.append("REPOSITORY_IDENTITY_MISMATCH")
    if owner != pr_head_owner or owner != response.get("owner"):
        reasons.append("OWNER_IDENTITY_MISMATCH")
    if not isinstance(repository, str) or "/" not in repository:
        reasons.append("PROVENANCE_INVALID")
    else:
        repository_owner = repository.split("/", 1)[0]
        if repository_owner != owner:
            reasons.append("OWNER_IDENTITY_MISMATCH")
    if owner == challenge.get("producer_owner"):
        reasons.append("OPERATOR_NOT_INDEPENDENT")
    if workflow != response.get("workflow"):
        reasons.append("WORKFLOW_IDENTITY_MISMATCH")
    if (
        not isinstance(workflow, str)
        or WORKFLOW_RE.fullmatch(workflow) is None
        or not isinstance(repository, str)
        or not workflow.startswith(repository + "/.github/workflows/")
    ):
        reasons.append("WORKFLOW_IDENTITY_MISMATCH")
    if not _is_git_sha(source_sha) or not _is_git_sha(signer_sha) or not _is_git_sha(pr_head_sha):
        reasons.append("SOURCE_IDENTITY_INVALID")
    if source_ancestry_verified is not True:
        reasons.append("SOURCE_ANCESTRY_UNVERIFIED")
    if provenance.get("oidc_issuer") != "https://token.actions.githubusercontent.com":
        reasons.append("ATTESTATION_POLICY_INVALID")
    if provenance.get("deny_self_hosted_runners") is not True:
        reasons.append("ATTESTATION_POLICY_INVALID")
    if provenance.get("response_subject_digest") != response_subject_digest:
        reasons.append("ATTESTATION_SUBJECT_MISMATCH")
    if attestation_verified is not True:
        reasons.append("ATTESTATION_UNVERIFIED")


def _validate_domains(
    current_domains: dict[str, Any],
    response: dict[str, Any],
    reasons: list[str],
) -> None:
    if current_domains.get("profile_id") != DOMAINS_PROFILE:
        reasons.append("DOMAINS_INVALID")
        return
    domains = current_domains.get("domains")
    if not isinstance(domains, list):
        reasons.append("DOMAINS_INVALID")
        return
    for domain in domains:
        if not isinstance(domain, dict):
            reasons.append("DOMAINS_INVALID")
            continue
        if domain.get("domain_id") == response.get("domain_id"):
            reasons.append("DOMAIN_DUPLICATE")
        if domain.get("repository") == response.get("repository"):
            reasons.append("REPOSITORY_DUPLICATE")
        if domain.get("workflow") == response.get("workflow"):
            reasons.append("WORKFLOW_DUPLICATE")


def verify_admission(
    challenge: dict[str, Any],
    response: dict[str, Any],
    submission: dict[str, Any],
    provenance: dict[str, Any],
    current_domains: dict[str, Any],
    *,
    pr_head_repository: str,
    pr_head_owner: str,
    pr_head_sha: str,
    response_subject_digest: str,
    attestation_result_digest: str,
    attestation_verified: bool,
    source_ancestry_verified: bool,
) -> dict[str, Any]:
    reasons: list[str] = []
    _validate_challenge(challenge, reasons)
    _validate_response(challenge, response, response_subject_digest, reasons)
    _validate_submission(response, submission, response_subject_digest, reasons)
    _validate_provenance(
        challenge,
        response,
        provenance,
        pr_head_repository=pr_head_repository,
        pr_head_owner=pr_head_owner,
        pr_head_sha=pr_head_sha,
        response_subject_digest=response_subject_digest,
        attestation_verified=attestation_verified,
        source_ancestry_verified=source_ancestry_verified,
        reasons=reasons,
    )
    _validate_domains(current_domains, response, reasons)
    if not _is_digest(attestation_result_digest):
        reasons.append("ATTESTATION_UNVERIFIED")

    reasons = sorted(set(reasons))
    decision = _decision(reasons)

    domain_entry: dict[str, Any] | None = None
    updated_domains: dict[str, Any] | None = None
    if decision == "ACCEPT":
        domain_entry = {
            "domain_id": response["domain_id"],
            "repository": response["repository"],
            "owner": response["owner"],
            "workflow": response["workflow"],
            "role": "independent-external-witness",
            "attestation_verified": True,
            "claims_organizational_independence": True,
            "attestation_subject_digest": response_subject_digest,
            "attestation_verification_digest": attestation_result_digest,
            "attestation_evidence": {
                "source_sha": provenance["source_sha"],
                "signer_sha": provenance["signer_sha"],
                "oidc_issuer": provenance["oidc_issuer"],
                "self_hosted_runners_denied": provenance["deny_self_hosted_runners"],
                "pr_head_sha": pr_head_sha,
                "source_ancestry_verified": source_ancestry_verified,
            },
            "consensus": consensus_projection(response["consensus"]),
        }
        updated_domains = copy.deepcopy(current_domains)
        updated_domains["domains"] = list(updated_domains["domains"]) + [domain_entry]

    report: dict[str, Any] = {
        "profile_id": ADMISSION_PROFILE,
        "decision": decision,
        "valid": decision == "ACCEPT",
        "reason_codes": reasons,
        "challenge_root": challenge.get("challenge_root"),
        "response_subject_digest": response_subject_digest,
        "attestation_result_digest": attestation_result_digest,
        "pr_head": {
            "repository": pr_head_repository,
            "owner": pr_head_owner,
            "sha": pr_head_sha,
        },
        "operator_provenance": {
            "repository": provenance.get("repository"),
            "owner": provenance.get("owner"),
            "workflow": provenance.get("workflow"),
            "source_sha": provenance.get("source_sha"),
            "signer_sha": provenance.get("signer_sha"),
        },
        "domain_entry": domain_entry,
        "updated_domains_document": updated_domains,
        "admission_root": None,
        "authority_granted": False,
        "permitted_next_transition": (
            "EVALUATE_ORGANIZATIONAL_INDEPENDENCE"
            if decision == "ACCEPT"
            else "REJECT_OR_REPAIR_EXTERNAL_SUBMISSION"
        ),
    }
    report["admission_root"] = digest(ADMISSION_DOMAIN, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("challenge", type=Path)
    parser.add_argument("response", type=Path)
    parser.add_argument("submission", type=Path)
    parser.add_argument("provenance", type=Path)
    parser.add_argument("current_domains", type=Path)
    parser.add_argument("--pr-head-repository", required=True)
    parser.add_argument("--pr-head-owner", required=True)
    parser.add_argument("--pr-head-sha", required=True)
    parser.add_argument("--attestation-result", type=Path, required=True)
    parser.add_argument("--attestation-verified", action="store_true")
    parser.add_argument("--source-ancestry-verified", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        report = verify_admission(
            load_json(args.challenge),
            load_json(args.response),
            load_json(args.submission),
            load_json(args.provenance),
            load_json(args.current_domains),
            pr_head_repository=args.pr_head_repository,
            pr_head_owner=args.pr_head_owner,
            pr_head_sha=args.pr_head_sha,
            response_subject_digest=sha256_file(args.response),
            attestation_result_digest=sha256_file(args.attestation_result),
            attestation_verified=args.attestation_verified,
            source_ancestry_verified=args.source_ancestry_verified,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2) + "\n", end="")
        return EXIT_CODE[report["decision"]]
    except (EvidenceError, OSError) as exc:
        print(json.dumps({"decision": "BLOCK", "error": str(exc)}, indent=2))
        return 3


if __name__ == "__main__":
    sys.exit(main())
