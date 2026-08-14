#!/usr/bin/env python3
"""Fail-closed validation for ProofPath capability canonicality.

This validator intentionally does not query GitHub. It validates the repository's
checked-in declaration of capability state and prevents non-canonical capabilities
from being treated as default consumer contracts.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA40 = re.compile(r"^[0-9a-f]{40}$")
STATUSES = {"CANONICAL", "PROPOSED", "EXPERIMENTAL", "SUPERSEDED", "ARCHIVED"}


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_keys)


def validate_manifest(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if data.get("schema_version") != "proofpath.capability-manifest.v0.1":
        errors.append("schema_version must be proofpath.capability-manifest.v0.1")
    if data.get("repository") != "safal207/ProofPath":
        errors.append("repository must be safal207/ProofPath")

    observed_main = data.get("observed_main_sha")
    if not isinstance(observed_main, str) or not SHA40.fullmatch(observed_main):
        errors.append("observed_main_sha must be a lowercase 40-character SHA")

    policy = data.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy must be an object")
    else:
        if policy.get("default_consumer_status") != "CANONICAL":
            errors.append("default_consumer_status must be CANONICAL")
        for key in (
            "noncanonical_requires_exact_head_pin",
            "noncanonical_requires_explicit_opt_in",
            "canonical_dependency_must_be_canonical",
        ):
            if policy.get(key) is not True:
                errors.append(f"policy.{key} must be true")

    capabilities = data.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        errors.append("capabilities must be a non-empty array")
        return errors

    by_id: dict[str, dict[str, Any]] = {}
    for index, capability in enumerate(capabilities):
        prefix = f"capabilities[{index}]"
        if not isinstance(capability, dict):
            errors.append(f"{prefix} must be an object")
            continue

        cid = capability.get("id")
        if not isinstance(cid, str) or not cid.strip():
            errors.append(f"{prefix}.id must be non-empty")
            continue
        if cid in by_id:
            errors.append(f"duplicate capability id: {cid}")
            continue
        by_id[cid] = capability

        status = capability.get("status")
        if status not in STATUSES:
            errors.append(f"{cid}: invalid status {status!r}")
            continue

        deps = capability.get("depends_on")
        if not isinstance(deps, list) or any(not isinstance(dep, str) or not dep for dep in deps):
            errors.append(f"{cid}: depends_on must be an array of capability ids")

        consumer_default = capability.get("consumer_default_allowed")
        if not isinstance(consumer_default, bool):
            errors.append(f"{cid}: consumer_default_allowed must be boolean")

        canonical_commit = capability.get("canonical_commit")
        head_sha = capability.get("head_sha")
        source_pr = capability.get("source_pr")

        if status == "CANONICAL":
            if not isinstance(canonical_commit, str) or not SHA40.fullmatch(canonical_commit):
                errors.append(f"{cid}: CANONICAL requires canonical_commit")
            if head_sha is not None:
                errors.append(f"{cid}: CANONICAL must not expose a branch head_sha as its consumer identity")
            if consumer_default is not True:
                errors.append(f"{cid}: CANONICAL must allow default consumption")
        else:
            if canonical_commit is not None:
                errors.append(f"{cid}: non-canonical capability must not claim canonical_commit")
            if consumer_default is not False:
                errors.append(f"{cid}: non-canonical capability cannot be a default consumer dependency")
            if status in {"PROPOSED", "EXPERIMENTAL"}:
                if not isinstance(source_pr, int) or source_pr <= 0:
                    errors.append(f"{cid}: {status} requires positive source_pr")
                if not isinstance(head_sha, str) or not SHA40.fullmatch(head_sha):
                    errors.append(f"{cid}: {status} requires exact lowercase head_sha")

    for cid, capability in by_id.items():
        deps = capability.get("depends_on", [])
        if not isinstance(deps, list):
            continue
        for dep in deps:
            if dep not in by_id:
                errors.append(f"{cid}: unknown dependency {dep}")
                continue
            if capability.get("status") == "CANONICAL" and by_id[dep].get("status") != "CANONICAL":
                errors.append(f"{cid}: CANONICAL capability depends on non-canonical {dep}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(cid: str, trail: list[str]) -> None:
        if cid in visited:
            return
        if cid in visiting:
            cycle = " -> ".join(trail + [cid])
            errors.append(f"dependency cycle: {cycle}")
            return
        visiting.add(cid)
        capability = by_id.get(cid, {})
        deps = capability.get("depends_on", [])
        if isinstance(deps, list):
            for dep in deps:
                if dep in by_id:
                    visit(dep, trail + [cid])
        visiting.remove(cid)
        visited.add(cid)

    for cid in by_id:
        visit(cid, [])

    return errors


def summarize(data: dict[str, Any]) -> dict[str, int]:
    counts = {status: 0 for status in sorted(STATUSES)}
    for capability in data.get("capabilities", []):
        if isinstance(capability, dict) and capability.get("status") in counts:
            counts[capability["status"]] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=Path("governance/capability-manifest.v0.1.json"),
    )
    args = parser.parse_args()

    try:
        data = load_manifest(args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"CAPABILITY_MANIFEST_INVALID: {exc}")
        return 1

    errors = validate_manifest(data)
    if errors:
        print("CAPABILITY_MANIFEST_INVALID")
        for error in errors:
            print(f"- {error}")
        return 1

    print("CAPABILITY_MANIFEST_VALID")
    print(json.dumps(summarize(data), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
