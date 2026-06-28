#!/usr/bin/env python3
"""SessionStart hook: 骨架必要配置开机体检（只读，不自动修）。

每次 session 开始照一份「骨架约定的必要配置」清单逐项核对，发现不达标只**报告**
（纯 ASCII，一行一条 + 修复提示），**绝不自动改任何文件** —— 修不修由用户决定。
全部达标时静默（不刷屏）。

为什么只读不自动修：本 hook 会被复印进所有下游项目、每次开机在每台机器上跑。
一个「会自动改你配置」的 hook 复印出去就是埋雷（在别人机器上自作主张改错 / 写坏）。
故定位为「体检仪」：测温报数，开药留给人。（与 2026-06-25 encoding-fix-scope debate 同源决策。）

为什么输出纯 ASCII：万一缺的恰好是 PYTHONUTF8（UTF-8 Mode 没生效），用中文报警，
警报自己会在 GBK 控制台糊成乱码 —— 正是它要查的病。故护栏文本一律英文 ASCII。

单一事实源：下面 ACTIVE_CHECKS + DELEGATED 两张表就是「骨架要求哪些配置 + 谁来保证」
的唯一清单。新增必要配置只改这里：本 hook 亲测的加进 ACTIVE_CHECKS；已有专职 hook
兜的登记进 DELEGATED（本 hook 不重复测，避免双重刷屏 / 时序竞争）。

非阻塞：始终 exit 0；任何单项检查抛异常都吞掉，绝不拖垮 session 启动。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

USER_SETTINGS = Path.home() / ".claude" / "settings.json"
PROJECT_SETTINGS = Path(".claude") / "settings.json"          # SessionStart hook cwd = 项目根
PROJECT_SETTINGS_LOCAL = Path(".claude") / "settings.local.json"


# --- 各体检项：返回 None=通过，返回字符串=不达标（一行纯 ASCII，含修复提示） ---

def _check_pythonutf8() -> "str | None":
    """承重柱：UTF-8 Mode 真生效没。查 sys.flags.utf8_mode（事实，不被 stdout.reconfigure 掩盖）。

    GBK Windows 上若 OFF，hook 的中文输出 / open() 读文件会糊成 U+FFFD 注入 context
    （曾高频致 agent 跑偏，见 memory utf8-garble-rootcause）。原 utf8-guard 即此项，已归位到这。
    """
    if not sys.flags.utf8_mode:
        return ("PYTHONUTF8: OFF (Python UTF-8 Mode not active). On GBK Windows this can "
                "corrupt Chinese hook output into the context. "
                "FIX: add \"env\":{\"PYTHONUTF8\":\"1\",\"PYTHONIOENCODING\":\"utf-8\"} "
                "to ~/.claude/settings.json, then restart the session.")
    return None


def _check_settings_json_valid() -> "str | None":
    """user / project settings.json 必须是合法 JSON —— 坏掉会静默架空 hooks/permissions。"""
    bad = []
    for label, p in (("~/.claude/settings.json", USER_SETTINGS),
                     (".claude/settings.json", PROJECT_SETTINGS),
                     (".claude/settings.local.json", PROJECT_SETTINGS_LOCAL)):
        if not p.is_file():
            continue
        try:
            with open(p, encoding="utf-8") as f:
                json.load(f)
        except Exception as e:
            bad.append("%s (%s)" % (label, type(e).__name__))
    if bad:
        return ("settings.json invalid JSON: %s. "
                "FIX: repair the JSON syntax (a broken settings file silently disables "
                "hooks/permissions)." % ", ".join(bad))
    return None


# 本 hook 亲测 + 报告的项（单一事实源之一）。
ACTIVE_CHECKS = (
    ("pythonutf8", _check_pythonutf8),
    ("settings-json-valid", _check_settings_json_valid),
)

# 已有专职 hook 保证的必要配置 —— 本 hook **不重复测**（避免双重刷屏 / 时序竞争），仅在此
# 登记备查，让本文件成为「骨架要求哪些配置 + 谁来保证」的完整单一事实源。新增「已有 owner」
# 的必要配置登记到这；若要本 hook 亲测，则改放 ACTIVE_CHECKS。
DELEGATED = (
    ("memory-junction-intact", "memory_junction_check.py (self-heals + reports on action)"),
    ("no-project-effortlevel", "enforce_no_effortlevel.py (strips + reports on action)"),
    ("user-skill-sync", "skill_sync_check.py (reports drift)"),
)


def main() -> int:
    failures = []
    for _name, fn in ACTIVE_CHECKS:
        try:
            msg = fn()
        except Exception:
            continue  # 单项检查异常绝不拖垮启动
        if msg:
            failures.append(msg)

    if not failures:
        return 0  # 全绿静默

    print("[health-check] %d skeleton setting(s) need attention "
          "(check-only, nothing changed):" % len(failures))
    for msg in failures:
        print("  - %s" % msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
