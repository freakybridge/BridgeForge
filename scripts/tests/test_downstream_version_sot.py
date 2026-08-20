from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class DownstreamVersionSourceOfTruthTests(unittest.TestCase):
    def test_factory_version_matches_current_changelog(self) -> None:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        current = re.search(r"(?m)^## \[([^]]+)]", changelog)
        self.assertIsNotNone(current)
        self.assertEqual(version, current.group(1))
        self.assertFalse((ROOT / "templates/VERSION").exists())

    def test_codex_runtime_reads_only_new_skeleton_stamp(self) -> None:
        for relative in (
            "templates/hooks/show_state.py",
            "templates/hooks/session_snapshot.py",
            ".codex/hooks/show_state.py",
            ".codex/hooks/session_snapshot.py",
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(".bridgeforge_codex_version", text)
            self.assertNotIn('".bridgeforge_version"', text)

    def test_schema_stamp_is_new_and_dogfood_is_identical(self) -> None:
        template = json.loads(
            (ROOT / "templates/managed-skeleton.json").read_text(encoding="utf-8-sig")
        )
        dogfood = json.loads(
            (ROOT / ".codex/managed-skeleton.json").read_text(encoding="utf-8-sig")
        )
        self.assertEqual(template, dogfood)
        self.assertEqual(template["stamp"], ".codex/.bridgeforge_codex_version")

    def test_project_sync_is_only_stamp_writer(self) -> None:
        sync = (ROOT / "scripts/bridgeforge_codex_project_sync.py").read_text(encoding="utf-8")
        self.assertIn('CURRENT_STAMP = ".codex/.bridgeforge_codex_version"', sync)
        self.assertIn('OBSOLETE_STAMP = ".codex/.bridgeforge_version"', sync)
        self.assertFalse((ROOT / "scripts/bridgeforge_project_finalize.py").exists())


if __name__ == "__main__":
    unittest.main()
