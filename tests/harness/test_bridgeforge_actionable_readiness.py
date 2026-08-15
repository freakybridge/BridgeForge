#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SWITCH_PATHS = (
    ROOT / "scripts/bridgeforge_switch.py",
    ROOT / "templates/claude/scripts/bridgeforge_switch.py",
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class BridgeForgeActionableReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.switch = load(SWITCH_PATHS[0], "bridgeforge_switch_actionable")

    def make_switch_plan(self):
        module = self.switch
        project = Path("C:/fixture")
        source_map = module.LoadedMap(project / ".claude/.bridgeforge-map.json", "missing")
        target_map = module.LoadedMap(project / ".codex/.bridgeforge-map.json", "missing")
        risks = {
            ".codex/hooks/retired-a.py",
            ".codex/hooks/retired-b.py",
        }
        return module.SyncPlan(
            current_host="codex",
            source_host="claude",
            project_root=project,
            template_root=Path("C:/bridgeforge"),
            source_map=source_map,
            target_map=target_map,
            source_snapshot={},
            source_map_state=("missing", None),
            target_map_state=("missing", None),
            target_prestate={rel: f"sha256:{index:064x}" for index, rel in enumerate(sorted(risks), 1)},
            deletes=set(risks),
            retired_deletes=set(risks),
        )

    def test_switch_partial_selection_is_bound_to_displayed_ids(self) -> None:
        module = self.switch
        plan = self.make_switch_plan()
        fingerprint = module._risk_fingerprint(plan)
        selected, declined, displayed = module._select_risks(
            plan,
            supplied_fingerprint=fingerprint,
            selected_ids=("R2",),
            decline_risk=False,
        )
        self.assertEqual([item_id for item_id, _rel in selected], ["R2"])
        self.assertEqual([item_id for item_id, _rel in declined], ["R1"])
        self.assertEqual(displayed, fingerprint)
        self.assertEqual(plan.retired_deletes, {selected[0][1]})
        self.assertEqual(plan.deletes, {selected[0][1]})

    def test_switch_invalid_or_declined_selection_has_no_hidden_risk(self) -> None:
        module = self.switch
        plan = self.make_switch_plan()
        fingerprint = module._risk_fingerprint(plan)
        with self.assertRaisesRegex(module.SyncError, "unknown selected risk IDs"):
            module._select_risks(
                plan,
                supplied_fingerprint=fingerprint,
                selected_ids=("R9",),
                decline_risk=False,
            )
        self.assertEqual(len(plan.retired_deletes), 2)

        plan = self.make_switch_plan()
        selected, declined, _displayed = module._select_risks(
            plan,
            supplied_fingerprint=None,
            selected_ids=None,
            decline_risk=True,
        )
        self.assertEqual(selected, [])
        self.assertEqual([item_id for item_id, _rel in declined], ["R1", "R2"])
        self.assertEqual(plan.retired_deletes, set())
        self.assertEqual(plan.deletes, set())

    def test_switch_dry_run_prints_dual_state_and_one_action_card(self) -> None:
        module = self.switch
        plan = self.make_switch_plan()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            module._print_summary(plan, True)
        text = output.getvalue()
        self.assertIn("execution_status=planned", text)
        self.assertIn("target_readiness=action_required", text)
        action_line = next(line for line in text.splitlines() if line.startswith("action_card="))
        card = json.loads(action_line.removeprefix("action_card="))
        self.assertEqual(card["recommended_selection"], ["R1", "R2"])
        self.assertEqual(card["confirmation"]["business_confirmation_count"], "one")
        self.assertEqual([item["id"] for item in card["required_actions"]], ["R1", "R2"])

    def test_switch_product_mirror_is_exact(self) -> None:
        self.assertEqual(SWITCH_PATHS[0].read_bytes(), SWITCH_PATHS[1].read_bytes())

    def test_root_skill_defines_aggressive_upstream_absorption_without_second_prompt(self) -> None:
        skill = (ROOT / "skills/bridgeforge/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("A. 激进更新：执行全部 R/C/U", skill)
        self.assertIn("B. 温和更新", skill)
        self.assertIn("C. 保守更新", skill)
        self.assertIn("所有 U 项必须在用户选择前一次展示", skill)
        self.assertIn("禁止执行后补问", skill)
        self.assertIn("keyed table 只覆盖同键冲突行", skill)
        self.assertIn("下游独有行", skill)


if __name__ == "__main__":
    unittest.main()
