from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import importlib.util


ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "templates" / "hooks" / "project_structure_check.py"

SPEC = importlib.util.spec_from_file_location("project_structure_check", HOOK)
assert SPEC and SPEC.loader
PROJECT_STRUCTURE_CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROJECT_STRUCTURE_CHECK)


class ProjectStructureCheckTests(unittest.TestCase):
    def make_project(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        doc = root / "doc"
        for name in (
            "0_architecture",
            "1_delivery",
            "2_bugs",
            "3_reference",
            "4_archive",
        ):
            (doc / name).mkdir(parents=True, exist_ok=True)
        (doc / "README.md").write_text(
            "---\ndelivery_layout: flat\n---\n\n# Docs\n",
            encoding="utf-8",
        )
        return root

    def run_check(self, root: Path, *, json_output: bool = False) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, str(HOOK), "--root", str(root)]
        if json_output:
            command.append("--json")
        return subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def test_clean_five_layer_project_passes(self) -> None:
        project = self.make_project()
        result = self.run_check(project, json_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["errors"], [])

    def test_legacy_test_root_is_blocked_without_writes(self) -> None:
        project = self.make_project()
        marker = project / "tests" / "test_marker.py"
        marker.parent.mkdir()
        marker.write_text("MARKER\n", encoding="utf-8")
        before = marker.read_bytes()

        result = self.run_check(project, json_output=True)

        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertIn("legacy-test-root", {item["code"] for item in payload["errors"]})
        self.assertEqual(marker.read_bytes(), before)

    def test_unindexed_delivery_topic_is_blocked(self) -> None:
        project = self.make_project()
        topic = project / "doc" / "1_delivery" / "missing-topic"
        topic.mkdir()
        (topic / "requirements_2026-08-16_missing.md").write_text(
            "---\nstatus: active\n---\n",
            encoding="utf-8",
        )

        result = self.run_check(project, json_output=True)

        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertIn(
            "unindexed-delivery-topic",
            {item["code"] for item in payload["errors"]},
        )

    def test_legacy_archive_and_closed_items_are_advisory(self) -> None:
        project = self.make_project()
        topic = project / "doc" / "1_delivery" / "done-topic"
        topic.mkdir()
        requirement = topic / "requirements_2026-08-16_done.md"
        requirement.write_text("---\nstatus: completed\n---\n", encoding="utf-8")
        archive = project / "doc" / "4_archive" / "old-report.md"
        archive.write_text("# old\n", encoding="utf-8")
        readme = project / "doc" / "README.md"
        readme.write_text(readme.read_text(encoding="utf-8") + "\n- done-topic\n", encoding="utf-8")

        result = self.run_check(project, json_output=True)

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        codes = {item["code"] for item in payload["advisories"]}
        self.assertIn("delivery-archive-candidate", codes)
        self.assertIn("legacy-archive-file", codes)

    def test_reparse_delivery_topic_fails_closed_without_traversal(self) -> None:
        project = self.make_project()
        topic = project / "doc" / "1_delivery" / "unsafe-topic"
        topic.mkdir()
        marker = topic / "requirements_unsafe.md"
        marker.write_text("---\nstatus: active\n---\n", encoding="utf-8")

        original = PROJECT_STRUCTURE_CHECK._is_reparse

        def fake_is_reparse(path: Path) -> bool:
            return path == topic or original(path)

        with mock.patch.object(PROJECT_STRUCTURE_CHECK, "_is_reparse", side_effect=fake_is_reparse):
            payload = PROJECT_STRUCTURE_CHECK.inspect_project(project)

        self.assertIn("unsafe-doc-entry", {item["code"] for item in payload["errors"]})
        self.assertEqual(marker.read_text(encoding="utf-8"), "---\nstatus: active\n---\n")

    def test_reparse_project_root_fails_closed(self) -> None:
        project = self.make_project()
        with mock.patch.object(PROJECT_STRUCTURE_CHECK, "_is_reparse", return_value=True):
            payload = PROJECT_STRUCTURE_CHECK.inspect_project(project)

        self.assertEqual(payload["errors"][0]["code"], "unsafe-project-root")

    def test_product_hook_is_registered_mirrored_and_managed(self) -> None:
        hook_paths = (
            ROOT / "templates" / "hooks" / "project_structure_check.py",
            ROOT / ".codex" / "hooks" / "project_structure_check.py",
        )
        hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in hook_paths}
        self.assertEqual(len(hashes), 1)

        registrations = {
            ROOT / ".githooks" / "pre-commit": ".codex/hooks/project_structure_check.py",
            ROOT / "templates" / ".githooks" / "pre-commit": ".codex/hooks/project_structure_check.py",
        }
        for precommit, marker in registrations.items():
            self.assertIn(marker, precommit.read_text(encoding="utf-8"))

        for schema_path in (
            ROOT / "templates" / "managed-skeleton.json",
            ROOT / ".codex" / "managed-skeleton.json",
        ):
            schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
            assets = {item["id"]: item for item in schema["assets"]}
            self.assertEqual(
                assets["codex.hook.project-structure-check"]["target"],
                ".codex/hooks/project_structure_check.py",
            )


if __name__ == "__main__":
    unittest.main()
