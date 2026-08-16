#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SHOW_STATES = (
    ROOT / ".codex/hooks/show_state.py",
    ROOT / "templates/hooks/show_state.py",
)
ARCHIVE_SCANS = (
    ROOT / ".codex/scripts/archive_scan.py",
    ROOT / "templates/scripts/archive_scan.py",
)
ROUTING_FILES = (
    ROOT / ".codex/skill-routing.json",
    ROOT / "templates/skill-routing.json",
)


def load(path: Path, name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class SkillRuntimeEfficiencyTests(unittest.TestCase):
    def test_show_state_uses_one_git_process_and_preserves_fields(self) -> None:
        receipt = "\n".join((
            "# branch.oid abc123",
            "# branch.head codex/fast-path",
            "# branch.upstream origin/codex/fast-path",
            "# branch.ab +2 -3",
            "1 .M N... 100644 100644 100644 abc abc work.py",
            "? new.txt",
        ))
        for index, path in enumerate(SHOW_STATES):
            with self.subTest(path=path):
                module = load(path, f"show_state_efficiency_{index}")
                completed = types.SimpleNamespace(returncode=0, stdout=receipt)
                with mock.patch.object(module.subprocess, "run", return_value=completed) as run:
                    self.assertEqual(module._git_state(), ("codex/fast-path", 2, "2/3"))
                run.assert_called_once()
                self.assertEqual(
                    run.call_args.args[0],
                    ["git", "status", "--porcelain=v2", "--branch"],
                )

    def test_show_state_preserves_detached_and_no_upstream_fallbacks(self) -> None:
        module = load(SHOW_STATES[0], "show_state_fallbacks")
        self.assertEqual(
            module._parse_git_status("# branch.oid abc\n# branch.head (detached)\n"),
            ("?", 0, "no-upstream"),
        )
        self.assertEqual(module._parse_git_status(""), ("?", 0, "no-upstream"))

    def test_archive_scan_batches_git_history_and_keeps_untracked_none(self) -> None:
        module = load(ARCHIVE_SCANS[0], "archive_scan_efficiency")
        module.REPO_ROOT = Path("C:/repo")
        tracked = module.REPO_ROOT / "doc/2_bugs/BUG-001-中文.md"
        untracked = module.REPO_ROOT / "doc/2_bugs/BUG-002.md"
        now = 50 * 86400
        receipt = (
            "\0@@bridgeforge-commit-time:864000\0\0\n"
            "doc/2_bugs/BUG-001-中文.md\0"
        )
        completed = types.SimpleNamespace(returncode=0, stdout=receipt)
        with (
            mock.patch.object(module.subprocess, "run", return_value=completed) as run,
            mock.patch.object(module.time, "time", return_value=now),
        ):
            days = module._days_by_path([tracked, untracked])
        self.assertEqual(days, {tracked: 40, untracked: None})
        run.assert_called_once()
        command = run.call_args.args[0]
        self.assertEqual(command[:11], [
            "git", "-c", "core.quotepath=false", "log", "--no-renames",
            "--format=%x00@@bridgeforge-commit-time:%at%x00", "--name-only",
            "-z", "--", "doc/2_bugs/BUG-001-中文.md",
            "doc/2_bugs/BUG-002.md",
        ])
        self.assertEqual(command[11:], [])

    def test_runtime_scripts_are_mirrored_for_codex(self) -> None:
        self.assertEqual(SHOW_STATES[0].read_bytes(), SHOW_STATES[1].read_bytes())
        archive = ARCHIVE_SCANS[0].read_bytes()
        for path in ARCHIVE_SCANS[1:]:
            self.assertEqual(archive, path.read_bytes())

    def test_routing_has_main_fast_paths_and_bounded_fallbacks(self) -> None:
        for path in ROUTING_FILES:
            with self.subTest(path=path):
                routing = json.loads(path.read_text(encoding="utf-8"))
                by_skill: dict[str, list[dict[str, str]]] = {}
                for route in routing["skills"]:
                    by_skill.setdefault(route["skill"], []).append(route)
                for skill in ("archive-scan", "find-doc", "find-memory", "todo"):
                    agents = {route["agent"] for route in by_skill[skill]}
                    self.assertEqual(agents, {"main", "light-explorer"})
                self.assertNotIn(
                    "light-explorer",
                    {route["agent"] for route in by_skill["debate"]},
                )
                self.assertTrue(all(
                    "only" in route["root_must_do"]
                    for skill in ("archive-scan", "find-doc", "find-memory", "todo")
                    for route in by_skill[skill]
                    if route["agent"] == "light-explorer"
                ))

    def test_memory_skills_forbid_manual_or_duplicate_index_updates(self) -> None:
        todo = (ROOT / "skills/todo/SKILL.md").read_text(encoding="utf-8")
        summary = (ROOT / "skills/summary/SKILL.md").read_text(encoding="utf-8")
        deep = (ROOT / "skills/summary/references/deep-steps.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("禁止手工编辑 `MEMORY.md`", todo)
        self.assertIn("禁止再次单独运行 `memory_rebuild_index.py`", summary)
        self.assertIn("writer 已返回成功 `rebuild_command` 时复用该收据", deep)


if __name__ == "__main__":
    unittest.main()
