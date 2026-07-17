#!/usr/bin/env python3
"""Report visible startup-context costs without printing prompt contents."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---", re.DOTALL)
DESCRIPTION_RE = re.compile(r"^description:\s*(.+)$", re.MULTILINE)


def token_estimate(chars: int) -> int:
    """Conservative language-agnostic display estimate; transcript totals stay authoritative."""
    return (chars + 3) // 4


def first_usage(transcript: Path) -> dict[str, int]:
    """Read the first current or legacy usage record from a Codex JSONL transcript."""
    with transcript.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            try:
                item = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if item.get("type") == "event_msg" and item.get("payload", {}).get("type") == "token_count":
                info = item["payload"].get("info") or {}
                usage = info.get("last_token_usage") or info.get("total_token_usage") or {}
                if usage:
                    return {
                        "input_tokens": int(usage.get("input_tokens", 0) or 0),
                        "cached_input_tokens": int(usage.get("cached_input_tokens", 0) or 0),
                        "output_tokens": int(usage.get("output_tokens", 0) or 0),
                        "context_window": int(info.get("model_context_window", 0) or 0),
                    }
            if item.get("type") == "assistant" and isinstance(item.get("usage"), dict):
                usage = item["usage"]
                return {
                    "input_tokens": int(usage.get("input_tokens", 0) or 0),
                    "cached_input_tokens": int(usage.get("cached_input_tokens", 0) or 0),
                    "output_tokens": int(usage.get("output_tokens", 0) or 0),
                    "context_window": 0,
                }
    return {}


def skill_description_chars(repo_root: Path) -> tuple[int, int]:
    files = list((repo_root / "skills").glob("*/SKILL.md"))
    root_skill = repo_root / "SKILL.md"
    if root_skill.exists():
        files.append(root_skill)
    chars = 0
    count = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        frontmatter = FRONTMATTER_RE.search(text)
        match = DESCRIPTION_RE.search(frontmatter.group(1)) if frontmatter else None
        if match:
            chars += len(match.group(1).strip().strip('"').strip("'"))
            count += 1
    return count, chars


def visible_components(repo_root: Path, memory_summary: Path | None) -> list[tuple[str, int]]:
    components: list[tuple[str, int]] = []
    agents = repo_root / "AGENTS.md"
    if agents.exists():
        components.append(("repo AGENTS.md", len(agents.read_text(encoding="utf-8", errors="ignore"))))
    count, chars = skill_description_chars(repo_root)
    components.append((f"skill catalog descriptions ({count})", chars))
    if memory_summary and memory_summary.exists():
        components.append(("global memory summary", len(memory_summary.read_text(encoding="utf-8", errors="ignore"))))
    return components


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure visible Codex startup-context components.")
    parser.add_argument("--transcript", type=Path, help="Codex rollout JSONL used for authoritative first-input tokens")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--memory-summary", type=Path, help="Optional global memory_summary.md")
    args = parser.parse_args()

    components = visible_components(args.repo.resolve(), args.memory_summary)
    print("Visible startup components (contents are never printed):")
    visible_estimate = 0
    for name, chars in components:
        estimate = token_estimate(chars)
        visible_estimate += estimate
        print(f"- {name}: {chars} chars, ~{estimate} tokens")
    print(f"- visible subtotal: ~{visible_estimate} tokens")

    if args.transcript:
        usage = first_usage(args.transcript)
        if not usage:
            print("- transcript first usage: not found")
            return 2
        actual = usage["input_tokens"]
        cached = usage["cached_input_tokens"]
        residual = max(0, actual - visible_estimate)
        print(f"- actual first input: {actual} tokens (cached {cached})")
        print(f"- unitemized runtime/base/tool context: ~{residual} tokens")
        if usage["context_window"]:
            print(f"- observed context window: {usage['context_window']} tokens")
    else:
        print("- actual first input: unavailable (pass --transcript)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
