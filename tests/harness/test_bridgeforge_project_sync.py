from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
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
        self.assertEqual(strategies, {"whole", "merge", "region", "seed", "retirement"})
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
            "0.91.1",
            "0.93.0",
            "0.92.0",
            "0.92.1",
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
        target = project / ".codex/scripts/archive_scan.py"
        target.write_text(
            target.read_text(encoding="utf-8") + "\n# project customization\n",
            encoding="utf-8",
        )
        before = target.read_bytes()
        stamp = project / ".codex/.bridgeforge_version"
        stamp.write_text("0.90.0\n", encoding="utf-8")
        plan = sync.build_plan(project, ROOT, "update")
        self.assertTrue(
            any(item.asset_id == "codex.script.archive-scan" for item in plan.gaps)
        )
        receipt = sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        self.assertEqual(receipt.status, "completed_with_gaps")
        self.assertEqual(receipt.execution_status, "completed")
        self.assertEqual(receipt.target_readiness, "action_required")
        self.assertEqual(receipt.manual_steps[0]["id"], "M1")
        self.assertFalse(receipt.stamp_written_last)
        self.assertEqual(stamp.read_text(encoding="utf-8"), "0.90.0\n")
        self.assertEqual(target.read_bytes(), before)

    def test_aggressive_absorption_lists_conflict_and_replaces_only_managed_blocks(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        target = project / ".codex/rules/architecture.md"
        canonical = target.read_text(encoding="utf-8")
        customized = canonical.replace(
            "## 1. 职责边界\n",
            "## 1. 职责边界\n\n本地区块定制，将被上游覆盖。\n",
            1,
        )
        customized = customized.replace(
            "## 2. 数据流方向\n",
            "## 2. 数据流方向\n\n本地数据流定制，B 模式必须保留。\n",
            1,
        )
        customized += "\n## 项目专属规则\n\n此区块必须保留。\n"
        target.write_text(customized, encoding="utf-8")
        before = target.read_bytes()
        stamp = project / ".codex/.bridgeforge_version"
        stamp.write_text("0.90.0\n", encoding="utf-8")

        plan = sync.build_plan(project, ROOT, "update")
        absorption = next(
            item
            for item in plan.absorption_actions
            if item.asset_id == "codex.rule.architecture"
        )
        self.assertIn("## 1. 职责边界", absorption.managed_blocks)
        payload = sync._plan_payload(plan)
        self.assertEqual(
            [item["id"] for item in payload["upstream_absorption_actions"]],
            ["U1", "U2"],
        )
        self.assertEqual(payload["conflict_file_items"][0]["target"], ".codex/rules/architecture.md")
        self.assertIn("aggressive", payload["confirmation"]["warning"])
        self.assertEqual(payload["confirmation"]["all"], ["U1", "U2"])
        self.assertIn(
            "执行全部 safe；不执行任何 R/C/U",
            payload["confirmation"]["options"][2]["text"],
        )
        self.assertTrue(
            payload["confirmation"]["rendering_contract"][
                "must_expand_every_conflict"
            ]
        )
        self.assertEqual(
            payload["conflict_file_groups"][0]["items"][0]["id"],
            "U1",
        )

        declined = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
            decline_risk=True,
        )
        self.assertEqual(declined.upstream_absorption_declined, ("U1", "U2"))
        self.assertEqual(target.read_bytes(), before)
        self.assertFalse(declined.stamp_written_last)

        selected = sync.build_plan(project, ROOT, "update")
        with self.assertRaisesRegex(
            sync.SyncBlocked,
            "does not name a selected U ID",
        ):
            sync.apply_plan(
                selected,
                plan_fingerprint=selected.aggregate_fingerprint,
                selected_risk_ids=("U1",),
                custom_absorption_directives=("U2：采用另一个区块",),
            )
        self.assertEqual(target.read_bytes(), before)

        with self.assertRaisesRegex(
            sync.SyncBlocked,
            "ambiguous or unsupported",
        ):
            sync.apply_plan(
                selected,
                plan_fingerprint=selected.aggregate_fingerprint,
                selected_risk_ids=("U1",),
                custom_absorption_directives=(
                    "U1：只吸收 hooks 规则，同时保留模型配置",
                ),
            )
        self.assertEqual(target.read_bytes(), before)

        preserved = sync.apply_plan(
            selected,
            plan_fingerprint=selected.aggregate_fingerprint,
            selected_risk_ids=("U1",),
            custom_absorption_directives=("U1：保留本地内容，禁止吸收上游",),
        )
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(preserved.selected_absorption_ids, ())
        self.assertEqual(preserved.selected_action_ids, ())
        self.assertEqual(
            preserved.upstream_absorption_declined,
            ("U1", "U2"),
        )
        self.assertEqual(
            [item["id"] for item in preserved.conflict_file_items],
            ["U1", "U2"],
        )
        self.assertEqual(
            [item["effect"] for item in preserved.managed_block_effects],
            ["preserved_local", "preserved_local"],
        )

        receipt = sync.apply_plan(
            selected,
            plan_fingerprint=selected.aggregate_fingerprint,
            selected_risk_ids=("U1",),
            custom_absorption_directives=("U1：采用上游受管区块",),
        )
        result = target.read_text(encoding="utf-8")
        self.assertNotIn("本地区块定制，将被上游覆盖", result)
        self.assertIn("本地数据流定制，B 模式必须保留", result)
        self.assertIn("## 项目专属规则\n\n此区块必须保留。", result)
        self.assertEqual(receipt.upstream_absorption_applied, ("codex.rule.architecture",))
        self.assertEqual(receipt.upstream_absorption_declined, ("U2",))
        self.assertEqual(receipt.selected_absorption_ids, ("U1",))
        self.assertEqual(receipt.selected_action_ids, ("U1",))
        self.assertEqual(receipt.custom_absorption_directives, ("U1：采用上游受管区块",))
        self.assertEqual(
            [item["id"] for item in receipt.conflict_file_items],
            ["U1", "U2"],
        )
        self.assertEqual(
            [item["effect"] for item in receipt.managed_block_effects],
            ["absorbed_upstream", "preserved_local"],
        )
        self.assertEqual([item["id"] for item in receipt.required_actions], ["U2"])
        self.assertFalse(receipt.stamp_written_last)

        remaining = sync.build_plan(project, ROOT, "update")
        completed = sync.apply_plan(
            remaining,
            plan_fingerprint=remaining.aggregate_fingerprint,
            confirmed_risk=True,
        )
        self.assertTrue(completed.stamp_written_last)
        self.assertNotIn(
            "本地数据流定制，B 模式必须保留",
            target.read_text(encoding="utf-8"),
        )

    def test_missing_blocks_append_cleanly_and_094_boundary_is_safe_repaired(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        contract = json.loads(
            (ROOT / "templates/codex/managed-skeleton.json").read_text(
                encoding="utf-8"
            )
        )
        missing_by_target = {
            "AGENTS.md": (
                "## 0.5 专业表达风格",
                "## 2.5 工具与证据红线",
                "## 8.5 自改审计独立性（红线）",
                "## 9.5 较大需求主动澄清 — `[clarify]`",
                "## 9.6 任务防漂移 — `[focus]`",
            ),
            ".codex/rules/workflow.md": ("## 9. 版本域隔离（红线）",),
        }
        for relative, missing in missing_by_target.items():
            asset = next(
                item for item in contract["assets"] if item["target"] == relative
            )
            target = project / relative
            before = target.read_bytes()
            sections = sync._markdown_heading_sections(
                before,
                tuple(asset["managed_blocks"]["headings"]),
            )
            for start, finish in sorted(
                (sections[heading] for heading in missing),
                reverse=True,
            ):
                before = before[:start] + before[finish:]
            target.write_bytes(
                before + b"\n## Project Owned\n\nproject tail\n\n---\n"
            )
        stamp = project / ".codex/.bridgeforge_version"
        stamp.write_text("0.93.0\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "fixture@example.invalid"],
            cwd=project,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Fixture"],
            cwd=project,
            check=True,
        )
        subprocess.run(["git", "add", "."], cwd=project, check=True)
        subprocess.run(
            ["git", "commit", "-m", "baseline"],
            cwd=project,
            check=True,
            capture_output=True,
        )

        plan = sync.build_plan(project, ROOT, "update")
        receipt = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
            confirmed_risk=True,
        )
        self.assertTrue(receipt.stamp_written_last)
        self.assertIn("git_diff_check", receipt.timings_ms)
        for relative in missing_by_target:
            payload = (project / relative).read_bytes()
            self.assertTrue(payload.endswith(b"\n"))
            self.assertFalse(payload.endswith(b"\n\n"))
            self.assertIn(b"## Project Owned\n\nproject tail\n\n---\n", payload)
        checked = subprocess.run(
            ["git", "diff", "--check", "HEAD"],
            cwd=project,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)

        agents = project / "AGENTS.md"
        agents.write_bytes(agents.read_bytes() + b"\n")
        repair = sync.build_plan(project, ROOT, "update")
        boundary = [
            item
            for item in repair.safe_actions
            if item.action == "normalize-managed-block-boundary"
        ]
        self.assertEqual([item.target for item in boundary], ["AGENTS.md"])
        repaired = sync.apply_plan(
            repair,
            plan_fingerprint=repair.aggregate_fingerprint,
        )
        self.assertTrue(repaired.stamp_written_last)
        self.assertFalse(agents.read_bytes().endswith(b"\n\n"))

    def test_managed_git_diff_failure_rolls_back_before_stamp(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        stamp = project / ".codex/.bridgeforge_version"
        stamp.write_text("0.93.0\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "fixture@example.invalid"],
            cwd=project,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Fixture"],
            cwd=project,
            check=True,
        )
        subprocess.run(["git", "add", "."], cwd=project, check=True)
        subprocess.run(
            ["git", "commit", "-m", "baseline"],
            cwd=project,
            check=True,
            capture_output=True,
        )
        target = project / ".codex/rules/architecture.md"
        customized = target.read_text(encoding="utf-8").replace(
            "## 1. 职责边界\n",
            "## 1. 职责边界\n\nlocal customization\n",
            1,
        )
        target.write_text(
            customized + "\n## Project Owned\n\ninvalid blank at eof\n\n",
            encoding="utf-8",
        )
        before = target.read_bytes()
        plan = sync.build_plan(project, ROOT, "update")
        with self.assertRaisesRegex(sync.SyncBlocked, "rolled back: managed git diff check"):
            sync.apply_plan(
                plan,
                plan_fingerprint=plan.aggregate_fingerprint,
                confirmed_risk=True,
            )
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(stamp.read_text(encoding="utf-8"), "0.93.0\n")

    def test_ambiguous_managed_block_boundary_remains_manual_and_unwritten(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        target = project / ".codex/rules/architecture.md"
        payload = target.read_text(encoding="utf-8").replace(
            "## 1. 职责边界",
            "## 项目自定义职责",
            1,
        )
        for heading in (
            "## 2. 数据流方向",
            "## 3. 关键链路完整性（红线）",
            "## 4. 重写 / 移植期间的功能等价性（红线）",
            "## 5. 模块组织约束",
        ):
            payload = payload.replace(heading, heading.replace("##", "###"), 1)
        target.write_text(payload, encoding="utf-8")
        before = target.read_bytes()
        plan = sync.build_plan(project, ROOT, "update")
        self.assertFalse(
            any(item.asset_id == "codex.rule.architecture" for item in plan.absorption_actions)
        )
        self.assertTrue(
            any(item.asset_id == "codex.rule.architecture" for item in plan.gaps)
        )
        receipt = sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        self.assertEqual(receipt.manual_steps[0]["category"], "manual")
        self.assertEqual(target.read_bytes(), before)

    def test_memory_index_is_project_owned_seed_after_init(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        memory_index = project / ".codex/memory/MEMORY.md"
        memory_index.write_text("# project generated memory index\n", encoding="utf-8")
        plan = sync.build_plan(project, ROOT, "update")
        self.assertFalse(
            any(item.asset_id == "codex.memory.index" for item in plan.actions)
        )
        self.assertFalse(
            any(item.asset_id == "codex.memory.index" for item in plan.gaps)
        )

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
        model_payload = model.read_bytes()
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

        payload = sync._plan_payload(plan)
        self.assertEqual(payload["execution_status"], "planned")
        self.assertEqual(payload["target_readiness"], "action_required")
        self.assertEqual(
            [item["id"] for item in payload["required_actions"]],
            ["R1", "R2"],
        )
        self.assertEqual(payload["recommended_selection"], ["R1", "R2"])
        self.assertEqual(payload["confirmation"]["business_confirmation_count"], "one")

        with self.assertRaisesRegex(sync.SyncBlocked, "unknown selected risk IDs"):
            sync.apply_plan(
                plan,
                plan_fingerprint=plan.aggregate_fingerprint,
                selected_risk_ids=("R9",),
            )
        with self.assertRaisesRegex(sync.SyncBlocked, "duplicate risk IDs"):
            sync.apply_plan(
                plan,
                plan_fingerprint=plan.aggregate_fingerprint,
                selected_risk_ids=("R1", "R1"),
            )
        self.assertTrue(model.exists() and version.exists())

        partial = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
            selected_risk_ids=("R1",),
        )
        self.assertEqual(partial.execution_status, "completed")
        self.assertEqual(partial.target_readiness, "action_required")
        self.assertEqual(partial.selected_action_ids, ("R1",))
        self.assertEqual(len(partial.risk_applied), 1)
        self.assertEqual(len(partial.risk_declined), 1)
        self.assertEqual([item["id"] for item in partial.required_actions], ["R2"])
        self.assertIsNotNone(partial.selection_fingerprint)
        self.assertFalse(model.exists())
        self.assertTrue(version.exists())
        self.assertFalse(partial.stamp_written_last)

        model.write_bytes(model_payload)
        plan = sync.build_plan(project, ROOT, "update")

        receipt = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
            confirmed_risk=True,
        )
        self.assertEqual(len(receipt.risk_applied), 2)
        self.assertEqual(receipt.target_readiness, "ready")
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

    def test_validators_run_concurrently_and_report_phase_timings(self) -> None:
        project = self.make_project()
        barrier = threading.Barrier(2)

        def complete_together(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
            barrier.wait(timeout=2)
            return subprocess.CompletedProcess([], 0, "", "")

        with mock.patch.object(sync.subprocess, "run", side_effect=complete_together):
            timings = sync._run_validation(project, ROOT, allow_memory_gap=False)

        self.assertEqual(set(timings), {"memory_validation", "config_validation"})
        self.assertTrue(all(value >= 0 for value in timings.values()))

    def test_cli_apply_builds_one_immediate_replan_and_emits_timings(self) -> None:
        project = self.make_project()
        displayed = sync.build_plan(project, ROOT, "init")
        output = io.StringIO()

        with mock.patch.object(sync, "build_plan", wraps=sync.build_plan) as build:
            with redirect_stdout(output):
                exit_code = sync.main(
                    [
                        "--project-root",
                        str(project),
                        "--template-root",
                        str(ROOT),
                        "--mode",
                        "init",
                        "--apply",
                        "--plan-fingerprint",
                        displayed.aggregate_fingerprint,
                    ]
                )

        self.assertEqual(exit_code, 0, output.getvalue())
        self.assertEqual(build.call_count, 1)
        receipt = json.loads(output.getvalue())
        self.assertEqual(receipt["status"], "completed")
        self.assertIn("replan", receipt["timings_ms"])
        self.assertIn("validation_wall", receipt["timings_ms"])

    def test_cli_plan_emits_timing_receipt(self) -> None:
        project = self.make_project()
        output = io.StringIO()
        with redirect_stdout(output):
            exit_code = sync.main(
                [
                    "--project-root",
                    str(project),
                    "--template-root",
                    str(ROOT),
                    "--mode",
                    "init",
                ]
            )
        self.assertEqual(exit_code, 0, output.getvalue())
        plan = json.loads(output.getvalue())
        self.assertIn("plan", plan["timings_ms"])


if __name__ == "__main__":
    unittest.main()
