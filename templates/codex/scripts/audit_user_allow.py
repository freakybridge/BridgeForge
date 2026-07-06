#!/usr/bin/env python3
"""用户级 settings.json allow 审计 — 找出项目专属/一次性条目。

扫描 ~/.codex/settings.json 的 permissions.allow，揪出疑似项目专属的条目：
  - 带项目绝对路径（Windows d:\\Quant\\... / Mac /Users/xxx/...）
  - 写死 PID（Get-Process -Id 12345）
  - 写死 IP（192.168.1.1 之类，排除版本号）
  - 一次性 clone / 编译命令（git clone / cl.exe / cargo build --manifest-path ...）

只报不删——输出列表供用户拍板，建议下沉到项目 settings.local.json。

用法:
  python audit_user_allow.py           # 扫默认位置

详见 rules/portability.md §3.1。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

# F10: Unix 路径白名单——系统目录（可移植，非污染）
_UNIX_SYSTEM_PREFIX = re.compile(
    r"^/(usr|bin|opt|etc|tmp|var|proc|dev|Library|System|sbin)/",
    re.IGNORECASE,
)
# 用户目录路径才是污染：/Users/<name>/... (Mac) 或 /home/<name>/... (Linux)
_UNIX_USER_PATH = re.compile(r"/(Users|home)/[A-Za-z0-9_.-]", re.IGNORECASE)

# F7: IPv4 每段严格 0-255 + 要求出现在网络上下文（@、//、:/ 或词首）
# 版本号 pip install foo==1.2.3.4 不在网络上下文 → 不命中
_IPV4_OCTET = r"(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9][0-9]|[0-9])"
_IPV4 = re.compile(
    rf"(?:^|[\s@])(?:{_IPV4_OCTET}\.){{3}}{_IPV4_OCTET}(?:[:/\s]|$)"
)


def _is_windows_abs_path(entry: str) -> bool:
    """[A-Za-z]:\\ 式绝对路径（反斜杠），跳过含 :// 的 URL（F4）。"""
    if "://" in entry:
        return False
    return bool(re.search(r"[A-Za-z]:\\", entry))


def _is_unix_user_path(entry: str) -> bool:
    """仅匹配用户目录路径，排除系统目录（F10）。"""
    if not _UNIX_USER_PATH.search(entry):
        return False
    # 额外排除：如果整个 entry 以系统前缀开头也不报
    if _UNIX_SYSTEM_PREFIX.match(entry):
        return False
    return True


def _flag_entry(entry: str) -> list[str]:
    """返回命中的规则描述列表（空 = 无命中）。F8: 调用方已保证 entry 是 str。"""
    reasons = []

    if _is_windows_abs_path(entry):
        reasons.append("绝对路径(Windows)")

    if _is_unix_user_path(entry):
        reasons.append("绝对路径(Unix用户目录)")

    if re.search(r"Get-Process\s+-Id\s+\d{4,7}", entry, re.IGNORECASE):
        reasons.append("PID(Get-Process -Id)")
    if re.search(r"kill\s+-9\s+\d{4,7}", entry):
        reasons.append("PID(kill -9)")

    if _IPV4.search(entry):  # F7: bounds + context
        reasons.append("IP(IPv4)")

    if re.search(r"git\s+clone\b", entry, re.IGNORECASE):
        reasons.append("一次性命令(git clone)")
    if re.search(r"cargo\s+build\s+--manifest-path", entry, re.IGNORECASE):
        reasons.append("一次性命令(cargo build --manifest-path)")
    if re.search(r"\b(cl\.exe|msbuild\.exe|link\.exe)\b", entry, re.IGNORECASE):
        reasons.append("一次性命令(cl.exe/msbuild)")

    return reasons


def main() -> None:
    settings_path = Path.home() / ".codex" / "settings.json"
    if not settings_path.exists():
        print(f"[audit-allow] 未找到 {settings_path}，跳过。")
        return

    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[audit-allow] 读取 settings.json 失败: {exc}", file=sys.stderr)
        sys.exit(1)

    allow_list = data.get("permissions", {}).get("allow", [])

    # F9: allow 可能误成 dict（手改 settings.json 时易发生）
    if not isinstance(allow_list, list):
        print(
            f"[audit-allow] ⚠ permissions.allow 不是列表（实际类型: {type(allow_list).__name__}），"
            "跳过审计。请检查 settings.json 格式。",
            file=sys.stderr,
        )
        return

    if not allow_list:
        print("[audit-allow] permissions.allow 为空，无条目需要审计。")
        return

    flagged: list[tuple[int, str, list[str]]] = []
    for idx, entry in enumerate(allow_list):
        if not isinstance(entry, str):  # F8: 跳过非字符串（null/数字/对象）
            continue
        reasons = _flag_entry(entry)
        if reasons:
            flagged.append((idx, entry, reasons))

    if not flagged:
        print(f"[audit-allow] ✓ 扫描了 {len(allow_list)} 条 allow，未发现疑似项目专属条目。")
        return

    print(f"[audit-allow] ⚠ 发现 {len(flagged)} 条疑似项目专属 allow（共 {len(allow_list)} 条）：")
    print()
    for idx, entry, reasons in flagged:
        print(f"  [{idx:3d}] {entry!r}")
        print(f"         原因: {', '.join(reasons)}")
        print()

    print("建议：将这些条目从用户级 settings.json 移到对应项目的 settings.local.json。")
    print("      （settings.local.json 已在 .gitignore，只对本机本项目生效）")


if __name__ == "__main__":
    main()
