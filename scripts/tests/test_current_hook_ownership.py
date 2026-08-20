from __future__ import annotations

import importlib.util
import json
import sys
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


OWNERSHIP = load(
    "bridgeforge_current_hook_ownership",
    ROOT / "scripts" / "hooks_ownership.py",
)
DISPATCHER = load(
    "bridgeforge_current_hook_dispatcher",
    ROOT / "templates" / "hooks" / "hook_dispatcher.py",
)


class CurrentHookOwnershipTests(unittest.TestCase):
    def expected(self):
        document = {
            "hooks": {
                "SessionStart": [{
                    "matcher": "startup",
                    "hooks": [{
                        "bridgeforgeCodexId": "bridgeforge-codex.test.v1:start",
                        "type": "command",
                        "command": "python current.py",
                    }],
                }],
            },
        }
        return OWNERSHIP.expected_groups(
            document,
            managed_prefix="bridgeforge-codex.test.v1:",
        )

    def test_current_handlers_are_added_without_touching_external_hooks(self) -> None:
        document = {
            "description": "current",
            "hooks": {"Stop": [{"hooks": [{"command": "vendor"}]}]},
        }
        canonical, external, receipts = OWNERSHIP.canonicalize(
            document,
            self.expected(),
            managed_prefixes=("bridgeforge-codex.test.v1:",),
            label="hooks.json",
            managed_top_level={"description": "current"},
        )
        self.assertEqual(external, {"hooks": {"Stop": [{"hooks": [{"command": "vendor"}]}]}})
        self.assertEqual(receipts[0]["action"], "add-missing")
        OWNERSHIP.validate_current(
            canonical,
            self.expected(),
            managed_prefixes=("bridgeforge-codex.test.v1:",),
            label="hooks.json",
            managed_top_level={"description": "current"},
        )

    def test_unknown_or_drifted_managed_handlers_fail_closed(self) -> None:
        expected = self.expected()
        current = {"hooks": {"SessionStart": [expected[0]["group"]]}}
        drifted = json.loads(json.dumps(current))
        drifted["hooks"]["SessionStart"][0]["hooks"][0]["command"] = "python drift.py"
        with self.assertRaisesRegex(OWNERSHIP.HooksOwnershipError, "content drifted"):
            OWNERSHIP.canonicalize(
                drifted,
                expected,
                managed_prefixes=("bridgeforge-codex.test.v1:",),
                label="hooks.json",
            )
        unknown = {"hooks": {"Stop": [{"hooks": [{
            "bridgeforgeCodexId": "bridgeforge-codex.test.v1:unknown",
            "command": "python unknown.py",
        }]}]}}
        with self.assertRaisesRegex(OWNERSHIP.HooksOwnershipError, "unknown managed"):
            OWNERSHIP.canonicalize(
                unknown,
                expected,
                managed_prefixes=("bridgeforge-codex.test.v1:",),
                label="hooks.json",
            )

    def test_dispatcher_routes_only_current_concrete_scripts(self) -> None:
        self.assertEqual(DISPATCHER.runtime_route_errors(), [])
        routed = {
            item
            for values in DISPATCHER.RUNTIME_ROUTES.values()
            for item in values
        }
        self.assertNotIn("hooks/rule_index_check.py", routed)
        self.assertNotIn("hooks/rule_size_check.py", routed)
        for relative in routed:
            self.assertTrue((ROOT / "templates" / relative).is_file(), relative)

    def test_template_and_dogfood_current_hook_sources_match(self) -> None:
        contract = json.loads(
            (ROOT / "templates" / "managed-skeleton.json").read_text(encoding="utf-8")
        )
        for asset in contract["assets"]:
            target = str(asset["target"])
            source = str(asset["source"])
            if not target.startswith(".codex/hooks/") or asset["strategy"] != "whole":
                continue
            with self.subTest(asset=asset["id"]):
                self.assertEqual((ROOT / source).read_bytes(), (ROOT / target).read_bytes())


if __name__ == "__main__":
    unittest.main()
