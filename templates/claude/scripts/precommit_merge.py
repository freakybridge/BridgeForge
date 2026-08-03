#!/usr/bin/env python3
"""Safely merge a BridgeForge-managed pre-commit block into a downstream hook.

The downstream hook has two explicit regions.  BridgeForge owns only the
managed region; the project extension is retained byte-for-byte.  An existing
hook without a complete, unambiguous layout is a conflict, never a candidate
for whole-file replacement.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


MANAGED_BEGIN = b"# >>> BRIDGEFORGE_MANAGED_BEGIN"
MANAGED_END = b"# <<< BRIDGEFORGE_MANAGED_END"
EXTENSION_BEGIN = b"# >>> PROJECT_EXTENSION_BEGIN"
EXTENSION_END = b"# <<< PROJECT_EXTENSION_END"
MARKERS = (MANAGED_BEGIN, MANAGED_END, EXTENSION_BEGIN, EXTENSION_END)
LEGACY_VERSION_BUMP_BEGIN = b"# === Step 2: VERSION bump"
LEGACY_VERSION_BUMP_COMMAND = b"scripts/bump_version.py"
LEGACY_VERSION_BUMP_STAGE = b"git add VERSION"
# SHA-256 values of the complete, marker-free BridgeForge managed hooks from
# the last release before PROJECT_EXTENSION boundaries were introduced.  A
# legacy migration is safe only when its whole prefix matches one of these
# frozen artifacts byte-for-byte; substring signatures are not ownership.
KNOWN_LEGACY_MANAGED_SHA256 = frozenset(
    {
        "e66c52daa9d5ef7c2cbb10d99a3f5544e5cc3b784a79b3e682d11e76724e7773",
        "404b4b0754e6d4b9a2e1f27278d191c5533259049a96b49bc7f5d376d870c345",
    }
)


class MergeBlocked(RuntimeError):
    """Raised when ownership of a downstream hook cannot be proven."""


@dataclass(frozen=True)
class Layout:
    managed_start: int
    managed_end: int
    extension_body_start: int
    extension_body_end: int


@dataclass(frozen=True)
class MergePlan:
    target: Path
    before: bytes | None
    after: bytes
    extension_sha256: str | None
    legacy_version_extension_migrated: bool = False


def _marker_lines(payload: bytes, path: Path) -> dict[bytes, tuple[int, int]]:
    positions: dict[bytes, list[tuple[int, int]]] = {marker: [] for marker in MARKERS}
    offset = 0
    for line in payload.splitlines(keepends=True):
        marker = line.rstrip(b"\r\n")
        if marker in positions:
            positions[marker].append((offset, offset + len(line)))
        offset += len(line)
    missing_or_duplicate = [
        marker.decode("ascii")
        for marker, values in positions.items()
        if len(values) != 1
    ]
    if missing_or_duplicate:
        raise MergeBlocked(
            f"{path}: pre-commit must contain exactly one complete managed and "
            f"project-extension boundary; invalid markers: {', '.join(missing_or_duplicate)}"
        )
    return {marker: values[0] for marker, values in positions.items()}


def parse_layout(payload: bytes, path: Path, *, template: bool = False) -> Layout:
    positions = _marker_lines(payload, path)
    managed_begin = positions[MANAGED_BEGIN]
    managed_end = positions[MANAGED_END]
    extension_begin = positions[EXTENSION_BEGIN]
    extension_end = positions[EXTENSION_END]
    if not (
        managed_begin[0] < managed_end[0] < extension_begin[0] < extension_end[0]
    ):
        raise MergeBlocked(f"{path}: pre-commit boundaries are out of order")
    if payload[:managed_begin[0]] not in (b"#!/bin/sh\n", b"#!/bin/sh\r\n"):
        raise MergeBlocked(f"{path}: only the #!/bin/sh line may precede BridgeForge")
    if payload[managed_end[1]:extension_begin[0]].strip() or payload[extension_end[1]:].strip():
        raise MergeBlocked(f"{path}: project code must stay inside PROJECT_EXTENSION markers")
    layout = Layout(
        managed_start=managed_begin[0],
        managed_end=managed_end[1],
        extension_body_start=extension_begin[1],
        extension_body_end=extension_end[0],
    )
    if template and payload[layout.extension_body_start:layout.extension_body_end].strip():
        raise MergeBlocked(f"{path}: template PROJECT_EXTENSION must be empty")
    return layout


def _legacy_version_extension(payload: bytes) -> bytes | None:
    """Return the one historical project-owned VERSION section, if proven.

    Before explicit ownership markers existed, BridgeForge's published hook put
    the project version-bump section after a stable ``Step 2`` heading.  The
    preceding managed bytes must exactly match a frozen historical template;
    every other unmarked hook remains blocked rather than guessed at.
    """
    if any(marker in payload for marker in MARKERS):
        return None
    if not payload.startswith((b"#!/bin/sh\n", b"#!/bin/sh\r\n")):
        return None
    if payload.count(LEGACY_VERSION_BUMP_BEGIN) != 1:
        return None
    extension_start = payload.index(LEGACY_VERSION_BUMP_BEGIN)
    # The historical section was separated from the managed body by one blank
    # line.  Preserve that separator as part of the project-owned bytes,
    # including legacy files with mixed LF/CRLF line endings.
    if payload[:extension_start].endswith((b"\r\n\r\n", b"\n\r\n")):
        extension_start -= 2
    elif payload[:extension_start].endswith(b"\n\n"):
        extension_start -= 1
    managed = payload[:extension_start]
    extension = payload[extension_start:]
    if (
        hashlib.sha256(managed).hexdigest() not in KNOWN_LEGACY_MANAGED_SHA256
        or LEGACY_VERSION_BUMP_COMMAND not in extension
        or not extension.rstrip(b"\r\n").endswith(LEGACY_VERSION_BUMP_STAGE)
    ):
        return None
    return extension


def build_plan(project_root: Path, template_path: Path) -> MergePlan:
    template = template_path.read_bytes()
    template_layout = parse_layout(template, template_path, template=True)
    target = project_root / ".githooks" / "pre-commit"
    if not target.exists():
        return MergePlan(target, None, template, None)
    if not target.is_file():
        raise MergeBlocked(f"{target}: pre-commit is not a regular file")
    before = target.read_bytes()
    try:
        target_layout = parse_layout(before, target)
    except MergeBlocked:
        extension = _legacy_version_extension(before)
        if extension is None:
            raise
        after = (
            template[:template_layout.extension_body_start]
            + extension
            + template[template_layout.extension_body_end:]
        )
        return MergePlan(
            target,
            before,
            after,
            hashlib.sha256(extension).hexdigest(),
            legacy_version_extension_migrated=True,
        )
    extension = before[target_layout.extension_body_start:target_layout.extension_body_end]
    after = (
        before[:target_layout.managed_start]
        + template[template_layout.managed_start:template_layout.managed_end]
        + before[target_layout.managed_end:]
    )
    return MergePlan(
        target,
        before,
        after,
        hashlib.sha256(extension).hexdigest(),
    )


def _render_diff(path: Path, before: bytes, after: bytes) -> str:
    try:
        before_text = before.decode("utf-8")
        after_text = after.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MergeBlocked(f"{path}: pre-commit must be UTF-8 text: {exc}") from exc
    return "".join(
        difflib.unified_diff(
            before_text.splitlines(keepends=True),
            after_text.splitlines(keepends=True),
            fromfile=str(path),
            tofile=f"{path} (merged)",
        )
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    temporary = Path(raw_temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--template-precommit", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmed", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = build_plan(Path(args.project_root).resolve(), args.template_precommit.resolve())
        before = plan.before or b""
        print(_render_diff(plan.target, before, plan.after), end="")
        if plan.extension_sha256:
            print(f"project_extension_sha256={plan.extension_sha256}")
        if plan.legacy_version_extension_migrated:
            print("legacy_version_extension_migrated=true")
        if not args.apply:
            return 0
        if not args.confirmed:
            raise MergeBlocked("--apply requires --confirmed after diff review")
        if plan.before is not None and plan.target.read_bytes() != plan.before:
            raise MergeBlocked(f"{plan.target}: changed after planning; refusing to replace")
        _atomic_write(plan.target, plan.after)
        verified = build_plan(Path(args.project_root).resolve(), args.template_precommit.resolve())
        if verified.after != plan.after:
            raise MergeBlocked("post-write verification is not idempotent")
    except (MergeBlocked, OSError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print("APPLIED: BridgeForge managed pre-commit block updated; project extension preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
