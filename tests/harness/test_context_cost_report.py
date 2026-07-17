#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".codex" / "scripts" / "context_cost_report.py"


class ContextCostReportTests(unittest.TestCase):
    def test_reports_first_usage_without_prompt_contents(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / "skills" / "demo").mkdir(parents=True)
            (base / "AGENTS.md").write_text("rules-secret", encoding="utf-8")
            (base / "skills" / "demo" / "SKILL.md").write_text(
                "---\nname: demo\ndescription: compact discovery\n---\nbody-secret\n", encoding="utf-8"
            )
            transcript = base / "rollout.jsonl"
            event = {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {"input_tokens": 26000, "cached_input_tokens": 4000, "output_tokens": 10},
                        "model_context_window": 258400,
                    },
                },
            }
            transcript.write_text(json.dumps(event) + "\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "--repo", str(base), "--transcript", str(transcript)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("actual first input: 26000", result.stdout)
            self.assertIn("observed context window: 258400", result.stdout)
            self.assertNotIn("rules-secret", result.stdout)
            self.assertNotIn("body-secret", result.stdout)


if __name__ == "__main__":
    unittest.main()
