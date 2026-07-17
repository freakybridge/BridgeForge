#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".codex" / "hooks" / "skill_metadata_check.py"


def skill_text(name: str, description: str = "compact discovery", body: str = "# Body\n") -> str:
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        "user_invocable: true\n"
        "argument: 无\n"
        "---\n\n"
        f"{body}"
    )


class SkillMetadataBudgetTests(unittest.TestCase):
    def make_repo(self) -> Path:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        repo = Path(self.temp.name)
        hooks = repo / ".codex" / "hooks"
        hooks.mkdir(parents=True)
        shutil.copy2(SCRIPT, hooks / SCRIPT.name)
        return repo

    def run_hook(self, repo: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-B", str(repo / ".codex" / "hooks" / SCRIPT.name)],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def write_skill(self, repo: Path, name: str, text: str) -> None:
        folder = repo / "skills" / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(text, encoding="utf-8")

    def test_good_skill_passes(self) -> None:
        repo = self.make_repo()
        self.write_skill(repo, "demo", skill_text("demo"))
        self.assertEqual(self.run_hook(repo).returncode, 0)

    def test_long_description_body_and_dead_reference_fail(self) -> None:
        repo = self.make_repo()
        body = "[missing](references/missing.md)\n" + "line\n" * 501
        self.write_skill(repo, "demo", skill_text("demo", "x" * 501, body))
        result = self.run_hook(repo)
        self.assertEqual(result.returncode, 2)
        self.assertIn("description exceeds", result.stderr)
        self.assertIn("exceeds 500 lines", result.stderr)
        self.assertIn("dead markdown reference", result.stderr)

    def test_project_links_and_placeholders_are_not_packaged_references(self) -> None:
        repo = self.make_repo()
        body = (
            "[TODO](doc/0_architecture/TODO-INDEX.md)\n"
            "[memory](<agent-dir>/memory/MEMORY.md)\n"
        )
        self.write_skill(repo, "demo", skill_text("demo", body=body))
        self.assertEqual(self.run_hook(repo).returncode, 0)

    def test_catalog_description_budget_fails(self) -> None:
        repo = self.make_repo()
        for index in range(9):
            name = f"demo-{index}"
            self.write_skill(repo, name, skill_text(name, "x" * 450))
        result = self.run_hook(repo)
        self.assertEqual(result.returncode, 2)
        self.assertIn("skill catalog descriptions exceed 4000", result.stderr)


if __name__ == "__main__":
    unittest.main()
