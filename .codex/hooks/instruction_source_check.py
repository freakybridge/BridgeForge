#!/usr/bin/env python3
"""Validate Codex native instruction sources; never writes files."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent.parent
MAX_AGENTS_BYTES = 48 * 1024
PROJECT_NAME_CLONE_RE = re.compile(
    r"(?m)^(git clone <repo_url> )"
    r"([A-Za-z0-9._-]+|\{\{PROJECT_NAME\}\})"
    r"( && cd )\2([ \t]*)$"
)
PUBLIC_REQUIRED_HEADINGS = (
    "## BridgeForge 公共区",
    "### 1.1 公共架构红线",
    "### 1.3 工具与证据红线",
    "### 2.1 原生指令承载索引",
    "### 2.3 文档管理",
    "### 5.2 鬼打墙觉察与渐进升级",
)
PROJECT_REQUIRED_HEADINGS = (
    "## 项目级专区",
    "### 项目架构红线",
    "### 项目业务与安全红线",
    "### 项目目录地图",
    "### 项目快速命令",
    "### 目录级 AGENTS 索引",
)
PUBLIC_BEGIN = "<!-- BRIDGEFORGE:PUBLIC:BEGIN -->"
PUBLIC_END = "<!-- BRIDGEFORGE:PUBLIC:END -->"
PROJECT_BEGIN = "<!-- BRIDGEFORGE:PROJECT:BEGIN -->"
PROJECT_END = "<!-- BRIDGEFORGE:PROJECT:END -->"
ZONE_MARKERS = (PUBLIC_BEGIN, PUBLIC_END, PROJECT_BEGIN, PROJECT_END)
FORBIDDEN_RULE_HEADINGS = ("规则文件索引", "Rule 文件索引")
POSITIVE_AUTOLOAD = (
    re.compile(r"详细规则按需加载自\s*[^\n]*rules", re.I),
    re.compile(r"Markdown[^\n]{0,80}(?:paths:|path)[^\n]{0,80}(?:自动|按需|始终)加载", re.I),
    re.compile(r"(?:自动|按需|始终)加载[^\n]{0,80}Markdown[^\n]{0,80}(?:paths:|path)", re.I),
    re.compile(r"(?:paths:|path-rule)[^\n]{0,80}(?:自动|按需|始终)加载", re.I),
)
NEGATED_AUTOLOAD = re.compile(
    r"不会|不能|不支持|并不|未被|禁止.{0,24}(?:宣称|建立)|does\s+not|not\s+(?:be\s+)?auto",
    re.I,
)
CLAUSE_BREAK = re.compile(r"[。！？；;，,\n]+")


def _claims_positive_autoload(text: str) -> bool:
    """Match unsupported positive claims without flagging explicit denials."""
    for clause in CLAUSE_BREAK.split(text):
        if any(pattern.search(clause) for pattern in POSITIVE_AUTOLOAD):
            if NEGATED_AUTOLOAD.search(clause):
                continue
            return True
    return False


def _read(path: Path, root: Path = ROOT) -> tuple[str | None, str | None]:
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_AGENTS_BYTES:
            return None, f"{path.relative_to(root)} exceeds {MAX_AGENTS_BYTES} bytes"
        if raw.startswith(b"\xef\xbb\xbf"):
            return None, f"{path.relative_to(root)} contains UTF-8 BOM"
        return raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n"), None
    except Exception as exc:
        return None, f"cannot read {path.relative_to(root)}: {exc}"


def _bounds(text: str, heading: str) -> tuple[int, int]:
    lines = text.splitlines(keepends=True)
    hits = [i for i, line in enumerate(lines) if line.rstrip("\n") == heading]
    if len(hits) != 1:
        raise ValueError(f"heading must appear exactly once: {heading}")
    start = hits[0]
    level = len(heading) - len(heading.lstrip("#"))
    end = len(lines)
    for index in range(start + 1, len(lines)):
        match = re.match(r"^(#+) ", lines[index])
        if match and len(match.group(1)) <= level:
            end = index
            break
    return start, end


def _visible_heading_positions(
    text: str,
    headings: tuple[str, ...],
) -> dict[str, list[int]]:
    configured = set(headings)
    matches = {heading: [] for heading in headings}
    fence_char: str | None = None
    fence_length = 0
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        if fence_char is not None:
            if re.fullmatch(
                r" {0,3}" + re.escape(fence_char) +
                r"{" + str(fence_length) + r",}[ \t]*",
                stripped,
            ):
                fence_char = None
                fence_length = 0
            offset += len(line)
            continue
        fence = re.fullmatch(r" {0,3}(`{3,}|~{3,})[^\r\n]*", stripped)
        if fence:
            marker = fence.group(1)
            fence_char = marker[0]
            fence_length = len(marker)
            offset += len(line)
            continue
        heading = stripped.lstrip(" ")
        if len(stripped) - len(heading) <= 3 and heading in configured:
            matches[heading].append(offset)
        offset += len(line)
    if fence_char is not None:
        raise ValueError("AGENTS contains an unclosed fenced code block")
    return matches


def _zone_parts(text: str) -> tuple[str, str] | None:
    counts = [text.count(marker) for marker in ZONE_MARKERS]
    if counts == [0, 0, 0, 0]:
        return None
    if counts != [1, 1, 1, 1]:
        raise ValueError("AGENTS zone markers must each appear exactly once")
    positions = [text.index(marker) for marker in ZONE_MARKERS]
    if positions != sorted(positions):
        raise ValueError("AGENTS zone markers are reversed or nested")
    public_finish = text.find("\n", positions[1])
    project_finish = text.find("\n", positions[3])
    public_finish = len(text) if public_finish < 0 else public_finish + 1
    project_finish = len(text) if project_finish < 0 else project_finish + 1
    outside = text[:positions[0]] + text[public_finish:positions[2]] + text[project_finish:]
    if outside.strip():
        raise ValueError("AGENTS content exists outside the public/project zones")
    return text[positions[0]:public_finish], text[positions[2]:project_finish]


def _canonical(text: str, *, template: bool) -> str:
    if template:
        text = text.replace("{{PROJECT_NAME}}", "BridgeForgeCodex")
    parts = _zone_parts(text)
    if parts is None:
        raise ValueError("factory AGENTS must use public/project zone markers")
    return parts[0] + "\n<!-- project-zone -->\n"


def _contract_public_hashes(root: Path) -> set[str]:
    for path in (
        root / ".codex" / "managed-skeleton.json",
        root / "templates" / "managed-skeleton.json",
    ):
        if not path.is_file():
            continue
        try:
            contract = json.loads(path.read_text(encoding="utf-8-sig"))
            asset = next(item for item in contract["assets"] if item.get("id") == "root.agents")
            public = asset["agents_zones"]["public"]
            return {str(public["current_sha256"])}
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            continue
    return set()


def _public_hash(public: str, root: Path) -> str:
    normalized = PROJECT_NAME_CLONE_RE.sub(
        r"\1{{PROJECT_NAME}}\3{{PROJECT_NAME}}\4",
        public,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(normalized).hexdigest()


def _root_agents_issues(
    text: str,
    root: Path,
    *,
    label: str,
) -> list[str]:
    issues: list[str] = []
    try:
        parts = _zone_parts(text)
    except ValueError as exc:
        return [f"{label}: {exc}"]
    if parts is None:
        return [f"{label}: public/project zone markers are required"]
    public, project = parts
    try:
        public_headings = _visible_heading_positions(public, PUBLIC_REQUIRED_HEADINGS)
        project_headings = _visible_heading_positions(project, PROJECT_REQUIRED_HEADINGS)
    except ValueError as exc:
        return [f"{label}: {exc}"]
    for heading, positions_for_heading in public_headings.items():
        if len(positions_for_heading) != 1:
            issues.append(f"{label} public zone must contain exactly one {heading}")
    positions: list[int] = []
    for heading, positions_for_heading in project_headings.items():
        if len(positions_for_heading) != 1:
            issues.append(f"{label} project zone must contain exactly one {heading}")
        else:
            positions.append(positions_for_heading[0])
    if positions != sorted(positions):
        issues.append(f"{label} project zone headings are out of order")
    accepted = _contract_public_hashes(root)
    if not accepted:
        issues.append(
            f"{label} BridgeForge public zone cannot be verified because the "
            "managed contract is missing, invalid, or has no trusted public hash"
        )
    elif _public_hash(public, root) not in accepted:
        issues.append(
            f"{label} BridgeForge public zone was modified; move project constraints "
            "to the project zone and restore the official public block"
        )
    return issues


def _git_agents(root: Path, ref: str) -> str | None:
    object_name = ":AGENTS.md" if ref == "INDEX" else f"{ref}:AGENTS.md"
    result = subprocess.run(
        ["git", "show", object_name], cwd=root,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=10, check=False,
    )
    return result.stdout.replace("\r\n", "\n").replace("\r", "\n") if result.returncode == 0 else None


def instruction_source_issues(root: Path = ROOT) -> list[str]:
    issues: list[str] = []
    root_agents = root / "AGENTS.md"
    text, error = _read(root_agents, root)
    if error:
        return [error]
    assert text is not None
    issues.extend(_root_agents_issues(text, root, label="AGENTS.md"))
    has_zone_markers = any(marker in text for marker in ZONE_MARKERS)
    if has_zone_markers:
        for heading in FORBIDDEN_RULE_HEADINGS:
            if heading in text:
                issues.append(f"active Markdown rule index is forbidden: {heading}")
        if _claims_positive_autoload(text):
            issues.append("AGENTS.md claims unsupported Markdown paths auto-loading")
    for nested in sorted(root.rglob("AGENTS.md")):
        relative_parts = nested.relative_to(root).parts
        if (
            nested == root_agents
            or ".git" in relative_parts
            or ".runtime" in relative_parts
            or relative_parts[:2] == ("doc", "4_archive")
        ):
            continue
        nested_text, nested_error = _read(nested, root)
        if nested_error:
            issues.append(nested_error)
        elif nested_text and _claims_positive_autoload(nested_text):
            issues.append(f"{nested.relative_to(root)} claims unsupported Markdown paths auto-loading")
    template = root / "templates" / "AGENTS.md"
    if template.is_file():
        template_text, template_error = _read(template, root)
        if template_error:
            issues.append(template_error)
        elif template_text is not None:
            try:
                if _canonical(template_text, template=True) != _canonical(text, template=False):
                    issues.append("factory AGENTS public regions drift from templates/AGENTS.md")
            except ValueError as exc:
                issues.append(str(exc))
        for rule_dir in (root / "templates" / "rules", root / ".codex" / "rules"):
            if rule_dir.is_dir() and any(rule_dir.glob("*.md")):
                issues.append(f"factory Markdown rule directory must remain retired: {rule_dir.relative_to(root)}")
    return issues


def _staged_agents_issues(root: Path) -> list[str]:
    staged = _git_agents(root, "INDEX")
    if staged is None or staged == _git_agents(root, "HEAD"):
        return []
    return _root_agents_issues(
        staged,
        root,
        label="staged AGENTS.md",
    )


def main() -> int:
    post_edit = "--post-edit" in sys.argv
    issues = instruction_source_issues()
    if not post_edit:
        issues.extend(_staged_agents_issues(ROOT))
    for issue in issues:
        print(f"[instruction-source] {issue}", file=sys.stderr)
    return 0 if post_edit or not issues else 2


if __name__ == "__main__":
    raise SystemExit(main())
