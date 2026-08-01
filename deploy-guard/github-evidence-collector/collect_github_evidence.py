#!/usr/bin/env python3
"""Collect commit-bound GitHub facts for the ProofPath Deploy Evidence Builder."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

COLLECTOR_PROFILE = "proofpath.github.evidence-collector.v0.1"
TRUSTED_FACTS_PROFILE = "proofpath.deploy.evidence-inputs.v0.1"
GOVERNANCE_PROFILE = "proofpath.github.governance-facts.v0.1"
ROLE_MAP_PROFILE = "proofpath.github.approval-role-map.v0.1"
ATTESTATION_PROFILE = "proofpath.github.attestation-result.v0.1"

SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_. /:@+\[\]()-]{1,200}$")
SUPPORTED_API_VERSION = "2022-11-28"
MAX_PAGES = 20


class CollectorError(ValueError):
    """Raised when GitHub evidence cannot be collected without ambiguity."""


def _reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CollectorError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate,
        )
    except (OSError, json.JSONDecodeError, CollectorError) as exc:
        raise CollectorError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CollectorError(f"{path} must contain one JSON object")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    def normalize(item: Any) -> Any:
        if isinstance(item, float):
            raise CollectorError("floats are forbidden in canonical collector evidence")
        if isinstance(item, dict):
            return {key: normalize(item[key]) for key in sorted(item)}
        if isinstance(item, list):
            return [normalize(entry) for entry in item]
        if item is None or isinstance(item, (str, int, bool)):
            return item
        raise CollectorError(f"unsupported canonical type: {type(item).__name__}")

    return json.dumps(
        normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _workspace_path(raw: str, *, name: str, must_exist: bool) -> Path:
    workspace_raw = os.environ.get("GITHUB_WORKSPACE")
    if not workspace_raw:
        raise CollectorError("GITHUB_WORKSPACE is required")
    workspace = Path(workspace_raw).resolve()
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = workspace / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise CollectorError(f"{name} must remain inside GITHUB_WORKSPACE") from exc
    if must_exist and not candidate.is_file():
        raise CollectorError(f"{name} does not exist: {candidate}")
    return candidate


def _required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value or "\x00" in value or "\n" in value or "\r" in value:
        raise CollectorError(f"{name} must be one non-empty line")
    return value


def _optional_env(name: str) -> str:
    value = os.environ.get(name, "")
    if "\x00" in value or "\n" in value or "\r" in value:
        raise CollectorError(f"{name} must be one line")
    return value


def _boolean_env(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name, "")
    if raw == "":
        return default
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise CollectorError(f"{name} must be true or false")


def _positive_int(value: str, *, name: str, allow_zero: bool = False) -> int:
    if not value.isdigit():
        raise CollectorError(f"{name} must be an integer")
    parsed = int(value)
    if parsed < (0 if allow_zero else 1):
        raise CollectorError(f"{name} is out of range")
    return parsed


def _validate_repository(value: str) -> str:
    if not REPOSITORY_RE.fullmatch(value):
        raise CollectorError("repository must use owner/name form")
    return value


def _validate_sha(value: str, *, name: str) -> str:
    if not SHA_RE.fullmatch(value):
        raise CollectorError(f"{name} must be a 40-64 character lowercase hex SHA")
    return value


def _validate_digest(value: str, *, name: str) -> str:
    if not DIGEST_RE.fullmatch(value):
        raise CollectorError(f"{name} must be sha256:<64 lowercase hex>")
    return value


def _validate_text(value: Any, *, name: str) -> str:
    if not isinstance(value, str) or not SAFE_NAME_RE.fullmatch(value):
        raise CollectorError(f"{name} must be a safe non-empty string")
    return value


def _api_base() -> str:
    raw = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise CollectorError("GITHUB_API_URL must be an HTTPS URL")
    if parsed.query or parsed.fragment:
        raise CollectorError("GITHUB_API_URL must not contain a query or fragment")
    if ".." in Path(parsed.path).parts:
        raise CollectorError("GITHUB_API_URL path is invalid")
    return raw


def _fixture_path(endpoint: str) -> Path | None:
    fixture_dir = os.environ.get("PROOFPATH_COLLECTOR_FIXTURE_DIR", "")
    if not fixture_dir:
        return None
    if os.environ.get("GITHUB_ACTIONS") == "true":
        raise CollectorError("API fixtures are forbidden inside GitHub Actions")
    root = _workspace_path(fixture_dir, name="fixture directory", must_exist=False)
    if not root.is_dir():
        raise CollectorError("fixture directory does not exist")
    digest = hashlib.sha256(endpoint.encode("utf-8")).hexdigest()
    candidate = (root / f"{digest}.json").resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise CollectorError("fixture path escaped fixture directory") from exc
    if not candidate.is_file():
        raise CollectorError(f"missing API fixture for {endpoint}")
    return candidate


def _api_get(endpoint: str, *, token: str) -> Any:
    if not endpoint.startswith("/") or "://" in endpoint or "\\" in endpoint:
        raise CollectorError("GitHub API endpoint must be an absolute API path")
    fixture = _fixture_path(endpoint)
    if fixture is not None:
        value = load_json(fixture)
        if set(value) != {"body"}:
            raise CollectorError("API fixture must contain exactly a body field")
        return value["body"]

    base = _api_base()
    url = base + endpoint
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "proofpath-github-evidence-collector/0.1",
            "X-GitHub-Api-Version": SUPPORTED_API_VERSION,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            final = urllib.parse.urlparse(response.geturl())
            expected = urllib.parse.urlparse(base)
            expected_prefix = expected.path.rstrip("/") + "/"
            if (
                final.scheme != expected.scheme
                or final.netloc != expected.netloc
                or not final.path.startswith(expected_prefix)
            ):
                raise CollectorError("GitHub API redirected outside the configured API root")
            payload = response.read(10_000_000)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise CollectorError(f"GitHub API request failed for {endpoint}: {exc}") from exc
    try:
        return json.loads(payload.decode("utf-8"), object_pairs_hook=_reject_duplicate)
    except (UnicodeDecodeError, json.JSONDecodeError, CollectorError) as exc:
        raise CollectorError(f"GitHub API returned invalid JSON for {endpoint}") from exc


def _api_get_pages(
    endpoint: str,
    *,
    token: str,
    array_key: str | None = None,
) -> list[Any]:
    items: list[Any] = []
    separator = "&" if "?" in endpoint else "?"
    for page in range(1, MAX_PAGES + 1):
        value = _api_get(f"{endpoint}{separator}page={page}", token=token)
        page_items = value.get(array_key) if array_key is not None and isinstance(value, dict) else value
        if not isinstance(page_items, list):
            raise CollectorError(f"paginated GitHub API response for {endpoint} is malformed")
        items.extend(page_items)
        if len(page_items) < 100:
            return items
    raise CollectorError(f"GitHub API pagination exceeded {MAX_PAGES} pages")


def _policy_required_checks(policy: dict[str, Any]) -> list[str]:
    value = policy.get("required_checks")
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not SAFE_NAME_RE.fullmatch(item) for item in value
    ):
        raise CollectorError("policy.required_checks must be an array of safe strings")
    if len(value) != len(set(value)):
        raise CollectorError("policy.required_checks must be unique")
    return value


def _load_governance(path: Path) -> dict[str, Any]:
    value = load_json(path)
    if value.get("profile_id") != GOVERNANCE_PROFILE:
        raise CollectorError("unsupported governance-facts profile")
    if set(value) != {"profile_id", "authority", "security", "change_ticket"}:
        raise CollectorError("governance facts contain unsupported fields")
    if not isinstance(value["authority"], dict):
        raise CollectorError("governance authority must be an object")
    security = value["security"]
    if (
        not isinstance(security, dict)
        or set(security) != {"critical_vulnerabilities"}
        or isinstance(security["critical_vulnerabilities"], bool)
        or not isinstance(security["critical_vulnerabilities"], int)
        or security["critical_vulnerabilities"] < 0
    ):
        raise CollectorError("security.critical_vulnerabilities must be a non-negative integer")
    ticket = value["change_ticket"]
    if ticket is not None and not isinstance(ticket, dict):
        raise CollectorError("change_ticket must be an object or null")
    return value


def _load_role_map(path: Path) -> dict[str, str]:
    value = load_json(path)
    if value.get("profile_id") != ROLE_MAP_PROFILE or set(value) != {"profile_id", "actors"}:
        raise CollectorError("unsupported approval-role-map profile")
    actors = value["actors"]
    if not isinstance(actors, dict):
        raise CollectorError("approval-role-map actors must be an object")
    result: dict[str, str] = {}
    for actor, role in actors.items():
        actor_value = _validate_text(actor, name="approval actor").lower()
        role_value = _validate_text(role, name=f"role for {actor_value}")
        if actor_value in result:
            raise CollectorError("approval actors must be unique")
        result[actor_value] = role_value
    return result


def _normalize_workflow(repository: str, run: dict[str, Any]) -> str:
    path = run.get("path")
    if not isinstance(path, str) or not path:
        raise CollectorError("workflow run did not expose a workflow path")
    path = path.split("@", 1)[0]
    if not path.startswith(".github/workflows/") or ".." in Path(path).parts:
        raise CollectorError("workflow run path is not a trusted workflow file")
    return f"{repository}/{path}"


def _collect_artifact(
    repository: str,
    *,
    run_id: int,
    artifact_name: str,
    source_sha: str,
    token: str,
    allow_current_run: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    owner, repo = repository.split("/", 1)
    run = _api_get(f"/repos/{owner}/{repo}/actions/runs/{run_id}", token=token)
    if not isinstance(run, dict):
        raise CollectorError("workflow run response must be an object")
    if run.get("head_sha") != source_sha:
        raise CollectorError("workflow run head_sha does not match source-sha")
    run_repo = run.get("repository")
    if not isinstance(run_repo, dict) or run_repo.get("full_name") != repository:
        raise CollectorError("workflow run repository does not match requested repository")
    current_run_id = os.environ.get("GITHUB_RUN_ID", "")
    is_current_run = current_run_id.isdigit() and int(current_run_id) == run_id
    if run.get("status") == "completed":
        if run.get("conclusion") != "success":
            raise CollectorError("artifact-producing workflow run did not complete successfully")
    elif not (
        allow_current_run
        and is_current_run
        and run.get("status") == "in_progress"
        and run.get("conclusion") is None
    ):
        raise CollectorError(
            "workflow run must be completed successfully, or the current in-progress run must be explicitly allowed"
        )

    encoded_name = urllib.parse.quote(artifact_name, safe="")
    response = _api_get(
        f"/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts?per_page=100&name={encoded_name}",
        token=token,
    )
    if not isinstance(response, dict) or not isinstance(response.get("artifacts"), list):
        raise CollectorError("artifact list response is malformed")
    matches = [
        item for item in response["artifacts"]
        if isinstance(item, dict)
        and item.get("name") == artifact_name
        and item.get("expired") is False
    ]
    if len(matches) != 1:
        raise CollectorError("exactly one non-expired artifact must match artifact-name")
    artifact = matches[0]
    _positive_int(str(artifact.get("id", "")), name="artifact id")
    _validate_digest(artifact.get("digest"), name="artifact digest")
    return run, artifact


def _check_status(check: dict[str, Any]) -> str:
    if check.get("status") != "completed":
        return "pending"
    conclusion = check.get("conclusion")
    if conclusion == "success":
        return "success"
    if conclusion in {
        "failure", "cancelled", "timed_out", "action_required",
        "startup_failure", "stale",
    }:
        return "failure"
    return "pending"


def _collect_checks(
    repository: str,
    *,
    source_sha: str,
    required_names: list[str],
    token: str,
) -> list[dict[str, Any]]:
    if not required_names:
        return []
    owner, repo = repository.split("/", 1)
    check_runs = _api_get_pages(
        f"/repos/{owner}/{repo}/commits/{source_sha}/check-runs?per_page=100&filter=latest",
        token=token,
        array_key="check_runs",
    )
    by_name: dict[str, list[dict[str, Any]]] = {name: [] for name in required_names}
    for item in check_runs:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if name in by_name:
            by_name[name].append(item)

    collected: list[dict[str, Any]] = []
    for name in required_names:
        candidates = by_name[name]
        if not candidates:
            continue
        max_id = max(
            _positive_int(str(item.get("id", "")), name=f"check id for {name}")
            for item in candidates
        )
        latest = [
            item for item in candidates
            if _positive_int(str(item.get("id", "")), name=f"check id for {name}") == max_id
        ]
        if len(latest) != 1:
            raise CollectorError(f"ambiguous latest check run for {name!r}")
        check = latest[0]
        check_suite = check.get("check_suite")
        if isinstance(check_suite, dict):
            head_sha = check_suite.get("head_sha")
            if head_sha is not None and head_sha != source_sha:
                raise CollectorError(f"check run {name!r} is bound to another commit")
        collected.append({
            "name": name,
            "status": _check_status(check),
            "commit_sha": source_sha,
        })
    return collected


def _collect_approvals(
    repository: str,
    *,
    pull_request_number: int | None,
    source_sha: str,
    role_map: dict[str, str],
    token: str,
) -> list[dict[str, Any]]:
    if pull_request_number is None or not role_map:
        return []
    owner, repo = repository.split("/", 1)
    pr = _api_get(
        f"/repos/{owner}/{repo}/pulls/{pull_request_number}",
        token=token,
    )
    if not isinstance(pr, dict):
        raise CollectorError("pull-request response must be an object")
    head = pr.get("head")
    base = pr.get("base")
    if not isinstance(head, dict) or head.get("sha") != source_sha:
        raise CollectorError("pull-request head SHA does not match source-sha")
    if not isinstance(base, dict) or not isinstance(base.get("ref"), str):
        raise CollectorError("pull-request base branch is missing")

    reviews = _api_get_pages(
        f"/repos/{owner}/{repo}/pulls/{pull_request_number}/reviews?per_page=100",
        token=token,
    )

    latest: dict[str, tuple[int, dict[str, Any]]] = {}
    for review in reviews:
        if not isinstance(review, dict):
            continue
        user = review.get("user")
        if not isinstance(user, dict) or not isinstance(user.get("login"), str):
            continue
        actor = user["login"].lower()
        if actor not in role_map:
            continue
        state = review.get("state")
        if state not in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            continue
        review_id = _positive_int(str(review.get("id", "")), name=f"review id for {actor}")
        previous = latest.get(actor)
        if previous is None or review_id > previous[0]:
            latest[actor] = (review_id, review)

    approvals: list[dict[str, Any]] = []
    for actor in sorted(latest):
        review = latest[actor][1]
        if review.get("state") != "APPROVED":
            continue
        if review.get("commit_id") != source_sha:
            continue
        approvals.append({
            "actor": actor,
            "role": role_map[actor],
            "approved": True,
            "commit_sha": source_sha,
        })
    return approvals


def _load_attestation(
    raw_path: str,
    *,
    source_sha: str,
    artifact_digest: str,
    workflow: str,
) -> dict[str, Any]:
    if not raw_path:
        return {
            "attestation_verified": False,
            "runner_environment": "unknown",
            "source_sha": source_sha,
            "signer_sha": source_sha,
        }
    path = _workspace_path(raw_path, name="attestation result", must_exist=True)
    value = load_json(path)
    required = {
        "profile_id", "verified", "source_sha", "artifact_digest",
        "workflow", "signer_sha", "runner_environment",
    }
    if set(value) != required or value.get("profile_id") != ATTESTATION_PROFILE:
        raise CollectorError("unsupported attestation-result profile")
    if value.get("source_sha") != source_sha:
        raise CollectorError("attestation result source_sha does not match source-sha")
    if value.get("artifact_digest") != artifact_digest:
        raise CollectorError("attestation result artifact_digest does not match collected artifact")
    if value.get("workflow") != workflow:
        raise CollectorError("attestation result workflow does not match artifact-producing workflow")
    if not isinstance(value.get("verified"), bool):
        raise CollectorError("attestation result verified must be a boolean")
    signer_sha = _validate_sha(value.get("signer_sha"), name="attestation signer_sha")
    runner = value.get("runner_environment")
    if runner not in {"github-hosted", "self-hosted", "unknown"}:
        raise CollectorError("attestation runner_environment is unsupported")
    return {
        "attestation_verified": value["verified"],
        "runner_environment": runner,
        "source_sha": source_sha,
        "signer_sha": signer_sha,
    }


def _write_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    if "\n" in value or "\r" in value or "\x00" in value:
        raise CollectorError(f"output {name} is not one line")
    with open(path, "a", encoding="utf-8") as stream:
        stream.write(f"{name}={value}\n")


def _write_summary(lines: Iterable[str]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")


def collect() -> tuple[dict[str, Any], dict[str, str]]:
    token = _required_env("PROOFPATH_GITHUB_TOKEN")
    repository = _validate_repository(
        _optional_env("PROOFPATH_REPOSITORY") or _required_env("GITHUB_REPOSITORY")
    )
    source_sha = _validate_sha(_required_env("PROOFPATH_SOURCE_SHA"), name="source-sha")
    run_id = _positive_int(_required_env("PROOFPATH_RUN_ID"), name="run-id")
    artifact_name = _validate_text(
        _required_env("PROOFPATH_ARTIFACT_NAME"), name="artifact-name"
    )
    allow_current_run = _boolean_env("PROOFPATH_ALLOW_CURRENT_RUN")
    pr_raw = _optional_env("PROOFPATH_PULL_REQUEST_NUMBER")
    pull_request_number = (
        _positive_int(pr_raw, name="pull-request-number") if pr_raw else None
    )

    policy_path = _workspace_path(
        _required_env("PROOFPATH_POLICY"), name="policy", must_exist=True
    )
    governance_path = _workspace_path(
        _required_env("PROOFPATH_GOVERNANCE_FACTS"),
        name="governance facts",
        must_exist=True,
    )
    role_map_path = _workspace_path(
        _required_env("PROOFPATH_APPROVAL_ROLE_MAP"),
        name="approval role map",
        must_exist=True,
    )
    output_path = _workspace_path(
        _optional_env("PROOFPATH_OUTPUT")
        or "proofpath-evidence/github-trusted-facts.json",
        name="output",
        must_exist=False,
    )

    policy = load_json(policy_path)
    required_checks = _policy_required_checks(policy)
    governance = _load_governance(governance_path)
    role_map = _load_role_map(role_map_path)

    run, artifact = _collect_artifact(
        repository,
        run_id=run_id,
        artifact_name=artifact_name,
        source_sha=source_sha,
        token=token,
        allow_current_run=allow_current_run,
    )
    artifact_digest = _validate_digest(artifact.get("digest"), name="artifact digest")
    workflow = _normalize_workflow(repository, run)
    provenance_binding = _load_attestation(
        _optional_env("PROOFPATH_ATTESTATION_RESULT"),
        source_sha=source_sha,
        artifact_digest=artifact_digest,
        workflow=workflow,
    )

    checks = _collect_checks(
        repository,
        source_sha=source_sha,
        required_names=required_checks,
        token=token,
    )
    approvals = _collect_approvals(
        repository,
        pull_request_number=pull_request_number,
        source_sha=source_sha,
        role_map=role_map,
        token=token,
    )

    trusted_facts = {
        "profile_id": TRUSTED_FACTS_PROFILE,
        "authority": governance["authority"],
        "build_provenance": {
            "commit_sha": source_sha,
            "artifact_digest": artifact_digest,
            "attestation_verified": provenance_binding["attestation_verified"],
            "runner_environment": provenance_binding["runner_environment"],
            "workflow": workflow,
            "source_sha": provenance_binding["source_sha"],
            "signer_sha": provenance_binding["signer_sha"],
        },
        "checks": checks,
        "security": governance["security"],
        "approvals": approvals,
        "change_ticket": governance["change_ticket"],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_bytes = json.dumps(
        trusted_facts, indent=2, sort_keys=True, ensure_ascii=False
    ).encode("utf-8") + b"\n"
    output_path.write_bytes(output_bytes)

    collector_record = {
        "profile_id": COLLECTOR_PROFILE,
        "repository": repository,
        "source_sha": source_sha,
        "pull_request_number": pull_request_number,
        "run_id": run_id,
        "artifact_id": artifact["id"],
        "artifact_name": artifact_name,
        "artifact_digest": artifact_digest,
        "workflow": workflow,
        "required_check_count": len(required_checks),
        "collected_check_count": len(checks),
        "mapped_approval_count": len(approvals),
        "allow_current_run": allow_current_run,
        "attestation_result_supplied": bool(_optional_env("PROOFPATH_ATTESTATION_RESULT")),
        "collector_verified_attestation": False,
        "trusted_facts_sha256": hashlib.sha256(output_bytes).hexdigest(),
    }
    collector_root = "sha256:" + hashlib.sha256(
        b"proofpath:github-evidence-collector:v0.1\n"
        + canonical_json_bytes(collector_record)
    ).hexdigest()

    outputs = {
        "trusted-facts-path": str(output_path),
        "collector-root": collector_root,
        "artifact-id": str(artifact["id"]),
        "artifact-digest": artifact_digest,
        "workflow": workflow,
        "source-sha": source_sha,
        "pull-request-number": str(pull_request_number or ""),
        "check-count": str(len(checks)),
        "approval-count": str(len(approvals)),
    }
    return trusted_facts, outputs


def main() -> int:
    try:
        trusted_facts, outputs = collect()
        for name, value in outputs.items():
            _write_output(name, value)
        _write_summary([
            "## ProofPath GitHub Evidence Collector",
            "",
            f"- Source SHA: `{outputs['source-sha']}`",
            f"- Artifact: `{outputs['artifact-id']}` / `{outputs['artifact-digest']}`",
            f"- Workflow: `{outputs['workflow']}`",
            f"- Required checks collected: `{outputs['check-count']}`",
            f"- Mapped approvals collected: `{outputs['approval-count']}`",
            f"- Collector root: `{outputs['collector-root']}`",
            "",
            "The collector binds GitHub API facts. It does not create authority, map business roles automatically, or cryptographically verify attestations.",
        ])
        print(
            "ProofPath GitHub Evidence Collector: "
            f"{outputs['artifact-digest']} / {outputs['collector-root']}"
        )
        return 0
    except (CollectorError, OSError, TypeError, KeyError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
