from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
CURRENT_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8-sig").strip()
LEGACY_VERSION = "1.4.30"
CLEAN_BASELINE_VERSION = "1.4.31"


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
        self.assertEqual(contract["release_version"], CURRENT_VERSION)
        self.assertEqual(contract["baseline_model"], "current-only")
        self.assertEqual(BASELINE.MINIMUM_CURRENT_BASELINE, (1, 4, 31))
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
        self.template_temporary = tempfile.TemporaryDirectory()
        self.template_base = Path(self.template_temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()
        self.template_temporary.cleanup()

    def apply(self, plan, **kwargs):
        return SYNC.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
            **kwargs,
        )

    def snapshot_tree(self) -> tuple[tuple[str, ...], dict[str, bytes]]:
        directories = tuple(sorted(
            path.relative_to(self.project).as_posix()
            for path in self.project.rglob("*")
            if path.is_dir()
        ))
        files = {
            path.relative_to(self.project).as_posix(): path.read_bytes()
            for path in self.project.rglob("*")
            if path.is_file()
        }
        return directories, files

    def write_project_hook_bundle(self, name: str = "project_risk") -> Path:
        bundle = self.project / ".codex" / "hooks" / name
        bundle.mkdir(parents=True)
        (bundle / "entrypoint.py").write_text(
            "from helper import run\nrun()\n",
            encoding="utf-8",
        )
        (bundle / "helper.py").write_text(
            "def run():\n    return None\n",
            encoding="utf-8",
        )
        hooks = self.project / ".codex" / "hooks.json"
        hooks.write_text(
            json.dumps({
                "hooks": {
                    "SessionStart": [{
                        "matcher": "",
                        "hooks": [{
                            "type": "command",
                            "command": (
                                f".venv/Scripts/python.exe "
                                f".codex/hooks/{name}/entrypoint.py"
                            ),
                        }],
                    }],
                },
            }),
            encoding="utf-8",
        )
        return bundle

    def template_with_removable_asset(
        self,
        name: str,
        strategy: str,
    ) -> tuple[Path, Path, str]:
        installed = self.template_base / f"{name}-installed"
        incoming = self.template_base / f"{name}-incoming"
        shutil.copytree(ROOT / "templates", installed / "templates")
        shutil.copy2(ROOT / "VERSION", installed / "VERSION")
        source = installed / "templates" / "hooks" / "phase2_removed.py"
        asset: dict[str, object] = {
            "id": f"codex.test.phase2-removed-{name}",
            "source": "templates/hooks/phase2_removed.py",
            "target": ".codex/hooks/phase2_removed.py",
            "strategy": strategy,
        }
        if strategy == "merge":
            payload = b'{"managed": true}\n'
            asset["merge_validation"] = {
                "format": "json-subset-current-v1",
                "required": {"managed": True},
            }
        elif strategy == "region":
            payload = b"# BEGIN PHASE2\nmanaged\n# END PHASE2\n"
            asset["region"] = {
                "begin": "# BEGIN PHASE2",
                "end": "# END PHASE2",
                "current_sha256": SYNC._sha256_bytes(payload),
            }
        else:
            payload = b"print('managed phase2 asset')\n"
        source.write_bytes(payload)
        asset["current_sha256"] = SYNC._sha256_bytes(payload)
        contract_path = installed / "templates" / "managed-skeleton.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["assets"].append(asset)
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        shutil.copytree(installed, incoming)
        incoming_contract_path = incoming / "templates" / "managed-skeleton.json"
        incoming_contract = json.loads(
            incoming_contract_path.read_text(encoding="utf-8")
        )
        incoming_contract["assets"] = [
            item
            for item in incoming_contract["assets"]
            if item["id"] != asset["id"]
        ]
        incoming_contract_path.write_text(
            json.dumps(incoming_contract, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return installed, incoming, str(asset["target"])

    def template_at_version(self, version: str) -> Path:
        template = self.template_base / f"baseline-{version}"
        shutil.copytree(ROOT / "templates", template / "templates")
        (template / "VERSION").write_text(version + "\n", encoding="utf-8")
        contract_path = template / "templates" / "managed-skeleton.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["release_version"] = version
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return template

    def test_init_installs_a_verified_current_baseline(self) -> None:
        plan = SYNC.build_plan(self.project, ROOT, "init")
        self.assertFalse(plan.blockers)
        receipt = self.apply(plan)
        self.assertEqual(receipt.status, "completed")
        self.assertTrue(receipt.stamp_written_last)
        report = BASELINE.verify_current_baseline(
            self.project,
            expected_version=CURRENT_VERSION,
        )
        self.assertEqual(report.version, CURRENT_VERSION)
        self.assertEqual(
            (self.project / ".codex" / ".bridgeforge_codex_version")
            .read_text(encoding="utf-8")
            .strip(),
            CURRENT_VERSION,
        )

    def test_explicit_init_rejects_existing_unstamped_skeleton(self) -> None:
        (self.project / ".codex").mkdir()
        plan = SYNC.build_plan(self.project, ROOT, "init")
        self.assertIn("no existing skeleton identity", " ".join(plan.blockers))
        with self.assertRaisesRegex(SYNC.SyncBlocked, "blockers"):
            self.apply(plan)

    def test_old_stamp_routes_to_confirmed_rebuild_and_preserves_manifest(self) -> None:
        codex = self.project / ".codex"
        (codex / "hooks").mkdir(parents=True)
        (codex / "rules").mkdir()
        (codex / "skills" / "project-skill").mkdir(parents=True)
        old_stamp = codex / ".bridgeforge_version"
        old_stamp.write_text(LEGACY_VERSION + "\n", encoding="utf-8")
        project_hook = self.write_project_hook_bundle("project_only")
        project_rule = codex / "rules" / "project_only.md"
        project_skill = codex / "skills" / "project-skill" / "SKILL.md"
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
        self.assertEqual(plan.previous_version, LEGACY_VERSION)
        with self.assertRaisesRegex(
            SYNC.SyncBlocked,
            "confirmed-preservation-manifest",
        ):
            self.apply(plan)
        self.assertEqual(
            old_stamp.read_text(encoding="utf-8").strip(),
            LEGACY_VERSION,
        )

        preserve = tuple(
            item["id"]
            for item in plan.preservation_entries
            if item.get("target")
            in {
                "AGENTS.md",
                ".codex/hooks/project_only",
                ".codex/rules/project_only.md",
            }
        )
        delete = tuple(
            item["id"]
            for item in plan.preservation_entries
            if item.get("disposition") == "user-decision"
            and item["id"] not in preserve
        )
        checkpoints: list[str] = []

        def observe_stamp_order(label: str) -> None:
            checkpoints.append(label)
            if label == "after-preservation-manifest-clear":
                self.assertFalse(
                    (codex / ".bridgeforge_codex_version").exists()
                )

        receipt = self.apply(
            plan,
            confirmed_preservation_manifest=True,
            confirmed_risk=True,
            preserved_project_asset_ids=preserve,
            deleted_project_asset_ids=delete,
            checkpoint=observe_stamp_order,
        )
        self.assertEqual(receipt.mode, "rebuild")
        self.assertFalse(old_stamp.exists())
        self.assertTrue((project_hook / "entrypoint.py").is_file())
        self.assertTrue((project_hook / "helper.py").is_file())
        self.assertTrue(project_rule.is_file())
        self.assertEqual(project_skill.read_bytes(), skill_before)
        self.assertEqual(memory.read_bytes(), memory_before)
        self.assertIn("after-preservation-manifest-clear", checkpoints)
        self.assertIn(
            "PROJECT-ZONE-SENTINEL",
            (self.project / "AGENTS.md").read_text(encoding="utf-8"),
        )
        BASELINE.verify_current_baseline(self.project)

    def test_current_update_is_idempotent(self) -> None:
        self.apply(SYNC.build_plan(self.project, ROOT, "init"))
        plan = SYNC.build_plan(self.project, ROOT, "update")
        self.assertFalse(plan.blockers)
        self.assertEqual(plan.mode, "update")
        self.assertEqual(plan.previous_version, CURRENT_VERSION)
        self.assertEqual(plan.actions, [])
        receipt = self.apply(plan)
        self.assertEqual(receipt.applied, ())

    def test_current_update_deletes_removed_unchanged_whole_asset(self) -> None:
        installed, incoming, relative = self.template_with_removable_asset(
            "whole-success",
            "whole",
        )
        self.apply(SYNC.build_plan(self.project, installed, "init"))
        target = self.project / relative
        self.assertTrue(target.is_file())

        plan = SYNC.build_plan(self.project, incoming, "update")
        self.assertFalse(plan.blockers)
        self.assertIn(
            relative,
            [action.target for action in plan.actions if action.action == "delete"],
        )
        receipt = self.apply(plan)

        self.assertIn("current.remove.codex.test.phase2-removed-whole-success", receipt.applied)
        self.assertFalse(target.exists())
        repeated = SYNC.build_plan(self.project, incoming, "update")
        self.assertFalse(repeated.blockers)
        self.assertEqual(repeated.actions, [])

    def test_removed_whole_asset_drift_blocks_without_writes(self) -> None:
        installed, incoming, relative = self.template_with_removable_asset(
            "whole-drift",
            "whole",
        )
        self.apply(SYNC.build_plan(self.project, installed, "init"))
        target = self.project / relative
        target.write_text("project drift\n", encoding="utf-8")
        before = self.snapshot_tree()

        plan = SYNC.build_plan(self.project, incoming, "update")

        self.assertIn("current baseline drifted", " ".join(plan.blockers))
        self.assertEqual(self.snapshot_tree(), before)

    def test_removed_non_whole_assets_block_without_writes(self) -> None:
        for strategy in ("merge", "region", "seed"):
            with self.subTest(strategy=strategy):
                with tempfile.TemporaryDirectory() as raw:
                    project = Path(raw)
                    installed, incoming, _relative = self.template_with_removable_asset(
                        f"non-whole-{strategy}",
                        strategy,
                    )
                    self.apply(SYNC.build_plan(project, installed, "init"))
                    before = {
                        path.relative_to(project).as_posix(): path.read_bytes()
                        for path in project.rglob("*")
                        if path.is_file()
                    }
                    plan = SYNC.build_plan(project, incoming, "update")
                    self.assertIn("not whole-owned", " ".join(plan.blockers))
                    after = {
                        path.relative_to(project).as_posix(): path.read_bytes()
                        for path in project.rglob("*")
                        if path.is_file()
                    }
                    self.assertEqual(after, before)

    def test_removed_asset_delete_failure_rolls_back(self) -> None:
        installed, incoming, relative = self.template_with_removable_asset(
            "whole-rollback",
            "whole",
        )
        self.apply(SYNC.build_plan(self.project, installed, "init"))
        plan = SYNC.build_plan(self.project, incoming, "update")
        before = self.snapshot_tree()

        def fail_after_removed_delete(label: str) -> None:
            if label.startswith("after-action:current.remove."):
                raise RuntimeError("injected removed-asset failure")

        with self.assertRaisesRegex(SYNC.SyncBlocked, "rolled back"):
            self.apply(plan, checkpoint=fail_after_removed_delete)
        self.assertEqual(self.snapshot_tree(), before)
        self.assertTrue((self.project / relative).is_file())

    def test_duplicate_normalized_target_and_damaged_contract_block(self) -> None:
        for damage in ("duplicate-target", "unknown-strategy"):
            with self.subTest(damage=damage):
                with tempfile.TemporaryDirectory() as raw:
                    project = Path(raw)
                    installed, incoming, relative = self.template_with_removable_asset(
                        f"damage-{damage}",
                        "whole",
                    )
                    self.apply(SYNC.build_plan(project, installed, "init"))
                    contract_path = project / ".codex" / "managed-skeleton.json"
                    contract = json.loads(contract_path.read_text(encoding="utf-8"))
                    asset = next(
                        item for item in contract["assets"]
                        if item["target"] == relative
                    )
                    if damage == "duplicate-target":
                        duplicate = dict(asset)
                        duplicate["id"] = "codex.test.duplicate-normalized-target"
                        duplicate["target"] = relative.replace("/", "\\")
                        contract["assets"].append(duplicate)
                    else:
                        asset["strategy"] = "unknown"
                    contract_path.write_text(
                        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    before = {
                        path.relative_to(project).as_posix(): path.read_bytes()
                        for path in project.rglob("*")
                        if path.is_file()
                    }
                    plan = SYNC.build_plan(project, incoming, "update")
                    self.assertTrue(plan.blockers)
                    if damage == "duplicate-target":
                        self.assertIn(
                            "duplicate",
                            " ".join(plan.blockers),
                        )
                    after = {
                        path.relative_to(project).as_posix(): path.read_bytes()
                        for path in project.rglob("*")
                        if path.is_file()
                    }
                    self.assertEqual(after, before)

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
        (codex / ".bridgeforge_version").write_text(
            LEGACY_VERSION + "\n",
            encoding="utf-8",
        )
        project_hook = self.write_project_hook_bundle("project_only")
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
        delete = tuple(
            item["id"]
            for item in plan.preservation_entries
            if item.get("disposition") == "user-decision"
        )
        receipt = self.apply(
            plan,
            confirmed_preservation_manifest=True,
            confirmed_risk=True,
            preserved_project_asset_ids=(),
            deleted_project_asset_ids=delete,
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
        self.assertNotIn("project_only/entrypoint.py", json.dumps(hooks))

    def test_project_skill_without_description_blocks_before_writes(self) -> None:
        skill = self.project / ".codex" / "skills" / "broken" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        (self.project / SYNC.OBSOLETE_STAMP).write_text(
            LEGACY_VERSION + "\n",
            encoding="utf-8",
        )
        skill.write_text("---\nname: broken\n---\n", encoding="utf-8")
        plan = SYNC.build_plan(self.project, ROOT, "adopt")
        self.assertIn("compatibility check", " ".join(plan.blockers))
        self.assertEqual(skill.read_text(encoding="utf-8"), "---\nname: broken\n---\n")

    def test_fingerprint_and_preservation_ids_fail_closed(self) -> None:
        plan = SYNC.build_plan(self.project, ROOT, "init")
        with self.assertRaisesRegex(SYNC.SyncBlocked, "fingerprint"):
            SYNC.apply_plan(plan, plan_fingerprint="sha256:" + "0" * 64)
        self.assertFalse((self.project / "AGENTS.md").exists())

        stamp = self.project / ".codex" / ".bridgeforge_version"
        stamp.parent.mkdir(parents=True)
        stamp.write_text(LEGACY_VERSION + "\n", encoding="utf-8")
        rebuild = SYNC.build_plan(self.project, ROOT, "auto")
        with self.assertRaisesRegex(SYNC.SyncBlocked, "unknown or non-selectable"):
            self.apply(
                rebuild,
                confirmed_preservation_manifest=True,
                confirmed_risk=True,
                preserved_project_asset_ids=("P:hook:not-present",),
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

        stamp.write_text(CURRENT_VERSION + "\n", encoding="utf-8")
        obsolete = self.project / ".codex" / ".bridgeforge_version"
        obsolete.write_text(LEGACY_VERSION + "\n", encoding="utf-8")
        double = SYNC.build_plan(self.project, ROOT, "update")
        self.assertIn("both current and obsolete", " ".join(double.blockers))

        stamp.unlink()
        obsolete.write_text("not-a-version\n", encoding="utf-8")
        invalid = SYNC.build_plan(self.project, ROOT, "update")
        self.assertIn("not stable SemVer", " ".join(invalid.blockers))

    def test_identity_blocker_never_executes_downstream_memory_lint(self) -> None:
        codex = self.project / ".codex"
        hooks = codex / "hooks"
        memory = codex / "memory" / "engineering"
        hooks.mkdir(parents=True)
        memory.mkdir(parents=True)
        (codex / ".bridgeforge_version").write_text(
            LEGACY_VERSION + "\n",
            encoding="utf-8",
        )
        (codex / ".bridgeforge_codex_version").write_text(
            CURRENT_VERSION + "\n",
            encoding="utf-8",
        )
        (hooks / "memory_lint.py").write_text(
            "from pathlib import Path\nPath('MALICIOUS-WRITE').write_text('ran')\n",
            encoding="utf-8",
        )
        (memory / "note.md").write_text(
            "---\ncategory: engineering\nstatus: active\n"
            "description: valid note\n---\n",
            encoding="utf-8",
        )
        before = self.snapshot_tree()

        plan = SYNC.build_plan(self.project, ROOT, "auto")

        self.assertIn("both current and obsolete", " ".join(plan.blockers))
        self.assertEqual(self.snapshot_tree(), before)
        self.assertFalse((self.project / "MALICIOUS-WRITE").exists())

    def test_both_stamp_names_route_legacy_version_to_rebuild(self) -> None:
        for stamp_name in (SYNC.OBSOLETE_STAMP, SYNC.CURRENT_STAMP):
            with self.subTest(stamp=stamp_name):
                with tempfile.TemporaryDirectory() as raw:
                    project = Path(raw)
                    stamp = project / stamp_name
                    stamp.parent.mkdir(parents=True)
                    stamp.write_text(LEGACY_VERSION + "\n", encoding="utf-8")

                    plan = SYNC.build_plan(project, ROOT, "auto")

                    self.assertFalse(plan.blockers)
                    self.assertEqual(plan.mode, "rebuild")
                    self.assertEqual(plan.previous_version, LEGACY_VERSION)

    def test_obsolete_clean_stamp_migrates_to_current_and_replans_noop(self) -> None:
        baseline_template = self.template_at_version(CLEAN_BASELINE_VERSION)
        self.apply(SYNC.build_plan(self.project, baseline_template, "init"))
        current = self.project / SYNC.CURRENT_STAMP
        obsolete = self.project / SYNC.OBSOLETE_STAMP
        current_plan = SYNC.build_plan(
            self.project,
            baseline_template,
            "update",
        )
        self.assertFalse(current_plan.blockers)
        self.assertEqual(current_plan.mode, "update")
        self.assertEqual(current_plan.previous_version, CLEAN_BASELINE_VERSION)
        current.replace(obsolete)
        self.assertEqual(
            obsolete.read_text(encoding="utf-8").strip(),
            CLEAN_BASELINE_VERSION,
        )

        plan = SYNC.build_plan(self.project, baseline_template, "auto")

        self.assertFalse(plan.blockers)
        self.assertEqual(plan.mode, "update")
        self.assertIn(
            "stamp.remove-obsolete",
            [item.asset_id for item in plan.actions],
        )
        receipt = self.apply(plan)
        self.assertEqual(receipt.mode, "update")
        self.assertFalse(obsolete.exists())
        self.assertEqual(
            current.read_text(encoding="utf-8").strip(),
            CLEAN_BASELINE_VERSION,
        )
        repeated = SYNC.build_plan(
            self.project,
            baseline_template,
            "update",
        )
        self.assertFalse(repeated.blockers)
        self.assertEqual(repeated.actions, [])

    def test_legacy_rebuild_ignores_missing_or_damaged_old_contract(self) -> None:
        for damage in ("missing", "damaged"):
            with self.subTest(damage=damage):
                with tempfile.TemporaryDirectory() as raw:
                    project = Path(raw)
                    stamp = project / SYNC.CURRENT_STAMP
                    stamp.parent.mkdir(parents=True)
                    stamp.write_text(LEGACY_VERSION + "\n", encoding="utf-8")
                    if damage == "damaged":
                        (project / ".codex" / "managed-skeleton.json").write_text(
                            "{not-json}\n",
                            encoding="utf-8",
                        )

                    plan = SYNC.build_plan(project, ROOT, "auto")

                    self.assertFalse(plan.blockers)
                    self.assertEqual(plan.mode, "rebuild")
                    receipt = SYNC.apply_plan(
                        plan,
                        plan_fingerprint=plan.aggregate_fingerprint,
                        confirmed_preservation_manifest=True,
                        confirmed_risk=True,
                    )
                    self.assertEqual(receipt.mode, "rebuild")
                    BASELINE.verify_current_baseline(project)

    def test_unknown_codex_structure_blocks_rebuild_without_writes(self) -> None:
        stamp = self.project / SYNC.OBSOLETE_STAMP
        stamp.parent.mkdir(parents=True)
        stamp.write_text(LEGACY_VERSION + "\n", encoding="utf-8")
        unknown = self.project / ".codex" / "unclassified" / "payload.txt"
        unknown.parent.mkdir()
        unknown.write_text("project data\n", encoding="utf-8")
        before = self.snapshot_tree()

        plan = SYNC.build_plan(self.project, ROOT, "auto")

        self.assertIn("unknown .codex structure", " ".join(plan.blockers))
        self.assertEqual(self.snapshot_tree(), before)

    def test_reparse_codex_directory_blocks_rebuild_without_writes(self) -> None:
        stamp = self.project / SYNC.OBSOLETE_STAMP
        stamp.parent.mkdir(parents=True)
        stamp.write_text(LEGACY_VERSION + "\n", encoding="utf-8")
        linked = self.project / ".codex" / "rules" / "linked"
        linked.mkdir(parents=True)
        before = self.snapshot_tree()
        original = SYNC._is_reparse

        with mock.patch.object(
            SYNC,
            "_is_reparse",
            side_effect=lambda path: path == linked or original(path),
        ):
            plan = SYNC.build_plan(self.project, ROOT, "auto")

        self.assertIn("unsafe .codex structure", " ".join(plan.blockers))
        self.assertEqual(self.snapshot_tree(), before)

    def test_reparse_project_asset_leaf_blocks_rebuild_without_writes(self) -> None:
        sources = {
            "AGENTS.md": ROOT / "templates" / "AGENTS.md",
            ".githooks/pre-commit": (
                ROOT / "templates" / ".githooks" / "pre-commit"
            ),
        }
        original = SYNC._is_reparse
        for relative, source in sources.items():
            with self.subTest(relative=relative):
                with tempfile.TemporaryDirectory() as raw:
                    project = Path(raw)
                    stamp = project / SYNC.OBSOLETE_STAMP
                    stamp.parent.mkdir(parents=True)
                    stamp.write_text(LEGACY_VERSION + "\n", encoding="utf-8")
                    leaf = project / relative
                    leaf.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, leaf)
                    before = leaf.read_bytes()

                    with mock.patch.object(
                        SYNC,
                        "_is_reparse",
                        side_effect=(
                            lambda path, target=leaf: (
                                path == target or original(path)
                            )
                        ),
                    ):
                        plan = SYNC.build_plan(project, ROOT, "auto")

                    self.assertIn("not a plain file", " ".join(plan.blockers))
                    self.assertEqual(leaf.read_bytes(), before)

    def test_scattered_hook_blocks_until_normalized_bundle_is_confirmed(self) -> None:
        codex = self.project / ".codex"
        hooks_root = codex / "hooks"
        hooks_root.mkdir(parents=True)
        (codex / ".bridgeforge_version").write_text(
            LEGACY_VERSION + "\n",
            encoding="utf-8",
        )
        scattered = hooks_root / "legacy_hook.py"
        scattered.write_text("print('legacy')\n", encoding="utf-8")
        (codex / "hooks.json").write_text(
            json.dumps({
                "hooks": {
                    "SessionStart": [{
                        "hooks": [{
                            "type": "command",
                            "command": (
                                ".venv/Scripts/python.exe "
                                ".codex/hooks/legacy_hook.py"
                            ),
                        }],
                    }],
                },
            }),
            encoding="utf-8",
        )
        before = self.snapshot_tree()

        blocked = SYNC.build_plan(self.project, ROOT, "auto")

        self.assertIn("must be normalized first", " ".join(blocked.blockers))
        self.assertEqual(self.snapshot_tree(), before)

        scattered.unlink()
        bundle = self.write_project_hook_bundle("project_legacy")
        plan = SYNC.build_plan(self.project, ROOT, "auto")
        self.assertFalse(plan.blockers)
        bundle_id = next(
            item["id"]
            for item in plan.preservation_entries
            if item.get("target") == ".codex/hooks/project_legacy"
        )
        receipt = self.apply(
            plan,
            confirmed_preservation_manifest=True,
            confirmed_risk=True,
            preserved_project_asset_ids=(bundle_id,),
        )
        self.assertEqual(receipt.mode, "rebuild")
        self.assertTrue((bundle / "entrypoint.py").is_file())
        repeated = SYNC.build_plan(self.project, ROOT, "update")
        self.assertFalse(repeated.blockers)
        self.assertEqual(repeated.actions, [])

    def test_obsolete_stamp_migration_failure_restores_old_identity(self) -> None:
        baseline_template = self.template_at_version(CLEAN_BASELINE_VERSION)
        self.apply(SYNC.build_plan(self.project, baseline_template, "init"))
        current = self.project / SYNC.CURRENT_STAMP
        obsolete = self.project / SYNC.OBSOLETE_STAMP
        current.replace(obsolete)
        plan = SYNC.build_plan(self.project, baseline_template, "update")
        before = self.snapshot_tree()

        def fail_after_obsolete_delete(label: str) -> None:
            if label == "after-action:stamp.remove-obsolete":
                raise RuntimeError("injected obsolete-stamp failure")

        with self.assertRaisesRegex(SYNC.SyncBlocked, "rolled back"):
            self.apply(plan, checkpoint=fail_after_obsolete_delete)
        self.assertEqual(self.snapshot_tree(), before)
        self.assertFalse(current.exists())
        self.assertEqual(
            obsolete.read_text(encoding="utf-8").strip(),
            CLEAN_BASELINE_VERSION,
        )

    def test_reparse_obsolete_stamp_blocks_current_migration_without_writes(
        self,
    ) -> None:
        baseline_template = self.template_at_version(CLEAN_BASELINE_VERSION)
        self.apply(SYNC.build_plan(self.project, baseline_template, "init"))
        current = self.project / SYNC.CURRENT_STAMP
        obsolete = self.project / SYNC.OBSOLETE_STAMP
        current.replace(obsolete)
        before = self.snapshot_tree()
        original = SYNC._is_reparse

        with mock.patch.object(
            SYNC,
            "_is_reparse",
            side_effect=lambda path: path == obsolete or original(path),
        ):
            plan = SYNC.build_plan(
                self.project,
                baseline_template,
                "update",
            )

        self.assertIn("not a plain file", " ".join(plan.blockers))
        self.assertEqual(plan.actions, [])
        self.assertEqual(self.snapshot_tree(), before)

    def test_stamp_identity_errors_block_without_writes(self) -> None:
        cases = (
            (SYNC.CURRENT_STAMP, "999.0.0", False, "newer than"),
            (SYNC.OBSOLETE_STAMP, "invalid", False, "not stable SemVer"),
            (SYNC.CURRENT_STAMP, "", True, "not a plain file"),
        )
        for stamp_name, version, directory, expected in cases:
            with self.subTest(stamp=stamp_name, version=version):
                with tempfile.TemporaryDirectory() as raw:
                    project = Path(raw)
                    stamp = project / stamp_name
                    stamp.parent.mkdir(parents=True)
                    if directory:
                        stamp.mkdir()
                    else:
                        stamp.write_text(version + "\n", encoding="utf-8")
                    before = tuple(sorted(
                        path.relative_to(project).as_posix()
                        for path in project.rglob("*")
                    ))

                    plan = SYNC.build_plan(project, ROOT, "auto")

                    self.assertIn(expected, " ".join(plan.blockers))
                    after = tuple(sorted(
                        path.relative_to(project).as_posix()
                        for path in project.rglob("*")
                    ))
                    self.assertEqual(after, before)

    def test_unknown_agents_and_precommit_markers_block_rebuild(self) -> None:
        stamp = self.project / SYNC.OBSOLETE_STAMP
        stamp.parent.mkdir(parents=True)
        stamp.write_text(LEGACY_VERSION + "\n", encoding="utf-8")
        (self.project / "AGENTS.md").write_text(
            "# project without canonical ownership markers\n",
            encoding="utf-8",
        )
        precommit = self.project / ".githooks" / "pre-commit"
        precommit.parent.mkdir()
        precommit.write_text(
            "# <<< PROJECT_EXTENSION_END\necho project\n"
            "# >>> PROJECT_EXTENSION_BEGIN\n",
            encoding="utf-8",
        )
        before = self.snapshot_tree()

        plan = SYNC.build_plan(self.project, ROOT, "auto")

        joined = " ".join(plan.blockers)
        self.assertIn("AGENTS project markers are invalid", joined)
        self.assertIn("pre-commit project-extension markers are invalid", joined)
        self.assertEqual(self.snapshot_tree(), before)

    def test_project_hook_bundle_and_registration_must_be_a_closed_pair(self) -> None:
        stamp = self.project / SYNC.OBSOLETE_STAMP
        stamp.parent.mkdir(parents=True)
        stamp.write_text(LEGACY_VERSION + "\n", encoding="utf-8")
        hooks = self.project / ".codex" / "hooks.json"
        hooks.write_text(
            json.dumps({
                "hooks": {
                    "SessionStart": [{
                        "hooks": [{
                            "type": "command",
                            "command": (
                                ".venv/Scripts/python.exe "
                                ".codex/hooks/project_missing/entrypoint.py"
                            ),
                        }],
                    }],
                },
            }),
            encoding="utf-8",
        )
        plan = SYNC.build_plan(self.project, ROOT, "auto")
        self.assertIn("has no canonical bundle", " ".join(plan.blockers))

    def test_noncanonical_project_hook_commands_are_not_reparsed(self) -> None:
        for command in (
            r".venv\Scripts\python.exe .codex\hooks\project_risk\entrypoint.py",
            (
                "powershell -NoProfile -Command "
                "'.venv/Scripts/python.exe .codex/hooks/project_risk/entrypoint.py'"
            ),
            r"C:\project\.venv\Scripts\python.exe C:\project\hook.py",
        ):
            with self.subTest(command=command):
                payload = json.dumps({
                    "hooks": {
                        "SessionStart": [{
                            "hooks": [{"type": "command", "command": command}],
                        }],
                    },
                }).encode("utf-8")
                with self.assertRaisesRegex(
                    SYNC.SyncBlocked,
                    "not a canonical Python command",
                ):
                    SYNC._project_hook_projection(payload)

    def test_rebuild_requires_explicit_disposition_for_every_project_asset(self) -> None:
        stamp = self.project / SYNC.OBSOLETE_STAMP
        stamp.parent.mkdir(parents=True)
        stamp.write_text(LEGACY_VERSION + "\n", encoding="utf-8")
        self.write_project_hook_bundle()
        plan = SYNC.build_plan(self.project, ROOT, "auto")
        before = self.snapshot_tree()
        with self.assertRaisesRegex(SYNC.SyncBlocked, "explicit preserve/delete"):
            self.apply(
                plan,
            confirmed_preservation_manifest=True,
                confirmed_risk=True,
            )
        self.assertEqual(self.snapshot_tree(), before)

    def test_bundle_delete_failure_restores_the_complete_directory(self) -> None:
        stamp = self.project / SYNC.OBSOLETE_STAMP
        stamp.parent.mkdir(parents=True)
        stamp.write_text(LEGACY_VERSION + "\n", encoding="utf-8")
        self.write_project_hook_bundle()
        plan = SYNC.build_plan(self.project, ROOT, "auto")
        delete = tuple(
            item["id"]
            for item in plan.preservation_entries
            if item.get("disposition") == "user-decision"
        )
        before = self.snapshot_tree()

        def fail_after_bundle_delete(label: str) -> None:
            if label == "after-project-hook-bundle-deletions":
                raise RuntimeError("injected bundle failure")

        with self.assertRaisesRegex(SYNC.SyncBlocked, "rolled back"):
            self.apply(
                plan,
                confirmed_preservation_manifest=True,
                confirmed_risk=True,
                deleted_project_asset_ids=delete,
                checkpoint=fail_after_bundle_delete,
            )
        self.assertEqual(self.snapshot_tree(), before)

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

    def test_current_stamp_drift_during_apply_is_not_absorbed(self) -> None:
        self.apply(SYNC.build_plan(self.project, ROOT, "init"))
        plan = SYNC.build_plan(self.project, ROOT, "update")
        stamp = self.project / SYNC.CURRENT_STAMP
        self.assertEqual(
            plan.current_stamp_before_sha256,
            SYNC._sha256_path(stamp),
        )

        def drift_stamp_after_index(label: str) -> None:
            if label == "after-memory-index":
                stamp.write_text("1.4.30\n", encoding="utf-8")

        with self.assertRaisesRegex(SYNC.SyncBlocked, "rolled back"):
            self.apply(plan, checkpoint=drift_stamp_after_index)

        self.assertEqual(stamp.read_text(encoding="utf-8").strip(), "1.4.30")


if __name__ == "__main__":
    unittest.main()
