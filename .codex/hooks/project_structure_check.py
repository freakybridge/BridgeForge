#!/usr/bin/env python3
"""Fail-closed project layout gate for bridgeforge-codex-managed repositories."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_DOC_LAYERS = {
    "0_architecture",
    "1_delivery",
    "2_bugs",
    "3_reference",
    "4_archive",
}
ALLOWED_DOC_ENTRIES = REQUIRED_DOC_LAYERS | {"README.md"}
CLOSED_DELIVERY_STATUSES = {"completed", "superseded"}
CLOSED_BUG_STATUSES = {"resolved", "fixed"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _is_reparse(path: Path) -> bool:
    try:
        attrs = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return path.is_symlink() or bool(attrs & 0x400)


def _exists_lexical(path: Path) -> bool:
    return os.path.lexists(path)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _delivery_layout(readme: str) -> str | None:
    match = re.search(r"(?m)^delivery_layout:\s*(flat|milestone)\s*(?:#.*)?$", readme)
    return match.group(1) if match else None


def _status(path: Path) -> str | None:
    head = "\n".join(_read_text(path).splitlines()[:40])
    match = re.search(r"(?im)^(?:[-*]\s*)?(?:\*\*)?status(?:\*\*)?\s*[:：]\s*([^\s]+)", head)
    return match.group(1).strip().casefold() if match else None


def _unsafe_entry(
    errors: list[dict[str, str]],
    path: Path,
    root: Path,
) -> None:
    relative = path.relative_to(root).as_posix()
    if any(item["code"] == "unsafe-doc-entry" and item["path"] == relative for item in errors):
        return
    errors.append({
        "code": "unsafe-doc-entry",
        "path": relative,
        "message": "doc 内禁止 symlink/junction/reparse point，检查器不会跟随该路径",
    })


def _visible_directories(
    path: Path,
    root: Path,
    errors: list[dict[str, str]],
) -> list[Path]:
    if not path.is_dir() or _is_reparse(path):
        return []
    directories: list[Path] = []
    for item in path.iterdir():
        if item.name.startswith("."):
            continue
        if _is_reparse(item):
            _unsafe_entry(errors, item, root)
            continue
        if item.is_dir():
            directories.append(item)
    return sorted(directories, key=lambda item: item.name.casefold())


def _contains_markdown(
    path: Path,
    root: Path,
    errors: list[dict[str, str]],
) -> bool:
    found = False
    pending = [path]
    while pending:
        current = pending.pop()
        for item in current.iterdir():
            if _is_reparse(item):
                _unsafe_entry(errors, item, root)
                continue
            if item.is_dir():
                pending.append(item)
            elif item.is_file() and item.suffix.casefold() == ".md":
                found = True
    return found


def inspect_project(root: Path) -> dict[str, list[dict[str, str]]]:
    root = root.absolute()
    errors: list[dict[str, str]] = []
    advisories: list[dict[str, str]] = []

    if _is_reparse(root) or not root.is_dir():
        return {
            "errors": [{
                "code": "unsafe-project-root",
                "path": str(root),
                "message": "项目根必须是普通目录，禁止 symlink/junction/reparse point",
            }],
            "advisories": advisories,
        }

    for name in ("test", "tests"):
        target = root / name
        if _exists_lexical(target):
            errors.append({
                "code": "legacy-test-root",
                "path": name,
                "message": f"顶层 {name}/ 已禁止；测试代码必须迁入 scripts/tests/**",
            })

    doc = root / "doc"
    if not _exists_lexical(doc):
        return {"errors": errors, "advisories": advisories}
    if _is_reparse(doc) or not doc.is_dir():
        errors.append({
            "code": "unsafe-doc-root",
            "path": "doc",
            "message": "doc 必须是项目内普通目录，禁止 symlink/junction/reparse point",
        })
        return {"errors": errors, "advisories": advisories}

    readme_path = doc / "README.md"
    if not readme_path.is_file() or _is_reparse(readme_path):
        errors.append({
            "code": "missing-doc-index",
            "path": "doc/README.md",
            "message": "doc/README.md 是唯一总索引，必须存在且为普通文件",
        })
        return {"errors": errors, "advisories": advisories}

    readme = _read_text(readme_path)
    layout = _delivery_layout(readme)
    if layout is None:
        errors.append({
            "code": "missing-delivery-layout",
            "path": "doc/README.md",
            "message": "缺少 delivery_layout: flat|milestone 单一事实源",
        })

    for item in sorted(doc.iterdir(), key=lambda value: value.name.casefold()):
        if _is_reparse(item):
            _unsafe_entry(errors, item, root)
            continue
        if item.name not in ALLOWED_DOC_ENTRIES:
            errors.append({
                "code": "unexpected-doc-entry",
                "path": item.relative_to(root).as_posix(),
                "message": "doc/ 顶层只允许五层目录和 README.md",
            })

    delivery = doc / "1_delivery"
    if delivery.is_dir() and not _is_reparse(delivery):
        topic_paths: list[Path] = []
        if layout == "flat":
            topic_paths = _visible_directories(delivery, root, errors)
        elif layout == "milestone":
            for milestone in _visible_directories(delivery, root, errors):
                topic_paths.extend(_visible_directories(milestone, root, errors))
        for topic in topic_paths:
            if not _contains_markdown(topic, root, errors):
                continue
            relative = topic.relative_to(delivery).as_posix()
            if relative not in readme and topic.name not in readme:
                errors.append({
                    "code": "unindexed-delivery-topic",
                    "path": topic.relative_to(root).as_posix(),
                    "message": f"活跃 delivery topic 未进入 doc/README.md：{relative}",
                })
            for requirement in topic.glob("requirements_*.md"):
                if _status(requirement) in CLOSED_DELIVERY_STATUSES:
                    advisories.append({
                        "code": "delivery-archive-candidate",
                        "path": requirement.relative_to(root).as_posix(),
                        "message": "交付状态已关闭，可经 $archive-scan 确认归档",
                    })

    bugs = doc / "2_bugs"
    if bugs.is_dir() and not _is_reparse(bugs):
        for bug in sorted(bugs.glob("BUG-*.md"), key=lambda item: item.name.casefold()):
            if bug.name not in readme:
                errors.append({
                    "code": "unindexed-bug",
                    "path": bug.relative_to(root).as_posix(),
                    "message": f"活跃 Bug 未进入 doc/README.md：{bug.name}",
                })
            if _status(bug) in CLOSED_BUG_STATUSES:
                advisories.append({
                    "code": "bug-archive-candidate",
                    "path": bug.relative_to(root).as_posix(),
                    "message": "Bug 状态已解决，可经 $archive-scan 确认归档",
                })

    archive = doc / "4_archive"
    if archive.is_dir() and not _is_reparse(archive):
        for item in sorted(archive.iterdir(), key=lambda value: value.name.casefold()):
            if item.is_file() and item.name != "README.md":
                advisories.append({
                    "code": "legacy-archive-file",
                    "path": item.relative_to(root).as_posix(),
                    "message": "旧式归档仍散放在 4_archive/ 根；后续确认后迁入 legacy/",
                })

    return {"errors": errors, "advisories": advisories}


def _print_human(report: dict[str, list[dict[str, str]]]) -> None:
    for item in report["advisories"]:
        print(f"[project-structure] ADVISORY {item['path']}: {item['message']}", file=sys.stderr)
    for item in report["errors"]:
        print(f"[project-structure] BLOCKED {item['path']}: {item['message']}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_repo_root())
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--pre-commit", action="store_true")
    args = parser.parse_args()
    try:
        report = inspect_project(args.root)
    except Exception as exc:
        print(f"[project-structure] checker failed closed: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_human(report)
    return 2 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
