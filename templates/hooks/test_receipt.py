#!/usr/bin/env python3
"""PostToolUse(Bash) hook: 测试类命令收据（D1-M2，尽量版）。

命令匹配 pytest / cargo test / npm test / go test / tsc / make 时，把「这条命令真跑过、
退出状态是什么」写成一行收据落 `.runtime/test_receipts/receipts.jsonl`，声称「测试通过」
时可对账（CLAUDE.md §2.5 收据红线：须指到命令签名匹配 + 本轮时间窗内 + exit==0 的收据）。

**尽量版说明（甲方案，2026-07-02 用户拍板）**：Claude Code 成功场景的 tool_response
不带显式退出码（成功=无声，只有失败才在文本里报 "Exit code N"）→ 本 hook 分级提取：
  1. tool_response 里有显式数字字段（exit_code/exitCode/returncode/...）→ 直接用，source=explicit
  2. 文本里匹配 "Exit code N" / "exit status N" → 用 N，source=text
  3. 无错误标记（无 is_error / 无 Exit code 文本 / 未中断）→ 推断 0，source=inferred
  4. 其余（中断 / 有错但拿不到码）→ exit_code=null，source=unknown
同时**每次把原始 payload（长字段截断）存 `payload_samples/`（保最近 5 份）**——供后续
会话核对真实 payload 形状后把提取逻辑改准（这一步是"尽量版→精确版"的升级依据）。

**覆盖边界（残余风险 §5.2/§5.7，别吹大）**：
  - 收据只证「命令真跑了 + 退出状态」，**不证验证内容有效**（断言写歪照样 exit 0 盖章）。
  - 命令真卡死不返回 → PostToolUse 不触发 → 无收据（继承 C2 失明缺陷，已记账）。
  - source=inferred 的 0 是推断非铁证（成功场景无显式码），对账时以 source 字段自知硬度。

自门控：非 Bash / 无 command / 非测试类命令 → 静默 no-op exit 0；任何异常 exit 0 不阻塞。
输入双兜底（stdin JSON / 环境变量）同 requirements_check.py。输出纯 ASCII（防 GBK 乱码）。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RECEIPT_DIR = REPO_ROOT / ".runtime" / "test_receipts"
SAMPLE_DIR = RECEIPT_DIR / "payload_samples"
KEEP_SAMPLES = 5          # payload 样本只保留最近 N 份
TRUNC = 2000              # 样本里单个字符串字段截断长度
CMD_FINGERPRINT_LEN = 200  # 收据里命令原文截断长度

# 测试类命令（与设计 D1-M2 清单一致；\b 防误命中 makeup/gotsc 之类）
_TEST_CMD = re.compile(
    r"\b(pytest|cargo\s+test|npm\s+(?:run\s+)?test|go\s+test|tsc|make)\b"
)
# 失败文本里的显式退出码（Claude Code 失败场景开头是 "Exit code N"）
_EXIT_TEXT = re.compile(r"\bexit\s+(?:code|status)\s+(\d+)", re.IGNORECASE)
# tool_response 里可能承载退出码的字段名（按可信度排序，见到即用）
_EXIT_KEYS = ("exit_code", "exitCode", "returncode", "returnCode", "code", "status")


def _read_payload() -> dict:
    """官方 PostToolUse 走 stdin JSON；老通道只有 CLAUDE_TOOL_INPUT（无 tool_response）。"""
    data: dict = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            data = json.loads(raw)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    if not data.get("tool_input"):
        try:
            ti = json.loads(os.environ.get("CLAUDE_TOOL_INPUT", "{}"))
            if isinstance(ti, dict) and ti:
                data.setdefault("tool_input", ti)
        except Exception:
            pass
    return data


def _response_text(resp) -> str:
    """把 tool_response 的可读文本尽量抠出来（str / dict.stdout+stderr / content 列表都试）。"""
    parts: list[str] = []
    if isinstance(resp, str):
        parts.append(resp)
    elif isinstance(resp, dict):
        for k in ("stdout", "stderr", "output", "text", "error"):
            v = resp.get(k)
            if isinstance(v, str) and v:
                parts.append(v)
        content = resp.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
    return "\n".join(parts)


def extract_exit(resp) -> tuple[int | None, str, bool]:
    """分级提取退出码。返回 (exit_code|None, source, interrupted)。"""
    interrupted = bool(isinstance(resp, dict) and resp.get("interrupted"))

    # 1) 显式数字字段
    if isinstance(resp, dict):
        for k in _EXIT_KEYS:
            v = resp.get(k)
            if isinstance(v, bool):  # bool 是 int 子类，先排掉
                continue
            if isinstance(v, int):
                return v, "explicit", interrupted
            if isinstance(v, str) and v.isdigit():
                return int(v), "explicit", interrupted

    # 2) 文本里的 "Exit code N"
    text = _response_text(resp)
    m = _EXIT_TEXT.search(text)
    if m:
        try:
            return int(m.group(1)), "text", interrupted
        except ValueError:
            pass

    # 3) 无错误标记 → 推断成功（成功场景无显式码，见模块 docstring）
    has_error_mark = bool(
        isinstance(resp, dict) and (resp.get("is_error") or resp.get("isError"))
    )
    if not has_error_mark and not interrupted:
        return 0, "inferred", interrupted

    # 4) 有错/中断但拿不到码
    return None, "unknown", interrupted


def _truncate_strings(obj, limit: int = TRUNC):
    """递归截断 payload 里的长字符串，控制样本文件体积。"""
    if isinstance(obj, str):
        return obj if len(obj) <= limit else obj[:limit] + f"...<truncated {len(obj)} chars>"
    if isinstance(obj, dict):
        return {k: _truncate_strings(v, limit) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_truncate_strings(v, limit) for v in obj]
    return obj


def _dump_sample(payload: dict, ts: str) -> None:
    """存原始 payload 样本（甲方案核心：给下个会话留提取逻辑校准的真数据），保最近 N 份。"""
    try:
        SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
        fname = SAMPLE_DIR / f"{ts.replace(':', '')}.json"
        fname.write_text(
            json.dumps(_truncate_strings(payload), ensure_ascii=True, indent=1),
            encoding="utf-8",
        )
        samples = sorted(SAMPLE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
        for old in samples[:-KEEP_SAMPLES]:
            old.unlink(missing_ok=True)
    except Exception:
        pass  # 兜底：样本存不上不影响收据主线


def main() -> int:
    data = _read_payload()
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0
    cmd = tool_input.get("command", "")
    if not isinstance(cmd, str) or not cmd:
        return 0
    m = _TEST_CMD.search(cmd)
    if not m:
        return 0  # 非测试类命令：自门控 no-op

    resp = data.get("tool_response")
    exit_code, source, interrupted = extract_exit(resp)
    ts = datetime.now().isoformat(timespec="seconds")

    receipt = {
        "ts": ts,
        "kind": m.group(1).split()[0],
        "cmd": cmd[:CMD_FINGERPRINT_LEN],
        "sha1": hashlib.sha1(cmd.encode("utf-8", "replace")).hexdigest()[:12],
        "exit_code": exit_code,
        "source": source,
        "interrupted": interrupted,
    }
    try:
        RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
        with (RECEIPT_DIR / "receipts.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(receipt, ensure_ascii=True) + "\n")
    except Exception:
        return 0  # 收据写不上也绝不阻塞

    _dump_sample(data, ts)

    # 纯 ASCII 一行注回 context：让模型当轮就知道收据在哪、硬度如何
    print(
        f"[test-receipt] {receipt['kind']} exit={exit_code} source={source} "
        f"sha1={receipt['sha1']} -> .runtime/test_receipts/receipts.jsonl"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
