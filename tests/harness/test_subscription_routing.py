#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "templates" / "codex" / "scripts" / "subscription_routing.py"
RUNTIME = ROOT / ".runtime" / "harness"

SPEC = importlib.util.spec_from_file_location("subscription_routing_under_test", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
ROUTING = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROUTING)


class SubscriptionRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        RUNTIME.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=RUNTIME)
        self.base = Path(self.temp.name)
        self.template = self.base / "template"
        (self.template / "agents").mkdir(parents=True)
        (self.template / "config.toml").write_text(
            'model = "gpt-5.6-terra"\n'
            'model_reasoning_effort = "high"\n\n'
            "[agents]\n"
            "max_threads = 6\n",
            encoding="utf-8",
        )
        (self.template / "agents" / "implementation-worker.toml").write_text(
            'name = "implementation-worker"\n'
            'description = "fixture"\n'
            'model = "gpt-5.6-sol"\n'
            'model_reasoning_effort = "high"\n',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_resolved_codex_symlink_or_junction_cannot_reach_user_codex(self) -> None:
        fake_home = self.base / "fake-home"
        user_codex = fake_home / ".codex"
        user_codex.mkdir(parents=True)
        project = self.base / "project"
        project.mkdir()
        project_codex = project / ".codex"

        with mock.patch.object(ROUTING.Path, "home", return_value=fake_home):
            try:
                os.symlink(user_codex, project_codex, target_is_directory=True)
            except OSError:
                real_resolve = ROUTING._resolve_real
                project_codex_lexical = ROUTING._lexical(project_codex)

                def resolve_as_user_codex(value: Path) -> Path:
                    lexical = ROUTING._lexical(value)
                    try:
                        relative = lexical.relative_to(project_codex_lexical)
                    except ValueError:
                        return real_resolve(value)
                    return user_codex / relative

                with mock.patch.object(
                    ROUTING,
                    "_resolve_real",
                    side_effect=resolve_as_user_codex,
                ):
                    with self.assertRaisesRegex(ValueError, "user-level Codex target"):
                        ROUTING._validate_layout(project, self.template)
            else:
                with self.assertRaisesRegex(ValueError, "user-level Codex target"):
                    ROUTING._validate_layout(project, self.template)

    def test_failed_second_replace_rolls_back_all_three_files(self) -> None:
        project = self.base / "project"
        codex = project / ".codex"
        agents = codex / "agents"
        agents.mkdir(parents=True)
        config = codex / "config.toml"
        implementation = agents / "implementation-worker.toml"
        marker = codex / "subscription-tier.toml"
        config.write_text(
            'model = "original-main"\nmodel_reasoning_effort = "medium"\n',
            encoding="utf-8",
        )
        implementation.write_text(
            'name = "implementation-worker"\n'
            'model = "original-implementation"\n'
            'model_reasoning_effort = "high"\n',
            encoding="utf-8",
        )
        marker.write_text(
            'schema_version = "1"\ntier = "conservative"\n',
            encoding="utf-8",
        )
        originals = {
            path: path.read_bytes()
            for path in (config, implementation, marker)
        }

        real_replace = ROUTING._replace_file
        injected = False

        def fail_implementation_once(source: Path, target: Path) -> None:
            nonlocal injected
            if (
                not injected
                and "bridgeforge-new" in source.name
                and target.name == "implementation-worker.toml"
            ):
                injected = True
                raise OSError("injected implementation replace failure")
            real_replace(source, target)

        with mock.patch.object(
            ROUTING,
            "_replace_file",
            side_effect=fail_implementation_once,
        ):
            with self.assertRaisesRegex(OSError, "injected implementation replace failure"):
                ROUTING.apply_tier(project, self.template, "high")

        self.assertTrue(injected)
        for path, original in originals.items():
            self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(project.rglob("*.bridgeforge-*.tmp")), [])

    def test_failed_marker_replace_removes_new_config_and_agent(self) -> None:
        project = self.base / "new-project"
        project.mkdir()
        real_replace = ROUTING._replace_file
        injected = False

        def fail_marker_once(source: Path, target: Path) -> None:
            nonlocal injected
            if (
                not injected
                and "bridgeforge-new" in source.name
                and target.name == "subscription-tier.toml"
            ):
                injected = True
                raise OSError("injected marker replace failure")
            real_replace(source, target)

        with mock.patch.object(
            ROUTING,
            "_replace_file",
            side_effect=fail_marker_once,
        ):
            with self.assertRaisesRegex(OSError, "injected marker replace failure"):
                ROUTING.apply_tier(project, self.template, "conservative")

        self.assertTrue(injected)
        self.assertFalse((project / ".codex" / "config.toml").exists())
        self.assertFalse(
            (project / ".codex" / "agents" / "implementation-worker.toml").exists()
        )
        self.assertFalse((project / ".codex" / "subscription-tier.toml").exists())
        self.assertEqual(list(project.rglob("*.bridgeforge-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
