#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".codex" / "scripts" / "memory_rebuild_index.py"


class MemoryRebuildIndexTests(unittest.TestCase):
    def test_active_index_obeys_description_and_character_budgets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            scripts = repo / ".codex" / "scripts"
            memory = repo / ".codex" / "memory"
            scripts.mkdir(parents=True)
            memory.mkdir(parents=True)
            shutil.copy2(SCRIPT, scripts / SCRIPT.name)
            for index in range(60):
                (memory / f"note-{index:02d}.md").write_text(
                    "---\n"
                    f"description: {'x' * 250}\n"
                    f"created_at: 2026-07-{(index % 28) + 1:02d}\n"
                    "---\nbody\n",
                    encoding="utf-8",
                )
            (memory / "_stats.json").write_text(
                json.dumps({"config": {"pinned": [f"note-{index:02d}.md" for index in range(5)]}}),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, "-B", str(scripts / SCRIPT.name)],
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            index_text = (memory / "MEMORY.md").read_text(encoding="utf-8")
            self.assertLessEqual(len(index_text), 6000)
            self.assertIn("## 📌 Pinned", index_text)
            active_text = index_text.split("## Active", 1)[1].split("Cold（", 1)[0]
            active_lines = [line for line in active_text.splitlines() if line.startswith("- [")]
            self.assertLessEqual(len(active_lines), 40)
            self.assertLessEqual(sum(len(line) + 1 for line in active_lines), 6000)
            self.assertTrue(all(len(line.split(" — ", 1)[-1]) <= 180 for line in active_lines))
            self.assertIn("## 🔍 Cold（", index_text)


if __name__ == "__main__":
    unittest.main()
