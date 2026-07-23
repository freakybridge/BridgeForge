#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class BridgeForgeRootSkillTests(unittest.TestCase):
    def test_agent_specific_skill_dir_is_set_before_command_dir(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for user_dir in ("$HOME/.claude/skills", "$HOME/.agents/skills"):
            start = text.index(f'USER_SKILLS_DIR="{user_dir}"')
            command = text.index('BRIDGEFORGE_COMMAND_DIR="$USER_SKILLS_DIR/bridgeforge"', start)
            self.assertLess(start, command)

    def test_codex_product_inventory_is_covered_by_init_and_update(self) -> None:
        init = (ROOT / "references" / "init.md").read_text(encoding="utf-8")
        update = (ROOT / "references" / "update.md").read_text(encoding="utf-8")
        for marker in (
            "subscription-tier.toml",
            "config.toml",
            "agents/*.toml",
            "skill-routing.json",
            ".githooks/pre-commit",
        ):
            self.assertIn(marker, init)
            self.assertIn(marker, update)

    def test_codex_subscription_routing_is_main_dialog_and_all_modes(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("templates/codex/scripts/subscription_routing.py", skill)
        self.assertIn(
            "标记存在且 `tier` 为 `high` 或 `conservative`：沿用，不重复询问。",
            skill,
        )
        self.assertIn("标记缺失：必须由主对话询问一次。", skill)
        self.assertIn(
            "100 美元及以下、100–200 美元之间或无法判定都选 `conservative`。",
            skill,
        )
        self.assertIn(
            "标记存在时，只有用户主动要求切换档位才允许改写。",
            skill,
        )
        self.assertIn("Claude 跳过本节。", skill)
        for name in ("init.md", "adopt.md", "update.md"):
            text = (ROOT / "references" / name).read_text(encoding="utf-8")
            self.assertIn("订阅", text)

    def test_progressive_references_are_one_level_and_live(self) -> None:
        expected = {"switch.md", "user-skill-maintenance.md", "init.md", "adopt.md", "update.md"}
        references = ROOT / "references"
        self.assertEqual({path.name for path in references.glob("*.md")}, expected)
        self.assertFalse(any(path.is_dir() for path in references.iterdir()))


if __name__ == "__main__":
    unittest.main()
