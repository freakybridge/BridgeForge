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
HOOK = ROOT / "templates" / "hooks" / "instruction_source_check.py"
SYNC_PATH = ROOT / "scripts" / "bridgeforge_codex_project_sync.py"

def load_hook():
    spec = importlib.util.spec_from_file_location("instruction_source_check", HOOK)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_sync():
    spec = importlib.util.spec_from_file_location("rule_runtime_sync", SYNC_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class InstructionSourceCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.hook = load_hook()

    def _zoned_project(self, root: Path) -> Path:
        target = root / "AGENTS.md"
        target.write_text(
            (ROOT / "templates/AGENTS.md").read_text(encoding="utf-8").replace(
                "{{PROJECT_NAME}}", root.name
            ),
            encoding="utf-8",
        )
        contract = root / ".codex" / "managed-skeleton.json"
        contract.parent.mkdir(parents=True)
        shutil.copy2(ROOT / "templates/managed-skeleton.json", contract)
        return target

    def test_project_zone_edit_is_allowed_but_public_or_marker_edit_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents = self._zoned_project(root)
            self.assertEqual(self.hook.instruction_source_issues(root), [])
            baseline = agents.read_text(encoding="utf-8")
            agents.write_text(
                baseline.replace(
                    "### 项目业务与安全红线",
                    "### 项目业务与安全红线\n\n- 项目订单必须经过本地风控。",
                ),
                encoding="utf-8",
            )
            self.assertEqual(self.hook.instruction_source_issues(root), [])
            agents.write_text(
                baseline.replace("默认先给结论", "默认最后给结论", 1),
                encoding="utf-8",
            )
            issues = self.hook.instruction_source_issues(root)
            self.assertTrue(any("public zone was modified" in item for item in issues))
            agents.write_text(
                baseline.replace("<!-- BRIDGEFORGE:PROJECT:END -->", "", 1),
                encoding="utf-8",
            )
            issues = self.hook.instruction_source_issues(root)
            self.assertTrue(any("exactly once" in item for item in issues))

    def test_project_zone_allows_fenced_heading_examples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents = self._zoned_project(root)
            baseline = agents.read_text(encoding="utf-8")
            agents.write_text(
                baseline.replace(
                    "### 项目业务与安全红线",
                    "### 项目业务与安全红线\n\n"
                    "```markdown\n### 项目架构红线\n- 示例，不是结构标题。\n```",
                ),
                encoding="utf-8",
            )
            self.assertEqual(self.hook.instruction_source_issues(root), [])

    def test_zoned_agents_fail_closed_when_contract_is_missing_or_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._zoned_project(root)
            contract = root / ".codex" / "managed-skeleton.json"
            contract.unlink()
            issues = self.hook.instruction_source_issues(root)
            self.assertTrue(any("cannot be verified" in item for item in issues))

            contract.write_text("{invalid", encoding="utf-8")
            issues = self.hook.instruction_source_issues(root)
            self.assertTrue(any("cannot be verified" in item for item in issues))

    def test_staged_public_edit_is_detected_after_worktree_restore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents = self._zoned_project(root)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "add", "AGENTS.md", ".codex/managed-skeleton.json"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "baseline"], cwd=root, check=True, capture_output=True)
            baseline = agents.read_bytes()
            agents.write_bytes(baseline.replace("默认先给结论".encode(), "默认最后给结论".encode()))
            subprocess.run(["git", "add", "AGENTS.md"], cwd=root, check=True)
            agents.write_bytes(baseline)
            staged = self.hook._git_agents(root, "INDEX")
            self.assertIsNotNone(staged)
            issues = self.hook._root_agents_issues(
                staged, root, label="staged AGENTS.md"
            )
            self.assertTrue(any("public zone was modified" in item for item in issues))

    def test_unchanged_staged_agents_does_not_block_unrelated_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._zoned_project(root)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "add", "AGENTS.md"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "baseline"], cwd=root, check=True, capture_output=True)
            (root / "business.txt").write_text("changed\n", encoding="utf-8")
            subprocess.run(["git", "add", "business.txt"], cwd=root, check=True)
            self.assertEqual(self.hook._staged_agents_issues(root), [])

    def test_factory_rejects_markdown_rule_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "templates" / "rules").mkdir(parents=True)
            (root / "templates" / "rules" / "legacy.md").write_text("---\npaths: ['src/**']\n---\n", encoding="utf-8")
            self._zoned_project(root)
            (root / "templates" / "AGENTS.md").write_bytes(
                (ROOT / "templates" / "AGENTS.md").read_bytes()
            )
            issues = self.hook.instruction_source_issues(root)
            self.assertTrue(any("must remain retired" in item for item in issues), issues)

    def test_negative_autoload_statement_and_runtime_fixture_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agents = self._zoned_project(root)
            agents.write_text(
                agents.read_text(encoding="utf-8")
                .replace("<!-- BRIDGEFORGE:PROJECT:END -->", "Markdown 中的 paths: 不会被 Codex 自动加载。\n<!-- BRIDGEFORGE:PROJECT:END -->"),
                encoding="utf-8",
            )
            runtime_agents = root / ".runtime" / "historical" / "AGENTS.md"
            runtime_agents.parent.mkdir(parents=True)
            runtime_agents.write_text(
                "Markdown paths: 自动加载历史夹具。\n",
                encoding="utf-8",
            )
            self.assertEqual(self.hook.instruction_source_issues(root), [])

            normal_nested = root / "src" / "AGENTS.md"
            comma_nested = root / "lib" / "AGENTS.md"
            for nested, separator in (
                (normal_nested, "；"),
                (comma_nested, "，但"),
            ):
                nested.parent.mkdir(parents=True)
                nested.write_text(
                    f"Codex 不支持 Markdown paths{separator}BridgeForge 会自动加载 Markdown paths: rules。\n",
                    encoding="utf-8",
                )
            issues = self.hook.instruction_source_issues(root)
            self.assertTrue(any("src\\AGENTS.md" in item or "src/AGENTS.md" in item for item in issues))
            self.assertTrue(any("lib\\AGENTS.md" in item or "lib/AGENTS.md" in item for item in issues))

    def test_dispatcher_and_precommit_register_new_gate(self) -> None:
        for dispatcher in (
            ROOT / "templates" / "hooks" / "hook_dispatcher.py",
            ROOT / ".codex" / "hooks" / "hook_dispatcher.py",
        ):
            text = dispatcher.read_text(encoding="utf-8")
            self.assertIn('"hooks/instruction_source_check.py"', text)
        for precommit in (ROOT / "templates" / ".githooks" / "pre-commit", ROOT / ".githooks" / "pre-commit"):
            self.assertIn("instruction_source_check.py", precommit.read_text(encoding="utf-8"))

    def test_precommit_region_uses_only_the_current_ownership_rule(self) -> None:
        sync_source = SYNC_PATH.read_text(encoding="utf-8")
        builder_source = (
            ROOT / "scripts" / "rebuild_shared_skill_manifest.py"
        ).read_text(encoding="utf-8")
        release_source = (
            ROOT / "templates" / "scripts" / "version_release.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("BRIDGEFORGE_MANAGED_BEGIN", sync_source)
        self.assertNotIn("_merge_region_history", builder_source)
        self.assertNotIn("schema v1 managed region", release_source)

    def test_agents_contract_has_no_historical_ownership_path(self) -> None:
        sync = load_sync()
        contract = json.loads((ROOT / "templates" / "managed-skeleton.json").read_text(encoding="utf-8"))
        asset = next(item for item in contract["assets"] if item["id"] == "root.agents")
        self.assertEqual(set(asset).intersection({"managed_blocks", "section_layout"}), set())
        self.assertNotIn(
            "legacy_section_migrations",
            asset["agents_zones"]["project"],
        )
        self.assertFalse(hasattr(sync, "_legacy_agents_source"))


if __name__ == "__main__":
    unittest.main()
