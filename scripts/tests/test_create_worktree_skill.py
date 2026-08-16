#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = ROOT / "skills" / "create-worktree"
SCRIPT = SKILL_ROOT / "scripts" / "create_worktree.ps1"
SKILL_FILE = SKILL_ROOT / "SKILL.md"
OPENAI_YAML = SKILL_ROOT / "agents" / "openai.yaml"


def run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )


@unittest.skipUnless(os.name == "nt", "Windows-only skill")
class CreateWorktreeSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.git = shutil.which("git")
        cls.powershell = shutil.which("powershell.exe")
        if not cls.git or not cls.powershell:
            raise unittest.SkipTest("git and Windows PowerShell 5.1 are required")

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.counter = 0

    def git_run(self, repo: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "GIT_CONFIG_GLOBAL": "NUL",
                "GIT_CONFIG_SYSTEM": "NUL",
                "GIT_TERMINAL_PROMPT": "0",
            }
        )
        result = run([str(self.git), *arguments], repo, env)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return result

    def make_fixture(
        self,
        *,
        with_config: bool = True,
        root_exists: bool = True,
        desktop_launch_throws: bool = False,
        initial_branch: str = "main",
    ) -> dict[str, object]:
        self.counter += 1
        fixture = self.base / f"fixture-{self.counter}"
        repo = fixture / "source repo"
        repo.mkdir(parents=True)
        self.git_run(repo, "init", "-b", initial_branch)
        self.git_run(repo, "config", "user.name", "BridgeForge Test")
        self.git_run(repo, "config", "user.email", "bridgeforge@example.invalid")
        tracked = repo / "tracked.txt"
        tracked.write_text("base\n", encoding="utf-8")
        self.git_run(repo, "add", "tracked.txt")
        self.git_run(repo, "commit", "-m", "base")

        profile = fixture / "user profile"
        config_dir = profile / ".codex"
        config_dir.mkdir(parents=True)
        worktree_root = fixture / "permanent worktrees"
        if root_exists:
            worktree_root.mkdir(parents=True)
        if with_config:
            config_path = config_dir / "config.toml"
            config_path.write_text(
                "[unrelated]\n"
                "git-worktree-root = 'ignored'\n\n"
                "[desktop]\n"
                f"git-worktree-root = '{worktree_root}' # direct root\n",
                encoding="utf-8",
            )

        fake_bin = fixture / "fake bin"
        fake_bin.mkdir()
        git_log = fixture / "git-commands.log"
        desktop_log = fixture / "desktop-deep-link.log"
        (fake_bin / "git.cmd").write_text(
            "@echo off\n"
            "echo %*>>\"%CREATE_WORKTREE_GIT_LOG%\"\n"
            "\"%CREATE_WORKTREE_REAL_GIT%\" %*\n"
            "exit /b %ERRORLEVEL%\n",
            encoding="ascii",
        )
        launcher_wrapper = fixture / "invoke-create-worktree.ps1"
        launcher_wrapper.write_text(
            "param(\n"
            "    [string]$SkillScript,\n"
            "    [string]$WorktreeName,\n"
            "    [string]$BranchName,\n"
            "    [string]$BaseBranch\n"
            ")\n"
            "function Start-Process {\n"
            "    [CmdletBinding()]\n"
            "    param([Parameter(Mandatory = $true)][string]$FilePath)\n"
            "    if ($env:CREATE_WORKTREE_DESKTOP_THROW -eq '1') {\n"
            "        throw 'simulated Codex Desktop protocol denial'\n"
            "    }\n"
            "    [IO.File]::WriteAllText(\n"
            "        $env:CREATE_WORKTREE_DESKTOP_LOG,\n"
            "        $FilePath,\n"
            "        (New-Object Text.UTF8Encoding($false))\n"
            "    )\n"
            "}\n"
            "$skillArguments = @{\n"
            "    worktree_name = $WorktreeName\n"
            "    branch_name = $BranchName\n"
            "}\n"
            "if ($BaseBranch) { $skillArguments.base_branch = $BaseBranch }\n"
            "& $SkillScript @skillArguments\n"
            "exit $LASTEXITCODE\n",
            encoding="ascii",
        )

        env = os.environ.copy()
        env.update(
            {
                "USERPROFILE": str(profile),
                "HOME": str(profile),
                "XDG_CONFIG_HOME": str(profile / ".config"),
                "PATH": f"{fake_bin}{os.pathsep}{env.get('PATH', '')}",
                "CREATE_WORKTREE_REAL_GIT": str(self.git),
                "CREATE_WORKTREE_GIT_LOG": str(git_log),
                "CREATE_WORKTREE_DESKTOP_LOG": str(desktop_log),
                "CREATE_WORKTREE_DESKTOP_THROW": "1" if desktop_launch_throws else "0",
                "GIT_CONFIG_GLOBAL": "NUL",
                "GIT_CONFIG_SYSTEM": "NUL",
                "GIT_TERMINAL_PROMPT": "0",
            }
        )
        return {
            "fixture": fixture,
            "repo": repo,
            "tracked": tracked,
            "profile": profile,
            "worktree_root": worktree_root,
            "git_log": git_log,
            "desktop_log": desktop_log,
            "launcher_wrapper": launcher_wrapper,
            "env": env,
        }

    def invoke(
        self,
        fixture: dict[str, object],
        *,
        worktree_name: str = "risk-suite",
        branch_name: str = "risk-suite-2",
        base_branch: str | None = None,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            str(self.powershell),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(fixture["launcher_wrapper"]),
            "-SkillScript",
            str(SCRIPT),
            "-WorktreeName",
            worktree_name,
            "-BranchName",
            branch_name,
        ]
        if base_branch is not None:
            command.extend(["-BaseBranch", base_branch])
        return run(command, cwd or fixture["repo"], fixture["env"])

    def ref_exists(self, repo: Path, branch: str) -> bool:
        env = os.environ.copy()
        env.update({"GIT_CONFIG_GLOBAL": "NUL", "GIT_CONFIG_SYSTEM": "NUL"})
        result = run(
            [str(self.git), "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            repo,
            env,
        )
        return result.returncode == 0

    def assert_no_creation(self, fixture: dict[str, object], name: str, branch: str) -> None:
        target = fixture["worktree_root"] / name
        self.assertFalse(target.exists(), target)
        self.assertFalse(self.ref_exists(fixture["repo"], branch), branch)
        git_log = fixture["git_log"]
        logged = git_log.read_text(encoding="utf-8", errors="replace") if git_log.exists() else ""
        self.assertNotIn(" worktree add -b ", f" {logged} ")

    def test_success_creates_direct_attached_worktree_without_changing_source(self) -> None:
        fixture = self.make_fixture()
        repo = fixture["repo"]
        source_branch = self.git_run(repo, "branch", "--show-current").stdout.strip()
        source_head = self.git_run(repo, "rev-parse", "HEAD").stdout.strip()
        source_file = fixture["tracked"].read_bytes()

        result = self.invoke(fixture)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        target = fixture["worktree_root"] / "risk-suite"
        self.assertTrue(target.is_dir())
        self.assertEqual(
            self.git_run(target, "branch", "--show-current").stdout.strip(),
            "codex/risk-suite-2",
        )
        self.assertEqual(self.git_run(target, "rev-parse", "HEAD").stdout.strip(), source_head)
        self.assertEqual(self.git_run(repo, "branch", "--show-current").stdout.strip(), source_branch)
        self.assertEqual(self.git_run(repo, "rev-parse", "HEAD").stdout.strip(), source_head)
        self.assertEqual(fixture["tracked"].read_bytes(), source_file)
        self.assertEqual(self.git_run(repo, "status", "--porcelain").stdout, "")

        listed = self.git_run(repo, "worktree", "list", "--porcelain").stdout
        self.assertIn(str(target).replace("\\", "/"), listed.replace("\\", "/"))
        self.assertNotIn("risk-suite/slot", listed.replace("\\", "/"))
        self.assertEqual(
            fixture["desktop_log"].read_text(encoding="utf-8").strip(),
            f"codex://threads/new?path={quote(str(target), safe='')}",
        )

        commands = fixture["git_log"].read_text(encoding="utf-8", errors="replace").splitlines()
        write_commands = [line for line in commands if " worktree add -b " in f" {line} "]
        self.assertEqual(len(write_commands), 1, commands)
        forbidden = {"fetch", "pull", "commit", "merge", "push", "reset", "remove", "prune"}
        observed_tokens = {token for line in commands for token in line.lower().split()}
        self.assertTrue(forbidden.isdisjoint(observed_tokens), commands)

    def test_existing_codex_prefix_is_not_duplicated(self) -> None:
        fixture = self.make_fixture()
        result = self.invoke(fixture, branch_name="codex/already-prefixed")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        target = fixture["worktree_root"] / "risk-suite"
        self.assertEqual(
            self.git_run(target, "branch", "--show-current").stdout.strip(),
            "codex/already-prefixed",
        )
        self.assertFalse(self.ref_exists(fixture["repo"], "codex/codex/already-prefixed"))

    def test_omitted_base_prefers_main_and_falls_back_to_master(self) -> None:
        main_fixture = self.make_fixture()
        main_result = self.invoke(main_fixture, worktree_name="from-main")
        self.assertEqual(main_result.returncode, 0, main_result.stderr + main_result.stdout)
        main_log = main_fixture["git_log"].read_text(encoding="utf-8", errors="replace")
        self.assertIn(" worktree add -b codex/risk-suite-2 ", f" {main_log} ")
        self.assertIn(" main", main_log)

        master_fixture = self.make_fixture(initial_branch="master")
        master_result = self.invoke(master_fixture, worktree_name="from-master")
        self.assertEqual(master_result.returncode, 0, master_result.stderr + master_result.stdout)
        master_log = master_fixture["git_log"].read_text(encoding="utf-8", errors="replace")
        self.assertIn(" worktree add -b codex/risk-suite-2 ", f" {master_log} ")
        self.assertIn(" master", master_log)

    def test_omitted_base_without_main_or_master_is_zero_write(self) -> None:
        fixture = self.make_fixture(initial_branch="trunk")
        result = self.invoke(fixture)
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("No local main or master branch exists", result.stderr)
        self.assert_no_creation(fixture, "risk-suite", "codex/risk-suite-2")

    def test_non_ascii_worktree_name_is_passed_as_a_structured_argument(self) -> None:
        fixture = self.make_fixture()
        result = self.invoke(fixture, worktree_name="风险套件", branch_name="unicode-path")

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        target = fixture["worktree_root"] / "风险套件"
        self.assertTrue(target.is_dir())
        self.assertEqual(
            self.git_run(target, "branch", "--show-current").stdout.strip(),
            "codex/unicode-path",
        )

    def test_each_dirty_state_stops_before_git_or_path_write(self) -> None:
        for dirty_state in ("modified", "staged", "untracked"):
            with self.subTest(dirty_state=dirty_state):
                fixture = self.make_fixture()
                repo = fixture["repo"]
                if dirty_state == "modified":
                    fixture["tracked"].write_text("modified\n", encoding="utf-8")
                elif dirty_state == "staged":
                    fixture["tracked"].write_text("staged\n", encoding="utf-8")
                    self.git_run(repo, "add", "tracked.txt")
                else:
                    (repo / "untracked.txt").write_text("new\n", encoding="utf-8")

                result = self.invoke(fixture, worktree_name=f"dirty-{dirty_state}")
                self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
                self.assertIn("modified, staged, or untracked", result.stderr)
                self.assert_no_creation(
                    fixture,
                    f"dirty-{dirty_state}",
                    "codex/risk-suite-2",
                )

    def test_preflight_failures_are_zero_write(self) -> None:
        cases = (
            ("invalid-name", {"worktree_name": "../escape"}, "codex/risk-suite-2"),
            ("superscript-device-name", {"worktree_name": "LPT².txt"}, "codex/risk-suite-2"),
            ("invalid-branch", {"branch_name": "bad..branch"}, "codex/bad..branch"),
            ("blank-base", {"base_branch": " "}, "codex/risk-suite-2"),
            ("missing-base", {"base_branch": "missing"}, "codex/risk-suite-2"),
        )
        for label, arguments, expected_branch in cases:
            with self.subTest(label=label):
                fixture = self.make_fixture()
                result = self.invoke(fixture, **arguments)
                self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
                name = arguments.get("worktree_name", "risk-suite")
                if name == "../escape":
                    self.assertFalse((fixture["worktree_root"].parent / "escape").exists())
                    self.assertFalse(self.ref_exists(fixture["repo"], expected_branch))
                else:
                    self.assert_no_creation(fixture, name, expected_branch)
                if label == "superscript-device-name":
                    self.assertIn("reserved Windows name", result.stderr)

    def test_missing_config_invalid_root_and_non_git_directory_are_zero_write(self) -> None:
        missing_config = self.make_fixture(with_config=False)
        result = self.invoke(missing_config)
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("Missing Codex config file", result.stderr)
        self.assert_no_creation(missing_config, "risk-suite", "codex/risk-suite-2")

        missing_root = self.make_fixture(root_exists=False)
        result = self.invoke(missing_root)
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("does not exist", result.stderr)
        self.assert_no_creation(missing_root, "risk-suite", "codex/risk-suite-2")

        non_git = self.make_fixture()
        outside = non_git["fixture"] / "not a repository"
        outside.mkdir()
        result = self.invoke(non_git, cwd=outside)
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("not inside a valid Git repository", result.stderr)
        self.assert_no_creation(non_git, "risk-suite", "codex/risk-suite-2")

    def test_target_path_and_branch_conflicts_are_zero_write(self) -> None:
        path_conflict = self.make_fixture()
        target = path_conflict["worktree_root"] / "risk-suite"
        target.mkdir()
        result = self.invoke(path_conflict)
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("Target path already exists", result.stderr)
        self.assertFalse(self.ref_exists(path_conflict["repo"], "codex/risk-suite-2"))
        self.assertEqual(list(target.iterdir()), [])

        branch_conflict = self.make_fixture()
        self.git_run(branch_conflict["repo"], "branch", "codex/risk-suite-2", "main")
        result = self.invoke(branch_conflict)
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("Target branch already exists", result.stderr)
        self.assertFalse((branch_conflict["worktree_root"] / "risk-suite").exists())

    def test_configured_target_inside_source_repository_is_zero_write(self) -> None:
        fixture = self.make_fixture()
        nested_root = fixture["repo"] / "nested worktrees"
        nested_root.mkdir()
        config = fixture["profile"] / ".codex" / "config.toml"
        config.write_text(
            "[desktop]\n"
            f"git-worktree-root = '{nested_root}'\n",
            encoding="utf-8",
        )

        result = self.invoke(fixture)

        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("must be outside the source repository", result.stderr)
        self.assertFalse((nested_root / "risk-suite").exists())
        self.assertFalse(self.ref_exists(fixture["repo"], "codex/risk-suite-2"))

    def test_configured_worktree_root_junction_is_rejected_before_write(self) -> None:
        fixture = self.make_fixture()
        junction = fixture["fixture"] / "junction root"
        junction_env = dict(fixture["env"])
        junction_env["CREATE_WORKTREE_JUNCTION_PATH"] = str(junction)
        junction_env["CREATE_WORKTREE_JUNCTION_TARGET"] = str(fixture["worktree_root"])
        result = run(
            [
                str(self.powershell),
                "-NoProfile",
                "-Command",
                (
                    "New-Item -ItemType Junction "
                    "-Path $env:CREATE_WORKTREE_JUNCTION_PATH "
                    "-Target $env:CREATE_WORKTREE_JUNCTION_TARGET "
                    "-ErrorAction Stop | Out-Null"
                ),
            ],
            fixture["fixture"],
            junction_env,
        )
        if result.returncode != 0:
            self.skipTest(f"junction creation unavailable: {result.stderr.strip()}")

        config = fixture["profile"] / ".codex" / "config.toml"
        config.write_text(
            "[desktop]\n"
            f"git-worktree-root = '{junction}'\n",
            encoding="utf-8",
        )

        invoked = self.invoke(fixture)

        self.assertEqual(invoked.returncode, 2, invoked.stderr + invoked.stdout)
        self.assertIn("passes through a reparse point", invoked.stderr)
        self.assertFalse((fixture["worktree_root"] / "risk-suite").exists())
        self.assertFalse(self.ref_exists(fixture["repo"], "codex/risk-suite-2"))

    def test_desktop_protocol_failure_preserves_git_results_and_prints_retry(self) -> None:
        fixture = self.make_fixture(desktop_launch_throws=True)
        result = self.invoke(fixture)
        target = fixture["worktree_root"] / "risk-suite"

        self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
        self.assertIn("Partial success", result.stderr)
        self.assertIn("simulated Codex Desktop protocol denial", result.stderr)
        self.assertIn("Start-Process -FilePath 'codex://threads/new?path=", result.stderr)
        self.assertTrue(target.is_dir())
        self.assertTrue(self.ref_exists(fixture["repo"], "codex/risk-suite-2"))

    def test_skill_contract_is_explicit_and_script_is_low_freedom(self) -> None:
        skill = SKILL_FILE.read_text(encoding="utf-8")
        openai_yaml = OPENAI_YAML.read_text(encoding="utf-8")
        script = SCRIPT.read_text(encoding="ascii")

        self.assertIn("user_invocable: true", skill)
        self.assertIn("argument: ", skill)
        self.assertIn("/create-worktree <工作树名> <分支名> [基准分支]", skill)
        self.assertIn("一次只询问第一个缺失项", skill)
        self.assertIn("优先使用本地 `main`", skill)
        self.assertIn("使用本地 `master`", skill)
        self.assertIn("禁止要求用户输入 `worktree_name=`", skill)
        self.assertIn("运行脚本前必须使用当前宿主的提升权限机制", skill)
        self.assertIn("禁止先在默认沙箱运行再提升重试", skill)
        self.assertIn('display_name: "create-worktree"', openai_yaml)
        self.assertIn("$create-worktree", openai_yaml)
        self.assertIn("allow_implicit_invocation: false", openai_yaml)
        self.assertEqual(script.count('"worktree", "add", "-b"'), 1)
        self.assertIn('"codex://threads/new?path=$encodedTargetPath"', script)
        self.assertIn("Start-Process -FilePath $desktopDeepLink", script)
        self.assertNotIn("Get-Command codex", script)
        self.assertIn("[IO.FileAttributes]::ReparsePoint", script)
        self.assertIn(
            'Assert-NoReparsePointInExistingAncestors $repoRoot "Source repository root"',
            script,
        )
        self.assertIn(
            'Assert-NoReparsePointInExistingAncestors $worktreeRoot "desktop.git-worktree-root"',
            script,
        )
        for forbidden in (" worktree remove ", " fetch ", " pull ", " push ", " reset "):
            self.assertNotIn(forbidden, script.lower())
        for routing in (
            ROOT / ".codex" / "skill-routing.json",
            ROOT / "templates" / "skill-routing.json",
        ):
            manifest = json.loads(routing.read_text(encoding="utf-8-sig"))
            entry = next(
                item
                for item in manifest["global_entries"]
                if item["skill"] == "create-worktree"
            )
            self.assertEqual(entry["agent"], "main")
            self.assertEqual(entry["mode"], "main")
            self.assertNotIn(
                "create-worktree",
                {item["skill"] for item in manifest["skills"]},
            )


if __name__ == "__main__":
    unittest.main()
