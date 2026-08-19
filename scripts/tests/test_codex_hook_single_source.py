from __future__ import annotations

import json
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "templates"


def run(command: list[str], cwd: Path, payload: dict | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        command,
        cwd=cwd,
        input=json.dumps(payload) if payload is not None else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare_project_runtime(project_root: Path) -> Path:
    created = run(
        [
            sys.executable,
            "-m",
            "venv",
            "--without-pip",
            str(project_root / ".venv"),
        ],
        project_root,
    )
    if created.returncode != 0:
        raise AssertionError(created.stdout + created.stderr)
    return (
        project_root / ".venv" / "Scripts" / "python.exe"
        if os.name == "nt"
        else project_root / ".venv" / "bin" / "python"
    )


def prepare_dispatcher_runtime(project_root: Path) -> Path:
    project_python = prepare_project_runtime(project_root)
    scripts = project_root / ".codex" / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        TEMPLATE / "scripts" / "project_runtime.py",
        scripts / "project_runtime.py",
    )
    return project_python


class HookSingleSourceTest(unittest.TestCase):
    def test_atomic_write_stages_outside_codex_directory(self) -> None:
        module = load_module(
            TEMPLATE / "scripts" / "hooks_merge.py",
            "hooks_merge_atomic_write_staging",
        )
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            codex = root / ".codex"
            codex.mkdir()
            target = codex / "hooks.json"
            original_mkstemp = tempfile.mkstemp
            with mock.patch.object(
                module.tempfile,
                "mkstemp",
                wraps=original_mkstemp,
            ) as staged:
                module._atomic_write(target, '{"hooks": {}}\n')
            self.assertEqual(Path(staged.call_args.kwargs["dir"]), root)
            self.assertEqual(target.read_text(encoding="utf-8"), '{"hooks": {}}\n')
            self.assertFalse(list(root.glob("hooks.json.*")))

    def test_positive_suite_uses_project_python_311_or_newer(self) -> None:
        self.assertGreaterEqual(sys.version_info, (3, 11))
        self.assertEqual(
            Path(sys.executable).resolve(),
            (ROOT / ".venv" / "Scripts" / "python.exe").resolve(),
        )

    def test_precommit_rejects_low_project_venv_without_path_fallback(self) -> None:
        shell = shutil.which("sh")
        if shell is None:
            git = shutil.which("git")
            if git is not None:
                git_root = Path(git).resolve().parent.parent
                for candidate in (git_root / "bin" / "sh.exe", git_root / "usr" / "bin" / "sh.exe"):
                    if candidate.is_file():
                        shell = str(candidate)
                        break
        if shell is None:
            self.skipTest("POSIX shell is required to exercise pre-commit hooks")
        precommits = (
            ROOT / ".githooks" / "pre-commit",
            ROOT / "templates" / ".githooks" / "pre-commit",
        )
        for precommit in precommits:
            with self.subTest(precommit=precommit), tempfile.TemporaryDirectory() as raw:
                project = Path(raw)
                low_python = project / ".venv" / "bin" / "python"
                low_python.parent.mkdir(parents=True)
                low_python.write_text("#!/bin/sh\nexit 2\n", encoding="utf-8")
                low_python.chmod(0o755)
                stamp = project / ".bridgeforge_codex_version"
                stamp.write_text("old\n", encoding="utf-8")
                sentinel = project / "sentinel.txt"
                sentinel.write_text("unchanged\n", encoding="utf-8")
                before = (stamp.read_bytes(), sentinel.read_bytes())
                result = subprocess.run(
                    [shell, str(precommit)],
                    cwd=project,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("PATH fallback is forbidden", result.stderr)
                self.assertEqual(before, (stamp.read_bytes(), sentinel.read_bytes()))

            with self.subTest(precommit=precommit, runtime="missing"), \
                    tempfile.TemporaryDirectory() as raw:
                project = Path(raw)
                sentinel = project / "sentinel.txt"
                sentinel.write_text("unchanged\n", encoding="utf-8")
                result = subprocess.run(
                    [shell, str(precommit)],
                    cwd=project,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn("project .venv is missing", result.stderr)
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "unchanged\n")

    def test_handler_audit_maps_all_36_to_behavior(self) -> None:
        dispatcher_path = TEMPLATE / "hooks" / "hook_dispatcher.py"
        dispatcher = load_module(dispatcher_path, "hook_dispatcher_audit")
        audit = dispatcher.HANDLER_AUDIT
        self.assertEqual([int(key.split(":", 1)[0]) for key in audit], list(range(1, 37)))
        counts = {
            decision: sum(value[0] == decision for value in audit.values())
            for decision in ("retain", "adapt", "delete")
        }
        self.assertEqual(counts, {"retain": 16, "adapt": 18, "delete": 2})
        self.assertEqual(dispatcher.handler_audit_errors(), [])
        self.assertNotIn(
            "hooks/target_cleanup.py",
            {
                target
                for targets in dispatcher.RUNTIME_ROUTES.values()
                for target in targets
            },
        )
        for key, (decision, route, target) in audit.items():
            if route in dispatcher.RUNTIME_ROUTES:
                self.assertIn(target, dispatcher.RUNTIME_ROUTES[route], key)
            elif route == "replacement":
                self.assertEqual(decision, "adapt")
                self.assertEqual(target, "skill-routing:$find-doc")
            else:
                self.assertEqual(decision, "delete")
                self.assertEqual(route, "duplicate")
                duplicate_key = next(
                    item for item in audit if item.startswith(target + ":")
                )
                self.assertEqual(
                    key.rsplit(":", 1)[-1],
                    duplicate_key.rsplit(":", 1)[-1],
                )
                self.assertIn(":PowerShell:", key)
                self.assertIn(":Bash:", duplicate_key)

        broken_routes = {
            route: tuple(targets)
            for route, targets in dispatcher.RUNTIME_ROUTES.items()
        }
        broken_routes["pre-shell"] = tuple(
            target for target in broken_routes["pre-shell"]
            if target != "hooks/git_add_all_guard.py"
        )
        errors = dispatcher.handler_audit_errors(broken_routes)
        self.assertTrue(any(error.startswith("02:") for error in errors), errors)

    def test_dispatcher_blocks_invalid_project_runtime_before_any_route(self) -> None:
        dispatcher = load_module(
            TEMPLATE / "hooks" / "hook_dispatcher.py",
            "hook_dispatcher_runtime_contract",
        )
        for reason in (
            "project runtime must be CPython",
            "project runtime prefix is not the target project .venv",
            "current Python is not the target project .venv interpreter",
        ):
            with self.subTest(reason=reason), mock.patch.object(
                dispatcher,
                "_project_runtime_error",
                return_value=reason,
            ), mock.patch.object(dispatcher, "_read_payload") as read_payload, \
                    mock.patch.object(sys, "argv", ["hook_dispatcher.py", "pre-tool"]):
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    result = dispatcher.main()
                self.assertEqual(result, 2)
                self.assertIn(reason, stderr.getvalue())
                read_payload.assert_not_called()

    def test_retired_context_budget_is_absent_from_active_user_prompt_contract(self) -> None:
        template_hooks = json.loads(
            (TEMPLATE / "hooks.json").read_text(encoding="utf-8")
        )
        dogfood_hooks = json.loads(
            (ROOT / ".codex/hooks.json").read_text(encoding="utf-8")
        )
        self.assertEqual(template_hooks, dogfood_hooks)
        user_prompt = json.dumps(
            template_hooks["hooks"]["UserPromptSubmit"],
            ensure_ascii=False,
        ).casefold()
        self.assertNotIn("context budget", user_prompt)
        self.assertIn(
            "repository state, clarification, and focus signals",
            user_prompt,
        )

        dispatcher = load_module(
            TEMPLATE / "hooks" / "hook_dispatcher.py",
            "hook_dispatcher_without_context_budget",
        )
        self.assertNotIn(
            "hooks/context_warning.py",
            dispatcher.RUNTIME_ROUTES["user-prompt"],
        )
        contract = json.loads(
            (TEMPLATE / "managed-skeleton.json").read_text(encoding="utf-8")
        )
        context_warning = next(
            asset
            for asset in contract["assets"]
            if asset["id"] == "codex.hook.context-warning"
        )
        self.assertEqual(context_warning["strategy"], "retirement")
        self.assertNotIn("source", context_warning)

    def test_template_registration_is_single_source_and_git_rooted(self) -> None:
        settings = json.loads((TEMPLATE / "settings.json").read_text(encoding="utf-8"))
        dogfood_settings = json.loads((ROOT / ".codex" / "settings.json").read_text(encoding="utf-8"))
        hooks = json.loads((TEMPLATE / "hooks.json").read_text(encoding="utf-8"))
        self.assertNotIn("hooks", settings)
        self.assertNotIn("hooks", dogfood_settings)
        self.assertIsInstance(hooks.get("hooks"), dict)
        commands = []
        for blocks in hooks["hooks"].values():
            for block in blocks:
                for hook in block.get("hooks", []):
                    commands.append(hook)
        self.assertEqual(len(commands), 8)
        for hook in commands:
            self.assertIn("git rev-parse --show-toplevel", hook["command"])
            self.assertIn("git rev-parse --show-toplevel", hook["commandWindows"])
            self.assertIn("hook_dispatcher.py", hook["command"])
        session_start = hooks["hooks"]["SessionStart"][0]["hooks"][0]
        self.assertEqual(session_start["additionalContextLimit"], 0)

    def test_dogfood_registration_matches_template_and_uses_project_venv(self) -> None:
        template = json.loads((TEMPLATE / "hooks.json").read_text(encoding="utf-8"))
        dogfood = json.loads((ROOT / ".codex" / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(template, dogfood)
        for blocks in template["hooks"].values():
            for block in blocks:
                for hook in block.get("hooks", []):
                    self.assertIn(
                        '$(git rev-parse --show-toplevel)/.venv/Scripts/python.exe',
                        hook["command"],
                    )
                    self.assertIn(
                        "(Join-Path (git rev-parse --show-toplevel) '.venv/Scripts/python.exe')",
                        hook["commandWindows"],
                    )

    def test_dispatcher_orders_memory_chain_and_skips_lint_after_rebuild_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            host = root / ".codex"
            (host / "hooks").mkdir(parents=True)
            (host / "scripts").mkdir()
            shutil.copy2(TEMPLATE / "hooks" / "hook_dispatcher.py", host / "hooks" / "hook_dispatcher.py")
            project_python = prepare_dispatcher_runtime(root)
            log = root / "order.log"
            stub = (
                "import os,sys\n"
                f"open({str(log)!r}, 'a', encoding='utf-8').write(os.path.basename(__file__)+'\\n')\n"
                "sys.exit(int(os.environ.get('STUB_EXIT', '0')) if os.path.basename(__file__) == 'memory_rebuild_index.py' else 0)\n"
            )
            hook_names = (
                "encoding_check.py", "mirror_drift_check.py", "instruction_source_check.py",
                "rule_index_check.py", "rule_size_check.py",
                "requirements_check.py", "cargo_default_run_check.py",
                "fallback_smell_check.py", "memory_lint.py",
            )
            for name in hook_names:
                (host / "hooks" / name).write_text(stub, encoding="utf-8")
            (host / "scripts" / "memory_rebuild_index.py").write_text(stub, encoding="utf-8")
            payload = {
                "tool_name": "apply_patch",
                "tool_input": {"command": "*** Begin Patch\n*** Update File: .codex/memory/topic.md\n@@\n-old\n+new\n*** End Patch"},
            }
            result = run([str(project_python), str(host / "hooks" / "hook_dispatcher.py"), "post-edit"], root, payload)
            self.assertEqual(result.returncode, 0, result.stderr)
            order = log.read_text(encoding="utf-8").splitlines()
            self.assertLess(order.index("encoding_check.py"), order.index("memory_rebuild_index.py"))
            self.assertLess(order.index("memory_rebuild_index.py"), order.index("memory_lint.py"))

            log.write_text("", encoding="utf-8")
            env = dict(os.environ)
            env.update(PYTHONUTF8="1", STUB_EXIT="7")
            failed = subprocess.run(
                [str(project_python), str(host / "hooks" / "hook_dispatcher.py"), "post-edit"],
                cwd=root,
                input=json.dumps(payload),
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
                check=False,
            )
            self.assertEqual(failed.returncode, 7)
            self.assertIn("memory_lint skipped", failed.stderr)
            self.assertNotIn("memory_lint.py", log.read_text(encoding="utf-8"))

    def test_pre_edit_decisions_are_serial_and_mixed_patch_is_not_auto_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            hooks = root / ".codex" / "hooks"
            hooks.mkdir(parents=True)
            shutil.copy2(TEMPLATE / "hooks" / "hook_dispatcher.py", hooks / "hook_dispatcher.py")
            project_python = prepare_dispatcher_runtime(root)
            log = root / "pre.log"
            ordinary = (
                "import os\n"
                f"open({str(log)!r}, 'a', encoding='utf-8').write(os.path.basename(__file__)+'\\n')\n"
            )
            for name in ("cross_project_write_guard.py", "user_config_write_guard.py", "memory_dup_check.py"):
                (hooks / name).write_text(ordinary, encoding="utf-8")
            (hooks / "memory_dup_check.py").write_text(ordinary + "print('[memory-dup] similar topic')\n", encoding="utf-8")
            (hooks / "allow_memory_write.py").write_text(
                ordinary + "print('{\"hookSpecificOutput\":{\"permissionDecision\":\"allow\"}}')\n",
                encoding="utf-8",
            )
            single = {"tool_name": "apply_patch", "tool_input": {"command": "*** Add File: .codex/memory/topic.md"}}
            allowed = run([str(project_python), str(hooks / "hook_dispatcher.py"), "pre-tool"], root, single)
            self.assertEqual(allowed.returncode, 0, allowed.stderr)
            self.assertEqual(
                log.read_text(encoding="utf-8").splitlines(),
                ["cross_project_write_guard.py", "user_config_write_guard.py", "memory_dup_check.py", "allow_memory_write.py"],
            )
            allowed_output = json.loads(allowed.stdout)
            specific = allowed_output["hookSpecificOutput"]
            self.assertEqual(specific["hookEventName"], "PreToolUse")
            self.assertEqual(specific["permissionDecision"], "allow")
            self.assertIn("[memory-dup]", specific["additionalContext"])
            self.assertEqual(allowed.stdout.count("hookSpecificOutput"), 1)

            log.write_text("", encoding="utf-8")
            mixed = {"tool_name": "apply_patch", "tool_input": {"command": "*** Add File: .codex/memory/topic.md\n*** Update File: .codex/hooks.json"}}
            default_boundary = run([str(project_python), str(hooks / "hook_dispatcher.py"), "pre-tool"], root, mixed)
            self.assertEqual(default_boundary.returncode, 0, default_boundary.stderr)
            self.assertNotIn("allow_memory_write.py", log.read_text(encoding="utf-8"))
            mixed_output = json.loads(default_boundary.stdout)
            self.assertNotIn("permissionDecision", mixed_output["hookSpecificOutput"])
            self.assertIn("additionalContext", mixed_output["hookSpecificOutput"])

    def test_move_to_is_checked_as_a_write_target(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            hooks = root / ".codex" / "hooks"
            scripts = root / ".codex" / "scripts"
            hooks.mkdir(parents=True)
            scripts.mkdir()
            for name in ("hook_dispatcher.py", "cross_project_write_guard.py", "user_config_write_guard.py"):
                shutil.copy2(TEMPLATE / "hooks" / name, hooks / name)
            project_python = prepare_dispatcher_runtime(root)
            for name in ("memory_dup_check.py", "allow_memory_write.py"):
                (hooks / name).write_text("raise SystemExit(0)\n", encoding="utf-8")

            outside = root.parent / "outside-move.md"
            payload = {
                "tool_name": "apply_patch",
                "tool_input": {"command": f"*** Update File: inside.md\n*** Move to: {outside}"},
            }
            blocked = run([str(project_python), str(hooks / "hook_dispatcher.py"), "pre-tool"], root, payload)
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("cross-project-write-guard", blocked.stderr)

            # Let the dedicated user-config guard observe the same normalized
            # Move target instead of being short-circuited by the broader guard.
            (hooks / "cross_project_write_guard.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
            user_config = Path.home() / ".codex" / "config.toml"
            user_payload = {
                "tool_name": "apply_patch",
                "tool_input": {"command": f"*** Update File: inside.md\n*** Move to: {user_config}"},
            }
            protected = run([str(project_python), str(hooks / "hook_dispatcher.py"), "pre-tool"], root, user_payload)
            self.assertEqual(protected.returncode, 2)
            self.assertIn("user-config-write-guard", protected.stderr)

            observed = root / "observed.txt"
            probe = (
                "import json,sys\n"
                f"open({str(observed)!r}, 'a', encoding='utf-8').write(json.load(sys.stdin)['tool_input']['file_path']+'\\n')\n"
            )
            for name in (
                "encoding_check.py", "mirror_drift_check.py", "instruction_source_check.py",
                "rule_index_check.py", "rule_size_check.py",
                "requirements_check.py", "cargo_default_run_check.py", "fallback_smell_check.py",
            ):
                (hooks / name).write_text(probe if name == "encoding_check.py" else "raise SystemExit(0)\n", encoding="utf-8")
            post = run([str(project_python), str(hooks / "hook_dispatcher.py"), "post-edit"], root, payload)
            self.assertEqual(post.returncode, 0, post.stderr)
            self.assertIn(str(outside), observed.read_text(encoding="utf-8").splitlines())

    def test_post_tool_stdout_is_one_additional_context_json(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            hooks = root / ".codex" / "hooks"
            scripts = root / ".codex" / "scripts"
            hooks.mkdir(parents=True)
            scripts.mkdir()
            shutil.copy2(TEMPLATE / "hooks" / "hook_dispatcher.py", hooks / "hook_dispatcher.py")
            project_python = prepare_dispatcher_runtime(root)
            for name in (
                "encoding_check.py", "mirror_drift_check.py", "instruction_source_check.py",
                "rule_index_check.py", "rule_size_check.py",
                "requirements_check.py", "cargo_default_run_check.py",
            ):
                (hooks / name).write_text("raise SystemExit(0)\n", encoding="utf-8")
            (hooks / "fallback_smell_check.py").write_text("print('[fallback-smell] soft warning')\n", encoding="utf-8")
            payload = {"tool_name": "apply_patch", "tool_input": {"command": "*** Update File: app.py"}}
            edited = run([str(project_python), str(hooks / "hook_dispatcher.py"), "post-edit"], root, payload)
            edit_output = json.loads(edited.stdout)
            self.assertEqual(edit_output["hookSpecificOutput"]["hookEventName"], "PostToolUse")
            self.assertIn("[fallback-smell]", edit_output["hookSpecificOutput"]["additionalContext"])
            self.assertEqual(edited.stdout.count("hookSpecificOutput"), 1)

            (hooks / "test_receipt.py").write_text("print('[test-receipt] recorded')\n", encoding="utf-8")
            shell = run(
                [str(project_python), str(hooks / "hook_dispatcher.py"), "post-shell"],
                root,
                {"tool_name": "Bash", "tool_input": {"command": "pytest"}},
            )
            shell_output = json.loads(shell.stdout)
            self.assertEqual(shell_output["hookSpecificOutput"]["hookEventName"], "PostToolUse")
            self.assertIn("[test-receipt]", shell_output["hookSpecificOutput"]["additionalContext"])
            self.assertEqual(shell.stdout.count("hookSpecificOutput"), 1)

    def test_session_start_is_best_effort_but_returns_first_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            hooks = root / ".codex" / "hooks"
            scripts = root / ".codex" / "scripts"
            hooks.mkdir(parents=True)
            scripts.mkdir()
            shutil.copy2(TEMPLATE / "hooks" / "hook_dispatcher.py", hooks / "hook_dispatcher.py")
            project_python = prepare_dispatcher_runtime(root)
            log = root / "session.log"
            stub = (
                "import os,sys\n"
                f"open({str(log)!r}, 'a', encoding='utf-8').write(os.path.basename(__file__)+'\\n')\n"
                "print('[session-step] '+os.path.basename(__file__))\n"
                "sys.exit(7 if os.path.basename(__file__) == 'memory_context.py' else 0)\n"
            )
            for name in (
                "config_health_check.py", "enforce_no_effortlevel.py",
                "githooks_path_check.py", "show_state.py", "skill_sync_check.py",
            ):
                (hooks / name).write_text(stub, encoding="utf-8")
            (scripts / "memory_rebuild_index.py").write_text(stub, encoding="utf-8")
            (scripts / "memory_context.py").write_text(stub, encoding="utf-8")
            result = run([str(project_python), str(hooks / "hook_dispatcher.py"), "session-start"], root, {})
            self.assertEqual(result.returncode, 7)
            order = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(order), 7)
            self.assertLess(order.index("memory_rebuild_index.py"), order.index("show_state.py"))
            output = json.loads(result.stdout)
            self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "SessionStart")
            self.assertIn("show_state.py", output["hookSpecificOutput"]["additionalContext"])

    def test_session_start_never_injects_stale_context_after_rebuild_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            hooks = root / ".codex" / "hooks"
            scripts = root / ".codex" / "scripts"
            hooks.mkdir(parents=True)
            scripts.mkdir()
            shutil.copy2(TEMPLATE / "hooks" / "hook_dispatcher.py", hooks / "hook_dispatcher.py")
            project_python = prepare_dispatcher_runtime(root)
            log = root / "session.log"
            stub = (
                "import os,sys\n"
                f"open({str(log)!r}, 'a', encoding='utf-8').write(os.path.basename(__file__)+'\\n')\n"
                "sys.exit(9 if os.path.basename(__file__) == 'memory_rebuild_index.py' else 0)\n"
            )
            for name in (
                "config_health_check.py", "enforce_no_effortlevel.py",
                "githooks_path_check.py", "show_state.py", "skill_sync_check.py",
            ):
                (hooks / name).write_text(stub, encoding="utf-8")
            (scripts / "memory_rebuild_index.py").write_text(stub, encoding="utf-8")
            (scripts / "memory_context.py").write_text(stub, encoding="utf-8")
            result = run([str(project_python), str(hooks / "hook_dispatcher.py"), "session-start"], root, {})
            self.assertEqual(result.returncode, 9)
            order = log.read_text(encoding="utf-8").splitlines()
            self.assertIn("memory_rebuild_index.py", order)
            self.assertNotIn("memory_context.py", order)
            self.assertIn("memory_context skipped", result.stderr)
            self.assertIn("show_state.py", order)

    def test_merge_preserves_third_party_and_never_changes_version_stamp(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            codex = root / ".codex"
            codex.mkdir()
            template = root / "template-hooks.json"
            template.write_text(json.dumps({"hooks": {"SessionStart": [{"hooks": [{"type": "command", "bridgeforgeCodexId": "bridgeforge-codex.project-hook.v1:session-start", "command": "python .codex/hooks/hook_dispatcher.py session-start"}]}]}}), encoding="utf-8")
            collision_commands = [
                "python vendor/show_state.py",
                "python .codex/hooks/vendor/show_state.py",
                "python show_state.py",
                "python tools/memory_rebuild_then_lint.py",
            ]
            legacy_junction = "python .codex/hooks/memory_junction_check.py"
            retired_memory_chain = [
                "python .codex/hooks/memory_rebuild_then_lint.py",
                "python .codex/scripts/memory_rebuild_then_lint.py",
                "python .codex/hooks/target_cleanup.py",
            ]
            (codex / "hooks.json").write_text(json.dumps({"custom": 1, "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "third-party-stop"}, {"type": "command", "command": legacy_junction}, *[{"type": "command", "command": item} for item in collision_commands], *[{"type": "command", "command": item} for item in retired_memory_chain]]}]}}), encoding="utf-8")
            (codex / "settings.json").write_text(json.dumps({"permissions": {"allow": ["Read"]}, "hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "third-party-prompt"}]}], "SessionStart": [{"hooks": [{"type": "command", "command": "python .codex/hooks/show_state.py session-start", "comment": "locally changed"}]}]}}), encoding="utf-8")
            stamp = codex / ".bridgeforge_codex_version"
            stamp.write_text("old\n", encoding="utf-8")
            script = TEMPLATE / "scripts" / "hooks_merge.py"
            base = [sys.executable, str(script), "--project-root", str(root), "--template-hooks", str(template)]
            refused = run(base + ["--apply"], root)
            self.assertEqual(refused.returncode, 2)
            self.assertEqual(stamp.read_text(encoding="utf-8"), "old\n")
            applied = run(base + ["--apply", "--confirmed"], root)
            self.assertEqual(applied.returncode, 0, applied.stderr)
            settings = json.loads((codex / "settings.json").read_text(encoding="utf-8"))
            hooks = json.loads((codex / "hooks.json").read_text(encoding="utf-8"))
            self.assertNotIn("hooks", settings)
            serialized = json.dumps(hooks, ensure_ascii=False)
            self.assertIn("third-party-stop", serialized)
            self.assertIn("third-party-prompt", serialized)
            self.assertIn("hook_dispatcher.py", serialized)
            for command in collision_commands:
                self.assertIn(command, serialized)
            self.assertIn(legacy_junction, serialized)
            for command in retired_memory_chain:
                self.assertIn(command, serialized)
            self.assertIn("locally changed", serialized)
            self.assertEqual(hooks["custom"], 1)
            self.assertEqual(stamp.read_text(encoding="utf-8"), "old\n")

    def test_merge_rejects_duplicate_json_keys_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            codex = root / ".codex"
            codex.mkdir()
            hooks = codex / "hooks.json"
            settings = codex / "settings.json"
            stamp = codex / ".bridgeforge_codex_version"
            hooks.write_text(
                '{"hooks": {}, "hooks": {"Stop": []}}\n',
                encoding="utf-8",
            )
            settings.write_text('{"permissions": {}}\n', encoding="utf-8")
            stamp.write_text("old\n", encoding="utf-8")
            before = {
                path: path.read_bytes()
                for path in (hooks, settings, stamp)
            }

            result = run(
                [
                    sys.executable,
                    str(TEMPLATE / "scripts" / "hooks_merge.py"),
                    "--project-root",
                    str(root),
                    "--template-hooks",
                    str(TEMPLATE / "hooks.json"),
                    "--apply",
                    "--confirmed",
                ],
                root,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("duplicate JSON key: hooks", result.stderr)
            self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_merge_initializes_new_project_from_template(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            codex = root / ".codex"
            codex.mkdir()
            shutil.copy2(TEMPLATE / "settings.json", codex / "settings.json")
            result = run([
                sys.executable, str(TEMPLATE / "scripts" / "hooks_merge.py"),
                "--project-root", str(root),
                "--template-hooks", str(TEMPLATE / "hooks.json"),
                "--apply", "--confirmed",
            ], root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("hooks", json.loads((codex / "settings.json").read_text(encoding="utf-8")))
            self.assertIsInstance(json.loads((codex / "hooks.json").read_text(encoding="utf-8"))["hooks"], dict)
            self.assertFalse((codex / ".bridgeforge_codex_version").exists())

    def test_merge_rejects_retired_stamp_version_option_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            codex = root / ".codex"
            codex.mkdir()
            template = root / "template.json"
            template.write_text('{"hooks": {}}\n', encoding="utf-8")
            result = run(
                [
                    sys.executable,
                    str(TEMPLATE / "scripts" / "hooks_merge.py"),
                    "--project-root",
                    str(root),
                    "--template-hooks",
                    str(template),
                    "--stamp-version",
                    "new",
                ],
                root,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("unrecognized arguments: --stamp-version new", result.stderr)
            self.assertEqual(list(codex.iterdir()), [])

    def test_config_hooks_conflict_keeps_files_and_old_stamp(self) -> None:
        forms = (
            "[hooks]\n",
            '["hooks"]\n',
            "['hooks']\n",
            '["ho\\u006fks"]\n',
            "[[hooks.PreToolUse]]\n",
            '[["hooks".PreToolUse]]\n',
            '[["hooks".PreToolUse.hooks]]\n',
            " [[ hooks . PreToolUse . hooks ]] # inline\n",
            "hooks.PreToolUse = []\n",
            "hooks = { PreToolUse = [] }\n",
        )
        for form in forms:
            with self.subTest(form=form), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                codex = root / ".codex"
                codex.mkdir()
                hooks = codex / "hooks.json"
                settings = codex / "settings.json"
                stamp = codex / ".bridgeforge_codex_version"
                template = root / "template.json"
                hooks.write_text('{"hooks": {}}\n', encoding="utf-8")
                settings.write_text('{"permissions": {}}\n', encoding="utf-8")
                stamp.write_text("old\n", encoding="utf-8")
                template.write_text('{"hooks": {}}\n', encoding="utf-8")
                (codex / "config.toml").write_text(form, encoding="utf-8")
                before = (hooks.read_bytes(), settings.read_bytes(), stamp.read_bytes())
                result = run([
                    sys.executable, str(TEMPLATE / "scripts" / "hooks_merge.py"),
                    "--project-root", str(root), "--template-hooks", str(template),
                    "--apply", "--confirmed",
                ], root)
                self.assertEqual(result.returncode, 2)
                self.assertIn("forbidden hooks table", result.stderr)
                self.assertEqual(before, (hooks.read_bytes(), settings.read_bytes(), stamp.read_bytes()))

    def test_strict_health_gate_rejects_both_illegal_sources(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            codex = root / ".codex"
            (codex / "hooks").mkdir(parents=True)
            (codex / "scripts").mkdir()
            shutil.copy2(TEMPLATE / "hooks" / "config_health_check.py", codex / "hooks" / "config_health_check.py")
            shutil.copy2(TEMPLATE / "scripts" / "hook_config_policy.py", codex / "scripts" / "hook_config_policy.py")
            shutil.copy2(TEMPLATE / "scripts" / "project_runtime.py", codex / "scripts" / "project_runtime.py")
            (codex / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
            (codex / "settings.json").write_text('{"hooks": {}}\n', encoding="utf-8")
            (codex / "config.toml").write_text("[hooks]\n", encoding="utf-8")
            project_python = prepare_project_runtime(root)
            result = run([str(project_python), str(codex / "hooks" / "config_health_check.py"), "--strict"], root)
            self.assertEqual(result.returncode, 2)
            self.assertIn("settings.json contains hooks", result.stdout)
            self.assertIn("config.toml contains a hooks table", result.stdout)

    def test_strict_health_gate_rejects_non_project_python(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            codex = root / ".codex"
            (codex / "hooks").mkdir(parents=True)
            (codex / "scripts").mkdir()
            shutil.copy2(
                TEMPLATE / "hooks" / "config_health_check.py",
                codex / "hooks" / "config_health_check.py",
            )
            shutil.copy2(
                TEMPLATE / "hooks" / "memory_lint.py",
                codex / "hooks" / "memory_lint.py",
            )
            shutil.copy2(
                TEMPLATE / "scripts" / "hook_config_policy.py",
                codex / "scripts" / "hook_config_policy.py",
            )
            shutil.copy2(
                TEMPLATE / "scripts" / "project_runtime.py",
                codex / "scripts" / "project_runtime.py",
            )
            (codex / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
            (codex / "settings.json").write_text(
                '{"permissions": {}}\n',
                encoding="utf-8",
            )

            result = run(
                [
                    sys.executable,
                    str(codex / "hooks" / "config_health_check.py"),
                    "--strict",
                ],
                root,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("PROJECT_RUNTIME: project .venv is missing", result.stdout)

    def test_strict_health_gate_matches_merge_for_inline_toml_forms(self) -> None:
        forms = (
            "[hooks]\n",
            '["hooks"]\n',
            "['hooks']\n",
            '["ho\\u006fks"]\n',
            "[[hooks.PreToolUse]]\n",
            '[["hooks".PreToolUse]]\n',
            '[["hooks".PreToolUse.hooks]]\n',
            " [[ hooks . PreToolUse . hooks ]] # inline\n",
            "hooks.PreToolUse = []\n",
            "hooks = { PreToolUse = [] }\n",
        )
        for form in forms:
            with self.subTest(form=form), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                codex = root / ".codex"
                (codex / "hooks").mkdir(parents=True)
                (codex / "scripts").mkdir()
                shutil.copy2(TEMPLATE / "hooks" / "config_health_check.py", codex / "hooks" / "config_health_check.py")
                shutil.copy2(TEMPLATE / "scripts" / "hook_config_policy.py", codex / "scripts" / "hook_config_policy.py")
                shutil.copy2(TEMPLATE / "scripts" / "project_runtime.py", codex / "scripts" / "project_runtime.py")
                (codex / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
                (codex / "settings.json").write_text('{"permissions": {}}\n', encoding="utf-8")
                (codex / "config.toml").write_text(form, encoding="utf-8")
                project_python = prepare_project_runtime(root)
                result = run([str(project_python), str(codex / "hooks" / "config_health_check.py"), "--strict"], root)
                self.assertEqual(result.returncode, 2)
                self.assertIn("config.toml contains a hooks table", result.stdout)

    def test_quoted_non_hooks_tables_are_allowed_by_merge_and_health(self) -> None:
        forms = (
            '["not-hooks"]\n',
            "[['not-hooks'.PreToolUse]]\n",
            '[["event".PreToolUse.hooks]]\n',
            "matrix = [\n  [1, 2],\n  [3, 4],\n]\n[database]\nports = [8000, 8001]\n",
        )
        for form in forms:
            with self.subTest(form=form), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                codex = root / ".codex"
                (codex / "hooks").mkdir(parents=True)
                (codex / "scripts").mkdir()
                shutil.copy2(
                    TEMPLATE / "hooks" / "config_health_check.py",
                    codex / "hooks" / "config_health_check.py",
                )
                shutil.copy2(
                    TEMPLATE / "hooks" / "memory_lint.py",
                    codex / "hooks" / "memory_lint.py",
                )
                shutil.copy2(
                    TEMPLATE / "scripts" / "hook_config_policy.py",
                    codex / "scripts" / "hook_config_policy.py",
                )
                shutil.copy2(
                    TEMPLATE / "scripts" / "project_runtime.py",
                    codex / "scripts" / "project_runtime.py",
                )
                (codex / "settings.json").write_text('{"permissions": {}}\n', encoding="utf-8")
                (codex / "config.toml").write_text(form, encoding="utf-8")
                project_python = prepare_project_runtime(root)
                template = TEMPLATE / "hooks.json"
                merged = run([
                    sys.executable, str(TEMPLATE / "scripts" / "hooks_merge.py"),
                    "--project-root", str(root), "--template-hooks", str(template),
                    "--apply", "--confirmed",
                ], root)
                self.assertEqual(merged.returncode, 0, merged.stderr)
                self.assertFalse((codex / ".bridgeforge_codex_version").exists())
                health = run([
                    str(project_python),
                    str(codex / "hooks" / "config_health_check.py"),
                    "--strict",
                ], root)
                self.assertEqual(health.returncode, 0, health.stdout + health.stderr)

    def test_malformed_toml_header_fails_closed_in_merge_and_health(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            codex = root / ".codex"
            (codex / "hooks").mkdir(parents=True)
            (codex / "scripts").mkdir()
            shutil.copy2(
                TEMPLATE / "hooks" / "config_health_check.py",
                codex / "hooks" / "config_health_check.py",
            )
            shutil.copy2(
                TEMPLATE / "scripts" / "hook_config_policy.py",
                codex / "scripts" / "hook_config_policy.py",
            )
            shutil.copy2(
                TEMPLATE / "scripts" / "project_runtime.py",
                codex / "scripts" / "project_runtime.py",
            )
            (codex / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
            (codex / "settings.json").write_text('{"permissions": {}}\n', encoding="utf-8")
            (codex / "config.toml").write_text('["hooks\\q"]\n', encoding="utf-8")
            stamp = codex / ".bridgeforge_codex_version"
            stamp.write_text("old\n", encoding="utf-8")
            template = root / "template.json"
            template.write_text('{"hooks": {}}\n', encoding="utf-8")
            project_python = prepare_project_runtime(root)

            merged = run([
                sys.executable, str(TEMPLATE / "scripts" / "hooks_merge.py"),
                "--project-root", str(root), "--template-hooks", str(template),
                "--apply", "--confirmed",
            ], root)
            self.assertEqual(merged.returncode, 2)
            self.assertIn("invalid table header", merged.stderr)
            self.assertEqual(stamp.read_text(encoding="utf-8"), "old\n")

            health = run([
                str(project_python),
                str(codex / "hooks" / "config_health_check.py"),
                "--strict",
            ], root)
            self.assertEqual(health.returncode, 2)
            self.assertIn("table header invalid", health.stdout)

    def test_python_310_merge_dispatcher_and_health_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            codex = root / ".codex"
            (codex / "hooks").mkdir(parents=True)
            (codex / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
            (codex / "settings.json").write_text('{"permissions": {}}\n', encoding="utf-8")
            stamp = codex / ".bridgeforge_codex_version"
            stamp.write_text("old\n", encoding="utf-8")
            template = root / "template.json"
            template.write_text('{"hooks": {}}\n', encoding="utf-8")
            before = {
                path: path.read_bytes()
                for path in (codex / "hooks.json", codex / "settings.json", stamp)
            }

            merge = load_module(
                TEMPLATE / "scripts" / "hooks_merge.py",
                "hooks_merge_python_310",
            )
            merge_stderr = io.StringIO()
            with redirect_stderr(merge_stderr):
                merge_rc = merge.main([
                "--project-root", str(root), "--template-hooks", str(template),
                "--apply", "--confirmed",
                ], (3, 10))
            self.assertEqual(merge_rc, 2)
            self.assertIn("Python 3.11", merge_stderr.getvalue())
            self.assertEqual(
                before,
                {path: path.read_bytes() for path in before},
            )

            dispatcher = load_module(
                TEMPLATE / "hooks" / "hook_dispatcher.py",
                "hook_dispatcher_python_310",
            )
            dispatcher_stderr = io.StringIO()
            with redirect_stderr(dispatcher_stderr):
                dispatcher_rc = dispatcher.main((3, 10))
            self.assertEqual(dispatcher_rc, 2)
            self.assertIn("Python 3.11", dispatcher_stderr.getvalue())

            health = load_module(
                TEMPLATE / "hooks" / "config_health_check.py",
                "config_health_python_310",
            )
            health_stdout = io.StringIO()
            with redirect_stdout(health_stdout):
                health_rc = health.main((3, 10), strict=True)
            self.assertEqual(health_rc, 2)
            self.assertIn("PYTHON_VERSION: 3.10", health_stdout.getvalue())

if __name__ == "__main__":
    unittest.main()
