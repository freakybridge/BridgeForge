#!/usr/bin/env python3
"""Refresh the Claude/Codex harness parity report.

The report is intentionally advisory. It catches drift before git-sync, but it
does not try to decide every semantic difference automatically.
"""
from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    if (
        here.parent.name == "scripts"
        and here.parent.parent.name == "codex"
        and here.parent.parent.parent.name == "templates"
    ):
        return here.parents[3]
    return here.parents[2]


REPO_ROOT = _repo_root()
CLAUDE_ROOT = REPO_ROOT / "templates" / "claude"
CODEX_ROOT = REPO_ROOT / "templates" / "codex"
REPORT = REPO_ROOT / "docs" / "codex-harness-parity.md"

COMPARE_DIRS = ("hooks", "rules", "scripts")
CODEX_ONLY_EXPECTED = {
    "config.toml",
    "hooks/model_policy_check.py",
    "scripts/codex_git_sync.py",
    "scripts/harness_parity_check.py",
}

SKILL_SLASH_TO_DOLLAR = (
    "feature-dev",
    "archive-scan",
    "todo",
    "find-doc",
    "sync-docs",
    "snapshot",
    "resume",
    "git-sync",
    "spinoff",
    "focus",
    "escalate",
    "debate",
    "collab",
    "summary",
    "plan",
    "find-memory",
)

SUBSTITUTIONS: list[tuple[str, str]] = [
    ("templates/claude", "templates/codex"),
    (".claude", ".codex"),
    ("CLAUDE.md", "AGENTS.md"),
    ("CLAUDE", "AGENTS"),
    ("Claude Code", "Codex"),
    ("Claude", "Codex"),
    ("claude", "codex"),
]
SUBSTITUTIONS.extend((f"/{name}", f"${name}") for name in SKILL_SLASH_TO_DOLLAR)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _normalize_claude_text(text: str) -> str:
    for old, new in SUBSTITUTIONS:
        text = text.replace(old, new)
    return text


def _file_set(root: Path, subdir: str) -> set[str]:
    base = root / subdir
    if not base.is_dir():
        return set()
    return {p.name for p in base.iterdir() if p.is_file()}


def _diff_stats(claude_path: Path, codex_path: Path) -> tuple[int, int, int]:
    left = _normalize_claude_text(_read(claude_path)).splitlines()
    right = _read(codex_path).splitlines()
    diff = list(difflib.unified_diff(left, right, lineterm="", n=0))
    hunks = sum(1 for line in diff if line.startswith("@@"))
    removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
    added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    return hunks, removed, added


def _expected_codex_only() -> set[str]:
    expected = set(CODEX_ONLY_EXPECTED)
    agents = CODEX_ROOT / "agents"
    if agents.is_dir():
        expected.update(f"agents/{p.name}" for p in agents.iterdir() if p.is_file())
    return expected


def build_report() -> str | None:
    if not (CLAUDE_ROOT.is_dir() and CODEX_ROOT.is_dir()):
        return None

    expected_codex_only = _expected_codex_only()
    inventory_rows: list[str] = []
    diff_rows: list[str] = []
    missing_total = 0
    unexpected_total = 0

    for subdir in COMPARE_DIRS:
        claude_files = _file_set(CLAUDE_ROOT, subdir)
        codex_files = _file_set(CODEX_ROOT, subdir)
        missing = sorted(claude_files - codex_files)
        codex_only = sorted(codex_files - claude_files)
        unexpected = [name for name in codex_only if f"{subdir}/{name}" not in expected_codex_only]
        missing_total += len(missing)
        unexpected_total += len(unexpected)
        inventory_rows.append(
            f"| `{subdir}` | {len(claude_files)} | {len(codex_files)} | "
            f"{', '.join(f'`{x}`' for x in missing) or '-'} | "
            f"{', '.join(f'`{x}`' for x in codex_only) or '-'} |"
        )

        for name in sorted(claude_files & codex_files):
            hunks, removed, added = _diff_stats(CLAUDE_ROOT / subdir / name, CODEX_ROOT / subdir / name)
            if hunks:
                diff_rows.append(f"| `{subdir}/{name}` | {hunks} | -{removed} / +{added} | 待人工归类 |")

    for path in sorted(expected_codex_only):
        p = CODEX_ROOT / path
        if p.exists():
            continue
        unexpected_total += 1
        diff_rows.append(f"| `{path}` | - | - | 期望的 Codex 专属文件缺失 |")

    status = "OK" if missing_total == 0 and unexpected_total == 0 and not diff_rows else "REVIEW"
    lines = [
        "# Codex Harness Parity Report",
        "",
        "> 自动生成：`.codex/scripts/harness_parity_check.py`。本报告用于 git-sync 前维护 Claude/Codex harness 对照清单。",
        "",
        "## Summary",
        "",
        f"- 状态：`{status}`",
        f"- Claude 有但 Codex 缺失：{missing_total}",
        f"- 未登记的 Codex-only 文件：{unexpected_total}",
        f"- 归一化后仍有差异的同名文件：{len(diff_rows)}",
        "",
        "## Inventory",
        "",
        "| 层 | Claude 文件数 | Codex 文件数 | Codex 缺失 | Codex-only |",
        "|---|---:|---:|---|---|",
        *inventory_rows,
        "",
        "## Normalized Diffs",
        "",
        "归一化规则只处理确定的壳差异：`.claude` -> `.codex`、`CLAUDE.md` -> `AGENTS.md`、普通 `$skill` 入口等。`/bridgeforge` 不归一化，因为 Codex 与 Claude 已统一使用 slash 入口。",
        "",
        "| 文件 | diff hunk | 行变化 | 结论 |",
        "|---|---:|---:|---|",
    ]
    if diff_rows:
        lines.extend(diff_rows)
    else:
        lines.append("| - | 0 | 0 | 无 |")
    lines.extend(
        [
            "",
            "## 使用约定",
            "",
            "- `Codex 缺失` 默认需要补齐，除非有明确豁免原因。",
            "- `Codex-only` 必须登记为专属能力，例如模型路由、Codex git-sync 执行器。",
            "- `Normalized Diffs` 只提示差异，不自动判错；改动前先判断是应对齐、Codex 专属，还是文案残留。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Exit 2 if the report is stale.")
    parser.add_argument("--no-write", action="store_true", help="Print the report instead of writing it.")
    args = parser.parse_args()

    report = build_report()
    if report is None:
        return 0

    if args.no_write:
        print(report, end="")
        return 0

    old = REPORT.read_text(encoding="utf-8") if REPORT.exists() else None
    if args.check and old != report:
        print(f"[harness-parity] report stale: {REPORT}", file=sys.stderr)
        return 2

    if old != report:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(report, encoding="utf-8")
        print(f"[harness-parity] refreshed {REPORT.relative_to(REPO_ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
