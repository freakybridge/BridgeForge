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

OLD_RULE_INDEX = """### 2.1 规则文件索引

| 规则文件 | 内容 | 加载条件 |
|---------|------|---------|
| `rules/architecture.md` | 职责边界 + 数据流方向（核心红线） | 始终加载 |
| `rules/modules.md` | 模块组织范式 + 目录职责 + 新模块接入流程 | 始终加载 |
| `rules/anti_fabrication.md` | 防 AI 幻觉资源四层红线 R1-R5（用前必验 / 缺了直说 / 禁编造 / 禁甩锅 / 先认再改） | 始终加载 |
| `rules/debugging.md` | 调试检查项 + 鬼打墙红线 + 修 bug 前确认根因 | 编辑 `scripts/tests/**` 或核心代码目录 |
| `rules/workflow.md` | 范式同步文档 + 文档索引同步 + 经验总结 | 编辑 `doc/**`、`.codex/rules/**` |
| `rules/portability.md` | 换机可移植性 + 包安装陷阱 + hooks 路径约束 | 编辑 `.codex/**`、配置文件、依赖清单 |
| `rules/meta_rule_design.md` | 元规则：怎么写 rule（强制力梯度 + 加载策略 + 反模式速查） | 编辑 `.codex/rules/**` 或 `AGENTS.md` |
| `rules/anti_drift_hooks.md` | clarify / focus 的职责、路径、调参与豁免 | 编辑 `.codex/hooks/**`、`.codex/hooks.json` |

<!-- 按需追加项目特定 path-rule，如 `rules/<topic>.md`（按 `src/<topic>/**` 触发）。 -->"""


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

    def _agents(self) -> str:
        return "\n".join((
            "# Demo", "### 1.1 架构红线", "- 必须填写。",
            "### 1.3 工具与证据红线", "- 必须验证。",
            "### 2.1 原生指令承载索引", "- AGENTS。",
            "### 2.3 文档管理", "- 必须索引。", "## 3 项目目录地图",
            "- src", "### 4.2 快速命令", "- test", "### 5.2 鬼打墙觉察与渐进升级",
            "- 必须停止。", "",
        ))

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

    def test_legacy_agents_pass_but_zoned_legacy_index_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text(self._agents(), encoding="utf-8")
            self.assertEqual(self.hook.instruction_source_issues(root), [])
            agents = self._zoned_project(root)
            agents.write_text(
                agents.read_text(encoding="utf-8").replace(
                    "<!-- BRIDGEFORGE:PUBLIC:END -->",
                    "### 2.1 规则文件索引\n\n<!-- BRIDGEFORGE:PUBLIC:END -->",
                ),
                encoding="utf-8",
            )
            issues = self.hook.instruction_source_issues(root)
            self.assertTrue(any("rule index" in item for item in issues))

    def test_unmigrated_legacy_agents_remain_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text(
                "# Legacy project\n\n### 2.1 规则文件索引\n\n"
                "BridgeForge 会自动加载 Markdown paths: rules。\n",
                encoding="utf-8",
            )
            self.assertEqual(self.hook.instruction_source_issues(root), [])

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
                staged, root, label="staged AGENTS.md", baseline_has_zones=True
            )
            self.assertTrue(any("public zone was modified" in item for item in issues))

    def test_unchanged_staged_agents_does_not_block_unrelated_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text(
                "# Legacy customized project\n\n### 2.1 规则文件索引\n",
                encoding="utf-8",
            )
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
            (root / "AGENTS.md").write_text(self._agents(), encoding="utf-8")
            (root / "templates" / "AGENTS.md").write_text(self._agents(), encoding="utf-8")
            issues = self.hook.instruction_source_issues(root)
            self.assertTrue(any("must remain retired" in item for item in issues))

    def test_negative_autoload_statement_and_runtime_fixture_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text(
                self._agents() + "\nMarkdown 中的 paths: 不会被 Codex 自动加载。\n",
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

    def test_legacy_rule_hooks_delegate_to_native_gate(self) -> None:
        for host in (ROOT / "templates" / "hooks", ROOT / ".codex" / "hooks"):
            for name in ("rule_index_check.py", "rule_size_check.py"):
                text = (host / name).read_text(encoding="utf-8")
                tail = text.split("def main()", 1)[1]
                self.assertIn(
                    "from instruction_source_check import main as instruction_source_main",
                    text,
                )
                self.assertIn("return instruction_source_main()", tail)

    def test_rule_assets_are_retired_with_1_0_lineage_and_manual_targets(self) -> None:
        contract = json.loads((ROOT / "templates" / "managed-skeleton.json").read_text(encoding="utf-8"))
        rules = [item for item in contract["assets"] if item["id"].startswith("codex.rule.")]
        self.assertEqual(len(rules), 8)
        expected_1_0 = {
            "codex.rule.anti-drift-hooks": "sha256:555ac57a3ac58bf9960a1a543438959fa983fde6c4b66e505f8a9ec61ced10a1",
            "codex.rule.anti-fabrication": "sha256:ed04c396c1ba1340c67b7499c02545ca9529f086bd5594fff422a549bce9f5b3",
            "codex.rule.architecture": "sha256:d40e0fe58bef536f0786c96f6179cb55d206b74550fda701cc2ca06b400c9892",
            "codex.rule.debugging": "sha256:f64fbbdeb858730c1fd701491909c1e196d458d0aab97f2078246bee6de9f639",
            "codex.rule.meta-rule-design": "sha256:df2f777ce0216910c1362987de8b9c36227d4abd1036d8b016c2714974035925",
            "codex.rule.modules": "sha256:1b2a382deb8b5b333e7c72c7c882b139192ca9025a499694aa0d0f237d2fc6b0",
            "codex.rule.portability": [
                "sha256:62067905c2fcb25e6ff38266cc9341cd77ed700ba957008e968c34626dfcccc4",
                "sha256:70c741475267f630e6a6f6628a5bca71ee471b81cd52ba74e9ec5e7564beb9c9",
            ],
            "codex.rule.workflow": "sha256:6da716e1853bb65c3f5bebe284779706a154935ae2627833e81125c71aaec43d",
        }
        for asset in rules:
            self.assertEqual(asset["strategy"], "retirement")
            self.assertNotIn("source", asset)
            self.assertNotIn("current_sha256", asset)
            self.assertIn("1.0.0", asset["historical_sha256"])
            expected_hashes = expected_1_0[asset["id"]]
            if isinstance(expected_hashes, str):
                expected_hashes = [expected_hashes]
            self.assertEqual(asset["historical_sha256"]["1.0.0"], expected_hashes)
        sync = load_sync()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / ".codex" / "rules" / "architecture.md"
            target.parent.mkdir(parents=True)
            target.write_text("project-custom rule\n", encoding="utf-8")
            architecture = next(item for item in rules if item["id"] == "codex.rule.architecture")
            actions, gaps = sync._plan_retirement(architecture, target, root)
            self.assertEqual(actions, [])
            self.assertIn("AGENTS.md project zone", gaps[0].reason)
            self.assertEqual(target.read_text(encoding="utf-8"), "project-custom rule\n")

    def test_agents_contract_has_no_legacy_title_migration_path(self) -> None:
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
