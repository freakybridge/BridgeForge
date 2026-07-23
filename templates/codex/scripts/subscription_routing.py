#!/usr/bin/env python3
"""Persist and apply a project-local Codex subscription routing tier."""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

MARKER_NAME = "subscription-tier.toml"
POLICIES = {
    "high": {
        "main_model": "gpt-5.6-terra",
        "main_effort": "high",
        "implementation_model": "gpt-5.6-sol",
        "implementation_effort": "high",
    },
    "conservative": {
        "main_model": "gpt-5.6-terra",
        "main_effort": "medium",
        "implementation_model": "gpt-5.6-terra",
        "implementation_effort": "high",
    },
}


def _lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path.expanduser())))


def _path_key(path: Path) -> str:
    return os.path.normcase(os.fspath(path))


def _resolve_real(path: Path) -> Path:
    try:
        return path.expanduser().resolve(strict=False)
    except OSError as exc:
        raise ValueError(f"cannot resolve path safely: {path}: {exc}") from exc


def _same_path(left: Path, right: Path) -> bool:
    return _path_key(left) == _path_key(right)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        return os.path.commonpath((_path_key(path), _path_key(parent))) == _path_key(parent)
    except ValueError:
        return False


def _validate_layout(
    project_root: Path,
    template_root: Path,
) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    home = _lexical(Path.home())
    project_lexical = _lexical(project_root)
    if _same_path(project_lexical, home):
        raise ValueError(
            "refusing user-level Codex path; --project-root must be a project root, not ~ or ~/.codex"
        )

    project_root = _resolve_real(project_lexical)
    template_root = _resolve_real(_lexical(template_root))
    user_codex = _resolve_real(Path.home() / ".codex")

    if _is_within(project_root, user_codex):
        raise ValueError(
            "refusing user-level Codex path; --project-root must be a project root, not ~/.codex"
        )
    if _is_within(template_root, user_codex):
        raise ValueError(
            "refusing user-level Codex path; --template-root must not read from ~/.codex"
        )
    if not project_root.is_dir():
        raise ValueError(f"project root is not a directory: {project_root}")
    if not template_root.is_dir():
        raise ValueError(f"template root is not a directory: {template_root}")

    project_codex = _resolve_real(project_root / ".codex")
    config = _resolve_real(project_codex / "config.toml")
    implementation = _resolve_real(project_codex / "agents" / "implementation-worker.toml")
    marker = _resolve_real(project_codex / MARKER_NAME)
    targets = (project_codex, config, implementation, marker)
    if any(_is_within(target, user_codex) for target in targets):
        raise ValueError("refusing user-level Codex target resolved under ~/.codex")
    if any(not _is_within(target, project_root) for target in targets):
        raise ValueError("refusing project .codex target resolved outside --project-root")

    config_template = _resolve_real(template_root / "config.toml")
    implementation_template = _resolve_real(
        template_root / "agents" / "implementation-worker.toml"
    )
    sources = (config_template, implementation_template)
    if any(_is_within(source, user_codex) for source in sources):
        raise ValueError("refusing template source resolved under ~/.codex")
    if any(not _is_within(source, template_root) for source in sources):
        raise ValueError("refusing template source resolved outside --template-root")
    if not config_template.is_file():
        raise ValueError(f"required template file missing: {config_template}")
    if not implementation_template.is_file():
        raise ValueError(f"required template file missing: {implementation_template}")

    return (
        project_root,
        config,
        implementation,
        marker,
        config_template,
        implementation_template,
        project_codex,
    )


def _set_toml_string(text: str, key: str, value: str) -> str:
    pattern = re.compile(
        rf'^(\s*{re.escape(key)}\s*=\s*)"[^"]*"(\s*(?:#.*)?)$',
        re.MULTILINE,
    )
    replacement = rf'\1"{value}"\2'
    updated, count = pattern.subn(replacement, text, count=1)
    if count:
        return updated

    assignment = f'{key} = "{value}"'
    section = re.search(r"(?m)^\s*\[", text)
    if section:
        return text[: section.start()].rstrip() + "\n" + assignment + "\n\n" + text[section.start() :]
    return text.rstrip() + "\n" + assignment + "\n"


def _encoded_text(text: str, newline_source: str) -> bytes:
    newline = "\r\n" if "\r\n" in newline_source else "\n"
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)
    return normalized.encode("utf-8")


def _read_base_text(target: Path, template: Path) -> str:
    source = target if target.exists() else template
    if not source.is_file():
        raise ValueError(f"target is not a file: {source}")
    return source.read_text(encoding="utf-8")


def _stage_bytes(target: Path, data: bytes, kind: str) -> Path:
    descriptor, name = tempfile.mkstemp(
        prefix=f".{target.name}.bridgeforge-{kind}-",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        staged = _resolve_real(Path(name))
    except Exception:
        os.close(descriptor)
        Path(name).unlink(missing_ok=True)
        raise
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        staged.unlink(missing_ok=True)
        raise
    return staged


def _replace_file(source: Path, target: Path) -> None:
    source.replace(target)


def _create_parent_dirs(targets: tuple[Path, ...]) -> list[Path]:
    missing: set[Path] = set()
    for target in targets:
        cursor = target.parent
        while not cursor.exists():
            missing.add(cursor)
            cursor = cursor.parent
    for parent in sorted({target.parent for target in targets}, key=lambda item: len(item.parts)):
        parent.mkdir(parents=True, exist_ok=True)
    return sorted(missing, key=lambda item: len(item.parts), reverse=True)


def _cleanup_paths(paths: list[Path]) -> None:
    for path in paths:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _replace_transaction(updates: tuple[tuple[Path, bytes], ...]) -> None:
    originals = {
        target: target.read_bytes() if target.exists() else None
        for target, _data in updates
    }
    created_dirs = _create_parent_dirs(tuple(target for target, _data in updates))
    staged: dict[Path, Path] = {}
    backups: dict[Path, Path] = {}
    committed: list[Path] = []

    try:
        for target, data in updates:
            staged[target] = _stage_bytes(target, data, "new")
        for target, original in originals.items():
            if original is not None:
                backups[target] = _stage_bytes(target, original, "backup")

        for target, _data in updates:
            _replace_file(staged[target], target)
            committed.append(target)
    except Exception as exc:
        rollback_errors: list[str] = []
        for target in reversed(committed):
            try:
                original = originals[target]
                if original is None:
                    target.unlink(missing_ok=True)
                else:
                    _replace_file(backups[target], target)
                    backups.pop(target, None)
            except Exception as rollback_exc:
                rollback_errors.append(f"{target}: {rollback_exc}")
        _cleanup_paths([*staged.values(), *backups.values()])
        for directory in created_dirs:
            try:
                directory.rmdir()
            except OSError:
                pass
        if rollback_errors:
            raise OSError(
                f"subscription routing write failed ({exc}); rollback also failed: "
                + "; ".join(rollback_errors)
            ) from exc
        raise
    else:
        _cleanup_paths([*backups.values()])


def apply_tier(project_root: Path, template_root: Path, tier: str) -> None:
    (
        _project_root,
        config,
        implementation,
        marker_path,
        config_template,
        implementation_template,
        _project_codex,
    ) = _validate_layout(project_root, template_root)
    policy = POLICIES[tier]
    config_base = _read_base_text(config, config_template)
    config_text = config_base
    config_text = _set_toml_string(config_text, "model", policy["main_model"])
    config_text = _set_toml_string(
        config_text,
        "model_reasoning_effort",
        policy["main_effort"],
    )
    implementation_base = _read_base_text(implementation, implementation_template)
    implementation_text = implementation_base
    implementation_text = _set_toml_string(
        implementation_text,
        "model",
        policy["implementation_model"],
    )
    implementation_text = _set_toml_string(
        implementation_text,
        "model_reasoning_effort",
        policy["implementation_effort"],
    )
    marker = (
        '# Project-local Codex routing tier selected explicitly through /bridgeforge.\n'
        '# BridgeForge must never infer this value from account or billing data.\n'
        'schema_version = "1"\n'
        f'tier = "{tier}"\n'
        'selection_source = "user-declared-via-bridgeforge"\n'
    )
    _replace_transaction(
        (
            (config, _encoded_text(config_text, config_base)),
            (
                implementation,
                _encoded_text(implementation_text, implementation_base),
            ),
            (marker_path, marker.encode("utf-8")),
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", choices=sorted(POLICIES), required=True)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--template-root", type=Path, required=True)
    args = parser.parse_args()

    try:
        apply_tier(args.project_root, args.template_root, args.tier)
    except (OSError, ValueError) as exc:
        print(f"[subscription-routing] ERROR: {exc}", file=sys.stderr)
        return 2

    policy = POLICIES[args.tier]
    print(
        f"[subscription-routing] tier={args.tier} "
        f"main={policy['main_model']}+{policy['main_effort']} "
        f"implementation={policy['implementation_model']}+{policy['implementation_effort']} "
        f"marker=.codex/{MARKER_NAME}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
