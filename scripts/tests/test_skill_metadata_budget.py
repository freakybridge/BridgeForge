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
SCRIPT = ROOT / ".codex" / "hooks" / "skill_metadata_check.py"
ALL_METADATA_HOOKS = (
    (".codex", ROOT / ".codex" / "hooks" / "skill_metadata_check.py"),
    (".codex", ROOT / "templates" / "hooks" / "skill_metadata_check.py"),
)


def skill_text(
    name: str,
    description: str = "compact discovery",
    body: str = "# Body\n",
    invocation: bool = True,
) -> str:
    invocation_metadata = "user_invocable: true\nargument: 无\n" if invocation else ""
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"{invocation_metadata}"
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
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "SKILL.md").write_text(text, encoding="utf-8")

    def test_good_skill_passes(self) -> None:
        repo = self.make_repo()
        self.write_skill(repo, "demo", skill_text("demo"))
        self.assertEqual(self.run_hook(repo).returncode, 0)

    def test_openai_standard_frontmatter_passes(self) -> None:
        repo = self.make_repo()
        self.write_skill(repo, "demo", skill_text("demo", invocation=False))
        self.assertEqual(self.run_hook(repo).returncode, 0)

    def test_incomplete_invocation_metadata_fails(self) -> None:
        repo = self.make_repo()
        text = (
            "---\n"
            "name: demo\n"
            "description: compact discovery\n"
            "user_invocable: true\n"
            "---\n\n"
            "# Body\n"
        )
        self.write_skill(repo, "demo", text)
        result = self.run_hook(repo)
        self.assertEqual(result.returncode, 2)
        self.assertIn("invocation metadata requires argument", result.stderr)

    def test_orphan_skill_directory_and_root_file_fail(self) -> None:
        repo = self.make_repo()
        orphan = repo / "skills" / "orphan"
        orphan.mkdir(parents=True)
        (repo / "skills" / "README.md").write_text("not a skill\n", encoding="utf-8")
        result = self.run_hook(repo)
        self.assertEqual(result.returncode, 2)
        self.assertIn("skills/orphan: missing SKILL.md", result.stderr)
        self.assertIn("skills/README.md: skill root may contain directories only", result.stderr)

    def test_all_hook_copies_share_the_current_contract(self) -> None:
        for host_dir, source_hook in ALL_METADATA_HOOKS:
            with self.subTest(source_hook=source_hook):
                repo = self.make_repo()
                hook_dir = repo / host_dir / "hooks"
                hook_dir.mkdir(parents=True, exist_ok=True)
                hook = hook_dir / "skill_metadata_check.py"
                shutil.copy2(source_hook, hook)
                self.write_skill(repo, "demo", skill_text("demo", invocation=False))
                standard = subprocess.run(
                    [sys.executable, "-B", str(hook)],
                    cwd=repo,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                self.assertEqual(standard.returncode, 0, standard.stderr)

                incomplete = skill_text("demo").replace("argument: 无\n", "")
                self.write_skill(repo, "demo", incomplete)
                incomplete_result = subprocess.run(
                    [sys.executable, "-B", str(hook)],
                    cwd=repo,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                self.assertEqual(incomplete_result.returncode, 2, incomplete_result.stderr)
                self.assertIn("invocation metadata requires argument", incomplete_result.stderr)

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

    def test_factory_distribution_routing_and_global_agents_are_one_contract(self) -> None:
        repo = self.make_repo()
        self.write_skill(repo, "demo", skill_text("demo"))
        self.write_skill(repo, "bridgeforge-codex", skill_text("bridgeforge-codex"))
        manifest = {
            "platforms": {
                "codex": {
                    "skills": [
                        {"name": "demo"},
                        {"name": "bridgeforge-codex"},
                        {"name": "create-worktree"},
                    ]
                }
            }
        }
        (repo / "bridgeforge-codex-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        routing = {
            "skills": [{"skill": "demo"}],
            "global_entries": [{"skill": "bridgeforge-codex"}],
        }
        template = repo / "templates"
        template.mkdir(parents=True)
        (template / "managed-skeleton.json").write_text("{}\n", encoding="utf-8")
        for path in (repo / ".codex/skill-routing.json", template / "skill-routing.json"):
            path.write_text(json.dumps(routing), encoding="utf-8")
        (repo / "AGENTS.md").write_text("demo bridgeforge-codex\n", encoding="utf-8")
        (template / "AGENTS.md").write_text(
            "demo bridgeforge-codex\n",
            encoding="utf-8",
        )

        missing = self.run_hook(repo)
        self.assertEqual(missing.returncode, 2)
        self.assertIn("missing from routing: create-worktree", missing.stderr)

        routing["global_entries"].append({"skill": "create-worktree"})
        for path in (repo / ".codex/skill-routing.json", template / "skill-routing.json"):
            path.write_text(json.dumps(routing), encoding="utf-8")
        omitted = self.run_hook(repo)
        self.assertEqual(omitted.returncode, 2)
        self.assertIn("omits global entries: create-worktree", omitted.stderr)

        (repo / "AGENTS.md").write_text(
            "demo bridgeforge-codex create-worktree\n",
            encoding="utf-8",
        )
        (template / "AGENTS.md").write_text(
            "demo bridgeforge-codex create-worktree\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_hook(repo).returncode, 0)

        (repo / ".codex/skill-routing.json").unlink()
        absent_sot = self.run_hook(repo)
        self.assertEqual(absent_sot.returncode, 2)
        self.assertIn("factory skill routing SoT is missing", absent_sot.stderr)


if __name__ == "__main__":
    unittest.main()
