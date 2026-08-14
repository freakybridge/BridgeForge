#!/usr/bin/env python3
"""Finalize one BridgeForge project update only after all hard gates pass."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


HOSTS = ("codex", "claude")
SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")


class FinalizeBlocked(RuntimeError):
    """The project is not eligible for a new BridgeForge version stamp."""


def _run_check(command: list[str], cwd: Path, label: str) -> None:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise FinalizeBlocked(f"{label} timed out after 60 seconds") from exc
    except OSError as exc:
        raise FinalizeBlocked(f"{label} could not start: {exc}") from exc
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
    if result.returncode != 0:
        raise FinalizeBlocked(f"{label} failed with exit code {result.returncode}")


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    temporary = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _inside(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise FinalizeBlocked(f"{label} escapes the project root: {resolved}") from exc
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--template-root", required=True)
    parser.add_argument("--host", choices=HOSTS, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--confirmed", action="store_true")
    args = parser.parse_args(argv)

    if sys.version_info < (3, 11):
        print("BLOCKED: BridgeForge finalizer requires Python 3.11+", file=sys.stderr)
        return 2
    if not args.confirmed:
        print("BLOCKED: finalization requires --confirmed", file=sys.stderr)
        return 2
    version = args.version.strip()
    if not SEMVER_RE.fullmatch(version):
        print(f"BLOCKED: invalid stable SemVer version: {version!r}", file=sys.stderr)
        return 2

    project_root = Path(args.project_root).resolve()
    template_root = Path(args.template_root).resolve()
    if not project_root.is_dir():
        print(f"BLOCKED: project root is not a directory: {project_root}", file=sys.stderr)
        return 2
    host_dir = project_root / f".{args.host}"
    if not host_dir.is_dir():
        print(f"BLOCKED: target host directory is missing: {host_dir}", file=sys.stderr)
        return 2

    try:
        lint = template_root / "templates" / args.host / "hooks" / "memory_lint.py"
        if not lint.is_file():
            raise FinalizeBlocked(f"canonical memory linter is missing: {lint}")
        health = _inside(
            host_dir / "hooks" / "config_health_check.py",
            project_root,
            "config health check",
        )
        if not health.is_file():
            raise FinalizeBlocked(f"project config health check is missing: {health}")

        _run_check(
            [
                sys.executable,
                str(lint),
                "--organize",
                "--project-root",
                str(project_root),
                "--host",
                args.host,
            ],
            project_root,
            "memory schema audit",
        )
        _run_check(
            [sys.executable, str(health), "--strict"],
            project_root,
            "config health check",
        )

        stamp = _inside(
            host_dir / ".bridgeforge_version",
            project_root,
            "version stamp",
        )
        _atomic_write(stamp, version + "\n")
    except FinalizeBlocked as exc:
        print(f"BLOCKED: {exc}; version stamp was not changed", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"BLOCKED: finalization I/O failed: {exc}; version stamp was not changed", file=sys.stderr)
        return 2

    print(
        f"FINALIZED: host={args.host} version={version} "
        "memory_schema=clean config_health=clean"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
