#!/usr/bin/env python3
"""antifab-deny-hook.py — C1「确证不存在则硬 deny」参考脚本（**非出厂 hook**）

定位：防 AI 幻觉资源四层框架的 L4 兜底（详见 ../antifabrication-framework.md §3）。
agent 真去读「能解析出路径、且确证不存在」的资源那一刻，事中返回 **deny（硬拦）**，
并把「正确资源在哪」（REAL_SOURCE_HINT）投喂回去——deny 不是 warn，因为 agent 连系统
硬 FileNotFoundError 都刹不住，更软的提醒只会更没用。

⚠️ 这是 docs/examples 下的**参考实现，不被骨架 settings.json 注册、不会自动运行**。
   经两轮 debate 裁决：C1 不进 templates/hooks/（理由见框架文档 §3——空 hint 近零价值 +
   误伤是硬停 + dogfood 先伤自己）。下游真有「幻觉读文件」痛点时，自行 copy 进
   .claude/hooks/、填好下面 3 个配置、再在 settings.json 注册 PreToolUse matcher 才生效。

四 gate 漏斗（全过才 deny，缺一即放行——刻意窄交集「宁漏勿误」）：
  G0 工具匹配  : tool_name ∈ READ_TOOLS
  G1 读取意图  : 取出 file_path，非空且非 glob / 非目录 / 非 URL
  G2 路径可解析: 规范成确定本地绝对路径（解析 ~ / 相对拼 cwd / normpath）；含变量解析不出 → 放行
  G3 确证不存在: 规范化后路径 exists() == False（硬证据，不是「我猜」）
  G4 豁免      : 不在 EXEMPT_PREFIXES 内

宿主对接：本文件按 Claude Code 的 PreToolUse 协议输出 deny 决定（permissionDecision，
字段写法对齐本仓库 templates/hooks/allow_memory_write.py）。换宿主时只需改 main() 的
输入读取 + 决定输出两段；四 gate 纯函数 evaluate() 是宿主无关的，可原样复用。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# stdout/stderr 强制 UTF-8：deny 理由含中文 REAL_SOURCE_HINT，GBK Windows 不转会糊成乱码
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# 项目要填的 3 个配置（全是数据，不是代码分支）。空配置也能跑、不报错、不误伤。
# ─────────────────────────────────────────────────────────────────────────────

# 读取类工具名集合。默认即 Claude Code 的 Read；有自定义读取工具再扩展。
READ_TOOLS = {"Read"}

# 豁免前缀（绝对路径前缀列表）。给「故意读不存在文件是合法行为」留逃生口
# （touch-before-write、探针脚本等）。空列表也能跑——但启用前务必想清楚本项目
# 有哪些「合法地读不存在文件」的场景，否则会误伤。示例：[os.path.expanduser("~/.cache/myproj")]
EXEMPT_PREFIXES: list[str] = []

# deny 时投喂的「真实数据源在哪」。骨架给一句通用兜底；项目应覆盖成本项目的权威位置，
# 如「本项目行情数据走 causis_api，不在磁盘文件里」。这是 C1 真正的价值零件——不填则
# C1 ≈ 一条更啰嗦的 FileNotFoundError。
REAL_SOURCE_HINT = "若这是项目数据，请改用项目约定的权威数据源（接口 / 服务 / 索引），而非凭空假设的本地文件。"

# deny 理由通用前缀（骨架内置，所有项目一样；把 R3/R4「别编造、别甩锅」在拒绝现场再钉一次）
_DENY_PREFIX = (
    "该路径确证不存在。通道 / 路径错误 ≠ 资源缺失——不要凭空另寻或编造数据源，"
    "也不要把失败归咎于用户 / 工具 / 编辑器。"
)


def evaluate(tool_name: str, tool_input: dict) -> str | None:
    """四 gate 纯函数（宿主无关）。返回 deny 理由字符串；None = 放行不干预。"""
    # G0 工具匹配
    if tool_name not in READ_TOOLS:
        return None

    # G1 读取意图：取出具体目标路径，排除 glob / 目录 / URL
    raw = (tool_input or {}).get("file_path", "")
    if not raw or not isinstance(raw, str):
        return None
    if "://" in raw:                       # URL，非本地文件读取
        return None
    if any(ch in raw for ch in "*?[]"):    # glob / 模式匹配，本就允许 miss
        return None
    if raw.endswith(("/", "\\")):          # 显式目录意图
        return None

    # G2 路径可解析：含未解析变量 → 证据不足，放行
    if "$" in raw or "%" in raw:
        return None
    try:
        abs_path = Path(os.path.abspath(os.path.expanduser(raw)))
    except Exception:
        return None
    if abs_path.is_dir():                  # 解析后落到一个目录，非「读具体文件」
        return None

    # G3 确证不存在：硬证据 == False 才继续（误伤防线的锚点）
    if abs_path.exists():
        return None

    # G4 豁免
    norm = str(abs_path).replace("\\", "/")
    for pref in EXEMPT_PREFIXES:
        if norm.startswith(str(Path(os.path.abspath(os.path.expanduser(pref)))).replace("\\", "/")):
            return None

    # 四 gate 全过 → deny，拼通用前缀 + 项目 hint
    return f"{_DENY_PREFIX} {REAL_SOURCE_HINT}（确证不存在的路径：{abs_path}）"


def main() -> int:
    # 输入双兜底：官方 PreToolUse 走 stdin JSON；老 hook 走环境变量（对齐 allow_memory_write.py）
    data: dict = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            data = json.loads(raw)
    except Exception:
        data = {}

    tool_name = data.get("tool_name") or os.environ.get("CLAUDE_TOOL_NAME", "")
    tool_input = data.get("tool_input")
    if not tool_input:
        try:
            tool_input = json.loads(os.environ.get("CLAUDE_TOOL_INPUT", "{}"))
        except Exception:
            tool_input = {}

    reason = evaluate(tool_name, tool_input or {})
    if reason is None:
        return 0  # 放行，不干预

    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
