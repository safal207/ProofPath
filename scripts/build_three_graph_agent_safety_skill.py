#!/usr/bin/env python3
"""Validate and package the Three-Graph Agent Safety ChatGPT skill."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import NoReturn

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "three-graph-agent-safety"
SKILL_DIR = REPO_ROOT / "skills" / SKILL_NAME
DIST_DIR = REPO_ROOT / "dist"
ARCHIVE = DIST_DIR / f"{SKILL_NAME}.zip"
CHECKSUM = DIST_DIR / f"{SKILL_NAME}.zip.sha256"
FIXED_TIME = (2026, 1, 1, 0, 0, 0)
EXPECTED_VERSION = "1.1.0"


def fail(message: str) -> NoReturn:
    raise SystemExit(f"ERROR: {message}")


def validate_skill() -> list[Path]:
    skill_file = SKILL_DIR / "SKILL.md"
    if not skill_file.is_file():
        fail(f"missing {skill_file.relative_to(REPO_ROOT)}")
    text = skill_file.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail("SKILL.md must start with YAML frontmatter")
    parts = text.split("---", 2)
    if len(parts) != 3:
        fail("SKILL.md frontmatter is not closed")
    frontmatter = parts[1]
    name_match = re.search(r"^name:\s*(.+?)\s*$", frontmatter, re.MULTILINE)
    description_match = re.search(r"^description:\s*(.+?)\s*$", frontmatter, re.MULTILINE)
    version_match = re.search(r"^\s+version:\s*[\"']?(.+?)[\"']?\s*$", frontmatter, re.MULTILINE)
    if not name_match or not description_match or not version_match:
        fail("SKILL.md frontmatter is missing name, description, or version")
    declared_name = name_match.group(1).strip().strip("\"'")
    description = description_match.group(1).strip().strip("\"'")
    version = version_match.group(1).strip().strip("\"'")
    if declared_name != SKILL_NAME:
        fail(f"skill name {declared_name!r} does not match directory {SKILL_NAME!r}")
    if version != EXPECTED_VERSION:
        fail(f"skill version {version!r} does not match expected {EXPECTED_VERSION!r}")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", declared_name):
        fail("skill name must use lowercase kebab-case")
    if not 1 <= len(description) <= 1024:
        fail("description must contain 1..1024 characters")

    files: list[Path] = []
    for path in sorted(SKILL_DIR.rglob("*")):
        if path.is_symlink():
            fail(f"symlinks are not allowed in skill package: {path}")
        if path.is_file():
            files.append(path)
    required = {
        SKILL_DIR / "references" / "ARCHITECTURE.md",
        SKILL_DIR / "references" / "MEMORY_GRAPH.md",
        SKILL_DIR / "references" / "POLICY_GRAPH.md",
        SKILL_DIR / "references" / "RISK_GRAPH.md",
        SKILL_DIR / "references" / "MISMATCH_CATALOG.md",
        SKILL_DIR / "references" / "COMPLETION_CHECKLIST.md",
        SKILL_DIR / "assets" / "three-graph-bundle.schema.json",
        SKILL_DIR / "assets" / "personal-agent-safety-bundle.schema.json",
        SKILL_DIR / "assets" / "personal-agent-safety.example.json",
        SKILL_DIR / "tools" / "validate_personal_agent_safety_bundle.py",
        SKILL_DIR / "README_RU.md",
        SKILL_DIR / "LICENSE",
    }
    missing = sorted(path for path in required if path not in files)
    if missing:
        fail("missing package files: " + ", ".join(str(path.relative_to(REPO_ROOT)) for path in missing))

    for schema_name in ("three-graph-bundle.schema.json", "personal-agent-safety-bundle.schema.json"):
        payload = json.loads((SKILL_DIR / "assets" / schema_name).read_text(encoding="utf-8"))
        if not payload.get("$schema", "").endswith("2020-12/schema"):
            fail(f"{schema_name} is not draft 2020-12")
    validator = SKILL_DIR / "tools" / "validate_personal_agent_safety_bundle.py"
    example = SKILL_DIR / "assets" / "personal-agent-safety.example.json"
    subprocess.run([sys.executable, str(validator), str(example), "--self-test"], check=True)
    return files


def build(files: list[Path]) -> str:
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE.unlink(missing_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(SKILL_DIR)
            archive_name = (Path(SKILL_NAME) / relative).as_posix()
            info = zipfile.ZipInfo(archive_name, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
    with zipfile.ZipFile(ARCHIVE, "r") as archive:
        bad_member = archive.testzip()
        if bad_member:
            fail(f"ZIP integrity failed at {bad_member}")
        prefix = f"{SKILL_NAME}/"
        if any(not name.startswith(prefix) for name in archive.namelist()):
            fail("ZIP contains a file outside the skill root directory")
    digest = hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    CHECKSUM.write_text(f"{digest}  {ARCHIVE.name}\n", encoding="utf-8")
    return digest


def main() -> int:
    files = validate_skill()
    digest = build(files)
    print(f"PASS: validated {SKILL_NAME} v{EXPECTED_VERSION}")
    print(f"files: {len(files)}")
    print(f"archive: {ARCHIVE.relative_to(REPO_ROOT)}")
    print(f"sha256: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
