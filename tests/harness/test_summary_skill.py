#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "summary" / "SKILL.md"
DEEP_STEPS = ROOT / "skills" / "summary" / "references" / "deep-steps.md"
HARVEST = ROOT / "skills" / "harvest" / "SKILL.md"


class SummarySkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skill = SKILL.read_text(encoding="utf-8")
        cls.deep_steps = DEEP_STEPS.read_text(encoding="utf-8")
        cls.harvest = HARVEST.read_text(encoding="utf-8")
        cls.all_text = cls.skill + "\n" + cls.deep_steps

    def test_host_matrix_routes_capability_before_identity_and_fails_closed(self) -> None:
        for marker in (
            "先宿主、再能力、后身份",
            ".codex/.bridgeforge_version",
            ".codex/scripts/project_memory_writer.py",
            ".codex/memory/",
            ".codex/scripts/memory_rebuild_index.py",
            ".codex/hooks/memory_lint.py",
            ".claude/.bridgeforge_version",
            ".claude/scripts/project_memory_writer.py",
            ".claude/memory/",
            ".claude/scripts/memory_rebuild_index.py",
            ".claude/hooks/memory_lint.py",
            "writer 能力本身授权受限的项目内",
            "fail closed",
            "无参数 `/bridgeforge`",
            "禁止回退到用户级 memory",
            "禁止跨宿主",
            "另一宿主的 writer 不构成当前宿主能力",
        ):
            self.assertIn(marker, self.skill)

    def test_topic_has_one_canonical_summary_and_completion_needs_user_acceptance(self) -> None:
        for marker in (
            "<project-memory-root>/topics/<topic>/summary.md",
            ".codex/memory/topics/<topic>/summary.md",
            "后续总结只更新该 `summary.md`",
            "禁止按日期、单次对话、里程碑子项或子任务新增",
            "试用或明确验收",
            "不能代替用户验收",
        ):
            self.assertIn(marker, self.skill)

    def test_categories_and_metadata_contract_are_preserved(self) -> None:
        for marker in (
            "`architecture`、`engineering`、`domain`、",
            "`operations`",
            "`category` 必须是 `topic`",
            "`topic: <exact-slug>`",
            "`status` 只能是 `active`、`completed`、`superseded`",
            "`description`",
            "确认前禁止写入、",
        ):
            self.assertIn(marker, self.skill)

    def test_general_memory_requires_a_new_stable_question(self) -> None:
        for marker in (
            "新的稳定问题门槛",
            "正例",
            "网关重连时怎样恢复订阅并避免重复订单",
            "反例",
            "今天的断线事故经过",
            "本次 37 项测试数字",
            "必须停止写入并用一个单题请求用户裁决",
        ):
            self.assertIn(marker, self.skill)

    def test_old_fragments_only_produce_structured_candidates(self) -> None:
        for marker in (
            "建议的规范目标文件",
            "来源文件",
            "重复结论",
            "冲突或疑似过时结论",
            "建议保留内容",
            "建议删除文件",
            "只报告候选",
            "禁止自动合并、删除、移动",
        ):
            self.assertIn(marker, self.deep_steps)
        self.assertIn("交给独立整理任务", self.skill)

    def test_independent_consolidation_short_circuits_before_lint(self) -> None:
        rebuild = self.deep_steps.index(
            "运行 `<host-config-dir>/scripts/memory_rebuild_index.py`"
        )
        lint = self.deep_steps.index(
            "才运行 `<host-config-dir>/hooks/memory_lint.py`"
        )
        self.assertLess(rebuild, lint)
        for marker in (
            "禁止并行、禁止切换到另一宿主",
            "若当前宿主的 `memory_rebuild_index.py` 失败，立即停止",
            "标记为“跳过”",
            "继续 lint 或宣称整理成功",
        ):
            self.assertIn(marker, self.deep_steps)

    def test_harvest_candidates_have_no_summary_backchannel(self) -> None:
        self.assertIn("候选来源仅限", self.harvest)
        self.assertIn("`$ARGUMENTS` 显式提供", self.harvest)
        self.assertIn("已经存在的 harvest inbox", self.harvest)
        self.assertNotIn("`summary` 只捕捉候选", self.harvest)

    def test_archive_user_memory_evidence_git_and_runtime_boundaries(self) -> None:
        for marker in (
            "请另行调用 $archive-scan",
            "不执行 `git mv`",
            "用户级 memory 候选",
            "只有用户明确批准后才能写入",
            "不重新运行测试、build、审计",
            "runtime trust 未验证",
            "git status",
            "未暂存、未 commit、未 push",
            "$git-sync",
        ):
            self.assertIn(marker, self.all_text)

    def test_high_confidence_rules_and_docs_update_automatically(self) -> None:
        self.assertIn(
            "高置信、非破坏且确有必要的 rule 更新自动执行",
            self.skill,
        )
        self.assertIn(
            "高置信、非破坏且确有必要的 docs 同步自动执行",
            self.skill,
        )

    def test_retired_harvest_behavior_is_absent(self) -> None:
        lowered = self.all_text.lower()
        for retired_marker in ("harvest-inbox", "harvest candidate", "$harvest"):
            self.assertNotIn(retired_marker, lowered)


if __name__ == "__main__":
    unittest.main()
