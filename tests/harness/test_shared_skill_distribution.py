#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPDATER = ROOT / "scripts" / "bridgeforge_shared_update.ps1"
INSTALLER = ROOT / "scripts" / "install-shared-skills.ps1"
MANIFEST_REBUILDER = ROOT / "scripts" / "rebuild_shared_skill_manifest.py"
CANONICAL_REMOTE = "https://github.com/freakybridge/BridgeForge.git"


def sha256(path: Path) -> str:
    payload = path.read_bytes()
    if b"\0" not in payload:
        payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(payload).hexdigest()


def run(command: list[str], cwd: Path, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


class SharedSkillDistributionTests(unittest.TestCase):
    def setUp(self) -> None:
        if os.name != "nt":
            self.skipTest("Windows-only distribution tests")
        if shutil.which("git") is None or shutil.which("powershell.exe") is None:
            self.skipTest("git and Windows PowerShell are required")
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.profile = self.base / "profile"
        self.profile.mkdir()
        self.source = self.base / "source"
        self.source.mkdir()
        self.remote = self.base / "canonical.git"
        self.env = os.environ.copy()
        self.env["USERPROFILE"] = str(self.profile)
        self.env["GIT_CONFIG_COUNT"] = "1"
        self.env["GIT_CONFIG_KEY_0"] = f"url.{self.remote.as_uri()}.insteadOf"
        self.env["GIT_CONFIG_VALUE_0"] = CANONICAL_REMOTE

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_source(
        self,
        bridgeforge_text: str = "bridgeforge-v1",
        common_text: str = "common-v1",
        include_common: bool = True,
    ) -> None:
        (self.source / ".gitattributes").write_text("* text=auto eol=lf\n", encoding="utf-8")
        (self.source / "entry.md").write_text(bridgeforge_text, encoding="utf-8")
        common = self.source / "skills" / "common"
        common.mkdir(parents=True, exist_ok=True)
        (common / "SKILL.md").write_text(common_text, encoding="utf-8")
        scripts = self.source / "scripts"
        scripts.mkdir(exist_ok=True)
        shutil.copy2(UPDATER, scripts / UPDATER.name)

        bridgeforge = {
            "name": "bridgeforge",
            "files": [
                {
                    "source": "entry.md",
                    "target": "SKILL.md",
                    "sha256": f"sha256:{sha256(self.source / 'entry.md')}",
                }
            ],
        }
        common_skill = {
            "name": "common",
            "files": [
                {
                    "source": "skills/common/SKILL.md",
                    "target": "SKILL.md",
                    "sha256": f"sha256:{sha256(common / 'SKILL.md')}",
                }
            ],
        }
        skills = [bridgeforge]
        if include_common:
            skills.insert(0, common_skill)
        manifest = {
            "schema_version": 1,
            "canonical_remote": CANONICAL_REMOTE,
            "branch": "main",
            "platforms": {
                "codex": {"target": "~/.codex/skills", "skills": skills},
                "claude": {"target": "~/.claude/skills", "skills": skills},
            },
        }
        (self.source / "shared-skill-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

    def initialize_repository(self) -> None:
        bare = run(["git", "init", "--bare", str(self.remote)], self.base)
        self.assertEqual(bare.returncode, 0, bare.stderr)
        commands = [
            ["git", "init", "-b", "main"],
            ["git", "config", "user.email", "tests@example.invalid"],
            ["git", "config", "user.name", "BridgeForge Tests"],
            ["git", "add", "."],
            ["git", "commit", "-m", "fixture"],
            ["git", "remote", "add", "publish", str(self.remote)],
            ["git", "push", "publish", "main"],
            ["git", "remote", "add", "origin", CANONICAL_REMOTE],
        ]
        for command in commands:
            result = run(command, self.source)
            self.assertEqual(result.returncode, 0, result.stderr)

    def commit_source(self, message: str, *, publish: bool = True) -> str:
        for command in (["git", "add", "."], ["git", "commit", "-m", message]):
            result = run(command, self.source)
            self.assertEqual(result.returncode, 0, result.stderr)
        if publish:
            result = run(["git", "push", "publish", "main"], self.source)
            self.assertEqual(result.returncode, 0, result.stderr)
        result = run(["git", "rev-parse", "HEAD"], self.source)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip().lower()

    def invoke_updater(
        self,
        *extra_arguments: str,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(UPDATER),
                "-SourceRepositoryRoot",
                str(self.source),
                *extra_arguments,
            ],
            ROOT,
            env=env or self.env,
        )

    def invoke_installer(
        self,
        *extra_arguments: str,
    ) -> subprocess.CompletedProcess[str]:
        return run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(INSTALLER),
                *extra_arguments,
            ],
            ROOT,
            env=self.env,
        )

    def ledger(self, platform: str) -> dict[str, object]:
        return json.loads(
            (self.profile / f".{platform}" / "bridgeforge-managed.json").read_text(
                encoding="utf-8-sig"
            )
        )

    def test_repository_manifest_matches_complete_product_inventory(self) -> None:
        manifest = json.loads(
            (ROOT / "shared-skill-manifest.json").read_text(encoding="utf-8-sig")
        )
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["canonical_remote"], CANONICAL_REMOTE)
        self.assertEqual(manifest["branch"], "main")

        expected_bundle = {
            "VERSION",
            "CHANGELOG.md",
            "skills/bridgeforge/SKILL.md",
            "skills/bridgeforge/references/adopt.md",
            "skills/bridgeforge/references/init.md",
            "skills/bridgeforge/references/switch.md",
            "skills/bridgeforge/references/update.md",
            "skills/bridgeforge/references/user-skill-maintenance.md",
        }
        for folder in ("templates",):
            expected_bundle.update(
                path.relative_to(ROOT).as_posix()
                for path in (ROOT / folder).rglob("*")
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
            )
        expected_bundle.update(
            {
                "scripts/bridgeforge_switch.py",
                "scripts/bridgeforge_migrate_layout.py",
                "scripts/bridgeforge_shared_update.ps1",
            }
        )
        required_project_memory_scripts = {
            "templates/codex/scripts/project_memory_writer.py",
            "templates/codex/scripts/project_memory_recovery.py",
            "templates/claude/scripts/project_memory_writer.py",
        }

        platform_skills: dict[str, dict[str, dict[str, object]]] = {}
        for platform, expected_target in (
            ("codex", "~/.codex/skills"),
            ("claude", "~/.claude/skills"),
        ):
            platform_manifest = manifest["platforms"][platform]
            self.assertEqual(platform_manifest["target"], expected_target)
            skills = {skill["name"]: skill for skill in platform_manifest["skills"]}
            self.assertEqual(len(skills), len(platform_manifest["skills"]))
            platform_skills[platform] = skills

            bridgeforge_files = {
                item["source"]: item for item in skills["bridgeforge"]["files"]
            }
            self.assertEqual(set(bridgeforge_files), expected_bundle)
            self.assertTrue(
                required_project_memory_scripts.issubset(bridgeforge_files),
                f"{platform} BridgeForge release bundle omits required project-memory scripts",
            )
            for source, item in bridgeforge_files.items():
                expected_target = source.removeprefix("skills/bridgeforge/")
                self.assertEqual(item["target"], expected_target)
                self.assertEqual(item["sha256"], f"sha256:{sha256(ROOT / source)}")

            expected_skill_names = {
                path.name
                for path in (ROOT / "skills").iterdir()
                if path.is_dir() and path.name != "bridgeforge"
            }
            self.assertEqual(set(skills) - {"bridgeforge"}, expected_skill_names)
            for name in expected_skill_names:
                skill_root = ROOT / "skills" / name
                expected_files = {
                    path.relative_to(skill_root).as_posix(): path
                    for path in skill_root.rglob("*")
                    if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
                }
                actual_files = {item["target"]: item for item in skills[name]["files"]}
                self.assertEqual(set(actual_files), set(expected_files), name)
                for target, source_path in expected_files.items():
                    item = actual_files[target]
                    self.assertEqual(item["source"], source_path.relative_to(ROOT).as_posix())
                    self.assertEqual(item["sha256"], f"sha256:{sha256(source_path)}")

        self.assertEqual(platform_skills["codex"], platform_skills["claude"])

    def test_installer_uses_lf_checkout_when_user_enables_autocrlf(self) -> None:
        self.write_source()
        (self.source / "entry.md").write_bytes(b"bridgeforge-v1\r\n")
        rebuilt = run(
            [sys.executable, str(MANIFEST_REBUILDER), "--manifest", str(self.source / "shared-skill-manifest.json")],
            ROOT,
        )
        self.assertEqual(rebuilt.returncode, 0, rebuilt.stderr + rebuilt.stdout)
        manifest = json.loads((self.source / "shared-skill-manifest.json").read_text(encoding="utf-8"))
        expected = "sha256:" + hashlib.sha256(b"bridgeforge-v1\n").hexdigest()
        bridgeforge = next(
            skill
            for skill in manifest["platforms"]["codex"]["skills"]
            if skill["name"] == "bridgeforge"
        )
        self.assertEqual(
            bridgeforge["files"][0]["sha256"],
            expected,
        )
        self.initialize_repository()

        self.env["GIT_CONFIG_COUNT"] = "2"
        self.env["GIT_CONFIG_KEY_1"] = "core.autocrlf"
        self.env["GIT_CONFIG_VALUE_1"] = "true"
        result = self.invoke_installer()

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        for platform in ("codex", "claude"):
            self.assertEqual(
                (self.profile / f".{platform}" / "skills" / "bridgeforge" / "SKILL.md").read_text(),
                "bridgeforge-v1\n",
            )

    def test_installs_both_platforms_and_preserves_third_party(self) -> None:
        self.write_source()
        self.initialize_repository()
        for platform in ("codex", "claude"):
            third_party = self.profile / f".{platform}" / "skills" / "third-party"
            third_party.mkdir(parents=True)
            (third_party / "SKILL.md").write_text("keep", encoding="utf-8")

        result = self.invoke_updater()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        commit = run(["git", "rev-parse", "HEAD"], self.source).stdout.strip().lower()
        for platform in ("codex", "claude"):
            skills = self.profile / f".{platform}" / "skills"
            self.assertEqual((skills / "bridgeforge" / "SKILL.md").read_text(), "bridgeforge-v1")
            self.assertEqual((skills / "common" / "SKILL.md").read_text(), "common-v1")
            self.assertEqual((skills / "third-party" / "SKILL.md").read_text(), "keep")
            ledger = self.ledger(platform)
            self.assertEqual(ledger["schema_version"], 1)
            self.assertEqual(ledger["platform"], platform)
            self.assertEqual(set(ledger["records"]), {"bridgeforge", "common"})
            self.assertTrue(
                all(record["source_commit"] == commit for record in ledger["records"].values())
            )
        self.assertFalse((self.profile / ".bridgeforge-shared-update.json").exists())

    def test_hash_mismatch_has_no_managed_target_writes(self) -> None:
        self.write_source()
        manifest_path = self.source / "shared-skill-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["platforms"]["claude"]["skills"][0]["files"][0]["sha256"] = "sha256:" + "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.initialize_repository()

        result = self.invoke_updater()
        self.assertNotEqual(result.returncode, 0)
        for platform in ("codex", "claude"):
            self.assertFalse((self.profile / f".{platform}" / "bridgeforge-managed.json").exists())
            self.assertFalse((self.profile / f".{platform}" / "skills" / "bridgeforge").exists())
            self.assertFalse((self.profile / f".{platform}" / "skills" / "common").exists())
        self.assertFalse((self.profile / ".bridgeforge-shared-update.json").exists())

    def test_forged_canonical_origin_without_fetchable_remote_is_rejected(self) -> None:
        self.write_source()
        self.initialize_repository()
        forged_env = self.env.copy()
        missing_remote = (self.base / "missing.git").as_uri()
        forged_env["GIT_CONFIG_KEY_0"] = f"url.{missing_remote}.insteadOf"

        result = self.invoke_updater(env=forged_env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("git fetch", result.stderr + result.stdout)
        self.assertIn("failed:", result.stderr + result.stdout)
        self.assertFalse((self.profile / ".codex").exists())
        self.assertFalse((self.profile / ".claude").exists())
        self.assertFalse((self.profile / ".bridgeforge-shared-update.json").exists())

    def test_head_not_equal_to_fetched_origin_main_is_rejected(self) -> None:
        self.write_source()
        self.initialize_repository()
        self.write_source(bridgeforge_text="unpublished")
        self.commit_source("unpublished local commit", publish=False)

        result = self.invoke_updater()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match", result.stderr + result.stdout)
        self.assertFalse((self.profile / ".codex").exists())
        self.assertFalse((self.profile / ".claude").exists())
        self.assertFalse((self.profile / ".bridgeforge-shared-update.json").exists())

    def test_unmanaged_same_name_blocks_both_platforms(self) -> None:
        self.write_source()
        self.initialize_repository()
        conflict = self.profile / ".claude" / "skills" / "common"
        conflict.mkdir(parents=True)
        (conflict / "SKILL.md").write_text("unmanaged", encoding="utf-8")

        result = self.invoke_updater()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((conflict / "SKILL.md").read_text(), "unmanaged")
        self.assertFalse((self.profile / ".codex" / "skills" / "bridgeforge").exists())
        self.assertFalse((self.profile / ".claude" / "skills" / "bridgeforge").exists())
        self.assertFalse((self.profile / ".bridgeforge-shared-update.json").exists())

    def test_update_overwrites_managed_content_and_removes_retired_skill(self) -> None:
        self.write_source()
        self.initialize_repository()
        first = self.invoke_updater()
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        for platform in ("codex", "claude"):
            managed = self.profile / f".{platform}" / "skills"
            (managed / "bridgeforge" / "SKILL.md").write_text("local-edit", encoding="utf-8")
            third_party = managed / "third-party"
            third_party.mkdir()
            (third_party / "SKILL.md").write_text("keep", encoding="utf-8")

        self.write_source(bridgeforge_text="bridgeforge-v2", include_common=False)
        new_commit = self.commit_source("update")
        second = self.invoke_updater()
        self.assertEqual(second.returncode, 0, second.stderr + second.stdout)

        for platform in ("codex", "claude"):
            skills = self.profile / f".{platform}" / "skills"
            self.assertEqual((skills / "bridgeforge" / "SKILL.md").read_text(), "bridgeforge-v2")
            self.assertFalse((skills / "common").exists())
            self.assertEqual((skills / "third-party" / "SKILL.md").read_text(), "keep")
            ledger = self.ledger(platform)
            self.assertEqual(set(ledger["records"]), {"bridgeforge"})
            self.assertEqual(ledger["records"]["bridgeforge"]["source_commit"], new_commit)

    def test_manifest_path_escape_is_rejected_before_target_writes(self) -> None:
        self.write_source()
        manifest_path = self.source / "shared-skill-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["platforms"]["codex"]["skills"][0]["files"][0]["target"] = "../escape.md"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.initialize_repository()

        result = self.invoke_updater()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.profile / ".codex").exists())
        self.assertFalse((self.profile / ".claude").exists())
        self.assertFalse((self.profile / "escape.md").exists())

    def test_real_swap_crash_is_recovered_before_next_update(self) -> None:
        self.write_source()
        self.initialize_repository()
        first = self.invoke_updater()
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        old_commit = self.ledger("codex")["records"]["bridgeforge"]["source_commit"]
        self.write_source(bridgeforge_text="bridgeforge-v2", common_text="common-v2")
        new_commit = self.commit_source("second")

        crashed = self.invoke_updater("-TestCrashAfterActionCount", "1")
        self.assertEqual(crashed.returncode, 91, crashed.stderr + crashed.stdout)
        self.assertTrue((self.profile / ".bridgeforge-shared-update.json").exists())
        self.assertEqual(
            (self.profile / ".codex" / "skills" / "common" / "SKILL.md").read_text(),
            "common-v2",
        )
        self.assertEqual(
            self.ledger("codex")["records"]["bridgeforge"]["source_commit"],
            old_commit,
        )

        result = self.invoke_updater()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        for platform in ("codex", "claude"):
            skills = self.profile / f".{platform}" / "skills"
            self.assertEqual((skills / "bridgeforge" / "SKILL.md").read_text(), "bridgeforge-v2")
            self.assertEqual((skills / "common" / "SKILL.md").read_text(), "common-v2")
            self.assertEqual(
                self.ledger(platform)["records"]["bridgeforge"]["source_commit"],
                new_commit,
            )
        self.assertFalse((self.profile / ".bridgeforge-shared-update.json").exists())
        self.assertFalse(
            any(
                "bridgeforge-backup" in path.name
                for path in (self.profile / ".codex" / "skills").iterdir()
            )
        )

    def test_claude_first_swap_failure_rolls_back_after_codex_completed(self) -> None:
        self.write_source()
        self.initialize_repository()
        first = self.invoke_updater()
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        old_commit = self.ledger("codex")["records"]["bridgeforge"]["source_commit"]
        self.assertEqual(
            set(self.ledger("codex")["records"]),
            {"common", "bridgeforge"},
            "fixture must have exactly two Codex actions",
        )

        self.write_source(bridgeforge_text="bridgeforge-v2", common_text="common-v2")
        new_commit = self.commit_source("cross-platform transaction")
        failed = self.invoke_updater("-TestFailAfterSwap", "claude:1")
        output = failed.stderr + failed.stdout
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("after swap claude:1", output)
        self.assertIn("actions: 3.", output)

        # The injected failure occurs after two Codex swaps and the first Claude
        # swap. The normal catch path must roll back both platforms immediately.
        self.assertFalse((self.profile / ".bridgeforge-shared-update.json").exists())
        for platform in ("codex", "claude"):
            skills = self.profile / f".{platform}" / "skills"
            self.assertEqual((skills / "bridgeforge" / "SKILL.md").read_text(), "bridgeforge-v1")
            self.assertEqual((skills / "common" / "SKILL.md").read_text(), "common-v1")
            ledger = self.ledger(platform)
            self.assertTrue(
                all(record["source_commit"] == old_commit for record in ledger["records"].values())
            )
            self.assertFalse(
                any(
                    "bridgeforge-backup" in path.name or "bridgeforge-stage" in path.name
                    for path in skills.iterdir()
                )
            )

        recovered = self.invoke_updater()
        self.assertEqual(recovered.returncode, 0, recovered.stderr + recovered.stdout)
        for platform in ("codex", "claude"):
            skills = self.profile / f".{platform}" / "skills"
            self.assertEqual((skills / "bridgeforge" / "SKILL.md").read_text(), "bridgeforge-v2")
            self.assertEqual((skills / "common" / "SKILL.md").read_text(), "common-v2")
            ledger = self.ledger(platform)
            self.assertTrue(
                all(record["source_commit"] == new_commit for record in ledger["records"].values())
            )
        self.assertEqual(
            self.ledger("codex")["records"]["bridgeforge"]["source_commit"],
            self.ledger("claude")["records"]["bridgeforge"]["source_commit"],
        )

    def test_invalid_target_parent_is_preflighted_before_other_platform_changes(self) -> None:
        self.write_source()
        self.initialize_repository()
        (self.profile / ".claude").write_text("not-a-directory", encoding="utf-8")

        result = self.invoke_updater()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.profile / ".codex").exists())
        self.assertEqual((self.profile / ".claude").read_text(), "not-a-directory")
        self.assertFalse((self.profile / ".bridgeforge-shared-update.json").exists())

    def test_non_windows_guards_exit_before_distribution_writes(self) -> None:
        self.write_source()
        self.initialize_repository()

        updater = self.invoke_updater("-TestNonWindows")
        installer = self.invoke_installer("-TestNonWindows")
        self.assertNotEqual(updater.returncode, 0)
        self.assertNotEqual(installer.returncode, 0)
        self.assertIn("supports Windows", updater.stderr + updater.stdout)
        self.assertIn("supports Windows", installer.stderr + installer.stdout)
        self.assertFalse((self.profile / ".codex").exists())
        self.assertFalse((self.profile / ".claude").exists())
        self.assertFalse((self.profile / ".bridgeforge-shared-update.json").exists())

    def test_installer_uses_fetched_main_and_preserves_unverified_junction(self) -> None:
        self.write_source()
        self.initialize_repository()
        invalid_target = self.base / "not-a-repository"
        invalid_target.mkdir()
        legacy = self.profile / ".bridgeforge"
        linked = run(
            ["cmd.exe", "/c", "mklink", "/J", str(legacy), str(invalid_target)],
            self.base,
        )
        self.assertEqual(linked.returncode, 0, linked.stderr + linked.stdout)
        try:
            result = self.invoke_installer()
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue(legacy.exists())
            self.assertIn("left unchanged", result.stderr + result.stdout)
            for platform in ("codex", "claude"):
                self.assertEqual(
                    (
                        self.profile
                        / f".{platform}"
                        / "skills"
                        / "bridgeforge"
                        / "SKILL.md"
                    ).read_text(),
                    "bridgeforge-v1",
                )
        finally:
            if legacy.exists():
                os.rmdir(legacy)


if __name__ == "__main__":
    unittest.main()
