from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "templates" / "codex" / "scripts"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


WRITER = load("project_memory_writer_test", SCRIPTS / "project_memory_writer.py")
RECOVERY = load("project_memory_recovery_test", SCRIPTS / "project_memory_recovery.py")


class ProjectMemoryRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        (self.root / ".codex" / "memory").mkdir(parents=True)
        (self.root / ".codex" / ".bridgeforge_version").write_text("x\n", encoding="utf-8")
        (self.root / ".codex" / "memory" / "_stats.json").write_text('{"files": {}, "config": {}}', encoding="utf-8")
        scripts = self.root / ".codex" / "scripts"
        scripts.mkdir()
        for name in ("project_memory_writer.py", "project_memory_recovery.py", "memory_rebuild_index.py"):
            shutil.copy2(SCRIPTS / name, scripts / name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_writer_stays_in_project_and_rebuilds_index(self) -> None:
        receipt = WRITER.write_project_memory(
            self.root, "engineering/write-boundary.md",
            "---\ncategory: engineering\ndescription: boundary\n---\n\nbody\n",
        )
        self.assertTrue((self.root / ".codex" / "memory" / "engineering" / "write-boundary.md").is_file())
        self.assertIn("engineering/write-boundary.md", (self.root / ".codex" / "memory" / "MEMORY.md").read_text(encoding="utf-8"))
        self.assertEqual(receipt.target, "engineering/write-boundary.md")
        with self.assertRaises(WRITER.ProjectMemoryWriteError):
            WRITER.write_project_memory(self.root, "../escape.md", "x")

    def test_recovery_requires_exact_owner_and_never_deletes_unclassified(self) -> None:
        notes = Path(self.temp.name) / "notes"
        notes.mkdir()
        eligible = notes / "eligible.md"
        eligible.write_text(f"# x\n\n- 项目：`{self.root}`\n", encoding="utf-8")
        unknown = notes / "unknown.md"
        unknown.write_text("# CausisRiskSuite\n", encoding="utf-8")
        plan = RECOVERY.notes_plan(self.root, notes)
        self.assertEqual(len(plan), 1)
        result = RECOVERY.notes_apply(
            self.root, notes, eligible, plan[0]["sha256"], "domain/recovered.md",
            "---\ncategory: domain\ndescription: recovered\n---\n\nbody\n", True,
        )
        self.assertTrue(result["deleted"])
        self.assertFalse(eligible.exists())
        self.assertTrue(unknown.exists())

    def test_changed_note_and_orphan_without_confirmation_are_preserved(self) -> None:
        notes = Path(self.temp.name) / "notes"; notes.mkdir()
        note = notes / "owned.md"; note.write_text(f"项目：`{self.root}`\n", encoding="utf-8")
        plan = RECOVERY.notes_plan(self.root, notes)[0]
        note.write_text(f"项目：`{self.root}`\nchanged\n", encoding="utf-8")
        with self.assertRaises(RECOVERY.RecoveryError):
            RECOVERY.notes_apply(self.root, notes, note, plan["sha256"], "domain/x.md", "x", True)
        self.assertTrue(note.exists())
        orphan = Path(self.temp.name) / "orphan"; orphan.mkdir()
        for name, text in (("MEMORY.md", ""), ("MEMORY_COLD.md", ""), ("_stats.json", '{"files": {}}')):
            (orphan / name).write_text(text, encoding="utf-8")
        fingerprint = RECOVERY.orphan_plan(orphan)["fingerprint"]
        with self.assertRaises(RECOVERY.RecoveryError):
            RECOVERY.orphan_apply(orphan, fingerprint, False)
        self.assertTrue(orphan.exists())

    def _empty_orphan(self, name: str) -> Path:
        orphan = Path(self.temp.name) / name; orphan.mkdir()
        for file_name, text in (("MEMORY.md", "> Active: 0 | Cold: 0\n"), ("MEMORY_COLD.md", "<!-- empty -->\n"), ("_stats.json", '{"files": {}}')):
            (orphan / file_name).write_text(text, encoding="utf-8")
        return orphan

    def test_orphan_with_index_content_or_changed_plan_is_never_deleted(self) -> None:
        with_content = self._empty_orphan("with-content")
        (with_content / "MEMORY.md").write_text("- [real](real.md)\n", encoding="utf-8")
        self.assertFalse(RECOVERY.orphan_plan(with_content)["eligible"])
        self.assertTrue(with_content.exists())
        changed = self._empty_orphan("changed")
        plan = RECOVERY.orphan_plan(changed)
        (changed / "MEMORY_COLD.md").write_text("changed\n", encoding="utf-8")
        with self.assertRaises(RECOVERY.RecoveryError):
            RECOVERY.orphan_apply(changed, plan["fingerprint"], True)
        self.assertTrue(changed.exists())

    def test_confirmed_strict_empty_orphan_is_deleted(self) -> None:
        orphan = self._empty_orphan("empty")
        plan = RECOVERY.orphan_plan(orphan)
        self.assertTrue(plan["eligible"])
        result = RECOVERY.orphan_apply(orphan, plan["fingerprint"], True)
        self.assertTrue(result["deleted"])
        self.assertFalse(orphan.exists())

    def test_scripts_are_dogfood_mirrors(self) -> None:
        for name in ("project_memory_writer.py", "project_memory_recovery.py"):
            self.assertEqual((ROOT / ".codex" / "scripts" / name).read_bytes(), (SCRIPTS / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
