#!/usr/bin/env python3
"""Claude keeps the junction state machine; Codex explicitly retires it."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLAUDE_HOOK = ROOT / "templates" / "claude" / "hooks" / "memory_junction_check.py"


class MemoryJunctionHostBoundaryTests(unittest.TestCase):
    def test_codex_junction_runtime_is_retired(self) -> None:
        self.assertFalse((ROOT / "templates" / "codex" / "hooks" / "memory_junction_check.py").exists())
        self.assertFalse((ROOT / ".codex" / "hooks" / "memory_junction_check.py").exists())
        dispatcher = (ROOT / "templates" / "codex" / "hooks" / "hook_dispatcher.py").read_text(encoding="utf-8")
        self.assertNotIn("memory_junction_check.py", dispatcher)

    def test_claude_junction_runtime_remains_loadable(self) -> None:
        self.assertTrue(CLAUDE_HOOK.is_file())
        spec = importlib.util.spec_from_file_location("claude_memory_junction_check", CLAUDE_HOOK)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        self.assertTrue(callable(module.reconcile))

    def test_claude_template_and_dogfood_both_keep_their_own_runtime(self) -> None:
        self.assertTrue((ROOT / ".claude" / "hooks" / "memory_junction_check.py").is_file())


if __name__ == "__main__":
    unittest.main()
