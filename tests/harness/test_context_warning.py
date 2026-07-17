"""Regression tests for the Codex context-cost warning hook."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".codex" / "hooks" / "context_warning.py"
SPEC = importlib.util.spec_from_file_location("context_warning", HOOK)
assert SPEC and SPEC.loader
context_warning = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = context_warning
SPEC.loader.exec_module(context_warning)


class ContextWarningTests(unittest.TestCase):
    def _transcript(self, rows: list[dict]) -> Path:
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".jsonl", delete=False)
        with handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.addCleanup(Path(handle.name).unlink, missing_ok=True)
        return Path(handle.name)

    def test_reads_current_codex_token_count_without_double_counting_cache(self) -> None:
        path = self._transcript([
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {
                            "input_tokens": 45_230,
                            "cached_input_tokens": 10_496,
                            "output_tokens": 264,
                            "total_tokens": 45_494,
                        },
                        "model_context_window": 258_400,
                    },
                },
            }
        ])
        usage = context_warning.read_last_usage(path)
        self.assertIsNotNone(usage)
        self.assertEqual(usage.total_tokens, 45_494)
        self.assertEqual(usage.cached_input_tokens, 10_496)
        self.assertEqual(usage.model_context_window, 258_400)
        self.assertEqual(usage.source, "codex-token-count")

    def test_reads_legacy_usage(self) -> None:
        path = self._transcript([
            {
                "message": {
                    "role": "assistant",
                    "usage": {
                        "input_tokens": 1_000,
                        "cache_creation_input_tokens": 2_000,
                        "cache_read_input_tokens": 3_000,
                        "output_tokens": 400,
                    },
                }
            }
        ])
        usage = context_warning.read_last_usage(path)
        self.assertEqual(usage.total_tokens, 6_400)
        self.assertEqual(usage.cached_input_tokens, 3_000)
        self.assertEqual(usage.source, "legacy-assistant-usage")

    def test_cost_levels_and_cache_miss(self) -> None:
        snapshot = context_warning.UsageSnapshot
        self.assertEqual(context_warning.classify(snapshot(26_000, 10_000, 100, 26_100, 258_400, "test"), 258_400)[0], None)
        self.assertEqual(context_warning.classify(snapshot(80_000, 60_000, 0, 80_000, 258_400, "test"), 258_400)[0], "ECONOMY")
        self.assertEqual(context_warning.classify(snapshot(140_000, 100_000, 0, 140_000, 258_400, "test"), 258_400)[0], "HANDOFF")
        self.assertEqual(context_warning.classify(snapshot(200_000, 150_000, 0, 200_000, 353_000, "test"), 353_000)[0], "CRITICAL")
        level, cache_miss, pct = context_warning.classify(
            snapshot(274_671, 10_496, 151, 274_822, 353_400, "test"),
            353_400,
        )
        self.assertEqual(level, "CRITICAL")
        self.assertTrue(cache_miss)
        self.assertEqual(pct, 77)

    def test_observed_window_and_handoff_commands(self) -> None:
        self.assertEqual(context_warning.effective_window(258_400), (258_400, "token-count"))
        for prompt in ("$snapshot", "$resume latest", "/compact"):
            self.assertTrue(context_warning._is_handoff_command(prompt))
        self.assertFalse(context_warning._is_handoff_command("$git-sync"))

    def test_stdin_to_stdout_uses_latest_token_count(self) -> None:
        def row(tokens: int) -> dict:
            return {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {
                            "input_tokens": tokens,
                            "cached_input_tokens": 100_000,
                            "output_tokens": 0,
                            "total_tokens": tokens,
                        },
                        "model_context_window": 258_400,
                    },
                },
            }

        path = self._transcript([{"junk": "x" * 300_000}, row(80_000), row(140_000)])
        result = subprocess.run(
            [sys.executable, "-B", str(HOOK)],
            input=json.dumps({"prompt": "continue", "transcript_path": str(path)}),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("level=HANDOFF", result.stdout)
        self.assertIn("tokens=140000", result.stdout)

    def test_tail_scan_and_file_size_fallback(self) -> None:
        path = self._transcript([])
        path.write_text("x" * 400_000, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, "-B", str(HOOK)],
            input=json.dumps({"prompt": "continue", "transcript_path": str(path)}),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("level=ECONOMY+CACHE_MISS", result.stdout)
        self.assertIn("token_source=estimate:file-size", result.stdout)


if __name__ == "__main__":
    unittest.main()
