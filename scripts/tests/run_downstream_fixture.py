#!/usr/bin/env python3
"""Executable current-only downstream regression fixture for bridgeforge-codex."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CURRENT_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BASELINE = load(
    "bridgeforge_current_downstream_baseline",
    ROOT / "templates" / "scripts" / "current_baseline.py",
)


def project_python(project: Path) -> Path:
    venv.EnvBuilder(with_pip=False).create(project / ".venv")
    python = project / ".venv" / "Scripts" / "python.exe"
    if not python.is_file():
        python = project / ".venv" / "bin" / "python"
    if not python.is_file():
        raise RuntimeError("fixture project venv has no interpreter")
    return python


def cli(
    python: Path,
    project: Path,
    mode: str,
    *,
    apply_fingerprint: str | None = None,
    preserve: tuple[str, ...] = (),
    delete: tuple[str, ...] = (),
    allow_blocked: bool = False,
) -> dict[str, object]:
    command = [
        str(python),
        "-B",
        str(ROOT / "scripts" / "bridgeforge_codex_project_sync.py"),
        "--project-root",
        str(project),
        "--template-root",
        str(ROOT),
        "--mode",
        mode,
    ]
    if apply_fingerprint is not None:
        command.extend(["--apply", "--plan-fingerprint", apply_fingerprint])
        if preserve or delete:
            command.extend([
                "--confirmed-preservation-manifest",
                "--confirmed-risk",
            ])
            for item in preserve:
                command.extend(["--preserve-project-asset", item])
            for item in delete:
                command.extend(["--delete-project-asset", item])
    result = subprocess.run(
        command,
        cwd=project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        if allow_blocked and result.stdout:
            payload = json.loads(result.stdout)
            if payload.get("status") == "blocked":
                return payload
        raise RuntimeError(result.stderr or result.stdout)
    return json.loads(result.stdout)


def init_check(base: Path) -> dict[str, object]:
    project = base / "init"
    project.mkdir()
    python = project_python(project)
    plan = cli(python, project, "init")
    receipt = cli(
        python,
        project,
        "init",
        apply_fingerprint=str(plan["aggregate_fingerprint"]),
    )
    report = BASELINE.verify_current_baseline(project)
    repeated = cli(python, project, "update")
    return {
        "name": "current-init-idempotent",
        "ok": (
            receipt["stamp_written_last"]
            and report.version == CURRENT_VERSION
            and not repeated["blockers"]
            and not repeated["safe"]
            and not repeated["risk"]
        ),
    }


def rebuild_check(base: Path) -> dict[str, object]:
    project = base / "rebuild"
    hook = project / ".codex" / "hooks" / "project_only"
    scattered = project / ".codex" / "hooks" / "legacy_hook.py"
    skill = project / ".codex" / "skills" / "project" / "SKILL.md"
    scattered.parent.mkdir(parents=True)
    skill.parent.mkdir(parents=True)
    python = project_python(project)
    (project / ".codex" / ".bridgeforge_version").write_text(
        "1.4.30\n",
        encoding="utf-8",
    )
    project_maps = {
        project / ".codex" / "find-doc.map.md": b"# find-doc project map\n",
        project / ".codex" / "sync-docs.map.md": b"# sync-docs project map\n",
    }
    for path, payload in project_maps.items():
        path.write_bytes(payload)
    scattered.write_text("print('legacy')\n", encoding="utf-8")
    hooks_json = project / ".codex" / "hooks.json"
    hooks_json.write_text(
        json.dumps({
            "hooks": {
                "SessionStart": [{
                    "hooks": [{
                        "type": "command",
                        "command": (
                            ".venv/Scripts/python.exe "
                            ".codex/hooks/legacy_hook.py"
                        ),
                    }],
                }],
            },
        }),
        encoding="utf-8",
    )
    skill.write_text(
        "---\nname: project\ndescription: project skill\n---\n\n# Project\n",
        encoding="utf-8",
    )
    blocked = cli(python, project, "auto", allow_blocked=True)

    scattered.unlink()
    hook.mkdir()
    (hook / "entrypoint.py").write_text("print('project')\n", encoding="utf-8")
    (hook / "config.json").write_text('{"project": true}\n', encoding="utf-8")
    hooks_json.write_text(
        json.dumps({
            "hooks": {
                "SessionStart": [{
                    "hooks": [{
                        "type": "command",
                        "command": (
                            ".venv/Scripts/python.exe "
                            ".codex/hooks/project_only/entrypoint.py"
                        ),
                    }],
                }],
            },
        }),
        encoding="utf-8",
    )
    skill_before = skill.read_bytes()
    plan = cli(python, project, "auto")
    required_map_targets = {
        str(item["target"])
        for item in plan["preservation_manifest"]
        if item.get("kind") == "project-map"
        and item.get("disposition") == "required-preserve"
    }
    hook_id = next(
        item["id"]
        for item in plan["preservation_manifest"]
        if item.get("target") == ".codex/hooks/project_only"
    )
    delete = tuple(
        str(item["id"])
        for item in plan["preservation_manifest"]
        if item.get("disposition") == "user-decision"
        and item["id"] != hook_id
    )
    receipt = cli(
        python,
        project,
        "auto",
        apply_fingerprint=str(plan["aggregate_fingerprint"]),
        preserve=(str(hook_id),),
        delete=delete,
    )
    BASELINE.verify_current_baseline(project)
    repeated = cli(python, project, "update")
    return {
        "name": "old-project-confirmed-rebuild",
        "ok": (
            bool(blocked["blockers"])
            and "must be normalized first" in " ".join(blocked["blockers"])
            and plan["mode"] == "rebuild"
            and receipt["mode"] == "rebuild"
            and (hook / "entrypoint.py").is_file()
            and (hook / "config.json").is_file()
            and skill.read_bytes() == skill_before
            and required_map_targets == {
                ".codex/find-doc.map.md",
                ".codex/sync-docs.map.md",
            }
            and all(
                path.read_bytes() == payload
                for path, payload in project_maps.items()
            )
            and not (project / ".codex" / ".bridgeforge_version").exists()
            and not repeated["blockers"]
            and not repeated["safe"]
            and not repeated["risk"]
        ),
    }


def drift_check(base: Path) -> dict[str, object]:
    project = base / "drift"
    project.mkdir()
    python = project_python(project)
    plan = cli(python, project, "init")
    cli(
        python,
        project,
        "init",
        apply_fingerprint=str(plan["aggregate_fingerprint"]),
    )
    target = project / ".codex" / "hooks" / "requirements_check.py"
    target.write_text("# drift\n", encoding="utf-8")
    before = target.read_bytes()
    result = subprocess.run(
        [
            str(python),
            "-B",
            str(ROOT / "scripts" / "bridgeforge_codex_project_sync.py"),
            "--project-root",
            str(project),
            "--template-root",
            str(ROOT),
            "--mode",
            "update",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    blocked = json.loads(result.stdout)
    return {
        "name": "current-drift-zero-write-block",
        "ok": (
            result.returncode == 2
            and bool(blocked["blockers"])
            and target.read_bytes() == before
        ),
    }


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        checks = [
            init_check(base),
            rebuild_check(base),
            drift_check(base),
        ]
    status = "passed" if all(bool(item["ok"]) for item in checks) else "failed"
    print(json.dumps({"status": status, "checks": checks}, ensure_ascii=False, indent=2))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
