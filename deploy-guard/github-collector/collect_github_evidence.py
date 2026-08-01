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
from typing import Any

CONFIG_PROFILE = "proofpath.github.evidence-collector-config.v0.1"
FACTS_PROFILE = "proofpath.deploy.evidence-inputs.v0.1"
REPORT_PROFILE = "proofpath.github.evidence-collector-report.v0.1"
REPORT_DOMAIN = b"proofpath:github-evidence-collector:v0.1:report\n"

SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SAFE_TEXT_RE = re.compile(r"^[^\x00\r\n]+$")


class CollectorError(ValueError):
    """Raised when GitHub evidence cannot be collected safely."""


def _reject_duplicate(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CollectorError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_float(value: str) -> None:
    raise CollectorError(f"floats are forbidden in collector configuration: {value}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate,
            parse_float=_reject_float,
        )
    except (OSError, json.JSONDecodeError, CollectorError) as exc:
        raise CollectorError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CollectorError(f"{path} must contain one JSON object")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    def normalize(item: Any) -> Any:
        if isinstance(item, float):
            raise CollectorError("floats are forbidden in canonical collector output")
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


def digest(domain: bytes, value: Any) -> str:
    return "sha256:" + hashlib.sha256(domain + canonical_json_bytes(value)).hexdigest()


def _required_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or not SAFE_TEXT_RE.fullmatch(value):
        raise CollectorError(f"{name} must be a non-empty single-line string")
    return value


def _required_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise CollectorError(f"{name} must be an explicit boolean")
    return value


def _required_nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CollectorError(f"{name} must be a non-negative integer")
    return value


def _workspace_path(raw: str, name: str, *, must_exist: bool = False) -> Path:
    workspace_raw = os.environ.get("GITHUB_WORKSPACE")
    if not workspace_raw:
        raise CollectorError("GITHUB_WORKSPACE is required")
    workspace = Path(workspace_raw).resolve()
    path = Path(raw)
    if not path.is_absolute():
        path = workspace / path
    path = path.resolve()
    try:
        path.relative_to(workspace)
    except ValueError as exc:
        raise CollectorError(f"{name} must remain inside GITHUB_WORKSPACE") from exc
    if must_exist and not path.is_file():
        raise CollectorError(f"{name} does not exist: {path}")
    return path


def _api_base() -> str:
    value = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise CollectorError("GITHUB_API_URL must be an HTTPS origin without embedded credentials")
    return value


def _api_get(path: str, token: str) -> Any:
    url = _api_base() + path
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "proofpath-github-evidence-collector-v0.1",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raise CollectorError(f"GitHub API returned HTTP {exc.code} for {path}") from exc
    except urllib.error.URLError as exc:
        raise CollectorError(f"GitHub API request failed for {path}: {exc.reason}") from exc
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_reject_duplicate)
    except (UnicodeDecodeError, json.JSONDecodeError, CollectorError) as exc:
        raise CollectorError(f"GitHub API returned invalid JSON for {path}") from exc


def _api_list(path: str, key: str, token: str) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for page in range(1, 21):
        separator = "&" if "?" in path else "?"
        value = _api_get(f"{path}{separator}per_page=100&page={page}", token)
        if isinstance(value, dict):
            page_values = value.get(key)
        else:
            page_values = value
        if not isinstance(page_values, list):
            raise CollectorError(f"GitHub API list {path} is missing {key}")
        for entry in page_values:
            if not isinstance(entry, dict):
                raise CollectorError(f"GitHub API list {path} contains a non-object entry")
            values.append(entry)
        if len(page_values) < 100:
            return values
    raise CollectorError(f"GitHub API pagination limit exceeded for {path}")


def _validate_config(config: dict[str, Any], source_sha: str) -> dict[str, Any]:
    if config.get("profile_id") != CONFIG_PROFILE:
        raise CollectorError("unsupported GitHub evidence collector config profile")

    authority = config.get("authority")
    if not isinstance(authority, dict):
        raise CollectorError("config.authority must be an object")

    provenance = config.get("provenance")
    if not isinstance(provenance, dict):
        raise CollectorError("config.provenance must be an object")
    provenance_source_sha = _required_text(provenance.get("source_sha"), "provenance.source_sha")
    signer_sha = _required_text(provenance.get("signer_sha"), "provenance.signer_sha")
    if not SHA_RE.fullmatch(provenance_source_sha) or provenance_source_sha != source_sha:
        raise CollectorError("provenance.source_sha must exactly match source-sha")
    if not SHA_RE.fullmatch(signer_sha):
        raise CollectorError("provenance.signer_sha must be a 40-64 character lowercase hex SHA")
    _required_text(provenance.get("workflow"), "provenance.workflow")
    _required_text(provenance.get("runner_environment"), "provenance.runner_environment")
    _required_bool(provenance.get("attestation_verified"), "provenance.attestation_verified")

    security = config.get("security")
    if not isinstance(security, dict):
        raise CollectorError("config.security must be an object")
    _required_nonnegative_int(
        security.get("critical_vulnerabilities"),
        "security.critical_vulnerabilities",
    )

    ticket = config.get("change_ticket")
    if ticket is not None:
        if not isinstance(ticket, dict):
            raise CollectorError("config.change_ticket must be an object or null")
        ticket_sha = _required_text(ticket.get("commit_sha"), "change_ticket.commit_sha")
        if ticket_sha != source_sha:
            raise CollectorError("change_ticket.commit_sha must exactly match source-sha")

    role_map = config.get("approval_role_map")
    if not isinstance(role_map, dict):
        raise CollectorError("config.approval_role_map must be an object")
    normalized_roles: dict[str, str] = {}
    for actor, role in role_map.items():
        actor_text = _required_text(actor, "approval_role_map actor").lower()
        role_text = _required_text(role, f"approval_role_map[{actor!r}]")
        if actor_text in normalized_roles:
            raise CollectorError("approval_role_map contains duplicate actors by case")
        normalized_roles[actor_text] = role_text

    check_names = config.get("check_names")
    if not isinstance(check_names, list):
        raise CollectorError("config.check_names must be an array")
    normalized_checks: list[str] = []
    for value in check_names:
        name = _required_text(value, "check_names entry")
        if name in normalized_checks:
            raise CollectorError(f"duplicate configured check name: {name}")
        normalized_checks.append(name)

    app_allowlist = config.get("check_app_allowlist", {})
    if not isinstance(app_allowlist, dict):
        raise CollectorError("config.check_app_allowlist must be an object")
    normalized_apps: dict[str, str] = {}
    for name, slug in app_allowlist.items():
        name_text = _required_text(name, "check_app_allowlist check name")
        slug_text = _required_text(slug, f"check_app_allowlist[{name!r}]")
        if name_text not in normalized_checks:
            raise CollectorError("check_app_allowlist may only reference configured check_names")
        normalized_apps[name_text] = slug_text

    return {
        "authority": authority,
        "provenance": provenance,
        "security": security,
        "change_ticket": ticket,
        "approval_role_map": normalized_roles,
        "check_names": normalized_checks,
        "check_app_allowlist": normalized_apps,
    }


def _check_status(check: dict[str, Any]) -> str:
    if check.get("status") != "completed":
        return "pending"
    conclusion = check.get("conclusion")
    if conclusion == "success":
        return "success"
    if conclusion in {"failure", "cancelled", "timed_out"}:
        return str(conclusion)
    return "pending"


def _collect_checks(
    repository: str,
    source_sha: str,
    token: str,
    names: list[str],
    app_allowlist: dict[str, str],
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    encoded_repo = urllib.parse.quote(repository, safe="/")
    raw_checks = _api_list(
        f"/repos/{encoded_repo}/commits/{source_sha}/check-runs",
        "check_runs",
        token,
    )
    checks: list[dict[str, str]] = []
    selection: list[dict[str, Any]] = []
    for name in names:
        candidates = [
            check
            for check in raw_checks
            if check.get("name") == name and check.get("head_sha") == source_sha
        ]
        expected_app = app_allowlist.get(name)
        if expected_app:
            candidates = [
                check
                for check in candidates
                if isinstance(check.get("app"), dict)
                and check["app"].get("slug") == expected_app
            ]
        if not candidates:
            checks.append({"name": name, "status": "pending", "commit_sha": source_sha})
            selection.append({
                "name": name,
                "selected": False,
                "expected_app": expected_app,
                "reason": "NO_MATCHING_CHECK_RUN",
            })
            continue
        selected = max(
            candidates,
            key=lambda check: check.get("id") if isinstance(check.get("id"), int) else -1,
        )
        status = _check_status(selected)
        checks.append({"name": name, "status": status, "commit_sha": source_sha})
        selection.append({
            "name": name,
            "selected": True,
            "check_run_id": selected.get("id"),
            "app_slug": (
                selected.get("app", {}).get("slug")
                if isinstance(selected.get("app"), dict)
                else None
            ),
            "github_status": selected.get("status"),
            "github_conclusion": selected.get("conclusion"),
            "normalized_status": status,
        })
    return checks, selection


def _collect_approvals(
    repository: str,
    pull_request_number: int,
    source_sha: str,
    token: str,
    role_map: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if pull_request_number == 0:
        return [], [{"selected": False, "reason": "PULL_REQUEST_COLLECTION_DISABLED"}]

    encoded_repo = urllib.parse.quote(repository, safe="/")
    pull = _api_get(f"/repos/{encoded_repo}/pulls/{pull_request_number}", token)
    if not isinstance(pull, dict) or not isinstance(pull.get("head"), dict):
        raise CollectorError("GitHub pull request response is malformed")
    if pull["head"].get("sha") != source_sha:
        raise CollectorError("pull request head SHA does not match source-sha")

    reviews = _api_list(
        f"/repos/{encoded_repo}/pulls/{pull_request_number}/reviews",
        "reviews",
        token,
    )
    latest: dict[str, dict[str, Any]] = {}
    for review in reviews:
        user = review.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        if not isinstance(login, str) or not login:
            continue
        key = login.lower()
        current = latest.get(key)
        review_id = review.get("id") if isinstance(review.get("id"), int) else -1
        current_id = current.get("id") if current and isinstance(current.get("id"), int) else -1
        if review_id > current_id:
            latest[key] = review

    approvals: list[dict[str, Any]] = []
    selection: list[dict[str, Any]] = []
    for actor, role in sorted(role_map.items()):
        review = latest.get(actor)
        if review is None:
            selection.append({"actor": actor, "role": role, "selected": False, "reason": "NO_REVIEW"})
            continue
        state = review.get("state")
        commit_id = review.get("commit_id")
        selected = state == "APPROVED" and commit_id == source_sha
        selection.append({
            "actor": actor,
            "role": role,
            "selected": selected,
            "review_id": review.get("id"),
            "state": state,
            "commit_id": commit_id,
            "reason": None if selected else "LATEST_REVIEW_NOT_CURRENT_APPROVAL",
        })
        if selected:
            approvals.append({
                "actor": actor,
                "role": role,
                "approved": True,
                "commit_sha": source_sha,
            })
    return approvals, selection


def _collect_run_and_artifact(
    repository: str,
    source_sha: str,
    run_id: int,
    artifact_name: str,
    token: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    encoded_repo = urllib.parse.quote(repository, safe="/")
    run = _api_get(f"/repos/{encoded_repo}/actions/runs/{run_id}", token)
    if not isinstance(run, dict):
        raise CollectorError("GitHub workflow run response is malformed")
    run_repository = run.get("repository")
    if not isinstance(run_repository, dict) or run_repository.get("full_name") != repository:
        raise CollectorError("artifact workflow run belongs to another repository")
    if run.get("head_sha") != source_sha:
        raise CollectorError("artifact workflow run head SHA does not match source-sha")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise CollectorError("artifact workflow run must be completed successfully")
    source_branch = _required_text(run.get("head_branch"), "workflow_run.head_branch")

    artifacts = _api_list(
        f"/repos/{encoded_repo}/actions/runs/{run_id}/artifacts",
        "artifacts",
        token,
    )
    matches = [artifact for artifact in artifacts if artifact.get("name") == artifact_name]
    if len(matches) != 1:
        raise CollectorError("artifact name must match exactly one artifact in the selected run")
    artifact = matches[0]
    if artifact.get("expired") is not False:
        raise CollectorError("selected artifact is expired or has unknown expiry state")
    artifact_id = artifact.get("id")
    if isinstance(artifact_id, bool) or not isinstance(artifact_id, int) or artifact_id <= 0:
        raise CollectorError("selected artifact has an invalid artifact ID")
    artifact_digest = artifact.get("digest")
    if not isinstance(artifact_digest, str) or not DIGEST_RE.fullmatch(artifact_digest):
        raise CollectorError("selected artifact is missing a valid SHA-256 digest")

    return (
        {
            "run_id": run_id,
            "run_number": run.get("run_number"),
            "workflow_id": run.get("workflow_id"),
            "event": run.get("event"),
            "head_branch": source_branch,
            "head_sha": source_sha,
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "html_url": run.get("html_url"),
        },
        {
            "id": artifact_id,
            "name": artifact_name,
            "digest": artifact_digest,
            "size_in_bytes": artifact.get("size_in_bytes"),
            "created_at": artifact.get("created_at"),
            "expires_at": artifact.get("expires_at"),
        },
    )


def _write_output(name: str, value: str) -> None:
    if not SAFE_TEXT_RE.fullmatch(value):
        raise CollectorError(f"output {name} contains a forbidden newline or NUL")
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def _write_summary(report: dict[str, Any]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    artifact = report["artifact"]
    with Path(summary_path).open("a", encoding="utf-8") as handle:
        handle.write("## ProofPath GitHub Evidence Collector\n\n")
        handle.write(f"- Repository: `{report['repository']}`\n")
        handle.write(f"- Source SHA: `{report['source_sha']}`\n")
        handle.write(f"- Source branch: `{report['source_branch']}`\n")
        handle.write(f"- Artifact: `{artifact['name']}` (`{artifact['digest']}`)\n")
        handle.write(f"- Configured checks: `{report['check_count']}`\n")
        handle.write(f"- Current mapped approvals: `{report['approval_count']}`\n")
        handle.write("- Collector verified authority: `false`\n")
        handle.write("- Collector verified attestation claim: `false`\n")
        handle.write("- Deployment performed: `false`\n")


def main() -> int:
    try:
        token = _required_text(os.environ.get("PROOFPATH_GITHUB_TOKEN"), "github-token")
        repository = os.environ.get("PROOFPATH_REPOSITORY") or os.environ.get("GITHUB_REPOSITORY")
        repository = _required_text(repository, "repository")
        if not REPOSITORY_RE.fullmatch(repository):
            raise CollectorError("repository must use owner/name form")

        source_sha = os.environ.get("PROOFPATH_SOURCE_SHA") or os.environ.get("GITHUB_SHA")
        source_sha = _required_text(source_sha, "source-sha")
        if not SHA_RE.fullmatch(source_sha):
            raise CollectorError("source-sha must be a 40-64 character lowercase hex SHA")

        run_raw = _required_text(os.environ.get("PROOFPATH_ARTIFACT_RUN_ID"), "artifact-run-id")
        if not run_raw.isdigit() or int(run_raw) <= 0:
            raise CollectorError("artifact-run-id must be a positive integer")
        run_id = int(run_raw)
        artifact_name = _required_text(os.environ.get("PROOFPATH_ARTIFACT_NAME"), "artifact-name")

        pr_raw = os.environ.get("PROOFPATH_PULL_REQUEST_NUMBER", "0")
        if not isinstance(pr_raw, str) or not pr_raw.isdigit():
            raise CollectorError("pull-request-number must be a non-negative integer")
        pull_request_number = int(pr_raw)

        config_path = _workspace_path(
            _required_text(os.environ.get("PROOFPATH_COLLECTOR_CONFIG"), "config"),
            "config",
            must_exist=True,
        )
        output_path = _workspace_path(
            _required_text(os.environ.get("PROOFPATH_OUTPUT"), "output"),
            "output",
        )
        report_path = _workspace_path(
            _required_text(os.environ.get("PROOFPATH_REPORT"), "report"),
            "report",
        )
        if output_path == report_path:
            raise CollectorError("output and report paths must differ")

        config = _validate_config(load_json(config_path), source_sha)
        run, artifact = _collect_run_and_artifact(
            repository,
            source_sha,
            run_id,
            artifact_name,
            token,
        )
        checks, check_selection = _collect_checks(
            repository,
            source_sha,
            token,
            config["check_names"],
            config["check_app_allowlist"],
        )
        approvals, approval_selection = _collect_approvals(
            repository,
            pull_request_number,
            source_sha,
            token,
            config["approval_role_map"],
        )

        provenance_config = config["provenance"]
        trusted_facts = {
            "profile_id": FACTS_PROFILE,
            "authority": config["authority"],
            "build_provenance": {
                "commit_sha": source_sha,
                "artifact_digest": artifact["digest"],
                "attestation_verified": provenance_config["attestation_verified"],
                "runner_environment": provenance_config["runner_environment"],
                "workflow": provenance_config["workflow"],
                "source_sha": source_sha,
                "signer_sha": provenance_config["signer_sha"],
            },
            "checks": checks,
            "security": config["security"],
            "approvals": approvals,
            "change_ticket": config["change_ticket"],
        }

        report: dict[str, Any] = {
            "profile_id": REPORT_PROFILE,
            "repository": repository,
            "source_sha": source_sha,
            "source_branch": run["head_branch"],
            "pull_request_number": pull_request_number or None,
            "workflow_run": run,
            "artifact": artifact,
            "check_count": len(checks),
            "approval_count": len(approvals),
            "check_selection": check_selection,
            "approval_selection": approval_selection,
            "collector_live_github_api": True,
            "collector_verified_authority": False,
            "collector_verified_attestation_claim": False,
            "collector_verified_change_ticket": False,
            "deployment_performed": False,
            "limitations": [
                "GitHub checks, reviews, workflow-run identity, and artifact metadata are collected from the GitHub API",
                "approval roles come from explicit reviewed configuration rather than inference from GitHub usernames",
                "authority, vulnerability count, change ticket, and attestation-verification claims remain explicit upstream facts",
                "the collector does not deploy, merge, grant authority, or call a cloud provider",
            ],
            "report_root": None,
        }
        report["report_root"] = digest(REPORT_DOMAIN, report)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(trusted_facts, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        outputs = {
            "trusted-facts-path": str(output_path),
            "collector-report-path": str(report_path),
            "artifact-digest": artifact["digest"],
            "artifact-id": str(artifact["id"]),
            "artifact-run-id": str(run_id),
            "repository": repository,
            "source-branch": run["head_branch"],
            "source-sha": source_sha,
            "check-count": str(len(checks)),
            "approval-count": str(len(approvals)),
        }
        for name, value in outputs.items():
            _write_output(name, value)
        _write_summary(report)
        print(
            "ProofPath GitHub Evidence Collector: "
            f"{repository}@{source_sha} / {artifact['digest']} / "
            f"checks={len(checks)} approvals={len(approvals)}"
        )
        return 0
    except (CollectorError, OSError, KeyError, TypeError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
