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
        for marker in ("config.toml", "agents/*.toml", "skill-routing.json", ".githooks/pre-commit"):
            self.assertIn(marker, init)
            self.assertIn(marker, update)

    def test_progressive_references_are_one_level_and_live(self) -> None:
        expected = {"switch.md", "user-skill-maintenance.md", "init.md", "adopt.md", "update.md"}
        references = ROOT / "references"
        self.assertEqual({path.name for path in references.glob("*.md")}, expected)
        self.assertFalse(any(path.is_dir() for path in references.iterdir()))


if __name__ == "__main__":
    unittest.main()
