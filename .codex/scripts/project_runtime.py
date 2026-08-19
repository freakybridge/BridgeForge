#!/usr/bin/env python3
"""Validate and bootstrap the single project-local Python runtime contract."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MIN_PYTHON = (3, 11)
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class ProjectRuntimeError(RuntimeError):
    """The project-local Python runtime contract cannot be proven."""


@dataclass(frozen=True)
class ProjectRuntime:
    """A proven CPython runtime owned by one project ``.venv``."""

    project_root: Path
    python_executable: Path
    version: tuple[int, int, int]
    implementation: str = "CPython"

    def receipt(self, *, action: str, status: str) -> dict[str, Any]:
        return {
            "action": action,
            "implementation": self.implementation,
            "minimum_python": f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
            "project_root": str(self.project_root),
            "python_executable": str(self.python_executable),
            "status": status,
            "version": ".".join(str(item) for item in self.version),
        }


def _project_root(project_root: str | os.PathLike[str]) -> Path:
    raw = Path(project_root).expanduser()
    try:
        resolved = raw.resolve(strict=True)
    except OSError as exc:
        raise ProjectRuntimeError(f"project root is unavailable: {raw}") from exc
    if not resolved.is_dir():
        raise ProjectRuntimeError(f"project root is not a directory: {resolved}")
    return resolved


def _is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return path.is_symlink() or bool(
        getattr(info, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT
    )


def _inside(root: Path, candidate: Path, label: str) -> Path:
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise ProjectRuntimeError(
            f"{label} escapes or is unavailable under project root: {candidate}"
        ) from exc
    return resolved


def _venv_root(project_root: Path) -> Path:
    return project_root / ".venv"


def expected_project_python(
    project_root: str | os.PathLike[str],
) -> Path:
    """Return the only permitted Python path for ``project_root``."""

    root = _project_root(project_root)
    relative = (
        Path(".venv") / "Scripts" / "python.exe"
        if os.name == "nt"
        else Path(".venv") / "bin" / "python"
    )
    expected = root / relative
    try:
        expected.relative_to(root)
    except ValueError as exc:  # defensive: ``relative`` must stay lexical
        raise ProjectRuntimeError(
            f"project Python path escapes project root: {expected}"
        ) from exc
    return expected


def _resolve_command(executable: str | os.PathLike[str]) -> Path:
    raw = os.fspath(executable)
    candidate = Path(raw).expanduser()
    if candidate.parent == Path(".") and not candidate.is_file():
        found = shutil.which(raw)
        if found is None:
            raise ProjectRuntimeError(f"Python executable is unavailable: {raw}")
        candidate = Path(found)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ProjectRuntimeError(f"Python executable is unavailable: {candidate}") from exc
    if not resolved.is_file():
        raise ProjectRuntimeError(f"Python executable is not a file: {resolved}")
    return resolved


def _probe_python(executable: Path) -> dict[str, Any]:
    probe = (
        "import json,platform,sys;"
        "print(json.dumps({'implementation':platform.python_implementation(),"
        "'version':list(sys.version_info[:3]),'executable':sys.executable,"
        "'prefix':sys.prefix},separators=(',',':')))"
    )
    try:
        completed = subprocess.run(
            [str(executable), "-I", "-c", probe],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProjectRuntimeError(
            f"Python runtime probe failed: {executable} ({type(exc).__name__})"
        ) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise ProjectRuntimeError(
            f"Python runtime probe exited {completed.returncode}: {detail[:240]}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ProjectRuntimeError("Python runtime probe returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ProjectRuntimeError("Python runtime probe returned a non-object receipt")
    return payload


def _probe_identity(payload: dict[str, Any]) -> tuple[str, tuple[int, int, int]]:
    implementation = payload.get("implementation")
    raw_version = payload.get("version")
    if implementation != "CPython":
        raise ProjectRuntimeError(
            f"project runtime must be CPython, observed {implementation!r}"
        )
    if (
        not isinstance(raw_version, list)
        or len(raw_version) != 3
        or any(not isinstance(item, int) for item in raw_version)
    ):
        raise ProjectRuntimeError("Python runtime probe returned an invalid version")
    version = tuple(raw_version)
    if version[:2] < MIN_PYTHON:
        raise ProjectRuntimeError(
            "project runtime requires CPython "
            f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}+, observed "
            + ".".join(str(item) for item in version)
        )
    return implementation, version  # type: ignore[return-value]


def validate_project_runtime(
    project_root: str | os.PathLike[str],
    executable: str | os.PathLike[str] = sys.executable,
) -> ProjectRuntime:
    """Prove ``executable`` is the healthy CPython in this project's ``.venv``."""

    root = _project_root(project_root)
    venv = _venv_root(root)
    if not os.path.lexists(venv):
        raise ProjectRuntimeError(f"project .venv is missing: {venv}")
    if not venv.is_dir() or _is_reparse(venv):
        raise ProjectRuntimeError(f"project .venv is not a plain directory: {venv}")

    expected = expected_project_python(root)
    if not expected.is_file() or _is_reparse(expected):
        raise ProjectRuntimeError(
            f"project .venv Python is missing or unsafe: {expected}"
        )
    resolved_expected = _inside(root, expected, "project .venv Python")
    requested = _resolve_command(executable)
    if os.path.normcase(str(requested)) != os.path.normcase(str(resolved_expected)):
        raise ProjectRuntimeError(
            "current Python is not the target project .venv: "
            f"expected {resolved_expected}, observed {requested}"
        )

    payload = _probe_python(resolved_expected)
    implementation, version = _probe_identity(payload)
    reported_executable = _resolve_command(str(payload.get("executable", "")))
    if os.path.normcase(str(reported_executable)) != os.path.normcase(
        str(resolved_expected)
    ):
        raise ProjectRuntimeError(
            "project runtime reported a different executable: "
            f"expected {resolved_expected}, observed {reported_executable}"
        )
    try:
        reported_prefix = Path(str(payload.get("prefix", ""))).resolve(strict=True)
        expected_prefix = venv.resolve(strict=True)
    except OSError as exc:
        raise ProjectRuntimeError("project runtime prefix is unavailable") from exc
    if os.path.normcase(str(reported_prefix)) != os.path.normcase(str(expected_prefix)):
        raise ProjectRuntimeError(
            "project runtime prefix is not the target project .venv: "
            f"expected {expected_prefix}, observed {reported_prefix}"
        )
    return ProjectRuntime(root, resolved_expected, version, implementation)


def _cleanup_created_venv(project_root: Path, venv: Path) -> None:
    if not os.path.lexists(venv):
        return
    if _is_reparse(venv):
        raise ProjectRuntimeError(
            f"refusing to clean an unexpected reparse point after bootstrap failure: {venv}"
        )
    try:
        resolved = venv.resolve(strict=True)
        resolved.relative_to(project_root)
    except (OSError, ValueError) as exc:
        raise ProjectRuntimeError(
            f"refusing to clean escaped .venv after bootstrap failure: {venv}"
        ) from exc
    shutil.rmtree(venv)


def bootstrap_project_venv(
    project_root: str | os.PathLike[str],
    mode: str,
    bootstrap_executable: str | os.PathLike[str] = sys.executable,
) -> ProjectRuntime:
    """Create a missing project ``.venv`` through the one init/adopt exception."""

    root = _project_root(project_root)
    if mode not in {"init", "adopt"}:
        raise ProjectRuntimeError(
            "project .venv bootstrap is allowed only for init or adopt mode"
        )
    venv = _venv_root(root)
    if os.path.lexists(venv):
        raise ProjectRuntimeError(
            f"project .venv already exists; validate or repair it explicitly: {venv}"
        )

    bootstrap_python = _resolve_command(bootstrap_executable)
    _probe_identity(_probe_python(bootstrap_python))
    try:
        venv.mkdir()
    except FileExistsError as exc:
        raise ProjectRuntimeError(
            f"project .venv appeared during bootstrap; zero product writes performed: {venv}"
        ) from exc
    except OSError as exc:
        raise ProjectRuntimeError(f"project .venv cannot be created: {venv}") from exc
    try:
        created = subprocess.run(
            [str(bootstrap_python), "-m", "venv", str(venv)],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
        )
        if created.returncode != 0:
            detail = (created.stderr or created.stdout).strip()
            raise ProjectRuntimeError(
                f"project .venv bootstrap exited {created.returncode}: {detail[:240]}"
            )
        return validate_project_runtime(
            root,
            executable=expected_project_python(root),
        )
    except Exception as exc:
        try:
            _cleanup_created_venv(root, venv)
        except Exception as cleanup_exc:
            raise ProjectRuntimeError(
                f"project .venv bootstrap failed and cleanup was not proven: {cleanup_exc}"
            ) from exc
        if isinstance(exc, ProjectRuntimeError):
            raise
        raise ProjectRuntimeError(
            f"project .venv bootstrap failed: {type(exc).__name__}: {exc}"
        ) from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--project-root", required=True, type=Path)
    validate.add_argument("--executable", type=Path, default=Path(sys.executable))
    bootstrap = commands.add_parser("bootstrap")
    bootstrap.add_argument("--project-root", required=True, type=Path)
    bootstrap.add_argument("--mode", required=True, choices=("init", "adopt", "update"))
    bootstrap.add_argument(
        "--bootstrap-executable",
        type=Path,
        default=Path(sys.executable),
    )
    return parser


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.action == "validate":
            runtime = validate_project_runtime(
                args.project_root,
                executable=args.executable,
            )
            _emit(runtime.receipt(action="validate", status="valid"))
            return 0
        runtime = bootstrap_project_venv(
            args.project_root,
            args.mode,
            bootstrap_executable=args.bootstrap_executable,
        )
        _emit(runtime.receipt(action="bootstrap", status="created"))
        return 0
    except ProjectRuntimeError as exc:
        _emit(
            {
                "action": args.action,
                "error": str(exc),
                "project_root": str(args.project_root),
                "status": "blocked",
            }
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
