from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
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


SCRIPT_DIR = ROOT / "templates" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
RELEASE = load_module("bridgeforge_current_release", SCRIPT_DIR / "version_release.py")
CURRENT = sys.modules["current_baseline"]
SYNC = load_module(
    "bridgeforge_release_project_sync",
    ROOT / "scripts" / "bridgeforge_codex_project_sync.py",
)


def commit_baseline(project: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True)
    subprocess.run(
        [
            "git", "-c", "user.name=BridgeForge Test",
            "-c", "user.email=test@example.invalid",
            "commit", "-qm", "baseline",
        ],
        cwd=project,
        check=True,
    )


class CurrentReleaseTests(unittest.TestCase):
    def test_current_contract_meets_size_and_no_growth_gates(self) -> None:
        contract_path = ROOT / "templates" / "managed-skeleton.json"
        original = contract_path.read_text(encoding="utf-8")
        contract = json.loads(original)
        self.assertLessEqual(len(original.splitlines()), int(7163 * 0.30))

        sync_lines = len(
            (ROOT / "scripts" / "bridgeforge_codex_project_sync.py")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        release_lines = len(
            (ROOT / "templates" / "scripts" / "version_release.py")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        self.assertLessEqual(sync_lines + release_lines, int(9216 * 0.75))

        baseline_lines = len(
            (json.dumps(contract, ensure_ascii=False, indent=2) + "\n").splitlines()
        )
        asset_keys = [set(asset) for asset in contract["assets"]]
        for version in ("1.4.29", "1.4.30"):
            contract["release_version"] = version
            rendered = json.dumps(contract, ensure_ascii=False, indent=2) + "\n"
            self.assertEqual(len(rendered.splitlines()), baseline_lines)
            self.assertEqual([set(asset) for asset in contract["assets"]], asset_keys)

    def test_current_contract_rejects_noncanonical_windows_target(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "managed-skeleton.json"
            contract = json.loads(
                (ROOT / "templates" / "managed-skeleton.json").read_text(encoding="utf-8")
            )
            asset = next(item for item in contract["assets"] if "/" in item["target"])
            asset["target"] = str(asset["target"]).replace("/", "\\")
            path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaisesRegex(CURRENT.BaselineError, "POSIX relative path"):
                CURRENT.load_contract(path)

    def test_downstream_precommit_uses_template_current_baseline(self) -> None:
        contract = json.loads(
            (ROOT / "templates" / "managed-skeleton.json").read_text(
                encoding="utf-8"
            )
        )
        precommit = next(
            asset for asset in contract["assets"] if asset["id"] == "codex.precommit"
        )
        self.assertEqual(precommit["source"], "templates/.githooks/pre-commit")
        template = (ROOT / precommit["source"]).read_text(encoding="utf-8")
        self.assertIn(".codex/scripts/current_baseline.py", template)
        self.assertIn("--index", template)
        self.assertIn('memory_rebuild_index.py" --check', template)
        self.assertNotIn("git add", template)
        self.assertIn('[ "$rc" = 2 ] && exit 2\n    return 0', template)
        self.assertNotIn("factory_version_check.py", template)

    def test_index_verification_cannot_be_bypassed_by_worktree_restore(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            plan = SYNC.build_plan(project, ROOT, "init")
            SYNC.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
            subprocess.run(["git", "init", "-q"], cwd=project, check=True)
            subprocess.run(["git", "add", "-A"], cwd=project, check=True)

            target = project / ".codex" / "hooks" / "requirements_check.py"
            canonical = target.read_bytes()
            target.write_text("# staged drift\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", ".codex/hooks/requirements_check.py"],
                cwd=project,
                check=True,
            )
            target.write_bytes(canonical)

            CURRENT.verify_current_baseline(project)
            with self.assertRaisesRegex(CURRENT.BaselineError, "drifted"):
                CURRENT.verify_index_baseline(project)

    def test_head_anchor_rejects_same_version_contract_self_proof(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            plan = SYNC.build_plan(project, ROOT, "init")
            SYNC.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
            subprocess.run(["git", "init", "-q"], cwd=project, check=True)
            subprocess.run(["git", "add", "-A"], cwd=project, check=True)
            subprocess.run(
                [
                    "git", "-c", "user.name=BridgeForge Test",
                    "-c", "user.email=test@example.invalid",
                    "commit", "-qm", "baseline",
                ],
                cwd=project,
                check=True,
            )

            target = project / ".codex" / "hooks" / "requirements_check.py"
            target.write_text("# coordinated drift\n", encoding="utf-8")
            contract_path = project / ".codex" / "managed-skeleton.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            asset = next(
                item
                for item in contract["assets"]
                if item["target"] == ".codex/hooks/requirements_check.py"
            )
            asset["current_sha256"] = CURRENT._normalized_render_hash(
                target.read_bytes(),
                asset,
                project,
            )
            contract_path.write_text(
                json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(CURRENT.BaselineError, "trusted HEAD"):
                CURRENT.verify_current_baseline(project)

    def test_factory_uses_the_current_baseline_evaluator(self) -> None:
        current = (ROOT / "VERSION").read_text(encoding="utf-8-sig").strip()
        classification, changed = RELEASE.evaluate_release_transition(
            ROOT,
            changed_paths={"templates/AGENTS.md", "doc/README.md"},
            prospective_version=RELEASE.bump_semver(current, "patch"),
        )
        self.assertEqual(classification, "factory")
        self.assertEqual(changed, {"templates/AGENTS.md", "doc/README.md"})

    def test_downstream_classification_uses_project_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            plan = SYNC.build_plan(project, ROOT, "init")
            SYNC.apply_plan(
                plan,
                plan_fingerprint=plan.aggregate_fingerprint,
            )
            commit_baseline(project)
            agents = project / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8").replace(
                    "<!-- BRIDGEFORGE:PROJECT:BEGIN -->",
                    "<!-- BRIDGEFORGE:PROJECT:BEGIN -->\nproject-business-rule",
                    1,
                ),
                encoding="utf-8",
            )
            project_only = RELEASE.evaluate_release_transition(
                project,
                changed_paths={"AGENTS.md"},
            )[0]
            project_with_source = RELEASE.evaluate_release_transition(
                project,
                changed_paths={"AGENTS.md", "src/strategy.py"},
            )[0]
        self.assertEqual(project_only, "project-only")
        self.assertEqual(project_with_source, "project-only")

    def test_hook_event_and_matcher_are_part_of_current_identity(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            plan = SYNC.build_plan(project, ROOT, "init")
            SYNC.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
            hooks_path = project / ".codex" / "hooks.json"
            canonical = hooks_path.read_text(encoding="utf-8")
            hooks = json.loads(canonical)
            found = None
            for event, entries in hooks["hooks"].items():
                for entry in entries:
                    for handler in entry["hooks"]:
                        if str(handler.get("bridgeforgeCodexId", "")).startswith(
                            "bridgeforge-codex.project-hook.v1:"
                        ):
                            found = (event, entry, handler)
                            break
                    if found:
                        break
                if found:
                    break
            assert found is not None
            event, entry, handler = found
            entry["hooks"].remove(handler)
            hooks["hooks"].setdefault("__WrongEvent__", []).append(
                {"matcher": entry.get("matcher", ""), "hooks": [handler]}
            )
            hooks_path.write_text(json.dumps(hooks), encoding="utf-8")
            with self.assertRaisesRegex(CURRENT.BaselineError, "event drifted"):
                CURRENT.verify_current_baseline(project)

            hooks = json.loads(canonical)
            for entries in hooks["hooks"].values():
                for candidate in entries:
                    if any(
                        str(item.get("bridgeforgeCodexId", "")).startswith(
                            "bridgeforge-codex.project-hook.v1:"
                        )
                        for item in candidate["hooks"]
                    ):
                        candidate["matcher"] = "__WrongMatcher__"
                        hooks_path.write_text(json.dumps(hooks), encoding="utf-8")
                        with self.assertRaisesRegex(
                            CURRENT.BaselineError,
                            "matcher drifted",
                        ):
                            CURRENT.verify_current_baseline(project)
                        return
            self.fail("managed hook not found")

    def test_partial_factory_witness_cannot_replace_downstream_stamp(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            plan = SYNC.build_plan(project, ROOT, "init")
            SYNC.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
            (project / ".codex" / ".bridgeforge_codex_version").unlink()
            templates = project / "templates"
            templates.mkdir()
            (templates / "managed-skeleton.json").write_bytes(
                (project / ".codex" / "managed-skeleton.json").read_bytes()
            )
            (project / "VERSION").write_text(
                (ROOT / "VERSION").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(CURRENT.BaselineError, "ambiguous"):
                CURRENT.verify_current_baseline(project)

    def test_empty_skill_manifest_cannot_claim_factory_identity(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            for relative in CURRENT.FACTORY_WITNESSES:
                source = ROOT / relative
                target = project / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            validator = project / "scripts" / "rebuild_shared_skill_manifest.py"
            validator.write_text(
                "def validate_manifest_path(*args, **kwargs):\n    return {}\n",
                encoding="utf-8",
            )
            manifest = {
                "schema_version": 1,
                "canonical_remote": CURRENT.FACTORY_MANIFEST_REMOTE,
                "branch": "main",
                "platforms": {
                    "codex": {
                        "target": "~/.codex/skills",
                        "skills": [],
                    },
                },
            }
            (project / CURRENT.FACTORY_MANIFEST).write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )

            role = CURRENT.detect_repository_role(project)

            self.assertEqual(role.kind, "ambiguous")
            self.assertIn("bridgeforge-codex", role.reason)

    def test_missing_or_drifted_downstream_baseline_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            with self.assertRaises(RELEASE.TransitionBlocked):
                RELEASE.evaluate_release_transition(
                    project,
                    changed_paths={"src/strategy.py"},
                )

            plan = SYNC.build_plan(project, ROOT, "init")
            SYNC.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
            target = project / ".codex" / "hooks" / "requirements_check.py"
            target.write_text("# drift\n", encoding="utf-8")
            with self.assertRaises(RELEASE.TransitionBlocked):
                RELEASE.evaluate_release_transition(
                    project,
                    changed_paths={"src/strategy.py"},
                )

    def test_skeleton_only_release_does_not_bump_business_version(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            sync_plan = SYNC.build_plan(project, ROOT, "init")
            SYNC.apply_plan(
                sync_plan,
                plan_fingerprint=sync_plan.aggregate_fingerprint,
            )
            commit_baseline(project)
            target = project / ".codex" / "hooks" / "requirements_check.py"
            target.write_text("# forward public release\n", encoding="utf-8")
            contract_path = project / ".codex" / "managed-skeleton.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            major, minor, patch = map(int, contract["release_version"].split("."))
            forward = f"{major}.{minor}.{patch + 1}"
            contract["release_version"] = forward
            asset = next(
                item
                for item in contract["assets"]
                if item["target"] == ".codex/hooks/requirements_check.py"
            )
            asset["current_sha256"] = CURRENT._normalized_render_hash(
                target.read_bytes(),
                asset,
                project,
            )
            contract_path.write_text(
                json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (project / ".codex" / ".bridgeforge_codex_version").write_text(
                forward + "\n",
                encoding="utf-8",
            )
            release_plan = RELEASE.build_release_plan(
                project,
                "chore: 同步当前骨架",
                {".codex/hooks/requirements_check.py"},
            )
            self.assertIsNone(release_plan)

    def test_semver_and_commit_parsing_remain_current_features(self) -> None:
        info = RELEASE.parse_commit_message(
            "feat!: 更新交易网关\n\nBREAKING CHANGE: 接口变更"
        )
        self.assertTrue(info.breaking)
        self.assertEqual(info.level, "major")
        self.assertEqual(RELEASE.bump_semver("1.4.28", "patch"), "1.4.29")
        with self.assertRaises(RELEASE.ReleaseError):
            RELEASE.parse_commit_message("随意提交")

    def test_release_json_renderers_wrap_duplicate_keys_as_release_errors(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest = root / "package.json"
            manifest.write_text('{"version":"1.2.3","version":"1.2.3"}\n', encoding="utf-8")
            lock = root / "package-lock.json"
            lock.write_text('{"lockfileVersion":3,"lockfileVersion":3}\n', encoding="utf-8")
            for action in (
                lambda: RELEASE._render_json_version(manifest, "1.2.4"),
                lambda: RELEASE._render_package_lock(lock, "1.2.3", "1.2.4"),
            ):
                with self.subTest(action=action), self.assertRaisesRegex(
                    RELEASE.ReleaseError, "duplicate key"
                ):
                    action()

    def test_native_manifest_and_lock_versions_remain_synchronized(self) -> None:
        cases = {
            "node": {
                "package.json": '{"name": "demo", "version": "1.2.3"}\n',
                "package-lock.json": json.dumps(
                    {
                        "name": "demo",
                        "version": "1.2.3",
                        "lockfileVersion": 3,
                        "packages": {"": {"name": "demo", "version": "1.2.3"}},
                    }
                ),
            },
            "cargo": {
                "Cargo.toml": '[package]\nname = "demo"\nversion = "1.2.3"\n',
                "Cargo.lock": '[[package]]\nname = "demo"\nversion = "1.2.3"\n',
            },
            "python": {
                "pyproject.toml": '[project]\nname = "demo"\nversion = "1.2.3"\n',
            },
        }
        for label, files in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as raw:
                project = Path(raw)
                sync_plan = SYNC.build_plan(project, ROOT, "init")
                SYNC.apply_plan(
                    sync_plan,
                    plan_fingerprint=sync_plan.aggregate_fingerprint,
                )
                (project / "VERSION").write_text("1.2.3\n", encoding="utf-8")
                for relative, content in files.items():
                    (project / relative).write_text(content, encoding="utf-8")
                plan = RELEASE.build_release_plan(
                    project,
                    "fix: 同步原生版本",
                    {next(iter(files))},
                )
                self.assertIsNotNone(plan)
                assert plan is not None
                self.assertEqual(plan.new_version, "1.2.4")
                self.assertEqual(plan.writes[project / "VERSION"], b"1.2.4\n")
                for relative in files:
                    if relative.endswith((".json", ".toml", ".lock")):
                        self.assertIn(b"1.2.4", plan.writes[project / relative])

    def test_release_plan_has_no_compatibility_wrappers_or_before_package(self) -> None:
        self.assertFalse(hasattr(RELEASE, "classify_changes"))
        self.assertFalse(hasattr(RELEASE, "preflight_contract_transition"))
        plan = RELEASE.build_release_plan(
            ROOT,
            "refactor: 建立 1.4.31 干净基线",
            {"scripts/bridgeforge_codex_project_sync.py"},
        )
        self.assertIsNotNone(plan)
        assert plan is not None
        current = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(plan.old_version, current)
        self.assertEqual(plan.new_version, RELEASE.bump_semver(current, "patch"))
        self.assertEqual(plan.classification, "factory")


if __name__ == "__main__":
    unittest.main()
