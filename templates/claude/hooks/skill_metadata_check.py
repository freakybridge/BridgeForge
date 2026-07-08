#!/usr/bin/env python3
"""pre-commit hook: validate BridgeForge common skill frontmatter.

Scope:
- Only checks the factory source tree `skills/<name>/SKILL.md`.
- Downstream projects normally do not keep common skills in repo root `skills/`,
  so this hook self-gates to no-op there.

Hard gates are limited to metadata that controls discoverability and invocation:
frontmatter exists, `name` matches the directory, `description` is present,
`user_invocable: true` uses the current spelling, and `argument` is present.
"""
from __future__ import annotations

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


def _validate_skill(skill_file: Path) -> list[str]:
    rel = skill_file.relative_to(REPO_ROOT).as_posix()
    meta, issues = _parse_frontmatter(skill_file)
    expected_name = skill_file.parent.name

    if not meta:
        return [f"{rel}: {issue}" for issue in issues]

    name = meta.get("name", "")
    if name != expected_name:
        issues.append(f"name must be {expected_name!r}, got {name!r}")

    description = meta.get("description", "")
    if not description:
        issues.append("description is required")

    if "user-invocable" in meta:
        issues.append("use user_invocable, not legacy user-invocable")
    if meta.get("user_invocable", "").lower() != "true":
        issues.append("user_invocable: true is required")

    if not meta.get("argument", ""):
        issues.append("argument is required; use `argument: 无` for no-argument skills")

    return [f"{rel}: {issue}" for issue in issues]


def main() -> int:
    try:
        if not SKILLS_DIR.is_dir():
            return 0

        issues: list[str] = []
        for skill_file in sorted(SKILLS_DIR.glob("*/SKILL.md")):
            issues.extend(_validate_skill(skill_file))

        if not issues:
            return 0

        print("[skill-metadata] pre-commit 硬拦: 通用 skill frontmatter 不完整, 提交被阻断", file=sys.stderr)
        for issue in issues:
            print(f"[skill-metadata]   {issue}", file=sys.stderr)
        print("[skill-metadata] 修法: 补齐 name/description/user_invocable/argument 后再提交。", file=sys.stderr)
        return 2
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
