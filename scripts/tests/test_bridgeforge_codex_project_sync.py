from __future__ import annotations

import importlib.util
import copy
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
SCRIPT = ROOT / "scripts" / "bridgeforge_codex_project_sync.py"
SPEC = importlib.util.spec_from_file_location("bridgeforge_codex_project_sync", SCRIPT)
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
CURRENT_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
LEGACY_DISTRIBUTION_REVISION = manifest_builder.LEGACY_DISTRIBUTION_REVISION


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

    @staticmethod
    def legacy_agents(*, filled: bool = True, project_name: str = "fixture") -> str:
        text = git_blob(
            LEGACY_DISTRIBUTION_REVISION,
            "templates/codex/AGENTS.md",
        ).decode("utf-8")
        text = text.replace("{{PROJECT_NAME}}", project_name)
        if filled:
            text = text.replace(
                "<!-- 填 3-5 条“必须 X / 禁止 Y”硬约束（数据流方向 / 资源上限 / 时序约束），填好删注释。 -->",
                "- 必须保持 fixture 数据流单向。",
            )
            text = text.replace(
                "<!-- 填项目构建 / 运行 / 测试 / 检查命令（每天敲得最多的几行），填好删注释。 -->",
                "- `.venv/Scripts/python.exe -m unittest`",
            )
            text = text.replace(
                "<!-- 列顶层目录及职责（一行一个），帮 Codex 快速定位代码。跑 `ls` 看顶层照填。 -->",
                "- `src/`：fixture 源码入口。",
            )
        return text

    def test_schema_v2_is_explicit_and_hashes_supported_baselines(self) -> None:
        contract = json.loads(
            (ROOT / "templates/managed-skeleton.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(contract["schema_version"], 2)
        self.assertEqual(
            contract["release_version"],
            (ROOT / "VERSION").read_text(encoding="utf-8-sig").strip(),
        )
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
        precommit = next(
            item for item in contract["assets"] if item["id"] == "codex.precommit"
        )
        self.assertRegex(precommit["region"]["current_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertIn("1.4.1", precommit["region"]["historical_sha256"])
        active = next(item for item in contract["assets"] if item["id"] == "root.agents")
        self.assertIn("0.86.0", active["historical_sha256"])
        self.assertIn("0.90.0", active["historical_sha256"])
        self.assertNotIn("## 1. 架构红线", active["managed_blocks"]["headings"])
        self.assertNotIn("## 3. 快速命令", active["managed_blocks"]["headings"])
        self.assertEqual(
            active["managed_blocks"]["headings"],
            ["### 2.1 原生指令承载索引"],
        )
        self.assertEqual(active["managed_blocks"]["keyed_tables"], [])
        self.assertEqual(active["managed_blocks"]["additive_headings"], [])
        layout = active["section_layout"]
        self.assertEqual(layout["format"], "markdown-section-layout")
        project_sections = {
            entry["heading"]
            for entry in sync._layout_sections(layout)
            if entry["ownership"] == "project" and entry.get("required") is True
        }
        self.assertEqual(project_sections, {
            "### 1.1 架构红线",
            "## 3 项目目录地图",
            "### 4.2 快速命令",
        })
        zones = active["agents_zones"]
        self.assertEqual(zones["format"], "bridgeforge-agents-zones")
        self.assertEqual(
            zones["project"]["required_content_headings"],
            [
                "### 项目架构红线",
                "### 项目目录地图",
                "### 项目快速命令",
            ],
        )
        architecture = next(
            item
            for item in contract["assets"]
            if item["id"] == "codex.rule.architecture"
        )
        self.assertEqual(architecture["strategy"], "retirement")
        self.assertNotIn("source", architecture)
        self.assertNotIn("managed_blocks", architecture)
        self.assertIn("1.0.0", architecture["historical_sha256"])
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
            "0.94.0",
            "0.94.1",
            "0.94.2",
            "0.94.4",
            "1.4.3",
            "1.4.1",
            "1.3.0",
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
        self.assertIn(
            manifest_builder.PRE_FLATTEN_CONTRACT_SHA256,
            contract["contract_historical_sha256"]["1.0.0"],
        )
        assets_by_id = {asset["id"]: asset for asset in contract["assets"]}
        for asset_id, digest in manifest_builder.PRE_FLATTEN_ASSET_SHA256.items():
            with self.subTest(pre_flatten_asset=asset_id):
                self.assertIn(
                    digest,
                    assets_by_id[asset_id]["historical_sha256"]["1.0.0"],
                )
        for asset_id, digest in (
            manifest_builder.PROJECT_ZONE_TRANSITION_ASSET_SHA256.items()
        ):
            with self.subTest(project_zone_transition_asset=asset_id):
                self.assertIn(
                    digest,
                    assets_by_id[asset_id]["historical_sha256"][
                        manifest_builder.PROJECT_ZONE_TRANSITION_VERSION
                    ],
                )

    def test_contract_dogfood_manifest_and_retirements_are_current(self) -> None:
        template_contract = ROOT / "templates/managed-skeleton.json"
        self.assertFalse((ROOT / "templates/codex").exists())
        self.assertEqual(
            json.loads(template_contract.read_text(encoding="utf-8-sig")),
            json.loads(
                (ROOT / ".codex/managed-skeleton.json").read_text(
                    encoding="utf-8-sig"
                )
            ),
        )
        for retired in (
            "context_warning.py",
            "model_policy_check.py",
            "version_check.py",
        ):
            self.assertFalse((ROOT / "templates/hooks" / retired).exists())
            self.assertFalse((ROOT / ".codex/hooks" / retired).exists())
        self.assertFalse((ROOT / "templates/scripts/bridgeforge_switch.py").exists())
        self.assertFalse((ROOT / ".codex/scripts/bridgeforge_switch.py").exists())
        self.assertFalse(
            (ROOT / "doc/0_architecture/design/codex-harness-parity.md").exists()
        )
        self.assertTrue(
            (ROOT / "doc/4_archive/codex-harness-parity-design.md").is_file()
        )
        contract = json.loads(template_contract.read_text(encoding="utf-8-sig"))
        self.assertTrue(
            all(
                not str(asset.get("source", "")).startswith("templates" + "/codex/")
                for asset in contract["assets"]
            )
        )
        retirement_targets = {
            asset["target"]
            for asset in contract["assets"]
            if asset["strategy"] == "retirement"
        }
        self.assertIn(".codex/scripts/bridgeforge_switch.py", retirement_targets)
        self.assertIn(".codex/scripts/harness_parity_check.py", retirement_targets)

    def test_active_factory_surfaces_do_not_reference_legacy_template_root(self) -> None:
        legacy_root = "templates" + "/codex/"
        active_roots = (
            ROOT / "templates",
            ROOT / "skills",
            ROOT / "scripts",
            ROOT / ".codex",
            ROOT / ".githooks",
            ROOT / "doc" / "0_architecture",
            ROOT / "doc" / "3_reference",
        )
        active_files = [
            path
            for path in ROOT.iterdir()
            if path.is_file() and path.name != "CHANGELOG.md"
        ]
        active_files.append(ROOT / "doc" / "README.md")
        for active_root in active_roots:
            active_files.extend(
                path
                for path in active_root.rglob("*")
                if path.is_file()
                and "__pycache__" not in path.parts
                and not path.is_relative_to(ROOT / ".codex" / "memory")
            )

        historical_test_lines = {
            f'"{legacy_root}AGENTS.md",',
            f'"{legacy_root}hooks/context_warning.py",',
            f'"{legacy_root}skill-routing.json",',
            f'"{legacy_root}hooks/model_policy_check.py",',
            f'"{legacy_root}hooks/version_check.py",',
        }
        violations: list[str] = []
        for path in active_files:
            if path.suffix.lower() not in {
                ".json", ".md", ".py", ".toml", ".ps1", ".sh", ""
            }:
                continue
            try:
                lines = path.read_text(encoding="utf-8-sig").splitlines()
            except UnicodeDecodeError:
                continue
            for line_number, line in enumerate(lines, start=1):
                if legacy_root not in line:
                    continue
                stripped = line.strip()
                if path in {
                    ROOT / "templates" / "managed-skeleton.json",
                    ROOT / ".codex" / "managed-skeleton.json",
                } and '"historical_source"' in line:
                    continue
                if path == ROOT / "scripts" / "rebuild_shared_skill_manifest.py" and (
                    "source.startswith" in line or "source.removeprefix" in line
                ):
                    continue
                if path == ROOT / "scripts" / "tests" / "run_downstream_fixture.py" and (
                    "historical_contract = _git_blob" in line
                ):
                    continue
                if path == ROOT / "scripts" / "tests" / "test_bridgeforge_codex_project_sync.py" and (
                    stripped in historical_test_lines
                ):
                    continue
                if path == ROOT / "doc" / "README.md" and (
                    "template-root-flattening" in line and "提升为 `templates/**`" in line
                ):
                    continue
                violations.append(f"{path.relative_to(ROOT)}:{line_number}: {line.strip()}")
        self.assertEqual(violations, [])
    def test_required_project_sections_use_dual_state_without_repeating_update(self) -> None:
        project = self.make_project()
        receipt = self.apply_init(project)
        self.assertEqual(receipt.status, "completed")
        self.assertEqual(receipt.readiness, "ready")
        self.assertEqual(receipt.project_readiness, "needs_user_action")
        self.assertEqual(receipt.target_readiness, "action_required")
        self.assertEqual(
            [item["id"] for item in receipt.required_actions],
            ["P1", "P2", "P3"],
        )
        stamp = project / ".codex/.bridgeforge_codex_version"
        self.assertEqual(stamp.read_text(encoding="utf-8").strip(), CURRENT_VERSION)

        second = sync.build_plan(project, ROOT, "update")
        self.assertFalse(second.actions)
        self.assertFalse(second.gaps)
        self.assertFalse(second.gaps)
        self.assertEqual(len(second.project_requirements), 3)
        repeated = sync.apply_plan(
            second,
            plan_fingerprint=second.aggregate_fingerprint,
        )
        self.assertFalse(repeated.stamp_written_last)
        self.assertEqual(repeated.project_readiness, "needs_user_action")

    def test_legacy_test_root_is_actionable_and_never_auto_moved(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        marker = project / "tests" / "test_project_only.py"
        marker.parent.mkdir()
        marker.write_text("PROJECT TEST MARKER\n", encoding="utf-8")
        before = marker.read_bytes()

        plan = sync.build_plan(project, ROOT, "update")
        migration = next(
            item
            for item in plan.project_requirements
            if item["category"] == "project_layout_migration"
        )
        self.assertEqual(migration["id"], "P4")
        self.assertIn("tests/ -> scripts/tests/", migration["title"])
        self.assertFalse(any(action.target.startswith("tests/") for action in plan.actions))

        receipt = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
        )

        self.assertEqual(receipt.project_readiness, "needs_user_action")
        self.assertEqual(marker.read_bytes(), before)
        self.assertFalse((project / "scripts/tests/test_project_only.py").exists())

    def test_exact_legacy_layout_migrates_and_preserves_project_sections(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        agents = project / "AGENTS.md"
        agents.write_text(
            self.legacy_agents(project_name=project.name),
            encoding="utf-8",
        )
        retired_hook = project / ".codex/hooks/context_warning.py"
        retired_hook.write_bytes(git_blob(
            LEGACY_DISTRIBUTION_REVISION,
            "templates/codex/hooks/context_warning.py",
        ))
        stamp = project / ".codex/.bridgeforge_codex_version"
        stamp.write_text("0.94.4\n", encoding="utf-8")

        plan = sync.build_plan(project, ROOT, "update")
        self.assertFalse(plan.gaps)
        self.assertTrue(any(
            item.asset_id == "root.agents"
            and item.action == "migrate-agents-zones"
            for item in plan.safe_actions
        ))
        receipt = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
            confirmed_risk=True,
        )
        migrated = agents.read_text(encoding="utf-8")
        for marker in (
            "<!-- BRIDGEFORGE:PUBLIC:BEGIN -->",
            "<!-- BRIDGEFORGE:PROJECT:BEGIN -->",
            "### 项目架构红线",
            "### 项目目录地图",
            "### 项目快速命令",
            "必须保持 fixture 数据流单向",
            ".venv/Scripts/python.exe -m unittest",
            "`src/`：fixture 源码入口",
        ):
            self.assertIn(marker, migrated)
        for legacy in (
            "## 1. 架构红线",
            "## 3. 快速命令",
            "## 7. 项目结构速查",
            "[ctx-budget]",
        ):
            self.assertNotIn(legacy, migrated)
        self.assertFalse(retired_hook.exists())
        self.assertEqual(receipt.project_readiness, "ready")
        self.assertEqual(receipt.target_readiness, "ready")
        self.assertEqual(stamp.read_text(encoding="utf-8").strip(), CURRENT_VERSION)

        second = sync.build_plan(project, ROOT, "update")
        self.assertFalse(second.actions)
        self.assertFalse(second.gaps)
        self.assertFalse(second.project_requirements)

    def test_legacy_layout_preserves_rendered_project_name_outside_worktree_name(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        agents = project / "AGENTS.md"
        agents.write_text(
            self.legacy_agents(project_name="causis_risk_suite"),
            encoding="utf-8",
        )
        stamp = project / ".codex/.bridgeforge_codex_version"
        stamp.write_text("0.94.4\n", encoding="utf-8")

        plan = sync.build_plan(project, ROOT, "update")
        self.assertFalse(plan.gaps)
        receipt = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
            confirmed_risk=True,
        )
        migrated = agents.read_text(encoding="utf-8")
        self.assertIn(
            "git clone <repo_url> causis_risk_suite && cd causis_risk_suite",
            migrated,
        )
        self.assertNotIn(project.name, migrated)
        self.assertTrue(receipt.stamp_written_last)

        second = sync.build_plan(project, ROOT, "update")
        self.assertFalse(second.actions)
        self.assertFalse(second.gaps)

    def test_legacy_unclassified_preamble_or_group_prose_is_preserved_as_gap(self) -> None:
        for case in ("preamble", "group-prose"):
            with self.subTest(case=case):
                project = self.make_project()
                self.apply_init(project)
                agents = project / "AGENTS.md"
                if case == "preamble":
                    legacy = self.legacy_agents(project_name=project.name)
                    legacy = "PROJECT CUSTOM PREAMBLE MUST SURVIVE.\n\n" + legacy
                else:
                    contract = json.loads(
                        (ROOT / "templates/managed-skeleton.json").read_text(
                            encoding="utf-8"
                        )
                    )
                    asset = next(
                        item for item in contract["assets"]
                        if item["id"] == "root.agents"
                    )
                    desired = (ROOT / "templates/AGENTS.md").read_bytes().replace(
                        b"{{PROJECT_NAME}}", project.name.encode("utf-8")
                    )
                    legacy = sync._legacy_agents_source(asset, desired).decode("utf-8")
                    heading = "## 1 项目基础约束"
                    self.assertIn(heading, legacy)
                    legacy = legacy.replace(
                        heading,
                        heading + "\n\nPROJECT GROUP PROSE MUST SURVIVE.",
                        1,
                    )
                agents.write_text(legacy, encoding="utf-8")
                before = agents.read_bytes()

                plan = sync.build_plan(project, ROOT, "update")
                self.assertFalse(any(
                    item.asset_id == "root.agents" for item in plan.safe_actions
                ))
                self.assertTrue(any(
                    item.asset_id == "root.agents"
                    and "unclassified content" in item.reason
                    for item in plan.gaps
                ))
                receipt = sync.apply_plan(
                    plan,
                    plan_fingerprint=plan.aggregate_fingerprint,
                )
                self.assertEqual(agents.read_bytes(), before)
                self.assertFalse(receipt.stamp_written_last)

    def test_rendered_project_name_normalizer_does_not_trust_other_edits(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        agents = project / "AGENTS.md"
        customized = self.legacy_agents(project_name="causis_risk_suite").replace(
            "用户提到“换电脑 / 新机 clone / 重装”时",
            "项目本地改写：用户换机时",
            1,
        )
        agents.write_text(customized, encoding="utf-8")
        before = agents.read_bytes()

        plan = sync.build_plan(project, ROOT, "update")
        self.assertTrue(any(
            item.asset_id == "root.agents"
            and "managed legacy section drifted" in item.reason
            for item in plan.gaps
        ))
        receipt = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
        )
        self.assertEqual(agents.read_bytes(), before)
        self.assertFalse(receipt.stamp_written_last)

    def test_zone_update_preserves_project_bytes_and_rejects_public_drift(self) -> None:
        project = self.make_project()
        contract = json.loads(
            (ROOT / "templates/managed-skeleton.json").read_text(encoding="utf-8")
        )
        asset = copy.deepcopy(next(
            item for item in contract["assets"] if item["id"] == "root.agents"
        ))
        source = (ROOT / "templates/AGENTS.md").read_bytes()
        before = source.replace(b"{{PROJECT_NAME}}", project.name.encode("utf-8"))
        before = before.replace(
            "<!-- [按需] 写明本项目特有的业务、数据、风控、安全与合规红线，填好删注释。 -->".encode(),
            "- 项目订单必须经过本地风控。".encode(),
        )
        target = project / "AGENTS.md"
        target.write_bytes(before)
        before_parts = sync._agents_zone_parts(before, asset["agents_zones"])
        desired = source.replace("默认先给结论".encode(), "默认直接给结论".encode())
        desired_rendered = desired.replace(b"{{PROJECT_NAME}}", project.name.encode("utf-8"))
        desired_parts = sync._agents_zone_parts(desired_rendered, asset["agents_zones"])
        asset["agents_zones"]["public"]["historical_sha256"] = {
            "1.2.0": [sync._agents_zone_hash(before_parts[1], asset, project)]
        }
        asset["agents_zones"]["public"]["current_sha256"] = (
            sync._agents_zone_hash(desired_parts[1], asset, project)
        )
        actions, gaps = sync._plan_whole(asset, desired, target, project)
        self.assertEqual(gaps, [])
        self.assertEqual(len(actions), 1)
        after_parts = sync._agents_zone_parts(actions[0].payload, asset["agents_zones"])
        self.assertEqual(after_parts[3], before_parts[3])
        self.assertIn("项目订单必须经过本地风控".encode(), after_parts[3])

        target.write_bytes(before.replace("默认先给结论".encode(), "项目自行改写".encode()))
        actions, gaps = sync._plan_whole(asset, desired, target, project)
        self.assertEqual(actions, [])
        self.assertTrue(any("public zone drifted" in item.reason for item in gaps))

    def test_partial_or_reversed_zone_markers_fail_closed(self) -> None:
        project = self.make_project()
        contract = json.loads(
            (ROOT / "templates/managed-skeleton.json").read_text(encoding="utf-8")
        )
        asset = next(item for item in contract["assets"] if item["id"] == "root.agents")
        source = (ROOT / "templates/AGENTS.md").read_bytes()
        target = project / "AGENTS.md"
        target.write_bytes(source.replace(b"<!-- BRIDGEFORGE:PROJECT:END -->", b""))
        actions, gaps = sync._plan_whole(asset, source, target, project)
        self.assertEqual(actions, [])
        self.assertTrue(any("missing or duplicated" in item.reason for item in gaps))

    def test_custom_legacy_title_is_gap_and_layout_is_unwritten(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        agents = project / "AGENTS.md"
        agents.write_text(
            self.legacy_agents().replace(
                "## 1. 架构红线",
                "## 项目自定义架构约束",
                1,
            ),
            encoding="utf-8",
        )
        before = agents.read_bytes()
        stamp = project / ".codex/.bridgeforge_codex_version"
        stamp.write_text("0.94.4\n", encoding="utf-8")
        plan = sync.build_plan(project, ROOT, "update")
        self.assertTrue(any(
            item.asset_id == "root.agents"
            and (
                "unrecognized top-level layout heading" in item.reason
                or "unclassified content outside recognized sections" in item.reason
            )
            for item in plan.gaps
        ))
        self.assertFalse(any(item.asset_id == "root.agents" for item in plan.actions))
        receipt = sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        self.assertEqual(agents.read_bytes(), before)
        self.assertFalse(receipt.stamp_written_last)
        self.assertEqual(stamp.read_text(encoding="utf-8"), "0.94.4\n")

    def test_modified_managed_legacy_section_is_gap_and_unwritten(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        agents = project / "AGENTS.md"
        agents.write_text(
            self.legacy_agents().replace(
                "## 0.5 专业表达风格\n",
                "## 0.5 专业表达风格\n\n- 项目本地表达扩展。\n",
                1,
            ),
            encoding="utf-8",
        )
        before = agents.read_bytes()
        plan = sync.build_plan(project, ROOT, "update")
        self.assertTrue(any(
            item.asset_id == "root.agents"
            and "managed legacy section drifted" in item.reason
            for item in plan.gaps
        ))
        self.assertFalse(any(item.asset_id == "root.agents" for item in plan.actions))
        sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        self.assertEqual(agents.read_bytes(), before)

    def test_modified_retired_ctx_budget_section_is_gap_and_unwritten(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        agents = project / "AGENTS.md"
        agents.write_text(
            self.legacy_agents().replace(
                "边界附近以信号为准。",
                "项目自定义上下文预算必须保留。",
                1,
            ),
            encoding="utf-8",
        )
        before = agents.read_bytes()
        plan = sync.build_plan(project, ROOT, "update")
        self.assertTrue(any(
            item.asset_id == "root.agents"
            and "retired legacy section drifted" in item.reason
            and "## 10. 上下文成本与预算" in item.reason
            for item in plan.gaps
        ))
        self.assertFalse(any(item.asset_id == "root.agents" for item in plan.actions))
        receipt = sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        self.assertFalse(receipt.stamp_written_last)
        self.assertEqual(agents.read_bytes(), before)

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
        self.assertEqual(writes[-1], ".codex/.bridgeforge_codex_version")
        self.assertEqual(
            (project / ".codex/.bridgeforge_codex_version").read_text(encoding="utf-8"),
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
        (project / ".codex/.bridgeforge_codex_version").write_text(
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
        stamp = project / ".codex/.bridgeforge_codex_version"
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

    def test_official_retired_rules_are_removed_and_modified_rules_are_preserved(self) -> None:
        contract = json.loads(
            (ROOT / "templates/managed-skeleton.json").read_text(encoding="utf-8")
        )
        retired_rules = [
            asset for asset in contract["assets"]
            if asset["id"].startswith("codex.rule.")
        ]
        self.assertEqual(len(retired_rules), 8)

        official_project = self.make_project()
        self.apply_init(official_project)
        legacy_root = "templates" + "/codex/"
        for asset in retired_rules:
            target = official_project / asset["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            legacy_source = str(asset["historical_source"]).replace(
                "templates" + "/", legacy_root, 1
            )
            target.write_bytes(git_blob(LEGACY_DISTRIBUTION_REVISION, legacy_source))
        official_plan = sync.build_plan(official_project, ROOT, "update")
        retired_ids = {
            action.asset_id
            for action in official_plan.risk_actions
            if action.action == "retire"
        }
        self.assertEqual(retired_ids, {asset["id"] for asset in retired_rules})
        official_receipt = sync.apply_plan(
            official_plan,
            plan_fingerprint=official_plan.aggregate_fingerprint,
            confirmed_risk=True,
        )
        self.assertFalse(official_receipt.stamp_written_last)
        self.assertEqual(
            (official_project / ".codex/.bridgeforge_codex_version")
            .read_text(encoding="utf-8")
            .strip(),
            (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        )
        self.assertTrue(all(
            not (official_project / asset["target"]).exists()
            for asset in retired_rules
        ))

        modified_project = self.make_project()
        self.apply_init(modified_project)
        stamp = modified_project / ".codex/.bridgeforge_codex_version"
        stamp.write_text("1.0.0\n", encoding="utf-8")
        before: dict[str, bytes] = {}
        for asset in retired_rules:
            target = modified_project / asset["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = f"project customization for {asset['id']}\n".encode("utf-8")
            target.write_bytes(payload)
            before[asset["target"]] = payload
        modified_plan = sync.build_plan(modified_project, ROOT, "update")
        rule_gaps = {
            gap.asset_id: gap
            for gap in modified_plan.gaps
            if gap.asset_id.startswith("codex.rule.")
        }
        self.assertEqual(set(rule_gaps), {asset["id"] for asset in retired_rules})
        for asset in retired_rules:
            self.assertIn(
                sync.RETIRED_RULE_MIGRATION_TARGETS[asset["target"]],
                rule_gaps[asset["id"]].reason,
            )
        modified_receipt = sync.apply_plan(
            modified_plan,
            plan_fingerprint=modified_plan.aggregate_fingerprint,
        )
        self.assertEqual(modified_receipt.status, "completed_with_gaps")
        self.assertFalse(modified_receipt.stamp_written_last)
        self.assertEqual(stamp.read_text(encoding="utf-8"), "1.0.0\n")
        for relative, payload in before.items():
            self.assertEqual((modified_project / relative).read_bytes(), payload)

    def test_customized_legacy_rule_index_is_preserved_as_gap(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        contract = json.loads(
            (ROOT / "templates/managed-skeleton.json").read_text(encoding="utf-8")
        )
        retired_rules = [
            asset for asset in contract["assets"]
            if asset["id"].startswith("codex.rule.")
        ]
        legacy_root = "templates" + "/codex/"
        rule_bytes: dict[str, bytes] = {}
        for asset in retired_rules:
            target = project / asset["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            legacy_source = str(asset["historical_source"]).replace(
                "templates" + "/", legacy_root, 1
            )
            payload = git_blob(LEGACY_DISTRIBUTION_REVISION, legacy_source)
            target.write_bytes(payload)
            rule_bytes[asset["target"]] = payload
        agents = project / "AGENTS.md"
        customized = self.legacy_agents().replace(
            "职责边界 + 数据流方向（核心红线）",
            "项目自定义架构索引，禁止覆盖",
            1,
        )
        agents.write_text(customized, encoding="utf-8")
        before = agents.read_bytes()
        stamp = project / ".codex/.bridgeforge_codex_version"
        stamp.write_text("1.0.0\n", encoding="utf-8")

        plan = sync.build_plan(project, ROOT, "update")
        self.assertTrue(any(
            gap.asset_id == "root.agents"
            and "retired legacy section drifted" in gap.reason
            for gap in plan.gaps
        ))
        self.assertFalse(any(
            action.action == "retire"
            and action.target in sync.RETIRED_RULE_MIGRATION_TARGETS
            for action in plan.actions
        ))
        self.assertEqual(
            {
                gap.asset_id
                for gap in plan.gaps
                if "native AGENTS instruction migration is incomplete" in gap.reason
            },
            {asset["id"] for asset in retired_rules},
        )
        receipt = sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        self.assertEqual(agents.read_bytes(), before)
        self.assertFalse(receipt.stamp_written_last)
        self.assertEqual(stamp.read_text(encoding="utf-8"), "1.0.0\n")
        for relative, payload in rule_bytes.items():
            self.assertEqual((project / relative).read_bytes(), payload)

    def test_doc_index_keyed_merge_preserves_downstream_only_rows(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        target = project / "doc/README.md"
        text = target.read_text(encoding="utf-8")
        text = text.replace(
            "系统当前架构、关键接口、数据流与 ADR",
            "项目定制的架构目录说明",
            1,
        )
        text = text.replace(
            "| [`4_archive/`](4_archive/) |",
            "| [`quant_reports/`](quant_reports/) | 项目量化报告 | 活跃 |\n"
            "| [`4_archive/`](4_archive/) |",
            1,
        )
        text = text.replace(
            "<!-- TODO: 已完成的 delivery 保持原 milestone/topic 层级归档；已解决 Bug 归档至 bugs/。 -->",
            "项目归档索引由本项目维护。",
            1,
        )
        target.write_text(text, encoding="utf-8")
        plan = sync.build_plan(project, ROOT, "update")
        payload = sync._plan_payload(plan)
        conflict = next(
            item
            for item in payload["upstream_absorption_actions"]
            if item["managed_key"] == "0_architecture/"
        )
        receipt = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
            confirmed_risk=True,
        )
        result = target.read_text(encoding="utf-8")
        self.assertIn("quant_reports/", result)
        self.assertIn("系统当前架构、关键接口、数据流与 ADR", result)
        self.assertNotIn("项目定制的架构目录说明", result)
        self.assertIn("项目归档索引由本项目维护", result)
        effect = next(
            item for item in receipt.managed_block_effects if item["id"] == conflict["id"]
        )
        self.assertEqual(effect["managed_key"], "0_architecture/")

    def test_layout_migration_git_diff_failure_rolls_back_before_stamp(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        stamp = project / ".codex/.bridgeforge_codex_version"
        stamp.write_text("0.94.4\n", encoding="utf-8")
        target = project / "AGENTS.md"
        target.write_text(self.legacy_agents(), encoding="utf-8")
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
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "- 必须保持 fixture 数据流单向。",
                "- 必须保持 fixture 数据流单向。 ",
                1,
            ),
            encoding="utf-8",
        )
        before = target.read_bytes()
        plan = sync.build_plan(project, ROOT, "update")
        self.assertTrue(any(
            action.asset_id == "root.agents"
            and action.action == "migrate-agents-zones"
            for action in plan.safe_actions
        ))
        with self.assertRaisesRegex(sync.SyncBlocked, "rolled back: managed git diff check"):
            sync.apply_plan(
                plan,
                plan_fingerprint=plan.aggregate_fingerprint,
            )
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(stamp.read_text(encoding="utf-8"), "0.94.4\n")
    def test_heading_scanner_ignores_fenced_examples_and_fails_unclosed(self) -> None:
        heading = "## 1. Managed"
        payload = (
            "# Rule\n\n## 1. Managed\n\n"
            "```markdown\n## example\n```\n\n"
            "   ~~~~text\n## another example\n   ~~~~\n\n"
            "## 2. Next\n"
        ).encode("utf-8")
        sections = sync._markdown_heading_sections(payload, (heading,))
        block = payload[slice(*sections[heading])]
        self.assertIn(b"## example", block)
        self.assertIn(b"## another example", block)
        self.assertTrue(block.rstrip().endswith(b"~~~~"))
        with self.assertRaisesRegex(sync.SyncBlocked, "unclosed fenced code block"):
            sync._markdown_heading_sections(
                b"## 1. Managed\n\n```markdown\n## example\n",
                (heading,),
            )

    def test_markdown_structure_failure_rolls_back_before_stamp(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        agents = project / "AGENTS.md"
        agents.write_text(
            agents.read_text(encoding="utf-8").replace(
                "### 5.3 自改审计独立性",
                "## removed additive heading",
                1,
            ),
            encoding="utf-8",
        )
        before = agents.read_bytes()
        stamp = project / ".codex/.bridgeforge_codex_version"
        stamp.write_text("0.93.0\n", encoding="utf-8")
        plan = sync.build_plan(project, ROOT, "update")
        with mock.patch.object(
            sync,
            "_validate_changed_markdown",
            side_effect=sync.SyncBlocked(
                "managed Markdown contains an unclosed fenced code block"
            ),
        ):
            with self.assertRaisesRegex(sync.SyncBlocked, "rolled back"):
                sync.apply_plan(
                    plan,
                    plan_fingerprint=plan.aggregate_fingerprint,
                    confirmed_risk=True,
                )
        self.assertEqual(agents.read_bytes(), before)
        self.assertEqual(stamp.read_text(encoding="utf-8"), "0.93.0\n")

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
        stamp = project / ".codex/.bridgeforge_codex_version"
        stamp.write_text("0.90.0\n", encoding="utf-8")
        agents = project / "AGENTS.md"
        agents_text = agents.read_text(encoding="utf-8")
        agents_text = agents_text.replace(
            "<!-- [必填] 写明本项目的模块职责、依赖方向、数据流与外部副作用边界，填好删注释。 -->",
            "- 必须保持项目数据流单向。",
            1,
        ).replace(
            "<!-- [必填] 列出核心目录、入口、配置、测试和文档位置，并说明职责边界，填好删注释。 -->",
            "- `src/`：项目源码入口。",
            1,
        ).replace(
            "<!-- [必填] 写入本项目真实可执行的初始化、检查、测试、构建与运行命令，填好删注释。 -->",
            "- `.venv/Scripts/python.exe -m unittest`",
            1,
        )
        agents.write_text(agents_text, encoding="utf-8")
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
            [
                item["id"]
                for item in payload["required_actions"]
                if item["id"].startswith("R")
            ],
            ["R1", "R2"],
        )
        self.assertEqual(payload["recommended_selection"], ["R1", "R2"])
        self.assertEqual(payload["confirmation"]["business_confirmation_count"], "one")
        warning = payload["confirmation"]["warning"]
        self.assertIn("普通 Markdown 标题的本地内容不会因 A 被覆盖", warning)
        self.assertNotIn("普通受管区块以上游为准", warning)

        plan = sync.build_plan(project, ROOT, "update")
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
                self.assertFalse((project / ".codex/.bridgeforge_codex_version").exists())
                self.assertFalse((project / ".codex/managed-skeleton.json").exists())

    def test_pre_086_update_is_blocked(self) -> None:
        project = self.make_project()
        (project / ".codex").mkdir()
        (project / ".codex/.bridgeforge_codex_version").write_text(
            "0.85.9\n", encoding="utf-8"
        )
        plan = sync.build_plan(project, ROOT, "update")
        self.assertTrue(plan.blockers)
        self.assertIn("predates", " ".join(plan.blockers))

    def test_legacy_stamp_requires_risk_and_migrates_stamp_last(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        current = project / ".codex/.bridgeforge_codex_version"
        legacy = project / ".codex/.bridgeforge_version"
        current.replace(legacy)
        legacy.write_text("0.90.0\n", encoding="utf-8")

        plan = sync.build_plan(project, ROOT, "auto")
        migration = next(
            item
            for item in plan.risk_actions
            if item.asset_id == "codex.legacy-version-stamp-migration"
        )
        self.assertEqual(migration.action, "migrate-stamp")

        declined = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
            decline_risk=True,
        )
        self.assertFalse(declined.stamp_written_last)
        self.assertTrue(legacy.is_file())
        self.assertFalse(current.exists())

        plan = sync.build_plan(project, ROOT, "auto")
        applied = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
            confirmed_risk=True,
        )
        self.assertTrue(applied.stamp_written_last)
        self.assertFalse(legacy.exists())
        self.assertEqual(current.read_text(encoding="utf-8"), f"{CURRENT_VERSION}\n")

    def test_dual_or_malformed_stamps_block_with_zero_writes(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        legacy = project / ".codex/.bridgeforge_version"
        legacy.write_text("0.90.0\n", encoding="utf-8")
        dual = sync.build_plan(project, ROOT, "auto")
        self.assertIn("both legacy", " ".join(dual.blockers))
        with self.assertRaises(sync.SyncBlocked):
            sync.apply_plan(dual, plan_fingerprint=dual.aggregate_fingerprint)
        self.assertEqual(legacy.read_text(encoding="utf-8"), "0.90.0\n")

        (project / ".codex/.bridgeforge_codex_version").unlink()
        legacy.write_text("not-semver\n", encoding="utf-8")
        malformed = sync.build_plan(project, ROOT, "auto")
        self.assertIn("stable SemVer", " ".join(malformed.blockers))
        with self.assertRaises(sync.SyncBlocked):
            sync.apply_plan(malformed, plan_fingerprint=malformed.aggregate_fingerprint)
        self.assertEqual(legacy.read_text(encoding="utf-8"), "not-semver\n")

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
