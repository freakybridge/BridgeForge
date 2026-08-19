#!/usr/bin/env python3
"""Plan/apply the Codex project hook single-source migration.

The default mode is read-only and prints a unified diff.  ``--apply`` requires
``--confirmed`` and updates only hook configuration.  The project transaction
executor owns validation, rollback, and the final bridgeforge-codex version stamp.
"""
from __future__ import annotations

import argparse
import copy
import difflib
import json
import os
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from hook_config_policy import TomlHeaderError, has_hooks_table
from hooks_ownership import (
    HooksOwnershipError,
    canonicalize,
    expected_groups,
    load_json_object,
)
MIN_PYTHON = (3, 11)
PROJECT_MANAGED_PREFIX = "bridgeforge-codex.project-hook.v1:"


class MergeBlocked(RuntimeError):
    pass


def _python_version_error(version_info: object = sys.version_info) -> str | None:
    major = int(getattr(version_info, "major", version_info[0]))  # type: ignore[index]
    minor = int(getattr(version_info, "minor", version_info[1]))  # type: ignore[index]
    if (major, minor) >= MIN_PYTHON:
        return None
    return (
        f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required; "
        f"running {major}.{minor}"
    )


def _load_json(path: Path, default: dict | None = None) -> dict:
    if not path.is_file() and default is not None:
        return copy.deepcopy(default)
    try:
        value = load_json_object(path.read_bytes(), str(path))
    except (OSError, HooksOwnershipError) as exc:
        raise MergeBlocked(f"invalid JSON: {path}: {exc}") from exc
    return value


def _append_unique_events(target: dict, source_events: object) -> None:
    if source_events is None:
        return
    if not isinstance(source_events, dict):
        raise MergeBlocked("settings/hooks value must be an object")
    events = target.setdefault("hooks", {})
    if not isinstance(events, dict):
        raise MergeBlocked("hooks.json 'hooks' must be an object")
    for event, blocks in source_events.items():
        if not isinstance(blocks, list):
            raise MergeBlocked(f"hook event must be an array: {event}")
        bucket = events.setdefault(event, [])
        if not isinstance(bucket, list):
            raise MergeBlocked(f"hook event must be an array: {event}")
        seen = {json.dumps(item, sort_keys=True, ensure_ascii=False) for item in bucket}
        for block in blocks:
            key = json.dumps(block, sort_keys=True, ensure_ascii=False)
            if key not in seen:
                bucket.append(copy.deepcopy(block))
                seen.add(key)


def build_plan(project_root: Path, template_hooks: Path) -> tuple[dict, dict, list[dict]]:
    codex = project_root / ".codex"
    hooks_path = codex / "hooks.json"
    settings_path = codex / "settings.json"
    config_path = codex / "config.toml"
    if config_path.is_file():
        try:
            if has_hooks_table(config_path.read_text(encoding="utf-8")):
                raise MergeBlocked(".codex/config.toml contains a forbidden hooks table")
        except TomlHeaderError as exc:
            raise MergeBlocked(f".codex/config.toml has an invalid table header: {exc}") from exc

    existing_hooks = _load_json(hooks_path, {"hooks": {}})
    settings = _load_json(settings_path, {})
    template = _load_json(template_hooks)

    combined = copy.deepcopy(existing_hooks)
    _append_unique_events(combined, settings.get("hooks"))
    clean = combined
    removed: list[dict] = []
    try:
        expected = expected_groups(
            template,
            managed_prefix=PROJECT_MANAGED_PREFIX,
        )
        clean, _external, receipts = canonicalize(
            clean,
            expected,
            managed_prefixes=(PROJECT_MANAGED_PREFIX,),
            label=str(hooks_path),
            managed_looking=lambda _handler: False,
            managed_top_level={"description": template.get("description")},
        )
    except HooksOwnershipError as exc:
        raise MergeBlocked(str(exc)) from exc
    removed.extend(
        {"bridgeforgeCodexId": item["id"], "action": item["action"]}
        for item in receipts
        if item["action"] != "add-missing"
    )
    new_settings = copy.deepcopy(settings)
    new_settings.pop("hooks", None)
    return clean, new_settings, removed


def _render(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def _diff(path: Path, before: str, after: str) -> str:
    return "".join(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True),
        fromfile=str(path), tofile=str(path) + " (merged)",
    ))


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Codex may protect .codex/ from creating arbitrary temporary files even
    # when replacement of its managed configuration is permitted.  Stage next
    # to that directory instead: it remains on the same filesystem, so
    # os.replace keeps its atomic-replacement guarantee on Windows.
    staging_dir = path.parent.parent if path.parent.name == ".codex" else path.parent
    fd, raw = tempfile.mkstemp(prefix=path.name + ".", dir=str(staging_dir))
    tmp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def main(
    argv: list[str] | None = None,
    version_info: object = sys.version_info,
) -> int:
    version_error = _python_version_error(version_info)
    if version_error:
        print(f"BLOCKED: {version_error}", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--template-hooks", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmed", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    hooks_path = root / ".codex" / "hooks.json"
    settings_path = root / ".codex" / "settings.json"
    try:
        hooks, settings, removed = build_plan(root, Path(args.template_hooks).resolve())
    except (MergeBlocked, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2

    old_hooks = hooks_path.read_text(encoding="utf-8") if hooks_path.is_file() else ""
    old_settings = settings_path.read_text(encoding="utf-8") if settings_path.is_file() else ""
    new_hooks = _render(hooks)
    new_settings = _render(settings)
    print(_diff(hooks_path, old_hooks, new_hooks), end="")
    print(_diff(settings_path, old_settings, new_settings), end="")
    print(f"managed_handlers_replaced={len(removed)}")
    if not args.apply:
        return 0
    if not args.confirmed:
        print("BLOCKED: --apply requires --confirmed after diff review", file=sys.stderr)
        return 2

    original_hooks = old_hooks if hooks_path.is_file() else None
    original_settings = old_settings if settings_path.is_file() else None
    try:
        _atomic_write(hooks_path, new_hooks)
        _atomic_write(settings_path, new_settings)
        # Re-parse and re-check the committed shape. The project finalizer is
        # the sole owner of the bridgeforge-codex version stamp.
        verified_hooks, verified_settings, _ = build_plan(root, Path(args.template_hooks).resolve())
        if _render(verified_hooks) != new_hooks or _render(verified_settings) != new_settings:
            raise MergeBlocked("post-write verification is not idempotent")
    except Exception as exc:
        if original_hooks is None:
            hooks_path.unlink(missing_ok=True)
        else:
            _atomic_write(hooks_path, original_hooks)
        if original_settings is None:
            settings_path.unlink(missing_ok=True)
        else:
            _atomic_write(settings_path, original_settings)
        print(f"BLOCKED: apply rolled back: {exc}", file=sys.stderr)
        return 2
    print("APPLIED: hooks single-source migration verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
