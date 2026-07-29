#!/usr/bin/env python3
"""Regression coverage for the downstream BridgeForge version source of truth."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERSION_CHECKS = (
    ROOT / "templates" / "codex" / "hooks" / "version_check.py",
    ROOT / ".codex" / "hooks" / "version_check.py",
    ROOT / "templates" / "claude" / "hooks" / "version_check.py",
    ROOT / ".claude" / "hooks" / "version_check.py",
)
SHOW_STATES = (
    ROOT / "templates" / "codex" / "hooks" / "show_state.py",
    ROOT / ".codex" / "hooks" / "show_state.py",
    ROOT / "templates" / "claude" / "hooks" / "show_state.py",
    ROOT / ".claude" / "hooks" / "show_state.py",
)
SESSION_SNAPSHOTS = (
    ROOT / "templates" / "codex" / "hooks" / "session_snapshot.py",
    ROOT / ".codex" / "hooks" / "session_snapshot.py",
    ROOT / "templates" / "claude" / "hooks" / "session_snapshot.py",
    ROOT / ".claude" / "hooks" / "session_snapshot.py",
)


def run(command: list[str], cwd: Path, *, input_text: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


class DownstreamVersionSotTests(unittest.TestCase):
    def test_template_and_dogfood_hooks_are_mirrored(self) -> None:
        self.assertEqual(VERSION_CHECKS[0].read_bytes(), VERSION_CHECKS[1].read_bytes())
        self.assertEqual(VERSION_CHECKS[2].read_bytes(), VERSION_CHECKS[3].read_bytes())
        self.assertIn(
            "业务 manifest 不参与", SHOW_STATES[0].read_text(encoding="utf-8")
        )
        self.assertIn(
            "业务 manifest 不参与", SHOW_STATES[1].read_text(encoding="utf-8")
        )
        self.assertIn(
            "业务 manifest 不参与", SHOW_STATES[2].read_text(encoding="utf-8")
        )
        self.assertIn(
            "业务 manifest 不参与", SHOW_STATES[3].read_text(encoding="utf-8")
        )

    def test_show_state_ignores_native_manifest_versions(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            repo = Path(raw_temp)
            (repo / "VERSION").write_text("0.71.0\n", encoding="utf-8")
            (repo / "package.json").write_text('{"version": "9.9.9"}\n', encoding="utf-8")
            (repo / "pyproject.toml").write_text('version = "8.8.8"\n', encoding="utf-8")
            (repo / "Cargo.toml").write_text('version = "7.7.7"\n', encoding="utf-8")

            for index, script in enumerate(SHOW_STATES):
                spec = importlib.util.spec_from_file_location(f"show_state_{index}", script)
                self.assertIsNotNone(spec)
                self.assertIsNotNone(spec.loader)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.REPO_ROOT = repo
                self.assertEqual(module._version(), "0.71.0")

    def test_session_snapshot_ignores_native_manifest_versions(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            repo = Path(raw_temp)
            (repo / "VERSION").write_text("0.71.0\n", encoding="utf-8")
            (repo / "package.json").write_text('{"version": "9.9.9"}\n', encoding="utf-8")
            (repo / "pyproject.toml").write_text('version = "8.8.8"\n', encoding="utf-8")
            (repo / "Cargo.toml").write_text('version = "7.7.7"\n', encoding="utf-8")

            for index, script in enumerate(SESSION_SNAPSHOTS):
                spec = importlib.util.spec_from_file_location(
                    f"session_snapshot_{index}", script
                )
                self.assertIsNotNone(spec)
                self.assertIsNotNone(spec.loader)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.REPO_ROOT = repo
                self.assertEqual(module._version(), "0.71.0")

    def test_version_hook_requires_root_version_even_with_native_manifests(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")

        with tempfile.TemporaryDirectory() as raw_temp:
            repo = Path(raw_temp)
            hook_dir = repo / ".codex" / "hooks"
            hook_dir.mkdir(parents=True)
            hook = hook_dir / "version_check.py"
            shutil.copy2(VERSION_CHECKS[0], hook)
            (repo / "VERSION").write_text("0.71.0\n", encoding="utf-8")
            (repo / "package.json").write_text('{"version": "9.9.9"}\n', encoding="utf-8")
            (repo / "pyproject.toml").write_text('version = "8.8.8"\n', encoding="utf-8")
            (repo / "Cargo.toml").write_text('version = "7.7.7"\n', encoding="utf-8")
            (repo / "payload.txt").write_text("baseline\n", encoding="utf-8")

            for command in (
                ["git", "init"],
                ["git", "config", "user.email", "test@example.invalid"],
                ["git", "config", "user.name", "BridgeForge Test"],
                ["git", "add", "."],
                ["git", "commit", "-m", "baseline"],
            ):
                result = run(command, repo)
                self.assertEqual(result.returncode, 0, result.stderr)

            (repo / "payload.txt").write_text("changed\n", encoding="utf-8")
            (repo / "package.json").write_text('{"version": "10.0.0"}\n', encoding="utf-8")
            result = run(["git", "add", "payload.txt", "package.json"], repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            request = json.dumps({"tool_input": {"command": "git commit -m update"}})
            blocked = run([sys.executable, str(hook)], repo, input_text=request)
            self.assertEqual(blocked.returncode, 2, blocked.stderr)
            self.assertIn("`VERSION`", blocked.stderr)

            (repo / "VERSION").write_text("0.72.0\n", encoding="utf-8")
            result = run(["git", "add", "VERSION"], repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            allowed = run([sys.executable, str(hook)], repo, input_text=request)
            self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_init_reference_requires_upstream_root_version(self) -> None:
        reference = (ROOT / "skills" / "bridgeforge" / "references" / "init.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("$BRIDGEFORGE_HOME/VERSION", reference)
        self.assertIn("原生 manifest 的版本字段属于下游业务", reference)

    def test_downstream_fixture_copies_bridgeforge_root_version(self) -> None:
        script = ROOT / "tests" / "harness" / "run_downstream_fixture.py"
        spec = importlib.util.spec_from_file_location("downstream_fixture", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        fixture = module.build_codex_fixture()
        self.assertEqual(
            (fixture / "VERSION").read_text(encoding="utf-8"),
            (ROOT / "VERSION").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
