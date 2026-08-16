#!/usr/bin/env python3
"""Deterministic weighted search for project ``.codex/memory`` notes."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

GENERATED = {"MEMORY.md", "MEMORY_COLD.md"}
TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]+|[\u3400-\u9fff]+")
CJK_RE = re.compile(r"^[\u3400-\u9fff]+$")
CJK_STOP_TERMS = {
    "帮我", "一下", "问题", "这个", "那个", "看看", "查一下", "请问",
    "我们", "你们", "怎么", "什么", "是否", "关于",
}


@dataclass(frozen=True)
class SearchResult:
    path: str
    description: str
    reason: str
    score: int
    created_at: str


def _frontmatter(raw: str) -> dict[str, object]:
    if not raw.startswith("---\n"):
        return {}
    end = raw.find("\n---", 4)
    if end < 0:
        return {}
    data: dict[str, object] = {}
    active_list: str | None = None
    for line in raw[4:end].splitlines():
        item = re.match(r"^\s*-\s+(.+)$", line)
        if item and active_list:
            value = data.setdefault(active_list, [])
            if isinstance(value, list):
                value.append(item.group(1).strip().strip("'\""))
            continue
        match = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        value = value.strip()
        active_list = key if not value else None
        if value.startswith("[") and value.endswith("]"):
            data[key] = [part.strip().strip("'\"") for part in value[1:-1].split(",") if part.strip()]
        else:
            data[key] = value.strip("'\"")
    return data


def _values(meta: dict[str, object], key: str) -> list[str]:
    value = meta.get(key, [])
    if isinstance(value, list):
        return [str(item).lower() for item in value]
    return [part.strip().lower() for part in re.split(r"[,;]", str(value)) if part.strip()]


def _terms(query: str) -> list[str]:
    terms: list[str] = []
    for token in TOKEN_RE.findall(query):
        lowered = token.lower()
        if not CJK_RE.fullmatch(token):
            if len(lowered) > 1:
                terms.append(lowered)
            continue
        # Python's Unicode \w treats an entire Chinese sentence as one word.
        # Long-to-short n-grams preserve business phrases such as “订单路由”
        # while still matching shorter tags and titles in natural prompts.
        max_size = min(6, len(token))
        for size in range(max_size, 1, -1):
            for start in range(0, len(token) - size + 1):
                candidate = token[start:start + size]
                if candidate not in CJK_STOP_TERMS:
                    terms.append(candidate)
    return list(dict.fromkeys(terms))[:80]


def search(memory_dir: Path, query: str, limit: int = 5) -> list[SearchResult]:
    terms = _terms(query)
    if not terms or not memory_dir.is_dir():
        return []
    results: list[SearchResult] = []
    for path in sorted(memory_dir.rglob("*.md")):
        if path.name.startswith("_") or path.name in GENERATED or path.is_symlink():
            continue
        raw = path.read_text(encoding="utf-8", errors="ignore")
        meta = _frontmatter(raw)
        relative = path.relative_to(memory_dir).as_posix()
        topic = str(meta.get("topic") or "").lower()
        related = _values(meta, "related_paths")
        tags = _values(meta, "tags")
        name = str(meta.get("name") or path.stem).lower()
        description = str(meta.get("description") or "").strip()
        header = f"{name} {description.lower()}"
        body = raw.lower()
        exact_topic = sum(1 for term in terms if term == topic or any(term in value for value in related) or term in relative.lower())
        tag_hits = sum(1 for term in terms for tag in tags if term == tag or term in tag)
        header_hits = sum(header.count(term) for term in terms)
        body_hits = min(20, sum(body.count(term) for term in terms))
        score = exact_topic * 10000 + tag_hits * 1000 + header_hits * 100 + body_hits
        if score <= 0:
            continue
        created = str(meta.get("created_at") or meta.get("date") or "")
        if not created:
            created = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
        reasons = []
        if exact_topic:
            reasons.append("topic/path")
        if tag_hits:
            reasons.append("tags")
        if header_hits:
            reasons.append("name/description")
        if body_hits:
            reasons.append("body")
        results.append(SearchResult(relative, description, "+".join(reasons), score, created))
    def created_rank(item: SearchResult) -> float:
        try:
            return datetime.fromisoformat(item.created_at.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0

    results.sort(key=lambda item: (-item.score, -created_rank(item), item.path))
    return results[: max(0, limit)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="+")
    parser.add_argument("--memory-dir", type=Path)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    memory_dir = args.memory_dir or Path(__file__).resolve().parent.parent / "memory"
    results = search(memory_dir, " ".join(args.query), args.limit)
    if args.json:
        print(json.dumps([asdict(item) for item in results], ensure_ascii=False))
    elif not results:
        print("未找到匹配")
    else:
        for item in results:
            print(f"[{item.score:5d}] {item.path} - {item.description} ({item.reason})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
