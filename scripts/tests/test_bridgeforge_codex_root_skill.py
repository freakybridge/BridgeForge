from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/bridgeforge-codex/SKILL.md"
REFERENCES = ROOT / "skills/bridgeforge-codex/references"
OPENAI_YAML = ROOT / "skills/bridgeforge-codex/agents/openai.yaml"
SLASH_COMMAND = re.compile(r"(?<![A-Za-z0-9_.~-])/bridgeforge(?:-codex)?\b")

USER_COMMAND_SURFACES = (
    ROOT / "README.md",
    ROOT / "INSTALL.md",
    ROOT / "skills/bridgeforge-codex/SKILL.md",
    ROOT / "scripts/install-shared-skills.ps1",
    ROOT / "skills/summary/SKILL.md",
    ROOT / "templates/hooks/config_health_check.py",
    ROOT / ".codex/hooks/config_health_check.py",
    ROOT / "templates/hooks/skill_sync_check.py",
    ROOT / ".codex/hooks/skill_sync_check.py",
    ROOT / "templates/scripts/version_release.py",
    ROOT / ".codex/scripts/version_release.py",
)

ACTIVE_TEXT_SUFFIXES = {".json", ".md", ".ps1", ".py", ".toml", ".yaml", ".yml"}
PASCAL_CASE_ALLOWED_SNIPPETS = (
    "https://github.com/freakybridge/BridgeForgeCodex.git",
    "freakybridge/BridgeForgeCodex",
    r"D:\tools\BridgeForgeCodex",
    "BridgeForgeCodex/",
    "git clone <repo_url> BridgeForgeCodex && cd BridgeForgeCodex",
    r"Local\BridgeForgeCodex.SharedSkillUpdate",
    '"heading": "## 2 BridgeForgeCodex 协作骨架"',
    'replace("{{PROJECT_NAME}}", "BridgeForgeCodex")',
)


class BridgeForgeCodexRootSkillTests(unittest.TestCase):
    def test_active_user_commands_use_dollar_skill_invocation(self) -> None:
        for path in USER_COMMAND_SURFACES:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8-sig")
                self.assertIsNone(SLASH_COMMAND.search(text))

    def test_pascal_case_name_is_confined_to_technical_allowlist(self) -> None:
        candidates = [
            ROOT / "README.md",
            ROOT / "INSTALL.md",
            ROOT / "AGENTS.md",
            ROOT / "bridgeforge-codex-manifest.json",
        ]
        for base in (ROOT / "skills", ROOT / "scripts", ROOT / "templates", ROOT / ".codex"):
            candidates.extend(
                path
                for path in base.rglob("*")
                if path.is_file()
                and path.suffix.lower() in ACTIVE_TEXT_SUFFIXES
                and not {"tests", "compat", "memory", "__pycache__"}.intersection(
                    path.relative_to(ROOT).parts
                )
            )

        for path in sorted(set(candidates)):
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for line_number, line in enumerate(text.splitlines(), start=1):
                if "BridgeForge Codex" not in line and "BridgeForgeCodex" not in line:
                    continue
                with self.subTest(path=path, line=line_number):
                    self.assertNotIn("BridgeForge Codex", line)
                    self.assertTrue(
                        any(snippet in line for snippet in PASCAL_CASE_ALLOWED_SNIPPETS),
                        f"unexpected active PascalCase product name at {path}:{line_number}",
                    )

    def test_menu_display_name_is_exact_lowercase_slug(self) -> None:
        metadata = OPENAI_YAML.read_text(encoding="utf-8")
        self.assertIn('display_name: "bridgeforge-codex"', metadata)
        self.assertIn("$bridgeforge-codex", metadata)

    def test_user_visible_product_name_is_lowercase_kebab_case(self) -> None:
        display_surfaces = (
            ROOT / "templates/AGENTS.md",
            ROOT / "skills/bridgeforge-codex/SKILL.md",
            ROOT / "doc/0_architecture/design/codex-project-sync.md",
            ROOT / "doc/3_reference/codex-project-operating-guide.md",
        )
        for path in display_surfaces:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertIn("bridgeforge-codex", text)
                self.assertNotIn("BridgeForgeCodex", text)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        install = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
        self.assertTrue(readme.startswith("# bridgeforge-codex\n"))
        self.assertTrue(install.startswith("# bridgeforge-codex 安装与迁移\n"))
        self.assertIn("freakybridge/BridgeForgeCodex.git", readme)
        self.assertIn("freakybridge/BridgeForgeCodex.git", install)

    def test_only_new_codex_entry_is_active(self) -> None:
        self.assertTrue(SKILL.is_file())
        self.assertFalse((ROOT / "skills/bridgeforge").exists())
        self.assertFalse((ROOT / "templates/claude").exists())
        self.assertFalse((ROOT / "CLAUDE.md").exists())
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("name: bridgeforge-codex", text)
        self.assertIn("Codex-only", text)
        self.assertIn('".bridgeforge-codex"', text)
        self.assertIn("只是 Codex 可发现的薄入口", text)
        self.assertIn("scripts/bridgeforge_codex_project_sync.py", text)

    def test_legacy_user_migration_surfaces_are_retired(self) -> None:
        for relative in (
            "shared-skill-manifest.json",
            "scripts/bridgeforge_codex_legacy_entry.SKILL.md",
            "scripts/bridgeforge_codex_user_migrate.py",
        ):
            self.assertFalse((ROOT / relative).exists(), relative)
        compatibility_root = ROOT / "scripts/compat/legacy-shared-skills"
        self.assertFalse(
            compatibility_root.exists()
            and any(path.is_file() for path in compatibility_root.rglob("*"))
        )

    def test_one_risk_card_and_project_sync_contract_are_explicit(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        for marker in (
            "native memories、`.agents` 布局迁移、版本戳迁移、上游 absorption 和其他项目 risk 汇总成一张清单",
            "整轮最多确认一次",
            "plan-fingerprint",
            "A：执行全部推荐项",
            "B：只执行用户列出的 ID",
            "C：不再执行风险动作",
            "`action_required_items` 按 G1、G2……逐项完整展示",
            "G 项是非执行 review 清单",
            "禁止只显示 gap 数量后让用户再次追问",
            "`repair-hook` 只能修改用户 hooks",
            "项目骨架更新禁止顺手执行完整 `reconcile`",
            "本地较新自动上传",
            "远端较新自动恢复",
            "日常同步和 hook 修复不得重复询问",
            "user_native_memory_readiness",
            "remote_reconcile=applied/declined/not_requested",
            ".codex/.bridgeforge_codex_version",
            ".codex/.bridgeforge_version",
        ):
            self.assertIn(marker, text)

    def test_python_preflight_native_memory_and_layout_are_in_one_orchestration(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        preflight = text.index("## 2. Python preflight")
        native_memory = text.index("codex_memory_sync.py", preflight)
        layout = text.index("bridgeforge_codex_migrate_layout.py", native_memory)
        project_sync = text.index("bridgeforge_codex_project_sync.py", layout)
        self.assertLess(preflight, native_memory)
        self.assertLess(native_memory, layout)
        self.assertLess(layout, project_sync)
        self.assertNotIn("\npython ", text)
        self.assertIn("本轮统一 safe/risk/gap accumulator", text)

    def test_references_are_codex_only_and_have_no_switch(self) -> None:
        expected = {"user-skill-maintenance.md", "init.md", "adopt.md", "update.md"}
        self.assertEqual({path.name for path in REFERENCES.glob("*.md")}, expected)
        combined = "\n".join(
            path.read_text(encoding="utf-8") for path in sorted(REFERENCES.glob("*.md"))
        )
        self.assertIn("bridgeforge_codex_project_sync.py", combined)
        self.assertNotIn("bridgeforge_switch.py", combined)
        self.assertNotIn("project_finalize", combined)
        self.assertNotIn("bridgeforge_codex_user_maintenance.ps1", combined)

    def test_shared_skills_inherit_session_model(self) -> None:
        skill_files = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertGreaterEqual(len(skill_files), 15)
        for path in skill_files:
            with self.subTest(path=path):
                frontmatter = path.read_text(encoding="utf-8").split("---", 2)[1]
                self.assertNotRegex(frontmatter, r"(?m)^model\s*:")


if __name__ == "__main__":
    unittest.main()
