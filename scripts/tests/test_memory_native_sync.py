#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


search_mod = load(ROOT / "templates/scripts/memory_search.py", "memory_search")
context_mod = load(ROOT / "templates/scripts/memory_context.py", "bf_memory_context")
usage_mod = load(ROOT / "templates/scripts/memory_usage.py", "memory_usage")
router_mod = load(ROOT / "templates/scripts/memory_router.py", "memory_router")
sync_mod = load(ROOT / "scripts/codex_memory_sync.py", "bf_codex_memory_sync")


class ProjectMemoryTests(unittest.TestCase):
    def test_field_weight_beats_body_noise_and_context_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            memory = Path(raw)
            (memory / "exact.md").write_text("---\nname: Exact\ntopic: orders\nrelated_paths: [src/orders.rs]\ntags: [oms]\ndescription: route orders\ncreated_at: 2026-01-01\n---\nshort", encoding="utf-8")
            (memory / "noise.md").write_text("---\nname: Noise\ndescription: repeated body\ncreated_at: 2026-02-01\n---\n" + "orders " * 200, encoding="utf-8")
            results = search_mod.search(memory, "orders", 5)
            self.assertEqual(results[0].path, "exact.md")
            self.assertIn("topic/path", results[0].reason)
            (memory / "chinese.md").write_text(
                "---\nname: 订单路由\ntags: [订单路由]\ndescription: 订单路由规则\ncreated_at: 2026-03-01\n---\n按账户和市场路由订单",
                encoding="utf-8",
            )
            chinese = search_mod.search(memory, "帮我查一下订单路由问题", 5)
            self.assertEqual(chinese[0].path, "chinese.md")
            self.assertIn("tags", chinese[0].reason)
            (memory / "MEMORY.md").write_text("x" * 7000, encoding="utf-8")
            self.assertLessEqual(len(context_mod.build_context(memory)), 6000)

    def test_router_records_candidates_and_only_counts_successful_body_reads(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            memory = repo / ".codex" / "memory"
            memory.mkdir(parents=True)
            for index in range(3):
                (memory / f"note-{index}.md").write_text(
                    f"---\nname: Orders {index}\ndescription: order routing {index}\ncreated_at: 2026-01-0{index + 1}\n---\norders",
                    encoding="utf-8",
                )
            stats = memory / "_stats.json"
            stats.write_text('{"keep": true}\n', encoding="utf-8")
            with mock.patch.object(router_mod, "REPO_ROOT", repo), mock.patch.object(router_mod, "MEMORY_DIR", memory):
                candidates, receipt = router_mod.route({"prompt": "orders"})
                self.assertEqual(len(candidates), 3)
                self.assertIn("candidates 3; used 0", receipt)
                self.assertFalse(router_mod.record_read({"tool_name": "mcp__fs__read", "tool_input": {"path": str(memory / "note-0.md")}, "tool_response": {"isError": True}}))
                self.assertFalse(router_mod.record_read({"tool_name": "apply_patch", "tool_input": {"path": str(memory / "note-0.md")}, "tool_response": "write"}))
                self.assertTrue(router_mod.record_read({"tool_name": "Read", "tool_input": {"path": str(memory / "note-0.md")}, "tool_response": "body"}))
                self.assertTrue(router_mod.record_read({"tool_name": "mcp__fs__read_file", "tool_input": {"path": str(memory / "note-1.md")}, "tool_response": "body"}))
            events = [json.loads(line) for line in (repo / ".runtime/memory_usage.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([event["event"] for event in events], ["search", "used", "used"])
            self.assertEqual(usage_mod.used_count_since_last_search(repo), 2)
            self.assertEqual(stats.read_text(encoding="utf-8"), '{"keep": true}\n')

    def test_usage_counts_are_isolated_by_session_and_turn(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw)
            usage_mod.append_event(repo, {"event": "search", "session_id": "s", "turn_id": "a"})
            usage_mod.append_event(repo, {"event": "search", "session_id": "s", "turn_id": "b"})
            usage_mod.append_event(repo, {"event": "used", "path": "a.md", "session_id": "s", "turn_id": "a"})
            usage_mod.append_event(repo, {"event": "used", "path": "b.md", "session_id": "s", "turn_id": "b"})
            usage_mod.append_event(repo, {"event": "used", "path": "other.md", "session_id": "other", "turn_id": "a"})
            self.assertEqual(usage_mod.used_count_since_last_search(repo, session_id="s", turn_id="a"), 1)
            self.assertEqual(usage_mod.used_count_since_last_search(repo, session_id="s", turn_id="b"), 1)


class NativeMemorySyncTests(unittest.TestCase):
    def _write_ledger(self, codex: Path, consent: str | None = None) -> Path:
        codex.mkdir(parents=True, exist_ok=True)
        ledger: dict[str, object] = {
            "schema_version": 1,
            "platform": "codex",
            "records": {},
        }
        if consent is not None:
            ledger["consents"] = {"native_memories": consent}
        path = codex / "bridgeforge-codex-managed.json"
        path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
        return path

    def _create_empty_remote(
        self,
        base: Path,
        manifest_changes: dict[str, object] | None = None,
    ) -> tuple[Path, dict[str, object], str]:
        remote = base / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
        source = base / "empty-source"
        source.mkdir()
        snapshot = base / "empty-snapshot"
        manifest = sync_mod.build_snapshot(source, snapshot, 2)
        if manifest_changes:
            manifest.update(manifest_changes)
            (snapshot / "snapshot-manifest.json").write_text(
                json.dumps(manifest) + "\n",
                encoding="utf-8",
            )
        commit = sync_mod._push_snapshot(snapshot, base / "publish-state", str(remote), None)
        return remote, manifest, commit

    def test_stable_hook_python_prefers_the_venv_base_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            venv_python = root / "project/.venv/Scripts/python.exe"
            base_python = root / "Python312/python.exe"
            venv_python.parent.mkdir(parents=True)
            base_python.parent.mkdir(parents=True)
            venv_python.write_bytes(b"venv")
            base_python.write_bytes(b"base")
            with mock.patch.object(sync_mod.sys, "executable", str(venv_python)), mock.patch.object(
                sync_mod.sys,
                "_base_executable",
                str(base_python),
            ):
                self.assertEqual(sync_mod.stable_hook_python(), base_python.resolve())

    def test_stable_hook_python_rejects_a_missing_base_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            venv_python = root / "project/.venv/Scripts/python.exe"
            venv_python.parent.mkdir(parents=True)
            venv_python.write_bytes(b"venv")
            with mock.patch.object(sync_mod.sys, "executable", str(venv_python)), mock.patch.object(
                sync_mod.sys,
                "_base_executable",
                str(root / "missing/python.exe"),
            ):
                with self.assertRaisesRegex(sync_mod.SyncError, "no stable base interpreter"):
                    sync_mod.stable_hook_python()

    def test_stable_hook_python_rejects_a_base_interpreter_inside_the_venv(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            venv = root / "project/.venv"
            venv_python = venv / "Scripts/python.exe"
            base_prefix = root / "Python312"
            venv_python.parent.mkdir(parents=True)
            base_prefix.mkdir()
            venv_python.write_bytes(b"venv")
            with mock.patch.object(sync_mod.sys, "executable", str(venv_python)), mock.patch.object(
                sync_mod.sys,
                "_base_executable",
                str(venv_python),
            ), mock.patch.object(
                sync_mod.sys,
                "prefix",
                str(venv),
            ), mock.patch.object(
                sync_mod.sys,
                "base_prefix",
                str(base_prefix),
            ):
                with self.assertRaisesRegex(sync_mod.SyncError, "inside the venv"):
                    sync_mod.stable_hook_python()

    def test_status_reports_setup_hook_and_remote_runtime_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex = Path(raw) / ".codex"
            self._write_ledger(codex, "approved")
            (codex / "config.toml").write_text(
                "[features]\nmemories = true\n[memories]\ngenerate_memories = true\nuse_memories = true\n",
                encoding="utf-8",
            )
            output = io.StringIO()
            with mock.patch.dict(sync_mod.os.environ, {"CODEX_HOME": str(codex)}), contextlib.redirect_stdout(output):
                self.assertEqual(sync_mod.main(["status"]), 0)
            receipt = json.loads(output.getvalue())
            self.assertTrue(receipt["enabled"])
            self.assertFalse(receipt["hookInstalled"])
            self.assertFalse(receipt["remoteConfigured"])
            self.assertEqual(receipt["consent"], "approved")
            self.assertEqual(receipt["setupPython"], str(Path(sync_mod.sys.executable).resolve()))
            self.assertEqual(receipt["hookPython"], str(sync_mod.stable_hook_python()))

    def test_status_is_strictly_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex = Path(raw) / ".codex"
            self._write_ledger(codex, "declined")
            before = {
                path.relative_to(codex).as_posix(): path.read_bytes()
                for path in codex.rglob("*")
                if path.is_file()
            }
            with mock.patch.dict(sync_mod.os.environ, {"CODEX_HOME": str(codex)}):
                self.assertEqual(sync_mod.main(["status"]), 0)
            after = {
                path.relative_to(codex).as_posix(): path.read_bytes()
                for path in codex.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after, before)

    def test_legacy_enabled_status_keeps_null_consent_without_prompt_or_write(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex = Path(raw) / ".codex"
            self._write_ledger(codex)
            (codex / "config.toml").write_text(
                "[features]\nmemories = true\n[memories]\ngenerate_memories = true\nuse_memories = true\n",
                encoding="utf-8",
            )
            before = {path.name: path.read_bytes() for path in codex.iterdir() if path.is_file()}
            output = io.StringIO()
            with mock.patch.dict(sync_mod.os.environ, {"CODEX_HOME": str(codex)}), contextlib.redirect_stdout(output):
                self.assertEqual(sync_mod.main(["status"]), 0)
            receipt = json.loads(output.getvalue())
            self.assertTrue(receipt["enabled"])
            self.assertIsNone(receipt["consent"])
            after = {path.name: path.read_bytes() for path in codex.iterdir() if path.is_file()}
            self.assertEqual(after, before)

    def test_approved_enabled_maintain_repairs_runtime_and_reconciles(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex = Path(raw) / ".codex"
            self._write_ledger(codex, "approved")
            (codex / "config.toml").write_text(
                "[features]\nmemories = true\n[memories]\ngenerate_memories = true\nuse_memories = true\n",
                encoding="utf-8",
            )
            hook_python = Path(sync_mod.sys.executable).resolve()
            output = io.StringIO()
            with mock.patch.dict(sync_mod.os.environ, {"CODEX_HOME": str(codex)}), mock.patch.object(
                sync_mod, "stable_hook_python", return_value=hook_python
            ), mock.patch.object(
                sync_mod,
                "ensure_github_repository",
                return_value=("git@example.invalid:private/memories.git", "reused"),
            ) as github, mock.patch.object(sync_mod, "merge_user_hooks") as hooks, mock.patch.object(
                sync_mod, "reconcile", return_value="noop"
            ) as reconcile, contextlib.redirect_stdout(output):
                self.assertEqual(sync_mod.main(["maintain"]), 0)
            github.assert_called_once_with(confirmed_public_to_private=False)
            hooks.assert_called_once_with(
                codex / "hooks.json",
                Path(sync_mod.__file__).resolve(),
                hook_python=hook_python,
            )
            reconcile.assert_called_once_with(
                codex / "memories",
                codex / ".bridgeforge-codex" / "memory-sync",
                "git@example.invalid:private/memories.git",
            )
            self.assertEqual(
                (codex / ".bridgeforge-codex" / "memory-sync" / "remote.txt").read_text(encoding="utf-8"),
                "git@example.invalid:private/memories.git\n",
            )
            self.assertIn("reconcile=noop", output.getvalue())

    def test_maintain_migrates_legacy_state_and_hook_markers(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex = Path(raw) / ".codex"
            self._write_ledger(codex, "approved")
            (codex / "config.toml").write_text(
                "[features]\nmemories = true\n[memories]\ngenerate_memories = true\nuse_memories = true\n",
                encoding="utf-8",
            )
            legacy_state = codex / ".bridgeforge" / "memory-sync"
            legacy_state.mkdir(parents=True)
            (legacy_state / "remote.txt").write_text("old-remote\n", encoding="utf-8")
            hooks = {
                "hooks": {
                    event: [{"hooks": [{
                        sync_mod.LEGACY_HOOK_MARKER_KEY: f"{sync_mod.LEGACY_HOOK_ID}:{event}",
                        "type": "command",
                        "command": "legacy",
                    }]}]
                    for event in ("SessionStart", "Stop", "SessionEnd")
                }
            }
            (codex / "hooks.json").write_text(json.dumps(hooks), encoding="utf-8")
            hook_python = Path(sync_mod.sys.executable).resolve()
            with mock.patch.dict(sync_mod.os.environ, {"CODEX_HOME": str(codex)}), mock.patch.object(
                sync_mod, "stable_hook_python", return_value=hook_python
            ), mock.patch.object(
                sync_mod,
                "ensure_github_repository",
                return_value=("git@example.invalid:private/memories.git", "reused"),
            ), mock.patch.object(sync_mod, "reconcile", return_value="noop"):
                self.assertEqual(sync_mod.main(["maintain"]), 0)
            current_state = codex / ".bridgeforge-codex" / "memory-sync"
            self.assertFalse((codex / ".bridgeforge").exists())
            self.assertEqual(
                (current_state / "remote.txt").read_text(encoding="utf-8"),
                "git@example.invalid:private/memories.git\n",
            )
            document = json.loads((codex / "hooks.json").read_text(encoding="utf-8"))
            managed = [
                handler
                for entries in document["hooks"].values()
                for entry in entries
                for handler in entry["hooks"]
                if sync_mod.HOOK_MARKER_KEY in handler
            ]
            self.assertEqual(len(managed), 3)
            self.assertFalse(any(
                sync_mod.LEGACY_HOOK_MARKER_KEY in handler
                for entries in document["hooks"].values()
                for entry in entries
                for handler in entry["hooks"]
            ))

    def test_legacy_enabled_maintain_fails_closed_without_external_or_user_writes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex = Path(raw) / ".codex"
            self._write_ledger(codex)
            (codex / "config.toml").write_text(
                "[features]\nmemories = true\n[memories]\ngenerate_memories = true\nuse_memories = true\n",
                encoding="utf-8",
            )
            before = {path.name: path.read_bytes() for path in codex.iterdir() if path.is_file()}
            with mock.patch.dict(sync_mod.os.environ, {"CODEX_HOME": str(codex)}), mock.patch.object(
                sync_mod, "ensure_github_repository"
            ) as github, mock.patch.object(sync_mod, "merge_user_hooks") as hooks:
                self.assertEqual(sync_mod.main(["maintain"]), 2)
            github.assert_not_called()
            hooks.assert_not_called()
            after = {path.name: path.read_bytes() for path in codex.iterdir() if path.is_file()}
            self.assertEqual(after, before)
            self.assertFalse((codex / ".bridgeforge-codex").exists())

    def test_status_is_read_only_even_when_codex_home_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex = Path(raw) / "missing-codex"
            with mock.patch.dict(sync_mod.os.environ, {"CODEX_HOME": str(codex)}):
                self.assertEqual(sync_mod.main(["status"]), 2)
            self.assertFalse(codex.exists())

    def test_setup_leaves_config_untouched_when_github_preflight_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex = Path(raw) / ".codex"
            self._write_ledger(codex)
            with mock.patch.dict(sync_mod.os.environ, {"CODEX_HOME": str(codex)}), mock.patch.object(
                sync_mod, "ensure_github_repository", side_effect=sync_mod.SyncError("gh unavailable")
            ):
                self.assertEqual(sync_mod.main(["setup", "--confirmed-enable"]), 2)
            self.assertFalse((codex / "config.toml").exists())
            self.assertFalse((codex / "hooks.json").exists())

    def test_setup_from_project_venv_persists_only_the_base_python(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            codex = root / ".codex"
            self._write_ledger(codex)
            venv_python = root / "project/.venv/Scripts/python.exe"
            base_python = root / "Python312/python.exe"
            venv_python.parent.mkdir(parents=True)
            base_python.parent.mkdir(parents=True)
            venv_python.write_bytes(b"venv")
            base_python.write_bytes(b"base")
            output = io.StringIO()
            with mock.patch.dict(sync_mod.os.environ, {"CODEX_HOME": str(codex)}), mock.patch.object(
                sync_mod.sys,
                "executable",
                str(venv_python),
            ), mock.patch.object(
                sync_mod.sys,
                "_base_executable",
                str(base_python),
            ), mock.patch.object(
                sync_mod,
                "ensure_github_repository",
                return_value=("git@example.invalid:private/memories.git", "created"),
            ), contextlib.redirect_stdout(output):
                self.assertEqual(sync_mod.main(["setup", "--confirmed-enable"]), 0)
            hooks = json.loads((codex / "hooks.json").read_text(encoding="utf-8"))
            managed = [
                handler
                for entries in hooks["hooks"].values()
                for entry in entries
                for handler in entry["hooks"]
                if handler.get(sync_mod.HOOK_MARKER_KEY, "").startswith(sync_mod.HOOK_ID)
            ]
            self.assertEqual(len(managed), 3)
            self.assertTrue(all(str(base_python.resolve()) in handler["command"] for handler in managed))
            self.assertTrue(all(str(venv_python.resolve()) not in handler["command"] for handler in managed))
            self.assertIn(f"setup_python={venv_python.resolve()}", output.getvalue())
            self.assertIn(f"hook_python={base_python.resolve()}", output.getvalue())
            self.assertIn("remote_action=created", output.getvalue())
            self.assertEqual(
                (codex / ".bridgeforge-codex/memory-sync/remote.txt").read_text(encoding="utf-8"),
                "git@example.invalid:private/memories.git\n",
            )
            self.assertEqual(
                sync_mod.native_memories_consent(codex / "bridgeforge-codex-managed.json"),
                "approved",
            )

    def test_declined_consent_is_persisted_without_external_or_config_writes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex = Path(raw) / ".codex"
            ledger = self._write_ledger(codex)
            with mock.patch.dict(sync_mod.os.environ, {"CODEX_HOME": str(codex)}), mock.patch.object(
                sync_mod,
                "ensure_github_repository",
            ) as github, mock.patch.object(sync_mod, "merge_user_hooks") as hooks:
                self.assertEqual(sync_mod.main(["decline", "--confirmed"]), 0)
            github.assert_not_called()
            hooks.assert_not_called()
            self.assertEqual(sync_mod.native_memories_consent(ledger), "declined")
            self.assertFalse((codex / "config.toml").exists())
            self.assertFalse((codex / "hooks.json").exists())
            self.assertFalse((codex / ".bridgeforge-codex").exists())

    def test_consent_ledger_validation_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex = Path(raw) / ".codex"
            ledger = self._write_ledger(codex)
            data = json.loads(ledger.read_text(encoding="utf-8"))
            data["consents"] = {"native_memories": "maybe"}
            ledger.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(sync_mod.SyncError, "invalid native memories consent"):
                sync_mod.native_memories_consent(ledger)

    def test_config_merge_requires_confirmation_and_preserves_other_toml(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            config = Path(raw) / "config.toml"
            original = "model = 'custom'\n[features]\nfoo = true\nmemories = false # keep comment\n[memories]\ncustom = 7\n"
            config.write_text(original, encoding="utf-8")
            with self.assertRaises(sync_mod.SyncError):
                sync_mod.enable_memories(config, confirmed=False)
            self.assertEqual(config.read_text(encoding="utf-8"), original)
            self.assertTrue(sync_mod.enable_memories(config, confirmed=True))
            enabled, data = sync_mod.memory_switches(config)
            self.assertTrue(enabled)
            self.assertEqual(data["model"], "custom")
            self.assertEqual(data["memories"]["custom"], 7)
            self.assertIn("memories = true # keep comment", config.read_text(encoding="utf-8"))

    def test_user_hook_merge_is_idempotent_and_preserves_third_party(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "hooks.json"
            hook_python = Path(raw) / "Python312/python.exe"
            hook_python.parent.mkdir()
            hook_python.write_bytes(b"base")
            third_party = {"matcher": "*", "vendor": {"opaque": [1, 2]}, "hooks": [{"type": "command", "command": "display", "async": False}]}
            path.write_text(json.dumps({"custom": "keep", "hooks": {"SessionStart": [third_party]}}), encoding="utf-8")
            script = Path(raw) / "runtime.py"
            self.assertTrue(sync_mod.merge_user_hooks(path, script, hook_python=hook_python))
            self.assertTrue(sync_mod.user_hooks_healthy(path, script, hook_python=hook_python))
            first = path.read_bytes()
            self.assertFalse(sync_mod.merge_user_hooks(path, script, hook_python=hook_python))
            self.assertEqual(first, path.read_bytes())
            data = json.loads(first)
            self.assertEqual(data["custom"], "keep")
            self.assertEqual(data["hooks"]["SessionStart"][0], third_party)
            handlers = [
                handler
                for entries in data["hooks"].values()
                for entry in entries
                for handler in entry.get("hooks", [])
                if sync_mod.HOOK_MARKER_KEY in handler
            ]
            self.assertEqual(len(handlers), 3)
            self.assertTrue(all(handler["command"].startswith(f'"{hook_python.resolve()}"') for handler in handlers))
            session_end = next(h for h in handlers if h[sync_mod.HOOK_MARKER_KEY].endswith(":SessionEnd"))
            stop = next(h for h in handlers if h[sync_mod.HOOK_MARKER_KEY].endswith(":Stop"))
            session_start = next(h for h in handlers if h[sync_mod.HOOK_MARKER_KEY].endswith(":SessionStart"))
            self.assertEqual(session_end["timeout"], 3)
            self.assertNotIn("async", session_end)
            self.assertIn("kick --trigger session-end", session_end["command"])
            self.assertTrue(stop["async"])
            self.assertEqual(stop["timeout"], 120)
            self.assertEqual(session_start["timeout"], 120)

    def test_session_end_kick_detaches_reconciliation(self) -> None:
        with mock.patch.object(sync_mod.subprocess, "Popen") as popen:
            sync_mod.launch_background_reconcile("session-end")
        command = popen.call_args.args[0]
        kwargs = popen.call_args.kwargs
        self.assertEqual(command[0], str(sync_mod.stable_hook_python()))
        self.assertEqual(command[-3:], ["reconcile", "--trigger", "session-end"])
        self.assertIs(kwargs["stdout"], subprocess.DEVNULL)
        if sync_mod.os.name == "nt":
            self.assertTrue(kwargs["creationflags"] & 0x00000008)
        else:
            self.assertTrue(kwargs["start_new_session"])

    def test_external_command_timeout_becomes_a_normal_failure_receipt(self) -> None:
        with mock.patch.object(sync_mod.subprocess, "run", side_effect=subprocess.TimeoutExpired(["git"], 45)):
            result = sync_mod._default_run(["git", "fetch"])
        self.assertEqual(result.returncode, 124)
        self.assertIn("timed out", result.stderr)

    def test_user_hook_merge_repairs_and_deduplicates_managed_handlers(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "hooks.json"
            old_venv = Path(raw) / "old-project/.venv/Scripts/python.exe"
            hook_python = Path(raw) / "Python312/python.exe"
            hook_python.parent.mkdir()
            hook_python.write_bytes(b"base")
            legacy_managed_id = f"{sync_mod.LEGACY_HOOK_ID}:SessionStart"
            managed_id = f"{sync_mod.HOOK_ID}:SessionStart"
            path.write_text(
                json.dumps({"hooks": {"SessionStart": [
                    {"matcher": "keep", "hooks": [{sync_mod.LEGACY_HOOK_MARKER_KEY: legacy_managed_id, "command": f'"{old_venv}" runtime.py'}, {"command": "vendor"}]},
                    {"hooks": [{sync_mod.LEGACY_HOOK_MARKER_KEY: legacy_managed_id, "command": "duplicate"}]},
                ]}}),
                encoding="utf-8",
            )
            self.assertTrue(sync_mod.merge_user_hooks(path, Path(raw) / "runtime.py", hook_python=hook_python))
            data = json.loads(path.read_text(encoding="utf-8"))
            handlers = [handler for entry in data["hooks"]["SessionStart"] for handler in entry["hooks"]]
            self.assertEqual(sum(handler.get(sync_mod.HOOK_MARKER_KEY) == managed_id for handler in handlers), 1)
            self.assertFalse(any(sync_mod.LEGACY_HOOK_MARKER_KEY in handler for handler in handlers))
            self.assertIn({"command": "vendor"}, handlers)
            self.assertEqual(data["hooks"]["SessionStart"][0]["matcher"], "keep")
            managed = next(handler for handler in handlers if handler.get(sync_mod.HOOK_MARKER_KEY) == managed_id)
            self.assertIn(str(hook_python.resolve()), managed["command"])
            self.assertNotIn(str(old_venv), managed["command"])

    def test_snapshot_excludes_temp_lock_metadata_and_detects_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            source = base / "memories"
            source.mkdir()
            (source / "kept.md").write_text("keep", encoding="utf-8")
            (source / "skip.tmp").write_text("temp", encoding="utf-8")
            (source / "writer.lock").write_text("lock", encoding="utf-8")
            manifest = sync_mod.build_snapshot(source, base / "snapshot", 4)
            self.assertEqual(manifest["revision"], 4)
            self.assertEqual([item["path"] for item in manifest["files"]], ["kept.md"])
            self.assertFalse((base / "snapshot/memories/skip.tmp").exists())
            sync_mod.verify_snapshot(base / "snapshot", manifest)
            (base / "snapshot/memories/kept.md").write_text("tampered", encoding="utf-8")
            with self.assertRaises(sync_mod.SyncError):
                sync_mod.verify_snapshot(base / "snapshot", manifest)

    @unittest.skipUnless(sys.platform == "win32", "Windows junction semantics required")
    def test_snapshot_rejects_root_and_nested_directory_junctions(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            outside = base / "outside"
            outside.mkdir()
            (outside / "secret.md").write_text("outside", encoding="utf-8")

            root_link = base / "root-link"
            nested_root = base / "memories"
            nested_root.mkdir()
            nested_link = nested_root / "linked"
            for link in (root_link, nested_link):
                subprocess.run(
                    ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(outside)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            try:
                with self.assertRaises(sync_mod.SyncError):
                    sync_mod.capture_manifest(root_link, 1)
                with self.assertRaises(sync_mod.SyncError):
                    sync_mod.capture_manifest(nested_root, 1)
            finally:
                os.rmdir(nested_link)
                os.rmdir(root_link)
            self.assertEqual(
                sync_mod.choose_action(
                    "local-new", "remote-new", "old",
                    local_updated_at="2026-08-14T12:00:00+00:00",
                    remote_updated_at="2026-08-14T11:00:00+00:00",
                ),
                "push",
            )
            self.assertEqual(
                sync_mod.choose_action(
                    "local-new", "remote-new", None,
                    local_updated_at="1970-01-01T00:00:00+00:00",
                    remote_updated_at="2026-08-14T11:00:00+00:00",
                ),
                "restore",
            )

    def test_reconcile_does_not_create_native_memories_without_local_or_remote_content(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            memories = base / "memories"
            with mock.patch.object(sync_mod, "_read_remote_snapshot", return_value=(None, None, None)):
                action = sync_mod.reconcile(memories, base / "state", "unused")
            self.assertEqual(action, "noop")
            self.assertFalse(memories.exists())

    @unittest.skipUnless(shutil.which("git"), "git required")
    def test_real_empty_remote_is_a_quiet_noop_without_creating_native_memories(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            remote, manifest, commit = self._create_empty_remote(base)
            codex = base / ".codex"
            codex.mkdir()
            (codex / "config.toml").write_text(
                "[features]\nmemories = true\n[memories]\ngenerate_memories = true\nuse_memories = true\n",
                encoding="utf-8",
            )
            state = codex / ".bridgeforge-codex/memory-sync"
            state.mkdir(parents=True)
            (state / "remote.txt").write_text(str(remote), encoding="utf-8")
            sync_mod.mark_pending(state, "bridgeforge")
            output = io.StringIO()
            errors = io.StringIO()
            with mock.patch.dict(sync_mod.os.environ, {"CODEX_HOME": str(codex)}), contextlib.redirect_stdout(
                output
            ), contextlib.redirect_stderr(errors):
                self.assertEqual(sync_mod.main(["reconcile", "--trigger", "bridgeforge"]), 0)
            receipt = json.loads((state / "last-synced.json").read_text(encoding="utf-8"))
            self.assertEqual(output.getvalue(), "[memory-sync] noop\n")
            self.assertEqual(errors.getvalue(), "")
            self.assertFalse((codex / "memories").exists())
            self.assertFalse((state / "pending.json").exists())
            self.assertEqual(receipt["content_sha256"], manifest["content_sha256"])
            self.assertEqual(receipt["commit"], commit)

    @unittest.skipUnless(shutil.which("git"), "git required")
    def test_empty_local_directory_and_empty_remote_are_a_noop(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            remote, _manifest, _commit = self._create_empty_remote(base)
            memories = base / "memories"
            memories.mkdir()
            state = base / "state"
            sync_mod.mark_pending(state, "stop")
            self.assertEqual(sync_mod.reconcile(memories, state, str(remote)), "noop")
            self.assertTrue(memories.is_dir())
            self.assertEqual(list(memories.iterdir()), [])
            self.assertFalse((state / "pending.json").exists())

    @unittest.skipUnless(shutil.which("git"), "git required")
    def test_local_content_pushes_over_an_empty_remote(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            remote, _manifest, _commit = self._create_empty_remote(base)
            memories = base / "memories"
            memories.mkdir()
            payloads = {
                "crlf.md": b"local\r\nopaque\r\n",
                "lf.md": b"local\nopaque\n",
            }
            for name, payload in payloads.items():
                (memories / name).write_bytes(payload)
            self.assertEqual(sync_mod.reconcile(memories, base / "state", str(remote)), "push")
            verify_state = base / "verify-state"
            verify_state.mkdir()
            remote_manifest, extracted, _commit = sync_mod._read_remote_snapshot(verify_state, str(remote))
            self.assertIsNotNone(remote_manifest)
            self.assertEqual([item["path"] for item in remote_manifest["files"]], sorted(payloads))
            for name, payload in payloads.items():
                self.assertEqual((extracted / "memories" / name).read_bytes(), payload)

    @unittest.skipUnless(shutil.which("git"), "git required")
    def test_invalid_empty_remote_remains_corrupt(self) -> None:
        for changes in ({"content_sha256": "0" * 64}, {"schema_version": 99}):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as raw:
                base = Path(raw)
                remote, _manifest, _commit = self._create_empty_remote(base, changes)
                state = base / "state"
                sync_mod.mark_pending(state, "bridgeforge")
                memories = base / "memories"
                with self.assertRaisesRegex(sync_mod.SyncError, "remote snapshot is corrupt"):
                    sync_mod.reconcile(memories, state, str(remote))
                self.assertFalse(memories.exists())
                self.assertTrue((state / "pending.json").exists())

    def test_snapshot_retries_and_rejects_a_tree_that_changes_during_copy(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            source = base / "memories"
            source.mkdir()
            (source / "note.md").write_text("stable source", encoding="utf-8")
            real_copy = sync_mod.shutil.copy2

            def tampering_copy(source_path: Path, target_path: Path) -> None:
                real_copy(source_path, target_path)
                Path(target_path).write_text("changed after copy", encoding="utf-8")

            with mock.patch.object(sync_mod.shutil, "copy2", side_effect=tampering_copy):
                with self.assertRaises(sync_mod.SyncError):
                    sync_mod.build_snapshot(source, base / "snapshot", 1)

    def test_concurrent_reconcile_is_deduplicated_and_keeps_pending(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            state = base / "state"
            state.mkdir()
            descriptor = sync_mod._acquire_reconcile_lock(state)
            self.assertIsNotNone(descriptor)
            try:
                with mock.patch.object(sync_mod, "_read_remote_snapshot") as remote_read:
                    self.assertEqual(sync_mod.reconcile(base / "memories", state, "unused"), "busy")
                remote_read.assert_not_called()
                self.assertTrue((state / "pending.json").is_file())
            finally:
                sync_mod._release_reconcile_lock(state, descriptor)

    def test_stale_incomplete_reconcile_lock_is_recoverable(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            lock = state / "reconcile.lock"
            lock.write_text("incomplete", encoding="utf-8")
            old = time.time() - 120
            sync_mod.os.utime(lock, (old, old))
            descriptor = sync_mod._acquire_reconcile_lock(state)
            self.assertIsNotNone(descriptor)
            sync_mod._release_reconcile_lock(state, descriptor)
            self.assertFalse(lock.exists())

    def test_recorded_transient_snapshot_is_cleaned_on_the_next_run(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            state = Path(raw)
            stranded = Path(tempfile.mkdtemp(prefix=sync_mod.WORKDIR_PREFIX))
            (stranded / "memory.md").write_text("plaintext", encoding="utf-8")
            try:
                sync_mod._record_workdir(state, stranded)
                sync_mod._cleanup_recorded_workdir(state)
                self.assertFalse(stranded.exists())
                self.assertFalse((state / "transient-workdir.json").exists())
            finally:
                if stranded.exists():
                    shutil.rmtree(stranded)

    def test_hook_reconcile_trigger_has_no_invalid_plaintext_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            codex = Path(raw) / ".codex"
            codex.mkdir()
            (codex / "config.toml").write_text(
                "[features]\nmemories = true\n[memories]\ngenerate_memories = true\nuse_memories = true\n",
                encoding="utf-8",
            )
            state = codex / ".bridgeforge-codex/memory-sync"
            state.mkdir(parents=True)
            (state / "remote.txt").write_text("unused\n", encoding="utf-8")
            output = io.StringIO()
            with mock.patch.dict(sync_mod.os.environ, {"CODEX_HOME": str(codex)}), mock.patch.object(
                sync_mod, "reconcile", return_value="noop"
            ), contextlib.redirect_stdout(output):
                self.assertEqual(sync_mod.main(["reconcile", "--trigger", "stop"]), 0)
            self.assertEqual(output.getvalue(), "{}\n")

    @unittest.skipUnless(shutil.which("git"), "git required")
    def test_existing_ordinary_repository_is_reused_and_initialized(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            remote = base / "remote.git"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            ordinary = base / "ordinary"
            ordinary.mkdir()
            for command in (
                ["git", "init", "-b", "main"],
                ["git", "config", "user.name", "Test"],
                ["git", "config", "user.email", "test@example.invalid"],
            ):
                subprocess.run(command, cwd=ordinary, check=True, capture_output=True)
            (ordinary / "README.md").write_text("ordinary repo\n", encoding="utf-8")
            for command in (["git", "add", "README.md"], ["git", "commit", "-m", "readme"], ["git", "remote", "add", "origin", str(remote)], ["git", "push", "origin", "main"]):
                subprocess.run(command, cwd=ordinary, check=True, capture_output=True)

            local = base / "memories"
            local.mkdir()
            (local / "note.md").write_text("native memory", encoding="utf-8")
            self.assertEqual(sync_mod.reconcile(local, base / "state", str(remote)), "push")
            count = subprocess.run(["git", f"--git-dir={remote}", "rev-list", "--count", "main"], check=True, text=True, capture_output=True).stdout.strip()
            manifest = subprocess.run(["git", f"--git-dir={remote}", "show", "main:snapshot-manifest.json"], check=True, text=True, capture_output=True).stdout
            self.assertEqual(count, "1")
            self.assertEqual(json.loads(manifest)["schema_version"], 1)

    @unittest.skipUnless(shutil.which("git"), "git required")
    def test_valid_local_snapshot_repairs_a_corrupt_remote_commit(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            remote = base / "remote.git"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            broken = base / "broken"
            (broken / "memories").mkdir(parents=True)
            (broken / "memories/bad.md").write_text("bad", encoding="utf-8")
            (broken / "snapshot-manifest.json").write_text('{}\n', encoding="utf-8")
            bad_commit = sync_mod._push_snapshot(broken, base / "bad-state", str(remote), None)

            local = base / "local"
            local.mkdir()
            (local / "good.md").write_text("good", encoding="utf-8")
            action = sync_mod.reconcile(local, base / "repair-state", str(remote))
            verify_state = base / "verify-state"
            verify_state.mkdir()
            manifest, extracted, repaired_commit = sync_mod._read_remote_snapshot(verify_state, str(remote))

            self.assertEqual(action, "push")
            self.assertNotEqual(repaired_commit, bad_commit)
            self.assertIsNotNone(manifest)
            self.assertEqual((extracted / "memories/good.md").read_text(encoding="utf-8"), "good")

    @unittest.skipUnless(shutil.which("git"), "git required")
    def test_local_state_io_failure_never_overwrites_a_valid_remote(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            remote = base / "remote.git"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            cloud = base / "cloud"
            cloud.mkdir()
            (cloud / "cloud.md").write_text("cloud", encoding="utf-8")
            sync_mod.reconcile(cloud, base / "cloud-state", str(remote))

            local = base / "local"
            local.mkdir()
            (local / "local.md").write_text("local", encoding="utf-8")
            state = base / "local-state"
            with mock.patch.object(sync_mod, "_read_remote_snapshot", side_effect=OSError("disk failure")), mock.patch.object(
                sync_mod, "_push_snapshot"
            ) as push:
                with self.assertRaises(OSError):
                    sync_mod.reconcile(local, state, str(remote))
            push.assert_not_called()

    @unittest.skipUnless(shutil.which("git"), "git required")
    def test_new_machine_restores_newer_whole_remote_snapshot_without_backup(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            remote = base / "remote.git"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            cloud = base / "cloud-memories"
            cloud.mkdir()
            cloud_file = cloud / "cloud.md"
            cloud_file.write_text("cloud", encoding="utf-8")
            sync_mod.reconcile(cloud, base / "cloud-state", str(remote))

            local = base / "local-memories"
            local.mkdir()
            stale = local / "stale.md"
            stale.write_text("stale", encoding="utf-8")
            old = time.time() - 3600
            sync_mod.os.utime(stale, (old, old))
            action = sync_mod.reconcile(local, base / "local-state", str(remote))

            self.assertEqual(action, "restore")
            self.assertEqual((local / "cloud.md").read_text(encoding="utf-8"), "cloud")
            self.assertFalse((local / "stale.md").exists())
            self.assertFalse((base / ".local-memories.bridgeforge-codex-replaced").exists())
            for state in (base / "cloud-state", base / "local-state"):
                self.assertFalse(any(path.is_dir() for path in state.iterdir()))

    @unittest.skipUnless(shutil.which("git"), "git required")
    def test_force_lease_replaces_with_one_parentless_commit(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            remote = base / "remote.git"
            subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
            state = base / "state"
            state.mkdir()
            snapshot = base / "snapshot"
            (snapshot / "memories").mkdir(parents=True)
            (snapshot / "memories/a.md").write_text("one", encoding="utf-8")
            (snapshot / "snapshot-manifest.json").write_text('{}\n', encoding="utf-8")
            first = sync_mod._push_snapshot(snapshot, state, str(remote), None)
            (snapshot / "memories/a.md").write_text("two", encoding="utf-8")
            second = sync_mod._push_snapshot(snapshot, state, str(remote), first)
            self.assertNotEqual(first, second)
            count = subprocess.run(["git", f"--git-dir={remote}", "rev-list", "--count", "main"], check=True, text=True, capture_output=True).stdout.strip()
            parents = subprocess.run(["git", f"--git-dir={remote}", "rev-list", "--parents", "-1", "main"], check=True, text=True, capture_output=True).stdout.split()
            self.assertEqual(count, "1")
            self.assertEqual(len(parents), 1)

    def test_public_repository_needs_explicit_confirmation(self) -> None:
        calls: list[list[str]] = []
        def runner(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[:3] == ["gh", "auth", "status"]:
                return subprocess.CompletedProcess(command, 0, "", "")
            return subprocess.CompletedProcess(command, 0, json.dumps({"visibility": "PUBLIC", "url": "https://example/repo.git", "nameWithOwner": "me/bridgeforge-codex-memories"}), "")
        with mock.patch.object(sync_mod.shutil, "which", return_value="gh"):
            with self.assertRaises(sync_mod.SyncError):
                sync_mod.ensure_github_repository(confirmed_public_to_private=False, run=runner)
            remote, action = sync_mod.ensure_github_repository(confirmed_public_to_private=True, run=runner)
        self.assertEqual(remote, "https://example/repo.git")
        self.assertEqual(action, "made-private")
        edit = next(command for command in calls if command[:3] == ["gh", "repo", "edit"])
        self.assertIn("--accept-visibility-change-consequences", edit)
        auth = next(command for command in calls if command[:3] == ["gh", "auth", "status"])
        self.assertEqual(auth, ["gh", "auth", "status", "--active", "--hostname", "github.com"])


if __name__ == "__main__":
    unittest.main()
