#!/usr/bin/env python3
"""Focused regression coverage for automatic git-sync version releases."""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "templates" / "scripts" / "version_release.py"
SPEC = importlib.util.spec_from_file_location("version_release_under_test", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
VERSION_RELEASE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VERSION_RELEASE
SPEC.loader.exec_module(VERSION_RELEASE)
SCRIPTS_DIR = ROOT / "templates" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
GIT_SYNC_SPEC = importlib.util.spec_from_file_location(
    "codex_git_sync_under_test",
    SCRIPTS_DIR / "codex_git_sync.py",
)
assert GIT_SYNC_SPEC is not None and GIT_SYNC_SPEC.loader is not None
GIT_SYNC = importlib.util.module_from_spec(GIT_SYNC_SPEC)
sys.modules[GIT_SYNC_SPEC.name] = GIT_SYNC
GIT_SYNC_SPEC.loader.exec_module(GIT_SYNC)


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
    legacy_unzoned_agents: bool = False,
    include_renamed_asset: bool = False,
    include_stale_same_target_asset: bool = False,
    include_merge_noop_asset: bool = False,
    drift_merge_target_before_baseline: bool = False,
    omit_merge_handler_before_baseline: bool = False,
    duplicate_merge_handler_before_baseline: bool = False,
    legacy_merge_without_projection: bool = False,
    include_project_merge_handler: bool = True,
    include_region_asset: bool = False,
    old_region_mode: str = "valid",
) -> set[str]:
    host = repo / ".codex"
    host.mkdir(parents=True)
    if legacy_unzoned_agents:
        old_agents = (
            "# Project\n\n## Project\n\nproject defaults\n\n"
            "## Managed\n\nold public\n"
        )
    else:
        old_agents = (
            "<!-- PUBLIC -->\nold public\n<!-- /PUBLIC -->\n\n"
            "<!-- PROJECT -->\n## Project Zone\n\nproject defaults\n\n"
            "<!-- /PROJECT -->\n"
        )
    old_asset = {
        "id": "root.agents",
        "target": "AGENTS.md",
        "strategy": "whole",
        "current_sha256": VERSION_RELEASE._sha256_bytes(old_agents.encode("utf-8")),
    }
    if not legacy_unzoned_agents:
        old_asset["agents_zones"] = {
            "format": "bridgeforge-agents-zones",
            "public": {
                "begin": "<!-- PUBLIC -->",
                "end": "<!-- /PUBLIC -->",
                "current_sha256": VERSION_RELEASE._sha256_bytes(
                    b"<!-- PUBLIC -->\nold public\n<!-- /PUBLIC -->\n"
                ),
            },
            "project": {
                "begin": "<!-- PROJECT -->",
                "end": "<!-- /PROJECT -->",
            },
        }
    old_assets = [old_asset]
    old_region = (
        b"# >>> BRIDGEFORGE_MANAGED_BEGIN\n"
        b"old managed\n"
        b"# <<< BRIDGEFORGE_MANAGED_END"
    )
    if old_region_mode == "missing-end":
        old_region = b"# >>> BRIDGEFORGE_MANAGED_BEGIN\nold managed"
    elif old_region_mode == "duplicate":
        old_region += b"\n" + old_region
    elif old_region_mode == "current-missing-end":
        old_region = b"# >>> BRIDGEFORGE_CODEX_MANAGED_BEGIN\nold managed"
    elif old_region_mode == "current-duplicate":
        old_region = (
            b"# >>> BRIDGEFORGE_CODEX_MANAGED_BEGIN\nold managed\n"
            b"# <<< BRIDGEFORGE_CODEX_MANAGED_END"
        )
        old_region += b"\n" + old_region
    elif old_region_mode == "current-reversed":
        old_region = (
            b"# <<< BRIDGEFORGE_CODEX_MANAGED_END\nold managed\n"
            b"# >>> BRIDGEFORGE_CODEX_MANAGED_BEGIN"
        )
    elif old_region_mode == "current-drift":
        old_region = (
            b"# >>> BRIDGEFORGE_CODEX_MANAGED_BEGIN\ntampered managed\n"
            b"# <<< BRIDGEFORGE_CODEX_MANAGED_END"
        )
    elif old_region_mode != "valid":
        raise AssertionError(f"unsupported old region mode: {old_region_mode}")
    new_region = (
        b"# >>> BRIDGEFORGE_CODEX_MANAGED_BEGIN\n"
        b"new managed\n"
        b"# <<< BRIDGEFORGE_CODEX_MANAGED_END"
    )
    project_extension = b"\n\n# project extension\nexit 0\n"
    if include_region_asset:
        old_assets.append({
            "id": "codex.precommit",
            "target": ".githooks/pre-commit",
            "strategy": "region",
            "current_sha256": VERSION_RELEASE._sha256_bytes(old_region),
            "region": {
                "begin": "# >>> BRIDGEFORGE_MANAGED_BEGIN",
                "end": "# <<< BRIDGEFORGE_MANAGED_END",
            },
        })
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
    legacy_merge_handler = {
        "type": "command",
        "commandWindows": (
            "python .codex/hooks/hook_dispatcher.py pre-tool"
        ),
        "comment": "current managed dispatcher",
    }
    legacy_merge_required = [{
        "event": "PreToolUse",
        "matcher": "Bash|Edit|Write",
        "stage": "pre-tool",
        "sha256": VERSION_RELEASE._canonical_json_sha256(legacy_merge_handler),
    }]
    merge_handler = dict(legacy_merge_handler)
    merge_handler["bridgeforgeCodexId"] = (
        "bridgeforge-codex.project-hook.v1:pre-tool"
    )
    merge_required = [{
        "id": merge_handler["bridgeforgeCodexId"],
        "event": "PreToolUse",
        "matcher": "Bash|Edit|Write",
        "stage": "pre-tool",
        "sha256": VERSION_RELEASE._canonical_json_sha256(merge_handler),
    }]
    merge_projection = VERSION_RELEASE._canonical_json_sha256(merge_required)
    legacy_merge_projection = VERSION_RELEASE._canonical_json_sha256(
        legacy_merge_required
    )
    target_merge_handler = dict(legacy_merge_handler)
    if drift_merge_target_before_baseline:
        target_merge_handler["comment"] = "drifted managed dispatcher"
    target_handlers = [] if omit_merge_handler_before_baseline else [target_merge_handler]
    if duplicate_merge_handler_before_baseline:
        target_handlers.append(dict(target_merge_handler))
    if include_project_merge_handler:
        target_handlers.append(
            {"type": "command", "commandWindows": "python project_hook.py"}
        )
    historical_managed_description = "historical managed description"
    merge_target = {
        "description": historical_managed_description,
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash|Edit|Write",
                    "hooks": target_handlers,
                }
            ]
        },
    }
    legacy_whole_merge_target = {
        "description": historical_managed_description,
        "hooks": {
            "PreToolUse": [{
                "matcher": "Bash|Edit|Write",
                "hooks": (
                    [legacy_merge_handler]
                    + (
                        [{"type": "command", "commandWindows": "python project_hook.py"}]
                        if include_project_merge_handler
                        else []
                    )
                ),
            }]
        },
    }
    if include_merge_noop_asset:
        old_merge_asset = {
            "id": "codex.hooks-config",
            "target": ".codex/hooks.json",
            "strategy": "merge",
            "current_sha256": VERSION_RELEASE._sha256_bytes(
                (
                    json.dumps(
                        legacy_whole_merge_target,
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n"
                ).encode("utf-8")
                if legacy_merge_without_projection
                else b"old canonical source\n"
            ),
            "merge_policy": "codex-hooks",
        }
        if not legacy_merge_without_projection:
            old_merge_asset["merge_validation"] = {
                "format": "codex-hooks-dispatchers-v1",
                "required_handlers": legacy_merge_required,
                "current_projection_sha256": legacy_merge_projection,
            }
        old_assets.append(old_merge_asset)
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
    if include_region_asset:
        precommit = repo / ".githooks" / "pre-commit"
        precommit.parent.mkdir(parents=True)
        precommit.write_bytes(old_region + project_extension)
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
        },
    }
    current_assets = [{
        "id": "root.agents",
        "target": "AGENTS.md",
        "strategy": "whole",
        "agents_zones": zones,
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
                "format": "codex-hooks-zones-v2",
                "required_handlers": merge_required,
                "current_projection_sha256": merge_projection,
                "managed_top_level": {
                    "description": "managed description",
                },
                "managed_top_level_historical": {
                    "description": [historical_managed_description],
                },
            },
        })
    if include_region_asset:
        current_assets.append({
            "id": "codex.precommit",
            "target": ".githooks/pre-commit",
            "strategy": "region",
            "current_sha256": VERSION_RELEASE._sha256_bytes(
                new_region + project_extension
            ),
                "region": {
                    "begin": "# >>> BRIDGEFORGE_CODEX_MANAGED_BEGIN",
                    "end": "# <<< BRIDGEFORGE_CODEX_MANAGED_END",
                    "current_sha256": VERSION_RELEASE._sha256_bytes(new_region),
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
    if include_merge_noop_asset:
        current_merge_target = {
            "description": "managed description",
            "hooks": {
                "PreToolUse": (
                    ([{
                        "matcher": "Bash|Edit|Write",
                        "hooks": [
                            {"type": "command", "commandWindows": "python project_hook.py"}
                        ],
                    }] if include_project_merge_handler else [])
                    + [{
                        "matcher": "Bash|Edit|Write",
                        "hooks": [merge_handler],
                    }]
                )
            },
        }
        (host / "hooks.json").write_text(
            json.dumps(current_merge_target, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
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
    if include_region_asset:
        (repo / ".githooks/pre-commit").write_bytes(
            new_region + project_extension
        )
        changed.add(".githooks/pre-commit")
    if include_merge_noop_asset:
        changed.add(".codex/hooks.json")
    return changed


def write_schema_v1_transition_fixture(
    repo: Path,
    *,
    minimum_supported_version: str = "0.86.0",
    claim_unowned_existing: bool = False,
    omit_legacy_region: bool = False,
) -> tuple[set[str], Path, Path]:
    host = repo / ".codex"
    hooks = host / "hooks"
    hook = repo / ".githooks" / "pre-commit"
    hooks.mkdir(parents=True)
    hook.parent.mkdir(parents=True)
    old_version = "0.90.0"
    old_managed = b"old managed\n"
    new_managed = b"new managed\n"
    old_region = b"# LEGACY BEGIN\nold managed\n# LEGACY END"
    new_region = b"# BEGIN\nnew managed\n# END"
    legacy_regions = [] if omit_legacy_region else [{
        "path": ".githooks/pre-commit",
        "begin": "# LEGACY BEGIN",
        "end": "# LEGACY END",
    }]
    legacy_contract = {
        "schema_version": 1,
        "stamp": ".codex/.bridgeforge_version",
        "whole_files": [
            ".codex/.bridgeforge_version",
            ".codex/managed-skeleton.json",
            ".codex/hooks/*.py",
        ],
        "managed_regions": legacy_regions,
    }
    legacy_payload = (json.dumps(legacy_contract, indent=2) + "\n").encode("utf-8")
    (host / "managed-skeleton.json").write_bytes(legacy_payload)
    (host / ".bridgeforge_version").write_text(old_version + "\n", encoding="utf-8")
    (hooks / "managed.py").write_bytes(old_managed)
    (hooks / "project_extra.py").write_text("project extra\n", encoding="utf-8")
    hook.write_bytes(old_region + b"\nproject tail\n")
    if claim_unowned_existing:
        (host / "unowned.py").write_text("old unowned\n", encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "schema v1 baseline")

    assets = [
        {
            "id": "codex.hook.managed",
            "target": ".codex/hooks/managed.py",
            "strategy": "whole",
            "current_sha256": VERSION_RELEASE._sha256_bytes(new_managed),
            "historical_sha256": {
                old_version: [VERSION_RELEASE._sha256_bytes(old_managed)],
            },
        },
        {
            "id": "codex.precommit",
            "target": ".githooks/pre-commit",
            "strategy": "region",
            "current_sha256": VERSION_RELEASE._sha256_bytes(
                new_region + b"\nproject tail\n"
            ),
            "region": {
                "begin": "# BEGIN",
                "end": "# END",
                "current_sha256": VERSION_RELEASE._sha256_bytes(new_region),
            },
        },
    ]
    if claim_unowned_existing:
        assets.append({
            "id": "codex.unowned",
            "target": ".codex/unowned.py",
            "strategy": "whole",
            "current_sha256": VERSION_RELEASE._sha256_bytes(b"new unowned\n"),
            "historical_sha256": {},
        })
    current_contract = {
        "schema_version": 2,
        "release_version": "1.4.16",
        "minimum_supported_version": minimum_supported_version,
        "stamp": ".codex/.bridgeforge_codex_version",
        "contract_target": ".codex/managed-skeleton.json",
        "contract_historical_sha256": {
            old_version: [VERSION_RELEASE._sha256_bytes(legacy_payload)],
        },
        "assets": assets,
    }
    contract_path = host / "managed-skeleton.json"
    contract_path.write_text(
        json.dumps(current_contract, indent=2) + "\n",
        encoding="utf-8",
    )
    (host / ".bridgeforge_version").unlink()
    (host / ".bridgeforge_codex_version").write_text(
        "1.4.16\n",
        encoding="utf-8",
    )
    (hooks / "managed.py").write_bytes(new_managed)
    hook.write_bytes(new_region + b"\nproject tail\n")
    changed = {
        ".codex/managed-skeleton.json",
        ".codex/.bridgeforge_version",
        ".codex/.bridgeforge_codex_version",
        ".codex/hooks/managed.py",
        ".githooks/pre-commit",
    }
    if claim_unowned_existing:
        (host / "unowned.py").write_text("new unowned\n", encoding="utf-8")
        changed.add(".codex/unowned.py")
    return changed, contract_path, hooks / "project_extra.py"


def write_schema_v1_nested_history_fixture(
    repo: Path,
    strategy: str,
) -> set[str]:
    host = repo / ".codex"
    host.mkdir(parents=True)
    old_version = "0.90.0"
    later_version = "0.91.0"

    if strategy == "merge":
        target = ".codex/hooks.json"
        handler = {
            "type": "command",
            "commandWindows": "python .codex/hooks/hook_dispatcher.py pre-tool",
            "comment": "managed dispatcher",
        }
        required = [{
            "event": "PreToolUse",
            "matcher": "Bash|Edit|Write",
            "stage": "pre-tool",
            "sha256": VERSION_RELEASE._canonical_json_sha256(handler),
        }]
        payload = (json.dumps({
            "hooks": {
                "PreToolUse": [{
                    "matcher": "Bash|Edit|Write",
                    "hooks": [handler],
                }],
            },
        }, indent=2) + "\n").encode("utf-8")
        projection = VERSION_RELEASE._canonical_json_sha256(required)
        asset = {
            "id": "codex.hooks-config",
            "target": target,
            "strategy": "merge",
            "current_sha256": VERSION_RELEASE._sha256_bytes(payload),
            "historical_sha256": {},
            "merge_policy": "codex-hooks",
            "merge_validation": {
                "format": "codex-hooks-dispatchers-v1",
                "required_handlers": required,
                "current_projection_sha256": projection,
                "historical_projection_sha256": {
                    later_version: [projection],
                },
            },
        }
        legacy_whole = [target]
        legacy_regions: list[dict[str, str]] = []
    elif strategy == "managed-markdown":
        target = "doc/README.md"
        payload = b"# Doc\n\n## Managed\n\nmanaged\n\n## Project\n\nlocal\n"
        managed, _project = VERSION_RELEASE._managed_markdown_parts(
            payload,
            ["## Managed"],
            [],
            [],
        )
        projection = VERSION_RELEASE._sha256_bytes(managed or b"")
        asset = {
            "id": "codex.doc.readme",
            "target": target,
            "strategy": "whole",
            "current_sha256": VERSION_RELEASE._sha256_bytes(payload),
            "historical_sha256": {},
            "managed_blocks": {
                "format": "markdown-headings",
                "headings": ["## Managed"],
                "additive_headings": [],
                "keyed_tables": [],
                "current_projection_sha256": projection,
                "historical_projection_sha256": {
                    later_version: [projection],
                },
            },
        }
        legacy_whole = [target]
        legacy_regions = []
    elif strategy == "region":
        target = ".githooks/pre-commit"
        payload = b"# BEGIN\nmanaged\n# END\nproject\n"
        region_payload = b"# BEGIN\nmanaged\n# END"
        projection = VERSION_RELEASE._sha256_bytes(region_payload)
        asset = {
            "id": "codex.precommit",
            "target": target,
            "strategy": "region",
            "current_sha256": VERSION_RELEASE._sha256_bytes(payload),
            "historical_sha256": {},
            "region": {
                "begin": "# BEGIN",
                "end": "# END",
                "current_sha256": projection,
                "historical_sha256": {
                    later_version: [projection],
                },
            },
        }
        legacy_whole = []
        legacy_regions = [{
            "path": target,
            "begin": "# BEGIN",
            "end": "# END",
        }]
    else:
        raise AssertionError(f"unsupported nested history strategy: {strategy}")

    legacy_contract = {
        "schema_version": 1,
        "stamp": ".codex/.bridgeforge_version",
        "whole_files": [
            ".codex/.bridgeforge_version",
            ".codex/managed-skeleton.json",
            *legacy_whole,
        ],
        "managed_regions": legacy_regions,
    }
    legacy_payload = (json.dumps(legacy_contract, indent=2) + "\n").encode("utf-8")
    contract_path = host / "managed-skeleton.json"
    contract_path.write_bytes(legacy_payload)
    (host / ".bridgeforge_version").write_text(old_version + "\n", encoding="utf-8")
    target_path = repo / target
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(payload)
    git(repo, "add", ".")
    git(repo, "commit", "-m", "schema v1 nested history baseline")

    current_contract = {
        "schema_version": 2,
        "release_version": "1.4.16",
        "minimum_supported_version": "0.86.0",
        "stamp": ".codex/.bridgeforge_codex_version",
        "contract_target": ".codex/managed-skeleton.json",
        "contract_historical_sha256": {
            old_version: [VERSION_RELEASE._sha256_bytes(legacy_payload)],
        },
        "assets": [asset],
    }
    contract_path.write_text(
        json.dumps(current_contract, indent=2) + "\n",
        encoding="utf-8",
    )
    (host / ".bridgeforge_version").unlink()
    (host / ".bridgeforge_codex_version").write_text(
        "1.4.16\n",
        encoding="utf-8",
    )
    return {
        ".codex/managed-skeleton.json",
        ".codex/.bridgeforge_version",
        ".codex/.bridgeforge_codex_version",
        target,
    }


class VersionReleaseTests(unittest.TestCase):
    def test_git_sync_removes_matching_adaptation_receipt_only_after_commit(self) -> None:
        repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        init_repo(repo)
        receipt = repo / ".runtime" / "bridgeforge-codex" / "explicit-adaptation.json"
        receipt.parent.mkdir(parents=True)
        proof = {"schema_version": 1, "items": [{"id": "G1"}]}
        receipt.write_text(json.dumps(proof) + "\n", encoding="utf-8")
        args = mock.Mock(
            message="fix: explicit adaptation",
            message_file=None,
            remote="origin",
            skip_fetch=True,
            skip_push=True,
        )
        completed = subprocess.CompletedProcess(["git"], 0, stdout="", stderr="")
        with mock.patch.object(GIT_SYNC, "REPO_ROOT", repo), \
                mock.patch.object(GIT_SYNC, "ADAPTATION_RECEIPT", receipt), \
                mock.patch.object(GIT_SYNC, "_upstream", return_value="origin/main"), \
                mock.patch.object(GIT_SYNC, "_push_target", return_value="origin/main"), \
                mock.patch.object(GIT_SYNC, "_status", side_effect=[" M owned.py", ""]), \
                mock.patch.object(GIT_SYNC, "_ahead_behind", return_value=(0, 0)), \
                mock.patch.object(GIT_SYNC, "_changed_paths", return_value={"owned.py"}), \
                mock.patch.object(GIT_SYNC, "_read_adaptation_proof", return_value=proof), \
                mock.patch.object(GIT_SYNC, "build_release_plan", return_value=None) as build, \
                mock.patch.object(GIT_SYNC, "_rebuild_shared_skill_manifest"), \
                mock.patch.object(GIT_SYNC, "_check_factory_version_worktree"), \
                mock.patch.object(GIT_SYNC, "_has_staged_changes", return_value=True), \
                mock.patch.object(GIT_SYNC, "_run_git", return_value=completed):
            result = GIT_SYNC.sync(args)
        self.assertEqual(result, 0)
        self.assertFalse(receipt.exists())
        self.assertIs(build.call_args.kwargs["adaptation_proof"], proof)

    def test_git_sync_keeps_adaptation_receipt_when_commit_fails(self) -> None:
        repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        init_repo(repo)
        receipt = repo / ".runtime" / "bridgeforge-codex" / "explicit-adaptation.json"
        receipt.parent.mkdir(parents=True)
        proof = {"schema_version": 1, "items": [{"id": "G1"}]}
        receipt.write_text(json.dumps(proof) + "\n", encoding="utf-8")
        args = mock.Mock(
            message="fix: explicit adaptation",
            message_file=None,
            remote="origin",
            skip_fetch=True,
            skip_push=True,
        )
        completed = subprocess.CompletedProcess(["git"], 0, stdout="", stderr="")

        def run_git(arguments: list[str], **_kwargs: object) -> object:
            if arguments and arguments[0] == "commit":
                raise GIT_SYNC.SyncStop("git commit failed: fixture", 1)
            return completed

        with mock.patch.object(GIT_SYNC, "REPO_ROOT", repo), \
                mock.patch.object(GIT_SYNC, "ADAPTATION_RECEIPT", receipt), \
                mock.patch.object(GIT_SYNC, "_upstream", return_value="origin/main"), \
                mock.patch.object(GIT_SYNC, "_push_target", return_value="origin/main"), \
                mock.patch.object(GIT_SYNC, "_status", return_value=" M owned.py"), \
                mock.patch.object(GIT_SYNC, "_ahead_behind", return_value=(0, 0)), \
                mock.patch.object(GIT_SYNC, "_changed_paths", return_value={"owned.py"}), \
                mock.patch.object(GIT_SYNC, "_read_adaptation_proof", return_value=proof), \
                mock.patch.object(GIT_SYNC, "build_release_plan", return_value=None), \
                mock.patch.object(GIT_SYNC, "_rebuild_shared_skill_manifest"), \
                mock.patch.object(GIT_SYNC, "_check_factory_version_worktree"), \
                mock.patch.object(GIT_SYNC, "_has_staged_changes", return_value=True), \
                mock.patch.object(GIT_SYNC, "_run_git", side_effect=run_git):
            with self.assertRaisesRegex(GIT_SYNC.SyncStop, "git commit failed"):
                GIT_SYNC.sync(args)
        self.assertTrue(receipt.is_file())

    def test_explicit_adaptation_before_snapshot_rejects_path_aliases(self) -> None:
        with self.assertRaisesRegex(
            VERSION_RELEASE.ReleaseError,
            "path is duplicated",
        ):
            VERSION_RELEASE.decode_explicit_adaptation_before_snapshot({
                "a\\b": "QQ==",
                "a/b": "Qg==",
            })

        with self.assertRaisesRegex(
            VERSION_RELEASE.ReleaseError,
            "path is duplicated",
        ):
            VERSION_RELEASE.encode_explicit_adaptation_before_snapshot({
                "a\\b": b"A",
                "a/b": b"B",
            })

    def test_explicit_adaptation_before_snapshot_rejects_noncanonical_base64(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            VERSION_RELEASE.ReleaseError,
            "payload is not canonical",
        ):
            VERSION_RELEASE.decode_explicit_adaptation_before_snapshot({
                "a/b": "QR==",
            })

    def test_explicit_adaptation_consumes_only_exact_blocked_region(self) -> None:
        repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        init_repo(repo)
        changed = write_contract_transition_fixture(
            repo,
            include_region_asset=True,
            old_region_mode="current-drift",
        )
        with self.assertRaises(VERSION_RELEASE.TransitionBlocked):
            VERSION_RELEASE.evaluate_release_transition(
                repo,
                changed_paths=changed,
            )

        target = ".githooks/pre-commit"
        before = subprocess.run(
            ["git", "show", f"HEAD:{target}"],
            cwd=repo,
            capture_output=True,
            check=True,
        ).stdout
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout.strip()
        item = {
            "id": "G1",
            "asset_id": "codex.precommit",
            "target": target,
            "category": "release_transition_review",
            "before_sha256": VERSION_RELEASE._sha256_bytes(before),
            "after_sha256": VERSION_RELEASE._sha256_bytes(
                (repo / target).read_bytes()
            ),
        }
        before_snapshot = (
            VERSION_RELEASE.freeze_explicit_adaptation_before_snapshot(
                repo,
                None,
                [item],
            )
        )
        evidence = VERSION_RELEASE.build_explicit_adaptation_evidence(
            repo,
            None,
            [item],
            before_snapshot,
        )
        item = evidence["items"][0]
        transition_fingerprint = evidence["transition_fingerprint"]
        encoded_before = (
            VERSION_RELEASE.encode_explicit_adaptation_before_snapshot(
                before_snapshot
            )
        )
        before_fingerprint = (
            VERSION_RELEASE.explicit_adaptation_before_snapshot_fingerprint(
                encoded_before
            )
        )
        aggregate = "sha256:" + "a" * 64
        selection = VERSION_RELEASE._sha256_bytes(
            VERSION_RELEASE._canonical_json({
                "aggregate_fingerprint": aggregate,
                "transition_fingerprint": transition_fingerprint,
                "before_snapshot_fingerprint": before_fingerprint,
                "selected_adaptation_ids": ["G1"],
                "items": [item],
            })
        )
        contract = repo / ".codex" / "managed-skeleton.json"
        proof = {
            "schema_version": 2,
            "project_root": str(repo.resolve()),
            "head": head,
            "contract_target": ".codex/managed-skeleton.json",
            "contract_sha256": VERSION_RELEASE._sha256_bytes(
                contract.read_bytes()
            ),
            "aggregate_fingerprint": aggregate,
            "transition_fingerprint": transition_fingerprint,
            "before_snapshot": encoded_before,
            "before_snapshot_fingerprint": before_fingerprint,
            "selection_fingerprint": selection,
            "items": [item],
        }

        classification, _paths = VERSION_RELEASE.evaluate_release_transition(
            repo,
            changed_paths=changed,
            adaptation_proof=proof,
        )
        self.assertIn(classification, {"skeleton-only", "mixed"})

        drifted = json.loads(json.dumps(proof))
        drifted["items"][0]["after_sha256"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(
            VERSION_RELEASE.ReleaseError,
            "current target drifted",
        ):
            VERSION_RELEASE.evaluate_release_transition(
                repo,
                changed_paths=changed,
                adaptation_proof=drifted,
            )

        anchor_drifted = json.loads(json.dumps(proof))
        anchor_drifted["transition_fingerprint"] = "sha256:" + "1" * 64
        anchor_drifted["selection_fingerprint"] = VERSION_RELEASE._sha256_bytes(
            VERSION_RELEASE._canonical_json({
                "aggregate_fingerprint": anchor_drifted["aggregate_fingerprint"],
                "transition_fingerprint": anchor_drifted["transition_fingerprint"],
                "selected_adaptation_ids": ["G1"],
                "items": anchor_drifted["items"],
            })
        )
        with self.assertRaisesRegex(
            VERSION_RELEASE.ReleaseError,
            "ownership evidence drifted",
        ):
            VERSION_RELEASE.evaluate_release_transition(
                repo,
                changed_paths=changed,
                adaptation_proof=anchor_drifted,
            )

        for field, value, message in (
            ("project_root", str(repo.parent.resolve()), "another project"),
            ("head", "0" * 40, "HEAD drifted"),
            ("contract_sha256", "sha256:" + "2" * 64, "contract hash drifted"),
        ):
            with self.subTest(field=field):
                invalid = json.loads(json.dumps(proof))
                invalid[field] = value
                with self.assertRaisesRegex(VERSION_RELEASE.ReleaseError, message):
                    VERSION_RELEASE.evaluate_release_transition(
                        repo,
                        changed_paths=changed,
                        adaptation_proof=invalid,
                    )

    def test_explicit_region_adaptation_rejects_project_extension_change(self) -> None:
        repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        init_repo(repo)
        write_contract_transition_fixture(
            repo,
            include_region_asset=True,
            old_region_mode="current-drift",
        )
        target = ".githooks/pre-commit"
        path = repo / target
        path.write_bytes(path.read_bytes().replace(b"exit 0", b"exit 99"))
        before = subprocess.run(
            ["git", "show", f"HEAD:{target}"],
            cwd=repo,
            capture_output=True,
            check=True,
        ).stdout
        item = {
            "id": "G1",
            "asset_id": "codex.precommit",
            "target": target,
            "category": "release_transition_review",
            "before_sha256": VERSION_RELEASE._sha256_bytes(before),
            "after_sha256": VERSION_RELEASE._sha256_bytes(path.read_bytes()),
        }
        with self.assertRaisesRegex(
            VERSION_RELEASE.ReleaseError,
            "project extension",
        ):
            VERSION_RELEASE.build_explicit_adaptation_evidence(repo, None, [item])

    def test_explicit_hooks_adaptation_preserves_external_handlers(self) -> None:
        repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        init_repo(repo)
        write_contract_transition_fixture(
            repo,
            include_merge_noop_asset=True,
            legacy_merge_without_projection=True,
        )
        target = ".codex/hooks.json"
        before = subprocess.run(
            ["git", "show", f"HEAD:{target}"],
            cwd=repo,
            capture_output=True,
            check=True,
        ).stdout
        path = repo / target
        prospective_document = json.loads(path.read_text(encoding="utf-8"))
        user_prompt = {
            "type": "command",
            "commandWindows": (
                "python .codex/hooks/hook_dispatcher.py user-prompt"
            ),
            "bridgeforgeCodexId": (
                "bridgeforge-codex.project-hook.v1:user-prompt"
            ),
        }
        prospective_document["hooks"]["UserPromptSubmit"] = [{
            "matcher": "",
            "hooks": [user_prompt],
        }]
        external_handler = {
            "type": "command",
            "commandWindows": "python .codex/hooks/root_hygiene_check.py",
        }
        prospective_document["hooks"]["SessionStart"] = [{
            "matcher": "startup",
            "hooks": [external_handler],
        }]
        prospective = (
            json.dumps(prospective_document, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")

        historical_description = (
            "BridgeForge project lifecycle hooks. This is the only managed "
            "Codex hook registration source."
        )
        current_before_document = json.loads(before.decode("utf-8"))
        current_before_document["description"] = historical_description
        legacy_user_prompt = dict(user_prompt)
        legacy_user_prompt.pop("bridgeforgeCodexId")
        current_before_document["hooks"]["UserPromptSubmit"] = [{
            "matcher": "",
            "hooks": [legacy_user_prompt],
        }]
        current_before_document["hooks"]["SessionStart"] = [{
            "matcher": "startup",
            "hooks": [external_handler],
        }]
        current_before = (
            json.dumps(current_before_document, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        path.write_bytes(current_before)

        contract_path = repo / ".codex/managed-skeleton.json"
        prospective_contract = json.loads(
            contract_path.read_text(encoding="utf-8")
        )
        prospective_asset = next(
            asset
            for asset in prospective_contract["assets"]
            if asset["id"] == "codex.hooks-config"
        )
        prospective_required = list(
            prospective_asset["merge_validation"]["required_handlers"]
        )
        prospective_required.append({
            "id": user_prompt["bridgeforgeCodexId"],
            "event": "UserPromptSubmit",
            "matcher": "",
            "stage": "user-prompt",
            "sha256": VERSION_RELEASE._canonical_json_sha256(user_prompt),
        })
        prospective_required.sort(
            key=lambda entry: (
                entry["event"],
                entry["matcher"],
                entry["stage"],
                entry["id"],
            )
        )
        prospective_asset["merge_validation"][
            "required_handlers"
        ] = prospective_required
        prospective_asset["merge_validation"][
            "current_projection_sha256"
        ] = VERSION_RELEASE._canonical_json_sha256(prospective_required)
        prospective_asset["merge_validation"][
            "managed_top_level_historical"
        ] = {
            "description": [
                historical_description,
                json.loads(before.decode("utf-8"))["description"],
            ]
        }

        current_before_contract = json.loads(json.dumps(prospective_contract))
        current_before_contract["release_version"] = "1.4.2"
        current_before_contract["contract_historical_sha256"] = {}
        current_before_contract["assets"].append({
            "id": "codex.precommit",
            "target": ".githooks/pre-commit",
            "strategy": "region",
            "region": {
                "begin": "# OLD MANAGED BEGIN",
                "end": "# OLD MANAGED END",
                "current_sha256": "sha256:" + "2" * 64,
                "historical_sha256": {
                    "1.4.1": ["sha256:" + "1" * 64],
                },
            },
        })
        current_before_asset = next(
            asset
            for asset in current_before_contract["assets"]
            if asset["id"] == "codex.hooks-config"
        )
        current_before_required = []
        for event, groups in current_before_document["hooks"].items():
            for group in groups:
                for handler in group["hooks"]:
                    stage = VERSION_RELEASE._dispatcher_stage(handler)
                    if stage is None:
                        continue
                    current_before_required.append({
                        "event": event,
                        "matcher": group.get("matcher", ""),
                        "stage": stage,
                        "sha256": VERSION_RELEASE._canonical_json_sha256(handler),
                    })
        current_before_required.sort(
            key=lambda entry: (
                entry["event"],
                entry["matcher"],
                entry["stage"],
            )
        )
        current_before_asset["merge_validation"] = {
            "format": "codex-hooks-dispatchers-v1",
            "required_handlers": current_before_required,
        }
        current_before_payload = (
            json.dumps(current_before_contract, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        prospective_contract["contract_historical_sha256"]["1.4.2"] = [
            VERSION_RELEASE._sha256_bytes(current_before_payload)
        ]
        prospective_contract_payload = (
            json.dumps(prospective_contract, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        contract_path.write_bytes(current_before_payload)
        stamp_path = repo / ".codex/.bridgeforge_codex_version"
        stamp_path.write_text("1.4.2\n", encoding="utf-8")
        prospective_snapshot = {
            target: prospective,
            ".codex/managed-skeleton.json": prospective_contract_payload,
            ".codex/.bridgeforge_codex_version": b"1.4.3\n",
        }
        item = {
            "id": "G1",
            "asset_id": "codex.hooks-config",
            "target": target,
            "category": "release_transition_review",
            "before_sha256": VERSION_RELEASE._sha256_bytes(before),
            "after_sha256": VERSION_RELEASE._sha256_bytes(prospective),
        }
        before_snapshot = (
            VERSION_RELEASE.freeze_explicit_adaptation_before_snapshot(
                repo,
                prospective_snapshot,
                [item],
            )
        )
        evidence = VERSION_RELEASE.build_explicit_adaptation_evidence(
            repo,
            prospective_snapshot,
            [item],
            before_snapshot,
        )
        self.assertEqual(
            evidence["items"][0]["project_before_sha256"],
            evidence["items"][0]["project_after_sha256"],
        )

        unknown_description = json.loads(current_before.decode("utf-8"))
        unknown_description["description"] = (
            "user-only description not present in product history"
        )
        path.write_text(
            json.dumps(unknown_description, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            VERSION_RELEASE.ReleaseError,
            "managed top-level field",
        ):
            VERSION_RELEASE.build_explicit_adaptation_evidence(
                repo,
                prospective_snapshot,
                [item],
            )
        path.write_bytes(current_before)

        drifted_contract = json.loads(current_before_payload.decode("utf-8"))
        drifted_asset = next(
            asset
            for asset in drifted_contract["assets"]
            if asset["id"] == "codex.hooks-config"
        )
        drifted_required = drifted_asset["merge_validation"]["required_handlers"]
        next(
            entry
            for entry in drifted_required
            if entry["stage"] == "user-prompt"
        )["sha256"] = "sha256:" + "0" * 64
        drifted_asset["merge_validation"][
            "current_projection_sha256"
        ] = VERSION_RELEASE._canonical_json_sha256(drifted_required)
        drifted_contract_payload = (
            json.dumps(drifted_contract, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        prospective_contract["contract_historical_sha256"]["1.4.2"] = [
            VERSION_RELEASE._sha256_bytes(drifted_contract_payload)
        ]
        drifted_prospective_contract = (
            json.dumps(prospective_contract, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        drifted_snapshot = dict(prospective_snapshot)
        drifted_snapshot[
            ".codex/managed-skeleton.json"
        ] = drifted_prospective_contract
        contract_path.write_bytes(drifted_contract_payload)
        with self.assertRaisesRegex(
            VERSION_RELEASE.ReleaseError,
            "managed-looking handler has no trusted ownership",
        ):
            VERSION_RELEASE.build_explicit_adaptation_evidence(
                repo,
                drifted_snapshot,
                [item],
            )
        self.assertEqual(path.read_bytes(), current_before)
        contract_path.write_bytes(current_before_payload)

        drifted_document = json.loads(current_before.decode("utf-8"))
        drifted_document["hooks"]["SessionStart"][0]["hooks"][0][
            "commandWindows"
        ] = "python changed_project_hook.py"
        path.write_text(
            json.dumps(drifted_document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(
            VERSION_RELEASE.ReleaseError,
            "external handlers",
        ):
            VERSION_RELEASE.build_explicit_adaptation_evidence(
                repo,
                prospective_snapshot,
                [item],
            )

        path.write_bytes(prospective)
        contract_path.write_bytes(prospective_contract_payload)
        stamp_path.write_text("1.4.3\n", encoding="utf-8")
        canonical_item = evidence["items"][0]
        aggregate = "sha256:" + "a" * 64
        transition_fingerprint = evidence["transition_fingerprint"]
        encoded_before = (
            VERSION_RELEASE.encode_explicit_adaptation_before_snapshot(
                before_snapshot
            )
        )
        before_fingerprint = (
            VERSION_RELEASE.explicit_adaptation_before_snapshot_fingerprint(
                encoded_before
            )
        )
        selection = VERSION_RELEASE._sha256_bytes(
            VERSION_RELEASE._canonical_json({
                "aggregate_fingerprint": aggregate,
                "transition_fingerprint": transition_fingerprint,
                "before_snapshot_fingerprint": before_fingerprint,
                "selected_adaptation_ids": ["G1"],
                "items": [canonical_item],
            })
        )
        proof = {
            "schema_version": 2,
            "project_root": str(repo.resolve()),
            "head": VERSION_RELEASE._head_commit(repo),
            "contract_target": ".codex/managed-skeleton.json",
            "contract_sha256": VERSION_RELEASE._sha256_bytes(
                prospective_contract_payload
            ),
            "aggregate_fingerprint": aggregate,
            "transition_fingerprint": transition_fingerprint,
            "before_snapshot": encoded_before,
            "before_snapshot_fingerprint": before_fingerprint,
            "selection_fingerprint": selection,
            "items": [canonical_item],
        }
        validated = VERSION_RELEASE._validated_explicit_adaptations(
            repo,
            {},
            proof,
            before_snapshot,
        )
        self.assertEqual(
            set(validated),
            {("codex.hooks-config", target)},
        )

    def test_schema_v1_hooks_require_published_handler_history(self) -> None:
        repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        host = repo / ".codex"
        host.mkdir(parents=True)
        target = ".codex/hooks.json"
        managed_id = "bridgeforge-codex.project-hook.v1:pre-tool"
        published = {
            "type": "command",
            "commandWindows": (
                "python .codex/hooks/hook_dispatcher.py pre-tool"
            ),
        }
        canonical = dict(published)
        canonical["bridgeforgeCodexId"] = managed_id
        attack = dict(canonical)
        attack["commandWindows"] += " --unknown-payload"

        def document(handler: dict[str, object]) -> bytes:
            return (json.dumps({
                "hooks": {
                    "PreToolUse": [{
                        "matcher": "Bash|Edit|Write",
                        "hooks": [handler],
                    }],
                },
            }, indent=2) + "\n").encode("utf-8")

        legacy_contract = {
            "schema_version": 1,
            "stamp": ".codex/.bridgeforge_version",
            "whole_files": [
                ".codex/.bridgeforge_version",
                ".codex/managed-skeleton.json",
                target,
            ],
            "managed_regions": [],
        }
        legacy_payload = (
            json.dumps(legacy_contract, indent=2) + "\n"
        ).encode("utf-8")
        required = [{
            "id": managed_id,
            "event": "PreToolUse",
            "matcher": "Bash|Edit|Write",
            "stage": "pre-tool",
            "sha256": VERSION_RELEASE._canonical_json_sha256(canonical),
        }]
        current_asset = {
            "id": "codex.hooks-config",
            "target": target,
            "strategy": "merge",
            "merge_policy": "codex-hooks",
            "merge_validation": {
                "format": "codex-hooks-zones-v2",
                "required_handlers": required,
                "current_projection_sha256": (
                    VERSION_RELEASE._canonical_json_sha256(required)
                ),
                "historical_handler_sha256": {
                    managed_id: {
                        "0.90.0": [
                            VERSION_RELEASE._handler_without_managed_id_hash(
                                published
                            )
                        ],
                    },
                },
                "managed_top_level": {},
            },
        }
        prospective_contract = {
            "schema_version": 2,
            "release_version": "1.4.24",
            "stamp": ".codex/.bridgeforge_codex_version",
            "contract_target": ".codex/managed-skeleton.json",
            "contract_historical_sha256": {
                "0.90.0": [VERSION_RELEASE._sha256_bytes(legacy_payload)],
            },
            "assets": [current_asset],
        }
        prospective_payload = (
            json.dumps(prospective_contract, indent=2) + "\n"
        ).encode("utf-8")
        contract_path = host / "managed-skeleton.json"
        contract_path.write_bytes(legacy_payload)
        (host / ".bridgeforge_version").write_text(
            "0.90.0\n", encoding="utf-8"
        )
        hooks_path = repo / target
        hooks_path.write_bytes(document(attack))
        snapshot = {
            target: document(canonical),
            ".codex/managed-skeleton.json": prospective_payload,
        }
        before_snapshot = {
            target: hooks_path.read_bytes(),
            ".codex/managed-skeleton.json": legacy_payload,
            ".codex/.bridgeforge_version": b"0.90.0\n",
            ".codex/.bridgeforge_codex_version": None,
        }
        with self.assertRaisesRegex(
            VERSION_RELEASE.ReleaseError,
            "trusted published or current canonical handler",
        ):
            VERSION_RELEASE._trusted_current_before_contract_asset(
                repo,
                contract_path,
                prospective_contract,
                prospective_payload,
                "codex.hooks-config",
                target,
                snapshot,
                before_snapshot,
            )

        hooks_path.write_bytes(document(canonical))
        before_snapshot[target] = hooks_path.read_bytes()
        current_before_asset = (
            VERSION_RELEASE._trusted_current_before_contract_asset(
                repo,
                contract_path,
                prospective_contract,
                prospective_payload,
                "codex.hooks-config",
                target,
                snapshot,
                before_snapshot,
            )
        )

        current_handler = dict(canonical)
        current_handler["commandWindows"] += " --current"
        current_asset_v2 = json.loads(json.dumps(current_asset))
        current_asset_v2["merge_validation"]["required_handlers"][0][
            "sha256"
        ] = VERSION_RELEASE._canonical_json_sha256(current_handler)
        current_asset_v2["merge_validation"][
            "current_projection_sha256"
        ] = VERSION_RELEASE._canonical_json_sha256(
            current_asset_v2["merge_validation"]["required_handlers"]
        )
        current_before_asset_v2 = json.loads(json.dumps(current_asset_v2))
        current_before_asset_v2["_trusted_release_version"] = "1.4.2"
        head_project, current_project = (
            VERSION_RELEASE._adaptation_hooks_project_parts(
                document(published),
                document(current_handler),
                document(current_handler),
                {
                    "id": "codex.hooks-config",
                    "target": target,
                    "strategy": "merge",
                    "merge_validation": {
                        "format": "codex-hooks-dispatchers-v1",
                        "required_handlers": [],
                    },
                },
                current_before_asset_v2,
                current_asset_v2,
                "0.90.0",
                target,
                target,
            )
        )
        self.assertEqual(head_project, current_project)

        contract_path.write_bytes(prospective_payload)
        (host / ".bridgeforge_version").unlink()
        post_apply_snapshot = dict(snapshot)
        post_apply_snapshot[".codex/.bridgeforge_codex_version"] = (
            b"1.4.24\n"
        )
        self.assertEqual(
            VERSION_RELEASE._trusted_current_before_contract_asset(
                repo,
                contract_path,
                prospective_contract,
                prospective_payload,
                "codex.hooks-config",
                target,
                post_apply_snapshot,
                before_snapshot,
            )["_trusted_release_version"],
            "0.90.0",
        )
        contract_path.write_bytes(legacy_payload)
        (host / ".bridgeforge_version").write_text(
            "0.90.0\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(
            VERSION_RELEASE.ReleaseError,
            "HEAD dispatcher does not match",
        ):
            VERSION_RELEASE._adaptation_hooks_project_parts(
                document({
                    key: value
                    for key, value in attack.items()
                    if key != "bridgeforgeCodexId"
                }),
                document(canonical),
                document(canonical),
                {
                    "id": "codex.hooks-config",
                    "target": target,
                    "strategy": "merge",
                    "merge_validation": {
                        "format": "codex-hooks-dispatchers-v1",
                        "required_handlers": [],
                    },
                },
                current_before_asset,
                current_asset,
                "0.90.0",
                target,
                target,
            )

    def test_no_target_retirement_rechecks_lexical_absence(self) -> None:
        repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        with (
            mock.patch.object(
                VERSION_RELEASE,
                "_explicit_adaptation_context",
                return_value=(
                    ".codex/retired.py",
                    None,
                    {"strategy": "whole"},
                    None,
                    "0.90.0",
                    None,
                ),
            ),
            mock.patch.object(
                VERSION_RELEASE,
                "_lexical_entry_exists",
                return_value=True,
            ),
            self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError,
                "lexical directory entry",
            ),
        ):
            VERSION_RELEASE._explicit_adaptation_ownership_evidence(
                repo,
                {},
                "codex.retired.fixture",
                ".codex/retired.py",
                "release_transition_review",
                {("codex.retired.fixture", ".codex/retired.py")},
                True,
            )

    def test_explicit_hooks_adaptation_rejects_ambiguous_legacy_dispatcher(self) -> None:
        repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        init_repo(repo)
        write_contract_transition_fixture(
            repo,
            include_merge_noop_asset=True,
            legacy_merge_without_projection=True,
            duplicate_merge_handler_before_baseline=True,
        )
        target = ".codex/hooks.json"
        before = subprocess.run(
            ["git", "show", f"HEAD:{target}"],
            cwd=repo,
            capture_output=True,
            check=True,
        ).stdout
        path = repo / target
        item = {
            "id": "G1",
            "asset_id": "codex.hooks-config",
            "target": target,
            "category": "release_transition_review",
            "before_sha256": VERSION_RELEASE._sha256_bytes(before),
            "after_sha256": VERSION_RELEASE._sha256_bytes(path.read_bytes()),
        }
        with self.assertRaisesRegex(
            VERSION_RELEASE.ReleaseError,
            "ambiguous legacy dispatcher",
        ):
            VERSION_RELEASE.build_explicit_adaptation_evidence(repo, None, [item])

    def test_compatibility_entrypoints_delegate_to_single_evaluator(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            with mock.patch.object(
                VERSION_RELEASE,
                "evaluate_release_transition",
                return_value=("mixed", {"AGENTS.md"}),
            ) as evaluator:
                self.assertEqual(
                    VERSION_RELEASE.classify_changes(repo, {"AGENTS.md"}),
                    "mixed",
                )
                self.assertEqual(
                    VERSION_RELEASE.preflight_contract_transition(repo),
                    ("mixed", {"AGENTS.md"}),
                )

        self.assertEqual(evaluator.call_count, 2)

    def test_prospective_snapshot_matches_real_transition_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(repo)
            snapshot: dict[str, bytes | None] = {}
            for relative in changed:
                path = repo / relative
                snapshot[relative] = path.read_bytes() if path.is_file() else None
            expected = VERSION_RELEASE.evaluate_release_transition(
                repo,
                changed_paths=changed,
            )

            for relative in changed:
                result = subprocess.run(
                    ["git", "show", f"HEAD:{relative}"],
                    cwd=repo,
                    capture_output=True,
                    check=False,
                )
                path = repo / relative
                if result.returncode == 0:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(result.stdout)
                else:
                    path.unlink(missing_ok=True)
            baseline_status = subprocess.run(
                ["git", "status", "--porcelain=v1"],
                cwd=repo,
                capture_output=True,
                check=True,
            ).stdout

            actual = VERSION_RELEASE.evaluate_release_transition(
                repo,
                snapshot,
                changed_paths=changed,
            )

            self.assertEqual(actual, expected)
            self.assertEqual(
                subprocess.run(
                    ["git", "status", "--porcelain=v1"],
                    cwd=repo,
                    capture_output=True,
                    check=True,
                ).stdout,
                baseline_status,
            )

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

    def test_agents_contract_metadata_can_change_without_rewriting_zoned_target(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(repo)
            head_agents = subprocess.run(
                ["git", "show", "HEAD:AGENTS.md"],
                cwd=repo,
                check=True,
                capture_output=True,
            ).stdout
            contract_path = repo / ".codex/managed-skeleton.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            asset = next(
                item for item in contract["assets"] if item["id"] == "root.agents"
            )
            public, _project = VERSION_RELEASE._agents_zone_release_parts(
                head_agents,
                asset["agents_zones"],
            )
            assert public is not None
            asset["agents_zones"]["public"]["current_sha256"] = (
                VERSION_RELEASE._agents_public_hash(public)
            )
            asset["current_sha256"] = VERSION_RELEASE._sha256_bytes(head_agents)
            contract_path.write_text(json.dumps(contract) + "\n", encoding="utf-8")
            (repo / "AGENTS.md").write_bytes(head_agents)
            changed.discard("AGENTS.md")

            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, changed),
                "skeleton-only",
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

    def test_contract_transition_treats_unzoned_legacy_agents_as_mixed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(
                repo,
                customize_old_agents=True,
                legacy_unzoned_agents=True,
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
            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, changed), "mixed"
            )

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

    def test_contract_transition_accepts_explicit_current_region_adaptation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(
                repo,
                include_region_asset=True,
            )

            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, changed),
                "mixed",
            )
            snapshot = {
                relative: (repo / relative).read_bytes()
                if (repo / relative).is_file()
                else None
                for relative in changed
            }
            for relative in changed:
                path = repo / relative
                head_payload = VERSION_RELEASE._head_bytes(repo, relative)
                if head_payload is None:
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(head_payload)
            prospective, _paths = VERSION_RELEASE.evaluate_release_transition(
                repo,
                snapshot=snapshot,
                prospective_version="1.4.3",
                changed_paths=set(),
            )
            self.assertEqual(prospective, "mixed")
            for relative, payload in snapshot.items():
                path = repo / relative
                if payload is None:
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(payload)
            precommit = repo / ".githooks/pre-commit"
            precommit.write_bytes(
                precommit.read_bytes().replace(b"exit 0", b"exit 2")
            )
            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, changed),
                "mixed",
            )

        for old_region_mode in ("missing-end", "duplicate"):
            with self.subTest(old_region_mode=old_region_mode), \
                    tempfile.TemporaryDirectory() as raw:
                repo = Path(raw)
                init_repo(repo)
                changed = write_contract_transition_fixture(
                    repo,
                    include_region_asset=True,
                    old_region_mode=old_region_mode,
                )
                self.assertEqual(
                    VERSION_RELEASE.classify_changes(repo, changed),
                    "mixed",
                )

        for old_region_mode in (
            "current-missing-end",
            "current-duplicate",
            "current-reversed",
            "current-drift",
        ):
            with self.subTest(old_region_mode=old_region_mode), \
                    tempfile.TemporaryDirectory() as raw:
                repo = Path(raw)
                init_repo(repo)
                changed = write_contract_transition_fixture(
                    repo,
                    include_region_asset=True,
                    old_region_mode=old_region_mode,
                )
                with self.assertRaises(VERSION_RELEASE.TransitionBlocked) as captured:
                    VERSION_RELEASE.classify_changes(repo, changed)
                self.assertIn("managed region", captured.exception.issues[0]["reason"])

    def test_current_region_drift_is_blocked_without_contract_transition(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(
                repo,
                include_region_asset=True,
            )
            git(repo, "add", *sorted(changed))
            git(repo, "commit", "-m", "current region baseline")
            precommit = repo / ".githooks/pre-commit"
            precommit.write_bytes(
                precommit.read_bytes().replace(b"new managed", b"tampered managed")
            )
            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError,
                "current managed region does not match its declared hash",
            ):
                VERSION_RELEASE.classify_changes(repo, {".githooks/pre-commit"})

    def test_current_region_contract_rejects_historical_rules(self) -> None:
        for location in ("asset", "region"):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as raw:
                repo = Path(raw)
                init_repo(repo)
                changed = write_contract_transition_fixture(
                    repo,
                    include_region_asset=True,
                )
                contract_path = repo / ".codex/managed-skeleton.json"
                contract = json.loads(contract_path.read_text(encoding="utf-8"))
                precommit_asset = next(
                    asset
                    for asset in contract["assets"]
                    if asset["id"] == "codex.precommit"
                )
                owner = precommit_asset if location == "asset" else precommit_asset["region"]
                owner["historical_sha256"] = {"0.94.2": ["sha256:" + "0" * 64]}
                contract_path.write_text(json.dumps(contract) + "\n", encoding="utf-8")
                with self.assertRaisesRegex(
                    VERSION_RELEASE.ReleaseError,
                    "invalid schema v2 managed region",
                ):
                    VERSION_RELEASE.classify_changes(repo, changed)

    def test_schema_v1_transition_accepts_current_region_adaptation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed, _contract, project_extra = write_schema_v1_transition_fixture(repo)

            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, changed),
                "mixed",
            )
            project_extra.write_text("project changed\n", encoding="utf-8")
            self.assertEqual(
                VERSION_RELEASE.classify_changes(
                    repo,
                    changed | {".codex/hooks/project_extra.py"},
                ),
                "mixed",
            )

        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed, _contract, _project_extra = write_schema_v1_transition_fixture(
                repo,
                omit_legacy_region=True,
            )
            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, changed),
                "mixed",
            )

    def test_schema_v1_transition_rejects_untrusted_or_unsupported_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed, contract_path, _project_extra = write_schema_v1_transition_fixture(
                repo
            )
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            contract["contract_historical_sha256"]["0.90.0"] = ["sha256:" + "0" * 64]
            contract_path.write_text(json.dumps(contract) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError,
                "is not trusted for skeleton 0.90.0",
            ):
                VERSION_RELEASE.classify_changes(repo, changed)

        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed, _contract, _project_extra = write_schema_v1_transition_fixture(
                repo,
                minimum_supported_version="0.91.0",
            )
            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError,
                "below minimum supported 0.91.0",
            ):
                VERSION_RELEASE.classify_changes(repo, changed)

    def test_schema_v1_transition_rejects_unowned_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed, _contract, _project_extra = write_schema_v1_transition_fixture(
                repo,
                claim_unowned_existing=True,
            )
            with self.assertRaises(VERSION_RELEASE.TransitionBlocked) as captured:
                VERSION_RELEASE.classify_changes(repo, changed)
            self.assertEqual(captured.exception.issues[0]["asset_id"], "codex.unowned")
            self.assertIn("not trusted for schema v1 baseline", captured.exception.issues[0]["reason"])

    def test_schema_v1_transition_rejects_nested_hash_from_other_version(self) -> None:
        for strategy in ("managed-markdown",):
            with self.subTest(strategy=strategy), tempfile.TemporaryDirectory() as raw:
                repo = Path(raw)
                init_repo(repo)
                changed = write_schema_v1_nested_history_fixture(repo, strategy)

                with self.assertRaises(VERSION_RELEASE.TransitionBlocked) as captured:
                    VERSION_RELEASE.classify_changes(repo, changed)

                self.assertIn(
                    "does not match trusted",
                    captured.exception.issues[0]["reason"],
                )

    def test_schema_v1_prospective_and_real_evaluators_are_equivalent(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed, _contract, _project_extra = write_schema_v1_transition_fixture(repo)
            snapshot = {
                relative: (repo / relative).read_bytes()
                if (repo / relative).is_file()
                else None
                for relative in changed
            }

            for relative in changed:
                path = repo / relative
                head_payload = VERSION_RELEASE._head_bytes(repo, relative)
                if head_payload is None:
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(head_payload)
            prospective = VERSION_RELEASE.evaluate_release_transition(
                repo,
                snapshot=snapshot,
                prospective_version="1.4.16",
                changed_paths=set(),
            )

            for relative, payload in snapshot.items():
                path = repo / relative
                if payload is None:
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(payload)
            real = VERSION_RELEASE.evaluate_release_transition(
                repo,
                changed_paths=changed,
            )

            self.assertEqual(prospective, real)

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

    def test_contract_transition_accepts_verified_hooks_zones_adaptation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(
                repo,
                include_merge_noop_asset=True,
            )

            self.assertIn(".codex/hooks.json", changed)
            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, changed),
                "skeleton-only",
            )
            hooks = json.loads(
                (repo / ".codex/hooks.json").read_text(encoding="utf-8")
            )
            commands = [
                handler
                for group in hooks["hooks"]["PreToolUse"]
                for handler in group["hooks"]
            ]
            self.assertTrue(any("project_hook.py" in item["commandWindows"] for item in commands))
            managed = [
                item for item in commands if item.get("bridgeforgeCodexId")
            ]
            self.assertEqual(len(managed), 1)

    def test_current_hooks_contract_uses_canonical_handler_order(self) -> None:
        contract = json.loads(
            (ROOT / "templates/managed-skeleton.json").read_text(encoding="utf-8")
        )
        asset = next(
            item for item in contract["assets"] if item["id"] == "codex.hooks-config"
        )
        payload = (ROOT / "templates/hooks.json").read_bytes()

        actual, _external = VERSION_RELEASE._current_codex_hooks_zones_parts(
            payload,
            asset,
            ".codex/hooks.json",
        )

        self.assertGreater(len(actual), 1)
        self.assertEqual(actual, asset["merge_validation"]["required_handlers"])

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
                "no trusted ownership",
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
                "missing a trusted managed handler",
            ):
                VERSION_RELEASE.classify_changes(repo, changed)

    def test_contract_transition_accepts_trusted_duplicate_head_merge_handler(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(
                repo,
                include_merge_noop_asset=True,
                duplicate_merge_handler_before_baseline=True,
            )
            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, changed),
                "skeleton-only",
            )

    def test_contract_transition_accepts_exact_legacy_whole_hooks_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(
                repo,
                include_merge_noop_asset=True,
                legacy_merge_without_projection=True,
                include_project_merge_handler=False,
            )

            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, changed),
                "skeleton-only",
            )

    def test_contract_transition_rejects_drifted_legacy_whole_hooks_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(
                repo,
                include_merge_noop_asset=True,
                legacy_merge_without_projection=True,
                include_project_merge_handler=False,
                drift_merge_target_before_baseline=True,
            )

            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError,
                "no trusted managed projection",
            ):
                VERSION_RELEASE.classify_changes(repo, changed)

    def test_contract_transition_changed_merge_uses_managed_projection(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            changed = write_contract_transition_fixture(
                repo,
                include_merge_noop_asset=True,
            )
            hooks_path = repo / ".codex/hooks.json"
            hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
            handlers = [
                handler
                for group in hooks["hooks"]["PreToolUse"]
                for handler in group["hooks"]
            ]
            managed_handler = next(
                item for item in handlers if "hook_dispatcher.py" in item["commandWindows"]
            )
            managed_handler["comment"] = "upgraded managed dispatcher"
            hooks_path.write_text(
                json.dumps(hooks, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            contract_path = repo / ".codex/managed-skeleton.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            asset = next(
                item for item in contract["assets"]
                if item["id"] == "codex.hooks-config"
            )
            required = [{
                "id": managed_handler["bridgeforgeCodexId"],
                "event": "PreToolUse",
                "matcher": "Bash|Edit|Write",
                "stage": "pre-tool",
                "sha256": VERSION_RELEASE._canonical_json_sha256(managed_handler),
            }]
            asset["merge_validation"]["required_handlers"] = required
            asset["merge_validation"]["current_projection_sha256"] = (
                VERSION_RELEASE._canonical_json_sha256(required)
            )
            contract_path.write_text(
                json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            changed.add(".codex/hooks.json")

            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, changed),
                "skeleton-only",
            )
            project_handler = next(
                item for item in handlers if "project_hook.py" in item["commandWindows"]
            )
            project_handler["commandWindows"] = "python project_hook_v2.py"
            hooks_path.write_text(
                json.dumps(hooks, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, changed),
                "mixed",
            )

    def test_contract_transition_managed_markdown_preserves_project_content(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            init_repo(repo)
            host = repo / ".codex"
            host.mkdir(parents=True)
            managed_blocks = {
                "format": "markdown-headings",
                "headings": ["## Managed"],
                "additive_headings": [],
                "keyed_tables": [],
            }
            old_doc = b"# Doc\n\n## Managed\n\nold managed\n\n## Project\n\nlocal\n"
            old_managed, _old_project = VERSION_RELEASE._managed_markdown_parts(
                old_doc,
                ["## Managed"],
                [],
                [],
            )
            old_projection = VERSION_RELEASE._sha256_bytes(old_managed or b"")
            old_asset = {
                "id": "codex.doc.readme",
                "target": "doc/README.md",
                "strategy": "whole",
                "current_sha256": VERSION_RELEASE._sha256_bytes(old_doc),
                "managed_blocks": dict(managed_blocks),
            }
            old_contract = {
                "schema_version": 2,
                "stamp": ".codex/.bridgeforge_codex_version",
                "contract_target": ".codex/managed-skeleton.json",
                "assets": [old_asset],
            }
            old_payload = (json.dumps(old_contract, indent=2) + "\n").encode("utf-8")
            (host / "managed-skeleton.json").write_bytes(old_payload)
            (host / ".bridgeforge_codex_version").write_text("1.4.11\n")
            (repo / "doc").mkdir()
            (repo / "doc/README.md").write_bytes(old_doc)
            (repo / "VERSION").write_text("3.0.0\n")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "baseline")

            current_doc = old_doc.replace(b"old managed", b"new managed")
            current_managed, _current_project = VERSION_RELEASE._managed_markdown_parts(
                current_doc,
                ["## Managed"],
                [],
                [],
            )
            current_blocks = dict(managed_blocks)
            current_blocks["current_projection_sha256"] = (
                VERSION_RELEASE._sha256_bytes(current_managed or b"")
            )
            current_blocks["historical_projection_sha256"] = {
                "1.4.11": [old_projection],
            }
            current_asset = {
                "id": "codex.doc.readme",
                "target": "doc/README.md",
                "strategy": "whole",
                "current_sha256": VERSION_RELEASE._sha256_bytes(current_doc),
                "managed_blocks": current_blocks,
            }
            current_contract = {
                "schema_version": 2,
                "release_version": "1.4.12",
                "stamp": ".codex/.bridgeforge_codex_version",
                "contract_target": ".codex/managed-skeleton.json",
                "contract_historical_sha256": {
                    "1.4.11": [VERSION_RELEASE._sha256_bytes(old_payload)],
                },
                "assets": [current_asset],
            }
            (host / "managed-skeleton.json").write_text(
                json.dumps(current_contract, indent=2) + "\n"
            )
            (host / ".bridgeforge_codex_version").write_text("1.4.12\n")
            (repo / "doc/README.md").write_bytes(current_doc)
            changed = {
                ".codex/managed-skeleton.json",
                ".codex/.bridgeforge_codex_version",
                "doc/README.md",
            }
            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, changed),
                "skeleton-only",
            )

            (repo / "doc/README.md").write_bytes(
                current_doc.replace(b"local", b"local changed")
            )
            self.assertEqual(
                VERSION_RELEASE.classify_changes(repo, changed),
                "mixed",
            )
            (repo / "doc/README.md").write_bytes(
                current_doc.replace(b"new managed", b"drifted")
            )
            with self.assertRaisesRegex(
                VERSION_RELEASE.TransitionBlocked,
                "current managed Markdown does not match",
            ) as captured:
                VERSION_RELEASE.classify_changes(repo, changed)
            self.assertEqual(captured.exception.issues[0]["asset_id"], "codex.doc.readme")
            self.assertEqual(captured.exception.issues[0]["target"], "doc/README.md")

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

    def test_legacy_managed_region_without_current_hash_is_rejected(self) -> None:
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
            with self.assertRaisesRegex(
                VERSION_RELEASE.ReleaseError,
                "invalid managed region",
            ):
                VERSION_RELEASE.build_release_plan(
                    repo,
                    "fix: 旧 region contract 必须显式适配",
                    {".githooks/pre-commit"},
                )


if __name__ == "__main__":
    unittest.main()
