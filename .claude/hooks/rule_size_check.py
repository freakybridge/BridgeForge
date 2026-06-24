"""PostToolUse hook: rule 文件大小红线检查。

机制:
1. 仅对编辑 `.claude/rules/*.md` 的 Edit/Write 工具调用触发
2. 检查文件大小 + 行数 + 案例越界信号(版本号/日期/长 code 块)
3. 跨阈值输出 [rule-size] 警告到 stdout, Claude 看见后按 meta_rule_design.md
   §5 (量化红线) + §6 (维护节奏) 评估是否需要拆 path-specific 或下沉案例

阈值(对齐 meta_rule_design.md §5):
- 单 rule ≤ 50 KB / ≤ 500 行
- 版本号(v\\d+\\.\\d+\\.\\d+) > 5 处 → 案例越界信号
- 日期(YYYY-MM-DD) > 8 处 → 案例越界信号
- 长 code 块(> 20 行) > 2 个 → 示例过多
- 触发器(frontmatter paths)单段目录通配(a/**)或裸 ** → 伪常驻

非阻塞(exit 0), 只提醒。

详见 .claude/rules/meta_rule_design.md。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# 强制 stdout UTF-8 (Windows 默认 GBK 会乱码)
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
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


def check_rule(path: Path) -> list[str]:
    """检查单个 rule 文件, 返回违规列表(空表示合格)。"""
    violations: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return violations

    size_kb = path.stat().st_size // 1024
    lines = text.splitlines()
    line_count = len(lines)

    if size_kb > MAX_KB:
        violations.append(f"文件 {size_kb} KB > {MAX_KB} KB 红线 — 考虑拆 path-specific rule")
    if line_count > MAX_LINES:
        violations.append(f"行数 {line_count} > {MAX_LINES} 红线 — 案例下沉 memory 或拆分")

    ver_count = len(re.findall(r"v\d+\.\d+\.\d+", text))
    if ver_count > MAX_VERSIONS:
        violations.append(f"版本号引用 {ver_count} 处 > {MAX_VERSIONS} — 案例越界信号, 移 memory")

    date_count = len(re.findall(r"20\d{2}-\d{2}-\d{2}", text))
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
    if path.name not in CROSS_CUTTING_RULES:
        broad = [p for p in _frontmatter_paths(text) if BROAD_PATH_RE.match(p)]
        if broad:
            violations.append(
                f"触发器过宽 {broad} — 单段目录通配等同始终加载（伪常驻）, "
                f"收紧到具体子目录（≥2 段前缀如 a/b/**）或真红线进 CLAUDE.md"
            )

    return violations


def main() -> int:
    tool_input_raw = os.environ.get("CLAUDE_TOOL_INPUT", "{}")
    try:
        data = json.loads(tool_input_raw)
    except Exception:
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

    violations = check_rule(p)
    if not violations:
        return 0

    print(f"[rule-size] {p.name} 违反 meta_rule_design 量化红线:")
    for v in violations:
        print(f"[rule-size]   - {v}")
    print("[rule-size] 详见 .claude/rules/meta_rule_design.md §5 量化红线 + §6 维护节奏")
    return 0


if __name__ == "__main__":
    sys.exit(main())