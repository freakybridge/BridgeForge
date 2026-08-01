from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class MemoryLifecycleGovernanceTests(unittest.TestCase):
    def test_claude_and_codex_memory_contracts_are_equivalent(self) -> None:
        codex = (ROOT / "templates/codex/AGENTS.md").read_text(encoding="utf-8")
        claude = (ROOT / "templates/claude/CLAUDE.md").read_text(encoding="utf-8")
        markers = (
            "模块 memory 回答",
            "Topic memory 回答",
            "只有用户已确认且同时具备独立目标",
            "只更新一个当前主 memory",
            "才结算当前交付",
            "MEMORY_COLD.md",
        )
        for marker in markers:
            self.assertIn(marker, codex)
            self.assertIn(marker, claude)

    def test_design_source_covers_single_schema_and_lifecycle_flow(self) -> None:
        design = (ROOT / "doc/0_architecture/design/memory-scoring-design.md").read_text(
            encoding="utf-8"
        )
        for marker in (
            "```mermaid",
            "单一 schema 与交付生命周期",
            "统一布局",
            "模块 memory 与 topic memory 判定",
            "Topic 创建、对账、关闭与冷却",
            "`$summary` 文档范围",
            "MEMORY_COLD.md",
        ):
            self.assertIn(marker, design)

    def test_product_contract_has_no_size_branch_or_second_stamp_line(self) -> None:
        paths = (
            ROOT / "templates/codex/AGENTS.md",
            ROOT / "templates/claude/CLAUDE.md",
            ROOT / "skills/summary/SKILL.md",
            ROOT / "doc/0_architecture/design/memory-scoring-design.md",
        )
        forbidden = ("memory_profile", "Small profile", "Large profile")
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(marker, text, f"{path}: {marker}")

    def test_topic_rename_preserves_created_at_and_updates_pinned(self) -> None:
        for host in ("codex", "claude"):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as raw:
                project = Path(raw)
                config = project / f".{host}"
                hooks = config / "hooks"
                memory = config / "memory"
                source = memory / "topics/old-topic/summary.md"
                hooks.mkdir(parents=True)
                source.parent.mkdir(parents=True)
                shutil.copy2(
                    ROOT / f"templates/{host}/hooks/memory_lint.py",
                    hooks / "memory_lint.py",
                )
                source.write_text(
                    "---\ncategory: topic\ntopic: old-topic\nstatus: active\n"
                    "description: delivery state\n---\nbody\n",
                    encoding="utf-8",
                )
                stats = {
                    "config": {"pinned": ["topics/old-topic/summary.md"]},
                    "files": {
                        "topics/old-topic/summary.md": {
                            "created_at": "2026-01-02"
                        }
                    },
                }
                (memory / "_stats.json").write_text(
                    json.dumps(stats), encoding="utf-8"
                )
                command = [
                    sys.executable,
                    str(hooks / "memory_lint.py"),
                    "topics/old-topic/summary.md",
                    "--category",
                    "topic",
                    "--topic",
                    "new-topic",
                ]
                dry_run = subprocess.run(
                    command,
                    cwd=project,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                self.assertEqual(dry_run.returncode, 1, dry_run.stderr)
                self.assertTrue(source.exists())
                applied = subprocess.run(
                    command + ["--apply"],
                    cwd=project,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                self.assertEqual(applied.returncode, 0, applied.stderr)
                target = memory / "topics/new-topic/summary.md"
                self.assertTrue(target.is_file())
                self.assertIn("topic: new-topic", target.read_text(encoding="utf-8"))
                updated = json.loads((memory / "_stats.json").read_text(encoding="utf-8"))
                self.assertEqual(
                    updated["files"]["topics/new-topic/summary.md"]["created_at"],
                    "2026-01-02",
                )
                self.assertEqual(
                    updated["config"]["pinned"],
                    ["topics/new-topic/summary.md"],
                )

    def test_slug_frontmatter_mismatch_blocks_dry_run_and_apply(self) -> None:
        for host in ("codex", "claude"):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as raw:
                project = Path(raw)
                config = project / f".{host}"
                hooks = config / "hooks"
                source = config / "memory/topics/folder-slug/summary.md"
                hooks.mkdir(parents=True)
                source.parent.mkdir(parents=True)
                shutil.copy2(
                    ROOT / f"templates/{host}/hooks/memory_lint.py",
                    hooks / "memory_lint.py",
                )
                original = (
                    "---\ncategory: topic\ntopic: other-slug\nstatus: active\n"
                    "description: mismatch\n---\n"
                )
                source.write_text(original, encoding="utf-8")
                base = [
                    sys.executable,
                    str(hooks / "memory_lint.py"),
                    "topics/folder-slug/summary.md",
                ]
                for suffix in ([], ["--apply"]):
                    result = subprocess.run(
                        base + suffix,
                        cwd=project,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        check=False,
                    )
                    self.assertEqual(result.returncode, 1, result.stderr)
                    self.assertIn("directory topic", result.stdout)
                    self.assertEqual(source.read_text(encoding="utf-8"), original)

    def test_active_topic_moves_from_hot_to_cold_index(self) -> None:
        for host in ("codex", "claude"):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as raw:
                project = Path(raw)
                config = project / f".{host}"
                scripts = config / "scripts"
                memory = config / "memory"
                topic = memory / "topics/delivery/summary.md"
                scripts.mkdir(parents=True)
                topic.parent.mkdir(parents=True)
                shutil.copy2(
                    ROOT / f"templates/{host}/scripts/memory_rebuild_index.py",
                    scripts / "memory_rebuild_index.py",
                )
                topic.write_text(
                    "---\ncategory: topic\ntopic: delivery\nstatus: active\n"
                    "description: lifecycle\n---\n",
                    encoding="utf-8",
                )
                command = [sys.executable, str(scripts / "memory_rebuild_index.py")]
                active = subprocess.run(command, cwd=project, check=False)
                self.assertEqual(active.returncode, 0)
                self.assertIn(
                    "topics/delivery/summary.md",
                    (memory / "MEMORY.md").read_text(encoding="utf-8"),
                )
                topic.write_text(
                    topic.read_text(encoding="utf-8").replace(
                        "status: active", "status: completed"
                    ),
                    encoding="utf-8",
                )
                completed = subprocess.run(command, cwd=project, check=False)
                self.assertEqual(completed.returncode, 0)
                self.assertNotIn(
                    "topics/delivery/summary.md",
                    (memory / "MEMORY.md").read_text(encoding="utf-8"),
                )
                self.assertIn(
                    "topics/delivery/summary.md",
                    (memory / "MEMORY_COLD.md").read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
