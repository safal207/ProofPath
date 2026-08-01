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
POLICY_PROFILE = "proofpath.deploy.guard-policy.v0.1"
ATTESTATION_PROFILE = "proofpath.github.attestation-result.v0.1"
FACTS_PROFILE = "proofpath.deploy.evidence-inputs.v0.1"
REPORT_PROFILE = "proofpath.github.evidence-collector-report.v0.1"
REPORT_DOMAIN = b"proofpath:github-evidence-collector:v0.1:report\n"

SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SAFE_TEXT_RE = re.compile(r"^[^\x00\r\n]+$")
MAX_PAGES = 20


class CollectorError(ValueError):
    """Raised when GitHub evidence cannot be collected without ambiguity."""


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


def boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise CollectorError(f"{name} must be an explicit boolean")
    return value


def nonnegative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CollectorError(f"{name} must be a non-negative integer")
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
        raise CollectorError("GITHUB_API_URL must be an HTTPS URL without embedded credentials")
    if parsed.query or parsed.fragment or ".." in Path(parsed.path).parts:
        raise CollectorError("GITHUB_API_URL contains an unsafe path, query, or fragment")
    return value


def fixture_path(endpoint: str) -> Path | None:
    raw = os.environ.get("PROOFPATH_COLLECTOR_FIXTURE_DIR", "")
    if not raw:
        return None
    if os.environ.get("GITHUB_ACTIONS") == "true":
        raise CollectorError("API fixtures are forbidden inside GitHub Actions")
    directory = workspace_path(raw, "fixture directory")
    if not directory.is_dir():
        raise CollectorError("fixture directory does not exist")
    candidate = directory / f"{hashlib.sha256(endpoint.encode('utf-8')).hexdigest()}.json"
    if not candidate.is_file():
        raise CollectorError(f"missing API fixture for {endpoint}")
    return candidate


def api_get(endpoint: str, token: str) -> Any:
    if not endpoint.startswith("/") or "://" in endpoint or "\\" in endpoint:
        raise CollectorError("GitHub API endpoint must be an absolute API path")
    fixture = fixture_path(endpoint)
    if fixture is not None:
        value = load_json(fixture)
        if set(value) != {"body"}:
            raise CollectorError("API fixture must contain exactly a body field")
        return value["body"]

    base = api_base()
    request = urllib.request.Request(
        base + endpoint,
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
            final = urllib.parse.urlparse(response.geturl())
            expected = urllib.parse.urlparse(base)
            prefix = expected.path.rstrip("/") + "/"
            if (
                final.scheme != expected.scheme
                or final.netloc != expected.netloc
                or not final.path.startswith(prefix)
            ):
                raise CollectorError("GitHub API redirected outside the configured API root")
            raw = response.read(10_000_000)
    except urllib.error.HTTPError as exc:
        raise CollectorError(f"GitHub API returned HTTP {exc.code} for {endpoint}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise CollectorError(f"GitHub API request failed for {endpoint}: {exc}") from exc
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=reject_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError, CollectorError) as exc:
        raise CollectorError(f"GitHub API returned invalid JSON for {endpoint}") from exc


def api_list(endpoint: str, key: str, token: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        separator = "&" if "?" in endpoint else "?"
        value = api_get(f"{endpoint}{separator}per_page=100&page={page}", token)
        entries = value.get(key) if isinstance(value, dict) else value
        if not isinstance(entries, list):
            raise CollectorError(f"GitHub API list {endpoint} is missing {key}")
        if any(not isinstance(entry, dict) for entry in entries):
            raise CollectorError(f"GitHub API list {endpoint} contains a non-object entry")
        result.extend(entries)
        if len(entries) < 100:
            return result
    raise CollectorError(f"GitHub API pagination limit exceeded for {endpoint}")


def validate_policy(value: dict[str, Any]) -> list[str]:
    if value.get("profile_id") != POLICY_PROFILE:
        raise CollectorError("unsupported Deploy Guard policy profile")
    names = value.get("required_checks")
    if not isinstance(names, list):
        raise CollectorError("policy.required_checks must be an array")
    normalized: list[str] = []
    for entry in names:
        name = text(entry, "policy.required_checks entry")
        if name in normalized:
            raise CollectorError(f"duplicate required check name: {name}")
        normalized.append(name)
    return normalized


def validate_config(value: dict[str, Any], source_sha: str, required_checks: list[str]) -> dict[str, Any]:
    expected = {
        "profile_id",
        "artifact_job_name",
        "authority",
        "security",
        "approval_role_map",
        "check_app_allowlist",
        "change_ticket",
    }
    if value.get("profile_id") != CONFIG_PROFILE or set(value) != expected:
        raise CollectorError("unsupported or non-canonical collector config")

    authority = value["authority"]
    if not isinstance(authority, dict):
        raise CollectorError("config.authority must be an object")

    security = value["security"]
    if not isinstance(security, dict):
        raise CollectorError("config.security must be an object")
    nonnegative_int(security.get("critical_vulnerabilities"), "security.critical_vulnerabilities")

    ticket = value["change_ticket"]
    if ticket is not None:
        if not isinstance(ticket, dict):
            raise CollectorError("config.change_ticket must be an object or null")
        if ticket.get("commit_sha") != source_sha:
            raise CollectorError("change_ticket.commit_sha must exactly match source-sha")

    role_map = value["approval_role_map"]
    if not isinstance(role_map, dict):
        raise CollectorError("config.approval_role_map must be an object")
    roles: dict[str, str] = {}
    for actor, role in role_map.items():
        normalized_actor = text(actor, "approval role actor").lower()
        if normalized_actor in roles:
            raise CollectorError("approval_role_map contains duplicate actors by case")
        roles[normalized_actor] = text(role, f"approval_role_map[{actor!r}]")

    app_map = value["check_app_allowlist"]
    if not isinstance(app_map, dict):
        raise CollectorError("check_app_allowlist must be an object")
    apps: dict[str, str] = {}
    for name, slug in app_map.items():
        check_name = text(name, "check app name")
        if check_name not in required_checks:
            raise CollectorError("check_app_allowlist may only reference policy.required_checks")
        apps[check_name] = text(slug, f"check_app_allowlist[{name!r}]")

    return {
        "artifact_job_name": text(value["artifact_job_name"], "artifact_job_name"),
        "authority": authority,
        "security": security,
        "approval_role_map": roles,
        "check_app_allowlist": apps,
        "change_ticket": ticket,
    }


def normalize_workflow(repository: str, run: dict[str, Any]) -> str:
    path = run.get("path")
    if not isinstance(path, str) or not path:
        raise CollectorError("workflow run did not expose a workflow path")
    path = path.split("@", 1)[0]
    if not path.startswith(".github/workflows/") or ".." in Path(path).parts:
        raise CollectorError("workflow run path is not a trusted workflow file")
    return f"{repository}/{path}"


def normalize_check(check: dict[str, Any]) -> str:
    if check.get("status") != "completed":
        return "pending"
    conclusion = check.get("conclusion")
    if conclusion == "success":
        return "success"
    if conclusion in {
        "failure",
        "cancelled",
        "timed_out",
        "action_required",
        "startup_failure",
        "stale",
    }:
        return "failure"
    return "pending"


def collect_checks(
    repository: str,
    source_sha: str,
    token: str,
    required_checks: list[str],
    app_allowlist: dict[str, str],
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    if not required_checks:
        return [], []
    encoded = urllib.parse.quote(repository, safe="/")
    raw = api_list(
        f"/repos/{encoded}/commits/{source_sha}/check-runs?filter=latest",
        "check_runs",
        token,
    )
    facts: list[dict[str, str]] = []
    report: list[dict[str, Any]] = []
    for name in required_checks:
        matches = [
            item
            for item in raw
            if item.get("name") == name
            and (
                item.get("head_sha") == source_sha
                or (
                    isinstance(item.get("check_suite"), dict)
                    and item["check_suite"].get("head_sha") == source_sha
                )
            )
        ]
        expected_app = app_allowlist.get(name)
        if expected_app:
            matches = [
                item
                for item in matches
                if isinstance(item.get("app"), dict)
                and item["app"].get("slug") == expected_app
            ]
        if not matches:
            facts.append({"name": name, "status": "pending", "commit_sha": source_sha})
            report.append(
                {
                    "name": name,
                    "selected": False,
                    "expected_app": expected_app,
                    "reason": "NO_MATCHING_CHECK_RUN",
                }
            )
            continue
        selected = max(
            matches,
            key=lambda item: item.get("id") if isinstance(item.get("id"), int) else -1,
        )
        status = normalize_check(selected)
        facts.append({"name": name, "status": status, "commit_sha": source_sha})
        report.append(
            {
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
            }
        )
    return facts, report


def collect_approvals(
    repository: str,
    pull_request_number: int,
    source_sha: str,
    token: str,
    role_map: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if pull_request_number == 0 or not role_map:
        return [], [{"selected": False, "reason": "PULL_REQUEST_COLLECTION_DISABLED_OR_EMPTY_ROLE_MAP"}]

    encoded = urllib.parse.quote(repository, safe="/")
    pull = api_get(f"/repos/{encoded}/pulls/{pull_request_number}", token)
    if not isinstance(pull, dict) or not isinstance(pull.get("head"), dict):
        raise CollectorError("GitHub pull request response is malformed")
    if pull["head"].get("sha") != source_sha:
        raise CollectorError("pull request head SHA does not match source-sha")

    reviews = api_list(
        f"/repos/{encoded}/pulls/{pull_request_number}/reviews",
        "reviews",
        token,
    )
    latest: dict[str, dict[str, Any]] = {}
    for review in reviews:
        user = review.get("user")
        login = user.get("login") if isinstance(user, dict) else None
        if not isinstance(login, str) or not login:
            continue
        actor = login.lower()
        if actor not in role_map:
            continue
        state = review.get("state")
        if state not in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            continue
        current = latest.get(actor)
        review_id = review.get("id") if isinstance(review.get("id"), int) else -1
        current_id = current.get("id") if current and isinstance(current.get("id"), int) else -1
        if review_id > current_id:
            latest[actor] = review

    facts: list[dict[str, Any]] = []
    report: list[dict[str, Any]] = []
    for actor, role in sorted(role_map.items()):
        review = latest.get(actor)
        selected = bool(
            review
            and review.get("state") == "APPROVED"
            and review.get("commit_id") == source_sha
        )
        report.append(
            {
                "actor": actor,
                "role": role,
                "selected": selected,
                "review_id": review.get("id") if review else None,
                "state": review.get("state") if review else None,
                "commit_id": review.get("commit_id") if review else None,
                "reason": None if selected else "LATEST_REVIEW_NOT_CURRENT_APPROVAL",
            }
        )
        if selected:
            facts.append(
                {
                    "actor": actor,
                    "role": role,
                    "approved": True,
                    "commit_sha": source_sha,
                }
            )
    return facts, report


def collect_run_artifact_and_job(
    repository: str,
    source_sha: str,
    run_id: int,
    artifact_name: str,
    producer_job_name: str,
    token: str,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    encoded = urllib.parse.quote(repository, safe="/")
    run = api_get(f"/repos/{encoded}/actions/runs/{run_id}", token)
    if not isinstance(run, dict) or not isinstance(run.get("repository"), dict):
        raise CollectorError("GitHub workflow run response is malformed")
    if run["repository"].get("full_name") != repository:
        raise CollectorError("artifact workflow run belongs to another repository")
    if run.get("head_sha") != source_sha:
        raise CollectorError("artifact workflow run head SHA does not match source-sha")
    if run.get("status") == "completed":
        if run.get("conclusion") != "success":
            raise CollectorError("completed artifact workflow run must be successful")
    elif run.get("status") not in {"queued", "in_progress"}:
        raise CollectorError("artifact workflow run has an unsupported status")

    jobs = api_list(f"/repos/{encoded}/actions/runs/{run_id}/jobs", "jobs", token)
    producer_matches = [job for job in jobs if job.get("name") == producer_job_name]
    if len(producer_matches) != 1:
        raise CollectorError("artifact_job_name must match exactly one job in the selected run")
    producer = producer_matches[0]
    if producer.get("status") != "completed" or producer.get("conclusion") != "success":
        raise CollectorError("artifact producer job must be completed successfully")

    artifacts = api_list(
        f"/repos/{encoded}/actions/runs/{run_id}/artifacts",
        "artifacts",
        token,
    )
    matches = [
        artifact
        for artifact in artifacts
        if artifact.get("name") == artifact_name and artifact.get("expired") is False
    ]
    if len(matches) != 1:
        raise CollectorError("artifact name must match exactly one non-expired artifact")
    artifact = matches[0]
    artifact_id = artifact.get("id")
    artifact_digest = artifact.get("digest")
    if isinstance(artifact_id, bool) or not isinstance(artifact_id, int) or artifact_id <= 0:
        raise CollectorError("selected artifact has an invalid artifact ID")
    if not isinstance(artifact_digest, str) or not DIGEST_RE.fullmatch(artifact_digest):
        raise CollectorError("selected artifact is missing a valid SHA-256 digest")

    branch = text(run.get("head_branch"), "workflow_run.head_branch")
    workflow = normalize_workflow(repository, run)
    return (
        {
            "run_id": run_id,
            "run_number": run.get("run_number"),
            "workflow_id": run.get("workflow_id"),
            "workflow": workflow,
            "event": run.get("event"),
            "head_branch": branch,
            "head_sha": source_sha,
            "status": run.get("status"),
            "conclusion": run.get("conclusion"),
            "html_url": run.get("html_url"),
            "producer_job": {
                "id": producer.get("id"),
                "name": producer_job_name,
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
        workflow,
    )


def load_attestation_result(
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
            "result_supplied": False,
        }
    path = workspace_path(raw_path, "attestation-result", exists=True)
    value = load_json(path)
    expected = {
        "profile_id",
        "verified",
        "source_sha",
        "artifact_digest",
        "workflow",
        "signer_sha",
        "runner_environment",
    }
    if value.get("profile_id") != ATTESTATION_PROFILE or set(value) != expected:
        raise CollectorError("unsupported or non-canonical attestation result")
    if value.get("source_sha") != source_sha:
        raise CollectorError("attestation result source_sha does not match source-sha")
    if value.get("artifact_digest") != artifact_digest:
        raise CollectorError("attestation result artifact_digest does not match selected artifact")
    if value.get("workflow") != workflow:
        raise CollectorError("attestation result workflow does not match artifact-producing workflow")
    verified = boolean(value.get("verified"), "attestation-result.verified")
    signer_sha = text(value.get("signer_sha"), "attestation-result.signer_sha")
    if not SHA_RE.fullmatch(signer_sha):
        raise CollectorError("attestation-result.signer_sha must be a lowercase hex SHA")
    runner = value.get("runner_environment")
    if runner not in {"github-hosted", "self-hosted", "unknown"}:
        raise CollectorError("attestation-result.runner_environment is unsupported")
    return {
        "attestation_verified": verified,
        "runner_environment": runner,
        "source_sha": source_sha,
        "signer_sha": signer_sha,
        "result_supplied": True,
    }


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
        handle.write(f"- Workflow: `{report['workflow_run']['workflow']}`\n")
        handle.write(
            f"- Artifact: `{report['artifact']['name']}` "
            f"(`{report['artifact']['digest']}`)\n"
        )
        handle.write(f"- Checks: `{report['check_count']}`\n")
        handle.write(f"- Current mapped approvals: `{report['approval_count']}`\n")
        handle.write("- Collector verified authority: `false`\n")
        handle.write("- Collector verified attestation cryptography: `false`\n")
        handle.write("- Deployment performed: `false`\n")


def main() -> int:
    try:
        token = text(os.environ.get("PROOFPATH_GITHUB_TOKEN"), "github-token")
        repository = text(
            os.environ.get("PROOFPATH_REPOSITORY") or os.environ.get("GITHUB_REPOSITORY"),
            "repository",
        )
        source_sha = text(os.environ.get("PROOFPATH_SOURCE_SHA"), "source-sha")
        if not REPOSITORY_RE.fullmatch(repository):
            raise CollectorError("repository must use owner/name form")
        if not SHA_RE.fullmatch(source_sha):
            raise CollectorError("source-sha must be a 40-64 character lowercase hex SHA")

        run_raw = text(os.environ.get("PROOFPATH_ARTIFACT_RUN_ID"), "artifact-run-id")
        pr_raw = os.environ.get("PROOFPATH_PULL_REQUEST_NUMBER", "0")
        if not run_raw.isdigit() or int(run_raw) <= 0:
            raise CollectorError("artifact-run-id must be a positive integer")
        if not isinstance(pr_raw, str) or not pr_raw.isdigit():
            raise CollectorError("pull-request-number must be a non-negative integer")
        artifact_name = text(os.environ.get("PROOFPATH_ARTIFACT_NAME"), "artifact-name")

        policy_path = workspace_path(
            text(os.environ.get("PROOFPATH_POLICY"), "policy"),
            "policy",
            exists=True,
        )
        config_path = workspace_path(
            text(os.environ.get("PROOFPATH_COLLECTOR_CONFIG"), "config"),
            "config",
            exists=True,
        )
        output_path = workspace_path(
            text(os.environ.get("PROOFPATH_OUTPUT"), "output"),
            "output",
        )
        report_path = workspace_path(
            text(os.environ.get("PROOFPATH_REPORT"), "report"),
            "report",
        )
        if output_path == report_path:
            raise CollectorError("output and report paths must differ")

        required_checks = validate_policy(load_json(policy_path))
        config = validate_config(load_json(config_path), source_sha, required_checks)
        run, artifact, workflow = collect_run_artifact_and_job(
            repository,
            source_sha,
            int(run_raw),
            artifact_name,
            config["artifact_job_name"],
            token,
        )
        checks, check_report = collect_checks(
            repository,
            source_sha,
            token,
            required_checks,
            config["check_app_allowlist"],
        )
        approvals, approval_report = collect_approvals(
            repository,
            int(pr_raw),
            source_sha,
            token,
            config["approval_role_map"],
        )
        attestation = load_attestation_result(
            os.environ.get("PROOFPATH_ATTESTATION_RESULT", ""),
            source_sha=source_sha,
            artifact_digest=artifact["digest"],
            workflow=workflow,
        )

        facts = {
            "profile_id": FACTS_PROFILE,
            "authority": config["authority"],
            "build_provenance": {
                "commit_sha": source_sha,
                "artifact_digest": artifact["digest"],
                "attestation_verified": attestation["attestation_verified"],
                "runner_environment": attestation["runner_environment"],
                "workflow": workflow,
                "source_sha": source_sha,
                "signer_sha": attestation["signer_sha"],
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
            "pull_request_number": int(pr_raw) or None,
            "workflow_run": run,
            "artifact": artifact,
            "check_count": len(checks),
            "approval_count": len(approvals),
            "check_selection": check_report,
            "approval_selection": approval_report,
            "collector_live_github_api": not bool(
                os.environ.get("PROOFPATH_COLLECTOR_FIXTURE_DIR")
            ),
            "collector_verified_authority": False,
            "collector_verified_attestation_cryptography": False,
            "attestation_result_supplied": attestation["result_supplied"],
            "collector_verified_change_ticket": False,
            "deployment_performed": False,
            "limitations": [
                "checks, reviews, workflow identity, producer-job status, and artifact metadata come from the GitHub API",
                "approval roles come from explicit reviewed configuration rather than inference from GitHub usernames",
                "authority, vulnerability count, ticket, and attestation verification remain explicit upstream facts",
                "an attestation result is checked for exact artifact, source, workflow, signer, and runner binding but its cryptography is verified by the upstream verifier",
                "the collector does not deploy, merge, grant authority, or call a cloud provider",
            ],
            "report_root": None,
        }
        report["report_root"] = root(report)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(facts, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        values = {
            "trusted-facts-path": str(output_path),
            "collector-report-path": str(report_path),
            "collector-root": report["report_root"],
            "artifact-digest": artifact["digest"],
            "artifact-id": str(artifact["id"]),
            "artifact-run-id": run_raw,
            "workflow": workflow,
            "repository": repository,
            "source-branch": run["head_branch"],
            "source-sha": source_sha,
            "check-count": str(len(checks)),
            "approval-count": str(len(approvals)),
        }
        for name, value in values.items():
            emit(name, value)
        write_summary(report)
        print(
            f"ProofPath GitHub Evidence Collector: {repository}@{source_sha} / "
            f"{artifact['digest']} / checks={len(checks)} approvals={len(approvals)}"
        )
        return 0
    except (CollectorError, OSError, KeyError, TypeError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
