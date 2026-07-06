#!/usr/bin/env python3
"""校验 CLAUDE.md §2 规则索引 ↔ `.claude/rules/*.md` 一致性 — 双层:
  · PostToolUse(Edit|Write): 编辑瞬间软提醒(exit 0, 不阻塞)
  · pre-commit(--pre-commit): 死链/漏索引硬拦(exit 2)

**读法 = 以工作树为准(非 staged blob)**：本检查本质是「CLAUDE.md 索引 ↔ 整个 rules 目录」的
集合一致性比对(跨多文件)。纯 staged 只能看到 diff 子集, 会漏「只 stage 了 CLAUDE.md、
rule 文件在工作树已增删但没 stage」的死链/未索引。故以工作树为准 ——
**局限: 部分暂存(工作树与 index 不一致)时可能误报**; 误报可用 CHANGELOG 顶部 [skip-rule-size] 豁免。

自门控: 无 CLAUDE.md 或无 `.claude/rules/` 时直接放行(下游未建 rules 目录 = 恒 no-op)。
pre-commit 脚本自身异常一律 exit 0(宁漏不误伤)。
"""
from __future__ import annotations

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


def _detect() -> tuple[list[str], list[str]] | None:
    """以工作树为准比对 CLAUDE.md §2 索引 ↔ .claude/rules/*.md。

    返回 (missing, unlisted): missing=索引列了但文件不存在; unlisted=文件存在但没索引。
    返回 None = 自门控放行(无 CLAUDE.md 或无 .claude/rules/ 目录)。
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    claude_md = repo_root / "CLAUDE.md"
    rules_dir = repo_root / ".claude" / "rules"
    if not (claude_md.exists() and rules_dir.exists()):
        return None

    text = claude_md.read_text(encoding="utf-8")
    # 先剔除 HTML 注释块, 避免占位示例(如 `<!-- rules/foo.md -->`)被误判为真实索引条目。
    # 注意: 用"内容不含 <!--/-->"约束匹配跨度(而非简单非贪婪 .*?), 防止未闭合的
    # `<!--` 跨越吞掉中间真实索引行、级联误判成 unlisted(对抗测试实测坐实的边界漏洞)。
    text = re.sub(r"<!--(?:(?!<!--|-->).)*-->", "", text, flags=re.DOTALL)
    # 捕获 `rules/xxx.md` 形式的路径引用。F4: `[a-z_]`→`[\w-]` 放宽,
    # 否则 `gateway-v2.md`(含 `-`/数字)恒判 unlisted 误伤。
    listed = set(re.findall(r"rules/([\w-]+\.md)", text))
    actual = {p.name for p in rules_dir.glob("*.md")}

    missing = sorted(listed - actual)   # CLAUDE.md 列了但文件不存在
    unlisted = sorted(actual - listed)  # 文件存在但 CLAUDE.md 没列
    return missing, unlisted


def _git_show(ref: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "show", ref], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10,
        )
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def _changelog_skip() -> bool:
    """staged CHANGELOG.md 顶部当条含 `[skip-rule-size]` 即豁免(与 rule_size 同一逃生舱)。"""
    content = _git_show(":CHANGELOG.md")
    if not content:
        return False
    head = "\n".join(content.splitlines()[:40])
    return "[skip-rule-size]" in head


def pre_commit() -> int:
    """pre-commit 硬拦: 死链/漏索引 → stderr + exit 2; 自门控/异常/豁免 → exit 0。"""
    try:
        if _changelog_skip():
            return 0
        res = _detect()
        if res is None:
            return 0  # 无 rules 目录 → 恒 no-op
        missing, unlisted = res
        if not (missing or unlisted):
            return 0
        print("[rule-index] pre-commit 硬拦: CLAUDE.md §2 索引 ↔ .claude/rules/ 不一致, 提交被阻断", file=sys.stderr)
        if missing:
            print(f"[rule-index]   死链({len(missing)}): {', '.join(missing)} — 去 CLAUDE.md §2 删掉这些行(或补回文件)", file=sys.stderr)
        if unlisted:
            print(f"[rule-index]   未索引({len(unlisted)}): {', '.join(unlisted)} — 去 CLAUDE.md §2 各加一行索引(或删文件)", file=sys.stderr)
        print("[rule-index] 修好再提交, 或 CHANGELOG.md 顶部加 [skip-rule-size] 豁免本次", file=sys.stderr)
        return 2
    except Exception:
        return 0  # 脚本自身异常一律放行


def main() -> int:
    if "--pre-commit" in sys.argv:
        return pre_commit()

    # ── PostToolUse 软提醒(exit 0) ──
    # 输入双兜底（与 requirements_check.py 一致）：官方 PostToolUse 走 stdin JSON，
    # file_path 嵌在 `tool_input` 下；老 hook 走环境变量 CLAUDE_TOOL_INPUT。
    # 只读 env-var 会在「CC 仅走 stdin、不设该 env」时永不触发，故两路都试。
    tool_input: dict = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            ti = json.loads(raw).get("tool_input")
            if isinstance(ti, dict):
                tool_input = ti
    except Exception:
        tool_input = {}
    if not tool_input:
        try:
            tool_input = json.loads(os.environ.get("CLAUDE_TOOL_INPUT", "{}"))
        except Exception:
            return 0
    if not isinstance(tool_input, dict):
        return 0
    f = tool_input.get("file_path", "").replace("\\", "/")
    if not (".claude/rules" in f or f.endswith("CLAUDE.md")):
        return 0

    res = _detect()
    if res is None:
        return 0
    missing, unlisted = res

    issues: list[str] = []
    if missing:
        issues.append(f"CLAUDE.md 死链接（{len(missing)}）: {', '.join(missing)}")
    if unlisted:
        issues.append(f"rule 文件未加索引（{len(unlisted)}）: {', '.join(unlisted)}")

    if issues:
        print("[rule_index_check 发现问题]", file=sys.stderr)
        for i in issues:
            print(f"  - {i}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
