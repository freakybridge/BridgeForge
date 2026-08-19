from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "templates" / "scripts" / "project_runtime.py"
PROJECT_SYNC = ROOT / "scripts" / "bridgeforge_codex_project_sync.py"
SPEC = importlib.util.spec_from_file_location("project_runtime_under_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
runtime = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runtime
SPEC.loader.exec_module(runtime)


class ProjectRuntimeTests(unittest.TestCase):
    def make_project(self) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        return Path(temporary.name)

    def test_expected_python_is_lexically_inside_project(self) -> None:
        project = self.make_project()
        expected = runtime.expected_project_python(project)
        expected.relative_to(project.resolve())
        self.assertEqual(expected.parents[1], project.resolve() / ".venv")
        self.assertEqual(
            expected.name,
            "python.exe" if os.name == "nt" else "python",
        )

    def test_validate_rejects_missing_and_wrong_project_runtime(self) -> None:
        project = self.make_project()
        with self.assertRaisesRegex(runtime.ProjectRuntimeError, r"\.venv is missing"):
            runtime.validate_project_runtime(project, executable=sys.executable)

        (project / ".venv").mkdir()
        with self.assertRaisesRegex(
            runtime.ProjectRuntimeError,
            "Python is missing or unsafe",
        ):
            runtime.validate_project_runtime(project, executable=sys.executable)

    def test_bootstrap_creates_then_validates_single_project_runtime(self) -> None:
        project = self.make_project()
        created = runtime.bootstrap_project_venv(
            project,
            "init",
            bootstrap_executable=sys.executable,
        )
        expected = runtime.expected_project_python(project).resolve()
        self.assertEqual(created.project_root, project.resolve())
        self.assertEqual(created.python_executable, expected)
        self.assertEqual(created.implementation, "CPython")
        self.assertGreaterEqual(created.version[:2], runtime.MIN_PYTHON)
        self.assertEqual(
            runtime.validate_project_runtime(project, executable=expected),
            created,
        )

        valid_probe = runtime._probe_python(expected)
        for accepted in ([3, 11, 9], [3, 12, 9], [3, 12, 13]):
            with self.subTest(accepted=accepted):
                self.assertEqual(
                    runtime._probe_identity(
                        {
                            **valid_probe,
                            "implementation": "CPython",
                            "version": accepted,
                        }
                    ),
                    ("CPython", tuple(accepted)),
                )
        for implementation, version, message in (
            ("PyPy", [3, 11, 9], "must be CPython"),
            ("CPython", [3, 10, 14], "requires CPython 3.11"),
        ):
            with self.subTest(implementation=implementation, version=version):
                payload = {
                    **valid_probe,
                    "implementation": implementation,
                    "version": version,
                }
                with mock.patch.object(runtime, "_probe_python", return_value=payload):
                    with self.assertRaisesRegex(runtime.ProjectRuntimeError, message):
                        runtime.validate_project_runtime(project, executable=expected)

    def test_git_sync_entry_rejects_non_project_runtime_before_git(self) -> None:
        script_dir = ROOT / "templates" / "scripts"
        sys.path.insert(0, str(script_dir))
        try:
            spec = importlib.util.spec_from_file_location(
                "codex_git_sync_runtime_contract",
                script_dir / "codex_git_sync.py",
            )
            assert spec is not None and spec.loader is not None
            git_sync = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = git_sync
            spec.loader.exec_module(git_sync)
        finally:
            sys.path.pop(0)
        stderr = io.StringIO()
        with mock.patch.object(
            git_sync,
            "validate_project_runtime",
            side_effect=git_sync.ProjectRuntimeError("foreign interpreter"),
        ), mock.patch.object(git_sync, "sync") as run_sync, redirect_stderr(stderr):
            result = git_sync.main()
        self.assertEqual(result, 2)
        self.assertIn("project runtime contract rejected", stderr.getvalue())
        run_sync.assert_not_called()

    def test_bootstrap_rejects_update_and_any_existing_venv(self) -> None:
        project = self.make_project()
        with self.assertRaisesRegex(runtime.ProjectRuntimeError, "only for init or adopt"):
            runtime.bootstrap_project_venv(project, "update")
        self.assertFalse(os.path.lexists(project / ".venv"))

        for implementation, version, message in (
            ("CPython", [3, 10, 14], "requires CPython 3.11"),
            ("PyPy", [3, 11, 9], "must be CPython"),
        ):
            with self.subTest(implementation=implementation, version=version):
                with mock.patch.object(
                    runtime,
                    "_probe_python",
                    return_value={
                        "implementation": implementation,
                        "version": version,
                    },
                ):
                    with self.assertRaisesRegex(
                        runtime.ProjectRuntimeError,
                        message,
                    ):
                        runtime.bootstrap_project_venv(project, "init")
                self.assertFalse(os.path.lexists(project / ".venv"))

        venv = project / ".venv"
        venv.mkdir()
        sentinel = venv / "sentinel.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")
        with self.assertRaisesRegex(runtime.ProjectRuntimeError, "already exists"):
            runtime.bootstrap_project_venv(project, "adopt")
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve\n")

    def test_bootstrap_failure_removes_only_the_new_partial_venv(self) -> None:
        project = self.make_project()
        probe_payload = {
            "implementation": "CPython",
            "version": list(sys.version_info[:3]),
            "executable": sys.executable,
            "prefix": sys.prefix,
        }

        def run_side_effect(command: list[str], **_kwargs: object):
            if "-c" in command:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    json.dumps(probe_payload),
                    "",
                )
            (project / ".venv" / "partial.txt").write_text(
                "partial\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 7, "", "creation failed")

        with mock.patch.object(runtime.subprocess, "run", side_effect=run_side_effect):
            with self.assertRaisesRegex(runtime.ProjectRuntimeError, "exited 7"):
                runtime.bootstrap_project_venv(project, "init", sys.executable)
        self.assertFalse(os.path.lexists(project / ".venv"))

    def test_validate_rejects_venv_path_escape(self) -> None:
        project = self.make_project()
        external = self.make_project()
        try:
            os.symlink(external, project / ".venv", target_is_directory=True)
        except OSError as exc:
            if os.name != "nt":
                self.skipTest(f"directory symlink unavailable: {exc}")
            junction = subprocess.run(
                [
                    "cmd.exe",
                    "/d",
                    "/c",
                    "mklink",
                    "/J",
                    str(project / ".venv"),
                    str(external),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            if junction.returncode != 0:
                self.skipTest(
                    f"directory symlink and junction unavailable: {junction.stderr}"
                )
        with self.assertRaisesRegex(runtime.ProjectRuntimeError, "not a plain directory"):
            runtime.validate_project_runtime(project, executable=sys.executable)

    def test_cli_emits_stable_validate_and_blocked_receipts(self) -> None:
        project = self.make_project()
        created = runtime.bootstrap_project_venv(project, "adopt", sys.executable)
        output = io.StringIO()
        with redirect_stdout(output):
            result = runtime.main(
                [
                    "validate",
                    "--project-root",
                    str(project),
                    "--executable",
                    str(created.python_executable),
                ]
            )
        self.assertEqual(result, 0, output.getvalue())
        receipt = json.loads(output.getvalue())
        self.assertEqual(receipt["action"], "validate")
        self.assertEqual(receipt["status"], "valid")
        self.assertEqual(receipt["minimum_python"], "3.11")
        self.assertEqual(receipt["project_root"], str(project.resolve()))

        missing = self.make_project()
        output = io.StringIO()
        with redirect_stdout(output):
            result = runtime.main(
                ["validate", "--project-root", str(missing)]
            )
        self.assertEqual(result, 2)
        blocked = json.loads(output.getvalue())
        self.assertEqual(blocked["action"], "validate")
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn(".venv is missing", blocked["error"])

    def test_project_sync_cli_requires_target_project_runtime(self) -> None:
        project = self.make_project()
        command = [
            str(PROJECT_SYNC),
            "--project-root",
            str(project),
            "--template-root",
            str(ROOT),
            "--mode",
            "init",
        ]
        blocked = subprocess.run(
            [sys.executable, *command],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("project runtime contract rejected", blocked.stderr)
        self.assertEqual(list(project.iterdir()), [])

        created = runtime.bootstrap_project_venv(project, "init", sys.executable)
        planned = subprocess.run(
            [str(created.python_executable), *command],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertNotIn(
            "project runtime contract rejected",
            planned.stdout + planned.stderr,
        )
        receipt = json.loads(planned.stdout)
        if planned.returncode == 0:
            self.assertEqual(receipt["execution_status"], "planned")
            self.assertEqual(receipt["mode"], "init")
        else:
            self.assertNotIn("current Python is not", receipt.get("error", ""))


if __name__ == "__main__":
    unittest.main()
