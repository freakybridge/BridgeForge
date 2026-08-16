from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "bridgeforge-codex-manifest.json"
COMPATIBILITY_MANIFEST = ROOT / "shared-skill-manifest.json"
UPDATER = ROOT / "scripts/bridgeforge_codex_shared_update.ps1"
CANONICAL_REMOTE = "https://github.com/freakybridge/BridgeForgeCodex.git"
LEGACY_REMOTE = "https://github.com/freakybridge/BridgeForge.git"
LEGACY_UPDATER_REVISION = "1e4124358a5d0c6cee9dd73bcb7b18bc904515c9"


def sha256(path: Path) -> str:
    payload = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def tree_hash(files: dict[str, bytes]) -> str:
    lines = [
        f"{name}\n{hashlib.sha256(payload).hexdigest()}"
        for name, payload in files.items()
    ]
    return "sha256:" + hashlib.sha256(
        ("\n".join(sorted(lines)) + "\n").encode("utf-8")
    ).hexdigest()


def run(
    command: list[str],
    cwd: Path,
    *,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
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
    def test_manifest_exposes_one_active_codex_product(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
        self.assertEqual(
            manifest["canonical_remote"],
            "https://github.com/freakybridge/BridgeForgeCodex.git",
        )
        self.assertEqual(set(manifest["platforms"]), {"codex"})
        codex = manifest["platforms"]["codex"]
        self.assertFalse(any(item.get("legacy_transition") for item in codex["skills"]))
        self.assertIn("bridgeforge-codex", {item["name"] for item in codex["skills"]})
        command = next(item for item in codex["skills"] if item["name"] == "bridgeforge-codex")
        self.assertEqual(
            {file["target"] for file in command["files"]},
            {
                "SKILL.md",
                "references/adopt.md",
                "references/init.md",
                "references/update.md",
                "references/user-skill-maintenance.md",
                "scripts/bridgeforge_codex_shared_update.ps1",
            },
        )
        self.assertNotIn(
            "templates/AGENTS.md",
            {file["source"] for file in command["files"]},
        )
        self.assertEqual(codex["target"], "~/.codex/skills")

    def test_compatibility_manifest_freezes_legacy_payloads(self) -> None:
        manifest = json.loads(COMPATIBILITY_MANIFEST.read_text(encoding="utf-8-sig"))
        self.assertEqual(manifest["canonical_remote"], LEGACY_REMOTE)
        self.assertEqual(manifest["product_remote"], CANONICAL_REMOTE)
        claude = manifest["platforms"]["claude"]
        self.assertTrue(claude["retired_compatibility_surface"])
        self.assertTrue(claude["skills"])
        self.assertTrue(all(item["legacy_transition"] for item in claude["skills"]))
        item = next(item for item in claude["skills"] if item["name"] == "bridgeforge")
        self.assertEqual(
            {file["source"] for file in item["files"]},
            {"scripts/bridgeforge_codex_legacy_entry.SKILL.md"},
        )
        pinned = json.loads(
            run(
                ["git", "show", f"{LEGACY_UPDATER_REVISION}:shared-skill-manifest.json"],
                ROOT,
            ).stdout
        )
        for platform in ("codex", "claude"):
            actual = {
                skill["name"]: {file["target"]: file["sha256"] for file in skill["files"]}
                for skill in manifest["platforms"][platform]["skills"]
            }
            expected = {
                skill["name"]: {file["target"]: file["sha256"] for file in skill["files"]}
                for skill in pinned["platforms"][platform]["skills"]
                if skill["name"] != "bridgeforge"
            }
            for name, files in expected.items():
                self.assertEqual(actual[name], files)

    def test_new_updater_plans_only_codex_and_uses_new_ledger(self) -> None:
        text = UPDATER.read_text(encoding="utf-8-sig")
        self.assertIn("bridgeforge-codex-managed.json", text)
        self.assertIn("BRIDGEFORGE_CODEX_SHARED_UPDATE_RECEIPT", text)
        self.assertIn("BridgeForgeCodex.git", text)
        self.assertIn('$CommandHomeName = ".bridgeforge-codex"', text)
        self.assertIn('$ManifestName = "bridgeforge-codex-manifest.json"', text)
        self.assertIn('foreach ($platform in @("codex"))', text)

    def test_removed_distribution_entries_are_absent(self) -> None:
        for relative in (
            "scripts/bridgeforge_shared_update.ps1",
            "scripts/bridgeforge_user_maintenance.ps1",
            "scripts/claude_bridgeforge_entry.SKILL.md",
            "scripts/setup-junction.ps1",
            "scripts/setup-junction.sh",
        ):
            self.assertFalse((ROOT / relative).exists(), relative)

    def test_manifest_rebuild_check_is_read_only_and_current(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/rebuild_shared_skill_manifest.py", "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(sys.platform == "win32", "PowerShell parser is Windows-only")
    def test_powershell_entrypoints_parse(self) -> None:
        for script in (
            UPDATER,
            ROOT / "scripts/install-shared-skills.ps1",
        ):
            with self.subTest(script=script):
                command = (
                    "$text=[IO.File]::ReadAllText('"
                    + str(script).replace("'", "''")
                    + "'); [void][scriptblock]::Create($text)"
                )
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", command],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless(os.name == "nt", "Windows-only updater integration")
class SharedSkillUpdaterIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        if shutil.which("git") is None or shutil.which("powershell.exe") is None:
            self.skipTest("git and Windows PowerShell are required")
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.profile = self.base / "profile"
        self.source = self.base / "source"
        self.remote = self.base / "canonical.git"
        self.profile.mkdir()
        self.source.mkdir()
        self.env = os.environ.copy()
        self.env["USERPROFILE"] = str(self.profile)
        system_root = self.env.get("SystemRoot", r"C:\Windows")
        self.env["PSModulePath"] = os.pathsep.join(
            (
                r"C:\Program Files\WindowsPowerShell\Modules",
                str(
                    Path(system_root)
                    / "system32"
                    / "WindowsPowerShell"
                    / "v1.0"
                    / "Modules"
                ),
            )
        )
        self.env["GIT_CONFIG_COUNT"] = "2"
        self.env["GIT_CONFIG_KEY_0"] = f"url.{self.remote.as_uri()}.insteadOf"
        self.env["GIT_CONFIG_VALUE_0"] = CANONICAL_REMOTE
        self.env["GIT_CONFIG_KEY_1"] = f"url.{self.remote.as_uri()}.insteadOf"
        self.env["GIT_CONFIG_VALUE_1"] = LEGACY_REMOTE

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_source(self, entry: str = "entry-v1", common: str = "common-v1") -> None:
        (self.source / ".gitattributes").write_text("* text=auto eol=lf\n", encoding="utf-8")
        skill = self.source / "skills/bridgeforge-codex"
        scripts = self.source / "scripts"
        common_root = self.source / "skills/common"
        harvest_root = self.source / "skills/harvest"
        skill.mkdir(parents=True, exist_ok=True)
        scripts.mkdir(parents=True, exist_ok=True)
        common_root.mkdir(parents=True, exist_ok=True)
        harvest_root.mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text(entry, encoding="utf-8")
        (common_root / "SKILL.md").write_text(common, encoding="utf-8")
        (harvest_root / "SKILL.md").write_text("retired-harvest", encoding="utf-8")
        shutil.copy2(UPDATER, scripts / UPDATER.name)
        (self.source / "legacy.md").write_text("legacy-entry", encoding="utf-8")
        active = {
            "name": "bridgeforge-codex",
            "files": [
                {
                    "source": "skills/bridgeforge-codex/SKILL.md",
                    "target": "SKILL.md",
                    "sha256": sha256(skill / "SKILL.md"),
                },
                {
                    "source": "scripts/bridgeforge_codex_shared_update.ps1",
                    "target": "scripts/bridgeforge_codex_shared_update.ps1",
                    "sha256": sha256(scripts / UPDATER.name),
                },
            ],
        }
        common_skill = {
            "name": "common",
            "files": [
                {
                    "source": "skills/common/SKILL.md",
                    "target": "SKILL.md",
                    "sha256": sha256(common_root / "SKILL.md"),
                }
            ],
        }
        legacy = {
            "name": "bridgeforge",
            "legacy_transition": True,
            "files": [
                {
                    "source": "legacy.md",
                    "target": "SKILL.md",
                    "sha256": sha256(self.source / "legacy.md"),
                }
            ],
        }
        harvest = {
            "name": "harvest",
            "legacy_transition": True,
            "files": [
                {
                    "source": "skills/harvest/SKILL.md",
                    "target": "SKILL.md",
                    "sha256": sha256(harvest_root / "SKILL.md"),
                }
            ],
        }
        compatibility_manifest = {
            "schema_version": 1,
            "canonical_remote": LEGACY_REMOTE,
            "product_remote": CANONICAL_REMOTE,
            "branch": "main",
            "platforms": {
                "codex": {
                    "target": "~/.codex/skills",
                    "skills": [common_skill, active, legacy, harvest],
                },
                "claude": {
                    "target": "~/.claude/skills",
                    "skills": [common_skill, legacy, harvest],
                },
            },
        }
        (self.source / "shared-skill-manifest.json").write_text(
            json.dumps(compatibility_manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        active_manifest = {
            "schema_version": 1,
            "canonical_remote": CANONICAL_REMOTE,
            "branch": "main",
            "platforms": {
                "codex": {
                    "target": "~/.codex/skills",
                    "skills": [common_skill, active],
                }
            },
        }
        (self.source / "bridgeforge-codex-manifest.json").write_text(
            json.dumps(active_manifest, indent=2) + "\n",
            encoding="utf-8",
        )

    def write_repository_distribution(self) -> None:
        """Copy the exact release manifests and every referenced payload."""
        (self.source / ".gitattributes").write_text(
            "* text=auto eol=lf\n",
            encoding="utf-8",
        )
        for manifest_path in (MANIFEST, COMPATIBILITY_MANIFEST):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            shutil.copy2(manifest_path, self.source / manifest_path.name)
            for platform in manifest["platforms"].values():
                for skill in platform["skills"]:
                    for file in skill["files"]:
                        source = ROOT / file["source"]
                        target = self.source / file["source"]
                        target.parent.mkdir(parents=True, exist_ok=True)
                        payload = source.read_bytes().replace(b"\r\n", b"\n").replace(
                            b"\r", b"\n"
                        )
                        if target.exists():
                            self.assertEqual(target.read_bytes(), payload)
                        else:
                            target.write_bytes(payload)

    def initialize_repository(self) -> None:
        self.assertEqual(run(["git", "init", "--bare", str(self.remote)], self.base).returncode, 0)
        commands = (
            ["git", "init", "-b", "main"],
            ["git", "config", "user.email", "tests@example.invalid"],
            ["git", "config", "user.name", "BridgeForgeCodex Tests"],
            ["git", "add", "."],
            ["git", "commit", "-m", "fixture"],
            ["git", "remote", "add", "publish", str(self.remote)],
            ["git", "push", "publish", "main"],
            ["git", "remote", "add", "origin", CANONICAL_REMOTE],
        )
        for command in commands:
            result = run(command, self.source)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def commit_source(self, message: str) -> str:
        for command in (
            ["git", "add", "."],
            ["git", "commit", "-m", message],
            ["git", "push", "publish", "main"],
        ):
            result = run(command, self.source)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return run(["git", "rev-parse", "HEAD"], self.source).stdout.strip().lower()

    def invoke(self, *extra: str) -> subprocess.CompletedProcess[str]:
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
                *extra,
            ],
            ROOT,
            env=self.env,
        )

    def receipt(self, result: subprocess.CompletedProcess[str]) -> dict[str, object]:
        prefix = "BRIDGEFORGE_CODEX_SHARED_UPDATE_RECEIPT "
        matches = [line for line in result.stdout.splitlines() if line.startswith(prefix)]
        self.assertEqual(len(matches), 1, result.stderr + result.stdout)
        return json.loads(matches[0][len(prefix) :])

    def ledger(self) -> dict[str, object]:
        return json.loads(
            (self.profile / ".codex/bridgeforge-codex-managed.json").read_text(
                encoding="utf-8-sig"
            )
        )

    def test_installs_independent_home_thin_entry_and_preserves_third_party(self) -> None:
        self.write_source()
        self.initialize_repository()
        third_party = self.profile / ".codex/skills/third-party"
        third_party.mkdir(parents=True)
        (third_party / "SKILL.md").write_text("keep", encoding="utf-8")
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        home = self.profile / ".bridgeforge-codex"
        self.assertTrue((home / ".git").is_dir())
        self.assertEqual(
            run(["git", "remote", "get-url", "origin"], home).stdout.strip(),
            CANONICAL_REMOTE,
        )
        entry = self.profile / ".codex/skills/bridgeforge-codex"
        self.assertEqual((entry / "SKILL.md").read_text(), "entry-v1")
        self.assertTrue((entry / "scripts/bridgeforge_codex_shared_update.ps1").is_file())
        self.assertFalse((entry / "templates").exists())
        self.assertEqual((third_party / "SKILL.md").read_text(), "keep")
        self.assertEqual(set(self.ledger()["records"]), {"bridgeforge-codex", "common"})

    def test_identical_rerun_is_noop(self) -> None:
        self.write_source()
        self.initialize_repository()
        self.assertEqual(self.invoke().returncode, 0)
        second = self.invoke("-TestFailAfterSwap", "codex:1")
        self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
        self.assertEqual(self.receipt(second)["mode"], "noop")
        self.assertEqual(self.receipt(second)["action_count"], 0)

    def test_legacy_ledger_owned_bootstrap_is_adopted(self) -> None:
        self.write_source()
        self.initialize_repository()
        entry_files = {
            "SKILL.md": b"entry-v1",
            "scripts/bridgeforge_codex_shared_update.ps1": (UPDATER.read_bytes()),
        }
        entry = self.profile / ".codex/skills/bridgeforge-codex"
        for relative, payload in entry_files.items():
            target = entry / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
        legacy_ledger = self.profile / ".codex/bridgeforge-managed.json"
        legacy_ledger.parent.mkdir(parents=True, exist_ok=True)
        legacy_ledger.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "platform": "codex",
                    "records": {
                        "bridgeforge-codex": {
                            "source_commit": "a" * 40,
                            "content_hash": tree_hash(entry_files),
                            "installed_at": "legacy-bootstrap",
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("bridgeforge-codex", self.ledger()["records"])
        self.assertTrue((self.profile / ".bridgeforge-codex/.git").is_dir())

    def test_real_legacy_updater_handoff_preserves_old_surfaces_then_adopts(self) -> None:
        self.write_repository_distribution()
        self.initialize_repository()
        legacy_script = self.base / "bridgeforge_shared_update.ps1"
        exported = run(
            [
                "git",
                "show",
                f"{LEGACY_UPDATER_REVISION}:scripts/bridgeforge_shared_update.ps1",
            ],
            ROOT,
        )
        self.assertEqual(exported.returncode, 0, exported.stderr)
        legacy_script.write_text(exported.stdout, encoding="utf-8", newline="\n")

        compatibility = json.loads(
            (self.source / COMPATIBILITY_MANIFEST.name).read_text(encoding="utf-8-sig")
        )
        snapshots: dict[str, dict[str, dict[str, bytes]]] = {}
        for platform in ("codex", "claude"):
            target_root = self.profile / f".{platform}/skills"
            records: dict[str, object] = {}
            snapshots[platform] = {}
            for skill in compatibility["platforms"][platform]["skills"]:
                name = skill["name"]
                if name == "bridgeforge-codex":
                    continue
                files = (
                    {"SKILL.md": b"legacy-original"}
                    if name == "bridgeforge"
                    else {
                        file["target"]: (self.source / file["source"]).read_bytes()
                        for file in skill["files"]
                    }
                )
                for relative, payload in files.items():
                    target = target_root / name / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(payload)
                snapshots[platform][name] = files
                records[name] = {
                    "source_commit": "a" * 40,
                    "content_hash": tree_hash(files),
                    "installed_at": "legacy",
                }
            ledger = self.profile / f".{platform}/bridgeforge-managed.json"
            ledger.write_text(
                json.dumps({
                    "schema_version": 1,
                    "platform": platform,
                    "records": records,
                    **(
                        {"consents": {"native_memories": "declined"}}
                        if platform == "codex"
                        else {}
                    ),
                }),
                encoding="utf-8",
            )

        changed_remote = run(
            ["git", "remote", "set-url", "origin", LEGACY_REMOTE],
            self.source,
        )
        self.assertEqual(changed_remote.returncode, 0, changed_remote.stderr)
        old_result = run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(legacy_script),
                "-SourceRepositoryRoot",
                str(self.source),
            ],
            ROOT,
            env=self.env,
        )
        self.assertEqual(old_result.returncode, 0, old_result.stderr + old_result.stdout)
        for platform in ("codex", "claude"):
            target_root = self.profile / f".{platform}/skills"
            for name, files in snapshots[platform].items():
                if name == "bridgeforge":
                    continue
                for relative, payload in files.items():
                    self.assertEqual(
                        (target_root / name / relative).read_bytes(),
                        payload,
                        f"legacy updater rewrote {platform}/{name}/{relative}",
                    )
            old_ledger = json.loads(
                (self.profile / f".{platform}/bridgeforge-managed.json").read_text(
                    encoding="utf-8-sig"
                )
            )
            self.assertTrue(set(snapshots[platform]).issubset(old_ledger["records"]))
        self.assertTrue((self.profile / ".codex/skills/bridgeforge-codex/SKILL.md").is_file())

        changed_remote = run(
            ["git", "remote", "set-url", "origin", CANONICAL_REMOTE],
            self.source,
        )
        self.assertEqual(changed_remote.returncode, 0, changed_remote.stderr)
        new_result = self.invoke()
        self.assertEqual(new_result.returncode, 0, new_result.stderr + new_result.stdout)
        active = json.loads(
            (self.source / MANIFEST.name).read_text(encoding="utf-8-sig")
        )
        self.assertEqual(
            set(self.ledger()["records"]),
            {skill["name"] for skill in active["platforms"]["codex"]["skills"]},
        )
        self.assertEqual(
            self.ledger()["consents"],
            {"native_memories": "declined"},
        )
        self.assertTrue((self.profile / ".bridgeforge-codex/.git").is_dir())

    def test_hash_mismatch_and_unmanaged_conflict_leave_no_home(self) -> None:
        self.write_source()
        manifest_path = self.source / "bridgeforge-codex-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["platforms"]["codex"]["skills"][0]["files"][0]["sha256"] = (
            "sha256:" + "0" * 64
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.initialize_repository()
        bad_hash = self.invoke()
        self.assertNotEqual(bad_hash.returncode, 0)
        self.assertFalse((self.profile / ".bridgeforge-codex").exists())
        self.assertFalse((self.profile / ".codex").exists())

    def test_unmanaged_conflict_rolls_back_staged_home(self) -> None:
        self.write_source()
        self.initialize_repository()
        conflict = self.profile / ".codex/skills/common"
        conflict.mkdir(parents=True)
        (conflict / "SKILL.md").write_text("mine", encoding="utf-8")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((conflict / "SKILL.md").read_text(), "mine")
        self.assertFalse((self.profile / ".bridgeforge-codex").exists())
        self.assertFalse((self.profile / ".bridgeforge-codex-home-update.json").exists())

    def test_crash_recovers_both_home_and_skill_transaction(self) -> None:
        self.write_source()
        self.initialize_repository()
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        self.write_source(entry="entry-v2", common="common-v2")
        new_commit = self.commit_source("second")
        crashed = self.invoke("-TestCrashAfterActionCount", "1")
        self.assertEqual(crashed.returncode, 91, crashed.stderr + crashed.stdout)
        self.assertTrue((self.profile / ".bridgeforge-codex-home-update.json").is_file())
        recovered = self.invoke()
        self.assertEqual(recovered.returncode, 0, recovered.stderr + recovered.stdout)
        home = self.profile / ".bridgeforge-codex"
        self.assertEqual(run(["git", "rev-parse", "HEAD"], home).stdout.strip(), new_commit)
        self.assertEqual(
            (self.profile / ".codex/skills/common/SKILL.md").read_text(),
            "common-v2",
        )
        self.assertFalse((self.profile / ".bridgeforge-codex-home-update.json").exists())
        self.assertFalse((self.profile / ".bridgeforge-codex-shared-update.json").exists())

    def test_injected_skill_failure_restores_previous_home(self) -> None:
        self.write_source()
        self.initialize_repository()
        self.assertEqual(self.invoke().returncode, 0)
        home = self.profile / ".bridgeforge-codex"
        old_commit = run(["git", "rev-parse", "HEAD"], home).stdout.strip()
        self.write_source(entry="entry-v2", common="common-v2")
        self.commit_source("second")
        failed = self.invoke("-TestFailAfterSwap", "codex:1")
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(run(["git", "rev-parse", "HEAD"], home).stdout.strip(), old_commit)
        self.assertEqual(
            (self.profile / ".codex/skills/common/SKILL.md").read_text(),
            "common-v1",
        )
        self.assertFalse((self.profile / ".bridgeforge-codex-home-update.json").exists())


if __name__ == "__main__":
    unittest.main()
