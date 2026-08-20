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
LINT = ROOT / ".codex" / "hooks" / "memory_lint.py"
DUP = ROOT / ".codex" / "hooks" / "memory_dup_check.py"


class MemoryRebuildIndexTests(unittest.TestCase):
    def test_new_templates_start_with_only_memory_index(self) -> None:
        memory = ROOT / "templates/memory"
        self.assertEqual(
            {path.name for path in memory.iterdir()},
            {"MEMORY.md"},
        )

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

    def test_check_mode_is_read_only_and_blocks_stale_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            scripts = repo / ".codex" / "scripts"
            memory = repo / ".codex" / "memory"
            scripts.mkdir(parents=True)
            memory.mkdir(parents=True)
            shutil.copy2(SCRIPT, scripts / SCRIPT.name)
            (memory / "note.md").write_text(
                "---\ndescription: note\n---\nbody\n",
                encoding="utf-8",
            )

            stale = subprocess.run(
                [sys.executable, "-B", str(scripts / SCRIPT.name), "--check"],
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(stale.returncode, 2)
            self.assertFalse((memory / "MEMORY.md").exists())
            self.assertFalse((memory / "MEMORY_COLD.md").exists())

            rebuilt = subprocess.run(
                [sys.executable, "-B", str(scripts / SCRIPT.name)],
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(rebuilt.returncode, 0, rebuilt.stderr)
            before = {path.name: path.read_bytes() for path in memory.iterdir()}
            current = subprocess.run(
                [sys.executable, "-B", str(scripts / SCRIPT.name), "--check"],
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(current.returncode, 0, current.stderr)
            self.assertEqual(
                {path.name: path.read_bytes() for path in memory.iterdir()},
                before,
            )

    def test_nested_memory_and_completed_topic_are_indexed_as_cold(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            scripts = repo / ".codex" / "scripts"
            hooks = repo / ".codex" / "hooks"
            memory = repo / ".codex" / "memory"
            scripts.mkdir(parents=True)
            hooks.mkdir(parents=True)
            memory.mkdir(parents=True)
            shutil.copy2(SCRIPT, scripts / SCRIPT.name)
            shutil.copy2(LINT, hooks / LINT.name)
            active = memory / "engineering" / "indexing.md"
            active.parent.mkdir()
            active.write_text(
                "---\ncategory: engineering\nstatus: active\n"
                "description: nested engineering note\n---\nindexing\n",
                encoding="utf-8",
            )
            completed = memory / "topics" / "memory-layout" / "summary.md"
            completed.parent.mkdir(parents=True)
            completed.write_text(
                "---\ncategory: topic\ntopic: memory-layout\n"
                "status: completed\ndescription: completed topic\n---\n",
                encoding="utf-8",
            )
            superseded = memory / "topics" / "old-layout" / "summary.md"
            superseded.parent.mkdir(parents=True)
            superseded.write_text(
                "---\ncategory: topic\ntopic: old-layout\n"
                "status: superseded\ndescription: replaced topic\n---\n",
                encoding="utf-8",
            )

            rebuild = subprocess.run(
                [sys.executable, "-B", str(scripts / SCRIPT.name)],
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(rebuild.returncode, 0, rebuild.stderr)
            index_text = (memory / "MEMORY.md").read_text(encoding="utf-8")
            cold_text = (memory / "MEMORY_COLD.md").read_text(encoding="utf-8")
            self.assertIn("engineering/indexing.md", index_text)
            self.assertNotIn("topics/memory-layout/summary.md", index_text)
            self.assertIn("topics/memory-layout/summary.md", cold_text)
            self.assertNotIn("topics/old-layout/summary.md", index_text)
            self.assertIn("topics/old-layout/summary.md", cold_text)

            plan = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(hooks / LINT.name),
                    "legacy.md",
                    "--category",
                    "engineering",
                ],
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(plan.returncode, 2)
            legacy = memory / "legacy.md"
            legacy.write_text("---\ndescription: legacy\n---\n", encoding="utf-8")
            plan = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(hooks / LINT.name),
                    "legacy.md",
                    "--category",
                    "engineering",
                ],
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(plan.returncode, 1)
            self.assertTrue(legacy.exists())
            apply = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(hooks / LINT.name),
                    "legacy.md",
                    "--category",
                    "engineering",
                    "--apply",
                    "--confirmed",
                ],
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(apply.returncode, 0, apply.stderr)
            moved = memory / "engineering" / "legacy.md"
            self.assertTrue(moved.exists())
            self.assertIn("category: engineering", moved.read_text(encoding="utf-8"))
            self.assertIn("status: active", moved.read_text(encoding="utf-8"))

    def test_codex_duplicate_check_handles_hyphenated_topics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            hooks = repo / ".codex" / "hooks"
            memory = repo / ".codex" / "memory" / "topics" / "memory-layout"
            hooks.mkdir(parents=True)
            memory.mkdir(parents=True)
            shutil.copy2(DUP, hooks / DUP.name)
            for name in ("memory-layout-index.md", "memory-layout-index-plan.md"):
                (memory / name).write_text("existing\n", encoding="utf-8")
            candidate = memory / "memory-layout-index-summary.md"
            payload = json.dumps(
                {"tool_name": "Write", "tool_input": {"file_path": str(candidate)}}
            )
            result = subprocess.run(
                [sys.executable, "-B", str(hooks / DUP.name)],
                cwd=repo,
                input=payload,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("[memory-dup-check]", result.stdout)


if __name__ == "__main__":
    unittest.main()
