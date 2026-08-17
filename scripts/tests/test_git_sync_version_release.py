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
MODULE_PATH = ROOT / "templates" / "scripts" / "version_release.py"
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


def write_contract_transition_fixture(
    repo: Path,
    *,
    customize_old_agents: bool = False,
    include_renamed_asset: bool = False,
    include_stale_same_target_asset: bool = False,
    include_merge_noop_asset: bool = False,
    drift_merge_target_before_baseline: bool = False,
    omit_merge_handler_before_baseline: bool = False,
    duplicate_merge_handler_before_baseline: bool = False,
) -> set[str]:
    host = repo / ".codex"
    host.mkdir(parents=True)
    old_agents = (
        "# Project\n\n## Project\n\nproject defaults\n\n"
        "## Managed\n\nold public\n"
    )
    old_asset = {
        "id": "root.agents",
        "target": "AGENTS.md",
        "strategy": "whole",
        "current_sha256": VERSION_RELEASE._sha256_bytes(old_agents.encode("utf-8")),
    }
    old_assets = [old_asset]
    if include_renamed_asset:
        old_assets.append({
            "id": "codex.renamed",
            "target": ".codex/old.py",
            "strategy": "whole",
            "current_sha256": VERSION_RELEASE._sha256_bytes(b"old managed\n"),
        })
    if include_stale_same_target_asset:
        old_assets.append({
            "id": "codex.stale",
            "target": ".codex/stale.py",
            "strategy": "whole",
            "current_sha256": VERSION_RELEASE._sha256_bytes(b"old managed\n"),
        })
    merge_handler = {
        "type": "command",
        "commandWindows": (
            "python .codex/hooks/hook_dispatcher.py pre-tool"
        ),
        "comment": "current managed dispatcher",
    }
    target_merge_handler = dict(merge_handler)
    if drift_merge_target_before_baseline:
        target_merge_handler["comment"] = "drifted managed dispatcher"
    target_handlers = [] if omit_merge_handler_before_baseline else [target_merge_handler]
    if duplicate_merge_handler_before_baseline:
        target_handlers.append(dict(target_merge_handler))
    target_handlers.append(
        {"type": "command", "commandWindows": "python project_hook.py"}
    )
    merge_target = {
        "description": "project-owned description",
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash|Edit|Write",
                    "hooks": target_handlers,
                }
            ]
        },
    }
    if include_merge_noop_asset:
        old_assets.append({
            "id": "codex.hooks-config",
            "target": ".codex/hooks.json",
            "strategy": "merge",
            "current_sha256": VERSION_RELEASE._sha256_bytes(b"old canonical source\n"),
            "merge_policy": "codex-hooks",
        })
    old_contract = {
        "schema_version": 2,
        "stamp": ".codex/.bridgeforge_version",
        "contract_target": ".codex/managed-skeleton.json",
        "assets": old_assets,
    }
    old_payload = (json.dumps(old_contract, indent=2) + "\n").encode("utf-8")
    (host / "managed-skeleton.json").write_bytes(old_payload)
    actual_old_agents = old_agents.replace(
        "project defaults",
        "PROJECT CUSTOM SEMANTICS" if customize_old_agents else "project defaults",
    )
    (repo / "AGENTS.md").write_text(actual_old_agents, encoding="utf-8")
    if include_renamed_asset:
        (host / "old.py").write_text("old managed\n", encoding="utf-8")
    if include_stale_same_target_asset:
        (host / "stale.py").write_text("old managed\n", encoding="utf-8")
    if include_merge_noop_asset:
        (host / "hooks.json").write_text(
            json.dumps(merge_target, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    (host / ".bridgeforge_version").write_text("0.94.2\n", encoding="utf-8")
    (repo / "VERSION").write_text("3.0.0\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "baseline")

    current_agents = (
        "<!-- PUBLIC -->\nnew public\n<!-- /PUBLIC -->\n\n"
        "<!-- PROJECT -->\n## Project Zone\n\n"
        + ("PROJECT CUSTOM SEMANTICS" if customize_old_agents else "project defaults")
        + "\n\n<!-- /PROJECT -->\n"
    )
    zones = {
        "format": "bridgeforge-agents-zones",
        "public": {
            "begin": "<!-- PUBLIC -->",
            "end": "<!-- /PUBLIC -->",
            "current_sha256": VERSION_RELEASE._sha256_bytes(
                b"<!-- PUBLIC -->\nnew public\n<!-- /PUBLIC -->\n"
            ),
        },
        "project": {
            "begin": "<!-- PROJECT -->",
            "end": "<!-- /PROJECT -->",
            "legacy_section_migrations": [{
                "legacy_heading": "## Project",
                "project_heading": "## Project Zone",
            }],
        },
    }
    current_assets = [{
        "id": "root.agents",
        "target": "AGENTS.md",
        "strategy": "whole",
        "agents_zones": zones,
        "section_layout": {
            "format": "markdown-section-layout",
            "groups": [
                {
                    "heading": "## Project",
                    "ownership": "project",
                    "required": True,
                },
                {
                    "heading": "## Managed",
                    "ownership": "managed",
                    "trusted_legacy_sha256": {
                        "## Managed": {
                            "0.94.2": [VERSION_RELEASE._sha256_bytes(
                                b"## Managed\n\nold public\n"
                            )]
                        }
                    },
                },
            ],
            "trusted_residual_sha256": {
                "0.94.2": [VERSION_RELEASE._sha256_bytes(b"# Project\n\n")]
            },
        },
        "current_sha256": VERSION_RELEASE._sha256_bytes(
            current_agents.encode("utf-8")
        ),
    }]
    if include_renamed_asset:
        current_assets.append({
            "id": "codex.renamed",
            "target": ".codex/new.py",
            "strategy": "whole",
            "current_sha256": VERSION_RELEASE._sha256_bytes(b"new managed\n"),
        })
    if include_stale_same_target_asset:
        current_assets.append({
            "id": "codex.stale",
            "target": ".codex/stale.py",
            "strategy": "whole",
            "current_sha256": VERSION_RELEASE._sha256_bytes(b"new managed\n"),
        })
    if include_merge_noop_asset:
        current_assets.append({
            "id": "codex.hooks-config",
            "target": ".codex/hooks.json",
            "strategy": "merge",
            "current_sha256": VERSION_RELEASE._sha256_bytes(b"new canonical source\n"),
            "merge_policy": "codex-hooks",
            "merge_validation": {
                "format": "codex-hooks-dispatchers-v1",
                "required_handlers": [{
                    "event": "PreToolUse",
                    "matcher": "Bash|Edit|Write",
                    "stage": "pre-tool",
                    "sha256": VERSION_RELEASE._canonical_json_sha256(merge_handler),
                }],
            },
        })
    current_contract = {
        "schema_version": 2,
        "release_version": "1.4.3",
        "stamp": ".codex/.bridgeforge_codex_version",
        "contract_target": ".codex/managed-skeleton.json",
        "contract_historical_sha256": {
            "0.94.2": [VERSION_RELEASE._sha256_bytes(old_payload)]
        },
        "assets": current_assets,
    }
    (host / "managed-skeleton.json").write_text(
        json.dumps(current_contract, indent=2) + "\n", encoding="utf-8"
    )
    (repo / "AGENTS.md").write_text(current_agents, encoding="utf-8")
    (host / ".bridgeforge_version").unlink()
    (host / ".bridgeforge_codex_version").write_text("1.4.3\n", encoding="utf-8")
    changed = {
        ".codex/managed-skeleton.json",
        ".codex/.bridgeforge_version",
        ".codex/.bridgeforge_codex_version",
        "AGENTS.md",
    }
    if include_renamed_asset:
        (host / "old.py").unlink()
        (host / "new.py").write_text("new managed\n", encoding="utf-8")
        changed.update({".codex/old.py", ".codex/new.py"})
    return changed


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
            with self.assertRaisesRegex(VERSION_RELEASE.ReleaseError, r"outside \$bridgeforge-codex"):
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

    def test_section_layout_distinguishes_managed_project_and_mixed_changes(self) -> None:
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
                                            "heading": "### 2.1 Index",
                                            "key_column": 0,
                                            "managed_keys": ["rules/core.md"],
                                        }
                                    ],
                                },
                                "section_layout": {
                                    "groups": [
                                        {
                                            "heading": "## 1 Project",
                                            "sections": [
                                                {
                                                    "heading": "### 1.1 Architecture",
                                                    "ownership": "project",
                                                },
                                                {
                                                    "heading": "### 1.2 Style",
                                                    "ownership": "managed",
                                                },
                                            ],
                                        },
                                        {
                                            "heading": "## 2 Skeleton",
                                            "sections": [
                                                {
                                                    "heading": "### 2.1 Index",
                                                    "ownership": "keyed",
                                                }
                                            ],
                                        },
                                    ]
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            baseline = (
                "# Entry\n\n## 1 Project\n\n"
                "### 1.1 Architecture\n\nproject old\n\n"
                "### 1.2 Style\n\nmanaged old\n\n"
                "## 2 Skeleton\n\n### 2.1 Index\n\n"
                "| Rule | Purpose |\n|---|---|\n"
                "| `rules/core.md` | upstream |\n"
                "| `rules/local.md` | local old |\n"
            )
            agents = repo / "AGENTS.md"
            agents.write_text(baseline, encoding="utf-8")
            (host / ".bridgeforge_version").write_text("0.95.0\n", encoding="utf-8")
            (repo / "VERSION").write_text("3.0.0\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "baseline")
            configs = VERSION_RELEASE._load_managed_configs(repo)

            agents.write_text(
                baseline.replace("project old", "project new"), encoding="utf-8"
            )
            _config, managed, project = VERSION_RELEASE._change_ownership(
                repo, "AGENTS.md", configs
            )
            self.assertEqual((managed, project), (False, True))

            agents.write_text(
                baseline.replace("managed old", "managed new"), encoding="utf-8"
            )
            _config, managed, project = VERSION_RELEASE._change_ownership(
                repo, "AGENTS.md", configs
            )
            self.assertEqual((managed, project), (True, False))

            agents.write_text(
                baseline.replace("project old", "project new").replace(
                    "managed old", "managed new"
                ),
                encoding="utf-8",
            )
            _config, managed, project = VERSION_RELEASE._change_ownership(
                repo, "AGENTS.md", configs
            )
            self.assertEqual((managed, project), (True, True))

    def test_agents_zones_distinguish_public_project_and_mixed_changes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            host = repo / ".codex"
            host.mkdir(parents=True)
            zones = {
                "format": "bridgeforge-agents-zones",
                "public": {"begin": "<!-- PUBLIC -->", "end": "<!-- /PUBLIC -->"},
                "project": {"begin": "<!-- PROJECT -->", "end": "<!-- /PROJECT -->"},
            }
            (host / "managed-skeleton.json").write_text(json.dumps({
                "schema_version": 2,
                "stamp": ".codex/.bridgeforge_version",
                "contract_target": ".codex/managed-skeleton.json",
                "assets": [{
                    "id": "root.agents", "target": "AGENTS.md",
                    "strategy": "whole", "agents_zones": zones,
                }],
            }), encoding="utf-8")
            baseline = (
                "<!-- PUBLIC -->\npublic old\n<!-- /PUBLIC -->\n\n"
                "<!-- PROJECT -->\nproject old\n<!-- /PROJECT -->\n"
            )
            agents = repo / "AGENTS.md"
            agents.write_text(baseline, encoding="utf-8")
            (host / ".bridgeforge_version").write_text("1.2.0\n", encoding="utf-8")
            (repo / "VERSION").write_text("3.0.0\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "baseline")
            configs = VERSION_RELEASE._load_managed_configs(repo)

            cases = (
                (baseline.replace("project old", "project new"), (False, True)),
                (baseline.replace("public old", "public new"), (True, False)),
                (
                    baseline.replace("public old", "public new").replace(
                        "project old", "project new"
                    ),
                    (True, True),
                ),
            )
            for payload, expected in cases:
                agents.write_text(payload, encoding="utf-8")
                _config, managed, project = VERSION_RELEASE._change_ownership(
                    repo, "AGENTS.md", configs
                )
                self.assertEqual((managed, project), expected)

            agents.write_text(baseline.replace("<!-- /PROJECT -->", ""), encoding="utf-8")
            with self.assertRaisesRegex(VERSION_RELEASE.ReleaseError, "missing or duplicated"):
                VERSION_RELEASE._change_ownership(repo, "AGENTS.md", configs)

    def test_trusted_contract_transition_is_skeleton_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(repo)

            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, set(reversed(sorted(changed)))),
                "skeleton-only",
            )
            self.assertIsNone(
                VERSION_RELEASE.build_release_plan(repo, "chore: 更新骨架", changed)
            )

    def test_contract_transition_with_project_change_is_mixed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(repo)
            (repo / "project.txt").write_text("project change\n", encoding="utf-8")
            changed.add("project.txt")

            plan = VERSION_RELEASE.build_release_plan(
                repo, "fix: 同步骨架并修改项目", changed
            )
            self.assertIsNotNone(plan)
            self.assertEqual(plan.classification, "mixed")

    def test_contract_transition_rejects_untrusted_head_and_missing_stamp(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(repo)
            contract_path = repo / ".codex/managed-skeleton.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["contract_historical_sha256"]["0.94.2"] = ["sha256:" + "0" * 64]
            contract_path.write_text(json.dumps(contract) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError, "is not trusted for skeleton 0.94.2"
            ):
                VERSION_RELEASE.classify_changes(repo, changed)

        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(repo)
            (repo / ".codex/.bridgeforge_codex_version").unlink()
            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError, "current skeleton stamp is missing"
            ):
                VERSION_RELEASE.classify_changes(repo, changed)

    def test_contract_transition_rejects_stamp_contract_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(repo)
            (repo / ".codex/.bridgeforge_codex_version").write_text(
                "99.0.0\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError, "does not match.*release_version"
            ):
                VERSION_RELEASE.classify_changes(repo, changed)

    def test_contract_transition_maps_legacy_project_content_and_rejects_loss(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(
                repo, customize_old_agents=True
            )
            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, changed), "mixed"
            )
            agents = repo / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8").replace(
                    "PROJECT CUSTOM SEMANTICS", "project defaults"
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError,
                "legacy AGENTS project content changed during migration",
            ):
                VERSION_RELEASE.classify_changes(repo, changed)

    def test_contract_transition_rejects_mismatched_whole_asset(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(repo)
            contract_path = repo / ".codex/managed-skeleton.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["assets"].append({
                "id": "codex.guard",
                "target": ".codex/guard.py",
                "strategy": "whole",
                "current_sha256": "sha256:" + "0" * 64,
            })
            contract_path.write_text(json.dumps(contract) + "\n", encoding="utf-8")
            (repo / ".codex/guard.py").write_text("not declared\n", encoding="utf-8")
            changed.add(".codex/guard.py")
            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError, "does not match its declared hash"
            ):
                VERSION_RELEASE.classify_changes(repo, changed)

    def test_contract_transition_rejects_missing_new_asset(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(repo)
            contract_path = repo / ".codex/managed-skeleton.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["assets"].append({
                "id": "codex.missing",
                "target": ".codex/missing.py",
                "strategy": "whole",
                "current_sha256": VERSION_RELEASE._sha256_bytes(b"expected\n"),
            })
            contract_path.write_text(json.dumps(contract) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError, "target migration is missing changed paths"
            ):
                VERSION_RELEASE.classify_changes(repo, changed)

    def test_contract_transition_rejects_mismatched_managed_region(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(repo)
            contract_path = repo / ".codex/managed-skeleton.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["assets"].append({
                "id": "codex.region",
                "target": ".githooks/pre-commit",
                "strategy": "region",
                "current_sha256": "sha256:" + "0" * 64,
                "region": {
                    "begin": "# BEGIN",
                    "end": "# END",
                    "current_sha256": "sha256:" + "0" * 64,
                    "historical_sha256": {},
                },
            })
            contract_path.write_text(json.dumps(contract) + "\n", encoding="utf-8")
            hook = repo / ".githooks/pre-commit"
            hook.parent.mkdir(parents=True)
            hook.write_text("# BEGIN\nmanaged\n# END\nproject\n", encoding="utf-8")
            changed.add(".githooks/pre-commit")
            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError,
                "current managed region does not match its declared hash",
            ):
                VERSION_RELEASE.classify_changes(repo, changed)

    def test_contract_transition_aligns_target_rename_by_asset_id(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(
                repo, include_renamed_asset=True
            )
            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, changed), "skeleton-only"
            )
            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError, "target migration is missing changed paths"
            ):
                VERSION_RELEASE.classify_changes(
                    repo, changed - {".codex/old.py"}
                )

    def test_contract_transition_rejects_unreported_same_target_digest_change(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(
                repo, include_stale_same_target_asset=True
            )
            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError,
                "target migration is missing changed paths",
            ):
                VERSION_RELEASE.classify_changes(repo, changed)

    def test_contract_transition_accepts_verified_unchanged_merge_target(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(
                repo,
                include_merge_noop_asset=True,
            )

            self.assertNotIn(".codex/hooks.json", changed)
            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, changed),
                "skeleton-only",
            )
            hooks = json.loads(
                (repo / ".codex/hooks.json").read_text(encoding="utf-8")
            )
            commands = hooks["hooks"]["PreToolUse"][0]["hooks"]
            self.assertTrue(any("project_hook.py" in item["commandWindows"] for item in commands))

    def test_contract_transition_rejects_drifted_unchanged_merge_target(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(
                repo,
                include_merge_noop_asset=True,
                drift_merge_target_before_baseline=True,
            )

            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError,
                "managed dispatcher drifted",
            ):
                VERSION_RELEASE.classify_changes(repo, changed)

    def test_contract_transition_rejects_missing_unchanged_merge_handler(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(
                repo,
                include_merge_noop_asset=True,
                omit_merge_handler_before_baseline=True,
            )
            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError,
                "missing managed dispatcher",
            ):
                VERSION_RELEASE.classify_changes(repo, changed)

    def test_contract_transition_rejects_duplicate_unchanged_merge_handler(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(
                repo,
                include_merge_noop_asset=True,
                duplicate_merge_handler_before_baseline=True,
            )
            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError,
                "managed dispatcher drifted",
            ):
                VERSION_RELEASE.classify_changes(repo, changed)

    def test_contract_transition_rejects_invalid_current_agents_zones(self) -> None:
        invalid_replacements = (
            ("<!-- /PROJECT -->", ""),
            ("<!-- /PROJECT -->", "<!-- PUBLIC -->"),
            (
                "<!-- PUBLIC -->\nnew public\n<!-- /PUBLIC -->",
                "<!-- /PUBLIC -->\nnew public\n<!-- PUBLIC -->",
            ),
            ("<!-- PUBLIC -->", "outside\n<!-- PUBLIC -->"),
        )
        for old, new in invalid_replacements:
            with self.subTest(replacement=new), tempfile.TemporaryDirectory() as raw:
                repo = Path(raw)
                init_repo(repo)
                changed = write_contract_transition_fixture(repo)
                agents = repo / "AGENTS.md"
                agents.write_text(
                    agents.read_text(encoding="utf-8").replace(old, new),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(
                    VERSION_RELEASE.ReleaseError,
                    "current AGENTS ownership is invalid|public zone does not match",
                ):
                    VERSION_RELEASE.classify_changes(repo, changed)

    def test_managed_markdown_release_scanner_is_fence_aware(self) -> None:
        payload = (
            "# Entry\n\n## Managed\n\n"
            "```markdown\n## Example\n```\n\n"
            "## Project\n\nlocal\n"
        ).encode("utf-8")
        managed, project = VERSION_RELEASE._markdown_heading_parts(
            payload,
            ["## Managed"],
        )
        self.assertIn(b"## Example", managed)
        self.assertIn(b"## Project", project)
        with self.assertRaisesRegex(VERSION_RELEASE.ReleaseError, "unclosed"):
            VERSION_RELEASE._markdown_heading_parts(
                b"## Managed\n\n~~~markdown\n## Example\n",
                ["## Managed"],
            )

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
            with self.assertRaisesRegex(VERSION_RELEASE.ReleaseError, r"outside \$bridgeforge-codex"):
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
            with self.assertRaisesRegex(VERSION_RELEASE.ReleaseError, r"outside \$bridgeforge-codex"):
                VERSION_RELEASE.build_release_plan(
                    repo, "fix: 不允许", {".codex/hooks/guard.py"}
                )

    def test_project_rules_do_not_require_skeleton_stamp(self) -> None:
        for host_name in (".codex",):
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
                with self.assertRaisesRegex(VERSION_RELEASE.ReleaseError, r"outside \$bridgeforge-codex"):
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
