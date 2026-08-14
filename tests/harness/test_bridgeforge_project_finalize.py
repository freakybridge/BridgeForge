from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
FINALIZER = ROOT / "scripts/bridgeforge_project_finalize.py"
SPEC = importlib.util.spec_from_file_location("bridgeforge_project_finalize", FINALIZER)
assert SPEC is not None and SPEC.loader is not None
finalizer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(finalizer)


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["USERPROFILE"] = str(cwd)
    environment["HOME"] = str(cwd)
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        check=False,
    )


class BridgeForgeProjectFinalizeTests(unittest.TestCase):
    def test_atomic_write_stages_in_project_root_for_both_hosts(self) -> None:
        real_mkstemp = tempfile.mkstemp
        for host in ("codex", "claude"):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                host_dir = root / f".{host}"
                host_dir.mkdir()
                stamp = host_dir / ".bridgeforge_version"

                def guarded_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
                    directory = Path(str(kwargs["dir"])).resolve()
                    if directory == host_dir.resolve():
                        raise PermissionError("protected host directory")
                    return real_mkstemp(*args, **kwargs)

                with mock.patch.object(
                    finalizer.tempfile,
                    "mkstemp",
                    side_effect=guarded_mkstemp,
                ) as mkstemp:
                    finalizer._atomic_write(
                        stamp,
                        "0.86.2\n",
                        staging_dir=root,
                    )
                self.assertEqual(
                    Path(mkstemp.call_args.kwargs["dir"]).resolve(),
                    root.resolve(),
                )
                self.assertEqual(stamp.read_text(encoding="utf-8"), "0.86.2\n")
                self.assertEqual(list(root.glob(".bridgeforge_version.*")), [])

    def test_atomic_write_cleans_root_staging_file_after_replace_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            host_dir = root / ".codex"
            host_dir.mkdir()
            stamp = host_dir / ".bridgeforge_version"
            with mock.patch.object(
                finalizer.os,
                "replace",
                side_effect=PermissionError("protected target"),
            ):
                with self.assertRaises(PermissionError):
                    finalizer._atomic_write(
                        stamp,
                        "0.86.2\n",
                        staging_dir=root,
                    )
            self.assertFalse(stamp.exists())
            self.assertEqual(list(root.glob(".bridgeforge_version.*")), [])

    def _project(self, root: Path, host: str, *, valid_memory: bool = True) -> Path:
        host_dir = root / f".{host}"
        hooks = host_dir / "hooks"
        memory = host_dir / "memory"
        hooks.mkdir(parents=True)
        memory.mkdir()
        for name in ("memory_lint.py", "config_health_check.py"):
            shutil.copy2(ROOT / f"templates/{host}/hooks/{name}", hooks / name)
        if host == "codex":
            scripts = host_dir / "scripts"
            scripts.mkdir()
            shutil.copy2(
                ROOT / "templates/codex/scripts/hook_config_policy.py",
                scripts / "hook_config_policy.py",
            )
            (host_dir / "hooks.json").write_text('{"hooks": {}}\n', encoding="utf-8")
        (host_dir / "settings.json").write_text("{}\n", encoding="utf-8")
        description = "description: valid fixture\n" if valid_memory else ""
        (memory / "domain").mkdir()
        (memory / "domain/example.md").write_text(
            "---\ncategory: domain\nstatus: active\n"
            + description
            + "---\nbody\n",
            encoding="utf-8",
        )
        stamp = host_dir / ".bridgeforge_version"
        stamp.write_text("0.86.1\n", encoding="utf-8")
        return stamp

    def _command(self, root: Path, host: str, *extra: str) -> list[str]:
        return [
            sys.executable,
            str(FINALIZER),
            "--project-root",
            str(root),
            "--template-root",
            str(ROOT),
            "--host",
            host,
            "--version",
            "0.86.2",
            *extra,
        ]

    def test_clean_project_is_stamped_only_after_both_gates_pass(self) -> None:
        for host in ("codex", "claude"):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                stamp = self._project(root, host)
                result = run(self._command(root, host, "--confirmed"), root)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(stamp.read_text(encoding="utf-8"), "0.86.2\n")
                self.assertIn("memory_schema=clean config_health=clean", result.stdout)

    def test_invalid_memory_keeps_old_stamp_for_both_hosts(self) -> None:
        for host in ("codex", "claude"):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as raw:
                root = Path(raw)
                stamp = self._project(root, host, valid_memory=False)
                result = run(self._command(root, host, "--confirmed"), root)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(stamp.read_text(encoding="utf-8"), "0.86.1\n")
                self.assertIn("memory schema audit failed", result.stderr)
                self.assertIn("version stamp was not changed", result.stderr)

    def test_missing_confirmation_keeps_old_stamp(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            stamp = self._project(root, "codex")
            result = run(self._command(root, "codex"), root)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(stamp.read_text(encoding="utf-8"), "0.86.1\n")
            self.assertIn("requires --confirmed", result.stderr)

    def test_config_health_failure_keeps_old_stamp(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            stamp = self._project(root, "codex")
            settings = root / ".codex/settings.json"
            settings.write_text(json.dumps({"hooks": {}}), encoding="utf-8")
            result = run(self._command(root, "codex", "--confirmed"), root)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(stamp.read_text(encoding="utf-8"), "0.86.1\n")
            self.assertIn("config health check failed", result.stderr)
            self.assertIn("not single-source", result.stdout)


if __name__ == "__main__":
    unittest.main()
