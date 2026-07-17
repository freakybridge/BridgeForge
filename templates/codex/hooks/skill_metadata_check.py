#!/usr/bin/env python3
"""pre-commit hook: validate BridgeForge skill metadata and loading shape.

Scope:
- Only checks the factory source tree `skills/<name>/SKILL.md`.
- Downstream projects normally do not keep common skills in repo root `skills/`,
  so this hook self-gates to no-op there.

Hard gates cover discoverability plus unsafe context growth: required metadata,
single-line descriptions <= 500 chars, SKILL.md <= 500 lines, and live one-level
`references/` links. Descriptions over 300 chars are soft warnings.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
BOM = b"\xef\xbb\xbf"
DESCRIPTION_WARN_CHARS = 300
DESCRIPTION_MAX_CHARS = 500
SKILL_MAX_LINES = 500
CATALOG_DESCRIPTION_MAX_CHARS = 4_000
MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+\.md(?:#[^)]*)?)\)")


def _parse_frontmatter(path: Path) -> tuple[dict[str, str], list[str]]:
    issues: list[str] = []
    try:
        data = path.read_bytes()
    except Exception as exc:
        return {}, [f"cannot read file: {exc}"]

    if data.startswith(BOM):
        issues.append("starts with UTF-8 BOM; frontmatter must start at byte 0 with ---")
        data = data[len(BOM) :]

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return {}, [f"not valid UTF-8: {exc}"]

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, issues + ["missing opening frontmatter line ---"]

    close_idx: int | None = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            close_idx = i
            break
    if close_idx is None:
        return {}, issues + ["missing closing frontmatter line ---"]

    meta: dict[str, str] = {}
    for raw in lines[1:close_idx]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw[0].isspace():
            continue
        if ":" not in raw:
            issues.append(f"invalid frontmatter line: {raw}")
            continue
        key, value = raw.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, issues


def _validate_skill(skill_file: Path, expected_name: str | None = None) -> tuple[list[str], list[str]]:
    rel = skill_file.relative_to(REPO_ROOT).as_posix()
    meta, issues = _parse_frontmatter(skill_file)
    warnings: list[str] = []
    expected_name = expected_name or skill_file.parent.name

    if not meta:
        return [f"{rel}: {issue}" for issue in issues], warnings

    name = meta.get("name", "")
    if name != expected_name:
        issues.append(f"name must be {expected_name!r}, got {name!r}")

    description = meta.get("description", "")
    if not description:
        issues.append("description is required")
    elif description in {"|", ">", "|-", ">-"}:
        issues.append("description must be a compact single line, not a YAML block scalar")
    elif len(description) > DESCRIPTION_MAX_CHARS:
        issues.append(f"description exceeds {DESCRIPTION_MAX_CHARS} chars ({len(description)})")
    elif len(description) > DESCRIPTION_WARN_CHARS:
        warnings.append(f"description exceeds recommended {DESCRIPTION_WARN_CHARS} chars ({len(description)})")

    if "user-invocable" in meta:
        issues.append("use user_invocable, not legacy user-invocable")
    if meta.get("user_invocable", "").lower() != "true":
        issues.append("user_invocable: true is required")

    if not meta.get("argument", ""):
        issues.append("argument is required; use `argument: 无` for no-argument skills")

    try:
        text = skill_file.read_text(encoding="utf-8")
    except Exception as exc:
        issues.append(f"cannot read body: {exc}")
        text = ""
    line_count = len(text.splitlines())
    if line_count > SKILL_MAX_LINES:
        issues.append(f"SKILL.md exceeds {SKILL_MAX_LINES} lines ({line_count}); split conditional detail into references/")

    for target in MD_LINK_RE.findall(text):
        clean = target.split("#", 1)[0].strip()
        parts = Path(clean).parts
        # Only a skill's own one-level references/ directory is a packaged
        # resource. Links to a downstream project's docs or <agent-dir>
        # placeholders are usage examples, not files in this factory skill.
        if not parts or parts[0].lower() != "references":
            continue
        if len(parts) > 2:
            issues.append(f"reference nesting must stay one level deep: {clean}")
            continue
        resolved = (skill_file.parent / clean).resolve()
        if not resolved.exists():
            issues.append(f"dead markdown reference: {clean}")

    prefix = f"{rel}: "
    return [prefix + issue for issue in issues], [prefix + warning for warning in warnings]


def main() -> int:
    try:
        if not SKILLS_DIR.is_dir():
            return 0

        issues: list[str] = []
        warnings: list[str] = []
        for skill_file in sorted(SKILLS_DIR.glob("*/SKILL.md")):
            skill_issues, skill_warnings = _validate_skill(skill_file)
            issues.extend(skill_issues)
            warnings.extend(skill_warnings)

        root_skill = REPO_ROOT / "SKILL.md"
        if root_skill.exists():
            root_issues, root_warnings = _validate_skill(root_skill, "bridgeforge")
            issues.extend(root_issues)
            warnings.extend(root_warnings)

        catalog_files = list(sorted(SKILLS_DIR.glob("*/SKILL.md")))
        if root_skill.exists():
            catalog_files.append(root_skill)
        catalog_chars = sum(len(_parse_frontmatter(path)[0].get("description", "")) for path in catalog_files)
        if catalog_chars > CATALOG_DESCRIPTION_MAX_CHARS:
            issues.append(
                f"skill catalog descriptions exceed {CATALOG_DESCRIPTION_MAX_CHARS} chars "
                f"({catalog_chars}); shorten discovery metadata"
            )

        for warning in warnings:
            print(f"[skill-metadata] warning: {warning}", file=sys.stderr)

        if not issues:
            return 0

        print("[skill-metadata] pre-commit 硬拦: 通用 skill frontmatter 不完整, 提交被阻断", file=sys.stderr)
        for issue in issues:
            print(f"[skill-metadata]   {issue}", file=sys.stderr)
        print("[skill-metadata] 修法: 补 metadata、缩短入口，或把低频细节移到一层 references/。", file=sys.stderr)
        return 2
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
