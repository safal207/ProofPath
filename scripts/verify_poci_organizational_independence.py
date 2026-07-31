#!/usr/bin/env python3
"""Evaluate whether a PoCI federation has independent organizational governance."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

POLICY_PROFILE = "proofpath.poci.organizational-independence-policy.v0.1"
DOMAINS_PROFILE = "proofpath.poci.governance-domains.v0.1"
REPORT_PROFILE = "proofpath.poci.organizational-independence-report.v0.1"
CHALLENGE_PROFILE = "proofpath.poci.external-operator-challenge.v0.1"

REPORT_DOMAIN = b"proofpath:poci:organizational-independence:v0.1:report\n"
CHALLENGE_DOMAIN = b"proofpath:poci:organizational-independence:v0.1:challenge\n"

REQUIRED_GRAPHS = (
    "causal",
    "intent",
    "authority",
    "state_transition",
    "evidence",
    "time_continuity",
)

DECISION_RANK = {"ACCEPT": 0, "HOLD": 1, "BLOCK": 2, "CHALLENGE": 3}
EXIT_CODE = {"ACCEPT": 0, "HOLD": 2, "BLOCK": 3, "CHALLENGE": 4}
PRIORITY = {
    "GOVERNANCE_POLICY_INVALID": 10,
    "GOVERNANCE_DOMAINS_INVALID": 20,
    "GOVERNANCE_DOMAIN_DUPLICATE": 30,
    "GOVERNANCE_REPOSITORY_DUPLICATE": 40,
    "GOVERNANCE_WORKFLOW_DUPLICATE": 50,
    "GOVERNANCE_OWNER_REPOSITORY_MISMATCH": 60,
    "GOVERNANCE_ATTESTATION_UNVERIFIED": 70,
    "GOVERNANCE_GRAPH_COVERAGE_INCOMPLETE": 80,
    "GOVERNANCE_CONSENSUS_MISMATCH": 100,
    "GOVERNANCE_FALSE_INDEPENDENCE_CLAIM": 110,
    "GOVERNANCE_DOMAIN_COUNT_INSUFFICIENT": 200,
    "GOVERNANCE_OWNER_DIVERSITY_INSUFFICIENT": 210,
    "GOVERNANCE_EXTERNAL_OWNER_MISSING": 220,
    "GOVERNANCE_WORKFLOW_DIVERSITY_INSUFFICIENT": 230,
}


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize evidence deterministically and reject floats."""

    def normalize(item: Any) -> Any:
        if isinstance(item, float):
            raise ValueError("floats are not allowed in canonical governance evidence")
        if isinstance(item, dict):
            return {key: normalize(item[key]) for key in sorted(item)}
        if isinstance(item, list):
            return [normalize(value) for value in item]
        if item is None or isinstance(item, (str, int, bool)):
            return item
        raise TypeError(f"unsupported canonical value: {type(item).__name__}")

    return json.dumps(
        normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def digest(domain: bytes, value: Any) -> str:
    return "sha256:" + hashlib.sha256(domain + canonical_json_bytes(value)).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    """Load strict JSON and reject duplicate keys."""

    def reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicate,
    )
    if not isinstance(value, dict):
        raise ValueError("top-level JSON value must be an object")
    return value


def _finding(code: str, decision: str, path: str, message: str) -> dict[str, str]:
    return {"code": code, "decision": decision, "path": path, "message": message}


def _sort_findings(findings: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[tuple[str, str, str], dict[str, str]] = {}
    for finding in findings:
        unique[(finding["code"], finding["path"], finding["message"])] = finding
    return sorted(
        unique.values(),
        key=lambda finding: (
            -DECISION_RANK[finding["decision"]],
            PRIORITY.get(finding["code"], 500),
            finding["code"],
            finding["path"],
        ),
    )


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


def consensus_projection(value: dict[str, Any]) -> dict[str, Any]:
    """Return only the consensus fields that every admitted domain must match."""

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


def build_challenge(
    policy: dict[str, Any],
    *,
    current_domain_count: int,
    current_owner_count: int,
    current_external_owner_count: int,
    current_workflow_count: int,
) -> dict[str, Any]:
    """Build a deterministic handoff package for a genuinely external operator."""

    expected = policy.get("expected")
    if not isinstance(expected, dict):
        expected = {}

    challenge: dict[str, Any] = {
        "profile_id": CHALLENGE_PROFILE,
        "challenge_version": "0.1",
        "producer_owner": policy.get("producer_owner"),
        "status": "AWAITING_INDEPENDENT_OPERATOR",
        "current": {
            "domain_count": current_domain_count,
            "distinct_owner_count": current_owner_count,
            "external_owner_count": current_external_owner_count,
            "distinct_workflow_count": current_workflow_count,
        },
        "required": {
            "minimum_domains": policy.get("minimum_domains"),
            "minimum_distinct_owners": policy.get("minimum_distinct_owners"),
            "minimum_external_owners": policy.get("minimum_external_owners"),
            "minimum_distinct_workflows": policy.get("minimum_distinct_workflows"),
            "repository_owner_must_differ_from": policy.get("producer_owner"),
            "keyless_attestation_required": policy.get("require_attestation_verified"),
            "exact_consensus_required": policy.get("require_exact_consensus"),
        },
        "expected_consensus": consensus_projection(expected),
        "response_contract": {
            "profile_id": "proofpath.poci.external-operator-response.v0.1",
            "required_fields": [
                "domain_id",
                "repository",
                "owner",
                "workflow",
                "attestation_verified",
                "attestation_subject_digest",
                "attestation_verification_digest",
                "consensus",
            ],
            "verification_steps": [
                "verify the producer keyless attestation",
                "recompute the six graph roots independently",
                "compare every transition coordinate and the multi-graph root",
                "emit the response from a repository owned by another owner or organization",
                "keyless-attest the exact response bytes",
            ],
        },
        "challenge_root": None,
    }
    challenge["challenge_root"] = digest(CHALLENGE_DOMAIN, challenge)
    return challenge


def verify(
    policy: dict[str, Any],
    domains_document: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    findings: list[dict[str, str]] = []

    if policy.get("profile_id") != POLICY_PROFILE:
        findings.append(
            _finding(
                "GOVERNANCE_POLICY_INVALID",
                "BLOCK",
                "$.policy.profile_id",
                "unsupported organizational-independence policy profile",
            )
        )

    if domains_document.get("profile_id") != DOMAINS_PROFILE:
        findings.append(
            _finding(
                "GOVERNANCE_DOMAINS_INVALID",
                "BLOCK",
                "$.domains.profile_id",
                "unsupported governance-domains profile",
            )
        )

    producer_owner = _text(policy.get("producer_owner"))
    minimum_domains = _positive_int(policy.get("minimum_domains"))
    minimum_owners = _positive_int(policy.get("minimum_distinct_owners"))
    minimum_external_owners = _positive_int(policy.get("minimum_external_owners"))
    minimum_workflows = _positive_int(policy.get("minimum_distinct_workflows"))
    require_attestation = policy.get("require_attestation_verified")
    require_exact_consensus = policy.get("require_exact_consensus")
    expected = policy.get("expected")

    if (
        producer_owner is None
        or minimum_domains is None
        or minimum_owners is None
        or minimum_external_owners is None
        or minimum_workflows is None
        or not isinstance(require_attestation, bool)
        or not isinstance(require_exact_consensus, bool)
        or not isinstance(expected, dict)
    ):
        findings.append(
            _finding(
                "GOVERNANCE_POLICY_INVALID",
                "BLOCK",
                "$.policy",
                "policy requires an owner, positive thresholds, boolean requirements, and expected consensus",
            )
        )
        expected = {}

    expected_graph_roots = expected.get("graph_roots")
    if not isinstance(expected_graph_roots, dict) or set(expected_graph_roots) != set(REQUIRED_GRAPHS):
        findings.append(
            _finding(
                "GOVERNANCE_GRAPH_COVERAGE_INCOMPLETE",
                "BLOCK",
                "$.policy.expected.graph_roots",
                "expected consensus must commit exactly the six required graph roots",
            )
        )

    raw_domains = domains_document.get("domains")
    if not isinstance(raw_domains, list):
        findings.append(
            _finding(
                "GOVERNANCE_DOMAINS_INVALID",
                "BLOCK",
                "$.domains.domains",
                "domains must be an array",
            )
        )
        raw_domains = []

    valid_domains: list[dict[str, Any]] = []
    domain_ids: set[str] = set()
    repositories: set[str] = set()
    workflows: set[str] = set()
    owners: set[str] = set()
    external_owners: set[str] = set()

    for index, domain in enumerate(raw_domains):
        path = f"$.domains.domains[{index}]"
        if not isinstance(domain, dict):
            findings.append(
                _finding(
                    "GOVERNANCE_DOMAINS_INVALID",
                    "BLOCK",
                    path,
                    "domain entry must be an object",
                )
            )
            continue

        domain_id = _text(domain.get("domain_id"))
        repository = _text(domain.get("repository"))
        owner = _text(domain.get("owner"))
        workflow = _text(domain.get("workflow"))
        role = _text(domain.get("role"))
        consensus = domain.get("consensus")
        attestation_verified = domain.get("attestation_verified")
        claims_independence = domain.get("claims_organizational_independence", False)

        if None in (domain_id, repository, owner, workflow, role) or not isinstance(consensus, dict):
            findings.append(
                _finding(
                    "GOVERNANCE_DOMAINS_INVALID",
                    "BLOCK",
                    path,
                    "domain_id, repository, owner, workflow, role, and consensus are required",
                )
            )
            continue

        if domain_id in domain_ids:
            findings.append(
                _finding(
                    "GOVERNANCE_DOMAIN_DUPLICATE",
                    "BLOCK",
                    f"{path}.domain_id",
                    "domain identifiers must be unique",
                )
            )
        domain_ids.add(domain_id)

        if repository in repositories:
            findings.append(
                _finding(
                    "GOVERNANCE_REPOSITORY_DUPLICATE",
                    "BLOCK",
                    f"{path}.repository",
                    "each governance domain must use a distinct repository",
                )
            )
        repositories.add(repository)

        if workflow in workflows:
            findings.append(
                _finding(
                    "GOVERNANCE_WORKFLOW_DUPLICATE",
                    "BLOCK",
                    f"{path}.workflow",
                    "each governance domain must use a distinct signer workflow",
                )
            )
        workflows.add(workflow)

        repository_owner = repository.split("/", 1)[0] if "/" in repository else None
        if repository_owner != owner:
            findings.append(
                _finding(
                    "GOVERNANCE_OWNER_REPOSITORY_MISMATCH",
                    "BLOCK",
                    f"{path}.owner",
                    "declared owner must match the repository owner",
                )
            )

        if require_attestation is True and attestation_verified is not True:
            findings.append(
                _finding(
                    "GOVERNANCE_ATTESTATION_UNVERIFIED",
                    "BLOCK",
                    f"{path}.attestation_verified",
                    "every admitted governance domain requires a verified keyless attestation",
                )
            )

        graph_roots = consensus.get("graph_roots")
        if not isinstance(graph_roots, dict) or set(graph_roots) != set(REQUIRED_GRAPHS):
            findings.append(
                _finding(
                    "GOVERNANCE_GRAPH_COVERAGE_INCOMPLETE",
                    "BLOCK",
                    f"{path}.consensus.graph_roots",
                    "domain consensus must commit exactly the six required graph roots",
                )
            )

        if require_exact_consensus is True and consensus_projection(consensus) != consensus_projection(expected):
            findings.append(
                _finding(
                    "GOVERNANCE_CONSENSUS_MISMATCH",
                    "CHALLENGE",
                    f"{path}.consensus",
                    "domain consensus differs from the pinned PoCI consensus",
                )
            )

        if claims_independence is True and owner == producer_owner:
            findings.append(
                _finding(
                    "GOVERNANCE_FALSE_INDEPENDENCE_CLAIM",
                    "CHALLENGE",
                    f"{path}.claims_organizational_independence",
                    "a domain owned by the producer owner cannot claim organizational independence",
                )
            )

        owners.add(owner)
        if owner != producer_owner:
            external_owners.add(owner)
        valid_domains.append(domain)

    if minimum_domains is not None and len(valid_domains) < minimum_domains:
        findings.append(
            _finding(
                "GOVERNANCE_DOMAIN_COUNT_INSUFFICIENT",
                "HOLD",
                "$.domains.domains",
                f"{len(valid_domains)} domains available; {minimum_domains} required",
            )
        )

    if minimum_owners is not None and len(owners) < minimum_owners:
        findings.append(
            _finding(
                "GOVERNANCE_OWNER_DIVERSITY_INSUFFICIENT",
                "HOLD",
                "$.domains.domains",
                f"{len(owners)} distinct owners available; {minimum_owners} required",
            )
        )

    if minimum_external_owners is not None and len(external_owners) < minimum_external_owners:
        findings.append(
            _finding(
                "GOVERNANCE_EXTERNAL_OWNER_MISSING",
                "HOLD",
                "$.domains.domains",
                f"{len(external_owners)} external owners available; {minimum_external_owners} required",
            )
        )

    if minimum_workflows is not None and len(workflows) < minimum_workflows:
        findings.append(
            _finding(
                "GOVERNANCE_WORKFLOW_DIVERSITY_INSUFFICIENT",
                "HOLD",
                "$.domains.domains",
                f"{len(workflows)} distinct workflows available; {minimum_workflows} required",
            )
        )

    findings = _sort_findings(findings)
    primary = findings[0] if findings else None
    decision = primary["decision"] if primary else "ACCEPT"

    challenge = None
    if decision == "HOLD":
        challenge = build_challenge(
            policy,
            current_domain_count=len(valid_domains),
            current_owner_count=len(owners),
            current_external_owner_count=len(external_owners),
            current_workflow_count=len(workflows),
        )

    report: dict[str, Any] = {
        "profile_id": REPORT_PROFILE,
        "decision": decision,
        "primary_reason_code": primary["code"] if primary else None,
        "reason_codes": sorted({finding["code"] for finding in findings}),
        "findings": findings,
        "domain_count": len(valid_domains),
        "distinct_repository_count": len(repositories),
        "distinct_workflow_count": len(workflows),
        "distinct_owner_count": len(owners),
        "external_owner_count": len(external_owners),
        "owners": sorted(owners),
        "external_owners": sorted(external_owners),
        "admitted_domain_ids": sorted(
            domain["domain_id"]
            for domain in valid_domains
            if isinstance(domain.get("domain_id"), str)
        ),
        "expected_consensus": consensus_projection(expected),
        "challenge_root": challenge.get("challenge_root") if challenge else None,
        "permitted_next_transition": (
            "ADMIT_ORGANIZATIONAL_QUORUM"
            if decision == "ACCEPT"
            else "AWAIT_EXTERNAL_OPERATOR"
            if decision == "HOLD"
            else "REPAIR_GOVERNANCE_EVIDENCE"
        ),
        "honest_limitations": [
            "repository and workflow separation do not prove different controlling owners",
            "organizational independence requires at least one verified owner outside the producer owner",
            "the challenge bundle grants no merge, execution, or authorization authority",
        ],
        "report_root": None,
        "valid": decision == "ACCEPT",
    }
    report["report_root"] = digest(REPORT_DOMAIN, report)
    return report, challenge


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate PoCI organizational independence and emit an external-operator challenge"
    )
    parser.add_argument("policy", type=Path)
    parser.add_argument("domains", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--challenge-output", type=Path)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--allow-hold", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        report, challenge = verify(load_json(args.policy), load_json(args.domains))
        code = EXIT_CODE[report["decision"]]
    except (OSError, ValueError, TypeError, KeyError) as exc:
        report = {
            "profile_id": REPORT_PROFILE,
            "decision": "BLOCK",
            "primary_reason_code": "GOVERNANCE_DOMAINS_INVALID",
            "reason_codes": ["GOVERNANCE_DOMAINS_INVALID"],
            "findings": [
                _finding("GOVERNANCE_DOMAINS_INVALID", "BLOCK", "$", str(exc))
            ],
            "valid": False,
        }
        challenge = None
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

    if args.challenge_output and challenge is not None:
        args.challenge_output.parent.mkdir(parents=True, exist_ok=True)
        args.challenge_output.write_text(
            json.dumps(challenge, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    if args.allow_hold and report.get("decision") == "HOLD":
        return 0
    return code


if __name__ == "__main__":
    raise SystemExit(main())
