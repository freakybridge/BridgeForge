from __future__ import annotations

import json
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
HISTORICAL_HOOK_DESCRIPTION = (
    "BridgeForgeCodex project lifecycle hooks. "
    "This is the only managed Codex hook registration source."
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
                    historical_contract_value = (
                        path.name == "managed-skeleton.json"
                        and line.strip().rstrip(",")
                        == json.dumps(HISTORICAL_HOOK_DESCRIPTION)
                    )
                    self.assertTrue(
                        historical_contract_value
                        or any(
                            snippet in line
                            for snippet in PASCAL_CASE_ALLOWED_SNIPPETS
                        ),
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

    def test_current_only_risk_and_project_sync_contract_are_explicit(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        for marker in (
            "destructive rebuild 必须先由独立 agent",
            "用户逐项确认可",
            "plan-fingerprint",
            "--confirmed-preservation-manifest",
            "--confirmed-risk",
            "current baseline",
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

    def test_default_result_is_conclusion_first_and_hides_raw_receipt(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        result_contract = text[text.index("## 7. 用户结果与技术收据") :]
        for marker in (
            "结论、待处理事项、下一步",
            "本次操作已结束，无需继续处理",
            "骨架升级已完成，当前骨架版本为 {version}",
            "本次升级产生的 {count} 个骨架文件尚未保存到 GitHub",
            "当前 Codex 对话框运行 $git-sync",
            "骨架升级未完成",
            "无关且无需操作的 advisory 默认隐藏",
            "Native Memory 健康且无需用户操作时默认不单列",
            "只有用户追问原因、证据或技术细节时",
        ):
            self.assertIn(marker, result_contract)

        hidden_receipt = result_contract.index("### 7.2 内部技术收据")
        self.assertGreater(result_contract.index("`execution_status`"), hidden_receipt)
        self.assertGreater(result_contract.index("preserved project asset IDs"), hidden_receipt)
        self.assertGreater(result_contract.index("rollback 字段"), hidden_receipt)

    def test_preservation_manifest_is_the_only_old_project_decision_term(self) -> None:
        skill = SKILL.read_text(encoding="utf-8")
        sync = (
            ROOT / "scripts" / "bridgeforge_codex_project_sync.py"
        ).read_text(encoding="utf-8")
        self.assertIn("PreservationManifest", skill)
        self.assertIn("--confirmed-preservation-manifest", skill)
        obsolete_term = "white" + "list"
        self.assertNotIn(obsolete_term, skill.casefold())
        self.assertNotIn(obsolete_term, sync.casefold())
        self.assertNotIn("project_asset_" + obsolete_term, sync)
        self.assertNotIn("--confirmed-" + obsolete_term, sync)

    def test_python_preflight_native_memory_and_project_sync_are_in_one_orchestration(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        preflight = text.index("## 2. Python preflight")
        mode = text.index("按以下顺序只读判定并锁定 `$MODE`", preflight)
        bootstrap = text.index("project_runtime.py", mode)
        native_memory = text.index("codex_memory_sync.py", preflight)
        project_sync = text.index("bridgeforge_codex_project_sync.py", native_memory)
        self.assertLess(preflight, mode)
        self.assertLess(mode, bootstrap)
        self.assertLess(bootstrap, native_memory)
        self.assertLess(native_memory, project_sync)
        self.assertNotIn("\npython ", text)
        self.assertIn("status --project-root .", text)
        self.assertIn("禁止持久化任一项目的绝对 Python 路径", text)
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
