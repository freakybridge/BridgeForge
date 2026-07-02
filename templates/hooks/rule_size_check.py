"""rule 文件大小红线检查 — 双层:
  · PostToolUse(Edit|Write): 编辑瞬间软提醒 [rule-size](exit 0, 不阻塞)
  · pre-commit(--pre-commit): 对 staged .claude/rules/*.md 硬拦(exit 2)

机制:
1. PostToolUse: 仅对编辑 `.claude/rules/*.md` 的 Edit/Write 触发, 读工作树内容跑 check_rule,
   跨阈值输出 [rule-size] 警告到 stdout(非阻塞)。
2. pre-commit: 对 `git diff --cached` 命中的 `.claude/rules/*.md`(排除 meta_rule_design.md),
   用 `git show :path` 读 **staged blob** 内容跑 check_rule —— 体积/行数按"这次真要提交的内容"
   精确判定, 把"工作树脏改没 stage"的误伤降到零。违规 → stderr 列清单 + exit 2。
   脚本自身异常一律 exit 0(宁漏不误伤); 豁免走 CHANGELOG.md 顶部 `[skip-rule-size]`
   (pre-commit 在 commit message 生成前触发, 只能读已 staged 的 CHANGELOG, 不能读 message)。

阈值(对齐 meta_rule_design.md §5):
- 单 rule ≤ 50 KB / ≤ 500 行
- 版本号(v\\d+\\.\\d+\\.\\d+) > 5 处 → 案例越界信号
- 日期(YYYY-MM-DD) > 8 处 → 案例越界信号
- 长 code 块(> 20 行) > 2 个 → 示例过多
- 触发器(frontmatter paths)单段目录通配(a/**)或裸 ** → 伪常驻

详见 .claude/rules/meta_rule_design.md。
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# 强制 stdout/stderr UTF-8 (Windows 默认 GBK 会乱码)
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

# 阈值
MAX_KB = 50
MAX_LINES = 500
MAX_VERSIONS = 5
MAX_DATES = 8
MAX_LONG_CODE_BLOCKS = 2
LONG_CODE_BLOCK_LINES = 20

# 触发器宽度：单段目录通配（如 `src/**`）覆盖整个顶层目录 = 伪常驻；裸 `**`/`*` 更宽。
# 通用启发式，不写死任何项目名。≥2 段前缀（如 `src/foo/**`）才算够窄。
BROAD_PATH_RE = re.compile(r"^(?:\*\*?|[^/]+/\*\*?|\*\*/\*)$")

# 横切/框架规则白名单：骨架自带的这几条规则宽触发器是**有意且合理**的——调试横切所有源码、
# 工作流横切 doc、架构/模块常驻、可移植性横切 .claude/config/libs。豁免触发器宽度检查，
# 否则 hook 对它们永久误报 → 训练人忽略 [rule-size] 信号（狼来了）。
# 显式列名（meta_rule §4.2），**禁用通配**——否则退化成「关掉这条 lint」。下游可按需增删。
# 注意：仅豁免触发器宽度，**不**豁免体积/行数/戳数检查（宽 ≠ 可以无限胖）。
# ⚠️ v0.39.0 起本检查是 pre-commit 硬闸（exit 2 拦提交）——此白名单门控的是硬拦而非软提醒，
# 增删条目前掂量误拦/漏拦后果（欠账 E-5 复议结论：KEEP，按硬闸白名单标准维护）。
CROSS_CUTTING_RULES = {
    "architecture.md", "modules.md", "debugging.md", "workflow.md", "portability.md",
}


def _frontmatter_paths(text: str) -> list[str]:
    """抽取 YAML frontmatter 里 `paths:` 列表的各 glob（不依赖 yaml 库）。"""
    if not text.startswith("---"):
        return []
    end = text.find("\n---", 3)
    if end == -1:
        return []
    fm = text[3:end]
    out: list[str] = []
    in_paths = False
    for line in fm.splitlines():
        stripped = line.strip()
        if stripped.startswith("paths:"):
            in_paths = True
            inline = stripped[len("paths:"):].strip()
            if inline.startswith("["):
                out.extend(re.findall(r'["\']([^"\']+)["\']', inline))
                in_paths = False
            continue
        if in_paths:
            if stripped.startswith("- "):
                out.append(stripped[2:].strip().strip("\"'"))
            elif stripped and not line.startswith((" ", "\t", "-")):
                in_paths = False
    return out


def check_rule(content: str, name: str) -> list[str]:
    """检查单个 rule 内容, 返回违规列表(空表示合格)。

    接收内容字符串(而非路径)以便 pre-commit 传 staged blob(`git show :path`)——
    体积按 content 的 UTF-8 字节数算, 与"这次真要提交的内容"精确一致。
    """
    violations: list[str] = []
    text = content

    size_kb = len(content.encode("utf-8")) // 1024
    lines = text.splitlines()
    line_count = len(lines)

    if size_kb > MAX_KB:
        violations.append(f"文件 {size_kb} KB > {MAX_KB} KB 红线 — 考虑拆 path-specific rule")
    if line_count > MAX_LINES:
        violations.append(f"行数 {line_count} > {MAX_LINES} 红线 — 案例下沉 memory 或拆分")

    # 版本号/日期计数前先剔除 HTML 注释块, 避免注释里的教学占位示例(如举例写了几个
    # v1.0.0/日期)被误计入"案例越界"信号, 与 rule_index_check.py 同一类误判(同一天实测坐实)。
    text_sans_comments = re.sub(r"<!--(?:(?!<!--|-->).)*-->", "", text, flags=re.DOTALL)

    ver_count = len(re.findall(r"v\d+\.\d+\.\d+", text_sans_comments))
    if ver_count > MAX_VERSIONS:
        violations.append(f"版本号引用 {ver_count} 处 > {MAX_VERSIONS} — 案例越界信号, 移 memory")

    date_count = len(re.findall(r"20\d{2}-\d{2}-\d{2}", text_sans_comments))
    if date_count > MAX_DATES:
        violations.append(f"日期引用 {date_count} 处 > {MAX_DATES} — 案例越界信号, 移 memory")

    # 长 code 块: ``` ... ``` 之间 > 20 行
    code_blocks = re.findall(r"```[\w]*\n(.*?)```", text, re.DOTALL)
    long_blocks = [b for b in code_blocks if b.count("\n") > LONG_CODE_BLOCK_LINES]
    if len(long_blocks) > MAX_LONG_CODE_BLOCKS:
        violations.append(
            f"长 code 块 (>{LONG_CODE_BLOCK_LINES} 行) {len(long_blocks)} 个 > {MAX_LONG_CODE_BLOCKS} — 示例移 doc/3_design/"
        )

    # 触发器宽度：单段目录通配 / 裸 ** = 伪常驻（meta_rule §4.2）。横切规则白名单豁免。
    if name not in CROSS_CUTTING_RULES:
        broad = [p for p in _frontmatter_paths(text) if BROAD_PATH_RE.match(p)]
        if broad:
            violations.append(
                f"触发器过宽 {broad} — 单段目录通配等同始终加载（伪常驻）, "
                f"收紧到具体子目录（≥2 段前缀如 a/b/**）或真红线进 CLAUDE.md"
            )

    return violations


# ── pre-commit 模式辅助 ──────────────────────────────────────────────

def _git_show(ref: str) -> str | None:
    """`git show <ref>` 的内容; 失败返回 None。"""
    try:
        r = subprocess.run(
            ["git", "show", ref], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10,
        )
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def _changelog_skip() -> bool:
    """staged CHANGELOG.md 顶部当条是否含 `[skip-rule-size]` 豁免标记。

    pre-commit 在 commit message 生成之前触发, `.git/COMMIT_EDITMSG` 尚未写入 →
    豁免只能读已 staged 的 CHANGELOG.md 顶部(取前 ~40 行覆盖最新一条 entry)。
    """
    content = _git_show(":CHANGELOG.md")
    if not content:
        return False
    head = "\n".join(content.splitlines()[:40])
    return "[skip-rule-size]" in head


def _staged_rule_files() -> list[str]:
    """git diff --cached 命中的 .claude/rules/*.md(排除 meta_rule_design.md)。"""
    try:
        r = subprocess.run(
            ["git", "diff", "--cached", "--name-only"], capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=10,
        )
        if r.returncode != 0:
            return []
        out: list[str] = []
        for line in r.stdout.splitlines():
            f = line.strip().replace("\\", "/")
            if (
                ".claude/rules/" in f
                and f.endswith(".md")
                and not f.endswith("meta_rule_design.md")
            ):
                out.append(f)
        return out
    except Exception:
        return []


def pre_commit() -> int:
    """pre-commit 硬拦: staged .claude/rules/*.md 读 staged blob 跑 check_rule。

    违规 → stderr 列清单 + exit 2; [skip-rule-size] 豁免 → exit 0;
    脚本自身异常一律 exit 0(宁漏不误伤)。
    """
    try:
        if _changelog_skip():
            return 0
        problems: list[tuple[str, list[str]]] = []
        for f in _staged_rule_files():
            content = _git_show(f":{f}")
            if content is None:
                continue  # 读不到 staged blob → 跳过, 不误伤
            name = f.rsplit("/", 1)[-1]
            v = check_rule(content, name)
            if v:
                problems.append((name, v))
        if problems:
            print("[rule-size] pre-commit 硬拦: 以下 rule 超 meta_rule_design 量化红线, 提交被阻断", file=sys.stderr)
            for name, vs in problems:
                for v in vs:
                    print(f"[rule-size]   {name}: {v}", file=sys.stderr)
            print("[rule-size] 修好再提交, 或在 CHANGELOG.md 顶部当条加 [skip-rule-size] 豁免本次", file=sys.stderr)
            return 2
        return 0
    except Exception:
        return 0  # 脚本自身异常一律放行, 质量闸绝不退化成误伤源


def main() -> int:
    if "--pre-commit" in sys.argv:
        return pre_commit()

    # ── PostToolUse 软提醒(exit 0) ──
    # 输入双兜底（与 requirements_check.py 一致）：官方 PostToolUse 走 stdin JSON，
    # file_path 嵌在 `tool_input` 下；老 hook 走环境变量 CLAUDE_TOOL_INPUT。
    # 只读 env-var 会在「CC 仅走 stdin、不设该 env」时永不触发，故两路都试。
    data: dict = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            ti = json.loads(raw).get("tool_input")
            if isinstance(ti, dict):
                data = ti
    except Exception:
        data = {}
    if not data:
        try:
            data = json.loads(os.environ.get("CLAUDE_TOOL_INPUT", "{}"))
        except Exception:
            return 0
    if not isinstance(data, dict):
        return 0

    file_path = data.get("file_path", "")
    if not file_path:
        return 0

    # 只关心 .claude/rules/*.md
    p = Path(file_path)
    if not (".claude" in p.parts and "rules" in p.parts and p.suffix == ".md"):
        return 0
    # 排除 meta_rule_design.md 自身(它讨论规则,允许偏长)
    if p.name == "meta_rule_design.md":
        return 0

    if not p.exists():
        return 0

    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return 0

    violations = check_rule(text, p.name)
    if not violations:
        return 0

    print(f"[rule-size] {p.name} 违反 meta_rule_design 量化红线:")
    for v in violations:
        print(f"[rule-size]   - {v}")
    print("[rule-size] 详见 .claude/rules/meta_rule_design.md §5 量化红线 + §6 维护节奏")
    return 0


if __name__ == "__main__":
    sys.exit(main())
