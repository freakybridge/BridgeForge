from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "bridgeforge_codex_user_migrate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("bridgeforge_codex_user_migrate", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def file_hash(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def tree_hash(files: dict[str, bytes]) -> str:
    records = [
        f"{name}\n{hashlib.sha256(payload).hexdigest()}"
        for name, payload in files.items()
    ]
    return "sha256:" + hashlib.sha256(
        ("\n".join(sorted(records)) + "\n").encode("utf-8")
    ).hexdigest()


class UserMigrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.profile = base / "profile"
        self.source = self.profile / ".bridgeforge-codex"
        self.profile.mkdir()
        self.source.mkdir()
        self.module = load_module()

        self.active_files = {"SKILL.md": b"new-entry\n", "worker.py": b"pass\n"}
        active_root = self.profile / ".codex/skills/bridgeforge-codex"
        active_root.mkdir(parents=True)
        for relative, payload in self.active_files.items():
            (active_root / relative).write_bytes(payload)
        self.active_hash = tree_hash(self.active_files)

        legacy_root = self.profile / ".codex/skills/bridgeforge"
        legacy_root.mkdir(parents=True)
        (legacy_root / "SKILL.md").write_bytes(b"legacy-entry\n")
        self.legacy_hash = tree_hash({"SKILL.md": b"legacy-entry\n"})
        harvest_root = self.profile / ".codex/skills/harvest"
        harvest_root.mkdir(parents=True)
        (harvest_root / "SKILL.md").write_bytes(b"retired-harvest\n")
        self.harvest_hash = tree_hash({"SKILL.md": b"retired-harvest\n"})

        claude_root = self.profile / ".claude/skills/common"
        claude_root.mkdir(parents=True)
        (claude_root / "SKILL.md").write_bytes(b"claude-managed\n")
        self.claude_hash = tree_hash({"SKILL.md": b"claude-managed\n"})

        active_skill = {
            "name": "bridgeforge-codex",
            "files": [
                {
                    "source": f"unused/{name}",
                    "target": name,
                    "sha256": file_hash(payload),
                }
                for name, payload in self.active_files.items()
            ],
        }
        active_manifest = {
            "platforms": {
                "codex": {
                    "skills": [active_skill]
                }
            }
        }
        compatibility_manifest = {
            "platforms": {
                "codex": {
                    "skills": [
                        active_skill,
                        {
                            "name": "bridgeforge",
                            "legacy_transition": True,
                            "files": [],
                        },
                        {
                            "name": "harvest",
                            "legacy_transition": True,
                            "files": [],
                        },
                    ]
                }
            }
        }
        (self.source / "bridgeforge-codex-manifest.json").write_text(
            json.dumps(active_manifest), encoding="utf-8"
        )
        (self.source / "shared-skill-manifest.json").write_text(
            json.dumps(compatibility_manifest), encoding="utf-8"
        )
        self._init_repository(
            self.source,
            "https://github.com/freakybridge/BridgeForgeCodex.git",
        )
        legacy_home = self.profile / ".bridgeforge"
        legacy_home.mkdir()
        (legacy_home / "VERSION").write_text("0.94.3\n", encoding="utf-8")
        self._init_repository(
            legacy_home,
            "https://github.com/freakybridge/BridgeForge.git",
        )
        self._write_ledger(
            self.profile / ".codex/bridgeforge-managed.json",
            "codex",
            {
                "bridgeforge": self.legacy_hash,
                "bridgeforge-codex": self.active_hash,
                "harvest": self.harvest_hash,
            },
        )
        self._write_ledger(
            self.profile / ".claude/bridgeforge-managed.json",
            "claude",
            {"common": self.claude_hash},
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def _write_ledger(
        path: Path,
        platform: str,
        records: dict[str, str],
        consent: str | None = None,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "platform": platform,
            "records": {
                name: {
                    "source_commit": "a" * 40,
                    "content_hash": digest,
                    "installed_at": "test",
                }
                for name, digest in records.items()
            },
        }
        if consent is not None:
            payload["consents"] = {"native_memories": consent}
        path.write_text(json.dumps(payload), encoding="utf-8")

    @staticmethod
    def _init_repository(path: Path, remote: str) -> None:
        commands = (
            ["git", "init", "-q", "-b", "main"],
            ["git", "config", "user.name", "BridgeForgeCodex Test"],
            ["git", "config", "user.email", "test@example.invalid"],
            ["git", "add", "."],
            ["git", "commit", "-q", "-m", "fixture"],
            ["git", "remote", "add", "origin", remote],
        )
        for command in commands:
            subprocess.run(command, cwd=path, check=True, capture_output=True)

    def test_two_step_migration_retires_only_hash_owned_assets(self) -> None:
        plan = self.module.build_plan(self.profile, self.source)
        self.assertFalse(plan.blockers)
        receipt = self.module.apply_plan(plan, plan.fingerprint, confirmed=True)
        self.assertEqual(receipt["status"], "completed")
        self.assertTrue((self.profile / ".codex/bridgeforge-codex-managed.json").is_file())
        self.assertFalse((self.profile / ".codex/bridgeforge-managed.json").exists())
        self.assertFalse((self.profile / ".codex/skills/bridgeforge").exists())
        self.assertFalse((self.profile / ".codex/skills/harvest").exists())
        self.assertFalse((self.profile / ".claude/skills/common").exists())
        self.assertFalse((self.profile / ".claude/bridgeforge-managed.json").exists())
        self.assertTrue((self.profile / ".codex/skills/bridgeforge-codex").is_dir())
        self.assertFalse((self.profile / ".bridgeforge").exists())
        self.assertTrue((self.profile / ".bridgeforge-codex").is_dir())

    def test_existing_current_ledger_inherits_legacy_native_memory_consent(self) -> None:
        legacy_ledger = self.profile / ".codex/bridgeforge-managed.json"
        legacy = json.loads(legacy_ledger.read_text(encoding="utf-8"))
        legacy["consents"] = {"native_memories": "approved"}
        legacy_ledger.write_text(json.dumps(legacy), encoding="utf-8")
        self._write_ledger(
            self.profile / ".codex/bridgeforge-codex-managed.json",
            "codex",
            {"bridgeforge-codex": self.active_hash},
        )
        plan = self.module.build_plan(self.profile, self.source)
        self.assertFalse(plan.blockers)
        self.assertIn("write-ledger", {action.kind for action in plan.actions})
        self.module.apply_plan(plan, plan.fingerprint, confirmed=True)
        current = json.loads(
            (self.profile / ".codex/bridgeforge-codex-managed.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(current["consents"], {"native_memories": "approved"})
        self.assertFalse(legacy_ledger.exists())

    def test_drift_is_preserved_and_repeat_plan_is_supported(self) -> None:
        legacy = self.profile / ".codex/skills/bridgeforge/SKILL.md"
        legacy.write_text("local customization\n", encoding="utf-8")
        plan = self.module.build_plan(self.profile, self.source)
        self.assertIn("preserved modified legacy Codex skill", "\n".join(plan.gaps))
        receipt = self.module.apply_plan(plan, plan.fingerprint, confirmed=True)
        self.assertEqual(receipt["status"], "completed_with_gaps")
        self.assertTrue(legacy.is_file())
        self.assertTrue((self.profile / ".codex/bridgeforge-managed.json").is_file())
        repeated = self.module.build_plan(self.profile, self.source)
        self.assertFalse(repeated.blockers)
        self.assertIn("preserved modified legacy Codex skill", "\n".join(repeated.gaps))

    def test_fingerprint_drift_blocks_without_writes(self) -> None:
        plan = self.module.build_plan(self.profile, self.source)
        (self.profile / ".codex/skills/bridgeforge/SKILL.md").write_text(
            "changed after confirmation\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(self.module.MigrationBlocked, "fingerprint drifted"):
            self.module.apply_plan(plan, plan.fingerprint, confirmed=True)
        self.assertFalse((self.profile / ".codex/bridgeforge-codex-managed.json").exists())

    def test_untrusted_legacy_home_is_preserved_as_gap(self) -> None:
        legacy_home = self.profile / ".bridgeforge"
        subprocess.run(
            ["git", "remote", "set-url", "origin", "https://example.invalid/fork.git"],
            cwd=legacy_home,
            check=True,
        )
        plan = self.module.build_plan(self.profile, self.source)
        self.assertIn("preserved unproven legacy home", "\n".join(plan.gaps))
        self.assertNotIn(
            "retire-legacy-home",
            {action.kind for action in plan.actions},
        )

    def test_dirty_official_legacy_home_is_preserved_as_gap(self) -> None:
        legacy_home = self.profile / ".bridgeforge"
        (legacy_home / "VERSION").write_text("locally modified\n", encoding="utf-8")
        plan = self.module.build_plan(self.profile, self.source)
        self.assertIn("preserved unproven legacy home", "\n".join(plan.gaps))
        self.assertNotIn(
            "retire-legacy-home",
            {action.kind for action in plan.actions},
        )
        receipt = self.module.apply_plan(plan, plan.fingerprint, confirmed=True)
        self.assertEqual(receipt["status"], "completed_with_gaps")
        self.assertEqual(
            (legacy_home / "VERSION").read_text(encoding="utf-8"),
            "locally modified\n",
        )

    @unittest.skipUnless(os.name == "nt", "junction migration is Windows-only")
    def test_trusted_legacy_junction_retires_link_but_preserves_target(self) -> None:
        legacy_home = self.profile / ".bridgeforge"
        legacy_target = self.profile / "legacy-repository-kept"
        legacy_home.rename(legacy_target)
        created = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(legacy_home), str(legacy_target)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)
        plan = self.module.build_plan(self.profile, self.source)
        self.assertIn("retire-legacy-home", {action.kind for action in plan.actions})
        receipt = self.module.apply_plan(plan, plan.fingerprint, confirmed=True)
        self.assertEqual(receipt["status"], "completed")
        self.assertFalse(legacy_home.exists())
        self.assertTrue((legacy_target / "VERSION").is_file())

    def test_apply_failure_rolls_back_every_move_and_new_ledger(self) -> None:
        plan = self.module.build_plan(self.profile, self.source)
        with self.assertRaisesRegex(self.module.MigrationBlocked, "rolled back"):
            self.module.apply_plan(
                plan,
                plan.fingerprint,
                confirmed=True,
                fail_after=2,
            )
        self.assertTrue((self.profile / ".codex/skills/bridgeforge").is_dir())
        self.assertTrue((self.profile / ".codex/bridgeforge-managed.json").is_file())
        self.assertTrue((self.profile / ".claude/skills/common").is_dir())
        self.assertFalse((self.profile / ".codex/bridgeforge-codex-managed.json").exists())


if __name__ == "__main__":
    unittest.main()
