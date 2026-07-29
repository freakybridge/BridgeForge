#!/usr/bin/env python3
"""Write one verified project memory file and rebuild its deterministic index."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

INDEX_NAMES = {"MEMORY.md", "MEMORY_COLD.md"}
MARKER_RELATIVE = Path(".codex") / ".bridgeforge_version"
MEMORY_RELATIVE = Path(".codex") / "memory"
REBUILD_RELATIVE = Path(".codex") / "scripts" / "memory_rebuild_index.py"


class ProjectMemoryWriteError(RuntimeError):
    """The requested write cannot be proven to stay inside project memory."""


@dataclass(frozen=True)
class WriteReceipt:
    project_root: str
    target: str
    bytes_written: int
    sha256: str
    index: str
    rebuild_command: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _lexists(path: Path) -> bool:
    return os.path.lexists(str(path))


def _is_link(path: Path) -> bool:
    """Return True for symlinks and Windows reparse-point junctions."""
    try:
        if path.is_symlink():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            return True
        absolute = os.path.normcase(os.path.abspath(str(path)))
        resolved = os.path.normcase(os.path.realpath(str(path)))
        return path.is_dir() and absolute != resolved
    except OSError:
        return False


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left)) == os.path.normcase(str(right))


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _require_plain_directory(path: Path, label: str) -> None:
    if not _lexists(path) or _is_link(path) or not path.is_dir():
        raise ProjectMemoryWriteError(f"{label} is not a plain directory: {path}")


def _require_plain_file(path: Path, label: str) -> None:
    if not _lexists(path) or _is_link(path) or not path.is_file():
        raise ProjectMemoryWriteError(f"{label} is not a plain file: {path}")


def _validate_relative_target(relative_target: str | Path) -> Path:
    raw = str(relative_target)
    target = Path(raw)
    if (
        not raw
        or target.is_absolute()
        or bool(target.drive)
        or bool(target.root)
        or any(part in {"", ".", ".."} for part in target.parts)
    ):
        raise ProjectMemoryWriteError(
            f"target must be a clean relative path: {relative_target}"
        )
    if (
        target.suffix.lower() != ".md"
        or target.name in INDEX_NAMES
        or target.name.startswith("_")
    ):
        raise ProjectMemoryWriteError(
            f"target must be a non-index Markdown memory file: {relative_target}"
        )
    return target


@dataclass(frozen=True)
class _ValidatedPaths:
    project_root: Path
    memory_root: Path
    target_relative: Path
    target: Path
    rebuild_script: Path


def validate_write_target(
    project_root: str | Path, relative_target: str | Path
) -> _ValidatedPaths:
    root_input = Path(project_root)
    if not root_input.is_absolute():
        raise ProjectMemoryWriteError(
            f"project root must be absolute: {project_root}"
        )
    _require_plain_directory(root_input, "project root")
    root = root_input.resolve(strict=True)
    if not _same_path(root_input.absolute(), root):
        raise ProjectMemoryWriteError(
            f"project root resolves through a link: {project_root}"
        )

    codex = root / ".codex"
    marker = root / MARKER_RELATIVE
    memory = root / MEMORY_RELATIVE
    rebuild = root / REBUILD_RELATIVE
    _require_plain_directory(codex, "project .codex directory")
    _require_plain_file(marker, "BridgeForge project marker")
    _require_plain_directory(memory, "project memory directory")
    _require_plain_file(rebuild, "project memory index rebuilder")

    memory_resolved = memory.resolve(strict=True)
    if not _same_path(memory.absolute(), memory_resolved):
        raise ProjectMemoryWriteError(
            f"project memory resolves through a link: {memory}"
        )

    relative = _validate_relative_target(relative_target)
    target = memory / relative
    current = memory
    for part in relative.parts[:-1]:
        current = current / part
        if _lexists(current):
            _require_plain_directory(current, "target parent")

    if _lexists(target):
        _require_plain_file(target, "target")
        if not os.access(target, os.W_OK):
            raise ProjectMemoryWriteError(f"target is not writable: {target}")
        resolved_target = target.resolve(strict=True)
        if not _is_within(resolved_target, memory_resolved):
            raise ProjectMemoryWriteError(
                f"target resolves outside project memory: {target}"
            )
    else:
        existing_parent = target.parent
        while not _lexists(existing_parent):
            existing_parent = existing_parent.parent
        _require_plain_directory(existing_parent, "target parent")
        if not _is_within(existing_parent.resolve(strict=True), memory_resolved):
            raise ProjectMemoryWriteError(
                f"target parent resolves outside project memory: {existing_parent}"
            )
        if not os.access(existing_parent, os.W_OK):
            raise ProjectMemoryWriteError(
                f"target parent is not writable: {existing_parent}"
            )

    return _ValidatedPaths(root, memory_resolved, relative, target, rebuild)


def _atomic_write(path: Path, payload: bytes) -> None:
    temporary = path.parent / f".{path.name}.bridgeforge-{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if _lexists(temporary):
            temporary.unlink()


def _run_rebuilder(paths: _ValidatedPaths) -> tuple[str, ...]:
    command = (sys.executable, "-B", str(paths.rebuild_script))
    result = subprocess.run(
        list(command),
        cwd=paths.project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise ProjectMemoryWriteError(
            f"memory index rebuild failed with exit {result.returncode}: {detail}"
        )
    return command


def _verify_index(paths: _ValidatedPaths) -> str:
    expected_link = f"]({paths.target_relative.as_posix()})"
    for name in ("MEMORY.md", "MEMORY_COLD.md"):
        index = paths.memory_root / name
        _require_plain_file(index, "memory index")
        try:
            text = index.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProjectMemoryWriteError(
                f"cannot read rebuilt memory index {index}: {exc}"
            ) from exc
        if expected_link in text:
            return name
    raise ProjectMemoryWriteError(
        f"rebuilt indexes do not reference target: {paths.target_relative.as_posix()}"
    )


def write_project_memory(
    project_root: str | Path,
    relative_target: str | Path,
    final_content: str,
) -> WriteReceipt:
    """Write caller-supplied final content; this function never merges text."""
    if not isinstance(final_content, str):
        raise ProjectMemoryWriteError("final_content must be text")
    paths = validate_write_target(project_root, relative_target)
    payload = final_content.encode("utf-8")

    existed = _lexists(paths.target)
    previous = paths.target.read_bytes() if existed else None
    created_directories: list[Path] = []
    current = paths.memory_root
    try:
        for part in paths.target_relative.parts[:-1]:
            current = current / part
            if not _lexists(current):
                current.mkdir()
                created_directories.append(current)
            _require_plain_directory(current, "target parent")
        _atomic_write(paths.target, payload)
        if paths.target.read_bytes() != payload:
            raise ProjectMemoryWriteError(
                f"written target failed content verification: {paths.target}"
            )
        command = _run_rebuilder(paths)
        index = _verify_index(paths)
    except Exception as exc:
        rollback_error = ""
        try:
            if previous is None:
                if _lexists(paths.target):
                    _require_plain_file(paths.target, "rollback target")
                    paths.target.unlink()
            else:
                _atomic_write(paths.target, previous)
            for directory in reversed(created_directories):
                try:
                    directory.rmdir()
                except OSError:
                    break
            try:
                _run_rebuilder(paths)
            except Exception as rebuild_exc:
                rollback_error = f"; rollback index rebuild also failed: {rebuild_exc}"
        except Exception as restore_exc:
            rollback_error = f"; rollback failed: {restore_exc}"
        if isinstance(exc, ProjectMemoryWriteError):
            raise ProjectMemoryWriteError(f"{exc}{rollback_error}") from exc
        raise ProjectMemoryWriteError(
            f"project memory write failed: {exc}{rollback_error}"
        ) from exc

    return WriteReceipt(
        project_root=str(paths.project_root),
        target=paths.target_relative.as_posix(),
        bytes_written=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        index=index,
        rebuild_command=command,
    )


def _read_content_file(value: str) -> str:
    if value == "-":
        return sys.stdin.read()
    return Path(value).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument(
        "--content-file",
        required=True,
        help="UTF-8 final merged body, or - to read stdin",
    )
    args = parser.parse_args(argv)
    try:
        receipt = write_project_memory(
            args.project_root,
            args.target,
            _read_content_file(args.content_file),
        )
    except (OSError, UnicodeError, ProjectMemoryWriteError) as exc:
        print(
            json.dumps(
                {"ok": False, "error": str(exc)}, ensure_ascii=False
            )
        )
        return 1
    print(json.dumps({"ok": True, "receipt": receipt.to_dict()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
