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
PROJECT_SYNC_LEGACY_FIXTURE_REVISION = "1e4124358a5d0c6cee9dd73bcb7b18bc904515c9"


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

    def prepare_project_runtime(self, project: Path) -> Path:
        python = project / ".venv" / "Scripts" / "python.exe"
        if not python.is_file():
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "venv",
                    "--without-pip",
                    str(project / ".venv"),
                ],
                cwd=project,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return python

    def apply_init(self, project: Path) -> sync.Receipt:
        self.prepare_project_runtime(project)
        plan = sync.build_plan(project, ROOT, "init")
        self.assertFalse(plan.blockers)
        self.assertFalse(plan.risk_actions)
        receipt = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
        )
        self.assertEqual(receipt.release_preflight_status, "not_applicable")
        return receipt

    def init_git_project(self, project: Path) -> None:
        subprocess.run(["git", "init"], cwd=project, check=True, capture_output=True)
        (project / "README.md").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=project, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=BridgeForge Test",
                "-c",
                "user.email=bridgeforge@example.invalid",
                "commit",
                "-m",
                "chore: fixture baseline",
            ],
            cwd=project,
            check=True,
            capture_output=True,
        )

    @staticmethod
    def legacy_agents(*, filled: bool = True, project_name: str = "fixture") -> str:
        text = git_blob(
            PROJECT_SYNC_LEGACY_FIXTURE_REVISION,
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
        self.assertEqual(
            precommit["region"]["begin"],
            "# >>> BRIDGEFORGE_CODEX_MANAGED_BEGIN",
        )
        self.assertEqual(
            precommit["region"]["end"],
            "# <<< BRIDGEFORGE_CODEX_MANAGED_END",
        )
        self.assertNotIn("historical_sha256", precommit)
        self.assertNotIn("historical_sha256", precommit["region"])
        hooks_config = next(
            item for item in contract["assets"] if item["id"] == "codex.hooks-config"
        )
        self.assertEqual(
            hooks_config["merge_validation"]["format"],
            "codex-hooks-zones-v2",
        )
        self.assertTrue(hooks_config["merge_validation"]["required_handlers"])
        for handler in hooks_config["merge_validation"]["required_handlers"]:
            self.assertRegex(
                handler["id"],
                r"^bridgeforge-codex\.project-hook\.v1:",
            )
            self.assertRegex(handler["sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertRegex(
            hooks_config["merge_validation"]["current_projection_sha256"],
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertNotIn(
            "historical_projection_sha256",
            hooks_config["merge_validation"],
        )
        self.assertEqual(
            set(hooks_config["merge_validation"]["managed_top_level"]),
            {"description"},
        )
        self.assertIn(
            "BridgeForge project lifecycle hooks. This is the only managed "
            "Codex hook registration source.",
            hooks_config["merge_validation"][
                "managed_top_level_historical"
            ]["description"],
        )
        readme = next(
            item for item in contract["assets"] if item["id"] == "codex.doc.readme"
        )
        self.assertRegex(
            readme["managed_blocks"]["current_projection_sha256"],
            r"^sha256:[0-9a-f]{64}$",
        )
        self.assertIn(
            "1.4.11",
            readme["managed_blocks"]["historical_projection_sha256"],
        )
        self.assertIn(
            readme["managed_blocks"]["current_projection_sha256"],
            readme["managed_blocks"]["historical_projection_sha256"]["1.4.11"],
        )
        baselines = manifest_builder._baseline_revisions(ROOT)
        assets_by_id = {item["id"]: item for item in contract["assets"]}
        for asset_id, versions in {
            "codex.doc.readme": ("0.94.0", "0.94.1"),
        }.items():
            for version in versions:
                with self.subTest(asset_id=asset_id, projection_version=version):
                    historical_asset = manifest_builder._historical_contract_asset(
                        ROOT,
                        baselines[version],
                        asset_id,
                    )
                    self.assertIsNotNone(historical_asset)
                    assert historical_asset is not None
                    historical_payload = manifest_builder._git_blob_at(
                        ROOT,
                        baselines[version],
                        historical_asset["source"],
                    )
                    self.assertIsNotNone(historical_payload)
                    assert historical_payload is not None
                    historical_projection = (
                        manifest_builder._managed_markdown_projection_sha256(
                            ROOT,
                            historical_asset,
                            historical_payload,
                        )
                    )
                    self.assertIn(
                        historical_projection,
                        assets_by_id[asset_id]["managed_blocks"]
                        ["historical_projection_sha256"][version],
                    )
        active = next(item for item in contract["assets"] if item["id"] == "root.agents")
        self.assertIn("0.86.0", active["historical_sha256"])
        self.assertIn("0.90.0", active["historical_sha256"])
        self.assertNotIn("managed_blocks", active)
        self.assertNotIn("section_layout", active)
        zones = active["agents_zones"]
        self.assertEqual(zones["format"], "bridgeforge-agents-zones")
        self.assertNotIn("legacy_section_migrations", zones["project"])
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
            "1.4.5",
            "1.4.7",
            "1.4.9",
            "1.4.11",
            "1.4.14",
            "1.4.22",
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

    def test_versioned_history_keeps_unchanged_payload_for_every_release(self) -> None:
        baselines = {"0.86.0": "revision-a", "0.86.7": "revision-b"}
        payload = (
            b"prefix\n"
            b"<!-- PUBLIC:BEGIN -->\npublic\n<!-- PUBLIC:END -->\n"
            b"## Managed\nmanaged\n## Project\nproject\n"
        )
        with mock.patch.object(
            manifest_builder,
            "_git_blob_at",
            return_value=payload,
        ):
            whole = manifest_builder._merge_history(
                {}, ROOT, "fixture.txt", baselines
            )
            public = manifest_builder._merge_agents_public_history(
                {},
                ROOT,
                "fixture.md",
                baselines,
                "<!-- PUBLIC:BEGIN -->",
                "<!-- PUBLIC:END -->",
            )
            layout = manifest_builder._merge_layout_history(
                {},
                ROOT,
                "fixture.md",
                baselines,
                ["## Managed"],
            )
            residual = manifest_builder._merge_layout_residual_history(
                {},
                ROOT,
                "fixture.md",
                baselines,
                {
                    "sections": [{"heading": "## Managed"}],
                    "groups": [],
                },
            )

        for history in (whole, public, residual):
            self.assertEqual(set(history), set(baselines))
            self.assertEqual(history["0.86.0"], history["0.86.7"])
        self.assertEqual(set(layout["## Managed"]), set(baselines))
        self.assertEqual(
            layout["## Managed"]["0.86.0"],
            layout["## Managed"]["0.86.7"],
        )

    def test_agents_zones_rejects_parallel_legacy_ownership_rules(self) -> None:
        contract = json.loads(
            (ROOT / "templates/managed-skeleton.json").read_text(encoding="utf-8")
        )
        asset = next(item for item in contract["assets"] if item["id"] == "root.agents")
        invalid_variants = (
            {"managed_blocks": {"format": "markdown-headings"}},
            {"section_layout": {"format": "markdown-section-layout"}},
            {"legacy_section_migrations": []},
        )
        for variant in invalid_variants:
            with self.subTest(variant=next(iter(variant))):
                invalid = copy.deepcopy(contract)
                invalid_asset = next(
                    item for item in invalid["assets"] if item["id"] == asset["id"]
                )
                key, value = next(iter(variant.items()))
                if key == "legacy_section_migrations":
                    invalid_asset["agents_zones"]["project"][key] = value
                else:
                    invalid_asset[key] = value
                with tempfile.TemporaryDirectory(dir=ROOT) as raw:
                    path = Path(raw) / "managed-skeleton.json"
                    path.write_text(json.dumps(invalid), encoding="utf-8")
                    with self.assertRaisesRegex(
                        ValueError,
                        "agents_zones as its only ownership rule",
                    ):
                        manifest_builder.rebuild_managed_contract(path, write=False)

    def test_strict_historical_contract_asset_rejects_corruption(self) -> None:
        invalid_payloads = (
            None,
            b"{not-json",
            json.dumps({"schema_version": 2, "assets": {}}).encode("utf-8"),
            json.dumps({
                "schema_version": 2,
                "assets": ["not-an-asset"],
            }).encode("utf-8"),
            json.dumps({
                "schema_version": 2,
                "assets": [
                    {"id": "codex.precommit"},
                    {"id": "codex.precommit"},
                ],
            }).encode("utf-8"),
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), mock.patch.object(
                manifest_builder,
                "_git_blob_at",
                return_value=payload,
            ):
                with self.assertRaises(ValueError):
                    manifest_builder._historical_contract_asset(
                        ROOT,
                        "historical-revision",
                        "codex.precommit",
                        strict=True,
                    )

        valid_without_asset = json.dumps({
            "schema_version": 2,
            "assets": [{"id": "root.agents"}],
        }).encode("utf-8")
        with mock.patch.object(
            manifest_builder,
            "_git_blob_at",
            return_value=valid_without_asset,
        ):
            self.assertIsNone(
                manifest_builder._historical_contract_asset(
                    ROOT,
                    "historical-revision",
                    "codex.precommit",
                    strict=True,
                )
            )

        schema_v1 = json.dumps({
            "schema_version": 1,
            "managed_regions": [{
                "path": ".githooks/pre-commit",
                "begin": "# BEGIN",
                "end": "# END",
            }],
        }).encode("utf-8")
        with mock.patch.object(
            manifest_builder,
            "_git_blob_at",
            return_value=schema_v1,
        ):
            historical_asset = manifest_builder._historical_contract_asset(
                ROOT,
                "historical-revision",
                "codex.precommit",
                strict=True,
            )
        self.assertIsNone(historical_asset)

    def test_region_planner_rejects_legacy_marker_without_writes(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        precommit = project / ".githooks/pre-commit"
        precommit.write_bytes(
            precommit.read_bytes()
            .replace(
                b"# >>> BRIDGEFORGE_CODEX_MANAGED_BEGIN",
                b"# >>> BRIDGEFORGE_MANAGED_BEGIN",
                1,
            )
            .replace(
                b"# <<< BRIDGEFORGE_CODEX_MANAGED_END",
                b"# <<< BRIDGEFORGE_MANAGED_END",
                1,
            )
        )
        before = precommit.read_bytes()
        stamp = project / ".codex/.bridgeforge_codex_version"

        plan = sync.build_plan(project, ROOT, "update")
        self.assertFalse(any(
            item.asset_id == "codex.precommit" for item in plan.actions
        ))
        self.assertTrue(any(
            item.asset_id == "codex.precommit"
            and "region ownership is ambiguous" in item.reason
            for item in plan.gaps
        ))
        receipt = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
        )
        self.assertEqual(precommit.read_bytes(), before)
        self.assertFalse(receipt.stamp_written_last)
        self.assertEqual(
            stamp.read_text(encoding="utf-8"),
            CURRENT_VERSION + "\n",
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
            "target_cleanup.py",
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
        self.assertIn(".codex/hooks/target_cleanup.py", retirement_targets)
        target_cleanup = next(
            asset
            for asset in contract["assets"]
            if asset["id"] == "codex.hook.target-cleanup"
        )
        self.assertNotIn("source", target_cleanup)
        self.assertNotIn("current_sha256", target_cleanup)
        self.assertEqual(
            target_cleanup["historical_source"],
            "templates/hooks/target_cleanup.py",
        )
        self.assertIn("project-owned hook name", target_cleanup["retirement_guidance"])

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

    def test_exact_legacy_layout_requires_explicit_zone_adaptation(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        agents = project / "AGENTS.md"
        agents.write_text(
            self.legacy_agents(project_name=project.name),
            encoding="utf-8",
        )
        retired_hook = project / ".codex/hooks/context_warning.py"
        retired_hook.write_bytes(git_blob(
            PROJECT_SYNC_LEGACY_FIXTURE_REVISION,
            "templates/codex/hooks/context_warning.py",
        ))
        stamp = project / ".codex/.bridgeforge_codex_version"
        stamp.write_text("0.94.2\n", encoding="utf-8")

        plan = sync.build_plan(project, ROOT, "update")
        self.assertTrue(any(
            item.asset_id == "root.agents"
            and "does not use the current public/project zones" in item.reason
            for item in plan.gaps
        ))
        before = agents.read_bytes()
        with self.assertRaisesRegex(sync.SyncBlocked, "selected-adaptation"):
            sync.apply_plan(
                plan,
                plan_fingerprint=plan.aggregate_fingerprint,
                confirmed_risk=True,
            )
        self.assertEqual(agents.read_bytes(), before)
        self.assertEqual(stamp.read_text(encoding="utf-8"), "0.94.2\n")

    def test_unzoned_agents_with_other_project_name_require_explicit_adaptation(self) -> None:
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
        self.assertTrue(any(
            item.asset_id == "root.agents"
            and "does not use the current public/project zones" in item.reason
            for item in plan.gaps
        ))
        before = agents.read_bytes()
        with self.assertRaisesRegex(sync.SyncBlocked, "selected-adaptation"):
            sync.apply_plan(
                plan,
                plan_fingerprint=plan.aggregate_fingerprint,
                confirmed_risk=True,
            )
        self.assertEqual(agents.read_bytes(), before)

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
                    legacy = self.legacy_agents(project_name=project.name)
                    heading = "## 1. 架构红线"
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
                    and "does not use the current public/project zones" in item.reason
                    for item in plan.gaps
                ))
                with self.assertRaisesRegex(sync.SyncBlocked, "selected-adaptation"):
                    sync.apply_plan(
                        plan,
                        plan_fingerprint=plan.aggregate_fingerprint,
                    )
                self.assertEqual(agents.read_bytes(), before)

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
            and "does not use the current public/project zones" in item.reason
            for item in plan.gaps
        ))
        with self.assertRaisesRegex(sync.SyncBlocked, "selected-adaptation"):
            sync.apply_plan(
                plan,
                plan_fingerprint=plan.aggregate_fingerprint,
            )
        self.assertEqual(agents.read_bytes(), before)

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

    def test_missing_duplicate_or_reversed_zone_markers_fail_closed(self) -> None:
        project = self.make_project()
        contract = json.loads(
            (ROOT / "templates/managed-skeleton.json").read_text(encoding="utf-8")
        )
        asset = next(item for item in contract["assets"] if item["id"] == "root.agents")
        source = (ROOT / "templates/AGENTS.md").read_bytes()
        target = project / "AGENTS.md"
        public_begin = b"<!-- BRIDGEFORGE:PUBLIC:BEGIN -->"
        project_begin = b"<!-- BRIDGEFORGE:PROJECT:BEGIN -->"
        reversed_markers = source.replace(public_begin, b"<!-- TEMP -->", 1)
        reversed_markers = reversed_markers.replace(project_begin, public_begin, 1)
        reversed_markers = reversed_markers.replace(b"<!-- TEMP -->", project_begin, 1)
        cases = {
            "missing": (
                source.replace(b"<!-- BRIDGEFORGE:PROJECT:END -->", b""),
                "missing or duplicated",
            ),
            "duplicate": (
                source.replace(public_begin, public_begin + b"\n" + public_begin, 1),
                "missing or duplicated",
            ),
            "reversed": (reversed_markers, "reversed or nested"),
        }
        for name, (payload, expected_reason) in cases.items():
            with self.subTest(case=name):
                target.write_bytes(payload)
                actions, gaps = sync._plan_whole(asset, source, target, project)
                self.assertEqual(actions, [])
                self.assertTrue(any(expected_reason in item.reason for item in gaps))
                action_required = sync._action_required_items(gaps)
                self.assertEqual([item["id"] for item in action_required], ["G1"])
                self.assertIn("marker", action_required[0]["classification_reason"])

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
            and "does not use the current public/project zones" in item.reason
            for item in plan.gaps
        ))
        action_required = sync._plan_payload(plan)["action_required_items"]
        self.assertEqual(
            [item["id"] for item in action_required],
            [f"G{index}" for index in range(1, len(action_required) + 1)],
        )
        custom_item = action_required[0]
        self.assertIn("AGENTS.md lines", custom_item["source_location"])
        self.assertIn("unzoned AGENTS ownership", custom_item["classification_reason"])
        self.assertIn("project zone", custom_item["recommended_action"])
        self.assertFalse(any(item.asset_id == "root.agents" for item in plan.actions))
        with self.assertRaisesRegex(sync.SyncBlocked, "selected-adaptation"):
            sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        self.assertEqual(agents.read_bytes(), before)
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
            and "does not use the current public/project zones" in item.reason
            for item in plan.gaps
        ))
        action_required = sync._plan_payload(plan)["action_required_items"]
        self.assertEqual(len(action_required), 1)
        self.assertIn("项目本地表达扩展", action_required[0]["content_summary"])
        self.assertIn("project zone", action_required[0]["recommended_action"])
        self.assertFalse(any(item.asset_id == "root.agents" for item in plan.actions))
        with self.assertRaisesRegex(sync.SyncBlocked, "selected-adaptation"):
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
            and "does not use the current public/project zones" in item.reason
            for item in plan.gaps
        ))
        self.assertFalse(any(item.asset_id == "root.agents" for item in plan.actions))
        with self.assertRaisesRegex(sync.SyncBlocked, "selected-adaptation"):
            sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
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
            target.write_bytes(
                git_blob(PROJECT_SYNC_LEGACY_FIXTURE_REVISION, legacy_source)
            )
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
        self.assertEqual(
            sync._plan_payload(modified_plan)["action_required_items"],
            [],
        )
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
            payload = git_blob(PROJECT_SYNC_LEGACY_FIXTURE_REVISION, legacy_source)
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
            and "does not use the current public/project zones" in gap.reason
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
        with self.assertRaisesRegex(sync.SyncBlocked, "selected-adaptation"):
            sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        self.assertEqual(agents.read_bytes(), before)
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

    def test_confirmed_absorption_is_preflighted_before_any_write(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        target = project / "doc/README.md"
        target.write_text(
            target.read_text(encoding="utf-8").replace(
                "系统当前架构、关键接口、数据流与 ADR",
                "项目定制的架构目录说明",
                1,
            ),
            encoding="utf-8",
        )
        before = target.read_bytes()
        stamp = project / ".codex/.bridgeforge_codex_version"
        stamp_before = stamp.read_bytes()
        plan = sync.build_plan(project, ROOT, "update")
        self.assertTrue(plan.absorption_actions)
        items = sync._release_preflight_items(
            RuntimeError("selected absorption is not releasable")
        )
        checkpoints: list[str] = []

        with mock.patch.object(
            sync,
            "_run_release_preflight",
            side_effect=sync.ReleasePreflightBlocked("preflight rejected", items),
        ):
            with self.assertRaises(sync.ReleasePreflightBlocked) as captured:
                sync.apply_plan(
                    plan,
                    plan_fingerprint=plan.aggregate_fingerprint,
                    confirmed_risk=True,
                    checkpoint=checkpoints.append,
                )

        self.assertIn("zero writes performed", str(captured.exception))
        self.assertEqual(
            captured.exception.items[0]["recoverability"],
            "zero writes were performed",
        )
        self.assertEqual(checkpoints, [])
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(stamp.read_bytes(), stamp_before)

    def test_unzoned_agents_stop_before_release_preflight_and_write(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        stamp = project / ".codex/.bridgeforge_codex_version"
        stamp.write_text("0.94.4\n", encoding="utf-8")
        target = project / "AGENTS.md"
        target.write_text(self.legacy_agents(), encoding="utf-8")
        before = target.read_bytes()
        with mock.patch.object(sync, "_run_release_preflight") as preflight:
            plan = sync.build_plan(project, ROOT, "update")
        preflight.assert_not_called()
        self.assertTrue(any(
            gap.asset_id == "root.agents"
            and "does not use the current public/project zones" in gap.reason
            for gap in plan.gaps
        ))
        action_required = sync._plan_payload(plan)["action_required_items"]
        self.assertTrue(action_required[0]["adaptation_eligible"])
        adapted = sync._explicit_agents_action(plan, action_required[0])
        self.assertEqual(adapted.payload.count(before), 1)
        with self.assertRaisesRegex(sync.SyncBlocked, "selected-adaptation"):
            sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
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

    def test_unclosed_legacy_agents_lists_action_required_without_writing(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        agents = project / "AGENTS.md"
        agents.write_text(
            self.legacy_agents() + "\n```markdown\n## project example\n",
            encoding="utf-8",
        )
        before = agents.read_bytes()
        stamp = project / ".codex/.bridgeforge_codex_version"
        stamp.write_text("0.94.4\n", encoding="utf-8")

        plan = sync.build_plan(project, ROOT, "update")
        action_required = sync._plan_payload(plan)["action_required_items"]
        self.assertEqual([item["id"] for item in action_required], ["G1"])
        self.assertIn("unzoned AGENTS ownership", action_required[0]["classification_reason"])
        self.assertIn("project zone", action_required[0]["recommended_action"])
        self.assertFalse(action_required[0]["adaptation_eligible"])
        with self.assertRaisesRegex(sync.SyncBlocked, "selected-adaptation"):
            sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        self.assertEqual(agents.read_bytes(), before)
        self.assertEqual(stamp.read_text(encoding="utf-8"), "0.94.4\n")

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
            with self.assertRaisesRegex(sync.SyncBlocked, "selected-adaptation"):
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

    def test_hooks_zones_canonicalize_trusted_mixed_duplicate_and_preserve_project(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        hooks_path = project / ".codex/hooks.json"
        hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
        required: list[dict[str, str]] = []
        for event, groups in hooks["hooks"].items():
            for group in groups:
                matcher = str(group.get("matcher", ""))
                for handler in group["hooks"]:
                    handler.pop("bridgeforgeCodexId", None)
                    stage = sync._dispatcher_stage(handler)
                    assert stage is not None
                    required.append({
                        "event": event,
                        "matcher": matcher,
                        "stage": stage,
                        "sha256": manifest_builder._canonical_json_sha256(handler),
                    })
        session_groups = hooks["hooks"]["SessionStart"]
        legacy_session = copy.deepcopy(session_groups[0]["hooks"][0])
        project_handler = {
            "type": "command",
            "command": "python .codex/hooks/vault_junction_check.py",
            "comment": "project-owned vault handler",
        }
        session_groups[:] = [
            {"hooks": [project_handler, legacy_session]},
            {"hooks": [copy.deepcopy(legacy_session)]},
        ]
        hooks_path.write_text(
            json.dumps(hooks, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        contract_path = project / ".codex/managed-skeleton.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        hooks_asset = next(
            item for item in contract["assets"] if item["id"] == "codex.hooks-config"
        )
        hooks_asset["merge_validation"] = {
            "format": "codex-hooks-dispatchers-v1",
            "required_handlers": required,
            "current_projection_sha256": manifest_builder._canonical_json_sha256(required),
        }
        contract["release_version"] = "1.4.11"
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (project / ".codex/.bridgeforge_codex_version").write_text(
            "1.4.11\n",
            encoding="utf-8",
        )

        plan = sync.build_plan(project, ROOT, "update")
        self.assertFalse(
            any(gap.asset_id == "codex.hooks-config" for gap in plan.gaps)
        )
        action = next(
            item for item in plan.safe_actions if item.asset_id == "codex.hooks-config"
        )
        self.assertIsNotNone(action.payload)
        migrated = json.loads((action.payload or b"").decode("utf-8"))
        session_handlers = [
            handler
            for group in migrated["hooks"]["SessionStart"]
            for handler in group["hooks"]
        ]
        self.assertEqual(session_handlers.count(project_handler), 1)
        managed = [
            handler
            for handler in session_handlers
            if handler.get("bridgeforgeCodexId")
            == "bridgeforge-codex.project-hook.v1:session-start"
        ]
        self.assertEqual(len(managed), 1)
        managed_group = next(
            group
            for group in migrated["hooks"]["SessionStart"]
            if group["hooks"] == managed
        )
        self.assertEqual(managed_group["hooks"], managed)

        hooks["hooks"]["SessionStart"][0]["hooks"][1]["comment"] = "drifted"
        hooks_path.write_text(
            json.dumps(hooks, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        blocked = sync.build_plan(project, ROOT, "update")
        self.assertTrue(
            any(
                gap.asset_id == "codex.hooks-config"
                and "no trusted ownership" in gap.reason
                for gap in blocked.gaps
            )
        )

    def test_hooks_zones_reject_duplicate_json_keys_without_action(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        hooks_path = project / ".codex/hooks.json"
        canonical = json.loads(hooks_path.read_text(encoding="utf-8"))
        hooks_path.write_text(
            '{"hooks": {}, "hooks": '
            + json.dumps(canonical["hooks"], ensure_ascii=False)
            + ', "description": '
            + json.dumps(canonical["description"], ensure_ascii=False)
            + "}\n",
            encoding="utf-8",
        )

        plan = sync.build_plan(project, ROOT, "update")

        self.assertFalse(
            any(item.asset_id == "codex.hooks-config" for item in plan.actions)
        )
        hooks_gaps = [
            item for item in plan.gaps if item.asset_id == "codex.hooks-config"
        ]
        self.assertEqual(len(hooks_gaps), 1)
        self.assertIn("duplicate JSON key: hooks", hooks_gaps[0].reason)

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

    def test_target_cleanup_retirement_removes_only_a_published_copy(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        target = project / ".codex/hooks/target_cleanup.py"
        target.write_bytes(
            git_blob(
                "5a6c5564e3d828358c850113b856bcd4f74e15e0",
                "templates/hooks/target_cleanup.py",
            )
        )
        stamp = project / ".codex/.bridgeforge_codex_version"
        stamp.write_text("1.4.7\n", encoding="utf-8")

        plan = sync.build_plan(project, ROOT, "update")
        actions = [
            item
            for item in plan.risk_actions
            if item.asset_id == "codex.hook.target-cleanup"
        ]
        self.assertEqual(len(actions), 1)
        declined = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
            decline_risk=True,
        )
        self.assertTrue(target.is_file())
        self.assertFalse(declined.stamp_written_last)
        self.assertEqual(stamp.read_text(encoding="utf-8"), "1.4.7\n")

        plan = sync.build_plan(project, ROOT, "update")
        receipt = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
            confirmed_risk=True,
        )
        self.assertFalse(target.exists())
        self.assertIn("codex.hook.target-cleanup", receipt.risk_applied)
        replan = sync.build_plan(project, ROOT, "update")
        self.assertFalse(
            any(
                item.asset_id == "codex.hook.target-cleanup"
                for item in replan.actions + replan.gaps
            )
        )

    def test_modified_target_cleanup_is_preserved_with_project_guidance(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        target = project / ".codex/hooks/target_cleanup.py"
        payload = b"project-owned cleanup policy\n"
        target.write_bytes(payload)
        stamp = project / ".codex/.bridgeforge_codex_version"
        stamp.write_text("1.4.7\n", encoding="utf-8")

        plan = sync.build_plan(project, ROOT, "update")
        gaps = [
            item
            for item in plan.gaps
            if item.asset_id == "codex.hook.target-cleanup"
        ]
        self.assertEqual(len(gaps), 1)
        self.assertIn("preserve verbatim", gaps[0].reason)
        self.assertIn("project-owned hook name", gaps[0].reason)
        self.assertFalse(
            any(
                item.asset_id == "codex.hook.target-cleanup"
                for item in plan.actions
            )
        )

        receipt = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
        )
        self.assertEqual(target.read_bytes(), payload)
        self.assertFalse(receipt.stamp_written_last)
        self.assertEqual(stamp.read_text(encoding="utf-8"), "1.4.7\n")

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

    def test_release_preflight_passes_before_init_stamp(self) -> None:
        project = self.make_project()
        self.prepare_project_runtime(project)
        self.init_git_project(project)
        plan = sync.build_plan(project, ROOT, "init")

        receipt = sync.apply_plan(
            plan,
            plan_fingerprint=plan.aggregate_fingerprint,
        )

        self.assertEqual(receipt.release_preflight_status, "passed")
        self.assertEqual(receipt.release_preflight_classification, "mixed")
        self.assertTrue(receipt.stamp_written_last)
        self.assertIn("release_preflight", receipt.timings_ms)

    def test_plan_reports_release_preflight_failure_before_any_write(self) -> None:
        project = self.make_project()
        self.init_git_project(project)
        before_status = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=project,
            capture_output=True,
            check=True,
        ).stdout
        items = sync._release_preflight_items(
            RuntimeError("prospective managed projection drifted")
        )

        with mock.patch.object(sync, "_project_requirement_items", return_value=[]), \
                mock.patch.object(
                    sync,
                    "_run_release_preflight",
                    side_effect=sync.ReleasePreflightBlocked("preflight rejected", items),
                ):
            plan = sync.build_plan(project, ROOT, "init")
            payload = sync._plan_payload(plan)
            with self.assertRaises(sync.ReleasePreflightBlocked):
                sync.apply_plan(
                    plan,
                    plan_fingerprint=plan.aggregate_fingerprint,
                )

        self.assertEqual(plan.release_preflight_status, "blocked")
        self.assertEqual(payload["target_readiness"], "action_required")
        self.assertEqual(payload["release_preflight_items"][0]["id"], "G1")
        self.assertEqual(payload["action_required_items"][0]["id"], "G1")
        self.assertIsInstance(payload["release_preflight_timing_ms"], float)
        self.assertGreaterEqual(payload["release_preflight_timing_ms"], 0)
        self.assertEqual(
            payload["release_preflight_items"][0]["recoverability"],
            "zero writes were performed",
        )
        self.assertNotEqual(payload["readiness"], "ready")
        self.assertEqual(
            subprocess.run(
                ["git", "status", "--porcelain=v1"],
                cwd=project,
                capture_output=True,
                check=True,
            ).stdout,
            before_status,
        )
        self.assertFalse((project / ".codex").exists())

    def test_plan_preflights_the_recommended_risk_actions(self) -> None:
        project = self.make_project()
        self.prepare_project_runtime(project)
        (project / ".codex").mkdir(exist_ok=True)
        (project / sync.LEGACY_STAMP).write_text("0.90.0\n", encoding="utf-8")
        items = sync._release_preflight_items(
            RuntimeError("recommended risk projection rejected")
        )

        with (
            mock.patch.object(
                sync,
                "_project_requirement_items",
                return_value=[{
                    "id": "N1",
                    "affects_readiness": False,
                    "category": "unsupported_legacy_notice",
                }],
            ),
            mock.patch.object(sync, "_plan_memory_schema", return_value=([], [])),
            mock.patch.object(
                sync,
                "_run_release_preflight",
                side_effect=sync.ReleasePreflightBlocked(
                    "recommended risk projection rejected",
                    items,
                ),
            ) as preflight,
        ):
            plan = sync.build_plan(project, ROOT, "update")

        self.assertTrue(plan.risk_actions)
        self.assertEqual(plan.release_preflight_status, "blocked")
        self.assertTrue(plan.release_preflight_items)
        preflight.assert_called()

    def test_recommended_snapshot_materializes_safe_risk_and_absorption(self) -> None:
        project = self.make_project()
        safe = sync.Action(
            asset_id="safe",
            target="safe.txt",
            action="create",
            classification="safe",
            reason="fixture",
            before_sha256=None,
            after_sha256=sync._sha256_bytes(b"safe\n"),
            payload=b"safe\n",
        )
        risk = sync.Action(
            asset_id="risk",
            target="risk.txt",
            action="retire",
            classification="risk",
            reason="fixture",
            before_sha256=sync._sha256_bytes(b"old\n"),
            after_sha256=None,
        )
        absorb_before = b"# Project\n\n## Managed\nold\n"
        absorb_after = b"# Project\n\n## Managed\nnew\n"
        (project / "absorb.md").write_bytes(absorb_before)
        absorb = sync.Action(
            asset_id="absorb",
            target="absorb.md",
            action="replace-managed-markdown",
            classification="absorb",
            reason="fixture",
            before_sha256=sync._sha256_bytes(absorb_before),
            after_sha256=sync._sha256_bytes(absorb_after),
            managed_blocks=("## Managed",),
            payload=absorb_after,
            source_payload=absorb_after,
        )
        plan = sync.Plan(
            project_root=str(project),
            template_root=str(ROOT),
            mode="update",
            current_version=CURRENT_VERSION,
            previous_version="0.90.0",
            contract_sha256="fixture",
            actions=[safe, risk, absorb],
            gaps=[],
            blockers=[],
            project_requirements=[],
        )

        snapshot = sync._prospective_snapshot(
            sync._recommended_plan_actions(plan)
        )

        self.assertEqual(
            snapshot,
            {
                "safe.txt": b"safe\n",
                "risk.txt": None,
                "absorb.md": absorb_after,
            },
        )

    def test_selected_explicit_region_adaptation_is_transactional(self) -> None:
        project = self.make_project()
        self.prepare_project_runtime(project)
        self.init_git_project(project)
        initial = sync.build_plan(project, ROOT, "init")
        sync.apply_plan(initial, plan_fingerprint=initial.aggregate_fingerprint)
        agents = project / "AGENTS.md"
        agents_text = agents.read_text(encoding="utf-8")
        agents_text = agents_text.replace(
            "<!-- 填 3-5 条“必须 X / 禁止 Y”硬约束（数据流方向 / 资源上限 / 时序约束），填好删注释。 -->",
            "- 必须保持 fixture 数据流单向。",
        ).replace(
            "<!-- 列顶层目录及职责（一行一个），帮 Codex 快速定位代码。跑 `ls` 看顶层照填。 -->",
            "- `src/`：fixture 源码入口。",
        ).replace(
            "<!-- 填项目构建 / 运行 / 测试 / 检查命令（每天敲得最多的几行），填好删注释。 -->",
            "- `.venv/Scripts/python.exe -m unittest`",
        )
        agents.write_text(agents_text, encoding="utf-8")
        gitignore = project / ".gitignore"
        gitignore.write_text(
            (
                gitignore.read_text(encoding="utf-8")
                if gitignore.is_file()
                else ""
            )
            + "\n.runtime/\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=project, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=BridgeForge Test",
                "-c",
                "user.email=bridgeforge@example.invalid",
                "commit",
                "-m",
                "chore: current skeleton",
            ],
            cwd=project,
            check=True,
            capture_output=True,
        )
        target = project / ".githooks" / "pre-commit"
        payload = target.read_bytes()
        begin = b"# >>> BRIDGEFORGE_CODEX_MANAGED_BEGIN"
        end = b"# <<< BRIDGEFORGE_CODEX_MANAGED_END"
        start = payload.index(begin)
        finish = payload.index(end) + len(end)
        target.write_bytes(
            payload[:start]
            + begin
            + b"\n# explicitly reviewed legacy managed bytes\n"
            + end
            + payload[finish:]
        )
        subprocess.run(["git", "add", "."], cwd=project, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=BridgeForge Test",
                "-c",
                "user.email=bridgeforge@example.invalid",
                "commit",
                "-m",
                "chore: legacy managed region",
            ],
            cwd=project,
            check=True,
            capture_output=True,
        )
        with mock.patch.object(sync, "_project_requirement_items", return_value=[]):
            plan = sync.build_plan(project, ROOT, "update")
            action_items = sync._plan_payload(plan)["action_required_items"]
            self.assertEqual(
                [item["id"] for item in action_items],
                ["G1"],
                sync._plan_payload(plan),
            )
            self.assertTrue(action_items[0]["adaptation_eligible"])
            before = target.read_bytes()
            with self.assertRaises(sync.ReleasePreflightBlocked):
                sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
            self.assertEqual(target.read_bytes(), before)

            receipt = sync.apply_plan(
                plan,
                plan_fingerprint=plan.aggregate_fingerprint,
                selected_adaptation_ids=("G1",),
            )
            self.assertEqual(receipt.selected_adaptation_ids, ("G1",))
            self.assertEqual(receipt.release_preflight_status, "passed")
            self.assertIsNotNone(receipt.adaptation_selection_fingerprint)
            proof_path = project / sync.ADAPTATION_RECEIPT
            self.assertTrue(proof_path.is_file())
            self.assertNotEqual(target.read_bytes(), before)
            replan = sync.build_plan(project, ROOT, "update")
            self.assertEqual(replan.actions, [])
            self.assertEqual(replan.gaps, [])
            self.assertEqual(replan.release_preflight_items, ())

    def test_explicit_agents_adaptation_preserves_raw_crlf_bytes(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        agents = project / "AGENTS.md"
        legacy = self.legacy_agents().replace("\n", "\r\n").encode("utf-8")
        agents.write_bytes(legacy)
        plan = sync.build_plan(project, ROOT, "update")
        item = sync._plan_payload(plan)["action_required_items"][0]
        self.assertTrue(item["adaptation_eligible"])
        action = sync._explicit_agents_action(plan, item)
        self.assertEqual(action.payload.count(legacy), 1)

    def test_selected_schema_v1_retirements_are_transactional(self) -> None:
        template_root = self.make_project()
        (template_root / "templates/scripts").mkdir(parents=True)
        (template_root / "templates/scripts/version_release.py").write_bytes(
            (ROOT / "templates/scripts/version_release.py").read_bytes()
        )
        (template_root / "templates/scripts/hooks_ownership.py").write_bytes(
            (ROOT / "templates/scripts/hooks_ownership.py").read_bytes()
        )
        (template_root / "templates/hooks").mkdir()
        (template_root / "templates/hooks/memory_lint.py").write_bytes(
            (ROOT / "templates/hooks/memory_lint.py").read_bytes()
        )
        (template_root / "VERSION").write_bytes((ROOT / "VERSION").read_bytes())
        project = self.make_project()
        self.prepare_project_runtime(project)
        self.init_git_project(project)
        published_contract = json.loads(
            (ROOT / "templates/managed-skeleton.json").read_text(encoding="utf-8")
        )
        retired_rules = [
            asset
            for asset in published_contract["assets"]
            if str(asset["id"]).startswith("codex.rule.")
        ]
        self.assertEqual(len(retired_rules), 8)
        attested_payload = b"already current but absent from the old contract\n"
        attested_asset = {
            "id": "codex.attested-current",
            "source": "templates/scripts/attested_current.py",
            "target": ".codex/scripts/attested_current.py",
            "strategy": "whole",
            "current_sha256": sync._sha256_bytes(attested_payload),
        }
        absent_retired_asset = copy.deepcopy(retired_rules[0])
        absent_retired_asset["id"] = "codex.retired-never-present"
        absent_retired_asset["target"] = ".codex/rules/never_present.md"
        (template_root / attested_asset["source"]).write_bytes(attested_payload)
        old_contract = {
            "schema_version": 1,
            "stamp": ".codex/.bridgeforge_codex_version",
            "whole_files": [
                ".codex/.bridgeforge_codex_version",
                ".codex/managed-skeleton.json",
            ],
            "managed_regions": [],
        }
        old_payload = (
            json.dumps(old_contract, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        contract = {
            "schema_version": 2,
            "release_version": CURRENT_VERSION,
            "host": "codex",
            "minimum_supported_version": "0.86.0",
            "stamp": ".codex/.bridgeforge_codex_version",
            "contract_target": ".codex/managed-skeleton.json",
            "contract_historical_sha256": {
                "0.90.0": [sync._sha256_bytes(sync._git_blob_bytes(old_payload))],
            },
            "assets": retired_rules + [absent_retired_asset, attested_asset],
        }
        contract_path = template_root / "templates/managed-skeleton.json"
        contract_path.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (project / ".codex").mkdir(exist_ok=True)
        (project / ".codex/managed-skeleton.json").write_bytes(old_payload)
        (project / ".codex/.bridgeforge_codex_version").write_text(
            "0.90.0\n",
            encoding="utf-8",
        )
        expected: dict[str, bytes] = {}
        for asset in retired_rules:
            target = project / asset["target"]
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = f"committed legacy rule for {asset['id']}\n".encode("utf-8")
            target.write_bytes(payload)
            expected[str(asset["target"])] = payload
        attested_target = project / attested_asset["target"]
        attested_target.parent.mkdir(parents=True, exist_ok=True)
        attested_target.write_bytes(attested_payload)
        gitignore = project / ".gitignore"
        gitignore.write_text(".runtime/\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=project, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=BridgeForge Test",
                "-c",
                "user.email=bridgeforge@example.invalid",
                "commit",
                "-m",
                "chore: schema v1 retired rules",
            ],
            cwd=project,
            check=True,
            capture_output=True,
        )
        for relative in expected:
            (project / relative).unlink()

        with mock.patch.object(sync, "_project_requirement_items", return_value=[]):
            plan = sync.build_plan(project, template_root, "update")
            items = sync._plan_payload(plan)["action_required_items"]
            self.assertEqual(len(items), 10, sync._plan_payload(plan))
            self.assertTrue(
                all(item["adaptation_eligible"] for item in items),
                sync._plan_payload(plan),
            )
            self.assertEqual(
                {str(item["asset_id"]) for item in items},
                {
                    *(str(asset["id"]) for asset in retired_rules),
                    str(absent_retired_asset["id"]),
                    str(attested_asset["id"]),
                },
            )
            absent_item = next(
                item
                for item in items
                if item["asset_id"] == absent_retired_asset["id"]
            )
            with (
                mock.patch.object(
                    sync,
                    "_lexical_entry_exists",
                    return_value=True,
                ),
                self.assertRaisesRegex(
                    sync.SyncBlocked,
                    "exists outside Git HEAD",
                ),
            ):
                sync._explicit_release_action(plan, absent_item)
            with self.assertRaises(sync.ReleasePreflightBlocked):
                sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
            self.assertTrue(all(
                not (project / relative).exists()
                for relative in expected
            ))
            written_targets: list[str] = []
            original_write = sync._Transaction.write

            def recording_write(
                transaction: sync._Transaction,
                target: Path,
                payload: bytes,
            ) -> None:
                written_targets.append(target.relative_to(project).as_posix())
                original_write(transaction, target, payload)

            with (
                mock.patch.object(sync, "_run_validation", return_value={}),
                mock.patch.object(
                    sync._Transaction,
                    "write",
                    autospec=True,
                    side_effect=recording_write,
                ),
            ):
                receipt = sync.apply_plan(
                    plan,
                    plan_fingerprint=plan.aggregate_fingerprint,
                    selected_adaptation_ids=tuple(item["id"] for item in items),
                )
            self.assertEqual(receipt.release_preflight_status, "passed")
            self.assertTrue(all(
                not (project / relative).exists()
                for relative in expected
            ))
            self.assertEqual(attested_target.read_bytes(), attested_payload)
            self.assertNotIn(
                attested_asset["target"],
                written_targets,
            )
            self.assertNotIn(
                absent_retired_asset["target"],
                written_targets,
            )
            replan = sync.build_plan(project, template_root, "update")
            self.assertEqual(replan.actions, [])
            self.assertEqual(replan.gaps, [])
            self.assertEqual(replan.release_preflight_items, ())

    def test_schema_v1_retirement_with_worktree_drift_is_ineligible(self) -> None:
        project = self.make_project()
        self.init_git_project(project)
        contract = json.loads(
            (ROOT / "templates/managed-skeleton.json").read_text(encoding="utf-8")
        )
        asset = next(
            item
            for item in contract["assets"]
            if str(item["id"]).startswith("codex.rule.")
        )
        target = project / asset["target"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("committed legacy rule\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=project, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=BridgeForge Test",
                "-c",
                "user.email=bridgeforge@example.invalid",
                "commit",
                "-m",
                "chore: legacy rule",
            ],
            cwd=project,
            check=True,
            capture_output=True,
        )
        target.write_text("dirty project rule\n", encoding="utf-8")
        plan = sync.Plan(
            project_root=str(project),
            template_root=str(ROOT),
            mode="update",
            current_version=CURRENT_VERSION,
            previous_version="0.90.0",
            contract_sha256="fixture",
            actions=[],
            gaps=[],
            blockers=[],
            project_requirements=[],
        )
        item = {
            "id": "G1",
            "asset_id": asset["id"],
            "target": asset["target"],
            "category": "release_transition_review",
        }
        with self.assertRaisesRegex(sync.SyncBlocked, "does not match Git HEAD"):
            sync._explicit_release_action(plan, item)

    def test_selected_adaptation_with_ordinary_gap_is_zero_write(self) -> None:
        project = self.make_project()
        self.apply_init(project)
        agents = project / "AGENTS.md"
        agents.write_text(self.legacy_agents(), encoding="utf-8")
        contract = json.loads(
            (ROOT / "templates/managed-skeleton.json").read_text(encoding="utf-8")
        )
        retired = next(
            asset
            for asset in contract["assets"]
            if asset["id"].startswith("codex.rule.")
        )
        retired_target = project / retired["target"]
        retired_target.parent.mkdir(parents=True, exist_ok=True)
        retired_target.write_bytes(b"project-owned retired rule\n")
        before_agents = agents.read_bytes()
        before_rule = retired_target.read_bytes()
        plan = sync.build_plan(project, ROOT, "update")
        action_required = sync._plan_payload(plan)["action_required_items"]
        self.assertEqual([item["id"] for item in action_required], ["G1"])
        self.assertTrue(any(gap.asset_id == retired["id"] for gap in plan.gaps))
        with self.assertRaisesRegex(sync.SyncBlocked, "ordinary gaps remain"):
            sync.apply_plan(
                plan,
                plan_fingerprint=plan.aggregate_fingerprint,
                selected_adaptation_ids=("G1",),
            )
        self.assertEqual(agents.read_bytes(), before_agents)
        self.assertEqual(retired_target.read_bytes(), before_rule)
        self.assertFalse((project / sync.ADAPTATION_RECEIPT).exists())

    def test_explicit_adaptation_rejects_reordered_g_ids(self) -> None:
        project = self.make_project()
        plan = sync.Plan(
            project_root=str(project),
            template_root=str(ROOT),
            mode="update",
            current_version="1.4.23",
            previous_version="1.4.22",
            contract_sha256="contract",
            actions=[],
            gaps=[],
            blockers=[],
            project_requirements=[],
            release_preflight_status="blocked",
            release_preflight_items=(
                {
                    "id": "legacy-a",
                    "asset_id": "codex.precommit",
                    "target": ".githooks/pre-commit",
                    "category": "release_transition_review",
                },
                {
                    "id": "legacy-b",
                    "asset_id": "codex.hooks",
                    "target": ".codex/hooks.json",
                    "category": "release_transition_review",
                },
            ),
            aggregate_fingerprint="aggregate",
        )
        with self.assertRaisesRegex(sync.SyncBlocked, "reordered"):
            sync._select_explicit_adaptations(plan, ("G2", "G1"))

    def test_explicit_hooks_external_drift_before_apply_is_zero_write(self) -> None:
        project = self.make_project()
        managed = project / "managed.txt"
        external = project / ".codex" / "hooks.json"
        stamp = project / ".codex" / ".bridgeforge_codex_version"
        external.parent.mkdir(parents=True)
        managed.write_bytes(b"managed before\n")
        external.write_bytes(b"external before\n")
        stamp.write_text("1.4.22\n", encoding="utf-8")
        action = sync.Action(
            asset_id="fixture.managed",
            target="managed.txt",
            action="replace",
            classification="safe",
            reason="fixture",
            before_sha256=sync._sha256_bytes(b"managed before\n"),
            after_sha256=sync._sha256_bytes(b"managed after\n"),
            payload=b"managed after\n",
        )
        plan = sync.Plan(
            project_root=str(project),
            template_root=str(ROOT),
            mode="update",
            current_version="1.4.23",
            previous_version="1.4.22",
            contract_sha256="fixture",
            actions=[action],
            gaps=[],
            blockers=[],
            project_requirements=[],
            aggregate_fingerprint="sha256:" + "a" * 64,
        )
        selected = [{
            "id": "G1",
            "asset_id": "codex.hooks-config",
            "target": ".codex/hooks.json",
            "category": "release_transition_review",
            "adaptation_eligible": True,
        }]
        canonical_item = {
            **selected[0],
            "before_sha256": "sha256:" + "b" * 64,
            "after_sha256": "sha256:" + "c" * 64,
            "project_before_sha256": "sha256:" + "d" * 64,
            "project_after_sha256": "sha256:" + "d" * 64,
        }
        proof = {
            "schema_version": 2,
            "before_snapshot": {
                ".codex/hooks.json": "ZXh0ZXJuYWwgYmVmb3JlCg==",
            },
            "before_snapshot_fingerprint": "sha256:" + "1" * 64,
            "transition_fingerprint": "sha256:" + "e" * 64,
            "selection_fingerprint": "sha256:" + "f" * 64,
            "items": [canonical_item],
        }

        def checkpoint(stage: str) -> None:
            if stage == "before-apply":
                external.write_bytes(b"external drifted\n")

        release = mock.Mock()
        release.decode_explicit_adaptation_before_snapshot.return_value = {
            ".codex/hooks.json": b"external before\n",
        }
        release.freeze_explicit_adaptation_before_snapshot.return_value = {
            ".codex/hooks.json": b"external drifted\n",
        }
        contract = {
            "stamp": ".codex/.bridgeforge_codex_version",
            "contract_target": ".codex/managed-skeleton.json",
            "assets": [],
        }
        with mock.patch.object(
            sync,
            "_select_explicit_adaptations",
            return_value=(selected, [], []),
        ), mock.patch.object(
            sync,
            "_build_adaptation_proof",
            return_value=proof,
        ), mock.patch.object(
            sync,
            "_trusted_release_module",
            return_value=release,
        ), mock.patch.object(
            sync,
            "_assert_adaptation_receipt_ignored",
        ), mock.patch.object(
            sync,
            "_run_release_preflight",
            return_value=("passed", "skeleton-only", 0.0),
        ), mock.patch.object(
            sync,
            "load_contract",
            return_value=(contract, ROOT / "templates/managed-skeleton.json"),
        ):
            with self.assertRaisesRegex(
                sync.SyncBlocked,
                "current-before snapshot drifted before apply",
            ):
                sync._apply_rebuilt_plan(
                    plan,
                    plan,
                    plan_fingerprint=plan.aggregate_fingerprint,
                    selected_adaptation_ids=("G1",),
                    checkpoint=checkpoint,
                    replan_ms=0.0,
                    apply_started=0.0,
                )

        self.assertEqual(managed.read_bytes(), b"managed before\n")
        self.assertEqual(external.read_bytes(), b"external drifted\n")
        self.assertEqual(stamp.read_text(encoding="utf-8"), "1.4.22\n")
        self.assertFalse((project / sync.ADAPTATION_RECEIPT).exists())

    def test_apply_rechecks_prospective_preflight_before_any_write(self) -> None:
        project = self.make_project()
        plan = sync.build_plan(project, ROOT, "init")
        items = sync._release_preflight_items(RuntimeError("managed projection drifted"))

        with mock.patch.object(
            sync,
            "_run_release_preflight",
            side_effect=sync.ReleasePreflightBlocked("preflight rejected", items),
        ):
            with self.assertRaises(sync.ReleasePreflightBlocked) as captured:
                sync.apply_plan(
                    plan,
                    plan_fingerprint=plan.aggregate_fingerprint,
                )

        self.assertIn("zero writes performed", str(captured.exception))
        self.assertEqual(captured.exception.items[0]["id"], "G1")
        self.assertEqual(
            captured.exception.items[0]["category"],
            "release_transition_review",
        )
        self.assertEqual(
            captured.exception.items[0]["recoverability"],
            "zero writes were performed",
        )
        self.assertFalse((project / ".codex/.bridgeforge_codex_version").exists())
        self.assertFalse((project / ".codex/managed-skeleton.json").exists())

    def test_same_version_managed_retirement_is_preflighted_before_any_write(self) -> None:
        project = self.make_project()
        self.prepare_project_runtime(project)
        self.init_git_project(project)
        plan = sync.build_plan(project, ROOT, "init")
        sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        subprocess.run(["git", "add", "."], cwd=project, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=BridgeForge Test",
                "-c",
                "user.email=bridgeforge@example.invalid",
                "commit",
                "-m",
                "chore: current skeleton",
            ],
            cwd=project,
            check=True,
            capture_output=True,
        )
        target = project / ".codex/hooks/target_cleanup.py"
        target.write_bytes(
            git_blob(
                "5a6c5564e3d828358c850113b856bcd4f74e15e0",
                "templates/hooks/target_cleanup.py",
            )
        )
        subprocess.run(["git", "add", "."], cwd=project, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=BridgeForge Test",
                "-c",
                "user.email=bridgeforge@example.invalid",
                "commit",
                "-m",
                "chore: legacy managed hook",
            ],
            cwd=project,
            check=True,
            capture_output=True,
        )

        repair = sync.build_plan(project, ROOT, "update")
        checkpoints: list[str] = []
        with self.assertRaises(sync.ReleasePreflightBlocked) as captured:
            sync.apply_plan(
                repair,
                plan_fingerprint=repair.aggregate_fingerprint,
                confirmed_risk=True,
                checkpoint=checkpoints.append,
            )

        self.assertTrue(target.is_file())
        self.assertEqual(checkpoints, [])
        self.assertEqual(
            captured.exception.items[0]["recoverability"],
            "zero writes were performed",
        )
        self.assertEqual(
            captured.exception.items[0]["asset_id"],
            "codex.hook.target-cleanup",
        )
        self.assertIn(
            "missing updated skeleton stamp",
            captured.exception.items[0]["classification_reason"],
        )

    def test_trusted_release_loader_does_not_write_bytecode(self) -> None:
        template_root = self.make_project()
        script = template_root / "templates/scripts/version_release.py"
        script.parent.mkdir(parents=True)
        script.write_text("VALUE = 1\n", encoding="utf-8")
        previous = sys.dont_write_bytecode

        module = sync._trusted_release_module(template_root)

        self.assertEqual(module.VALUE, 1)
        self.assertEqual(sys.dont_write_bytecode, previous)
        self.assertFalse((script.parent / "__pycache__").exists())

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
        self.prepare_project_runtime(project)
        displayed = sync.build_plan(project, ROOT, "init")
        output = io.StringIO()
        runtime_contract = mock.Mock()
        runtime_contract.ProjectRuntimeError = RuntimeError
        runtime_contract.expected_project_python.return_value = (
            project / ".venv" / "Scripts" / "python.exe"
        )

        with mock.patch.object(
            sync,
            "_trusted_project_runtime_module",
            return_value=runtime_contract,
        ), mock.patch.object(sync, "build_plan", wraps=sync.build_plan) as build:
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
        self.prepare_project_runtime(project)
        output = io.StringIO()
        runtime_contract = mock.Mock()
        runtime_contract.ProjectRuntimeError = RuntimeError
        with mock.patch.object(
            sync,
            "_trusted_project_runtime_module",
            return_value=runtime_contract,
        ), redirect_stdout(output):
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
