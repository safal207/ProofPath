#!/usr/bin/env python3
"""Collect commit-bound GitHub facts for ProofPath Deploy Guard."""

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
    pass


def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CollectorError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def reject_float(value: str) -> None:
    raise CollectorError(f"floats are forbidden: {value}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_float=reject_float,
        )
    except (OSError, json.JSONDecodeError, CollectorError) as exc:
        raise CollectorError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CollectorError(f"{path} must contain one JSON object")
    return value


def canonical_bytes(value: Any) -> bytes:
    def normalize(item: Any) -> Any:
        if isinstance(item, float):
            raise CollectorError("floats are forbidden in canonical output")
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


def root(value: Any) -> str:
    return "sha256:" + hashlib.sha256(REPORT_DOMAIN + canonical_bytes(value)).hexdigest()


def text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value or not SAFE_TEXT_RE.fullmatch(value):
        raise CollectorError(f"{name} must be a non-empty single-line string")
    return value


def workspace_path(raw: str, name: str, *, exists: bool = False) -> Path:
    workspace_raw = os.environ.get("GITHUB_WORKSPACE")
    if not workspace_raw:
        raise CollectorError("GITHUB_WORKSPACE is required")
    workspace = Path(workspace_raw).resolve()
    path = Path(raw)
    path = (workspace / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        path.relative_to(workspace)
    except ValueError as exc:
        raise CollectorError(f"{name} must remain inside GITHUB_WORKSPACE") from exc
    if exists and not path.is_file():
        raise CollectorError(f"{name} does not exist: {path}")
    return path


def api_base() -> str:
    value = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise CollectorError("GITHUB_API_URL must be an HTTPS origin without embedded credentials")
    return value


def api_get(path: str, token: str) -> Any:
    request = urllib.request.Request(
        api_base() + path,
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
        return json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError, CollectorError) as exc:
        raise CollectorError(f"GitHub API returned invalid JSON for {path}") from exc


def api_list(path: str, key: str, token: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for page in range(1, 21):
        separator = "&" if "?" in path else "?"
        value = api_get(f"{path}{separator}per_page=100&page={page}", token)
        entries = value.get(key) if isinstance(value, dict) else value
        if not isinstance(entries, list):
            raise CollectorError(f"GitHub API list {path} is missing {key}")
        if any(not isinstance(entry, dict) for entry in entries):
            raise CollectorError(f"GitHub API list {path} contains a non-object entry")
        result.extend(entries)
        if len(entries) < 100:
            return result
    raise CollectorError(f"GitHub API pagination limit exceeded for {path}")


def validate_config(value: dict[str, Any], source_sha: str) -> dict[str, Any]:
    if value.get("profile_id") != CONFIG_PROFILE:
        raise CollectorError("unsupported collector config profile")
    authority = value.get("authority")
    provenance = value.get("provenance")
    security = value.get("security")
    role_map = value.get("approval_role_map")
    check_names = value.get("check_names")
    ticket = value.get("change_ticket")
    if not isinstance(authority, dict):
        raise CollectorError("config.authority must be an object")
    if not isinstance(provenance, dict):
        raise CollectorError("config.provenance must be an object")
    if not isinstance(security, dict):
        raise CollectorError("config.security must be an object")
    if not isinstance(role_map, dict):
        raise CollectorError("config.approval_role_map must be an object")
    if not isinstance(check_names, list):
        raise CollectorError("config.check_names must be an array")

    provenance_source = text(provenance.get("source_sha"), "provenance.source_sha")
    signer_sha = text(provenance.get("signer_sha"), "provenance.signer_sha")
    if provenance_source != source_sha or not SHA_RE.fullmatch(provenance_source):
        raise CollectorError("provenance.source_sha must exactly match source-sha")
    if not SHA_RE.fullmatch(signer_sha):
        raise CollectorError("provenance.signer_sha must be a lowercase hex SHA")
    for key in ("workflow", "runner_environment"):
        text(provenance.get(key), f"provenance.{key}")
    if not isinstance(provenance.get("attestation_verified"), bool):
        raise CollectorError("provenance.attestation_verified must be an explicit boolean")
    artifact_job_name = text(value.get("artifact_job_name"), "artifact_job_name")

    critical = security.get("critical_vulnerabilities")
    if isinstance(critical, bool) or not isinstance(critical, int) or critical < 0:
        raise CollectorError("security.critical_vulnerabilities must be a non-negative integer")
    if ticket is not None:
        if not isinstance(ticket, dict) or ticket.get("commit_sha") != source_sha:
            raise CollectorError("change_ticket must be null or bind exactly to source-sha")

    roles: dict[str, str] = {}
    for actor, role in role_map.items():
        normalized_actor = text(actor, "approval role actor").lower()
        if normalized_actor in roles:
            raise CollectorError("approval_role_map contains duplicate actors by case")
        roles[normalized_actor] = text(role, f"approval_role_map[{actor!r}]")

    names: list[str] = []
    for item in check_names:
        name = text(item, "check_names entry")
        if name in names:
            raise CollectorError(f"duplicate configured check name: {name}")
        names.append(name)
    app_map = value.get("check_app_allowlist", {})
    if not isinstance(app_map, dict):
        raise CollectorError("check_app_allowlist must be an object")
    apps: dict[str, str] = {}
    for name, slug in app_map.items():
        name = text(name, "check app name")
        if name not in names:
            raise CollectorError("check_app_allowlist may only reference configured checks")
        apps[name] = text(slug, f"check_app_allowlist[{name!r}]")

    return {
        "authority": authority,
        "provenance": provenance,
        "security": security,
        "approval_role_map": roles,
        "check_names": names,
        "check_app_allowlist": apps,
        "change_ticket": ticket,
        "artifact_job_name": artifact_job_name,
    }


def normalize_check(check: dict[str, Any]) -> str:
    if check.get("status") != "completed":
        return "pending"
    conclusion = check.get("conclusion")
    if conclusion == "success":
        return "success"
    if conclusion in {"failure", "cancelled", "timed_out"}:
        return str(conclusion)
    return "pending"


def collect_checks(repo: str, sha: str, token: str, config: dict[str, Any]):
    encoded = urllib.parse.quote(repo, safe="/")
    raw = api_list(f"/repos/{encoded}/commits/{sha}/check-runs", "check_runs", token)
    facts, report = [], []
    for name in config["check_names"]:
        matches = [item for item in raw if item.get("name") == name and item.get("head_sha") == sha]
        expected_app = config["check_app_allowlist"].get(name)
        if expected_app:
            matches = [
                item for item in matches
                if isinstance(item.get("app"), dict) and item["app"].get("slug") == expected_app
            ]
        if not matches:
            facts.append({"name": name, "status": "pending", "commit_sha": sha})
            report.append({"name": name, "selected": False, "reason": "NO_MATCHING_CHECK_RUN"})
            continue
        selected = max(matches, key=lambda item: item.get("id") if isinstance(item.get("id"), int) else -1)
        status = normalize_check(selected)
        facts.append({"name": name, "status": status, "commit_sha": sha})
        report.append({
            "name": name,
            "selected": True,
            "check_run_id": selected.get("id"),
            "app_slug": selected.get("app", {}).get("slug") if isinstance(selected.get("app"), dict) else None,
            "github_status": selected.get("status"),
            "github_conclusion": selected.get("conclusion"),
            "normalized_status": status,
        })
    return facts, report


def collect_approvals(repo: str, pr_number: int, sha: str, token: str, roles: dict[str, str]):
    if pr_number == 0:
        return [], [{"selected": False, "reason": "PULL_REQUEST_COLLECTION_DISABLED"}]
    encoded = urllib.parse.quote(repo, safe="/")
    pull = api_get(f"/repos/{encoded}/pulls/{pr_number}", token)
    if not isinstance(pull, dict) or not isinstance(pull.get("head"), dict):
        raise CollectorError("GitHub pull request response is malformed")
    if pull["head"].get("sha") != sha:
        raise CollectorError("pull request head SHA does not match source-sha")
    reviews = api_list(f"/repos/{encoded}/pulls/{pr_number}/reviews", "reviews", token)
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
    facts, report = [], []
    for actor, role in sorted(roles.items()):
        review = latest.get(actor)
        selected = bool(review and review.get("state") == "APPROVED" and review.get("commit_id") == sha)
        report.append({
            "actor": actor,
            "role": role,
            "selected": selected,
            "review_id": review.get("id") if review else None,
            "state": review.get("state") if review else None,
            "commit_id": review.get("commit_id") if review else None,
            "reason": None if selected else "LATEST_REVIEW_NOT_CURRENT_APPROVAL",
        })
        if selected:
            facts.append({"actor": actor, "role": role, "approved": True, "commit_sha": sha})
    return facts, report


def collect_artifact(repo: str, sha: str, run_id: int, artifact_name: str, job_name: str, token: str):
    encoded = urllib.parse.quote(repo, safe="/")
    run = api_get(f"/repos/{encoded}/actions/runs/{run_id}", token)
    if not isinstance(run, dict) or not isinstance(run.get("repository"), dict):
        raise CollectorError("GitHub workflow run response is malformed")
    if run["repository"].get("full_name") != repo or run.get("head_sha") != sha:
        raise CollectorError("artifact workflow run repository or head SHA does not match")
    if run.get("status") == "completed" and run.get("conclusion") != "success":
        raise CollectorError("completed artifact workflow run must be successful")
    if run.get("status") not in {"queued", "in_progress", "completed"}:
        raise CollectorError("artifact workflow run has an unsupported status")

    jobs = api_list(f"/repos/{encoded}/actions/runs/{run_id}/jobs", "jobs", token)
    producer_matches = [job for job in jobs if job.get("name") == job_name]
    if len(producer_matches) != 1:
        raise CollectorError("artifact_job_name must match exactly one job in the selected run")
    producer = producer_matches[0]
    if producer.get("status") != "completed" or producer.get("conclusion") != "success":
        raise CollectorError("artifact producer job must be completed successfully")

    artifacts = api_list(f"/repos/{encoded}/actions/runs/{run_id}/artifacts", "artifacts", token)
    matches = [artifact for artifact in artifacts if artifact.get("name") == artifact_name]
    if len(matches) != 1:
        raise CollectorError("artifact name must match exactly one artifact in the selected run")
    artifact = matches[0]
    artifact_id = artifact.get("id")
    artifact_digest = artifact.get("digest")
    if artifact.get("expired") is not False:
        raise CollectorError("selected artifact is expired or has unknown expiry state")
    if isinstance(artifact_id, bool) or not isinstance(artifact_id, int) or artifact_id <= 0:
        raise CollectorError("selected artifact has an invalid artifact ID")
    if not isinstance(artifact_digest, str) or not DIGEST_RE.fullmatch(artifact_digest):
        raise CollectorError("selected artifact is missing a valid SHA-256 digest")
    branch = text(run.get("head_branch"), "workflow_run.head_branch")
    return (
        {
            "run_id": run_id,
            "run_number": run.get("run_number"),
            "workflow_id": run.get("workflow_id"),
            "event": run.get("event"),
            "head_branch": branch,
            "head_sha": sha,
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "html_url": run.get("html_url"),
            "producer_job": {
                "id": producer.get("id"),
                "name": job_name,
                "status": producer.get("status"),
                "conclusion": producer.get("conclusion"),
            },
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


def emit(name: str, value: str) -> None:
    if not SAFE_TEXT_RE.fullmatch(value):
        raise CollectorError(f"output {name} contains a newline or NUL")
    if path := os.environ.get("GITHUB_OUTPUT"):
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")


def write_summary(report: dict[str, Any]) -> None:
    if not (path := os.environ.get("GITHUB_STEP_SUMMARY")):
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write("## ProofPath GitHub Evidence Collector\n\n")
        handle.write(f"- Repository: `{report['repository']}`\n")
        handle.write(f"- Source SHA: `{report['source_sha']}`\n")
        handle.write(f"- Artifact: `{report['artifact']['name']}` (`{report['artifact']['digest']}`)\n")
        handle.write(f"- Checks: `{report['check_count']}`\n")
        handle.write(f"- Current mapped approvals: `{report['approval_count']}`\n")
        handle.write("- Collector verified authority: `false`\n")
        handle.write("- Collector verified attestation claim: `false`\n")
        handle.write("- Deployment performed: `false`\n")


def main() -> int:
    try:
        token = text(os.environ.get("PROOFPATH_GITHUB_TOKEN"), "github-token")
        repo = text(os.environ.get("PROOFPATH_REPOSITORY") or os.environ.get("GITHUB_REPOSITORY"), "repository")
        sha = text(os.environ.get("PROOFPATH_SOURCE_SHA") or os.environ.get("GITHUB_SHA"), "source-sha")
        if not REPOSITORY_RE.fullmatch(repo):
            raise CollectorError("repository must use owner/name form")
        if not SHA_RE.fullmatch(sha):
            raise CollectorError("source-sha must be a lowercase hex SHA")
        run_raw = text(os.environ.get("PROOFPATH_ARTIFACT_RUN_ID"), "artifact-run-id")
        pr_raw = os.environ.get("PROOFPATH_PULL_REQUEST_NUMBER", "0")
        if not run_raw.isdigit() or int(run_raw) <= 0:
            raise CollectorError("artifact-run-id must be a positive integer")
        if not isinstance(pr_raw, str) or not pr_raw.isdigit():
            raise CollectorError("pull-request-number must be a non-negative integer")
        artifact_name = text(os.environ.get("PROOFPATH_ARTIFACT_NAME"), "artifact-name")
        config_path = workspace_path(text(os.environ.get("PROOFPATH_COLLECTOR_CONFIG"), "config"), "config", exists=True)
        output_path = workspace_path(text(os.environ.get("PROOFPATH_OUTPUT"), "output"), "output")
        report_path = workspace_path(text(os.environ.get("PROOFPATH_REPORT"), "report"), "report")
        if output_path == report_path:
            raise CollectorError("output and report paths must differ")

        config = validate_config(load_json(config_path), sha)
        run, artifact = collect_artifact(
            repo, sha, int(run_raw), artifact_name, config["artifact_job_name"], token
        )
        checks, check_report = collect_checks(repo, sha, token, config)
        approvals, approval_report = collect_approvals(
            repo, int(pr_raw), sha, token, config["approval_role_map"]
        )
        provenance = config["provenance"]
        facts = {
            "profile_id": FACTS_PROFILE,
            "authority": config["authority"],
            "build_provenance": {
                "commit_sha": sha,
                "artifact_digest": artifact["digest"],
                "attestation_verified": provenance["attestation_verified"],
                "runner_environment": provenance["runner_environment"],
                "workflow": provenance["workflow"],
                "source_sha": sha,
                "signer_sha": provenance["signer_sha"],
            },
            "checks": checks,
            "security": config["security"],
            "approvals": approvals,
            "change_ticket": config["change_ticket"],
        }
        report: dict[str, Any] = {
            "profile_id": REPORT_PROFILE,
            "repository": repo,
            "source_sha": sha,
            "source_branch": run["head_branch"],
            "pull_request_number": int(pr_raw) or None,
            "workflow_run": run,
            "artifact": artifact,
            "check_count": len(checks),
            "approval_count": len(approvals),
            "check_selection": check_report,
            "approval_selection": approval_report,
            "collector_live_github_api": True,
            "collector_verified_authority": False,
            "collector_verified_attestation_claim": False,
            "collector_verified_change_ticket": False,
            "deployment_performed": False,
            "limitations": [
                "checks, reviews, workflow identity, producer-job status, and artifact metadata come from the GitHub API",
                "approval roles come from explicit reviewed configuration rather than inference from GitHub usernames",
                "authority, vulnerability count, ticket, and attestation-verification claims remain explicit upstream facts",
                "the collector does not deploy, merge, grant authority, or call a cloud provider",
            ],
            "report_root": None,
        }
        report["report_root"] = root(report)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        values = {
            "trusted-facts-path": str(output_path),
            "collector-report-path": str(report_path),
            "artifact-digest": artifact["digest"],
            "artifact-id": str(artifact["id"]),
            "artifact-run-id": run_raw,
            "repository": repo,
            "source-branch": run["head_branch"],
            "source-sha": sha,
            "check-count": str(len(checks)),
            "approval-count": str(len(approvals)),
        }
        for name, value in values.items():
            emit(name, value)
        write_summary(report)
        print(
            f"ProofPath GitHub Evidence Collector: {repo}@{sha} / "
            f"{artifact['digest']} / checks={len(checks)} approvals={len(approvals)}"
        )
        return 0
    except (CollectorError, OSError, KeyError, TypeError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
