from __future__ import annotations

import importlib.util
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
UPDATER = ROOT / "scripts/bridgeforge_codex_shared_update.ps1"
CANONICAL_REMOTE = "https://github.com/freakybridge/BridgeForgeCodex.git"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MANIFEST_BUILDER = load_module(
    "bridgeforge_strict_manifest_builder",
    ROOT / "scripts" / "rebuild_shared_skill_manifest.py",
)


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
    def test_contract_builder_rejects_noncanonical_windows_target(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "managed-skeleton.json"
            contract = json.loads(
                (ROOT / "templates" / "managed-skeleton.json").read_text(encoding="utf-8")
            )
            asset = next(item for item in contract["assets"] if "/" in item["target"])
            asset["target"] = str(asset["target"]).replace("/", "\\")
            path.write_text(json.dumps(contract), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "POSIX relative path"):
                MANIFEST_BUILDER.rebuild_managed_contract(path, write=False)

    def test_manifest_exposes_one_active_codex_product(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
        self.assertEqual(
            manifest["canonical_remote"],
            "https://github.com/freakybridge/BridgeForgeCodex.git",
        )
        self.assertEqual(set(manifest["platforms"]), {"codex"})
        codex = manifest["platforms"]["codex"]
        self.assertTrue(all("legacy_transition" not in item for item in codex["skills"]))
        self.assertIn("bridgeforge-codex", {item["name"] for item in codex["skills"]})
        command = next(item for item in codex["skills"] if item["name"] == "bridgeforge-codex")
        self.assertEqual(
            {file["target"] for file in command["files"]},
            {
                "SKILL.md",
                "agents/openai.yaml",
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

    def test_legacy_compatibility_distribution_is_absent(self) -> None:
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
        installer = (ROOT / "scripts/install-shared-skills.ps1").read_text(
            encoding="utf-8-sig"
        )
        self.assertNotIn("Remove-VerifiedLegacyJunction", installer)
        self.assertNotIn('Join-Path $UserProfile ".bridgeforge"', installer)

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

    def test_manifest_builder_rejects_non_exact_or_duplicate_schema(self) -> None:
        original = MANIFEST.read_text(encoding="utf-8-sig")
        mutations = {
            "duplicate-key": original.replace(
                '"schema_version": 1,',
                '"schema_version": 1,\n  "schema_version": 1,',
                1,
            ),
            "unknown-field": json.dumps(
                {**json.loads(original), "legacy_history": []},
                ensure_ascii=False,
            ),
            "wrong-schema": json.dumps(
                {**json.loads(original), "schema_version": 99},
                ensure_ascii=False,
            ),
            "wrong-platform": json.dumps(
                {
                    **json.loads(original),
                    "platforms": {
                        **json.loads(original)["platforms"],
                        "claude": {},
                    },
                },
                ensure_ascii=False,
            ),
        }
        for label, payload in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as raw:
                path = Path(raw) / MANIFEST.name
                path.write_text(payload, encoding="utf-8")
                with self.assertRaises(ValueError):
                    MANIFEST_BUILDER.rebuild_manifest(path, write=False)

    def test_manifest_builder_rejects_normalized_duplicate_target(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
        files = manifest["platforms"]["codex"]["skills"][0]["files"]
        duplicate = dict(files[0])
        duplicate["source"] = files[1]["source"]
        duplicate["target"] = files[0]["target"].upper()
        files.append(duplicate)
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / MANIFEST.name
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate target"):
                MANIFEST_BUILDER.rebuild_manifest(path, write=False)

    def test_manifest_builder_requires_bridgeforge_command_bundle(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
        manifest["platforms"]["codex"]["skills"] = []
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / MANIFEST.name
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "must include bridgeforge-codex"):
                MANIFEST_BUILDER.validate_manifest_path(path)

    def test_manifest_check_does_not_write_validator_bytecode(self) -> None:
        cache_root = ROOT / "templates" / "scripts" / "__pycache__"

        def snapshot() -> dict[str, tuple[bytes, int]]:
            if not cache_root.is_dir():
                return {}
            return {
                path.name: (path.read_bytes(), path.stat().st_mtime_ns)
                for path in cache_root.iterdir()
                if path.is_file()
            }

        before = snapshot()
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/rebuild_shared_skill_manifest.py"), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(snapshot(), before)

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
        self.env["GIT_CONFIG_COUNT"] = "1"
        self.env["GIT_CONFIG_KEY_0"] = f"url.{self.remote.as_uri()}.insteadOf"
        self.env["GIT_CONFIG_VALUE_0"] = CANONICAL_REMOTE

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_source(self, entry: str = "entry-v1", common: str = "common-v1") -> None:
        (self.source / ".gitattributes").write_text("* text=auto eol=lf\n", encoding="utf-8")
        skill = self.source / "skills/bridgeforge-codex"
        scripts = self.source / "scripts"
        common_root = self.source / "skills/common"
        skill.mkdir(parents=True, exist_ok=True)
        scripts.mkdir(parents=True, exist_ok=True)
        common_root.mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text(entry, encoding="utf-8")
        (common_root / "SKILL.md").write_text(common, encoding="utf-8")
        shutil.copy2(UPDATER, scripts / UPDATER.name)
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

    def test_updater_rejects_duplicate_manifest_keys(self) -> None:
        self.write_source()
        manifest = self.source / "bridgeforge-codex-manifest.json"
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(
            text.replace(
                '"schema_version": 1,',
                '"schema_version": 1,\n  "schema_version": 1,',
                1,
            ),
            encoding="utf-8",
        )
        self.initialize_repository()

        result = self.invoke()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate JSON key", result.stderr + result.stdout)
        self.assertFalse((self.profile / ".codex/bridgeforge-codex-managed.json").exists())

    def test_updater_rejects_extra_manifest_platform(self) -> None:
        self.write_source()
        manifest_path = self.source / "bridgeforge-codex-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["platforms"]["claude"] = {
            "target": "~/.claude/skills",
            "skills": [],
        }
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        self.initialize_repository()

        result = self.invoke()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fields are not exact", result.stderr + result.stdout)
        self.assertFalse((self.profile / ".codex/bridgeforge-codex-managed.json").exists())

    def test_updater_rejects_unknown_manifest_file_field(self) -> None:
        self.write_source()
        manifest_path = self.source / "bridgeforge-codex-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["platforms"]["codex"]["skills"][0]["files"][0]["legacy"] = True
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        self.initialize_repository()

        result = self.invoke()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fields are not exact", result.stderr + result.stdout)
        self.assertFalse((self.profile / ".codex/bridgeforge-codex-managed.json").exists())

    def test_updater_requires_prefixed_lowercase_manifest_hash(self) -> None:
        self.write_source()
        manifest_path = self.source / "bridgeforge-codex-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        item = manifest["platforms"]["codex"]["skills"][0]["files"][0]
        item["sha256"] = item["sha256"].removeprefix("sha256:")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        self.initialize_repository()

        result = self.invoke()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid SHA-256", result.stderr + result.stdout)

    def test_updater_requires_lowercase_skill_name(self) -> None:
        self.write_source()
        manifest_path = self.source / "bridgeforge-codex-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["platforms"]["codex"]["skills"][0]["name"] = "Common"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        self.initialize_repository()

        result = self.invoke()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unsafe skill name", result.stderr + result.stdout)

    def test_identical_rerun_is_noop(self) -> None:
        self.write_source()
        self.initialize_repository()
        self.assertEqual(self.invoke().returncode, 0)
        second = self.invoke("-TestFailAfterSwap", "codex:1")
        self.assertEqual(second.returncode, 0, second.stderr + second.stdout)
        self.assertEqual(self.receipt(second)["mode"], "noop")
        self.assertEqual(self.receipt(second)["action_count"], 0)

    def test_structured_native_memory_consent_survives_skill_refresh(self) -> None:
        self.write_source()
        self.initialize_repository()
        self.assertEqual(self.invoke().returncode, 0)
        ledger_path = self.profile / ".codex/bridgeforge-codex-managed.json"
        ledger = self.ledger()
        authorization = {
            "decision": "approved",
            "policy_version": 1,
            "scope": "~/.codex/memories/**",
            "sync_mode": "bidirectional",
            "auto_hook_maintenance": True,
            "repository": "bridgeforge-codex-memories",
            "require_private": True,
            "remote": "https://github.com/example/bridgeforge-codex-memories",
        }
        ledger["consents"] = {"native_memories": authorization}
        ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
        self.write_source(entry="entry-v2")
        self.commit_source("refresh entry")
        refreshed = self.invoke()
        self.assertEqual(refreshed.returncode, 0, refreshed.stderr + refreshed.stdout)
        self.assertEqual(
            self.ledger()["consents"],
            {"native_memories": authorization},
        )

    def test_modified_managed_active_skill_blocks_refresh_without_writes(self) -> None:
        self.write_source()
        self.initialize_repository()
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        home = self.profile / ".bridgeforge-codex"
        old_commit = run(["git", "rev-parse", "HEAD"], home).stdout.strip()
        ledger_path = self.profile / ".codex/bridgeforge-codex-managed.json"
        ledger_before = ledger_path.read_bytes()
        installed = self.profile / ".codex/skills/common/SKILL.md"
        installed.write_text("local customization", encoding="utf-8")

        self.write_source(entry="entry-v2", common="common-v2")
        self.commit_source("refresh after local drift")
        blocked = self.invoke()

        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("content drifted", blocked.stderr + blocked.stdout)
        self.assertEqual(installed.read_text(encoding="utf-8"), "local customization")
        self.assertEqual(ledger_path.read_bytes(), ledger_before)
        self.assertEqual(run(["git", "rev-parse", "HEAD"], home).stdout.strip(), old_commit)
        self.assertFalse((self.profile / ".bridgeforge-codex-home-update.json").exists())
        self.assertFalse((self.profile / ".bridgeforge-codex-shared-update.json").exists())

    def test_modified_managed_skill_blocks_manifest_retirement_without_writes(self) -> None:
        self.write_source()
        self.initialize_repository()
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        home = self.profile / ".bridgeforge-codex"
        old_commit = run(["git", "rev-parse", "HEAD"], home).stdout.strip()
        ledger_path = self.profile / ".codex/bridgeforge-codex-managed.json"
        ledger_before = ledger_path.read_bytes()
        installed = self.profile / ".codex/skills/common/SKILL.md"
        installed.write_text("project-owned now", encoding="utf-8")

        manifest_path = self.source / "bridgeforge-codex-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["platforms"]["codex"]["skills"] = [
            skill
            for skill in manifest["platforms"]["codex"]["skills"]
            if skill["name"] != "common"
        ]
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        self.commit_source("retire common after local drift")
        blocked = self.invoke()

        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("content drifted", blocked.stderr + blocked.stdout)
        self.assertEqual(installed.read_text(encoding="utf-8"), "project-owned now")
        self.assertEqual(ledger_path.read_bytes(), ledger_before)
        self.assertEqual(run(["git", "rev-parse", "HEAD"], home).stdout.strip(), old_commit)
        self.assertFalse((self.profile / ".bridgeforge-codex-home-update.json").exists())
        self.assertFalse((self.profile / ".bridgeforge-codex-shared-update.json").exists())

    def test_legacy_ledger_cannot_authorize_active_skill_adoption(self) -> None:
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
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unmanaged skill conflict", result.stderr + result.stdout)
        self.assertEqual((entry / "SKILL.md").read_bytes(), b"entry-v1")
        self.assertTrue(legacy_ledger.is_file())
        self.assertFalse(
            (self.profile / ".codex/bridgeforge-codex-managed.json").exists()
        )
        self.assertFalse((self.profile / ".bridgeforge-codex").exists())

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
