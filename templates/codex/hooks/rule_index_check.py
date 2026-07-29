#!/usr/bin/env python3
"""校验 AGENTS.md §2 规则索引 ↔ `.codex/rules/*.md` 一致性 — 双层:
  · PostToolUse(Edit|Write): 编辑瞬间软提醒(exit 0, 不阻塞)
  · pre-commit(--pre-commit): 死链/漏索引硬拦(exit 2)

**读法 = 以工作树为准(非 staged blob)**：本检查本质是「AGENTS.md 索引 ↔ 整个 rules 目录」的
集合一致性比对(跨多文件)。纯 staged 只能看到 diff 子集, 会漏「只 stage 了 AGENTS.md、
rule 文件在工作树已增删但没 stage」的死链/未索引。故以工作树为准 ——
**局限: 部分暂存(工作树与 index 不一致)时可能误报**; pre-commit 误报可用 CHANGELOG 顶部 [skip-rule-size] 豁免。

自门控: 无 AGENTS.md 或无 `.codex/rules/` 时直接放行(下游未建 rules 目录 = 恒 no-op)。
pre-commit 脚本自身异常一律 exit 0(宁漏不误伤)。

`--audit-all` 是供 CI 与人工调用的只读全量入口：它与 pre-commit 使用相同的索引
作用域，但不接受 `[skip-rule-size]` 豁免，确保审计结果可复现。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


INDEX_HEADING = "## 2. 规则文件索引"


class IndexSectionError(ValueError):
    """入口文件缺少可机器识别的规则索引章节。"""

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


def _index_section(text: str) -> str:
    """返回唯一受支持的规则索引章节，拒绝从入口全文猜测。"""
    text = re.sub(r"<!--(?:(?!<!--|-->).)*-->", "", text, flags=re.DOTALL)
    section = re.search(
        rf"(?ms)^{re.escape(INDEX_HEADING)}[ \t]*\r?\n(.*?)(?=^##\s|\Z)",
        text,
    )
    if section is None:
        raise IndexSectionError(f"未找到明确的“{INDEX_HEADING}”章节")
    return section.group(1)


def _detect() -> tuple[list[str], list[str]] | None:
    """以工作树为准比对 AGENTS.md §2 索引 ↔ .codex/rules/*.md。

    返回 (missing, unlisted): missing=索引列了但文件不存在; unlisted=文件存在但没索引。
    返回 None = 自门控放行(无 AGENTS.md 或无 .codex/rules/ 目录)。
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    entry_md = repo_root / "AGENTS.md"
    rules_dir = repo_root / ".codex" / "rules"
    if not (entry_md.exists() and rules_dir.exists()):
        return None

    text = _index_section(entry_md.read_text(encoding="utf-8"))
    # 捕获 `rules/xxx.md` 形式的路径引用。F4: `[a-z_]`→`[\w-]` 放宽,
    # 否则 `gateway-v2.md`(含 `-`/数字)恒判 unlisted 误伤。
    listed = set(re.findall(r"rules/([\w-]+\.md)", text))
    actual = {p.name for p in rules_dir.glob("*.md")}

    missing = sorted(listed - actual)   # AGENTS.md 列了但文件不存在
    unlisted = sorted(actual - listed)  # 文件存在但 AGENTS.md 没列
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


def _hard_check(mode: str, *, allow_skip: bool) -> int:
    """运行索引硬检查；配置异常阻断，脚本异常保守放行并诊断。"""
    try:
        if allow_skip and _changelog_skip():
            return 0
        res = _detect()
        if res is None:
            return 0  # 无 rules 目录 → 恒 no-op
    except IndexSectionError as exc:
        print(f"[rule-index] {mode} 阻断: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"[rule-index] {mode} 脚本异常，保守放行: {exc}", file=sys.stderr)
        return 0

    missing, unlisted = res
    if not (missing or unlisted):
        return 0
    print(
        "[rule-index] "
        f"{mode} 硬拦: AGENTS.md §2 索引 ↔ .codex/rules/ 不一致, 提交被阻断",
        file=sys.stderr,
    )
    if missing:
        print(f"[rule-index]   死链({len(missing)}): {', '.join(missing)} — 去 AGENTS.md §2 删掉这些行(或补回文件)", file=sys.stderr)
    if unlisted:
        print(f"[rule-index]   未索引({len(unlisted)}): {', '.join(unlisted)} — 去 AGENTS.md §2 各加一行索引(或删文件)", file=sys.stderr)
    if allow_skip:
        print("[rule-index] 修好再提交, 或 CHANGELOG.md 顶部加 [skip-rule-size] 豁免本次", file=sys.stderr)
    return 2


def pre_commit() -> int:
    """pre-commit 硬拦；保留既有的部分暂存豁免。"""
    return _hard_check("pre-commit", allow_skip=True)


def audit_all() -> int:
    """只读全量审计；不允许借用 rule-size 豁免掩盖索引问题。"""
    return _hard_check("audit", allow_skip=False)


def main() -> int:
    if "--audit-all" in sys.argv:
        return audit_all()
    if "--pre-commit" in sys.argv:
        return pre_commit()

    # ── PostToolUse 软提醒(exit 0) ──
    # 输入双兜底（与 requirements_check.py 一致）：官方 Codex hook 走 stdin JSON，
    # file_path 嵌在 `tool_input` 下；环境变量只作兼容兜底，优先 CODEX_TOOL_INPUT，
    # CLAUDE_TOOL_INPUT 仅保留给旧导入配置。
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
            env_raw = os.environ.get("CODEX_TOOL_INPUT") or os.environ.get("CLAUDE_TOOL_INPUT", "{}")
            tool_input = json.loads(env_raw)
        except Exception:
            return 0
    if not isinstance(tool_input, dict):
        return 0
    f = tool_input.get("file_path", "").replace("\\", "/")
    if not (".codex/rules" in f or f.endswith("AGENTS.md")):
        return 0

    try:
        res = _detect()
    except IndexSectionError as exc:
        print(f"[rule_index_check 发现问题] {exc}", file=sys.stderr)
        return 0
    except Exception as exc:
        print(f"[rule_index_check 脚本异常，保守放行] {exc}", file=sys.stderr)
        return 0
    if res is None:
        return 0
    missing, unlisted = res

    issues: list[str] = []
    if missing:
        issues.append(f"AGENTS.md 死链接（{len(missing)}）: {', '.join(missing)}")
    if unlisted:
        issues.append(f"rule 文件未加索引（{len(unlisted)}）: {', '.join(unlisted)}")

    if issues:
        print("[rule_index_check 发现问题]", file=sys.stderr)
        for i in issues:
            print(f"  - {i}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
