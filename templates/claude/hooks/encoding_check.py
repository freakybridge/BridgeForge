#!/usr/bin/env python3
"""Encoding guard for BridgeForge text surfaces.

Hard blocks UTF-8 BOM. Also detects likely irreversible garbling such as long
question-mark runs and U+FFFD replacement characters in recently edited or
staged text files.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BOM = b"\xef\xbb\xbf"
GARBLE_RE = re.compile(r"\?{3,}|\ufffd")
TEXT_SUFFIXES = {
    ".md",
    ".json",
    ".py",
    ".toml",
    ".sh",
    ".ps1",
    ".yml",
    ".yaml",
    ".txt",
}
TEXT_NAMES = {
    "AGENTS.md",
    "CLAUDE.md",
    "CHANGELOG.md",
    "INSTALL.md",
    "README.md",
    "RETIRED.md",
    "SKILL.md",
    "VERSION",
    "pre-commit",
}
ROOTS = (
    "templates",
    "skills",
    "scripts",
    ".githooks",
    ".claude",
    ".codex",
    "doc",
    "README.md",
    "INSTALL.md",
    "SKILL.md",
    "CHANGELOG.md",
    "VERSION",
    "AGENTS.md",
    "CLAUDE.md",
)


def _is_text_surface(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES or path.name in TEXT_NAMES


def _under_repo(path: Path) -> bool:
    try:
        path.resolve().relative_to(REPO_ROOT.resolve())
        return True
    except ValueError:
        return False


def _iter_text_paths(roots: list[str] | None = None) -> list[Path]:
    files: list[Path] = []
    selected = roots if roots else list(ROOTS)
    for root in selected:
        path = (REPO_ROOT / root).resolve()
        if not _under_repo(path) or not path.exists():
            continue
        if path.is_file():
            if _is_text_surface(path):
                files.append(path)
            continue
        for child in path.rglob("*"):
            if child.is_file() and _is_text_surface(child):
                files.append(child)
    return sorted(set(files))


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _payload_file_paths(payload: object) -> list[Path]:
    if not isinstance(payload, dict):
        return []
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = payload

    paths: list[Path] = []
    for key in ("file_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            paths.append((REPO_ROOT / value).resolve())
    return [path for path in paths if _under_repo(path) and path.exists() and _is_text_surface(path)]


def _hook_file_paths() -> list[Path]:
    raw = ""
    try:
        raw = sys.stdin.read()
    except Exception:
        pass
    candidates = [raw]
    candidates.extend(os.environ.get(name, "") for name in ("CODEX_TOOL_INPUT", "CLAUDE_TOOL_INPUT"))

    paths: list[Path] = []
    for item in candidates:
        if not item or not item.strip():
            continue
        try:
            paths.extend(_payload_file_paths(json.loads(item)))
        except Exception:
            continue
    return sorted(set(paths))


def _staged_text_paths() -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []

    paths: list[Path] = []
    for line in result.stdout.splitlines():
        path = (REPO_ROOT / line.strip()).resolve()
        if _under_repo(path) and path.exists() and _is_text_surface(path):
            paths.append(path)
    return sorted(set(paths))


def _bom_hits(paths: list[Path]) -> list[str]:
    bad: list[str] = []
    for path in paths:
        try:
            if path.read_bytes().startswith(BOM):
                bad.append(_rel(path))
        except Exception:
            continue
    return bad


def _garble_hits(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            match = GARBLE_RE.search(line)
            if not match:
                continue
            snippet = line.strip()
            if len(snippet) > 120:
                snippet = snippet[:117] + "..."
            hits.append(f"{_rel(path)}:{lineno}: {snippet}")
    return hits


def _print_bom_hits(bad: list[str]) -> None:
    print("[encoding] hard gate: UTF-8 BOM is forbidden", file=sys.stderr)
    for rel in bad:
        print(f"[encoding]   {rel}", file=sys.stderr)
    print("[encoding] Fix: save these files as UTF-8 without BOM.", file=sys.stderr)


def _print_garble_hits(hits: list[str]) -> None:
    print("[encoding] suspicious replacement text detected", file=sys.stderr)
    for hit in hits:
        print(f"[encoding]   {hit}", file=sys.stderr)
    print(
        "[encoding] Stop and confirm the original text; automatic repair is unsafe.",
        file=sys.stderr,
    )


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--pre-commit", action="store_true")
    parser.add_argument("--scan-garble", action="store_true")
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()

    try:
        all_candidates = _iter_text_paths()
        bom_bad = _bom_hits(all_candidates)
        if bom_bad:
            _print_bom_hits(bom_bad)
            return 2

        if args.scan_garble:
            scan_paths = _iter_text_paths(args.paths or None)
            garble_bad = _garble_hits(scan_paths)
            if garble_bad:
                _print_garble_hits(garble_bad)
                return 2
            return 0

        if args.pre_commit:
            garble_bad = _garble_hits(_staged_text_paths())
            if garble_bad:
                _print_garble_hits(garble_bad)
                return 2
            return 0

        edited_paths = _hook_file_paths()
        if edited_paths:
            garble_bad = _garble_hits(edited_paths)
            if garble_bad:
                _print_garble_hits(garble_bad)
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
