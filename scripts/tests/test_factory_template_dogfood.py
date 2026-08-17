from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "templates" / "hooks" / "mirror_drift_check.py"
FACTORY_SENTINEL = "受管资产必须使用显式 target"


class FactoryTemplateDogfoodTest(unittest.TestCase):
    def _factory(self, root: Path) -> Path:
        (root / "templates" / "hooks").mkdir(parents=True)
        (root / ".codex" / "hooks").mkdir(parents=True)
        shutil.copy2(ROOT / "templates" / "AGENTS.md", root / "templates" / "AGENTS.md")
        shutil.copy2(ROOT / "AGENTS.md", root / "AGENTS.md")
        shutil.copy2(HOOK, root / "templates" / "hooks" / HOOK.name)
        shutil.copy2(HOOK, root / ".codex" / "hooks" / HOOK.name)
        return root / ".codex" / "hooks" / HOOK.name

    def _run(self, hook: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        return subprocess.run(
            [sys.executable, str(hook), *args],
            cwd=hook.parents[2],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )

    def test_current_factory_common_baseline_is_exact(self) -> None:
        result = self._run(HOOK, "--pre-commit")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_markdown_rule_reintroduction_blocks_precommit(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            hook = self._factory(root)
            target = root / ".codex" / "rules" / "local.md"
            target.parent.mkdir(parents=True)
            target.write_text("---\npaths: ['src/**']\n---\n", encoding="utf-8")
            post_edit = self._run(hook, "--post-edit")
            self.assertEqual(post_edit.returncode, 0, post_edit.stderr)
            self.assertIn("must remain retired", post_edit.stderr)
            precommit = self._run(hook, "--pre-commit")
            self.assertEqual(precommit.returncode, 2, precommit.stderr)
            self.assertIn(".codex", precommit.stderr)

    def test_agents_common_drift_blocks_but_project_slots_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            hook = self._factory(root)
            agents = root / "AGENTS.md"
            text = agents.read_text(encoding="utf-8")
            agents.write_text(text.replace("默认先给结论", "默认最后给结论", 1), encoding="utf-8")
            blocked = self._run(hook, "--pre-commit")
            self.assertEqual(blocked.returncode, 2, blocked.stderr)
            self.assertIn("AGENTS common regions drift", blocked.stderr)

            agents.write_text(text.replace("bridgeforge-codex 同时是", "本工厂同时是", 1), encoding="utf-8")
            allowed = self._run(hook, "--pre-commit")
            self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_factory_release_redline_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            hook = self._factory(root)
            agents = root / "AGENTS.md"
            agents.write_text(
                agents.read_text(encoding="utf-8").replace(FACTORY_SENTINEL, "removed", 1),
                encoding="utf-8",
            )
            result = self._run(hook, "--pre-commit")
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("missing required release redlines", result.stderr)

    def test_review_and_architecture_redlines_are_preserved(self) -> None:
        required = (
            "按严重度排序",
            "文件 / 行号 / 行为风险",
            "取舍理由、主要风险与触发条件",
            "禁止只罗列选项不拍板",
        )
        for path in (ROOT / "templates" / "AGENTS.md", ROOT / "AGENTS.md"):
            text = path.read_text(encoding="utf-8")
            for marker in required:
                self.assertIn(marker, text, f"{path}: missing {marker}")

    def test_mirror_hook_is_byte_identical(self) -> None:
        self.assertEqual(
            HOOK.read_bytes(),
            (ROOT / ".codex" / "hooks" / HOOK.name).read_bytes(),
        )

    def test_plain_downstream_without_template_hooks_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            hook = root / ".codex" / "hooks" / HOOK.name
            hook.parent.mkdir(parents=True)
            shutil.copy2(HOOK, hook)
            result = self._run(hook, "--pre-commit")
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
