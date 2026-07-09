#!/usr/bin/env python3
"""pre-commit hook: reject UTF-8 BOM in BridgeForge text surfaces."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BOM = b"\xef\xbb\xbf"
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


def _iter_candidates() -> list[Path]:
    files: list[Path] = []
    for root in ROOTS:
        path = REPO_ROOT / root
        if not path.exists():
            continue
        if path.is_file():
            if _is_text_surface(path):
                files.append(path)
            continue
        for child in path.rglob("*"):
            if child.is_file() and _is_text_surface(child):
                files.append(child)
    return sorted(set(files))


def main() -> int:
    try:
        bad: list[str] = []
        for path in _iter_candidates():
            try:
                if path.read_bytes().startswith(BOM):
                    bad.append(path.relative_to(REPO_ROOT).as_posix())
            except Exception:
                continue

        if not bad:
            return 0

        print("[encoding] pre-commit hard gate: UTF-8 BOM is forbidden", file=sys.stderr)
        for rel in bad:
            print(f"[encoding]   {rel}", file=sys.stderr)
        print("[encoding] Fix: save these files as UTF-8 without BOM.", file=sys.stderr)
        return 2
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
