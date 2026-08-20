from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SYNC = load_module(
    "bridgeforge_current_project_sync",
    ROOT / "scripts" / "bridgeforge_codex_project_sync.py",
)
BASELINE = load_module(
    "bridgeforge_current_baseline",
    ROOT / "templates" / "scripts" / "current_baseline.py",
)


class CurrentBaselineContractTests(unittest.TestCase):
    def test_contract_is_small_and_contains_no_history_model(self) -> None:
        path = ROOT / "templates" / "managed-skeleton.json"
        contract = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(contract["schema_version"], 3)
        self.assertEqual(contract["release_version"], "1.4.28")
        self.assertEqual(contract["baseline_model"], "current-only")
        self.assertNotIn("minimum_supported_version", contract)
        text = path.read_text(encoding="utf-8")
        self.assertLessEqual(len(text.splitlines()), 2148)
        for token in (
            "historical_sha256",
            "trusted_legacy_sha256",
            "retired_sections",
            "retirement_guidance",
            "rule_index_check.py",
            "rule_size_check.py",
        ):
            self.assertNotIn(token, text)

    def test_core_sync_code_meets_reduction_gate(self) -> None:
        paths = (
            ROOT / "scripts" / "bridgeforge_codex_project_sync.py",
            ROOT / "templates" / "scripts" / "version_release.py",
        )
        lines = sum(
            len(path.read_text(encoding="utf-8").splitlines()) for path in paths
        )
        self.assertLessEqual(lines, 6912)

    def test_contract_rejects_unknown_fields_and_source_escape(self) -> None:
        contract = json.loads(
            (ROOT / "templates" / "managed-skeleton.json").read_text(
                encoding="utf-8"
            )
        )
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "contract.json"
            contract["foo_by_version"] = {}
            path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaises(BASELINE.BaselineError):
                BASELINE.load_contract(path)
            contract.pop("foo_by_version")
            contract["assets"][0]["source"] = "../escape"
            path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaisesRegex(BASELINE.BaselineError, "escapes"):
                BASELINE.load_contract(path)


class CurrentProjectSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.project = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def apply(self, plan, **kwargs):
        return SYNC.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
            **kwargs,
        )

    def test_init_installs_a_verified_current_baseline(self) -> None:
        plan = SYNC.build_plan(self.project, ROOT, "init")
        self.assertFalse(plan.blockers)
        receipt = self.apply(plan)
        self.assertEqual(receipt.status, "completed")
        self.assertTrue(receipt.stamp_written_last)
        report = BASELINE.verify_current_baseline(
            self.project,
            expected_version="1.4.28",
        )
        self.assertEqual(report.version, "1.4.28")
        self.assertEqual(
            (self.project / ".codex" / ".bridgeforge_codex_version")
            .read_text(encoding="utf-8")
            .strip(),
            "1.4.28",
        )

    def test_explicit_init_rejects_existing_unstamped_skeleton(self) -> None:
        (self.project / ".codex").mkdir()
        plan = SYNC.build_plan(self.project, ROOT, "init")
        self.assertIn("no existing skeleton identity", " ".join(plan.blockers))
        with self.assertRaisesRegex(SYNC.SyncBlocked, "blockers"):
            self.apply(plan)

    def test_old_stamp_routes_to_confirmed_rebuild_and_preserves_whitelist(self) -> None:
        codex = self.project / ".codex"
        (codex / "hooks").mkdir(parents=True)
        (codex / "rules").mkdir()
        (codex / "skills" / "project-skill").mkdir(parents=True)
        old_stamp = codex / ".bridgeforge_version"
        old_stamp.write_text("1.4.27\n", encoding="utf-8")
        project_hook = codex / "hooks" / "project_only.py"
        project_rule = codex / "rules" / "project_only.md"
        project_skill = codex / "skills" / "project-skill" / "SKILL.md"
        project_hook.write_text("print('project hook')\n", encoding="utf-8")
        project_rule.write_text("# project rule\n", encoding="utf-8")
        project_skill.write_text(
            "---\nname: project-skill\ndescription: project semantics\n---\n\n# Project Skill\n",
            encoding="utf-8",
        )
        memory = codex / "memory" / "engineering" / "project.md"
        memory.parent.mkdir(parents=True)
        memory.write_text(
            "---\ncategory: engineering\nstatus: active\n"
            "description: project memory semantics\n---\n\n# Project\n",
            encoding="utf-8",
        )
        agents = (ROOT / "templates" / "AGENTS.md").read_text(encoding="utf-8")
        agents = agents.replace(
            "> 本区由项目完全所有。",
            "> 本区由项目完全所有。\n\nPROJECT-ZONE-SENTINEL",
            1,
        )
        (self.project / "AGENTS.md").write_text(agents, encoding="utf-8")
        skill_before = project_skill.read_bytes()
        memory_before = memory.read_bytes()

        plan = SYNC.build_plan(self.project, ROOT, "auto")
        self.assertEqual(plan.mode, "rebuild")
        self.assertEqual(plan.previous_version, "1.4.27")
        with self.assertRaisesRegex(SYNC.SyncBlocked, "confirmed-whitelist"):
            self.apply(plan)
        self.assertEqual(old_stamp.read_text(encoding="utf-8").strip(), "1.4.27")

        preserve = tuple(
            item["id"]
            for item in plan.project_requirements
            if item.get("target")
            in {
                "AGENTS.md",
                ".codex/hooks/project_only.py",
                ".codex/rules/project_only.md",
            }
        )
        receipt = self.apply(
            plan,
            confirmed_whitelist=True,
            confirmed_risk=True,
            preserved_project_asset_ids=preserve,
        )
        self.assertEqual(receipt.mode, "rebuild")
        self.assertFalse(old_stamp.exists())
        self.assertTrue(project_hook.is_file())
        self.assertTrue(project_rule.is_file())
        self.assertEqual(project_skill.read_bytes(), skill_before)
        self.assertEqual(memory.read_bytes(), memory_before)
        self.assertIn(
            "PROJECT-ZONE-SENTINEL",
            (self.project / "AGENTS.md").read_text(encoding="utf-8"),
        )
        BASELINE.verify_current_baseline(self.project)

    def test_current_update_is_idempotent(self) -> None:
        self.apply(SYNC.build_plan(self.project, ROOT, "init"))
        plan = SYNC.build_plan(self.project, ROOT, "update")
        self.assertFalse(plan.blockers)
        self.assertEqual(plan.actions, [])
        receipt = self.apply(plan)
        self.assertEqual(receipt.applied, ())

    def test_downstream_merge_and_markdown_projections_fail_closed(self) -> None:
        self.apply(SYNC.build_plan(self.project, ROOT, "init"))
        settings_path = self.project / ".codex" / "settings.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        settings["permissions"]["defaultMode"] = "bypassPermissions"
        settings_path.write_text(json.dumps(settings), encoding="utf-8")
        with self.assertRaisesRegex(BASELINE.BaselineError, "drifted"):
            BASELINE.verify_current_baseline(self.project)

        settings_path.write_bytes((ROOT / "templates" / "settings.json").read_bytes())
        readme = self.project / "doc" / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8").replace(
                "系统当前架构、关键接口、数据流与 ADR",
                "drifted managed row",
                1,
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(BASELINE.BaselineError, "Markdown projection"):
            BASELINE.verify_current_baseline(self.project)

    def test_hooks_reject_duplicate_json_and_unknown_managed_id(self) -> None:
        self.apply(SYNC.build_plan(self.project, ROOT, "init"))
        hooks_path = self.project / ".codex" / "hooks.json"
        canonical = hooks_path.read_text(encoding="utf-8")
        hooks_path.write_text(
            '{"hooks": {}, "hooks": {}}\n',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(BASELINE.BaselineError, "duplicate JSON key"):
            BASELINE.verify_current_baseline(self.project)

        hooks = json.loads(canonical)
        hooks["hooks"].setdefault("SessionStart", []).append(
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": "echo invalid",
                        "bridgeforgeCodexId": "bridgeforge-codex.project-hook.v1:unknown",
                    }
                ],
            }
        )
        hooks_path.write_text(json.dumps(hooks), encoding="utf-8")
        with self.assertRaisesRegex(BASELINE.BaselineError, "identity set"):
            BASELINE.verify_current_baseline(self.project)

    def test_rebuild_drops_every_unselected_project_surface(self) -> None:
        codex = self.project / ".codex"
        (codex / "hooks").mkdir(parents=True)
        (codex / ".bridgeforge_version").write_text("1.4.27\n", encoding="utf-8")
        project_hook = codex / "hooks" / "project_only.py"
        project_hook.write_text("print('project')\n", encoding="utf-8")
        (codex / "hooks.json").write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [
                            {
                                "matcher": "",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": ".venv/Scripts/python.exe .codex/hooks/project_only.py",
                                    }
                                ],
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        (codex / "settings.json").write_text(
            '{"projectOnly": true}\n', encoding="utf-8"
        )
        agents = (ROOT / "templates" / "AGENTS.md").read_text(encoding="utf-8")
        (self.project / "AGENTS.md").write_text(
            agents.replace(
                "> 本区由项目完全所有。",
                "> 本区由项目完全所有。\n\nDROP-ME",
                1,
            ),
            encoding="utf-8",
        )
        precommit = self.project / ".githooks" / "pre-commit"
        precommit.parent.mkdir()
        precommit.write_text(
            (ROOT / "templates" / ".githooks" / "pre-commit")
            .read_text(encoding="utf-8")
            .replace(
                "# >>> PROJECT_EXTENSION_BEGIN\n",
                "# >>> PROJECT_EXTENSION_BEGIN\necho project-only\n",
            ),
            encoding="utf-8",
        )

        plan = SYNC.build_plan(self.project, ROOT, "auto")
        receipt = self.apply(
            plan,
            confirmed_whitelist=True,
            confirmed_risk=True,
            preserved_project_asset_ids=(),
        )
        self.assertEqual(receipt.mode, "rebuild")
        self.assertFalse(project_hook.exists())
        self.assertNotIn("DROP-ME", (self.project / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertNotIn(
            "project-only",
            (self.project / ".githooks" / "pre-commit").read_text(encoding="utf-8"),
        )
        settings = json.loads(
            (self.project / ".codex" / "settings.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("projectOnly", settings)
        hooks = json.loads(
            (self.project / ".codex" / "hooks.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("project_only.py", json.dumps(hooks))

    def test_project_skill_without_description_blocks_before_writes(self) -> None:
        skill = self.project / ".codex" / "skills" / "broken" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("---\nname: broken\n---\n", encoding="utf-8")
        with self.assertRaisesRegex(SYNC.SyncBlocked, "compatibility check"):
            SYNC.build_plan(self.project, ROOT, "adopt")
        self.assertEqual(skill.read_text(encoding="utf-8"), "---\nname: broken\n---\n")

    def test_fingerprint_and_whitelist_ids_fail_closed(self) -> None:
        plan = SYNC.build_plan(self.project, ROOT, "init")
        with self.assertRaisesRegex(SYNC.SyncBlocked, "fingerprint"):
            SYNC.apply_plan(plan, plan_fingerprint="sha256:" + "0" * 64)
        self.assertFalse((self.project / "AGENTS.md").exists())

        stamp = self.project / ".codex" / ".bridgeforge_version"
        stamp.parent.mkdir(parents=True)
        stamp.write_text("1.4.27\n", encoding="utf-8")
        rebuild = SYNC.build_plan(self.project, ROOT, "auto")
        with self.assertRaisesRegex(SYNC.SyncBlocked, "unknown project asset"):
            self.apply(
                rebuild,
                confirmed_whitelist=True,
                confirmed_risk=True,
                preserved_project_asset_ids=("W:hook:not-present",),
            )
        self.assertTrue(stamp.is_file())

    def test_current_drift_and_stamp_identity_failures_block_without_writes(self) -> None:
        self.apply(SYNC.build_plan(self.project, ROOT, "init"))
        target = self.project / ".codex" / "hooks" / "requirements_check.py"
        target.write_text("# drift\n", encoding="utf-8")
        before = target.read_bytes()
        drifted = SYNC.build_plan(self.project, ROOT, "update")
        self.assertTrue(drifted.blockers)
        self.assertEqual(target.read_bytes(), before)

        target.write_bytes(
            (ROOT / "templates" / "hooks" / "requirements_check.py").read_bytes()
        )
        stamp = self.project / ".codex" / ".bridgeforge_codex_version"
        stamp.unlink()
        missing = SYNC.build_plan(self.project, ROOT, "update")
        self.assertIn("no recognized version stamp", " ".join(missing.blockers))
        self.assertFalse(stamp.exists())

        stamp.write_text("1.4.28\n", encoding="utf-8")
        obsolete = self.project / ".codex" / ".bridgeforge_version"
        obsolete.write_text("1.4.27\n", encoding="utf-8")
        double = SYNC.build_plan(self.project, ROOT, "update")
        self.assertIn("both current and obsolete", " ".join(double.blockers))

        stamp.unlink()
        obsolete.write_text("not-a-version\n", encoding="utf-8")
        invalid = SYNC.build_plan(self.project, ROOT, "update")
        self.assertIn("not stable SemVer", " ".join(invalid.blockers))

    def test_transaction_failure_rolls_back_every_write(self) -> None:
        plan = SYNC.build_plan(self.project, ROOT, "init")

        def fail_after_first_write(label: str) -> None:
            if label.startswith("after-action:"):
                raise RuntimeError("injected failure")

        with self.assertRaisesRegex(SYNC.SyncBlocked, "rolled back"):
            SYNC.apply_plan(
                plan,
                plan_fingerprint=plan.aggregate_fingerprint,
                checkpoint=fail_after_first_write,
            )
        self.assertFalse((self.project / "AGENTS.md").exists())
        self.assertFalse((self.project / ".codex").exists())

    def test_current_config_health_failure_blocks_apply(self) -> None:
        self.apply(SYNC.build_plan(self.project, ROOT, "init"))
        local = self.project / ".codex" / "settings.local.json"
        local.write_text('{"hooks": {"SessionStart": []}}\n', encoding="utf-8")
        plan = SYNC.build_plan(self.project, ROOT, "update")
        with self.assertRaisesRegex(SYNC.SyncBlocked, "config health"):
            self.apply(plan)
        self.assertTrue(local.is_file())

    def test_post_index_validator_failure_rolls_back_derived_memory(self) -> None:
        plan = SYNC.build_plan(self.project, ROOT, "init")
        def fail_after_index(label: str) -> None:
            if label == "after-memory-index":
                raise RuntimeError("post-index failure")

        with self.assertRaisesRegex(SYNC.SyncBlocked, "rolled back"):
            SYNC.apply_plan(
                plan,
                plan_fingerprint=plan.aggregate_fingerprint,
                checkpoint=fail_after_index,
            )

        self.assertFalse((self.project / "AGENTS.md").exists())
        self.assertFalse((self.project / ".codex" / "memory" / "MEMORY.md").exists())
        self.assertFalse(
            (self.project / ".codex" / "memory" / "MEMORY_COLD.md").exists()
        )


if __name__ == "__main__":
    unittest.main()
