#!/usr/bin/env python3
"""Factory dogfood drift check for hooks and native AGENTS regions.

判据分级(AGENTS.md §1 第4问 dogfood 红线 + 设计 D8-M1):
  · 无 templates/hooks/ 目录(下游 clone 项目) → 自门控 no-op exit 0。
  · **缺文件**(templates/hooks/ 有某 .py 但 .codex/hooks/ 无对应) → **exit 2 硬拦**
    (二值确定、近零误伤; dogfood 核心承诺 = 发给下游的 hook 自己也必须装)。
  · **正文差异**(归一化 .venv↔系统 python 前缀后逐字不一致) → 只 stderr 软提示、**放行 exit 0**
    (dogfood 合法差异不止 python 前缀[路径分隔/dev 注释措辞等], 逐字一致当硬闸只要一处
     没覆盖就误伤 —— 踩 antifabrication-framework 否 C1 的坑; 故正文差异降软)。

豁免(仅作用于缺文件硬拦): staged CHANGELOG.md 顶部当条含 `[dogfood-exempt: <hook> <因>]`
  —— pre-commit 在 commit message 生成之前触发, 读不到 message, 只能读已 staged 的 CHANGELOG。

原生指令契约:
  · 根 AGENTS.md 的 BridgeForge 公共区必须与 templates/AGENTS.md
    渲染结果一致；项目级专区由项目完全所有。
  · 工厂不得重新引入 Markdown path-rule；工厂发布红线必须在根 AGENTS 自定义区。
  · --post-edit 只报告、exit 0；pre-commit/default 报告并 exit 2。
  · 无 templates/hooks/ 的普通下游项目自门控 no-op。
"""
from __future__ import annotations

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
TEMPLATES_HOOKS = REPO_ROOT / "templates" / "hooks"
SELF_HOOKS = REPO_ROOT / ".codex" / "hooks"

PUBLIC_BEGIN = "<!-- BRIDGEFORGE:PUBLIC:BEGIN -->"
PUBLIC_END = "<!-- BRIDGEFORGE:PUBLIC:END -->"
PROJECT_BEGIN = "<!-- BRIDGEFORGE:PROJECT:BEGIN -->"
PROJECT_END = "<!-- BRIDGEFORGE:PROJECT:END -->"
FACTORY_SENTINELS = (
    "受管资产必须使用显式 target",
    "safe/risk/gap 计划必须在 apply 前重算 aggregate fingerprint",
    "发布前必须通过 factory dogfood",
)

# 归一化: 抹平 dev(.venv) 与下游(系统 python) 的解释器路径差异, 只留正文比对。
# 最长最具体的 token 先替换, 避免 "python3" 被 "python" 切成 "<PY>3"。
_PY_TOKENS = (".venv/Scripts/python.exe", ".venv/bin/python", "python3", "python")


def _normalize(text: str) -> str:
    out = text.replace("\r\n", "\n")
    for tok in _PY_TOKENS:
        out = out.replace(tok, "<PY>")
    return out


def _read_common_text(path: Path) -> tuple[str | None, str | None]:
    try:
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            return None, f"{path.relative_to(REPO_ROOT)} contains UTF-8 BOM"
        return raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n"), None
    except Exception as exc:
        return None, f"cannot read {path.relative_to(REPO_ROOT)}: {exc}"


def _markdown_section_bounds(
    text: str,
    heading: str,
) -> tuple[tuple[int, int] | None, str | None]:
    lines = text.splitlines(keepends=True)
    matches = [index for index, line in enumerate(lines) if line.rstrip("\n") == heading]
    if len(matches) != 1:
        return None, f"AGENTS heading must appear exactly once: {heading}"
    start = matches[0]
    level = len(heading) - len(heading.lstrip("#"))
    end = len(lines)
    for index in range(start + 1, len(lines)):
        candidate = lines[index]
        if not candidate.startswith("#"):
            continue
        candidate_level = len(candidate) - len(candidate.lstrip("#"))
        if candidate_level <= level and candidate[candidate_level:candidate_level + 1] == " ":
            end = index
            break
    return (start, end), None


def _mask_markdown_section(text: str, heading: str, marker: str) -> tuple[str, str | None]:
    lines = text.splitlines(keepends=True)
    bounds, issue = _markdown_section_bounds(text, heading)
    if issue or bounds is None:
        return text, issue
    start, end = bounds
    replacement = [lines[start], f"\n<!-- {marker} -->\n"]
    return "".join(lines[:start] + replacement + lines[end:]), None


def _canonical_agents(text: str, *, factory: bool) -> tuple[str | None, list[str]]:
    rendered = text
    if not factory:
        rendered = rendered.replace("{{PROJECT_NAME}}", "BridgeForgeCodex")
    markers = (PUBLIC_BEGIN, PUBLIC_END, PROJECT_BEGIN, PROJECT_END)
    if any(rendered.count(marker) != 1 for marker in markers):
        return None, ["AGENTS zone markers must each appear exactly once"]
    positions = tuple(rendered.index(marker) for marker in markers)
    if positions != tuple(sorted(positions)):
        return None, ["AGENTS zone markers are reversed or nested"]
    public_finish = rendered.find("\n", positions[1])
    project_finish = rendered.find("\n", positions[3])
    public_finish = len(rendered) if public_finish < 0 else public_finish + 1
    project_finish = len(rendered) if project_finish < 0 else project_finish + 1
    outside = (
        rendered[:positions[0]]
        + rendered[public_finish:positions[2]]
        + rendered[project_finish:]
    )
    if outside.strip():
        return None, ["AGENTS content exists outside public/project zones"]
    return rendered[positions[0]:public_finish] + "\n<!-- project-zone -->\n", []


def factory_dogfood_issues() -> list[str]:
    """Return exact common-baseline violations; no writes are performed."""
    if not TEMPLATES_HOOKS.is_dir():
        return []

    issues: list[str] = []

    template_agents, template_error = _read_common_text(REPO_ROOT / "templates" / "AGENTS.md")
    root_agents, root_error = _read_common_text(REPO_ROOT / "AGENTS.md")
    if template_error:
        issues.append(template_error)
    if root_error:
        issues.append(root_error)
    if template_agents is not None and root_agents is not None:
        expected, expected_issues = _canonical_agents(template_agents, factory=False)
        actual, actual_issues = _canonical_agents(root_agents, factory=True)
        issues.extend(expected_issues)
        issues.extend(actual_issues)
        if expected is not None and actual is not None and expected != actual:
            issues.append("AGENTS common regions drift from rendered templates/AGENTS.md")
        if any(sentinel not in root_agents for sentinel in FACTORY_SENTINELS):
            issues.append("factory AGENTS custom section is missing required release redlines")
    for rule_dir in (REPO_ROOT / "templates" / "rules", REPO_ROOT / ".codex" / "rules"):
        if rule_dir.exists() and any(rule_dir.glob("*.md")):
            issues.append(f"Markdown path-rule directory must remain retired: {rule_dir.relative_to(REPO_ROOT)}")
    return issues


def _git_show(ref: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "show", ref], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10,
        )
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def _exempt_hooks() -> set[str]:
    """staged CHANGELOG.md 顶部当条声明的 [dogfood-exempt: <hook> ...] 免检 hook 名集合。"""
    content = _git_show(":CHANGELOG.md")
    if not content:
        return set()
    head = "\n".join(content.splitlines()[:40])
    return {m.strip() for m in re.findall(r"\[dogfood-exempt:\s*([^\s\]]+)", head)}


def main() -> int:
    post_edit = "--post-edit" in sys.argv
    try:
        # 自门控: 无 templates/hooks/(下游项目) → no-op
        if not TEMPLATES_HOOKS.is_dir():
            return 0

        exempt = _exempt_hooks()
        missing: list[str] = []
        drift: list[str] = []
        for src in sorted(TEMPLATES_HOOKS.glob("*.py")):
            name = src.name
            if name in exempt:
                continue
            dst = SELF_HOOKS / name
            if not dst.is_file():
                missing.append(name)
                continue
            try:
                a = _normalize(src.read_text(encoding="utf-8"))
                b = _normalize(dst.read_text(encoding="utf-8"))
                if a != b:
                    drift.append(name)
            except Exception:
                continue  # 读失败不当漂移(宁漏不误伤)

        # Hook 正文差异沿用既有软提示契约。
        if drift:
            print("[mirror-drift] 以下 hook 正文疑似漂移(templates ↔ .codex, 已归一化 python 前缀), 请核对:", file=sys.stderr)
            for n in drift:
                print(f"[mirror-drift]   {n}", file=sys.stderr)
            print("[mirror-drift] (仅提示不阻断; 若确为合法差异可忽略)", file=sys.stderr)

        common_issues = factory_dogfood_issues()
        if common_issues:
            mode = "编辑后提示" if post_edit else "硬拦"
            print(f"[factory-dogfood] {mode}: Template 公共基线与工厂镜像不一致:", file=sys.stderr)
            for issue in common_issues:
                print(f"[factory-dogfood]   {issue}", file=sys.stderr)
            print("[factory-dogfood] 只报告不覆盖；请在同一修改中恢复精确一致。", file=sys.stderr)

        # 缺文件和公共基线漂移: 编辑后只提示，pre-commit/default 硬拦。
        if missing:
            print("[mirror-drift] pre-commit 硬拦: 产品层 hook 缺自身镜像(dogfood 欠账), 提交被阻断:", file=sys.stderr)
            for n in missing:
                print(f"[mirror-drift]   templates/hooks/{n} 缺对应 .codex/hooks/{n}", file=sys.stderr)
            print("[mirror-drift] 修法: 把缺的 hook 镜像进 .codex/hooks/(自身用系统 python 前缀),", file=sys.stderr)
            print("[mirror-drift]   或 CHANGELOG.md 顶部当条加 [dogfood-exempt: <hook> <因>] 豁免(仅纯下游场景 hook).", file=sys.stderr)
        if missing or common_issues:
            return 0 if post_edit else 2
        return 0
    except Exception as exc:
        print(f"[factory-dogfood] checker failure: {exc}", file=sys.stderr)
        return 0 if post_edit else 2


if __name__ == "__main__":
    sys.exit(main())
