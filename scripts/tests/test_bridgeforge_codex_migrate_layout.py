from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "bridgeforge_codex_migrate_layout.py"


def load_module():
    spec = importlib.util.spec_from_file_location("bridgeforge_codex_migrate_layout", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


class LayoutMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()

    def test_moves_private_skill_and_removes_manifest_owned_copy(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            project = base / "project"
            project.mkdir()
            (project / ".codex").mkdir()
            private = project / ".agents/skills/private"
            private.mkdir(parents=True)
            (private / "SKILL.md").write_text("private\n", encoding="utf-8")
            managed = project / ".agents/skills/common"
            managed.mkdir(parents=True)
            managed_payload = b"managed\n"
            (managed / "SKILL.md").write_bytes(managed_payload)

            source_root = base / "source"
            script_path = source_root / "scripts/migrate.py"
            script_path.parent.mkdir(parents=True)
            script_path.write_text("# fixture\n", encoding="utf-8")
            (source_root / "bridgeforge-codex-manifest.json").write_text(
                json.dumps({
                    "platforms": {
                        "codex": {
                            "skills": [{
                                "name": "common",
                                "files": [{
                                    "target": "SKILL.md",
                                    "sha256": digest(managed_payload),
                                }],
                            }],
                        }
                    }
                }),
                encoding="utf-8",
            )

            plan = self.module.build_plan(project, script_path)
            self.assertFalse(plan.blockers)
            self.assertFalse(plan.gaps)
            self.assertEqual(
                {action.action for action in plan.actions},
                {
                    "move_project_private_skill",
                    "delete_managed_skill_copy",
                    "delete_empty_legacy_root",
                },
            )
            self.module.apply_plan(
                plan,
                confirmed=True,
                plan_fingerprint=plan.plan_fingerprint,
            )
            self.assertFalse((project / ".agents").exists())
            self.assertEqual(
                (project / ".codex/skills/private/SKILL.md").read_text(encoding="utf-8"),
                "private\n",
            )

    @unittest.skipUnless(sys.platform == "win32", "CLI migration is Windows-only")
    def test_cli_fingerprint_drift_blocks_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw) / "project"
            private = project / ".agents/skills/private"
            private.mkdir(parents=True)
            (project / ".codex").mkdir()
            skill = private / "SKILL.md"
            skill.write_text("before\n", encoding="utf-8")
            dry = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--project-root",
                    str(project),
                    "--dry-run",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            self.assertEqual(dry.returncode, 0, dry.stdout + dry.stderr)
            fingerprint = json.loads(dry.stdout)["plan_fingerprint"]
            skill.write_text("after confirmation\n", encoding="utf-8")
            applied = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--project-root",
                    str(project),
                    "--apply",
                    "--confirmed",
                    "--plan-fingerprint",
                    fingerprint,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            self.assertEqual(applied.returncode, 2, applied.stdout + applied.stderr)
            self.assertIn("plan drifted", applied.stderr)
            self.assertEqual(skill.read_text(encoding="utf-8"), "after confirmation\n")
            self.assertFalse((project / ".codex/skills/private").exists())


if __name__ == "__main__":
    unittest.main()
