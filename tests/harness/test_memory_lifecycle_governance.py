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
    @staticmethod
    def _memory_text(
        category: str,
        description: str = "fixture memory",
        *,
        topic: str = "",
        status: str = "active",
    ) -> str:
        topic_line = f"topic: {topic}\n" if topic else ""
        description_line = f"description: {description}\n" if description else ""
        return (
            f"---\ncategory: {category}\n{topic_line}status: {status}\n"
            f"{description_line}---\nfixture body\n"
        )

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
                    command + ["--apply", "--confirmed"],
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
                for suffix in ([], ["--apply", "--confirmed"]):
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

    def test_apply_requires_explicit_confirmation_and_never_writes_without_it(self) -> None:
        for host in ("codex", "claude"):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as raw:
                project = Path(raw)
                source = project / f".{host}/memory/loose.md"
                source.parent.mkdir(parents=True)
                source.write_text(self._memory_text("domain"), encoding="utf-8")
                before = source.read_bytes()
                command = [
                    sys.executable,
                    str(ROOT / f"templates/{host}/hooks/memory_lint.py"),
                    "--organize",
                    "--project-root",
                    str(project),
                    "--host",
                    host,
                    "--apply",
                ]
                result = subprocess.run(
                    command,
                    cwd=project,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("--confirmed", result.stderr)
                self.assertEqual(source.read_bytes(), before)
                self.assertFalse((source.parent / "domain/loose.md").exists())

    def test_causis_like_invalid_layout_is_fully_reported_without_writes(self) -> None:
        for host in ("codex", "claude"):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as raw:
                project = Path(raw)
                memory = project / f".{host}/memory"
                fixtures = {
                    ".codex/memory/topics/risk-weekly/summary.md": self._memory_text(
                        "topic", topic="risk-weekly"
                    ),
                    "topics/root_hygiene/summary.md": self._memory_text(
                        "topic", topic="root_hygiene"
                    ),
                    "topics/hedge-exposure/summary.md": self._memory_text(
                        "topic", topic="hedge-exposure"
                    ),
                    "topics/hedge-exposure/delivery.md": self._memory_text(
                        "topic", topic="hedge-exposure"
                    ),
                    "domain/hedge_exposure_option_bar_t_fallback_2026_07_23.md": self._memory_text(
                        "domain", ""
                    ),
                    "engineering/scheduled_result_sync.md": self._memory_text(
                        "engineering", ""
                    ),
                    "domain/t0_fac_second_precision_and_result_columns.md": self._memory_text(
                        "domain", ""
                    ),
                }
                paths: list[Path] = []
                for relative, content in fixtures.items():
                    path = memory / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8")
                    paths.append(path)
                before = {path.relative_to(memory).as_posix(): path.read_bytes() for path in paths}

                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / f"templates/{host}/hooks/memory_lint.py"),
                        "--organize",
                        "--project-root",
                        str(project),
                        "--host",
                        host,
                    ],
                    cwd=project,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                self.assertEqual(result.returncode, 1, result.stderr)
                for marker in (
                    ".codex/memory/topics/risk-weekly/summary.md",
                    "root_hygiene",
                    "缺少非空 description",
                    "多个文件竞争同一规范目标 topics/hedge-exposure/summary.md",
                ):
                    self.assertIn(marker, result.stdout)
                after = {
                    path.relative_to(memory).as_posix(): path.read_bytes()
                    for path in memory.rglob("*.md")
                }
                self.assertEqual(after, before)

    def test_canonical_project_memory_layout_passes_for_both_hosts(self) -> None:
        for host in ("codex", "claude"):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as raw:
                project = Path(raw)
                summary = project / f".{host}/memory/topics/risk-weekly/summary.md"
                summary.parent.mkdir(parents=True)
                summary.write_text(
                    self._memory_text("topic", topic="risk-weekly"),
                    encoding="utf-8",
                )
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / f"templates/{host}/hooks/memory_lint.py"),
                        "--organize",
                        "--project-root",
                        str(project),
                        "--host",
                        host,
                    ],
                    cwd=project,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("[ok] topics/risk-weekly/summary.md", result.stdout)

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
