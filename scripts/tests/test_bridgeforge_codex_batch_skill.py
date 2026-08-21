from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / ".codex/skills/bridgeforge-codex-batch/SKILL.md"
SCRIPT = ROOT / ".codex/skills/bridgeforge-codex-batch/scripts/batch_control.py"

SPEC = importlib.util.spec_from_file_location("batch_control", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
BATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BATCH)


class BridgeForgeCodexBatchSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        patcher = mock.patch.object(
            BATCH,
            "_validate_factory_baseline",
            return_value=self.baseline_receipt(),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def git(self, root: Path, *arguments: str) -> str:
        result = subprocess.run(
            ["git", *arguments],
            cwd=root,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def make_repo(self, name: str) -> Path:
        root = self.base / name
        root.mkdir()
        self.git(root, "init", "-b", "main")
        self.git(root, "config", "user.name", "BridgeForge Test")
        self.git(root, "config", "user.email", "bridgeforge@example.invalid")
        return root

    def commit_all(self, root: Path, message: str = "fixture") -> str:
        self.git(root, "add", ".")
        self.git(root, "commit", "-m", message)
        return self.git(root, "rev-parse", "HEAD")

    def make_factory(self) -> Path:
        root = self.make_repo("factory")
        (root / ".gitignore").write_text(".runtime/\n", encoding="utf-8")
        for relative in BATCH.FACTORY_WITNESSES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n", encoding="utf-8")
        python = root / ".venv/Scripts/python.exe"
        python.parent.mkdir(parents=True)
        python.write_text("fixture\n", encoding="utf-8")
        head = self.commit_all(root)
        self.git(root, "remote", "add", "origin", BATCH.CANONICAL_REMOTE)
        self.git(root, "update-ref", "refs/remotes/origin/main", head)
        self.git(root, "branch", "--set-upstream-to=origin/main", "main")
        return root

    def make_target(self, name: str = "downstream") -> Path:
        root = self.make_repo(name)
        for relative in BATCH.TARGET_WITNESSES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            value = "1.4.37\n" if path.name == ".bridgeforge_codex_version" else "fixture\n"
            path.write_text(value, encoding="utf-8")
        head = self.commit_all(root)
        self.git(root, "remote", "add", "origin", f"https://example.invalid/{name}.git")
        self.git(root, "update-ref", "refs/remotes/origin/main", head)
        self.git(root, "branch", "--set-upstream-to=origin/main", "main")
        return root

    def baseline_receipt(self) -> dict[str, str]:
        return {
            "status": "passed",
            "version": "1.4.40",
            "fingerprint": "sha256:" + "1" * 64,
        }

    def start(self, targets: list[Path], batch_id: str = "batch-test-001") -> Path:
        factory = self.base / "factory"
        if not factory.exists():
            factory = self.make_factory()
        with mock.patch.object(
            BATCH,
            "_validate_factory_baseline",
            return_value=self.baseline_receipt(),
        ):
            plan = BATCH.create_plan(factory, targets)
            return BATCH.start_batch(
                factory,
                targets,
                plan["plan_fingerprint"],
                batch_id,
            )

    def load(self, state: Path) -> dict[str, object]:
        return json.loads(state.read_text(encoding="utf-8"))

    def defer(self, state: Path, target: Path, signature: str) -> None:
        with mock.patch.object(
            BATCH,
            "_validate_factory_baseline",
            return_value=self.baseline_receipt(),
        ):
            BATCH.begin_target(state, str(target))
        BATCH.finish_target(
            state,
            str(target),
            outcome="deferred",
            problem_summary="当前分支需要用户决定。",
            problem_signature=signature,
        )

    def test_skill_and_cli_use_only_verified_commands(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        for marker in (
            " plan --factory-root .",
            "--plan-fingerprint <confirmed-fingerprint>",
            "finish ... --outcome succeeded",
            "refresh-plan",
            "reconfirm --plan-fingerprint",
            "link-common --bug-doc",
            "restart",
            "close --state <state>",
            "禁止由调用者传入版本或保存结果",
        ):
            self.assertIn(marker, text)
        self.assertNotIn("targets-check", text)
        self.assertNotIn("--github-saved", text)
        self.assertNotIn("--version <version>", text)
        parser = BATCH._parser()
        choices = next(
            action.choices
            for action in parser._actions
            if isinstance(action, BATCH.argparse._SubParsersAction)
        )
        self.assertEqual(
            set(choices),
            {
                "factory-check",
                "plan",
                "start",
                "begin",
                "finish",
                "confirm-common",
                "link-common",
                "refresh-plan",
                "reconfirm",
                "restart",
                "close",
                "summary",
            },
        )

    def test_plan_and_begin_reject_target_or_factory_drift(self) -> None:
        factory = self.make_factory()
        target = self.make_target()
        with mock.patch.object(
            BATCH,
            "_validate_factory_baseline",
            return_value=self.baseline_receipt(),
        ):
            plan = BATCH.create_plan(factory, [target])
        (target / "drift.txt").write_text("drift\n", encoding="utf-8")
        with mock.patch.object(
            BATCH,
            "_validate_factory_baseline",
            return_value=self.baseline_receipt(),
        ):
            with self.assertRaisesRegex(BATCH.BatchError, "重新展示计划"):
                BATCH.start_batch(
                    factory,
                    [target],
                    plan["plan_fingerprint"],
                    "batch-drift-001",
                )
        (target / "drift.txt").unlink()
        state = self.start([target], "batch-drift-002")
        (target / "drift.txt").write_text("drift\n", encoding="utf-8")
        with mock.patch.object(
            BATCH,
            "_validate_factory_baseline",
            return_value=self.baseline_receipt(),
        ):
            with self.assertRaisesRegex(BATCH.BatchError, "状态已变化"):
                BATCH.begin_target(state, str(target))
        (target / "drift.txt").unlink()
        changed = {**self.baseline_receipt(), "fingerprint": "sha256:" + "2" * 64}
        with mock.patch.object(BATCH, "_validate_factory_baseline", return_value=changed):
            with self.assertRaisesRegex(BATCH.BatchError, "变化.*禁止继续"):
                BATCH.begin_target(state, str(target))

    def test_success_is_derived_from_baseline_version_and_git(self) -> None:
        target = self.make_target()
        state = self.start([target])
        with mock.patch.object(
            BATCH,
            "_validate_factory_baseline",
            return_value=self.baseline_receipt(),
        ):
            BATCH.begin_target(state, str(target))
        receipt = {
            "status": "passed",
            "version": "1.4.37",
            "fingerprint": "sha256:" + "3" * 64,
        }
        with mock.patch.object(BATCH, "_validate_target_baseline", return_value=receipt):
            (target / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            with self.assertRaisesRegex(BATCH.BatchError, "尚未保存"):
                BATCH.finish_target(state, str(target), outcome="succeeded")
            (target / "dirty.txt").unlink()
            bad = {**receipt, "version": "1.4.36"}
            with mock.patch.object(BATCH, "_validate_target_baseline", return_value=bad):
                with self.assertRaisesRegex(BATCH.BatchError, "版本不一致"):
                    BATCH.finish_target(state, str(target), outcome="succeeded")
            BATCH.finish_target(state, str(target), outcome="succeeded")
        result = self.load(state)["targets"][0]["result"]
        self.assertEqual(result["version"], "1.4.37")
        self.assertTrue(result["github_saved"])

    def test_global_active_lock_and_input_order(self) -> None:
        first = self.make_target("one")
        second = self.make_target("two")
        state = self.start([first, second], "batch-active-001")
        factory = Path(self.load(state)["factory_root"])
        with mock.patch.object(
            BATCH,
            "_validate_factory_baseline",
            return_value=self.baseline_receipt(),
        ):
            plan = BATCH.create_plan(factory, [second])
            with self.assertRaisesRegex(BATCH.BatchError, "已有未结束"):
                BATCH.start_batch(
                    factory,
                    [second],
                    plan["plan_fingerprint"],
                    "batch-active-002",
                )
            with self.assertRaisesRegex(BATCH.BatchError, "顺序"):
                BATCH.begin_target(state, str(second))
        lock = state.with_suffix(".lock")
        lock.write_text("held\n", encoding="utf-8")
        with self.assertRaisesRegex(BATCH.BatchError, "另一个批次操作"):
            BATCH.begin_target(state, str(first))
        lock.unlink()
        with mock.patch.object(
            BATCH,
            "_validate_factory_baseline",
            return_value=self.baseline_receipt(),
        ):
            BATCH.begin_target(state, str(first))
        with self.assertRaisesRegex(BATCH.BatchError, "禁止并行"):
            BATCH.begin_target(state, str(second))

    def test_pending_targets_precede_deferred_refresh_and_reconfirm(self) -> None:
        first = self.make_target("one")
        second = self.make_target("two")
        state = self.start([first, second])
        self.defer(state, first, "git:first:blocked")
        with self.assertRaisesRegex(BATCH.BatchError, "首次计划"):
            BATCH.refresh_plan(state, str(first))
        self.defer(state, second, "git:second:blocked")
        (first / "manual.txt").write_text("resolved\n", encoding="utf-8")
        with mock.patch.object(
            BATCH,
            "_validate_factory_baseline",
            return_value=self.baseline_receipt(),
        ):
            with self.assertRaisesRegex(BATCH.BatchError, "重新展示异常计划"):
                BATCH.begin_target(state, str(first))
            proposal = BATCH.refresh_plan(state, str(first))
            with self.assertRaisesRegex(BATCH.BatchError, "再次变化"):
                BATCH.reconfirm_target(
                    state,
                    str(first),
                    "sha256:" + "0" * 64,
                )
            BATCH.reconfirm_target(
                state,
                str(first),
                proposal["plan_fingerprint"],
            )
            BATCH.begin_target(state, str(first))

    def test_only_bridgeforge_signatures_trigger_common_stop(self) -> None:
        first = self.make_target("one")
        second = self.make_target("two")
        git_state = self.start([first, second], "batch-common-001")
        self.defer(git_state, first, "git:network:timeout")
        self.defer(git_state, second, "git:network:timeout")
        self.assertEqual(self.load(git_state)["phase"], "running")

        third = self.make_target("three")
        fourth = self.make_target("four")
        factory = Path(self.load(git_state)["factory_root"])
        active = factory / ".runtime/bridgeforge-codex-batch/active.json"
        active.unlink()
        bridge_state = self.start([third, fourth], "batch-common-002")
        self.defer(bridge_state, third, "bridgeforge:update:asset-drift")
        self.defer(bridge_state, fourth, "bridgeforge:update:asset-drift")
        self.assertEqual(self.load(bridge_state)["phase"], "common_pending_bug")

    def test_common_requires_bug_doc_and_restart_new_factory(self) -> None:
        first = self.make_target("one")
        second = self.make_target("two")
        state = self.start([first, second])
        self.defer(state, first, "bridgeforge:update:asset-drift")
        self.defer(state, second, "bridgeforge:update:asset-drift")
        factory = Path(self.load(state)["factory_root"])
        with self.assertRaisesRegex(BATCH.BatchError, "不存在"):
            BATCH.link_common_problem(state, "doc/2_bugs/BUG-missing.md")
        bug = factory / "doc/2_bugs/BUG-batch.md"
        bug.parent.mkdir(parents=True)
        bug.write_text("# Bug\n", encoding="utf-8")
        BATCH.link_common_problem(state, "doc/2_bugs/BUG-batch.md")
        blocked = self.load(state)
        same = {
            **blocked["factory_snapshot"],
            "fingerprint": "sha256:" + "9" * 64,
        }
        with mock.patch.object(BATCH, "inspect_factory", return_value=same):
            with self.assertRaisesRegex(BATCH.BatchError, "源码和骨架"):
                BATCH.restart_batch(state)
        new = {**same, "head": "f" * 40}
        with mock.patch.object(BATCH, "inspect_factory", return_value=new):
            with self.assertRaisesRegex(BATCH.BatchError, "Bug 文档"):
                BATCH.restart_batch(state)

        (factory / "templates/fix.txt").write_text("fixed\n", encoding="utf-8")
        new_head = self.commit_all(factory, "fix")
        self.git(factory, "update-ref", "refs/remotes/origin/main", new_head)
        fixed = {
            **blocked["factory_snapshot"],
            "head": new_head,
            "origin_main": new_head,
            "fingerprint": "sha256:" + "8" * 64,
        }
        with mock.patch.object(BATCH, "inspect_factory", return_value=fixed):
            BATCH.restart_batch(state)
        restarted = self.load(state)
        self.assertEqual(restarted["generation"], 2)
        self.assertTrue(all(item["status"] == "pending" for item in restarted["targets"]))
        self.assertTrue(all(item["result"] is None for item in restarted["targets"]))

    def test_explicit_common_rejects_non_bridgeforge_namespace(self) -> None:
        target = self.make_target()
        state = self.start([target])
        factory = Path(self.load(state)["factory_root"])
        bug = factory / "doc/2_bugs/BUG-explicit.md"
        bug.parent.mkdir(parents=True)
        bug.write_text("# Bug\n", encoding="utf-8")
        with self.assertRaisesRegex(BATCH.BatchError, "bridgeforge 命名空间"):
            BATCH.confirm_common_problem(
                state,
                "git:network:timeout",
                str(target),
                "doc/2_bugs/BUG-explicit.md",
            )

    def test_state_schema_path_and_summary_are_hardened(self) -> None:
        target = self.make_target()
        state = self.start([target])
        with mock.patch.object(
            BATCH,
            "_validate_factory_baseline",
            return_value=self.baseline_receipt(),
        ):
            BATCH.begin_target(state, str(target))
        for unsafe in (
            "Traceback: failed",
            r"请查看 D:\secret\trace.txt",
            "查看 doc/secret.md",
            "problem_signature=git:x",
        ):
            with self.subTest(unsafe=unsafe):
                with self.assertRaisesRegex(BATCH.BatchError, "单行白话"):
                    BATCH.finish_target(
                        state,
                        str(target),
                        outcome="deferred",
                        problem_summary=unsafe,
                    )
        malformed = self.load(state)
        malformed["unexpected"] = True
        state.write_text(json.dumps(malformed), encoding="utf-8")
        with self.assertRaisesRegex(BATCH.BatchError, "结构无效"):
            BATCH.summary_text(state)

    def test_state_symlink_is_rejected_when_supported(self) -> None:
        target = self.make_target()
        state = self.start([target])
        alias = state.with_name("batch-alias-001.json")
        try:
            os.symlink(state, alias)
        except OSError as exc:
            self.skipTest(f"symlink unavailable: {exc}")
        with self.assertRaisesRegex(BATCH.BatchError, "符号链接"):
            BATCH.summary_text(alias)

    def test_duplicate_names_are_disambiguated_without_paths(self) -> None:
        first = self.make_target("project-one")
        second = self.make_target("project-two")
        first.rename(self.base / "project")
        first = self.base / "project"
        # A linked worktree has the same basename and a distinct branch.
        linked_parent = self.base / "linked"
        linked_parent.mkdir()
        linked = linked_parent / "project"
        self.git(first, "branch", "feature")
        self.git(first, "worktree", "add", str(linked), "feature")
        state = self.start([first, linked])
        summary = BATCH.summary_text(state)
        self.assertIn("project（main）", summary)
        self.assertIn("project（feature）", summary)
        self.assertNotIn(str(first), summary)
        self.assertNotIn("common_git_dir", summary)

    def test_completed_close_releases_active_and_deletes_state(self) -> None:
        target = self.make_target()
        state = self.start([target])
        with mock.patch.object(
            BATCH,
            "_validate_factory_baseline",
            return_value=self.baseline_receipt(),
        ):
            BATCH.begin_target(state, str(target))
        receipt = {
            "status": "passed",
            "version": "1.4.37",
            "fingerprint": "sha256:" + "3" * 64,
        }
        with mock.patch.object(BATCH, "_validate_target_baseline", return_value=receipt):
            BATCH.finish_target(state, str(target), outcome="succeeded")
        factory = Path(self.load(state)["factory_root"])
        self.assertFalse(
            (factory / ".runtime/bridgeforge-codex-batch/active.json").exists()
        )
        self.assertIn("本批次已完成", BATCH.summary_text(state))
        BATCH.close_batch(state)
        self.assertFalse(state.exists())


if __name__ == "__main__":
    unittest.main()
