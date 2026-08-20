from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CHECK = load(
    "bridgeforge_current_instruction_source",
    ROOT / "templates" / "hooks" / "instruction_source_check.py",
)


class CurrentInstructionSourceTests(unittest.TestCase):
    def fixture(self, root: Path) -> None:
        (root / ".codex").mkdir()
        (root / "templates").mkdir()
        (root / "AGENTS.md").write_bytes((ROOT / "AGENTS.md").read_bytes())
        (root / "templates" / "AGENTS.md").write_bytes(
            (ROOT / "templates" / "AGENTS.md").read_bytes()
        )
        (root / ".codex" / "managed-skeleton.json").write_bytes(
            (ROOT / ".codex" / "managed-skeleton.json").read_bytes()
        )

    def test_factory_current_instruction_sources_pass(self) -> None:
        self.assertEqual(CHECK.instruction_source_issues(ROOT), [])

    def test_current_agents_keep_review_and_factory_redlines(self) -> None:
        common = (ROOT / "templates" / "AGENTS.md").read_text(encoding="utf-8")
        factory = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for marker in (
            "按严重度排序",
            "文件 / 行号 / 行为风险",
            "取舍理由、主要风险与触发条件",
            "禁止只罗列选项不拍板",
        ):
            self.assertIn(marker, common)
        self.assertIn("受管资产必须使用显式 target", factory)

    def test_unzoned_or_publicly_drifted_agents_fail(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.fixture(root)
            (root / "AGENTS.md").write_text("# project\n", encoding="utf-8")
            self.assertIn("zone markers are required", " ".join(CHECK.instruction_source_issues(root)))
            (root / "AGENTS.md").write_bytes((ROOT / "AGENTS.md").read_bytes())
            text = (root / "AGENTS.md").read_text(encoding="utf-8")
            (root / "AGENTS.md").write_text(
                text.replace("公共架构红线", "公共架构红线-DRIFT", 1),
                encoding="utf-8",
            )
            self.assertIn("public zone was modified", " ".join(CHECK.instruction_source_issues(root)))

    def test_project_zone_can_be_customized(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.fixture(root)
            text = (root / "AGENTS.md").read_text(encoding="utf-8")
            text = text.replace(
                "> 本区由项目完全所有。",
                "> 本区由项目完全所有。\n\nPROJECT-CUSTOM",
                1,
            )
            (root / "AGENTS.md").write_text(text, encoding="utf-8")
            self.assertEqual(CHECK.instruction_source_issues(root), [])

    def test_contract_has_no_rule_compatibility_assets_or_history(self) -> None:
        contract = json.loads(
            (ROOT / "templates" / "managed-skeleton.json").read_text(encoding="utf-8")
        )
        serialized = json.dumps(contract)
        self.assertNotIn("rule_index_check.py", serialized)
        self.assertNotIn("rule_size_check.py", serialized)
        self.assertNotIn("historical_sha256", serialized)
        self.assertFalse(any(asset.get("strategy") == "retirement" for asset in contract["assets"]))


if __name__ == "__main__":
    unittest.main()
