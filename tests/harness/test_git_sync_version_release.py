#!/usr/bin/env python3
"""Focused regression coverage for automatic git-sync version releases."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "templates" / "codex" / "scripts" / "version_release.py"
SPEC = importlib.util.spec_from_file_location("version_release_under_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
VERSION_RELEASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VERSION_RELEASE
SPEC.loader.exec_module(VERSION_RELEASE)


def git(repo: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode:
        raise AssertionError(result.stderr or result.stdout)


def init_repo(repo: Path) -> None:
    git(repo, "init")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "config", "user.name", "BridgeForge Fixture")


class VersionReleaseTests(unittest.TestCase):
    def test_bump_levels(self) -> None:
        cases = {
            "fix: 修复": "1.2.4",
            "docs: 说明": "1.2.4",
            "perf: 加速": "1.2.4",
            "feat: 新能力": "1.3.0",
            "feat!: 重做": "2.0.0",
            "fix: 修复\n\nBREAKING CHANGE: 接口变化": "2.0.0",
        }
        for message, expected in cases.items():
            with self.subTest(message=message):
                info = VERSION_RELEASE.parse_commit_message(message)
                self.assertEqual(VERSION_RELEASE.bump_semver("1.2.3", info.level), expected)

    def test_project_release_updates_root_package_and_lock(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            (repo / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (repo / "package.json").write_text(
                json.dumps({"name": "demo", "version": "1.2.3"}) + "\n",
                encoding="utf-8",
            )
            (repo / "package-lock.json").write_text(
                json.dumps(
                    {
                        "name": "demo",
                        "version": "1.2.3",
                        "lockfileVersion": 3,
                        "packages": {"": {"name": "demo", "version": "1.2.3"}},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (repo / "work.txt").write_text("baseline\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "baseline")
            (repo / "work.txt").write_text("changed\n", encoding="utf-8")

            plan = VERSION_RELEASE.build_release_plan(repo, "fix: 修复同步", {"work.txt"})
            self.assertIsNotNone(plan)
            VERSION_RELEASE.apply_release_plan(plan)
            self.assertEqual((repo / "VERSION").read_text().strip(), "1.2.4")
            self.assertEqual(json.loads((repo / "package.json").read_text())["version"], "1.2.4")
            lock = json.loads((repo / "package-lock.json").read_text())
            self.assertEqual(lock["version"], "1.2.4")
            self.assertEqual(lock["packages"][""]["version"], "1.2.4")
            self.assertIn("## [1.2.4]", (repo / "CHANGELOG.md").read_text())

    def test_missing_root_version_is_inferred_then_bumped(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            (repo / "pyproject.toml").write_text(
                '[project]\nname = "demo"\nversion = "2.4.0"\n', encoding="utf-8"
            )
            (repo / "note.md").write_text("changed\n", encoding="utf-8")
            plan = VERSION_RELEASE.build_release_plan(repo, "feat: 新增能力", {"note.md"})
            self.assertEqual(plan.old_version, "2.4.0")
            self.assertEqual(plan.new_version, "2.5.0")

    def test_rust_workspace_and_lock_follow_manual_root_bump(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            (repo / "VERSION").write_text("1.5.0\n", encoding="utf-8")
            (repo / "Cargo.toml").write_text(
                '[workspace]\nmembers = ["core", "app"]\n\n'
                '[workspace.package]\nversion = "1.4.3"\n',
                encoding="utf-8",
            )
            (repo / "Cargo.lock").write_text(
                'version = 4\n\n'
                '[[package]]\nname = "core"\nversion = "1.4.3"\n\n'
                '[[package]]\nname = "app"\nversion = "1.4.3"\n\n'
                '[[package]]\nname = "external"\nversion = "1.4.3"\n'
                'source = "registry+https://example.invalid/index"\n',
                encoding="utf-8",
            )
            plan = VERSION_RELEASE.build_release_plan(repo, "fix: 修复撮合", {"src/lib.rs"})
            self.assertEqual(plan.old_version, "1.5.0")
            self.assertEqual(plan.new_version, "1.5.1")
            VERSION_RELEASE.apply_release_plan(plan)
            cargo = (repo / "Cargo.toml").read_text(encoding="utf-8")
            lock = (repo / "Cargo.lock").read_text(encoding="utf-8")
            self.assertIn('version = "1.5.1"', cargo)
            self.assertEqual(lock.count('version = "1.5.1"'), 2)
            self.assertEqual(lock.count('version = "1.4.3"'), 1)

    def test_pure_bridgeforge_update_does_not_bump_project(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            host = repo / ".codex"
            (host / "hooks").mkdir(parents=True)
            (host / "managed-skeleton.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "stamp": ".codex/.bridgeforge_version",
                        "whole_files": [".codex/hooks/*.py", ".codex/.bridgeforge_version"],
                        "managed_regions": [],
                    }
                ),
                encoding="utf-8",
            )
            (host / "hooks" / "guard.py").write_text("old\n", encoding="utf-8")
            (host / ".bridgeforge_version").write_text("0.82.0\n", encoding="utf-8")
            (repo / "VERSION").write_text("3.0.0\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "baseline")
            (host / "hooks" / "guard.py").write_text("new\n", encoding="utf-8")
            (host / ".bridgeforge_version").write_text("0.83.0\n", encoding="utf-8")
            plan = VERSION_RELEASE.build_release_plan(
                repo,
                "chore: 更新骨架",
                {".codex/hooks/guard.py", ".codex/.bridgeforge_version"},
            )
            self.assertIsNone(plan)
            (repo / "work.txt").write_text("project change\n", encoding="utf-8")
            mixed = VERSION_RELEASE.build_release_plan(
                repo,
                "fix: 同时修改项目",
                {
                    ".codex/hooks/guard.py",
                    ".codex/.bridgeforge_version",
                    "work.txt",
                },
            )
            self.assertIsNotNone(mixed)
            self.assertEqual(mixed.classification, "mixed")

    def test_schema_v2_contract_drives_git_sync_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            host = repo / ".codex"
            (host / "hooks").mkdir(parents=True)
            (host / "managed-skeleton.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "stamp": ".codex/.bridgeforge_version",
                        "contract_target": ".codex/managed-skeleton.json",
                        "assets": [
                            {
                                "id": "hook.guard",
                                "target": ".codex/hooks/guard.py",
                                "strategy": "whole",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            guard = host / "hooks/guard.py"
            stamp = host / ".bridgeforge_version"
            guard.write_text("old\n", encoding="utf-8")
            stamp.write_text("0.90.0\n", encoding="utf-8")
            (repo / "VERSION").write_text("3.0.0\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "baseline")

            guard.write_text("new\n", encoding="utf-8")
            stamp.write_text("0.91.0\n", encoding="utf-8")
            plan = VERSION_RELEASE.build_release_plan(
                repo,
                "chore: 更新骨架",
                {".codex/hooks/guard.py", ".codex/.bridgeforge_version"},
            )
            self.assertIsNone(plan)

    def test_schema_v2_managed_blocks_preserve_project_owned_sections(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            host = repo / ".codex"
            memory = host / "memory" / "MEMORY.md"
            memory.parent.mkdir(parents=True)
            (host / "managed-skeleton.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "stamp": ".codex/.bridgeforge_version",
                        "contract_target": ".codex/managed-skeleton.json",
                        "assets": [
                            {
                                "id": "root.agents",
                                "target": "AGENTS.md",
                                "strategy": "whole",
                                "managed_blocks": {
                                    "format": "markdown-headings",
                                    "headings": ["## Managed"],
                                },
                            },
                            {
                                "id": "codex.memory.index",
                                "target": ".codex/memory/MEMORY.md",
                                "strategy": "seed",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            agents = repo / "AGENTS.md"
            stamp = host / ".bridgeforge_version"
            agents.write_text(
                "# Entry\n\n## Managed\n\nupstream\n\n## Project\n\nlocal old\n",
                encoding="utf-8",
            )
            memory.write_text("# generated index\n", encoding="utf-8")
            stamp.write_text("0.92.1\n", encoding="utf-8")
            (repo / "VERSION").write_text("3.0.0\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "baseline")

            agents.write_text(
                agents.read_text(encoding="utf-8").replace("local old", "local new"),
                encoding="utf-8",
            )
            plan = VERSION_RELEASE.build_release_plan(
                repo, "fix: 更新项目说明", {"AGENTS.md"}
            )
            self.assertEqual(plan.classification, "project")

            memory.write_text("# regenerated project index\n", encoding="utf-8")
            plan = VERSION_RELEASE.build_release_plan(
                repo,
                "fix: 更新项目索引",
                {"AGENTS.md", ".codex/memory/MEMORY.md"},
            )
            self.assertEqual(plan.classification, "project")

            agents.write_text(
                agents.read_text(encoding="utf-8").replace("upstream", "bypassed"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(VERSION_RELEASE.ReleaseError, "outside /bridgeforge"):
                VERSION_RELEASE.build_release_plan(
                    repo,
                    "fix: 禁止旁路修改受管区块",
                    {"AGENTS.md", ".codex/memory/MEMORY.md"},
                )

            stamp.write_text("0.92.2\n", encoding="utf-8")
            mixed = VERSION_RELEASE.build_release_plan(
                repo,
                "fix: 同步受管区块并保留项目定制",
                {
                    "AGENTS.md",
                    ".codex/memory/MEMORY.md",
                    ".codex/.bridgeforge_version",
                },
            )
            self.assertEqual(mixed.classification, "mixed")

    def test_schema_v2_keyed_table_distinguishes_managed_and_project_rows(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            host = repo / ".codex"
            host.mkdir(parents=True)
            (host / "managed-skeleton.json").write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "stamp": ".codex/.bridgeforge_version",
                        "contract_target": ".codex/managed-skeleton.json",
                        "assets": [
                            {
                                "id": "root.agents",
                                "target": "AGENTS.md",
                                "strategy": "whole",
                                "managed_blocks": {
                                    "format": "markdown-headings",
                                    "headings": [],
                                    "keyed_tables": [
                                        {
                                            "heading": "## Index",
                                            "key_column": 0,
                                            "managed_keys": ["rules/core.md"],
                                        }
                                    ],
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            agents = repo / "AGENTS.md"
            stamp = host / ".bridgeforge_version"
            baseline = (
                "# Entry\n\n## Index\n\n"
                "| Rule | Purpose |\n|---|---|\n"
                "| `rules/core.md` | upstream |\n"
                "| `rules/local.md` | local old |\n"
            )
            agents.write_text(baseline, encoding="utf-8")
            stamp.write_text("0.94.1\n", encoding="utf-8")
            (repo / "VERSION").write_text("3.0.0\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "baseline")

            agents.write_text(baseline.replace("local old", "local new"), encoding="utf-8")
            project_plan = VERSION_RELEASE.build_release_plan(
                repo, "fix: 更新项目索引", {"AGENTS.md"}
            )
            self.assertEqual(project_plan.classification, "project")

            agents.write_text(
                baseline.replace("local old", "local \\| new"),
                encoding="utf-8",
            )
            escaped_pipe_plan = VERSION_RELEASE.build_release_plan(
                repo, "fix: 更新带转义竖线的项目索引", {"AGENTS.md"}
            )
            self.assertEqual(escaped_pipe_plan.classification, "project")

            agents.write_text(
                baseline.replace("| `rules/local.md` | local old |", "| `rules/local.md` | local old"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(VERSION_RELEASE.ReleaseError, "ambiguous"):
                VERSION_RELEASE.build_release_plan(
                    repo, "fix: 拒绝损坏的项目索引", {"AGENTS.md"}
                )

            agents.write_text(
                baseline.replace("upstream", "bypassed").replace(
                    "local old", "local new"
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(VERSION_RELEASE.ReleaseError, "outside /bridgeforge"):
                VERSION_RELEASE.build_release_plan(
                    repo, "fix: 禁止旁路官方索引", {"AGENTS.md"}
                )

            stamp.write_text("0.94.2\n", encoding="utf-8")
            mixed = VERSION_RELEASE.build_release_plan(
                repo,
                "fix: BridgeForge 更新官方索引",
                {"AGENTS.md", ".codex/.bridgeforge_version"},
            )
            self.assertEqual(mixed.classification, "mixed")

    def test_managed_file_without_stamp_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            host = repo / ".codex"
            (host / "hooks").mkdir(parents=True)
            (host / "managed-skeleton.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "stamp": ".codex/.bridgeforge_version",
                        "whole_files": [".codex/hooks/*.py", ".codex/.bridgeforge_version"],
                        "managed_regions": [],
                    }
                ),
                encoding="utf-8",
            )
            (host / "hooks" / "guard.py").write_text("old\n", encoding="utf-8")
            (host / ".bridgeforge_version").write_text("0.82.0\n", encoding="utf-8")
            (repo / "VERSION").write_text("1.0.0\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "baseline")
            (host / "hooks" / "guard.py").write_text("unauthorized\n", encoding="utf-8")
            with self.assertRaisesRegex(VERSION_RELEASE.ReleaseError, "outside /bridgeforge"):
                VERSION_RELEASE.build_release_plan(
                    repo, "fix: 不允许", {".codex/hooks/guard.py"}
                )

    def test_project_rules_do_not_require_skeleton_stamp(self) -> None:
        for host_name in (".codex", ".claude"):
            with self.subTest(host=host_name), tempfile.TemporaryDirectory() as raw:
                repo = Path(raw)
                init_repo(repo)
                host = repo / host_name
                (host / "rules").mkdir(parents=True)
                stamp = f"{host_name}/.bridgeforge_version"
                (host / "managed-skeleton.json").write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "stamp": stamp,
                            "whole_files": [stamp, f"{host_name}/hooks/*.py"],
                            "managed_regions": [],
                        }
                    ),
                    encoding="utf-8",
                )
                for name in ("app_layer.md", "database.md", "modules.md", "time.md"):
                    (host / "rules" / name).write_text("old\n", encoding="utf-8")
                (host / ".bridgeforge_version").write_text("0.84.0\n", encoding="utf-8")
                (repo / "VERSION").write_text("1.0.0\n", encoding="utf-8")
                git(repo, "add", ".")
                git(repo, "commit", "-m", "baseline")
                changed = set()
                for name in ("app_layer.md", "database.md", "modules.md", "time.md"):
                    (host / "rules" / name).write_text("project update\n", encoding="utf-8")
                    changed.add(f"{host_name}/rules/{name}")
                plan = VERSION_RELEASE.build_release_plan(repo, "fix: 更新项目规则", changed)
                self.assertEqual(plan.classification, "project")

    def test_managed_region_tracks_inside_and_outside_changes_independently(self) -> None:
        begin = "# >>> BRIDGEFORGE_MANAGED_BEGIN"
        end = "# <<< BRIDGEFORGE_MANAGED_END"
        baseline = f"project old\n{begin}\nmanaged old\n{end}\nproject tail\n"

        def prepare(repo: Path) -> tuple[Path, Path]:
            init_repo(repo)
            host = repo / ".codex"
            hook = repo / ".githooks" / "pre-commit"
            hook.parent.mkdir(parents=True)
            host.mkdir(parents=True)
            (host / "managed-skeleton.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "stamp": ".codex/.bridgeforge_version",
                        "whole_files": [".codex/.bridgeforge_version"],
                        "managed_regions": [
                            {"path": ".githooks/pre-commit", "begin": begin, "end": end}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (host / ".bridgeforge_version").write_text("0.84.0\n", encoding="utf-8")
            (repo / "VERSION").write_text("1.0.0\n", encoding="utf-8")
            hook.write_text(baseline, encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "baseline")
            return host, hook

        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            _host, hook = prepare(repo)
            hook.write_text(baseline.replace("project old", "project new"), encoding="utf-8")
            plan = VERSION_RELEASE.build_release_plan(
                repo, "fix: 更新项目 hook", {".githooks/pre-commit"}
            )
            self.assertEqual(plan.classification, "project")

        for change in ("managed only", "managed and project"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as raw:
                repo = Path(raw)
                _host, hook = prepare(repo)
                updated = baseline.replace("managed old", "managed new")
                if change == "managed and project":
                    updated = updated.replace("project old", "project new")
                hook.write_text(updated, encoding="utf-8")
                with self.assertRaisesRegex(VERSION_RELEASE.ReleaseError, "outside /bridgeforge"):
                    VERSION_RELEASE.build_release_plan(
                        repo, "fix: 不允许受管旁路", {".githooks/pre-commit"}
                    )

        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            host, hook = prepare(repo)
            hook.write_text(
                baseline.replace("managed old", "managed new").replace(
                    "project old", "project new"
                ),
                encoding="utf-8",
            )
            (host / ".bridgeforge_version").write_text("0.84.1\n", encoding="utf-8")
            plan = VERSION_RELEASE.build_release_plan(
                repo,
                "fix: 同步更新骨架与项目 hook",
                {".githooks/pre-commit", ".codex/.bridgeforge_version"},
            )
            self.assertEqual(plan.classification, "mixed")


if __name__ == "__main__":
    unittest.main()
