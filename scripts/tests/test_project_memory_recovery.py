from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CODEX_SCRIPTS = ROOT / "templates/scripts"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


WRITER = load("codex_project_memory_writer_test", CODEX_SCRIPTS / "project_memory_writer.py")
RECOVERY = load("codex_project_memory_recovery_test", CODEX_SCRIPTS / "project_memory_recovery.py")


class ProjectMemoryRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        memory = self.root / ".codex/memory"
        memory.mkdir(parents=True)
        (self.root / ".codex/.bridgeforge_codex_version").write_text(
            "1.0.0\n", encoding="utf-8"
        )
        (memory / "_stats.json").write_text('{"files": {}, "config": {}}', encoding="utf-8")
        scripts = self.root / ".codex/scripts"
        scripts.mkdir()
        for name in ("project_memory_writer.py", "project_memory_recovery.py", "memory_rebuild_index.py"):
            shutil.copy2(CODEX_SCRIPTS / name, scripts / name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_writer_is_codex_local_and_rebuilds_index(self) -> None:
        receipt = WRITER.write_project_memory(
            self.root,
            "engineering/write-boundary.md",
            "---\ncategory: engineering\ndescription: boundary\n---\n\nbody\n",
        )
        self.assertEqual(receipt.host, "codex")
        self.assertTrue((self.root / ".codex/memory/engineering/write-boundary.md").is_file())
        self.assertIn(
            "engineering/write-boundary.md",
            (self.root / ".codex/memory/MEMORY.md").read_text(encoding="utf-8"),
        )
        self.assertFalse((self.root / ".claude").exists())
        with self.assertRaises(WRITER.ProjectMemoryWriteError):
            WRITER.write_project_memory(self.root, "../escape.md", "x")

    def test_writer_rejects_bom_and_stdin(self) -> None:
        content = Path(self.temp.name) / "bom.md"
        content.write_bytes(b"\xef\xbb\xbfbody")
        with self.assertRaisesRegex(WRITER.ProjectMemoryWriteError, "without BOM"):
            WRITER._read_content_file(str(content))
        with self.assertRaisesRegex(WRITER.ProjectMemoryWriteError, "stdin content is forbidden"):
            WRITER._read_content_file("-")

    def test_recovery_requires_exact_owner_and_preserves_unknown(self) -> None:
        notes = Path(self.temp.name) / "notes"
        notes.mkdir()
        eligible = notes / "eligible.md"
        eligible.write_text(f"# x\n\n- 项目：`{self.root}`\n", encoding="utf-8")
        unknown = notes / "unknown.md"
        unknown.write_text("# another project\n", encoding="utf-8")
        plan = RECOVERY.notes_plan(self.root, notes)
        self.assertEqual(len(plan), 1)
        result = RECOVERY.notes_apply(
            self.root,
            notes,
            eligible,
            plan[0]["sha256"],
            "domain/recovered.md",
            "---\ncategory: domain\ndescription: recovered\n---\n\nbody\n",
            True,
        )
        self.assertTrue(result["deleted"])
        self.assertTrue(unknown.exists())

    def test_codex_scripts_are_dogfood_mirrors(self) -> None:
        for name in ("project_memory_writer.py", "project_memory_recovery.py"):
            self.assertEqual(
                (CODEX_SCRIPTS / name).read_bytes(),
                (ROOT / ".codex/scripts" / name).read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
