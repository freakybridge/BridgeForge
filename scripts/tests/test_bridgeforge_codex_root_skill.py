from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/bridgeforge-codex/SKILL.md"
REFERENCES = ROOT / "skills/bridgeforge-codex/references"


class BridgeForgeCodexRootSkillTests(unittest.TestCase):
    def test_only_new_codex_entry_is_active(self) -> None:
        self.assertTrue(SKILL.is_file())
        self.assertFalse((ROOT / "skills/bridgeforge").exists())
        self.assertFalse((ROOT / "templates/claude").exists())
        self.assertFalse((ROOT / "CLAUDE.md").exists())
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("name: bridgeforge-codex", text)
        self.assertIn("Codex-only", text)
        self.assertIn('".bridgeforge-codex"', text)
        self.assertIn("只是 Codex 可发现的薄入口", text)
        self.assertIn("scripts/bridgeforge_codex_project_sync.py", text)

    def test_legacy_entry_is_an_install_only_bridge(self) -> None:
        text = (ROOT / "scripts/bridgeforge_codex_legacy_entry.SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("只用于旧入口兼容", text)
        self.assertIn("已发布旧 updater 已完成兼容 manifest 事务", text)
        self.assertIn("bridgeforge-codex", text)
        self.assertIn("立即停止", text)
        self.assertNotIn("project_sync", text)

    def test_one_risk_card_and_project_sync_contract_are_explicit(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        for marker in (
            "用户级迁移、native memories、`.agents` 布局迁移、版本戳迁移、上游 absorption 和其他项目 risk 汇总成一张清单",
            "整轮最多确认一次",
            "bridgeforge_codex_user_migrate.py",
            "plan-fingerprint",
            "A：执行全部推荐项",
            "B：只执行用户列出的 ID",
            "C：不再执行风险动作",
            ".codex/.bridgeforge_codex_version",
            ".codex/.bridgeforge_version",
        ):
            self.assertIn(marker, text)

    def test_python_preflight_native_memory_and_layout_are_in_one_orchestration(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        preflight = text.index("## 2. Python preflight")
        user_migration = text.index("$USER_MIGRATION = & $HOOK_PYTHON")
        native_memory = text.index("codex_memory_sync.py", user_migration)
        layout = text.index("bridgeforge_codex_migrate_layout.py", native_memory)
        project_sync = text.index("bridgeforge_codex_project_sync.py", user_migration + 1)
        self.assertLess(preflight, user_migration)
        self.assertLess(user_migration, native_memory)
        self.assertLess(native_memory, layout)
        self.assertLess(layout, project_sync)
        self.assertNotIn("\npython ", text)
        self.assertIn("本轮统一 safe/risk/gap accumulator", text)

    def test_references_are_codex_only_and_have_no_switch(self) -> None:
        expected = {"user-skill-maintenance.md", "init.md", "adopt.md", "update.md"}
        self.assertEqual({path.name for path in REFERENCES.glob("*.md")}, expected)
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in sorted(REFERENCES.glob("*.md"))
        )
        self.assertIn("bridgeforge_codex_project_sync.py", combined)
        self.assertNotIn("bridgeforge_switch.py", combined)
        self.assertNotIn("project_finalize", combined)
        self.assertNotIn("bridgeforge_codex_user_maintenance.ps1", combined)

    def test_shared_skills_inherit_session_model(self) -> None:
        skill_files = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertGreaterEqual(len(skill_files), 15)
        for path in skill_files:
            with self.subTest(path=path):
                frontmatter = path.read_text(encoding="utf-8").split("---", 2)[1]
                self.assertNotRegex(frontmatter, r"(?m)^model\s*:")


if __name__ == "__main__":
    unittest.main()
