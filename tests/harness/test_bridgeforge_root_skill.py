#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class BridgeForgeRootSkillTests(unittest.TestCase):
    def test_agent_specific_skill_dir_is_set_before_command_dir(self) -> None:
        text = (ROOT / "skills" / "bridgeforge" / "SKILL.md").read_text(encoding="utf-8")
        for user_dir in (".claude\\skills", ".codex\\skills"):
            start = text.index(
                f'$USER_SKILLS_DIR = Join-Path $env:USERPROFILE "{user_dir}"'
            )
            command = text.index(
                "$BRIDGEFORGE_COMMAND_DIR = Join-Path $USER_SKILLS_DIR \"bridgeforge\"",
                start,
            )
            self.assertLess(start, command)

    def test_codex_product_inventory_is_covered_by_init_and_update(self) -> None:
        init = (ROOT / "skills" / "bridgeforge" / "references" / "init.md").read_text(encoding="utf-8")
        update = (ROOT / "skills" / "bridgeforge" / "references" / "update.md").read_text(encoding="utf-8")
        for marker in (
            "config.toml",
            "agents/*.toml",
            "skill-routing.json",
            ".githooks/pre-commit",
        ):
            self.assertIn(marker, init)
            self.assertIn(marker, update)

    def test_codex_platform_default_policy_is_main_dialog_and_all_modes(self) -> None:
        skill = (ROOT / "skills" / "bridgeforge" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Codex 平台默认调度", skill)
        self.assertIn("不再创建、读取或修改项目级模型、reasoning effort 或订阅档位配置", skill)
        self.assertNotIn("subscription_routing.py", skill)
        self.assertIn("Claude 跳过本节。", skill)
        for name in ("init.md", "adopt.md", "update.md"):
            text = (ROOT / "skills" / "bridgeforge" / "references" / name).read_text(encoding="utf-8")
            self.assertNotIn("subscription-tier.toml", text)

    def test_progressive_references_are_one_level_and_live(self) -> None:
        expected = {"switch.md", "user-skill-maintenance.md", "init.md", "adopt.md", "update.md"}
        references = ROOT / "skills" / "bridgeforge" / "references"
        self.assertEqual({path.name for path in references.glob("*.md")}, expected)
        self.assertFalse(any(path.is_dir() for path in references.iterdir()))


if __name__ == "__main__":
    unittest.main()
