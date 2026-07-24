#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "explain" / "SKILL.md"


class ExplainSkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SKILL.read_text(encoding="utf-8")
        cls.frontmatter = cls.text.split("---", 2)[1]

    def test_discovery_covers_explicit_and_natural_language_requests(self) -> None:
        for marker in ("$explain", "白话", "举例", "没看懂", "未理解"):
            self.assertIn(marker, self.frontmatter)
        self.assertIn("user_invocable: true", self.frontmatter)

    def test_output_contract_is_ordered(self) -> None:
        conclusion = self.text.index("**结论**")
        plain = self.text.index("**白话解释**")
        example = self.text.index("**当前话题例子**")
        self.assertLess(conclusion, plain)
        self.assertLess(plain, example)

    def test_language_uncertainty_and_scope_boundaries_are_explicit(self) -> None:
        for marker in (
            "中文请求使用简体中文",
            "条件、不确定性和限制",
            "不猜测",
            "不实施、重设计或扩张",
        ):
            self.assertIn(marker, self.text)

    def test_missing_context_has_a_conservative_output(self) -> None:
        self.assertIn("没有可定位的原文或上下文", self.text)
        self.assertIn("明确说明缺失内容以及因此无法确认的部分", self.text)


if __name__ == "__main__":
    unittest.main()
