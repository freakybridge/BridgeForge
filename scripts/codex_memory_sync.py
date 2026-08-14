#!/usr/bin/env python3
"""BridgeForge single-writer sync for opaque Codex native memories.

The runtime is distributed inside the user-level BridgeForge command bundle.
Setup may be launched by a project virtual environment, but installed user
hooks always use that environment's stable base interpreter and never import
project code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

MIN_PYTHON = (3, 11)
EXTERNAL_COMMAND_TIMEOUT = 45
REPOSITORY = "bridgeforge-codex-memories"
HOOK_ID = "bridgeforge.codex-native-memory-sync.v1"
WORKDIR_PREFIX = "bridgeforge-memory-sync-"
EXCLUDED_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini", "snapshot-manifest.json"}
EXCLUDED_SUFFIXES = {".tmp", ".temp", ".lock", ".lck", ".swp", ".part"}
Run = Callable[..., subprocess.CompletedProcess[str]]


class SyncError(RuntimeError):
    pass


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _remove_tree(path: Path) -> None:
    def writable_then_retry(function: object, target: str, _info: object) -> None:
        os.chmod(target, stat.S_IWRITE)
        function(target)  # type: ignore[operator]
    shutil.rmtree(path, onerror=writable_then_retry)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _real_directory(path: Path, *, create: bool = False) -> Path:
    if create:
        path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir() or _is_link_or_reparse(path):
        raise SyncError(f"directory must exist and must not be a link: {path}")
    current = path
    while True:
        if _is_link_or_reparse(current):
            raise SyncError(f"path traverses a link: {current}")
        if current.parent == current:
            break
        current = current.parent
    return path.resolve()


def _atomic_text(path: Path, text: str) -> None:
    _real_directory(path.parent, create=True)
    if path.exists() and _is_link_or_reparse(path):
        raise SyncError(f"refusing to replace linked file: {path}")
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _atomic_json(path: Path, value: object) -> None:
    _atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def codex_paths(home: Path | None = None) -> tuple[Path, Path, Path]:
    codex = Path(os.environ.get("CODEX_HOME", "")) if os.environ.get("CODEX_HOME") else (home or Path.home()) / ".codex"
    return codex, codex / "memories", codex / ".bridgeforge" / "memory-sync"


def memory_switches(config_path: Path) -> tuple[bool, dict[str, object]]:
    if not config_path.exists():
        return False, {}
    raw = config_path.read_bytes()
    try:
        data = tomllib.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise SyncError(f"invalid config.toml: {exc}") from exc
    features = data.get("features", {})
    memories = data.get("memories", {})
    enabled = (
        isinstance(features, dict) and features.get("memories") is True
        and isinstance(memories, dict) and memories.get("generate_memories") is True
        and memories.get("use_memories") is True
    )
    return enabled, data


def _merge_toml_bool(text: str, section: str, key: str) -> str:
    header = re.compile(rf"(?m)^\s*\[{re.escape(section)}\]\s*(?:#.*)?$")
    match = header.search(text)
    assignment = re.compile(
        rf"(?m)^(\s*){re.escape(key)}(\s*=\s*)(?:true|false)(\s*(?:#.*)?)$"
    )
    if match:
        next_header = re.search(r"(?m)^\s*\[", text[match.end():])
        end = match.end() + (next_header.start() if next_header else len(text) - match.end())
        block = text[match.end():end]
        if assignment.search(block):
            block = assignment.sub(
                lambda item: f"{item.group(1)}{key}{item.group(2)}true{item.group(3)}",
                block,
                count=1,
            )
        else:
            block = f"\n{key} = true" + block
        return text[:match.end()] + block + text[end:]
    separator = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
    return text + separator + f"[{section}]\n{key} = true\n"


def enable_memories(config_path: Path, *, confirmed: bool) -> bool:
    if not confirmed:
        raise SyncError("native memories remain unchanged without --confirmed-enable")
    original = config_path.read_text(encoding="utf-8-sig") if config_path.exists() else ""
    merged = original
    for section, key in (("features", "memories"), ("memories", "generate_memories"), ("memories", "use_memories")):
        merged = _merge_toml_bool(merged, section, key)
    tomllib.loads(merged)
    if merged != original:
        _atomic_text(config_path, merged)
        return True
    return False


def stable_hook_python() -> Path:
    """Return a user-stable interpreter instead of a project venv executable."""
    current = Path(sys.executable).resolve()
    base_value = getattr(sys, "_base_executable", None)
    candidate = (
        Path(base_value).resolve()
        if base_value
        else (Path(sys.base_prefix) / current.name).resolve()
    )
    if not candidate.is_file():
        raise SyncError(
            "the project Python has no stable base interpreter; "
            "native memories hooks were not installed"
        )
    prefix = Path(sys.prefix).resolve()
    base_prefix = Path(sys.base_prefix).resolve()
    if prefix != base_prefix and candidate.is_relative_to(prefix):
        raise SyncError(
            "the project Python resolves its base interpreter inside the venv; "
            "native memories hooks were not installed"
        )
    return candidate


def _hook_handler(
    event: str,
    script: Path,
    *,
    hook_python: Path | None = None,
) -> dict[str, object]:
    if event == "SessionEnd":
        args = "kick --trigger session-end"
    else:
        args = f"reconcile --trigger {event.lower()}"
    runtime = (hook_python or stable_hook_python()).resolve()
    command = f'"{runtime}" "{script}" {args}'
    handler: dict[str, object] = {"type": "command", "command": command, "bridgeforgeId": f"{HOOK_ID}:{event}"}
    if event == "Stop":
        handler["async"] = True
        handler["timeout"] = 120
    if event == "SessionStart":
        handler["timeout"] = 120
    if event == "SessionEnd":
        handler["timeout"] = 3
    return handler


def merge_user_hooks(
    hooks_path: Path,
    script: Path,
    *,
    hook_python: Path | None = None,
) -> bool:
    if hooks_path.exists():
        try:
            document = json.loads(hooks_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise SyncError(f"invalid user hooks.json: {exc}") from exc
        if not isinstance(document, dict):
            raise SyncError("user hooks.json root must be an object")
    else:
        document = {}
    hooks = document.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise SyncError("user hooks.json hooks must be an object")
    before = json.dumps(document, ensure_ascii=False, sort_keys=True)
    for event in ("SessionStart", "Stop", "SessionEnd"):
        entries = hooks.setdefault(event, [])
        if not isinstance(entries, list):
            raise SyncError(f"user hook event must be a list: {event}")
        expected = _hook_handler(event, script, hook_python=hook_python)
        found = False
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            handlers = entry.get("hooks")
            if not isinstance(handlers, list):
                continue
            rebuilt_handlers: list[object] = []
            for handler in handlers:
                if isinstance(handler, dict) and handler.get("bridgeforgeId") == expected["bridgeforgeId"]:
                    if not found:
                        rebuilt_handlers.append(expected)
                        found = True
                    continue
                rebuilt_handlers.append(handler)
            if rebuilt_handlers != handlers:
                entry["hooks"] = rebuilt_handlers
        if not found:
            entries.append({"hooks": [expected]})
    after = json.dumps(document, ensure_ascii=False, sort_keys=True)
    if after != before:
        _atomic_json(hooks_path, document)
        return True
    return False


def user_hooks_healthy(
    hooks_path: Path,
    script: Path,
    *,
    hook_python: Path | None = None,
) -> bool:
    try:
        document = json.loads(hooks_path.read_text(encoding="utf-8-sig"))
        hooks = document["hooks"]
        if not isinstance(hooks, dict):
            return False
        for event in ("SessionStart", "Stop", "SessionEnd"):
            expected = _hook_handler(event, script, hook_python=hook_python)
            matches = [
                handler
                for entry in hooks.get(event, [])
                if isinstance(entry, dict) and isinstance(entry.get("hooks"), list)
                for handler in entry["hooks"]
                if isinstance(handler, dict) and handler.get("bridgeforgeId") == expected["bridgeforgeId"]
            ]
            if matches != [expected]:
                return False
        return True
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return False


def _excluded(relative: Path) -> bool:
    return (
        any(part in {"__pycache__", ".git", ".bridgeforge"} for part in relative.parts)
        or relative.name in EXCLUDED_NAMES
        or relative.suffix.lower() in EXCLUDED_SUFFIXES
        or relative.name.startswith(".~")
    )


def _memory_files(source: Path) -> list[Path]:
    files: list[Path] = []
    pending = [source]
    while pending:
        directory = pending.pop()
        try:
            entries = sorted(os.scandir(directory), key=lambda entry: entry.name, reverse=True)
        except OSError as exc:
            raise SyncError(f"cannot scan native memories: {directory}: {exc}") from exc
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(source)
            if _excluded(relative):
                continue
            if _is_link_or_reparse(path):
                raise SyncError(f"native memories contain a link or junction: {relative.as_posix()}")
            try:
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                elif entry.is_file(follow_symlinks=False):
                    files.append(path)
            except OSError as exc:
                raise SyncError(f"cannot inspect native memory: {relative.as_posix()}: {exc}") from exc
    return sorted(files)


def capture_manifest(source: Path, revision: int, captured_at: str | None = None) -> dict[str, object]:
    source = _real_directory(source)
    files: list[dict[str, str]] = []
    newest_mtime = 0.0
    for path in _memory_files(source):
        relative = path.relative_to(source)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"path": relative.as_posix(), "sha256": digest})
        newest_mtime = max(newest_mtime, path.stat().st_mtime)
    content = hashlib.sha256(json.dumps(files, separators=(",", ":"), sort_keys=True).encode()).hexdigest()
    updated_at = datetime.fromtimestamp(newest_mtime, timezone.utc).isoformat() if newest_mtime else datetime.fromtimestamp(0, timezone.utc).isoformat()
    return {
        "schema_version": 1,
        "captured_at_utc": captured_at or utc_now(),
        "updated_at_utc": updated_at,
        "revision": revision,
        "content_sha256": content,
        "files": files,
    }


def build_snapshot(source: Path, destination: Path, revision: int) -> dict[str, object]:
    last_error: Exception | None = None
    for _attempt in range(3):
        manifest = capture_manifest(source, revision)
        if destination.exists():
            if _is_link_or_reparse(destination):
                raise SyncError(f"snapshot destination is a link: {destination}")
            _remove_tree(destination)
        (destination / "memories").mkdir(parents=True)
        try:
            for item in manifest["files"]:
                assert isinstance(item, dict)
                relative = Path(str(item["path"]))
                target = destination / "memories" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / relative, target)
            _atomic_json(destination / "snapshot-manifest.json", manifest)
            verify_snapshot(destination, manifest)
            return manifest
        except (OSError, SyncError) as exc:
            last_error = exc
    raise SyncError(f"native memories changed while snapshotting: {last_error}")


def verify_snapshot(snapshot: Path, manifest: dict[str, object]) -> None:
    if manifest.get("schema_version") != 1 or not isinstance(manifest.get("files"), list):
        raise SyncError("remote snapshot manifest schema is invalid")
    actual = capture_manifest(snapshot / "memories", int(manifest.get("revision", 0)))
    if actual["files"] != manifest["files"] or actual["content_sha256"] != manifest.get("content_sha256"):
        raise SyncError("remote snapshot content does not match its SHA-256 manifest")


def choose_action(
    local: str,
    remote: str | None,
    synced: str | None,
    *,
    local_updated_at: str | None = None,
    remote_updated_at: str | None = None,
) -> str:
    if remote is None:
        return "push"
    if local == remote:
        return "noop"
    local_changed = synced is None or local != synced
    remote_changed = synced is None or remote != synced
    if local_changed and remote_changed:
        if not local_updated_at or not remote_updated_at:
            raise SyncError("local and remote snapshots both changed but update times are unavailable")
        # A whole snapshot wins as a unit. On an exact tie, prefer the remote
        # snapshot so a newly installed machine cannot overwrite cloud state.
        return "push" if local_updated_at > remote_updated_at else "restore"
    return "push" if local_changed else "restore"


def launch_background_reconcile(trigger: str) -> None:
    command = [str(stable_hook_python()), str(Path(__file__).resolve()), "reconcile", "--trigger", trigger]
    kwargs: dict[str, object] = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen(command, **kwargs)


def _default_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    kwargs.setdefault("timeout", EXTERNAL_COMMAND_TIMEOUT)
    try:
        return subprocess.run(command, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False, **kwargs)
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            command,
            124,
            str(exc.stdout or ""),
            f"command timed out after {kwargs['timeout']} seconds",
        )


def ensure_github_repository(
    *,
    confirmed_public_to_private: bool,
    run: Run = _default_run,
) -> tuple[str, str]:
    if shutil.which("gh") is None:
        raise SyncError("gh is not installed; memories setup stopped")
    auth = run(["gh", "auth", "status", "--active", "--hostname", "github.com"])
    if auth.returncode:
        raise SyncError("gh is not logged in; memories setup stopped")
    action = "reused"
    view = run(["gh", "repo", "view", REPOSITORY, "--json", "visibility,url,nameWithOwner"])
    if view.returncode:
        created = run(["gh", "repo", "create", REPOSITORY, "--private", "--confirm"])
        if created.returncode:
            raise SyncError(f"failed to create private repository: {created.stderr.strip()}")
        action = "created"
        view = run(["gh", "repo", "view", REPOSITORY, "--json", "visibility,url,nameWithOwner"])
    if view.returncode:
        raise SyncError(f"failed to inspect repository: {view.stderr.strip()}")
    data = json.loads(view.stdout)
    visibility = str(data.get("visibility", "")).upper()
    if visibility == "PUBLIC":
        if not confirmed_public_to_private:
            raise SyncError("same-name repository is public; explicit visibility confirmation required")
        name = str(data.get("nameWithOwner") or REPOSITORY)
        changed = run(["gh", "repo", "edit", name, "--visibility", "private", "--accept-visibility-change-consequences"])
        if changed.returncode:
            raise SyncError(f"failed to make repository private: {changed.stderr.strip()}")
        action = "made-private"
    elif visibility != "PRIVATE":
        raise SyncError(f"unsupported repository visibility: {visibility or 'unknown'}")
    remote = str(data.get("url") or f"https://github.com/{data.get('nameWithOwner')}.git")
    return remote, action


def mark_pending(state_dir: Path, trigger: str) -> None:
    _real_directory(state_dir, create=True)
    _atomic_json(state_dir / "pending.json", {"trigger": trigger, "utc": utc_now()})


def _workdir_marker(state_dir: Path) -> Path:
    return state_dir / "transient-workdir.json"


def _record_workdir(state_dir: Path, work_dir: Path) -> None:
    _atomic_json(_workdir_marker(state_dir), {"path": str(work_dir), "utc": utc_now()})


def _cleanup_recorded_workdir(state_dir: Path) -> None:
    marker = _workdir_marker(state_dir)
    if not marker.is_file():
        return
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
        work_dir = Path(str(payload["path"]))
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise SyncError(f"invalid transient workdir marker: {marker}") from exc
    temp_root = Path(tempfile.gettempdir()).resolve()
    try:
        parent = work_dir.parent.resolve()
    except OSError as exc:
        raise SyncError(f"cannot resolve transient workdir: {work_dir}") from exc
    if parent != temp_root or not work_dir.name.startswith(WORKDIR_PREFIX):
        raise SyncError(f"refusing to clean untrusted transient workdir: {work_dir}")
    if work_dir.exists():
        _remove_tree(work_dir)
    marker.unlink()


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except (OSError, PermissionError):
        return True


def _acquire_reconcile_lock(state_dir: Path) -> int | None:
    lock = state_dir / "reconcile.lock"
    for _attempt in range(2):
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                os.write(descriptor, json.dumps({"pid": os.getpid(), "utc": utc_now()}).encode("utf-8"))
            except OSError:
                os.close(descriptor)
                lock.unlink(missing_ok=True)
                raise
            return descriptor
        except FileExistsError:
            try:
                owner = json.loads(lock.read_text(encoding="utf-8"))
                if _process_alive(int(owner.get("pid", 0))):
                    return None
                lock.unlink()
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                try:
                    if time.time() - lock.stat().st_mtime > 60:
                        lock.unlink()
                        continue
                except OSError:
                    pass
                return None
    return None


def _release_reconcile_lock(state_dir: Path, descriptor: int) -> None:
    os.close(descriptor)
    (state_dir / "reconcile.lock").unlink(missing_ok=True)


def _clear_pending_if_unchanged(state_dir: Path, previous: bytes | None) -> None:
    pending = state_dir / "pending.json"
    if previous is None or not pending.is_file():
        return
    try:
        if pending.read_bytes() == previous:
            pending.unlink()
    except OSError:
        pass


def _git(command: list[str], cwd: Path, *, env: dict[str, str] | None = None) -> str:
    result = _default_run(["git", *command], cwd=cwd, env=env)
    if result.returncode:
        raise SyncError(f"git {' '.join(command)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _read_remote_snapshot(state_dir: Path, remote: str) -> tuple[dict[str, object] | None, Path | None, str | None]:
    bare = state_dir / "remote.git"
    if not bare.exists():
        _git(["init", "--bare", str(bare)], state_dir)
    (bare / "info" / "attributes").write_bytes(b"* -text\n")
    remotes = _git(["remote"], bare).splitlines()
    if "origin" in remotes:
        _git(["remote", "set-url", "origin", remote], bare)
    else:
        _git(["remote", "add", "origin", remote], bare)
    result = _default_run(["git", "fetch", "--prune", "origin", "+refs/heads/main:refs/remotes/origin/main"], cwd=bare)
    if result.returncode:
        if "couldn't find remote ref" in result.stderr.lower() or "not found" in result.stderr.lower():
            return None, None, None
        raise SyncError(f"remote fetch failed: {result.stderr.strip()}")
    commit = _git(["rev-parse", "refs/remotes/origin/main"], bare)
    shown = _default_run(
        ["git", "show", "refs/remotes/origin/main:snapshot-manifest.json"],
        cwd=bare,
    )
    if shown.returncode:
        missing = "path 'snapshot-manifest.json' does not exist" in shown.stderr.lower()
        if missing:
            return None, None, commit
        raise SyncError(f"remote manifest read failed: {shown.stderr.strip()}")
    raw = shown.stdout
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError:
        return None, None, commit
    if not isinstance(manifest, dict):
        return None, None, commit
    files = manifest.get("files")
    if manifest.get("schema_version") != 1 or not isinstance(files, list):
        return None, None, commit
    extracted = state_dir / "remote-snapshot"
    if extracted.exists():
        _remove_tree(extracted)
    extracted.mkdir()
    checkout_paths = ["snapshot-manifest.json"]
    if files:
        checkout_paths.insert(0, "memories")
    else:
        tracked_memories = _git(
            ["ls-tree", "-r", "--name-only", "refs/remotes/origin/main", "--", "memories"],
            bare,
        )
        if tracked_memories:
            return None, None, commit
    _git(
        ["-c", "core.autocrlf=false", f"--work-tree={extracted}", "checkout", "-f", "refs/remotes/origin/main", "--", *checkout_paths],
        bare,
    )
    if not files:
        (extracted / "memories").mkdir()
    try:
        verify_snapshot(extracted, manifest)
    except SyncError:
        # Only explicit remote schema/hash failures enter repair mode. Local
        # state-directory, checkout, permission and disk errors propagate.
        return None, None, commit
    return manifest, extracted, commit


def _push_snapshot(snapshot: Path, state_dir: Path, remote: str, expected: str | None) -> str:
    publish = state_dir / "publish"
    if publish.exists():
        _remove_tree(publish)
    shutil.copytree(snapshot, publish)
    _git(["init", "-b", "main"], publish)
    (publish / ".git" / "info" / "attributes").write_bytes(b"* -text\n")
    _git(["-c", "core.autocrlf=false", "add", "--all"], publish)
    tree = _git(["write-tree"], publish)
    env = os.environ.copy()
    env.update({"GIT_AUTHOR_NAME": "BridgeForge Memory Sync", "GIT_AUTHOR_EMAIL": "bridgeforge@invalid", "GIT_COMMITTER_NAME": "BridgeForge Memory Sync", "GIT_COMMITTER_EMAIL": "bridgeforge@invalid"})
    commit = _git(["commit-tree", tree, "-m", "BridgeForge Codex memories snapshot"], publish, env=env)
    _git(["update-ref", "refs/heads/main", commit], publish)
    _git(["remote", "add", "origin", remote], publish)
    lease = f"--force-with-lease=refs/heads/main:{expected}" if expected else "--force-with-lease=refs/heads/main:"
    _git(["push", lease, "origin", "refs/heads/main:refs/heads/main"], publish)
    return commit


def _restore_snapshot(extracted: Path, memories: Path) -> None:
    incoming = extracted / "memories"
    capture_manifest(incoming, 0)
    stage = memories.parent / f".{memories.name}.bridgeforge-incoming"
    old = memories.parent / f".{memories.name}.bridgeforge-replaced"
    for path in (stage, old):
        if path.exists():
            _remove_tree(path)
    shutil.copytree(incoming, stage)
    had_existing = memories.exists()
    if had_existing:
        os.replace(memories, old)
    try:
        os.replace(stage, memories)
    except Exception:
        if had_existing:
            os.replace(old, memories)
        raise
    finally:
        if old.exists():
            _remove_tree(old)


def _reconcile_in_work(
    memories: Path,
    state_dir: Path,
    work_dir: Path,
    remote: str,
    pending_before: bytes | None,
) -> str:
    state_file = state_dir / "last-synced.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.exists() else {}
    remote_manifest, extracted, remote_commit = _read_remote_snapshot(work_dir, remote)
    if not memories.exists():
        if remote_manifest is None or extracted is None:
            if remote_commit is not None:
                raise SyncError("remote snapshot is corrupt and no local memories exist to repair it")
            _clear_pending_if_unchanged(state_dir, pending_before)
            return "noop"
        action = "restore"
        if remote_manifest["files"]:
            _restore_snapshot(extracted, memories)
        else:
            action = "noop"
        _atomic_json(state_file, {
            "content_sha256": remote_manifest["content_sha256"],
            "revision": remote_manifest["revision"],
            "commit": remote_commit,
            "utc": utc_now(),
        })
        _clear_pending_if_unchanged(state_dir, pending_before)
        return action
    _real_directory(memories)
    local_manifest = capture_manifest(memories, 0)
    remote_digest = str(remote_manifest.get("content_sha256")) if remote_manifest else None
    local_digest = str(local_manifest["content_sha256"])
    remote_updated_at = None
    if remote_manifest:
        remote_updated_at = str(remote_manifest.get("updated_at_utc") or remote_manifest.get("captured_at_utc") or "")
    action = choose_action(
        local_digest,
        remote_digest,
        str(state.get("content_sha256")) if state.get("content_sha256") else None,
        local_updated_at=str(local_manifest["updated_at_utc"]),
        remote_updated_at=remote_updated_at,
    )
    if action == "push":
        revision = max(
            int(state.get("revision", 0)),
            int(remote_manifest.get("revision", 0)) if remote_manifest else 0,
        ) + 1
        snapshot = work_dir / "local-snapshot"
        local_manifest = build_snapshot(memories, snapshot, revision)
        commit = _push_snapshot(snapshot, work_dir, remote, remote_commit)
        result_manifest = local_manifest
    elif action == "restore":
        assert extracted is not None and remote_manifest is not None
        _restore_snapshot(extracted, memories)
        commit = remote_commit
        result_manifest = remote_manifest
    else:
        commit = remote_commit
        result_manifest = remote_manifest or local_manifest
    _atomic_json(state_file, {"content_sha256": result_manifest["content_sha256"], "revision": result_manifest["revision"], "commit": commit, "utc": utc_now()})
    _clear_pending_if_unchanged(state_dir, pending_before)
    return action


def _reconcile_unlocked(memories: Path, state_dir: Path, remote: str, pending_before: bytes | None) -> str:
    try:
        _cleanup_recorded_workdir(state_dir)
    except (OSError, SyncError) as exc:
        mark_pending(state_dir, "work-cleanup-pending")
        print(f"[memory-sync] WARNING: prior temporary snapshot cleanup still pending: {exc}", file=sys.stderr)
        return "cleanup-pending"
    work_dir = Path(tempfile.mkdtemp(prefix=WORKDIR_PREFIX))
    try:
        _record_workdir(state_dir, work_dir)
    except (OSError, SyncError):
        _remove_tree(work_dir)
        raise
    try:
        return _reconcile_in_work(memories, state_dir, work_dir, remote, pending_before)
    finally:
        try:
            _remove_tree(work_dir)
            _workdir_marker(state_dir).unlink(missing_ok=True)
        except OSError as exc:
            mark_pending(state_dir, "work-cleanup-failed")
            print(f"[memory-sync] WARNING: temporary snapshot cleanup failed: {exc}", file=sys.stderr)


def reconcile(memories: Path, state_dir: Path, remote: str) -> str:
    _real_directory(state_dir, create=True)
    pending = state_dir / "pending.json"
    pending_before = pending.read_bytes() if pending.is_file() else None
    descriptor = _acquire_reconcile_lock(state_dir)
    if descriptor is None:
        mark_pending(state_dir, "deduplicated")
        return "busy"
    try:
        return _reconcile_unlocked(memories, state_dir, remote, pending_before)
    finally:
        _release_reconcile_lock(state_dir, descriptor)


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < MIN_PYTHON:
        print("[memory-sync] WARNING: Python 3.11+ is required", file=sys.stderr)
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    setup = sub.add_parser("setup")
    setup.add_argument("--confirmed-enable", action="store_true")
    setup.add_argument("--confirmed-public-to-private", action="store_true")
    reconcile_cmd = sub.add_parser("reconcile")
    reconcile_cmd.add_argument("--trigger", default="bridgeforge")
    mark = sub.add_parser("mark")
    mark.add_argument("--trigger", required=True)
    kick = sub.add_parser("kick")
    kick.add_argument("--trigger", required=True)
    sub.add_parser("status")
    args = parser.parse_args(argv)
    codex, memories, state_dir = codex_paths()
    try:
        _real_directory(codex, create=True)
        enabled, _ = memory_switches(codex / "config.toml")
        if args.command == "status":
            hook_python = stable_hook_python()
            remote_configured = (state_dir / "remote.txt").is_file()
            print(json.dumps({
                "enabled": enabled,
                "hookInstalled": user_hooks_healthy(
                    codex / "hooks.json",
                    Path(__file__).resolve(),
                    hook_python=hook_python,
                ),
                "pending": (state_dir / "pending.json").exists(),
                "setupPython": str(Path(sys.executable).resolve()),
                "hookPython": str(hook_python),
                "remoteConfigured": remote_configured,
            }, ensure_ascii=False))
            return 0
        if args.command in {"mark", "kick"}:
            if enabled:
                mark_pending(state_dir, args.trigger)
                if args.command == "kick":
                    launch_background_reconcile(args.trigger)
            return 0
        if args.command == "setup":
            hook_python = stable_hook_python()
            if not enabled:
                if not args.confirmed_enable:
                    raise SyncError("native memories remain unchanged without --confirmed-enable")
            remote, remote_action = ensure_github_repository(
                confirmed_public_to_private=args.confirmed_public_to_private
            )
            if not enabled:
                enable_memories(codex / "config.toml", confirmed=True)
            merge_user_hooks(
                codex / "hooks.json",
                Path(__file__).resolve(),
                hook_python=hook_python,
            )
            _atomic_text(state_dir / "remote.txt", remote + "\n")
            print(
                "[memory-sync] configured; "
                f"setup_python={Path(sys.executable).resolve()}; "
                f"hook_python={hook_python}; hook_installed=true; "
                f"remote_configured=true; remote_action={remote_action}; remote={remote}; "
                "review/trust the user hooks in /hooks"
            )
            return 0
        if not enabled:
            return 0
        remote_file = state_dir / "remote.txt"
        if not remote_file.is_file():
            print("[memory-sync] WARNING: setup is incomplete; run $bridgeforge", file=sys.stderr)
            return 0
        action = reconcile(memories, state_dir, remote_file.read_text(encoding="utf-8").strip())
        if args.trigger == "bridgeforge":
            print(f"[memory-sync] {action}")
        elif args.trigger == "stop":
            print("{}")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError, SyncError) as exc:
        try:
            mark_pending(state_dir, getattr(args, "trigger", args.command))
        except Exception:
            pass
        print(f"[memory-sync] WARNING: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
