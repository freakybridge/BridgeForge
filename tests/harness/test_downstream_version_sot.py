#!/usr/bin/env python3
"""Regression coverage for the downstream BridgeForge version source of truth."""
from __future__ import annotations

import importlib.util
import json
import re
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
SETTINGS = (
    ROOT / "templates" / "codex" / "settings.json",
    ROOT / ".codex" / "settings.json",
    ROOT / "templates" / "claude" / "settings.json",
    ROOT / ".claude" / "settings.json",
)
FACTORY_VERSION_CHECK = ROOT / ".codex" / "scripts" / "factory_version_check.py"
GIT_SYNC_RUNNERS = (
    ROOT / ".codex" / "scripts" / "codex_git_sync.py",
    ROOT / "templates" / "codex" / "scripts" / "codex_git_sync.py",
    ROOT / ".claude" / "scripts" / "codex_git_sync.py",
    ROOT / "templates" / "claude" / "scripts" / "codex_git_sync.py",
)
VERSION_RELEASES = (
    ROOT / ".codex" / "scripts" / "version_release.py",
    ROOT / "templates" / "codex" / "scripts" / "version_release.py",
    ROOT / ".claude" / "scripts" / "version_release.py",
    ROOT / "templates" / "claude" / "scripts" / "version_release.py",
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
    def test_factory_has_one_version_and_one_changelog(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8-sig").strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8-sig")
        self.assertRegex(changelog, rf"(?m)^## \[{re.escape(version)}\](?:\s|$)")
        for host in ("codex", "claude"):
            self.assertFalse((ROOT / "templates" / host / "VERSION").exists())
            self.assertFalse((ROOT / "templates" / host / "CHANGELOG.md").exists())

    def test_template_and_dogfood_hooks_are_mirrored(self) -> None:
        self.assertEqual(VERSION_CHECKS[0].read_bytes(), VERSION_CHECKS[1].read_bytes())
        self.assertEqual(VERSION_CHECKS[2].read_bytes(), VERSION_CHECKS[3].read_bytes())
        for script in VERSION_CHECKS:
            self.assertIn("Compatibility shim", script.read_text(encoding="utf-8"))
        for settings in SETTINGS:
            self.assertNotIn("version_check.py", settings.read_text(encoding="utf-8"))
        for script in SHOW_STATES:
            self.assertIn(".bridgeforge_version", script.read_text(encoding="utf-8"))

    def test_show_state_ignores_native_manifest_versions(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            repo = Path(raw_temp)
            (repo / "VERSION").write_text("9.9.9\n", encoding="utf-8")
            (repo / "package.json").write_text('{"version": "9.9.9"}\n', encoding="utf-8")
            (repo / "pyproject.toml").write_text('version = "8.8.8"\n', encoding="utf-8")
            (repo / "Cargo.toml").write_text('version = "7.7.7"\n', encoding="utf-8")

            for index, script in enumerate(SHOW_STATES):
                spec = importlib.util.spec_from_file_location(f"show_state_{index}", script)
                self.assertIsNotNone(spec)
                self.assertIsNotNone(spec.loader)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                host = ".codex" if index < 2 else ".claude"
                module.HOST_DIR = repo / host
                module.HOST_DIR.mkdir(exist_ok=True)
                (module.HOST_DIR / ".bridgeforge_version").write_text(
                    "0.71.0\n", encoding="utf-8"
                )
                self.assertEqual(module._version(), "0.71.0")

    def test_session_snapshot_ignores_native_manifest_versions(self) -> None:
        with tempfile.TemporaryDirectory() as raw_temp:
            repo = Path(raw_temp)
            (repo / "VERSION").write_text("9.9.9\n", encoding="utf-8")
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
                host = ".codex" if index < 2 else ".claude"
                module.HOST_DIR = repo / host
                module.HOST_DIR.mkdir(exist_ok=True)
                (module.HOST_DIR / ".bridgeforge_version").write_text(
                    "0.71.0\n", encoding="utf-8"
                )
                self.assertEqual(module._version(), "0.71.0")

    def test_legacy_version_hook_is_a_noop(self) -> None:
        request = '{"tool_input": {"command": "git commit -m update"}}'
        for hook in VERSION_CHECKS:
            allowed = run([sys.executable, str(hook)], ROOT, input_text=request)
            self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_factory_version_check_requires_version_for_product_changes(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("git is required")

        with tempfile.TemporaryDirectory() as raw_temp:
            repo = Path(raw_temp)
            (repo / "VERSION").write_text("0.71.0\n", encoding="utf-8")
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
            result = run(["git", "add", "payload.txt"], repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            allowed = run([sys.executable, str(FACTORY_VERSION_CHECK)], repo)
            self.assertEqual(allowed.returncode, 0, allowed.stderr)

            (repo / "templates" / "codex").mkdir(parents=True)
            (repo / "templates" / "codex" / "AGENTS.md").write_text("changed\n", encoding="utf-8")
            allowed = run([sys.executable, str(FACTORY_VERSION_CHECK)], repo)
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            blocked = run(
                [sys.executable, str(FACTORY_VERSION_CHECK), "--worktree"],
                repo,
            )
            self.assertEqual(blocked.returncode, 2, blocked.stderr)

            result = run(["git", "add", "templates/codex/AGENTS.md"], repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            blocked = run([sys.executable, str(FACTORY_VERSION_CHECK)], repo)
            self.assertEqual(blocked.returncode, 2, blocked.stderr)
            self.assertIn("根 VERSION", blocked.stderr)

            (repo / "VERSION").write_text("0.72.0\n", encoding="utf-8")
            blocked = run([sys.executable, str(FACTORY_VERSION_CHECK)], repo)
            self.assertEqual(blocked.returncode, 2, blocked.stderr)
            allowed = run(
                [sys.executable, str(FACTORY_VERSION_CHECK), "--worktree"],
                repo,
            )
            self.assertEqual(allowed.returncode, 0, allowed.stderr)

            result = run(["git", "add", "VERSION"], repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            allowed = run([sys.executable, str(FACTORY_VERSION_CHECK)], repo)
            self.assertEqual(allowed.returncode, 0, allowed.stderr)

            result = run(["git", "commit", "-m", "product baseline"], repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            (repo / "templates" / "codex" / "AGENTS.md").write_text(
                "unstaged product change\n",
                encoding="utf-8",
            )
            allowed = run([sys.executable, str(FACTORY_VERSION_CHECK)], repo)
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            blocked = run(
                [sys.executable, str(FACTORY_VERSION_CHECK), "--worktree"],
                repo,
            )
            self.assertEqual(blocked.returncode, 2, blocked.stderr)

    def test_git_sync_runner_mirror_has_no_active_memory_rebuild(self) -> None:
        canonical = GIT_SYNC_RUNNERS[1].read_bytes()
        for runner in GIT_SYNC_RUNNERS:
            self.assertEqual(runner.read_bytes(), canonical)
            self.assertNotIn("memory_rebuild_index", runner.read_text(encoding="utf-8"))
        release = VERSION_RELEASES[1].read_bytes()
        for implementation in VERSION_RELEASES:
            self.assertEqual(implementation.read_bytes(), release)

    def test_git_sync_routes_directly_through_main(self) -> None:
        routing_files = (
            ROOT / ".codex" / "skill-routing.json",
            ROOT / "templates" / "codex" / "skill-routing.json",
        )
        for routing_file in routing_files:
            with self.subTest(routing=routing_file):
                routing = json.loads(routing_file.read_text(encoding="utf-8"))
                route = next(
                    entry for entry in routing["skills"] if entry["skill"] == "git-sync"
                )
                self.assertEqual(route["stage"], "all")
                self.assertEqual(route["agent"], "main")
                self.assertEqual(route["mode"], "main")

        skill = (ROOT / "skills" / "git-sync" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("mechanical-sync-worker", skill)
        self.assertIn("必须直接且只运行", skill)
        self.assertNotIn("### 3. 标准路径", skill)
        self.assertNotIn("git fetch origin", skill)
        self.assertIn("根据真实 diff 固化 1-3 条", skill)
        self.assertIn("代码变动效果", skill)
        self.assertIn("禁止只罗列文件名", skill)
        self.assertIn("本轮没有代码变动，仅确认本地与远端已同步", skill)
        self.assertIn("因提交后 diff 已清空而省略", skill)

    def test_confirm_and_develop_enforce_scale_and_budget(self) -> None:
        confirm = (ROOT / "skills" / "confirm" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        develop = (ROOT / "skills" / "develop" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("### 0. 规模与预算硬闸", confirm)
        self.assertIn("20 分钟 / 8k 新增 token", confirm)
        self.assertIn("45 分钟 / 20k 新增 token", confirm)
        self.assertIn("禁止伪报精确 token 消耗", confirm)
        self.assertIn("**S 级直接路径**", develop)
        self.assertIn("0 个子 agent", develop)
        self.assertIn("禁止 S/M 任务默认启动完整三段 agent 流程", develop)

        routing_files = (
            ROOT / ".codex" / "skill-routing.json",
            ROOT / "templates" / "codex" / "skill-routing.json",
        )
        for routing_file in routing_files:
            with self.subTest(routing=routing_file):
                routing = json.loads(routing_file.read_text(encoding="utf-8"))
                routes = [
                    entry for entry in routing["skills"] if entry["skill"] == "develop"
                ]
                size_gate = next(
                    entry
                    for entry in routes
                    if entry["stage"] == "size-gate-and-lean-delivery"
                )
                self.assertEqual(size_gate["agent"], "main")
                self.assertEqual(size_gate["mode"], "main")
                delegated = [entry for entry in routes if entry["agent"] != "main"]
                self.assertTrue(delegated)
                self.assertTrue(
                    all("L only" in entry["root_must_do"] for entry in delegated)
                )

    def test_init_reference_keeps_business_version_outside_bridgeforge(self) -> None:
        reference = (ROOT / "skills" / "bridgeforge" / "references" / "init.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("根 `VERSION` 是下游业务版本唯一事实源", reference)
        self.assertIn("$PROJECT_AGENT_DIR/.bridgeforge_version", reference)
        self.assertIn("首次执行 `$git-sync`", reference)

    def test_downstream_fixture_separates_business_and_skeleton_versions(self) -> None:
        script = ROOT / "tests" / "harness" / "run_downstream_fixture.py"
        spec = importlib.util.spec_from_file_location("downstream_fixture", script)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        fixture = module.build_codex_fixture()
        self.assertNotEqual(
            (fixture / "VERSION").read_text(encoding="utf-8"),
            (ROOT / "VERSION").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            (fixture / ".codex" / ".bridgeforge_version").read_text(encoding="utf-8"),
            (ROOT / "VERSION").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
