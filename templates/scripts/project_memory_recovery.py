#!/usr/bin/env python3
"""Fail-closed recovery of explicitly project-owned user memory notes."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path


class RecoveryError(RuntimeError):
    pass


def _lexists(path: Path) -> bool:
    return os.path.lexists(str(path))


def _is_link(path: Path) -> bool:
    try:
        return path.is_symlink() or bool(
            getattr(path.lstat(), "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
    except OSError:
        return True


def _plain_dir(path: Path) -> None:
    if not _lexists(path) or _is_link(path) or not path.is_dir():
        raise RecoveryError(f"abnormal directory: {path}")


def _root(path: Path) -> Path:
    root = path.resolve(strict=True)
    if not (root / ".codex" / ".bridgeforge_codex_version").is_file():
        raise RecoveryError(f"unmanaged project: {root}")
    return root


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _project_field(text: str) -> Path | None:
    match = re.search(
        r"(?mi)^\s*(?:[-*]\s*)?项目\s*[：:]\s*`?([A-Za-z]:[\\/][^`\r\n]+)`?\s*$",
        text,
    )
    if not match:
        return None
    try:
        return Path(match.group(1).strip()).resolve(strict=True)
    except OSError:
        return None


def notes_plan(project_root: Path, notes_root: Path) -> list[dict[str, str]]:
    root = _root(project_root)
    if not _lexists(notes_root):
        return []
    _plain_dir(notes_root)
    found: list[dict[str, str]] = []
    for current, dirs, files in os.walk(notes_root, topdown=True, followlinks=False):
        base = Path(current)
        for name in dirs:
            if _is_link(base / name):
                raise RecoveryError(f"linked notes directory: {base / name}")
        for name in files:
            note = base / name
            if note.suffix.lower() != ".md":
                continue
            if _is_link(note) or not note.is_file():
                raise RecoveryError(f"abnormal note: {note}")
            try:
                owner = _project_field(note.read_text(encoding="utf-8"))
            except OSError as exc:
                raise RecoveryError(f"cannot read note: {note}") from exc
            if owner is not None and os.path.normcase(str(owner)) == os.path.normcase(str(root)):
                found.append({"note": str(note.resolve()), "sha256": _sha(note)})
    return sorted(found, key=lambda item: item["note"])


def _writer():
    path = Path(__file__).with_name("project_memory_writer.py")
    spec = importlib.util.spec_from_file_location("project_memory_writer", path)
    if spec is None or spec.loader is None:
        raise RecoveryError("project memory writer unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def notes_apply(project_root: Path, notes_root: Path, note: Path, source_sha256: str,
                target: str, final_content: str, confirmed: bool) -> dict[str, object]:
    if not confirmed:
        raise RecoveryError("notes apply requires confirmed=True")
    root = _root(project_root)
    candidates = {item["note"]: item["sha256"] for item in notes_plan(root, notes_root)}
    key = str(note.resolve(strict=True))
    if candidates.get(key) != source_sha256 or _sha(note) != source_sha256:
        raise RecoveryError("note is not an unchanged eligible recovery candidate")
    receipt = _writer().write_project_memory(root, target, final_content)
    if _sha(note) != source_sha256:
        raise RecoveryError("source changed before deletion")
    note.unlink()
    return {"source": key, "deleted": True, "writer": receipt.to_dict()}


def orphan_plan(orphan_root: Path) -> dict[str, object]:
    _plain_dir(orphan_root)
    entries = sorted(path.name for path in orphan_root.iterdir())
    allowed = {"MEMORY.md", "MEMORY_COLD.md", "_stats.json"}
    stats = orphan_root / "_stats.json"
    hot = orphan_root / "MEMORY.md"
    cold = orphan_root / "MEMORY_COLD.md"
    try:
        empty = json.loads(stats.read_text(encoding="utf-8")).get("files", None) == {}
    except Exception:
        empty = False
    try:
        empty_indexes = "- [" not in hot.read_text(encoding="utf-8") and "- [" not in cold.read_text(encoding="utf-8")
    except OSError:
        empty_indexes = False
    eligible = set(entries) == allowed and empty and empty_indexes and all(
        (orphan_root / name).is_file() and not _is_link(orphan_root / name)
        for name in allowed
    )
    fingerprint = hashlib.sha256(
        "\n".join(entries + [_sha(orphan_root / name) if (orphan_root / name).exists() else "" for name in sorted(allowed)]).encode("utf-8")
    ).hexdigest()
    return {"path": str(orphan_root.resolve()), "eligible": eligible, "fingerprint": fingerprint}


def orphan_apply(orphan_root: Path, fingerprint: str, confirmed: bool) -> dict[str, object]:
    if not confirmed:
        raise RecoveryError("orphan apply requires confirmed=True")
    plan = orphan_plan(orphan_root)
    if not plan["eligible"] or plan["fingerprint"] != fingerprint:
        raise RecoveryError("orphan directory no longer matches approved empty plan")
    shutil.rmtree(orphan_root)
    return {"path": plan["path"], "deleted": True}


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("notes-plan", "notes-apply"):
        p = sub.add_parser(name); p.add_argument("--project-root", type=Path, required=True); p.add_argument("--notes-root", type=Path, required=True)
    apply = sub.choices["notes-apply"]
    apply.add_argument("--confirmed", action="store_true"); apply.add_argument("--note", type=Path, required=True); apply.add_argument("--source-sha256", required=True); apply.add_argument("--target", required=True); apply.add_argument("--content-file", type=Path, required=True)
    for name in ("orphan-plan", "orphan-apply"):
        p = sub.add_parser(name); p.add_argument("--orphan-root", type=Path, required=True)
    orphan = sub.choices["orphan-apply"]
    orphan.add_argument("--confirmed", action="store_true"); orphan.add_argument("--plan-fingerprint", required=True)
    args = parser.parse_args()
    try:
        if args.command == "notes-plan": out = notes_plan(args.project_root, args.notes_root)
        elif args.command == "notes-apply": out = notes_apply(args.project_root, args.notes_root, args.note, args.source_sha256, args.target, args.content_file.read_text(encoding="utf-8"), args.confirmed)
        elif args.command == "orphan-plan": out = orphan_plan(args.orphan_root)
        else: out = orphan_apply(args.orphan_root, args.plan_fingerprint, args.confirmed)
    except (RecoveryError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(out, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
