from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "bridgeforge_project_sync.py"
SPEC = importlib.util.spec_from_file_location("bridgeforge_project_sync", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
sync = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sync
SPEC.loader.exec_module(sync)

MANIFEST_SCRIPT = ROOT / "scripts" / "rebuild_shared_skill_manifest.py"
MANIFEST_SPEC = importlib.util.spec_from_file_location(
    "rebuild_shared_skill_manifest",
    MANIFEST_SCRIPT,
)
assert MANIFEST_SPEC is not None and MANIFEST_SPEC.loader is not None
manifest_builder = importlib.util.module_from_spec(MANIFEST_SPEC)
sys.modules[MANIFEST_SPEC.name] = manifest_builder
MANIFEST_SPEC.loader.exec_module(manifest_builder)


def git_blob(revision: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{revision}:{path}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr.decode("utf-8", errors="replace"))
    return result.stdout


class BridgeForgeProjectSyncTests(unittest.TestCase):
    def make_project(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name)

    def apply_init(self, project: Path) -> sync.Receipt:
        plan = sync.build_plan(project, ROOT, "init")
        self.assertFalse(plan.blockers)
        self.assertFalse(plan.risk_actions)
        return sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
        )

    def test_schema_v2_is_explicit_and_hashes_supported_baselines(self) -> None:
        contract = json.loads(
            (ROOT / "templates/codex/managed-skeleton.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(contract["schema_version"], 2)
        self.assertEqual(contract["minimum_supported_version"], "0.86.0")
        ids: set[str] = set()
        targets: set[str] = set()
        strategies: set[str] = set()
        for asset in contract["assets"]:
            self.assertNotIn(asset["id"], ids)
            self.assertNotIn(asset["target"].casefold(), targets)
            self.assertFalse(any(char in asset["target"] for char in "*?["))
            self.assertFalse(any(char in str(asset.get("source", "")) for char in "*?["))
            strategies.add(asset["strategy"])
            ids.add(asset["id"])
            targets.add(asset["target"].casefold())
        self.assertEqual(strategies, {"whole", "merge", "region", "retirement"})
        active = next(item for item in contract["assets"] if item["id"] == "root.agents")
        self.assertIn("0.86.0", active["historical_sha256"])
        self.assertIn("0.90.0", active["historical_sha256"])
        retired = next(
            item
            for item in contract["assets"]
            if item["id"] == "codex.retired.model-policy-check"
        )
        self.assertNotIn("source", retired)
        self.assertIn("0.90.0", retired["historical_sha256"])

        expected_releases = {
            "0.86.0",
            "0.86.1",
            "0.86.2",
            "0.86.4",
            "0.86.6",
            "0.86.7",
            "0.87.0",
            "0.88.0",
            "0.88.2",
            "0.88.4",
            "0.90.0",
        }
        self.assertEqual(
            set(manifest_builder._baseline_revisions(ROOT)),
            expected_releases,
        )
        hooks_merge = next(
            item
            for item in contract["assets"]
            if item["id"] == "codex.script.hooks-merge"
        )
        historical_hashes = {
            digest
            for values in hooks_merge["historical_sha256"].values()
            for digest in values
        }
        self.assertIn(
            "sha256:8b67d0683be8ac43e0590bd10dca46298e53249e3f9dacd5f2e5bccb16660633",
            historical_hashes,
        )

    def test_contract_dogfood_manifest_and_parity_are_current(self) -> None:
        template_contract = ROOT / "templates/codex/managed-skeleton.json"
        self.assertEqual(
            json.loads(template_contract.read_text(encoding="utf-8-sig")),
            json.loads(
                (ROOT / ".codex/managed-skeleton.json").read_text(
                    encoding="utf-8-sig"
                )
            ),
        )
        for retired in (
            "model_policy_check.py",
            "version_check.py",
        ):
            self.assertFalse((ROOT / "templates/codex/hooks" / retired).exists())
            self.assertFalse((ROOT / ".codex/hooks" / retired).exists())
        self.assertFalse((ROOT / "templates/codex/scripts/bridgeforge_switch.py").exists())
        self.assertFalse((ROOT / ".codex/scripts/bridgeforge_switch.py").exists())
        report = (
            ROOT / "doc/0_architecture/design/codex-harness-parity.md"
        ).read_text(encoding="utf-8")
        self.assertIn("状态：`OK`", report)
        self.assertIn("Claude 有但 Codex 缺失：0", report)
        self.assertIn("未登记的 Codex-only 文件：0", report)
        self.assertIn("未分类：0", report)

    def test_init_validates_and_writes_stamp_last(self) -> None:
        project = self.make_project()
        writes: list[str] = []
        original = sync._atomic_write

        def record(path: Path, payload: bytes, root: Path) -> None:
            writes.append(path.relative_to(root).as_posix())
            original(path, payload, root)

        with mock.patch.object(sync, "_atomic_write", side_effect=record):
            receipt = self.apply_init(project)
        self.assertEqual(receipt.status, "completed")
        self.assertTrue(receipt.stamp_written_last)
        self.assertEqual(writes[-1], ".codex/.bridgeforge_version")
        self.assertEqual(
            (project / ".codex/.bridgeforge_version").read_text(encoding="utf-8"),
            (ROOT / "VERSION").read_text(encoding="utf-8"),
        )

    def test_published_090_asset_is_safe_fast_forward(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        routing = project / ".codex/skill-routing.json"
        routing.write_bytes(
            git_blob(
                "3ab876c0b2570d8f8a716c18d29542468fc91087",
                "templates/codex/skill-routing.json",
            )
        )
        (project / ".codex/.bridgeforge_version").write_text(
            "0.90.0\n", encoding="utf-8"
        )
        plan = sync.build_plan(project, ROOT, "update")
        action = next(
            item for item in plan.safe_actions if item.asset_id == "codex.skill-routing"
        )
        self.assertEqual(action.action, "replace")
        sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        self.assertIn(
            "create-worktree",
            routing.read_text(encoding="utf-8"),
        )

    def test_modified_whole_file_is_gap_and_is_preserved(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        target = project / ".codex/rules/architecture.md"
        target.write_text(
            target.read_text(encoding="utf-8") + "\nproject customization\n",
            encoding="utf-8",
        )
        before = target.read_bytes()
        stamp = project / ".codex/.bridgeforge_version"
        stamp.write_text("0.90.0\n", encoding="utf-8")
        plan = sync.build_plan(project, ROOT, "update")
        self.assertTrue(
            any(item.asset_id == "codex.rule.architecture" for item in plan.gaps)
        )
        receipt = sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        self.assertEqual(receipt.status, "completed_with_gaps")
        self.assertFalse(receipt.stamp_written_last)
        self.assertEqual(stamp.read_text(encoding="utf-8"), "0.90.0\n")
        self.assertEqual(target.read_bytes(), before)

    def test_memory_schema_is_planned_applied_and_rolled_back_transactionally(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        memory = project / ".codex/memory"
        loose = memory / "loose.md"
        loose.write_text(
            "---\ncategory: domain\nstatus: active\n"
            "description: legacy layout\n---\nbody\n",
            encoding="utf-8",
        )
        plan = sync.build_plan(project, ROOT, "update")
        self.assertTrue(any(item.asset_id == sync.MEMORY_ACTION_ID for item in plan.risk_actions))

        declined = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
            decline_risk=True,
        )
        self.assertEqual(declined.status, "completed_with_gaps")
        self.assertFalse(declined.stamp_written_last)
        self.assertTrue(loose.is_file())
        self.assertFalse((memory / "domain/loose.md").exists())

        def fail(name: str) -> None:
            if name == "before-validate":
                raise RuntimeError("simulated failure after memory apply")

        with self.assertRaisesRegex(sync.SyncBlocked, "rolled back"):
            sync.apply_plan(
                plan,
                plan_fingerprint=plan.aggregate_fingerprint,
                confirmed_risk=True,
                checkpoint=fail,
            )
        self.assertTrue(loose.is_file())
        self.assertFalse((memory / "domain/loose.md").exists())

        retry = sync.build_plan(project, ROOT, "update")
        receipt = sync.apply_plan(
            retry,
            plan_fingerprint=retry.aggregate_fingerprint,
            confirmed_risk=True,
        )
        self.assertEqual(receipt.status, "completed")
        self.assertFalse(loose.exists())
        self.assertTrue((memory / "domain/loose.md").is_file())

    def test_ambiguous_memory_is_a_preserved_gap_not_a_false_ready_state(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        memory = project / ".codex/memory"
        invalid = memory / "topics/bad_slug/summary.md"
        invalid.parent.mkdir(parents=True)
        payload = (
            "---\ncategory: topic\ntopic: bad_slug\nstatus: active\n"
            "description: ambiguous topic\n---\nbody\n"
        ).encode("utf-8")
        invalid.write_bytes(payload)
        plan = sync.build_plan(project, ROOT, "update")
        self.assertTrue(any(item.asset_id == sync.MEMORY_ACTION_ID for item in plan.gaps))
        receipt = sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        self.assertEqual(receipt.status, "completed_with_gaps")
        self.assertEqual(receipt.readiness, "degraded")
        self.assertFalse(receipt.stamp_written_last)
        self.assertEqual(invalid.read_bytes(), payload)

    def test_third_party_hook_and_project_extension_survive_merge(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        hooks_path = project / ".codex/hooks.json"
        hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
        hooks["hooks"]["SessionStart"].append(
            {"matcher": "third-party", "hooks": [{"type": "command", "command": "third-party"}]}
        )
        hooks_path.write_text(
            json.dumps(hooks, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        precommit = project / ".githooks/pre-commit"
        payload = precommit.read_bytes()
        payload = payload.replace(
            b"# >>> PROJECT_EXTENSION_BEGIN\n",
            b"# >>> PROJECT_EXTENSION_BEGIN\n# project-owned extension\n",
            1,
        )
        payload = payload.replace(b"run_exit2_hook", b"run_exit2_hook ", 1)
        precommit.write_bytes(payload)

        plan = sync.build_plan(project, ROOT, "update")
        self.assertTrue(any(item.asset_id == "codex.precommit" for item in plan.safe_actions))
        sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        merged = json.loads(hooks_path.read_text(encoding="utf-8"))
        self.assertTrue(
            any(
                item.get("matcher") == "third-party"
                for item in merged["hooks"]["SessionStart"]
            )
        )
        self.assertIn(b"# project-owned extension", precommit.read_bytes())

    def test_retirement_requires_one_risk_decision_and_preserves_modifications(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        model = project / ".codex/hooks/model_policy_check.py"
        version = project / ".codex/hooks/version_check.py"
        model.write_bytes(
            git_blob(
                "3ab876c0b2570d8f8a716c18d29542468fc91087",
                "templates/codex/hooks/model_policy_check.py",
            )
        )
        version.write_bytes(
            git_blob(
                "3ab876c0b2570d8f8a716c18d29542468fc91087",
                "templates/codex/hooks/version_check.py",
            )
        )
        stamp = project / ".codex/.bridgeforge_version"
        stamp.write_text("0.90.0\n", encoding="utf-8")
        plan = sync.build_plan(project, ROOT, "update")
        self.assertEqual(len(plan.risk_actions), 2)
        with self.assertRaisesRegex(sync.SyncBlocked, "single --confirmed-risk"):
            sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        self.assertTrue(model.exists() and version.exists())

        declined = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
            decline_risk=True,
        )
        self.assertEqual(declined.status, "completed_with_gaps")
        self.assertFalse(declined.stamp_written_last)
        self.assertEqual(stamp.read_text(encoding="utf-8"), "0.90.0\n")
        self.assertTrue(model.exists() and version.exists())

        receipt = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
            confirmed_risk=True,
        )
        self.assertEqual(len(receipt.risk_applied), 2)
        self.assertFalse(model.exists() or version.exists())

        model.write_text("manual replacement\n", encoding="utf-8")
        gap_plan = sync.build_plan(project, ROOT, "update")
        self.assertTrue(
            any(
                item.asset_id == "codex.retired.model-policy-check"
                for item in gap_plan.gaps
            )
        )
        self.assertFalse(
            any(
                item.asset_id == "codex.retired.model-policy-check"
                for item in gap_plan.actions
            )
        )

    def test_fingerprint_drift_has_zero_transaction_writes(self) -> None:
        project = self.make_project()
        plan = sync.build_plan(project, ROOT, "init")
        (project / "AGENTS.md").write_text("external change\n", encoding="utf-8")
        with self.assertRaisesRegex(sync.SyncBlocked, "fingerprint drifted"):
            sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        self.assertFalse((project / ".codex").exists())
        self.assertEqual(
            (project / "AGENTS.md").read_text(encoding="utf-8"),
            "external change\n",
        )

    def test_failures_at_each_apply_phase_roll_back_owned_state(self) -> None:
        checkpoints = (
            "after-action:contract.managed-skeleton",
            "before-validate",
            "before-stamp",
            "after-stamp",
        )
        for failure_point in checkpoints:
            with self.subTest(failure_point=failure_point):
                project = self.make_project()
                plan = sync.build_plan(project, ROOT, "init")

                def fail(name: str) -> None:
                    if name == failure_point:
                        raise RuntimeError(f"simulated {name}")

                with self.assertRaisesRegex(sync.SyncBlocked, "rolled back"):
                    sync.apply_plan(
                        plan,
                        plan_fingerprint=plan.aggregate_fingerprint,
                        checkpoint=fail,
                    )
                self.assertFalse((project / ".codex/.bridgeforge_version").exists())
                self.assertFalse((project / ".codex/managed-skeleton.json").exists())

    def test_pre_086_update_is_blocked(self) -> None:
        project = self.make_project()
        (project / ".codex").mkdir()
        (project / ".codex/.bridgeforge_version").write_text(
            "0.85.9\n", encoding="utf-8"
        )
        plan = sync.build_plan(project, ROOT, "update")
        self.assertTrue(plan.blockers)
        self.assertIn("predates", " ".join(plan.blockers))

    def test_path_escape_and_project_root_reparse_are_blocked(self) -> None:
        with self.assertRaisesRegex(sync.SyncBlocked, "safe relative path"):
            sync._inside(ROOT, "../escape", "fixture")
        if os.name != "nt":
            return
        target = self.make_project() / "target"
        target.mkdir()
        junction = target.parent / "junction"
        created = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(target)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if created.returncode != 0:
            self.skipTest(f"junction creation unavailable: {created.stderr.strip()}")
        with self.assertRaisesRegex(sync.SyncBlocked, "reparse point"):
            sync.build_plan(junction, ROOT, "init")

    def test_memory_gap_never_hides_a_validator_execution_error(self) -> None:
        project = self.make_project()
        with mock.patch.object(
            sync.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 2, "[invalid] fixture", "boom"),
        ):
            with self.assertRaisesRegex(sync.SyncBlocked, "failed with exit 2"):
                sync._run_validation(project, ROOT, allow_memory_gap=True)


if __name__ == "__main__":
    unittest.main()
