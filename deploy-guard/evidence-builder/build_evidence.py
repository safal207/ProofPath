#!/usr/bin/env python3
"""Build deterministic ProofPath Deploy Guard evidence from explicit trusted facts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

POLICY_PROFILE = "proofpath.deploy.guard-policy.v0.1"
FACTS_PROFILE = "proofpath.deploy.evidence-inputs.v0.1"
EVIDENCE_PROFILE = "proofpath.deploy.action-evidence.v0.1"
EVIDENCE_DOMAIN = b"proofpath:deploy-guard:v0.1:evidence\n"
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")


class BuildError(ValueError):
    """Raised when evidence inputs are malformed, ambiguous, or inconsistently bound."""


def _reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise BuildError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate,
        )
    except (OSError, json.JSONDecodeError, BuildError) as exc:
        raise BuildError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BuildError(f"{path} must contain one JSON object")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    def normalize(item: Any) -> Any:
        if isinstance(item, float):
            raise BuildError("floats are forbidden in canonical deployment evidence")
        if isinstance(item, dict):
            return {key: normalize(item[key]) for key in sorted(item)}
        if isinstance(item, list):
            return [normalize(entry) for entry in item]
        if item is None or isinstance(item, (str, int, bool)):
            return item
        raise BuildError(f"unsupported canonical type: {type(item).__name__}")

    return json.dumps(
        normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def evidence_root(value: dict[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(EVIDENCE_DOMAIN + canonical_json_bytes(value)).hexdigest()


def _single_line(name: str, value: str | None, *, required: bool = True) -> str:
    if value is None:
        value = ""
    if "\n" in value or "\r" in value or "\0" in value:
        raise BuildError(f"{name} must be a single-line value")
    value = value.strip()
    if required and not value:
        raise BuildError(f"{name} is required")
    return value


def _workspace_path(workspace: Path, raw: str, name: str) -> Path:
    raw = _single_line(name, raw)
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = workspace / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError as exc:
        raise BuildError(f"{name} must remain inside GITHUB_WORKSPACE") from exc
    return resolved


def _timestamp(value: str) -> str:
    if not value:
        parsed = datetime.now(timezone.utc)
    else:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise BuildError("evaluated-at must be timezone-aware ISO-8601") from exc
        if parsed.tzinfo is None:
            raise BuildError("evaluated-at must be timezone-aware ISO-8601")
        parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def _list_of_text(value: Any, name: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise BuildError(f"{name} must be an array")
    if not allow_empty and not value:
        raise BuildError(f"{name} must not be empty")
    if any(not isinstance(item, str) or not item or "\n" in item or "\r" in item for item in value):
        raise BuildError(f"{name} must contain non-empty single-line strings")
    return value


def _validate_facts(
    facts: dict[str, Any],
    *,
    repository: str,
    source_sha: str,
    environment: str,
    artifact_digest: str,
) -> None:
    if facts.get("profile_id") != FACTS_PROFILE:
        raise BuildError("unsupported trusted-facts profile")

    authority = facts.get("authority")
    if not isinstance(authority, dict) or not isinstance(authority.get("active"), bool):
        raise BuildError("trusted-facts.authority requires explicit active boolean")
    _timestamp(_single_line("authority.expires_at", authority.get("expires_at")))
    scope = authority.get("scope")
    if not isinstance(scope, dict):
        raise BuildError("trusted-facts.authority.scope is required")
    _list_of_text(scope.get("repositories"), "authority.scope.repositories", allow_empty=False)
    _list_of_text(scope.get("environments"), "authority.scope.environments", allow_empty=False)
    _list_of_text(scope.get("actions"), "authority.scope.actions", allow_empty=False)

    provenance = facts.get("build_provenance")
    if not isinstance(provenance, dict):
        raise BuildError("trusted-facts.build_provenance is required")
    if provenance.get("commit_sha") != source_sha:
        raise BuildError("build provenance commit does not match source-sha")
    if provenance.get("artifact_digest") != artifact_digest:
        raise BuildError("build provenance artifact does not match artifact-digest")
    if not isinstance(provenance.get("attestation_verified"), bool):
        raise BuildError("build provenance attestation_verified must be boolean")
    _single_line("build_provenance.runner_environment", provenance.get("runner_environment"))
    _single_line("build_provenance.workflow", provenance.get("workflow"))
    for key in ("source_sha", "signer_sha"):
        value = _single_line(f"build_provenance.{key}", provenance.get(key))
        if not SHA_RE.fullmatch(value):
            raise BuildError(f"build_provenance.{key} must be a 40-64 character lowercase hex SHA")

    checks = facts.get("checks")
    if not isinstance(checks, list):
        raise BuildError("trusted-facts.checks must be an array")
    seen_checks: set[str] = set()
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise BuildError(f"checks[{index}] must be an object")
        name = _single_line(f"checks[{index}].name", check.get("name"))
        if name in seen_checks:
            raise BuildError("check names must be unique")
        seen_checks.add(name)
        _single_line(f"checks[{index}].status", check.get("status"))
        if check.get("commit_sha") != source_sha:
            raise BuildError(f"checks[{index}] commit does not match source-sha")

    security = facts.get("security")
    if not isinstance(security, dict):
        raise BuildError("trusted-facts.security is required")
    critical = security.get("critical_vulnerabilities")
    if isinstance(critical, bool) or not isinstance(critical, int) or critical < 0:
        raise BuildError("security.critical_vulnerabilities must be a non-negative integer")

    approvals = facts.get("approvals")
    if not isinstance(approvals, list):
        raise BuildError("trusted-facts.approvals must be an array")
    seen_actors: set[str] = set()
    for index, approval in enumerate(approvals):
        if not isinstance(approval, dict):
            raise BuildError(f"approvals[{index}] must be an object")
        actor = _single_line(f"approvals[{index}].actor", approval.get("actor"))
        _single_line(f"approvals[{index}].role", approval.get("role"))
        if actor in seen_actors:
            raise BuildError("approval actors must be unique")
        seen_actors.add(actor)
        if not isinstance(approval.get("approved"), bool):
            raise BuildError(f"approvals[{index}].approved must be boolean")
        if approval.get("commit_sha") != source_sha:
            raise BuildError(f"approvals[{index}] commit does not match source-sha")

    ticket = facts.get("change_ticket")
    if ticket is not None:
        if not isinstance(ticket, dict):
            raise BuildError("change_ticket must be an object or null")
        _single_line("change_ticket.id", ticket.get("id"))
        _single_line("change_ticket.status", ticket.get("status"))
        if ticket.get("commit_sha") != source_sha:
            raise BuildError("change ticket commit does not match source-sha")

    # These are policy facts, not builder assertions. Preserve mismatches for Deploy Guard.
    if repository not in scope["repositories"]:
        pass
    if environment not in scope["environments"]:
        pass


def _derive_action_id(repository: str, source_sha: str, environment: str, artifact_digest: str) -> str:
    material = canonical_json_bytes(
        {
            "action_type": "deploy",
            "artifact_digest": artifact_digest,
            "environment": environment,
            "repository": repository,
            "source_sha": source_sha,
        }
    )
    return "deploy-" + hashlib.sha256(material).hexdigest()[:24]


def _write_action_output(name: str, value: str) -> None:
    value = _single_line(name, value)
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def _write_summary(evidence: dict[str, Any], root: str, output: Path) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    lines = [
        "## ProofPath Deploy Evidence Builder",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Action | `{evidence['action_id']}` |",
        f"| Repository | `{evidence['repository']}` |",
        f"| Branch | `{evidence['branch']}` |",
        f"| Commit | `{evidence['commit_sha']}` |",
        f"| Environment | `{evidence['environment']}` |",
        f"| Artifact | `{evidence['artifact_digest']}` |",
        f"| Evidence root | `{root}` |",
        f"| Output | `{output}` |",
        "",
        "> The builder binds explicit workflow facts. It does not verify authority, approvals, checks, tickets, or attestations by itself.",
        "",
    ]
    with Path(summary).open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def build(args: argparse.Namespace) -> tuple[dict[str, Any], str, Path]:
    workspace = Path(args.workspace).resolve()
    policy_path = _workspace_path(workspace, args.policy, "policy")
    facts_path = _workspace_path(workspace, args.trusted_facts, "trusted-facts")
    output_path = _workspace_path(workspace, args.output, "output")

    policy = load_json(policy_path)
    facts = load_json(facts_path)
    if policy.get("profile_id") != POLICY_PROFILE:
        raise BuildError("unsupported deploy-guard policy profile")
    policy_id = _single_line("policy.policy_id", policy.get("policy_id"))
    policy_version = _single_line("policy.policy_version", policy.get("policy_version"))

    repository = _single_line(
        "repository", args.repository or os.environ.get("GITHUB_REPOSITORY")
    )
    branch = _single_line(
        "source-branch", args.source_branch or os.environ.get("GITHUB_REF_NAME")
    )
    source_sha = _single_line(
        "source-sha", args.source_sha or os.environ.get("GITHUB_SHA")
    )
    if not SHA_RE.fullmatch(source_sha):
        raise BuildError("source-sha must be a 40-64 character lowercase hex SHA")
    artifact_digest = _single_line("artifact-digest", args.artifact_digest)
    if not DIGEST_RE.fullmatch(artifact_digest):
        raise BuildError("artifact-digest must match sha256:<64 lowercase hex>")
    environment = _single_line("environment", args.environment)
    agent_id = _single_line("agent-id", args.agent_id)
    evaluated_at = _timestamp(_single_line("evaluated-at", args.evaluated_at, required=False))
    action_id = _single_line("action-id", args.action_id, required=False) or _derive_action_id(
        repository, source_sha, environment, artifact_digest
    )

    _validate_facts(
        facts,
        repository=repository,
        source_sha=source_sha,
        environment=environment,
        artifact_digest=artifact_digest,
    )

    evidence: dict[str, Any] = {
        "profile_id": EVIDENCE_PROFILE,
        "action_id": action_id,
        "action_type": "deploy",
        "agent_id": agent_id,
        "repository": repository,
        "branch": branch,
        "commit_sha": source_sha,
        "environment": environment,
        "artifact_digest": artifact_digest,
        "evaluated_at": evaluated_at,
        "policy": {
            "policy_id": policy_id,
            "policy_version": policy_version,
        },
        "authority": facts["authority"],
        "build_provenance": facts["build_provenance"],
        "checks": facts["checks"],
        "security": facts["security"],
        "approvals": facts["approvals"],
        "change_ticket": facts.get("change_ticket"),
        "execution": {"performed": False},
    }
    root = evidence_root(evidence)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return evidence, root, output_path


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--workspace", default=os.environ.get("GITHUB_WORKSPACE", os.getcwd()))
    value.add_argument("--policy", default=os.environ.get("PROOFPATH_POLICY", ""))
    value.add_argument("--trusted-facts", default=os.environ.get("PROOFPATH_TRUSTED_FACTS", ""))
    value.add_argument("--artifact-digest", default=os.environ.get("PROOFPATH_ARTIFACT_DIGEST", ""))
    value.add_argument("--environment", default=os.environ.get("PROOFPATH_ENVIRONMENT", ""))
    value.add_argument("--agent-id", default=os.environ.get("PROOFPATH_AGENT_ID", ""))
    value.add_argument("--action-id", default=os.environ.get("PROOFPATH_ACTION_ID", ""))
    value.add_argument("--repository", default=os.environ.get("PROOFPATH_REPOSITORY", ""))
    value.add_argument("--source-branch", default=os.environ.get("PROOFPATH_SOURCE_BRANCH", ""))
    value.add_argument("--source-sha", default=os.environ.get("PROOFPATH_SOURCE_SHA", ""))
    value.add_argument("--evaluated-at", default=os.environ.get("PROOFPATH_EVALUATED_AT", ""))
    value.add_argument("--output", default=os.environ.get("PROOFPATH_OUTPUT", "proofpath-evidence/deploy-action-evidence.json"))
    return value


def main() -> int:
    try:
        evidence, root, output = build(parser().parse_args())
        outputs = {
            "evidence-path": str(output),
            "evidence-root": root,
            "action-id": evidence["action_id"],
            "repository": evidence["repository"],
            "source-branch": evidence["branch"],
            "source-sha": evidence["commit_sha"],
            "artifact-digest": evidence["artifact_digest"],
        }
        for name, item in outputs.items():
            _write_action_output(name, item)
        _write_summary(evidence, root, output)
        print(f"ProofPath Deploy Evidence Builder: {evidence['action_id']} / {root}")
        return 0
    except (BuildError, OSError, TypeError, KeyError) as exc:
        print(f"::error title=ProofPath Deploy Evidence Builder::{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
