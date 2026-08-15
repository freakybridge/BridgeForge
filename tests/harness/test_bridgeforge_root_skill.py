#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class BridgeForgeRootSkillTests(unittest.TestCase):
    def test_agent_specific_skill_dir_is_set_before_command_dir(self) -> None:
        text = (ROOT / "skills" / "bridgeforge" / "SKILL.md").read_text(encoding="utf-8")
        for user_dir in (".claude\\skills", ".codex\\skills"):
            start = text.index(
                f'$USER_SKILLS_DIR = Join-Path $env:USERPROFILE "{user_dir}"'
            )
            command = text.index(
                "$BRIDGEFORGE_COMMAND_DIR = Join-Path $USER_SKILLS_DIR \"bridgeforge\"",
                start,
            )
            self.assertLess(start, command)

    def test_codex_product_inventory_is_covered_by_init_and_update(self) -> None:
        init = (ROOT / "skills" / "bridgeforge" / "references" / "init.md").read_text(encoding="utf-8")
        update = (ROOT / "skills" / "bridgeforge" / "references" / "update.md").read_text(encoding="utf-8")
        for marker in (
            "config.toml",
            "agents/*.toml",
            "skill-routing.json",
            ".githooks/pre-commit",
        ):
            self.assertIn(marker, init)
            self.assertIn(marker, update)

    def test_python_preflight_precedes_every_project_write_mode(self) -> None:
        skill = (ROOT / "skills" / "bridgeforge" / "SKILL.md").read_text(encoding="utf-8")
        preflight = skill.index("Step 2.1：项目 Python 3.11+ 一次性 preflight")
        native_memories = skill.index("Step 2.2：Codex 原生 memories 只读 planner")
        legacy_write = skill.index("Step 2.5：当前项目遗留 `.agents/` 只读 planner")
        switch = skill.index("Step 3：显式 switch planner 优先")
        self.assertLess(preflight, native_memories)
        self.assertLess(native_memories, legacy_write)
        self.assertLess(preflight, legacy_write)
        self.assertLess(preflight, switch)
        for marker in (
            "$HOOK_PYTHON",
            "project .venv must use Python 3.11+",
            "PATH fallback is forbidden",
            "基础解释器写入用户级 hook",
            "禁止把任何项目 `.venv` 路径持久化",
            "禁止复制、删除、merge",
            "禁止重新探测、切换",
        ):
            self.assertIn(marker, skill)
        self.assertNotIn("$MEMORY_SYNC_PYTHON", skill)
        self.assertNotIn("禁止使用项目 `.venv`", skill)

        references = ROOT / "skills" / "bridgeforge" / "references"
        for name in ("init.md", "adopt.md", "update.md"):
            text = (references / name).read_text(encoding="utf-8")
            self.assertIn("$HOOK_PYTHON", text)
            self.assertIn("Python 3.11+", text)

    def test_all_modes_share_zero_or_one_confirmation_accumulator(self) -> None:
        skill = (ROOT / "skills" / "bridgeforge" / "SKILL.md").read_text(encoding="utf-8")
        for marker in (
            "统一 safe / risk / gap accumulator",
            "aggregate_fingerprint=sha256:<64hex>",
            "业务确认次数为 0",
            "只展示一张卡",
            "紧邻重跑全部 planner",
            "用户拒绝时 risk 跳过，safe 继续",
            "status=completed|completed_with_gaps|failed",
            "readiness=ready|degraded|blocked",
        ):
            self.assertIn(marker, skill)
        for name in ("init.md", "adopt.md", "update.md", "switch.md"):
            text = (ROOT / "skills" / "bridgeforge" / "references" / name).read_text(encoding="utf-8")
            self.assertNotIn("无条件删除 `.codex/hooks/stall_warning.py`", text)
        combined = "\n".join(
            (ROOT / "skills" / "bridgeforge" / "references" / name).read_text(encoding="utf-8")
            for name in ("init.md", "adopt.md", "update.md", "switch.md")
        )
        for forbidden in (
            "展示 diff 并确认",
            "展示 diff 后决定",
            "由用户决定是否保留",
            "让用户逐段吸收",
        ):
            self.assertNotIn(forbidden, combined)

    def test_user_maintenance_and_native_consent_use_narrow_existing_state(self) -> None:
        skill = (ROOT / "skills" / "bridgeforge" / "SKILL.md").read_text(encoding="utf-8")
        maintenance = (ROOT / "skills" / "bridgeforge" / "references" / "user-skill-maintenance.md").read_text(encoding="utf-8")
        self.assertIn("bridgeforge_user_maintenance.ps1", skill)
        self.assertIn("consents.native_memories", skill)
        self.assertIn("declined", skill)
        self.assertIn("禁止调用 `gh`", skill)
        self.assertIn("SourceRepositoryRoot", maintenance)
        self.assertIn("未知 action", maintenance)
        self.assertIn("非持久平台审批", maintenance)
        self.assertIn("只接受 `refresh`", maintenance)
        self.assertIn("未记录 consent 但已启用", skill)
        self.assertIn("legacy_enabled", skill)
        self.assertNotIn("-Action native-status", skill)
        self.assertNotIn("-Action native-reconcile", skill)
        self.assertIn("codex_memory_sync.py maintain", skill)
        self.assertIn("窄的非持久平台审批", skill)
        self.assertIn("禁止加入 refresh 的持久规则", skill)

    def test_codex_platform_default_policy_is_main_dialog_and_all_modes(self) -> None:
        skill = (ROOT / "skills" / "bridgeforge" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Codex 平台默认调度", skill)
        self.assertIn("不再创建、读取或修改项目级模型、reasoning effort 或订阅档位配置", skill)
        self.assertNotIn("subscription_routing.py", skill)
        self.assertIn("Claude 跳过本节。", skill)
        for name in ("init.md", "adopt.md", "update.md"):
            text = (ROOT / "skills" / "bridgeforge" / "references" / name).read_text(encoding="utf-8")
            self.assertNotIn("subscription-tier.toml", text)

    def test_progressive_references_are_one_level_and_live(self) -> None:
        expected = {"switch.md", "user-skill-maintenance.md", "init.md", "adopt.md", "update.md"}
        references = ROOT / "skills" / "bridgeforge" / "references"
        self.assertEqual({path.name for path in references.glob("*.md")}, expected)
        self.assertFalse(any(path.is_dir() for path in references.iterdir()))

    def test_update_memory_audit_precedes_the_only_version_finalizer(self) -> None:
        update = (
            ROOT / "skills" / "bridgeforge" / "references" / "update.md"
        ).read_text(encoding="utf-8")
        audit = update.index("templates\\$TEMPLATE_AGENT\\hooks\\memory_lint.py")
        finalizer = update.index("scripts\\bridgeforge_project_finalize.py")
        self.assertLess(audit, finalizer)
        latest = update.index("已是最新（vX.Y.Z）")
        self.assertIn("判断“已是最新”前必须先执行 U2.1", update[:latest])
        for marker in (
            "--organize --project-root . --host $CURRENT_HOST",
            "--apply --confirmed",
            "memory_schema=clean",
            "config_health=clean",
            "completed_with_gaps",
            "禁止绕过 `bridgeforge_project_finalize.py` 手工写",
        ):
            self.assertIn(marker, update)


if __name__ == "__main__":
    unittest.main()
