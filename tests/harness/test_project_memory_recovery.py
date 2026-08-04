from __future__ import annotations

import io
import importlib.util
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
CODEX_SCRIPTS = ROOT / "templates" / "codex" / "scripts"
CLAUDE_SCRIPTS = ROOT / "templates" / "claude" / "scripts"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CODEX_WRITER = load("codex_project_memory_writer_test", CODEX_SCRIPTS / "project_memory_writer.py")
CLAUDE_WRITER = load("claude_project_memory_writer_test", CLAUDE_SCRIPTS / "project_memory_writer.py")
RECOVERY = load("project_memory_recovery_test", CODEX_SCRIPTS / "project_memory_recovery.py")


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
            shutil.copy2(CODEX_SCRIPTS / name, scripts / name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_writer_stays_in_project_and_rebuilds_index(self) -> None:
        receipt = CODEX_WRITER.write_project_memory(
            self.root, "engineering/write-boundary.md",
            "---\ncategory: engineering\ndescription: boundary\n---\n\nbody\n",
        )
        self.assertTrue((self.root / ".codex" / "memory" / "engineering" / "write-boundary.md").is_file())
        self.assertIn("engineering/write-boundary.md", (self.root / ".codex" / "memory" / "MEMORY.md").read_text(encoding="utf-8"))
        self.assertEqual(receipt.target, "engineering/write-boundary.md")
        self.assertEqual(receipt.host, "codex")
        with self.assertRaises(CODEX_WRITER.ProjectMemoryWriteError):
            CODEX_WRITER.write_project_memory(self.root, "../escape.md", "x")

    def test_markerless_codex_and_claude_writers_are_host_local(self) -> None:
        content = "---\ncategory: engineering\ndescription: host\n---\n\nbody\n"
        for host, module, source in (
            ("codex", CODEX_WRITER, CODEX_SCRIPTS),
            ("claude", CLAUDE_WRITER, CLAUDE_SCRIPTS),
        ):
            with self.subTest(host=host):
                config = f".{host}"
                project = Path(self.temp.name) / f"markerless-{host}"
                memory = project / config / "memory"
                memory.mkdir(parents=True)
                (memory / "_stats.json").write_text(
                    '{"files": {}, "config": {}}', encoding="utf-8"
                )
                scripts = project / config / "scripts"
                scripts.mkdir()
                for name in ("project_memory_writer.py", "memory_rebuild_index.py"):
                    shutil.copy2(source / name, scripts / name)
                self.assertFalse((project / config / ".bridgeforge_version").exists())

                receipt = module.write_project_memory(
                    project, "engineering/host-boundary.md", content
                )
                self.assertEqual(receipt.host, host)
                self.assertTrue((memory / "engineering" / "host-boundary.md").is_file())
                self.assertFalse((project / (".claude" if host == "codex" else ".codex")).exists())
                with self.assertRaises(module.ProjectMemoryWriteError):
                    module.write_project_memory(project, "../escape.md", "x")

    def test_writer_content_file_is_bom_free_utf8_and_byte_preserving(self) -> None:
        valid = "---\r\ncategory: engineering\r\ndescription: 中文🚦\r\n---\r\n\r\n正文—ok\r\n".encode("utf-8")
        content = Path(self.temp.name) / "content.md"
        bom = Path(self.temp.name) / "bom.md"
        invalid = Path(self.temp.name) / "invalid.md"
        content.write_bytes(valid)
        bom.write_bytes(b"\xef\xbb\xbf" + valid)
        invalid.write_bytes(b"\xff\xfe\x00")

        for host, module in (("codex", CODEX_WRITER), ("claude", CLAUDE_WRITER)):
            with self.subTest(host=host):
                decoded = module._read_content_file(str(content))
                self.assertEqual(decoded.encode("utf-8"), valid)
                with self.assertRaisesRegex(
                    module.ProjectMemoryWriteError, "stdin content is forbidden"
                ):
                    module._read_content_file("-")
                with self.assertRaisesRegex(
                    module.ProjectMemoryWriteError, "without BOM"
                ):
                    module._read_content_file(str(bom))
                with self.assertRaisesRegex(
                    module.ProjectMemoryWriteError, "valid UTF-8"
                ):
                    module._read_content_file(str(invalid))

                config = f".{host}"
                project = Path(self.temp.name) / f"roundtrip-{host}"
                memory = project / config / "memory"
                memory.mkdir(parents=True)
                (memory / "_stats.json").write_text(
                    '{"files": {}, "config": {}}', encoding="utf-8"
                )
                scripts = project / config / "scripts"
                scripts.mkdir()
                source = CODEX_SCRIPTS if host == "codex" else CLAUDE_SCRIPTS
                for name in ("project_memory_writer.py", "memory_rebuild_index.py"):
                    shutil.copy2(source / name, scripts / name)

                receipt = module.write_project_memory(
                    project,
                    "engineering/encoding-roundtrip.md",
                    decoded,
                )
                target = memory / "engineering" / "encoding-roundtrip.md"
                self.assertEqual(target.read_bytes(), valid)
                self.assertEqual(receipt.bytes_written, len(valid))
                self.assertIn(
                    "中文🚦",
                    (memory / "MEMORY.md").read_text(encoding="utf-8"),
                )

    def test_writer_cli_rejects_stdin_before_any_project_write(self) -> None:
        for host, module in (("codex", CODEX_WRITER), ("claude", CLAUDE_WRITER)):
            output = io.StringIO()
            with self.subTest(host=host), patch.object(
                module, "write_project_memory"
            ) as write_mock, redirect_stdout(output):
                result = module.main(
                    [
                        "--project-root",
                        str(self.root),
                        "--target",
                        "engineering/stdin.md",
                        "--content-file",
                        "-",
                    ]
                )
                self.assertEqual(result, 1)
                write_mock.assert_not_called()
                self.assertIn("stdin content is forbidden", output.getvalue())

    def test_writer_api_rejects_bom_before_target_creation(self) -> None:
        target = self.root / ".codex" / "memory" / "engineering" / "bom.md"
        with self.assertRaisesRegex(
            CODEX_WRITER.ProjectMemoryWriteError, "UTF-8 without BOM"
        ):
            CODEX_WRITER.write_project_memory(
                self.root,
                "engineering/bom.md",
                "\ufeff---\ncategory: engineering\ndescription: bom\n---\n",
            )
        self.assertFalse(target.exists())

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
        writer_copies = (
            CODEX_SCRIPTS / "project_memory_writer.py",
            CLAUDE_SCRIPTS / "project_memory_writer.py",
            ROOT / ".codex" / "scripts" / "project_memory_writer.py",
            ROOT / ".claude" / "scripts" / "project_memory_writer.py",
        )
        canonical = writer_copies[0].read_bytes()
        for path in writer_copies[1:]:
            self.assertEqual(path.read_bytes(), canonical, path)
        self.assertEqual(
            (ROOT / ".codex" / "scripts" / "project_memory_recovery.py").read_bytes(),
            (CODEX_SCRIPTS / "project_memory_recovery.py").read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
