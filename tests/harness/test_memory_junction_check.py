#!/usr/bin/env python3
"""Focused regression tests for the shared memory junction state machine."""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "templates" / "codex" / "hooks" / "memory_junction_check.py"
SPEC = importlib.util.spec_from_file_location("memory_junction_check", HOOK)
assert SPEC and SPEC.loader
memory_junction = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = memory_junction
SPEC.loader.exec_module(memory_junction)


class MemoryJunctionCheckTests(unittest.TestCase):
    def _memory_paths(self, root: Path) -> tuple[Path, Path]:
        return root / "system" / "memory", root / "repo" / ".codex" / "memory"

    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _junction(self, link: Path, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        memory_junction._create_junction(link, target)
        self.assertTrue(memory_junction._link_matches(link, target))

    def test_all_host_scripts_are_exact_mirrors(self) -> None:
        expected = HOOK.read_bytes()
        for relative in (
            "templates/claude/hooks/memory_junction_check.py",
            ".codex/hooks/memory_junction_check.py",
        ):
            self.assertEqual((ROOT / relative).read_bytes(), expected)

    def test_correct_junction_is_noop_and_target_is_checked_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            system, project = self._memory_paths(root)
            wrong = root / "wrong"
            self._junction(system, project)

            result = memory_junction.reconcile(
                "check", system_memory=system, project_memory=project
            )
            self.assertEqual(result.state, "linked")
            self.assertFalse(result.changed)

            system.rmdir()
            self._junction(system, wrong)
            result = memory_junction.reconcile(
                "check", system_memory=system, project_memory=project
            )
            self.assertEqual(result.state, "error")
            self.assertTrue(memory_junction._link_matches(system, wrong))

    def test_broken_junction_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            system, project = self._memory_paths(root)
            self._junction(system, project)
            shutil.rmtree(project)

            result = memory_junction.reconcile(
                "check", system_memory=system, project_memory=project
            )
            self.assertEqual(result.state, "error")
            self.assertTrue(memory_junction._lexists(system))

    def test_new_clone_restores_missing_junction(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            system, project = self._memory_paths(Path(temp))
            self._write(project / "MEMORY.md", "tracked\n")

            result = memory_junction.reconcile(
                "check", system_memory=system, project_memory=project
            )
            self.assertEqual(result.state, "linked")
            self.assertTrue(result.changed)
            self.assertTrue(memory_junction._link_matches(system, project))

    def test_session_start_never_migrates_real_system_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            system, project = self._memory_paths(Path(temp))
            self._write(system / "system.md", "system\n")
            self._write(project / "project.md", "project\n")
            before_system = (system / "system.md").read_bytes()
            before_project = (project / "project.md").read_bytes()

            with (
                mock.patch.object(
                    memory_junction, "_copy_unique_files"
                ) as copy_unique,
                mock.patch.object(memory_junction.shutil, "rmtree") as remove,
                mock.patch.object(
                    memory_junction, "_create_junction"
                ) as create_junction,
            ):
                result = memory_junction.reconcile(
                    "check", system_memory=system, project_memory=project
                )

            self.assertEqual(result.state, "migration-required")
            self.assertIn("/bridgeforge to review and confirm migration", result.detail)
            copy_unique.assert_not_called()
            remove.assert_not_called()
            create_junction.assert_not_called()
            self.assertEqual((system / "system.md").read_bytes(), before_system)
            self.assertEqual((project / "project.md").read_bytes(), before_project)

    def test_direct_api_call_cannot_bypass_migration_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            system, project = self._memory_paths(Path(temp))
            self._write(system / "system.md", "system\n")
            self._write(project / "project.md", "project\n")

            with (
                mock.patch.object(
                    memory_junction, "_copy_unique_files"
                ) as copy_unique,
                mock.patch.object(memory_junction.shutil, "rmtree") as remove,
                mock.patch.object(
                    memory_junction, "_create_junction"
                ) as create_junction,
            ):
                result = memory_junction.reconcile(
                    "migrate",
                    system_memory=system,
                    project_memory=project,
                )

            self.assertEqual(result.state, "error")
            self.assertIn("confirmed=True", result.detail)
            copy_unique.assert_not_called()
            remove.assert_not_called()
            create_junction.assert_not_called()
            self.assertTrue((system / "system.md").is_file())
            self.assertFalse((project / "system.md").exists())

    def test_invalid_mode_cannot_enter_destructive_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            system, project = self._memory_paths(Path(temp))
            self._write(system / "system.md", "system\n")
            self._write(project / "project.md", "project\n")

            with (
                mock.patch.object(
                    memory_junction, "_copy_unique_files"
                ) as copy_unique,
                mock.patch.object(memory_junction.shutil, "rmtree") as remove,
                mock.patch.object(
                    memory_junction, "_create_junction"
                ) as create_junction,
            ):
                result = memory_junction.reconcile(
                    "invalid",
                    confirmed=True,
                    system_memory=system,
                    project_memory=project,
                )

            self.assertEqual(result.state, "error")
            self.assertIn("invalid reconciliation mode", result.detail)
            copy_unique.assert_not_called()
            remove.assert_not_called()
            create_junction.assert_not_called()
            self.assertTrue((system / "system.md").is_file())
            self.assertFalse((project / "system.md").exists())

    def test_plan_is_read_only_and_reports_merge_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            system, project = self._memory_paths(Path(temp))
            self._write(system / "system.md", "system\n")
            self._write(system / "same.md", "same\n")
            self._write(project / "same.md", "same\n")
            self._write(project / "project.md", "project\n")

            result = memory_junction.reconcile(
                "plan", system_memory=system, project_memory=project
            )

            self.assertEqual(result.state, "migration-required")
            self.assertEqual(
                result.detail,
                "migration plan: copy=1, identical=1, project_only=1",
            )
            self.assertFalse((project / "system.md").exists())
            self.assertTrue(system.is_dir())

    def test_confirmed_migration_merges_verifies_deletes_and_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            system, project = self._memory_paths(root)
            self._write(system / "nested" / "system.md", "system\n")
            self._write(system / "same.md", "same\n")
            self._write(project / "same.md", "same\n")
            self._write(project / "project.md", "project\n")

            result = memory_junction.reconcile(
                "migrate",
                confirmed=True,
                system_memory=system,
                project_memory=project,
            )

            self.assertEqual(result.state, "linked", result.detail)
            self.assertTrue(result.changed)
            self.assertTrue(memory_junction._link_matches(system, project))
            self.assertEqual(
                (project / "nested" / "system.md").read_text(encoding="utf-8"),
                "system\n",
            )
            self.assertEqual(
                (project / "project.md").read_text(encoding="utf-8"),
                "project\n",
            )
            self.assertFalse((root / "system" / "memory.premigrate.bak").exists())

    def test_conflict_blocks_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            system, project = self._memory_paths(Path(temp))
            self._write(system / "unique.md", "system unique\n")
            self._write(system / "conflict.md", "system\n")
            self._write(project / "conflict.md", "project\n")
            before = (project / "conflict.md").read_bytes()

            result = memory_junction.reconcile(
                "migrate",
                confirmed=True,
                system_memory=system,
                project_memory=project,
            )

            self.assertEqual(result.state, "error")
            self.assertIn("conflict.md", result.detail)
            self.assertFalse((project / "unique.md").exists())
            self.assertEqual((project / "conflict.md").read_bytes(), before)
            self.assertTrue(system.is_dir())
            self.assertFalse(memory_junction._is_link(system))

    def test_integrity_failure_never_deletes_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            system, project = self._memory_paths(Path(temp))
            self._write(system / "system.md", "system\n")
            project.mkdir(parents=True)

            with mock.patch.object(
                memory_junction,
                "_verify_contains",
                side_effect=memory_junction.ReconcileError(
                    "injected integrity failure"
                ),
            ):
                result = memory_junction.reconcile(
                    "migrate",
                    confirmed=True,
                    system_memory=system,
                    project_memory=project,
                )

            self.assertEqual(result.state, "error")
            self.assertIn("integrity failure", result.detail)
            self.assertTrue((system / "system.md").is_file())
            self.assertFalse(memory_junction._is_link(system))

    def test_abnormal_nested_link_blocks_without_copying(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            system, project = self._memory_paths(root)
            external = root / "external"
            self._write(external / "outside.md", "outside\n")
            system.mkdir(parents=True)
            self._junction(system / "linked", external)
            project.mkdir(parents=True)

            result = memory_junction.reconcile(
                "migrate",
                confirmed=True,
                system_memory=system,
                project_memory=project,
            )

            self.assertEqual(result.state, "error")
            self.assertIn("abnormal directory entry", result.detail)
            self.assertEqual(list(project.iterdir()), [])
            self.assertTrue((external / "outside.md").is_file())

    @unittest.skipUnless(os.name == "nt", "Windows case semantics only")
    def test_case_only_file_conflict_blocks_before_copying(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            system, project = self._memory_paths(Path(temp))
            self._write(system / "unique.md", "unique\n")
            self._write(system / "Foo.md", "same\n")
            self._write(project / "foo.md", "same\n")

            result = memory_junction.reconcile(
                "migrate",
                confirmed=True,
                system_memory=system,
                project_memory=project,
            )

            self.assertEqual(result.state, "error")
            self.assertIn("Foo.md <-> foo.md", result.detail)
            self.assertFalse((project / "unique.md").exists())
            self.assertTrue((system / "unique.md").is_file())

    @unittest.skipUnless(os.name == "nt", "Windows case semantics only")
    def test_case_only_directory_file_conflict_blocks_before_copying(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            system, project = self._memory_paths(Path(temp))
            self._write(system / "Folder" / "source.md", "source\n")
            self._write(project / "folder", "project file\n")

            result = memory_junction.reconcile(
                "migrate",
                confirmed=True,
                system_memory=system,
                project_memory=project,
            )

            self.assertEqual(result.state, "error")
            self.assertIn("Folder <-> folder", result.detail)
            self.assertFalse((project / "Folder" / "source.md").exists())
            self.assertTrue((system / "Folder" / "source.md").is_file())

    def test_cli_requires_confirmation_for_migrate_mode(self) -> None:
        self.assertEqual(memory_junction.main(["--mode", "migrate"]), 2)


if __name__ == "__main__":
    unittest.main()
