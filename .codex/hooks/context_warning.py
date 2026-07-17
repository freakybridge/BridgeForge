"""Codex 上下文成本预警（UserPromptSubmit hook）。

优先读取当前 Codex JSONL 的 ``event_msg.token_count``；兼容旧版
``assistant.usage``。两种真实 usage 都不存在时，才退化为文件大小估算。

成本档位：80k ECONOMY / 140k HANDOFF / 200k CRITICAL；上下文 >= 80k
且缓存命中率 < 50% 时追加 CACHE_MISS。信号只提醒、不拦截。
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

DEFAULT_CODEX_WINDOW = 353_000
WINDOW_ENV = "BRIDGEFORGE_CODEX_CTX_WINDOW"
ECONOMY_ENV = "BRIDGEFORGE_CTX_ECONOMY_TOKENS"
HANDOFF_ENV = "BRIDGEFORGE_CTX_HANDOFF_TOKENS"
CRITICAL_ENV = "BRIDGEFORGE_CTX_CRITICAL_TOKENS"
DEFAULT_ECONOMY = 80_000
DEFAULT_HANDOFF = 140_000
DEFAULT_CRITICAL = 200_000
SAFETY_CRITICAL_PCT = 75
CACHE_MISS_MIN_TOKENS = 80_000
CACHE_MISS_RATIO_PCT = 50
TAIL_BYTES = 256 * 1024


@dataclass(frozen=True)
class UsageSnapshot:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    total_tokens: int
    model_context_window: int | None
    source: str

    @property
    def cache_ratio_pct(self) -> int:
        if self.input_tokens <= 0:
            return 0
        return min(100, self.cached_input_tokens * 100 // self.input_tokens)


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _read_tail(path: Path) -> list[bytes]:
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > TAIL_BYTES:
                f.seek(size - TAIL_BYTES)
                f.readline()
            return f.read().splitlines()
    except Exception:
        return []


def _codex_usage(row: dict) -> UsageSnapshot | None:
    if row.get("type") != "event_msg":
        return None
    payload = row.get("payload") or {}
    if payload.get("type") != "token_count":
        return None
    info = payload.get("info") or {}
    usage = info.get("last_token_usage") or {}
    if not usage:
        return None
    input_tokens = _as_int(usage.get("input_tokens"))
    output_tokens = _as_int(usage.get("output_tokens"))
    return UsageSnapshot(
        input_tokens=input_tokens,
        cached_input_tokens=_as_int(usage.get("cached_input_tokens")),
        output_tokens=output_tokens,
        total_tokens=_as_int(usage.get("total_tokens"), input_tokens + output_tokens),
        model_context_window=_as_int(info.get("model_context_window")) or None,
        source="codex-token-count",
    )


def _legacy_usage(row: dict) -> UsageSnapshot | None:
    message = row.get("message") or {}
    if not message and row.get("type") == "response_item":
        payload = row.get("payload") or {}
        if payload.get("type") == "message":
            message = payload
    if message.get("role") != "assistant":
        return None
    usage = message.get("usage") or {}
    if not usage:
        return None
    plain_input = _as_int(usage.get("input_tokens"))
    cache_create = _as_int(usage.get("cache_creation_input_tokens"))
    cache_read = _as_int(usage.get("cache_read_input_tokens"))
    output = _as_int(usage.get("output_tokens"))
    combined_input = plain_input + cache_create + cache_read
    return UsageSnapshot(
        input_tokens=combined_input,
        cached_input_tokens=cache_read,
        output_tokens=output,
        total_tokens=combined_input + output,
        model_context_window=None,
        source="legacy-assistant-usage",
    )


def read_last_usage(path: Path) -> UsageSnapshot | None:
    """倒查最近一条真实 usage，优先当前 Codex token_count。"""
    rows: list[dict] = []
    for raw in _read_tail(path):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    for row in reversed(rows):
        current = _codex_usage(row)
        if current is not None:
            return current
    for row in reversed(rows):
        legacy = _legacy_usage(row)
        if legacy is not None:
            return legacy
    return None


def _env_positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip().replace("_", "")
    if not raw:
        return default
    value = _as_int(raw, default)
    return value if value > 0 else default


def effective_window(observed: int | None) -> tuple[int, str]:
    raw = os.environ.get(WINDOW_ENV, "").strip().replace("_", "")
    if raw:
        value = _as_int(raw)
        if value > 0:
            return value, f"env:{WINDOW_ENV}"
    if observed and observed > 0:
        return observed, "token-count"
    return DEFAULT_CODEX_WINDOW, "default"


def classify(usage: UsageSnapshot, window: int) -> tuple[str | None, bool, int]:
    pct = usage.total_tokens * 100 // max(1, window)
    if usage.total_tokens >= _env_positive_int(CRITICAL_ENV, DEFAULT_CRITICAL) or pct >= SAFETY_CRITICAL_PCT:
        level = "CRITICAL"
    elif usage.total_tokens >= _env_positive_int(HANDOFF_ENV, DEFAULT_HANDOFF):
        level = "HANDOFF"
    elif usage.total_tokens >= _env_positive_int(ECONOMY_ENV, DEFAULT_ECONOMY):
        level = "ECONOMY"
    else:
        level = None
    cache_miss = (
        usage.input_tokens >= CACHE_MISS_MIN_TOKENS
        and usage.cache_ratio_pct < CACHE_MISS_RATIO_PCT
    )
    return level, cache_miss, pct


def _is_handoff_command(prompt: str) -> bool:
    first = prompt.lstrip().split(maxsplit=1)[0].lower() if prompt.strip() else ""
    return first in {"$snapshot", "/snapshot", "$resume", "/resume", "/compact"}


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return

    prompt = data.get("prompt", "") or ""
    if _is_handoff_command(prompt):
        return
    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        return
    p = Path(transcript_path)
    if not p.exists():
        return

    usage = read_last_usage(p)
    if usage is None:
        try:
            estimate = p.stat().st_size // 4
        except Exception:
            return
        usage = UsageSnapshot(estimate, 0, 0, estimate, None, "estimate:file-size")

    window, window_source = effective_window(usage.model_context_window)
    level, cache_miss, pct = classify(usage, window)
    if level is None and not cache_miss:
        return

    labels = "+".join(filter(None, [level, "CACHE_MISS" if cache_miss else None]))
    if level == "CRITICAL":
        instruction = "上下文成本已很高；强烈建议先 $snapshot，再开新任务用 $resume latest 接续。"
    elif level == "HANDOFF":
        instruction = "完成当前小步骤后交接；不要在本任务继续开启新的大型子任务。"
    else:
        instruction = "当前子任务完成后准备短交接，避免上下文继续膨胀。"
    if cache_miss:
        instruction += " 本轮缓存命中偏低，旧长任务可能已发生整段重算。"

    print(
        f"[ctx-budget] surface=codex level={labels} "
        f"tokens={usage.total_tokens} input={usage.input_tokens} "
        f"cached={usage.cached_input_tokens} cache_ratio={usage.cache_ratio_pct}% "
        f"window={window} pct={pct}% token_source={usage.source} "
        f"window_source={window_source}\n"
        f"[ctx-budget] {instruction} 信号仅提醒，不阻断用户明确要求。"
    )


if __name__ == "__main__":
    main()
