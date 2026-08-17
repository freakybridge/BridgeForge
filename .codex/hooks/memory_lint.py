#!/usr/bin/env python3
"""Hook B: 校验 MEMORY.md 行数（≤200 硬线）+ 孤儿/死链接检测。

触发：PostToolUse(Edit|Write) 且 file_path 含 `.codex/memory`。
非阻塞：问题打印到 stderr，Codex 下一轮会看到并自主修复。
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

MEMORY_MAX_LINES = 200
GENERATED_MEMORY_FILES = {"MEMORY.md", "MEMORY_COLD.md"}
VALID_CATEGORIES = ("architecture", "engineering", "domain", "operations", "topic")
VALID_STATUSES = ("active", "completed", "superseded")
TOPIC_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER_RE = re.compile(
    r"\A---\s*\r?\n(.*?)\r?\n---(?:\r?\n|\Z)",
    re.DOTALL,
)
TAG_CATEGORY_ALIASES = {
    "architecture": "architecture",
    "架构": "architecture",
    "engineering": "engineering",
    "工程": "engineering",
    "domain": "domain",
    "领域": "domain",
    "operations": "operations",
    "运维": "operations",
}


def parse_metadata(raw: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(raw)
    if not match:
        return {}
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        item = re.match(r"^([A-Za-z_][\w-]*):\s*(.*?)\s*$", line)
        if item:
            metadata[item.group(1).lower()] = item.group(2).strip().strip("\"'")
    return metadata


def update_metadata(raw: str, updates: dict[str, str]) -> str:
    match = FRONTMATTER_RE.match(raw)
    if not match:
        header = "\n".join(f"{key}: {value}" for key, value in updates.items())
        return f"---\n{header}\n---\n{raw.lstrip()}"

    seen: set[str] = set()
    lines: list[str] = []
    for line in match.group(1).splitlines():
        item = re.match(r"^([A-Za-z_][\w-]*):", line)
        key = item.group(1).lower() if item else ""
        if key in updates:
            lines.append(f"{key}: {updates[key]}")
            seen.add(key)
        else:
            lines.append(line)
    for key, value in updates.items():
        if key not in seen:
            lines.append(f"{key}: {value}")
    body = raw[match.end() :]
    header = "\n".join(lines)
    return f"---\n{header}\n---\n{body}"


def iter_memory_files(memory_dir: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in memory_dir.rglob("*.md")
            if path.name not in GENERATED_MEMORY_FILES
            and not path.name.startswith(("_", "."))
        ),
        key=lambda path: path.relative_to(memory_dir).as_posix(),
    )


def category_from_tags(metadata: dict[str, str]) -> str:
    tags = metadata.get("tags", "").strip("[]")
    tokens = {
        token.strip().strip("\"'").lower()
        for token in re.split(r"[,，\s]+", tags)
        if token.strip()
    }
    matches = {
        TAG_CATEGORY_ALIASES[token]
        for token in tokens
        if token in TAG_CATEGORY_ALIASES
    }
    return next(iter(matches)) if len(matches) == 1 else ""


def expected_path(
    memory_dir: Path,
    source: Path,
    category: str,
    topic: str,
) -> Path:
    if category == "topic":
        return memory_dir / "topics" / topic / "summary.md"
    return memory_dir / category / source.name


def resolve_source(memory_dir: Path, raw_path: str) -> Path:
    source = (memory_dir / raw_path).resolve()
    source.relative_to(memory_dir.resolve())
    if not source.is_file() or not source.name.endswith(".md"):
        raise ValueError(f"不是 memory Markdown 文件: {raw_path}")
    if source.name in GENERATED_MEMORY_FILES or source.name.startswith(("_", ".")):
        raise ValueError(f"拒绝整理生成/系统文件: {raw_path}")
    return source


def move_stats_entry(memory_dir: Path, source: Path, target: Path) -> None:
    """Keep deterministic ordering and pinned settings after an explicit move."""
    stats_file = memory_dir / "_stats.json"
    if not stats_file.exists():
        return
    try:
        stats = json.loads(stats_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(stats, dict):
        return
    source_rel = source.relative_to(memory_dir).as_posix()
    target_rel = target.relative_to(memory_dir).as_posix()
    files = stats.get("files")
    if isinstance(files, dict) and source_rel in files:
        files[target_rel] = files.pop(source_rel)
    config = stats.get("config")
    if isinstance(config, dict) and isinstance(config.get("pinned"), list):
        config["pinned"] = [
            target_rel if item == source_rel else item
            for item in config["pinned"]
        ]
    stats_file.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def organize_cli() -> int:
    parser = argparse.ArgumentParser(description="检查或显式整理 memory 分类")
    parser.add_argument("path", nargs="?", help="相对 memory/ 的 Markdown 路径")
    parser.add_argument(
        "--organize",
        action="store_true",
        help="检查全部 memory；默认不写入、不移动",
    )
    parser.add_argument("--apply", action="store_true", help="应用已明确/高置信分类")
    parser.add_argument("--confirmed", action="store_true", help="确认应用完整 dry-run 计划")
    parser.add_argument("--category", choices=VALID_CATEGORIES)
    parser.add_argument("--topic", help="topic category 的 exact slug")
    parser.add_argument("--status", choices=VALID_STATUSES)
    parser.add_argument("--description", help="单个 memory 的非空单行 description")
    parser.add_argument("--project-root", help="由 bridgeforge-codex 扫描的目标项目根目录")
    args = parser.parse_args()

    if (args.category or args.topic or args.status or args.description) and not args.path:
        parser.error("--category/--topic/--status/--description 必须同时指定单个 path")
    if args.category == "topic" and not args.topic:
        parser.error("--category topic 必须同时指定 --topic <exact-slug>")
    if args.topic and args.category not in (None, "topic"):
        parser.error("--topic 只能与 --category topic 一起使用")
    if args.topic and not TOPIC_SLUG_RE.fullmatch(args.topic):
        parser.error("topic 必须是小写字母/数字/连字符组成的 exact slug")
    if args.description is not None and (
        not args.description.strip() or "\n" in args.description or "\r" in args.description
    ):
        parser.error("description 必须是非空单行纯文本")
    if args.apply and not args.confirmed:
        parser.error("--apply 必须同时指定 --confirmed，表示已确认完整 dry-run 计划")
    if args.project_root:
        memory_dir = Path(args.project_root).resolve() / ".codex" / "memory"
    else:
        memory_dir = Path(__file__).resolve().parent.parent / "memory"
    if not memory_dir.exists():
        return 0
    try:
        sources = (
            [resolve_source(memory_dir, args.path)]
            if args.path
            else iter_memory_files(memory_dir)
        )
    except ValueError as exc:
        parser.error(str(exc))

    records: list[dict[str, object]] = []
    for source in sources:
        relative = source.relative_to(memory_dir).as_posix()
        raw = source.read_text(encoding="utf-8")
        metadata = parse_metadata(raw)
        category = args.category or metadata.get("category", "").lower()
        explicit = bool(args.category)
        if category not in VALID_CATEGORIES:
            category = category_from_tags(metadata)
            explicit = False
        issues: list[str] = []
        if relative.split("/", 1)[0] == "_archive":
            issues.append("memory/_archive 已退役，必须保留原 topic 路径并通过状态降温")
        description = args.description if args.description is not None else metadata.get("description", "")
        if not description.strip() or re.fullmatch(r"[>|][+-]?\d?", description.strip()):
            issues.append("缺少非空 description")
        if not category:
            topic_hint = metadata.get("topic", "<topic>")
            records.append({
                "source": source,
                "relative": relative,
                "candidate": (
                    "architecture/ | engineering/ | domain/ | operations/ | "
                    f"topics/{topic_hint}/"
                ),
                "issues": issues,
            })
            continue

        status = args.status or metadata.get("status", "").lower()
        if status and status not in VALID_STATUSES:
            issues.append(f"status={status!r} 非法")
        topic = args.topic or metadata.get("topic", "")
        if category == "topic" and not TOPIC_SLUG_RE.fullmatch(topic):
            issues.append("topic category 缺少合法 topic slug")
        if category == "topic":
            parts = source.relative_to(memory_dir).parts
            directory_topic = (
                parts[1]
                if len(parts) >= 3 and parts[0] == "topics"
                else ""
            )
            metadata_topic = metadata.get("topic", "")
            if (
                directory_topic
                and metadata_topic
                and directory_topic != metadata_topic
                and args.topic is None
            ):
                issues.append(
                    f"directory topic={directory_topic!r} != frontmatter "
                    f"topic={metadata_topic!r}；显式改名需 --category topic --topic <exact-slug>"
                )

        target = (
            expected_path(memory_dir, source, category, topic)
            if category != "topic" or TOPIC_SLUG_RE.fullmatch(topic)
            else source
        )
        updates: dict[str, str] = {}
        if explicit or metadata.get("category", "").lower() not in VALID_CATEGORIES:
            updates["category"] = category
        if category == "topic" and (args.topic or metadata.get("topic") != topic):
            updates["topic"] = topic
        if args.status or not status:
            updates["status"] = args.status or "active"
        if args.description is not None:
            updates["description"] = args.description.strip()
        records.append({
            "source": source,
            "relative": relative,
            "target": target,
            "updates": updates,
            "issues": issues,
            "explicit": explicit,
        })

    target_sources: dict[Path, list[Path]] = {}
    for record in records:
        target = record.get("target")
        source = record.get("source")
        if isinstance(target, Path) and isinstance(source, Path):
            target_sources.setdefault(target, []).append(source)

    unresolved = False
    changes_pending = False
    for record in records:
        relative = str(record["relative"])
        candidate = record.get("candidate")
        issues = list(record.get("issues", []))
        if candidate:
            print(f"[candidate] {relative} -> {candidate}；未修改")
            if issues:
                print(f"[invalid] {relative}: {'；'.join(issues)}；未修改")
            unresolved = True
            continue
        source = record["source"]
        target = record["target"]
        updates = record["updates"]
        assert isinstance(source, Path) and isinstance(target, Path) and isinstance(updates, dict)
        shared = target_sources.get(target, [])
        if len(shared) > 1:
            names = ", ".join(path.relative_to(memory_dir).as_posix() for path in shared)
            issues.append(f"多个文件竞争同一规范目标 {target.relative_to(memory_dir).as_posix()}: {names}")
        elif target != source and target.exists():
            issues.append(f"目标已存在: {target.relative_to(memory_dir).as_posix()}")
        if issues:
            print(f"[invalid] {relative}: {'；'.join(issues)}；未修改")
            unresolved = True
            continue
        target_relative = target.relative_to(memory_dir).as_posix()
        if target != source or updates:
            confidence = "explicit" if record.get("explicit") else "high-confidence"
            metadata_plan = ", ".join(f"{key}={value}" for key, value in updates.items()) or "metadata unchanged"
            print(
                f"[{confidence}] {relative} -> {target_relative}; {metadata_plan}；"
                "未修改（确认后加 --apply --confirmed）"
            )
            changes_pending = True
        else:
            print(f"[ok] {relative}")

    if unresolved:
        return 1
    if not args.apply:
        return 1 if changes_pending else 0

    for record in records:
        source = record["source"]
        target = record["target"]
        updates = record["updates"]
        assert isinstance(source, Path) and isinstance(target, Path) and isinstance(updates, dict)
        raw = source.read_text(encoding="utf-8")
        if updates:
            source.write_text(update_metadata(raw, updates), encoding="utf-8")
        if target != source:
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
            move_stats_entry(memory_dir, source, target)
        print(
            f"[applied] {source.relative_to(memory_dir).as_posix()} -> "
            f"{target.relative_to(memory_dir).as_posix()}"
        )
    return 0


def main() -> int:
    # 输入双兜底（与 requirements_check.py 一致）：官方 Codex hook 走 stdin JSON，
    # file_path 嵌在 `tool_input` 下；环境变量只使用 CODEX_TOOL_INPUT 兜底。
    tool_input: dict = {}
    try:
        raw = sys.stdin.read()
        if raw.strip():
            ti = json.loads(raw).get("tool_input")
            if isinstance(ti, dict):
                tool_input = ti
    except Exception:
        tool_input = {}
    if not tool_input:
        try:
            env_raw = os.environ.get("CODEX_TOOL_INPUT", "{}")
            tool_input = json.loads(env_raw)
        except Exception:
            return 0
    if not isinstance(tool_input, dict):
        return 0
    f = tool_input.get("file_path", "").replace("\\", "/")
    if ".codex/memory" not in f:
        return 0

    repo_root = Path(__file__).resolve().parent.parent.parent
    memory_dir = repo_root / ".codex" / "memory"
    memory_md = memory_dir / "MEMORY.md"
    if not memory_md.exists():
        return 0

    text = memory_md.read_text(encoding="utf-8")
    lines = text.splitlines()
    issues: list[str] = []

    if len(lines) > MEMORY_MAX_LINES:
        issues.append(
            f"MEMORY.md 超 {MEMORY_MAX_LINES} 行: 当前 {len(lines)} 行，"
            f"超过会被 Codex 静默截断"
        )

    cold_md = memory_dir / "MEMORY_COLD.md"
    cold_text = cold_md.read_text(encoding="utf-8") if cold_md.exists() else ""
    linked = set(re.findall(r"\(([^()\s]+\.md)\)", text + cold_text))
    actual = {
        path.relative_to(memory_dir).as_posix()
        for path in memory_dir.rglob("*.md")
        if path.name not in GENERATED_MEMORY_FILES
        and not path.name.startswith(("_", "."))
    }

    orphans = sorted(actual - linked)
    broken = sorted(linked - actual)

    if orphans:
        issues.append(f"未索引 orphans（{len(orphans)}）: {', '.join(orphans)}")
    if broken:
        issues.append(f"索引死链接（{len(broken)}）: {', '.join(broken)}")

    if issues:
        print("[memory_lint 发现问题]", file=sys.stderr)
        for i in issues:
            print(f"  - {i}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(organize_cli())
    sys.exit(main())
