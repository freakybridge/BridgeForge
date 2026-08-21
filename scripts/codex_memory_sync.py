#!/usr/bin/env python3
"""bridgeforge-codex single-writer sync for opaque Codex native memories.

The managed script is distributed with bridgeforge-codex. Every invocation is
authorized by the current project's CPython 3.11+ ``.venv``; user hooks store a
dynamic Git-root command and never persist a project's interpreter path.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Iterator

MIN_PYTHON = (3, 11)
EXTERNAL_COMMAND_TIMEOUT = 45
REPOSITORY = "bridgeforge-codex-memories"
CONSENT_POLICY_VERSION = 1
CONSENT_SCOPE = "~/.codex/memories/**"
CONSENT_SYNC_MODE = "bidirectional"
HOOK_ID = "bridgeforge-codex.native-memory-sync.v1"
HOOK_MARKER_KEY = "bridgeforgeCodexId"
HOOK_EVENTS = ("SessionStart", "Stop", "SessionEnd")
HOOK_RUNTIME_REVISION = 3
WINDOWS_HOOK_WRAPPER_NAME = "codex_memory_sync_hook.ps1"
LEGACY_WINDOWS_HOOK_WRAPPER_NAME = "codex_memory_sync_hook.cmd"
WORKDIR_PREFIX = "bridgeforge-codex-memory-sync-"
EXCLUDED_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini", "snapshot-manifest.json"}
EXCLUDED_SUFFIXES = {".tmp", ".temp", ".lock", ".lck", ".swp", ".part"}
Run = Callable[..., subprocess.CompletedProcess[str]]
CONSENT_VALUES = {"approved", "declined"}
HOOK_RUNTIME_CONTRACT = "git-root/.venv/Scripts/python.exe; CPython>=3.11"
DYNAMIC_HOOK_RUNTIME = "<git-root>/.venv/Scripts/python.exe"
HOOK_LOCK_TIMEOUT_SECONDS = 10.0


def _load_hooks_ownership_module() -> object:
    path = Path(__file__).resolve().with_name("hooks_ownership.py")
    spec = importlib.util.spec_from_file_location("_bridgeforge_user_hooks_ownership", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load hooks ownership parser: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


HOOKS_OWNERSHIP = _load_hooks_ownership_module()


def _load_project_runtime_module() -> object:
    path = Path(__file__).resolve().parent.parent / "templates" / "scripts" / "project_runtime.py"
    spec = importlib.util.spec_from_file_location("_bridgeforge_project_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load project runtime contract: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SyncError(RuntimeError):
    pass


class HookLockConflict(SyncError):
    pass


@dataclass(frozen=True)
class HookRepairReceipt:
    hook_repair: str
    configured_runtime: str
    actual_runtime: str
    runtime_drift_reason: str | None = None


def _validated_project_runtime(project_root: Path) -> tuple[Path, Path]:
    try:
        module = _load_project_runtime_module()
        root = project_root.resolve(strict=True)
        expected = module.expected_project_python(root)
        module.validate_project_runtime(root, executable=Path(sys.executable))
    except (OSError, RuntimeError, ValueError) as exc:
        raise SyncError(f"project runtime is invalid: {exc}") from exc
    return root, Path(expected).resolve()


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


def _atomic_bytes(path: Path, payload: bytes) -> None:
    _real_directory(path.parent, create=True)
    if path.exists() and _is_link_or_reparse(path):
        raise SyncError(f"refusing to replace linked file: {path}")
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(raw)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _atomic_json(path: Path, value: object) -> None:
    _atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _hooks_lock_name(codex: Path) -> str:
    digest = hashlib.sha256(str(codex.resolve()).casefold().encode("utf-8")).hexdigest()
    return f"bridgeforge-codex-native-hooks-{digest}"


@contextlib.contextmanager
def user_hooks_lock(
    codex: Path,
    *,
    timeout: float = HOOK_LOCK_TIMEOUT_SECONDS,
) -> Iterator[None]:
    """Serialize BridgeForge writers without touching the user's hooks files."""
    deadline = time.monotonic() + timeout
    if os.name == "nt":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.WaitForSingleObject.restype = ctypes.c_uint32
        kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel32.CreateMutexW(None, False, "Local\\" + _hooks_lock_name(codex))
        if not handle:
            raise SyncError("failed to create the user hooks mutex")
        wait_ms = max(0, int(timeout * 1000))
        result = kernel32.WaitForSingleObject(handle, wait_ms)
        if result == 0x00000080:  # WAIT_ABANDONED grants ownership with untrusted state.
            kernel32.ReleaseMutex(handle)
            kernel32.CloseHandle(handle)
            raise HookLockConflict("user hooks mutex was abandoned; shared state is untrusted")
        if result != 0x00000000:
            kernel32.CloseHandle(handle)
            if result == 0x00000102:
                raise HookLockConflict("user hooks lock is busy")
            raise SyncError(f"failed to acquire the user hooks mutex: {result}")
        try:
            yield
        finally:
            kernel32.ReleaseMutex(handle)
            kernel32.CloseHandle(handle)
        return

    import fcntl  # POSIX-only fallback used by non-Windows test hosts.

    lock_path = Path(tempfile.gettempdir()) / (_hooks_lock_name(codex) + ".lock")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise HookLockConflict("user hooks lock is busy")
                time.sleep(0.02)
        try:
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def codex_paths(home: Path | None = None) -> tuple[Path, Path, Path]:
    codex = Path(os.environ.get("CODEX_HOME", "")) if os.environ.get("CODEX_HOME") else (home or Path.home()) / ".codex"
    return codex, codex / "memories", codex / ".bridgeforge-codex" / "memory-sync"


def _normalize_remote(value: str) -> str:
    normalized = value.strip().rstrip("/")
    return normalized[:-4] if normalized.lower().endswith(".git") else normalized


def _remote_targets_managed_repository(value: str) -> bool:
    normalized = _normalize_remote(value).replace("\\", "/").lower()
    return bool(
        normalized
        and (
            normalized.endswith(f"/{REPOSITORY.lower()}")
            or normalized.endswith(f":{REPOSITORY.lower()}")
        )
    )


def _authorization_payload(decision: str, remote: str | None) -> dict[str, object]:
    if decision not in CONSENT_VALUES:
        raise SyncError(f"unsupported native memories consent: {decision}")
    if decision == "approved":
        if not isinstance(remote, str) or not _remote_targets_managed_repository(remote):
            raise SyncError("approved native memories consent requires the managed repository remote")
        remote = _normalize_remote(remote)
    elif remote is not None:
        raise SyncError("declined native memories consent must not retain a remote authorization")
    return {
        "decision": decision,
        "policy_version": CONSENT_POLICY_VERSION,
        "scope": CONSENT_SCOPE,
        "sync_mode": CONSENT_SYNC_MODE,
        "auto_hook_maintenance": True,
        "repository": REPOSITORY,
        "require_private": True,
        "remote": remote,
    }


def _validate_authorization(value: object) -> str:
    if not isinstance(value, dict) or set(value) != {
        "decision",
        "policy_version",
        "scope",
        "sync_mode",
        "auto_hook_maintenance",
        "repository",
        "require_private",
        "remote",
    }:
        raise SyncError("managed ledger has invalid native memories consent")
    decision = value.get("decision")
    if decision not in CONSENT_VALUES:
        raise SyncError("managed ledger has invalid native memories consent")
    expected = _authorization_payload(
        str(decision),
        str(value["remote"]) if value.get("remote") is not None else None,
    )
    if value != expected:
        raise SyncError("managed ledger has invalid native memories authorization scope")
    return str(decision)


def managed_ledger(path: Path) -> dict[str, object]:
    """Read the existing schema-v1 Codex ledger without inventing preference state."""
    if not path.is_file() or _is_link_or_reparse(path):
        raise SyncError(f"managed ledger is missing or unsafe: {path}")
    try:
        data = HOOKS_OWNERSHIP.load_json_object(path.read_bytes(), str(path))
    except (OSError, RuntimeError) as exc:
        raise SyncError(f"invalid managed ledger: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise SyncError("managed ledger must use schema_version 1")
    if data.get("platform") != "codex" or not isinstance(data.get("records"), dict):
        raise SyncError("managed ledger is not a Codex schema-v1 ledger")
    allowed_keys = {"schema_version", "platform", "records", "consents"}
    if not set(data).issubset(allowed_keys):
        raise SyncError("managed ledger contains unsupported top-level fields")
    for name, record in data["records"].items():
        if not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) is None:
            raise SyncError("managed ledger contains an invalid record name")
        if not isinstance(record, dict):
            raise SyncError(f"managed ledger record is invalid: {name}")
        if (
            re.fullmatch(r"[0-9a-f]{40}", str(record.get("source_commit", ""))) is None
            or re.fullmatch(r"sha256:[0-9a-f]{64}", str(record.get("content_hash", ""))) is None
            or not isinstance(record.get("installed_at"), str)
            or not record["installed_at"].strip()
        ):
            raise SyncError(f"managed ledger record is invalid: {name}")
    consents = data.get("consents")
    if consents is not None:
        if not isinstance(consents, dict) or set(consents) != {"native_memories"}:
            raise SyncError("managed ledger has invalid native memories consent")
        _validate_authorization(consents.get("native_memories"))
    return data


def native_memories_consent(ledger_path: Path) -> str | None:
    data = managed_ledger(ledger_path)
    consents = data.get("consents")
    if not isinstance(consents, dict):
        return None
    return _validate_authorization(consents["native_memories"])


def native_memories_authorization(ledger_path: Path) -> dict[str, object] | None:
    data = managed_ledger(ledger_path)
    consents = data.get("consents")
    if not isinstance(consents, dict):
        return None
    value = consents["native_memories"]
    _validate_authorization(value)
    return value


def record_native_memories_consent(
    ledger_path: Path,
    value: str,
    *,
    confirmed: bool,
    remote: str | None = None,
) -> bool:
    if not confirmed:
        raise SyncError("consent changes require explicit confirmation")
    data = managed_ledger(ledger_path)
    before = data.get("consents")
    desired = {"native_memories": _authorization_payload(value, remote)}
    if before == desired:
        return False
    data["consents"] = desired
    _atomic_json(ledger_path, data)
    return True


def _configured_remote(state_dir: Path) -> str:
    remote_file = state_dir / "remote.txt"
    if not remote_file.is_file() or _is_link_or_reparse(remote_file):
        raise SyncError("native memories remote authorization is missing or unsafe")
    remote = remote_file.read_text(encoding="utf-8-sig").strip()
    if not _remote_targets_managed_repository(remote):
        raise SyncError("native memories remote is outside the approved repository scope")
    return _normalize_remote(remote)


def require_runtime_authorization(
    ledger_path: Path,
    state_dir: Path,
) -> dict[str, object]:
    value = native_memories_authorization(ledger_path)
    decision = _validate_authorization(value) if value is not None else None
    if decision != "approved":
        raise SyncError("native memories automatic synchronization is not approved")
    remote = _configured_remote(state_dir)
    assert isinstance(value, dict)
    if _normalize_remote(str(value["remote"])) != remote:
        raise SyncError("native memories remote changed outside the approved scope")
    return value


def _memory_switches_from_bytes(
    raw: bytes | None,
) -> tuple[bool, dict[str, object]]:
    if raw is None:
        return False, {}
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


def memory_switches(config_path: Path) -> tuple[bool, dict[str, object]]:
    return _memory_switches_from_bytes(_read_optional_bytes(config_path))


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


def _windows_hook_command(script: Path, event: str) -> str:
    wrapper = script.resolve().with_name(WINDOWS_HOOK_WRAPPER_NAME)
    raw_wrapper = str(wrapper).replace('"', '`"')
    return (
        "powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden "
        f'-ExecutionPolicy Bypass -File "{raw_wrapper}" {event}'
    )


def _legacy_cmd_hook_command(script: Path, event: str) -> str:
    wrapper = script.resolve().with_name(LEGACY_WINDOWS_HOOK_WRAPPER_NAME)
    raw_wrapper = str(wrapper).replace('"', '""')
    return f'cmd.exe /d /c call "{raw_wrapper}" {event}'


def _legacy_inline_powershell_hook_handler(
    event: str,
    script: Path,
) -> dict[str, object]:
    """Reconstruct the exact v1 handler that is safe to migrate in place."""
    if event not in HOOK_EVENTS:
        raise SyncError(f"unsupported hook event: {event}")
    args = (
        "kick --trigger session-end"
        if event == "SessionEnd"
        else f"reconcile --trigger {event.lower()}"
    )
    managed_script = script.resolve()
    posix_script = shlex.quote(str(managed_script))
    powershell_script = "'" + str(managed_script).replace("'", "''") + "'"
    handler: dict[str, object] = {
        "type": "command",
        "command": (
            'root="$(git rev-parse --show-toplevel)" && '
            f'"$root/.venv/Scripts/python.exe" {posix_script} {args} '
            '--project-root "$root"'
        ),
        "commandWindows": (
            'powershell -NoProfile -Command "$root = (git rev-parse --show-toplevel); '
            f"& (Join-Path $root '.venv/Scripts/python.exe') {powershell_script} {args} "
            '--project-root $root"'
        ),
        HOOK_MARKER_KEY: f"{HOOK_ID}:{event}",
    }
    if event == "Stop":
        handler["async"] = True
        handler["timeout"] = 120
    if event == "SessionStart":
        handler["timeout"] = 120
    if event == "SessionEnd":
        handler["timeout"] = 3
    return handler


def _hook_handler(event: str, script: Path) -> dict[str, object]:
    if event not in HOOK_EVENTS:
        raise SyncError(f"unsupported hook event: {event}")
    managed_script = script.resolve()
    posix_script = shlex.quote(str(managed_script))
    handler: dict[str, object] = {
        "type": "command",
        "command": (
            'root="$(git rev-parse --show-toplevel)" && '
            f'"$root/.venv/Scripts/python.exe" {posix_script} hook-run '
            f'--event {event} '
            '--project-root "$root"'
        ),
        "commandWindows": _windows_hook_command(script, event),
        HOOK_MARKER_KEY: f"{HOOK_ID}:{event}",
    }
    if event == "Stop":
        handler["async"] = True
        handler["timeout"] = 120
    if event == "SessionStart":
        handler["timeout"] = 120
    if event == "SessionEnd":
        handler["timeout"] = 3
    return handler


def _legacy_cmd_hook_handler(event: str, script: Path) -> dict[str, object]:
    """Reconstruct the exact visible-console v2 handler for safe migration."""
    if event not in HOOK_EVENTS:
        raise SyncError(f"unsupported hook event: {event}")
    managed_script = script.resolve()
    posix_script = shlex.quote(str(managed_script))
    handler: dict[str, object] = {
        "type": "command",
        "command": (
            'root="$(git rev-parse --show-toplevel)" && '
            f'"$root/.venv/Scripts/python.exe" {posix_script} hook-run '
            f'--event {event} '
            '--project-root "$root"'
        ),
        "commandWindows": _legacy_cmd_hook_command(script, event),
        HOOK_MARKER_KEY: f"{HOOK_ID}:{event}",
    }
    if event == "Stop":
        handler["async"] = True
        handler["timeout"] = 120
    if event == "SessionStart":
        handler["timeout"] = 120
    if event == "SessionEnd":
        handler["timeout"] = 3
    return handler


def _migrate_exact_legacy_hook_handlers(
    document: dict[str, object],
    script: Path,
) -> None:
    """Upgrade only exact factory v1 handlers; edited drift stays fail-closed."""
    hooks = document.get("hooks")
    if not isinstance(hooks, dict):
        return
    for event in HOOK_EVENTS:
        groups = hooks.get(event)
        if not isinstance(groups, list):
            continue
        legacy_inline = _legacy_inline_powershell_hook_handler(event, script)
        legacy_cmd = _legacy_cmd_hook_handler(event, script)
        current = _hook_handler(event, script)
        for group in groups:
            if not isinstance(group, dict):
                continue
            handlers = group.get("hooks")
            if not isinstance(handlers, list):
                continue
            for index, handler in enumerate(handlers):
                if handler in (legacy_inline, legacy_cmd):
                    handlers[index] = current.copy()


def _read_optional_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


def _restore_optional_bytes(path: Path, payload: bytes | None) -> None:
    if payload is None:
        path.unlink(missing_ok=True)
    else:
        _atomic_bytes(path, payload)


def _render_user_hooks(
    payload: bytes | None,
    hooks_path: Path,
    script: Path,
) -> bytes:
    if payload is not None:
        try:
            document = HOOKS_OWNERSHIP.load_document(payload, str(hooks_path))
        except RuntimeError as exc:
            raise SyncError(f"invalid user hooks.json: {exc}") from exc
    else:
        document = {"hooks": {}}
    _migrate_exact_legacy_hook_handlers(document, script)
    expected_document = {
        "hooks": {
            event: [{"hooks": [_hook_handler(event, script)]}]
            for event in HOOK_EVENTS
        }
    }
    try:
        expected = HOOKS_OWNERSHIP.expected_groups(
            expected_document,
            managed_prefix=HOOK_ID + ":",
        )
        document, _external, _receipts = HOOKS_OWNERSHIP.canonicalize(
            document,
            expected,
            managed_prefixes=(HOOK_ID + ":",),
            label=str(hooks_path),
            managed_looking=lambda handler: (
                isinstance(handler.get(HOOK_MARKER_KEY), str)
                and handler[HOOK_MARKER_KEY].startswith(HOOK_ID + ":")
            ),
            replace_marked_drift=False,
        )
    except RuntimeError as exc:
        raise SyncError(f"user hooks ownership is invalid: {exc}") from exc
    return HOOKS_OWNERSHIP.render_document(document)


def merge_user_hooks(
    hooks_path: Path,
    script: Path,
    *,
    expected_before: bytes | None | object = ...,
) -> bool:
    initial = _read_optional_bytes(hooks_path)
    if expected_before is not ... and initial != expected_before:
        raise HookLockConflict("user hooks changed before the locked CAS")
    desired = _render_user_hooks(initial, hooks_path, script)
    if initial == desired:
        return False
    if _read_optional_bytes(hooks_path) != initial:
        raise HookLockConflict("user hooks changed during the locked CAS")
    _atomic_bytes(hooks_path, desired)
    return True


def user_hooks_healthy(
    hooks_path: Path,
    script: Path,
) -> bool:
    try:
        document = HOOKS_OWNERSHIP.load_document(
            hooks_path.read_bytes(),
            str(hooks_path),
        )
        expected_document = {
            "hooks": {
                event: [{"hooks": [_hook_handler(event, script)]}]
                for event in HOOK_EVENTS
            }
        }
        expected = HOOKS_OWNERSHIP.expected_groups(
            expected_document,
            managed_prefix=HOOK_ID + ":",
        )
        HOOKS_OWNERSHIP.validate_current(
            document,
            expected,
            managed_prefixes=(HOOK_ID + ":",),
            label=str(hooks_path),
            managed_looking=lambda handler: (
                isinstance(handler.get(HOOK_MARKER_KEY), str)
                and handler[HOOK_MARKER_KEY].startswith(HOOK_ID + ":")
            ),
        )
        return True
    except (OSError, KeyError, TypeError, json.JSONDecodeError, RuntimeError):
        return False


def _excluded(relative: Path) -> bool:
    return (
        any(
            part in {"__pycache__", ".git", ".bridgeforge", ".bridgeforge-codex"}
            for part in relative.parts
        )
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


def launch_background_reconcile(trigger: str, project_root: Path) -> None:
    root = project_root.resolve()
    command = [
        str(Path(sys.executable).resolve()),
        str(Path(__file__).resolve()),
        "reconcile",
        "--trigger",
        trigger,
        "--project-root",
        str(root),
    ]
    kwargs: dict[str, object] = {
        "cwd": root,
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


def _hook_runtime_receipt_path(state_dir: Path, event: str) -> Path:
    if event not in HOOK_EVENTS:
        raise SyncError(f"unsupported hook event: {event}")
    return state_dir / f"hook-runtime-{event.lower()}.json"


def latest_hook_runtime_receipt(state_dir: Path) -> dict[str, object] | None:
    receipts: list[dict[str, object]] = []
    for event in HOOK_EVENTS:
        path = _hook_runtime_receipt_path(state_dir, event)
        if not path.is_file() or _is_link_or_reparse(path):
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            receipts.append(value)
    if not receipts:
        return None
    return max(
        receipts,
        key=lambda item: str(item.get("completedUtc") or item.get("startedUtc") or ""),
    )


def hook_runtime_verified(receipt: dict[str, object] | None) -> bool:
    return bool(
        receipt
        and receipt.get("handlerRevision") == HOOK_RUNTIME_REVISION
        and receipt.get("status") == "succeeded"
    )


def run_hook_event(
    event: str,
    codex: Path,
    memories: Path,
    state_dir: Path,
    ledger_path: Path,
    project_root: Path,
) -> int:
    _real_directory(state_dir, create=True)
    receipt_path = _hook_runtime_receipt_path(state_dir, event)
    receipt: dict[str, object] = {
        "handlerRevision": HOOK_RUNTIME_REVISION,
        "event": event,
        "projectRoot": str(project_root.resolve()),
        "status": "started",
        "startedUtc": utc_now(),
    }
    _atomic_json(receipt_path, receipt)
    try:
        enabled, _ = memory_switches(codex / "config.toml")
        if not enabled:
            action = "disabled"
        elif event == "SessionEnd":
            validated_runtime_state(codex, state_dir, ledger_path)
            mark_pending(state_dir, "session-end")
            launch_background_reconcile("session-end", project_root)
            action = "kicked"
        else:
            state_dir, authorization = validated_runtime_state(
                codex,
                state_dir,
                ledger_path,
            )
            remote = str(authorization["remote"])
            verify_private_github_repository(remote)
            action = reconcile(memories, state_dir, remote)
        receipt.update({
            "status": "succeeded",
            "action": action,
            "completedUtc": utc_now(),
        })
        _atomic_json(receipt_path, receipt)
        return 0
    except Exception as exc:
        try:
            mark_pending(state_dir, event.lower())
        except Exception:
            pass
        receipt.update({
            "status": "failed",
            "error": str(exc),
            "completedUtc": utc_now(),
        })
        try:
            _atomic_json(receipt_path, receipt)
        except Exception:
            pass
        print(f"[memory-sync] WARNING: {exc}", file=sys.stderr)
        return 0


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


def verify_private_github_repository(
    remote: str,
    *,
    run: Run = _default_run,
) -> None:
    if not _remote_targets_managed_repository(remote):
        raise SyncError("native memories remote is outside the approved repository scope")
    if shutil.which("gh") is None:
        raise SyncError("gh is not installed; automatic memories synchronization stopped")
    view = run(
        [
            "gh",
            "repo",
            "view",
            remote,
            "--json",
            "visibility,url,nameWithOwner",
        ]
    )
    if view.returncode:
        raise SyncError("approved memories repository identity cannot be verified")
    try:
        data = json.loads(view.stdout)
    except json.JSONDecodeError as exc:
        raise SyncError("approved memories repository returned invalid metadata") from exc
    if str(data.get("visibility", "")).upper() != "PRIVATE":
        raise SyncError("approved memories repository is no longer private")
    if str(data.get("nameWithOwner", "")).split("/")[-1].lower() != REPOSITORY.lower():
        raise SyncError("approved memories repository identity changed")


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
    env.update({"GIT_AUTHOR_NAME": "bridgeforge-codex Memory Sync", "GIT_AUTHOR_EMAIL": "bridgeforge-codex@invalid", "GIT_COMMITTER_NAME": "bridgeforge-codex Memory Sync", "GIT_COMMITTER_EMAIL": "bridgeforge-codex@invalid"})
    commit = _git(["commit-tree", tree, "-m", "bridgeforge-codex memories snapshot"], publish, env=env)
    _git(["update-ref", "refs/heads/main", commit], publish)
    _git(["remote", "add", "origin", remote], publish)
    lease = f"--force-with-lease=refs/heads/main:{expected}" if expected else "--force-with-lease=refs/heads/main:"
    _git(["push", lease, "origin", "refs/heads/main:refs/heads/main"], publish)
    return commit


def _restore_snapshot(extracted: Path, memories: Path) -> None:
    incoming = extracted / "memories"
    capture_manifest(incoming, 0)
    stage = memories.parent / f".{memories.name}.bridgeforge-codex-incoming"
    old = memories.parent / f".{memories.name}.bridgeforge-codex-replaced"
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


def repair_user_hooks(
    codex: Path,
    current_state_dir: Path,
    ledger_path: Path,
    config_path: Path,
    script: Path,
    project_root: Path,
) -> HookRepairReceipt:
    actual_runtime = str(Path(sys.executable).resolve())
    hooks_path = codex / "hooks.json"
    try:
        with user_hooks_lock(codex):
            hooks_before: bytes | None = None
            ledger_before: bytes | None = None
            config_before: bytes | None = None
            mutated = False
            hook_written = False
            try:
                if hooks_path.exists() and _is_link_or_reparse(hooks_path):
                    raise SyncError("native memories hooks target is a link or reparse point")
                hooks_before = _read_optional_bytes(hooks_path)
                ledger_before = ledger_path.read_bytes()
                config_before = _read_optional_bytes(config_path)
                enabled, _config = _memory_switches_from_bytes(config_before)
                if native_memories_consent(ledger_path) != "approved":
                    raise SyncError("native memories maintenance requires approved consent")
                if not enabled:
                    raise SyncError("native memories were disabled by the user")

                # Strictly parse and calculate the desired hooks before any mutation.
                desired_hooks = _render_user_hooks(hooks_before, hooks_path, script)
                require_runtime_authorization(
                    ledger_path,
                    current_state_dir,
                )

                current_hooks = _read_optional_bytes(hooks_path)
                if current_hooks != hooks_before:
                    raise HookLockConflict("user hooks changed after the locked read")
                if _read_optional_bytes(config_path) != config_before:
                    raise HookLockConflict("user config changed after the locked read")
                hook_changed = False
                if desired_hooks != current_hooks:
                    if _read_optional_bytes(hooks_path) != hooks_before:
                        raise HookLockConflict("user hooks changed during the locked CAS")
                    _atomic_bytes(hooks_path, desired_hooks)
                    hook_changed = True
                    hook_written = True
                    mutated = True
                if not user_hooks_healthy(hooks_path, script):
                    raise SyncError("native memories hooks failed post-repair validation")
                return HookRepairReceipt(
                    "applied" if mutated or hook_changed else "unchanged",
                    DYNAMIC_HOOK_RUNTIME,
                    actual_runtime,
                )
            except Exception as exc:
                external_after_write = (
                    hook_written and _read_optional_bytes(hooks_path) != desired_hooks
                )
                if mutated and ledger_before is not None:
                    if hook_written and not external_after_write:
                        _restore_optional_bytes(hooks_path, hooks_before)
                    _atomic_bytes(ledger_path, ledger_before)
                return HookRepairReceipt(
                    (
                        "rolled_back"
                        if (
                            mutated
                            and not isinstance(exc, HookLockConflict)
                            and not external_after_write
                        )
                        else "conflicted"
                    ),
                    DYNAMIC_HOOK_RUNTIME,
                    actual_runtime,
                    str(exc),
                )
    except HookLockConflict as exc:
        return HookRepairReceipt(
            "conflicted",
            DYNAMIC_HOOK_RUNTIME,
            actual_runtime,
            str(exc),
        )
    except Exception as exc:
        return HookRepairReceipt(
            "conflicted",
            DYNAMIC_HOOK_RUNTIME,
            actual_runtime,
            str(exc),
        )


def validated_runtime_state(
    codex: Path,
    current_state_dir: Path,
    ledger_path: Path,
) -> tuple[Path, dict[str, object]]:
    del codex
    authorization = require_runtime_authorization(
        ledger_path,
        current_state_dir,
    )
    return current_state_dir, authorization


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < MIN_PYTHON:
        print("[memory-sync] WARNING: Python 3.11+ is required", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def project_command(name: str) -> argparse.ArgumentParser:
        command = sub.add_parser(name)
        command.add_argument("--project-root", type=Path, required=True)
        return command

    setup = project_command("setup")
    setup.add_argument("--confirmed-enable", action="store_true")
    setup.add_argument("--confirmed-public-to-private", action="store_true")
    decline = project_command("decline")
    decline.add_argument("--confirmed", action="store_true")
    project_command("maintain")
    project_command("repair-hook")
    reconcile_cmd = project_command("reconcile")
    reconcile_cmd.add_argument("--trigger", default="bridgeforge-codex")
    hook_run = project_command("hook-run")
    hook_run.add_argument("--event", choices=HOOK_EVENTS, required=True)
    mark = project_command("mark")
    mark.add_argument("--trigger", required=True)
    kick = project_command("kick")
    kick.add_argument("--trigger", required=True)
    project_command("status")
    args = parser.parse_args(argv)
    codex, memories, current_state_dir = codex_paths()
    state_dir = current_state_dir
    ledger_path = codex / "bridgeforge-codex-managed.json"
    runtime_ready = False
    try:
        if args.command == "status":
            if not codex.is_dir() or _is_link_or_reparse(codex):
                raise SyncError(f"Codex home is missing or unsafe: {codex}")
            runtime_drift_reason: str | None = None
            try:
                project_root, _expected_python = _validated_project_runtime(args.project_root)
            except SyncError as exc:
                project_root = args.project_root.resolve()
                runtime_drift_reason = str(exc)
            with user_hooks_lock(codex):
                enabled, _ = memory_switches(codex / "config.toml")
                remote_configured = (state_dir / "remote.txt").is_file()
                authorization = native_memories_authorization(ledger_path)
                hook_installed = user_hooks_healthy(
                    codex / "hooks.json",
                    Path(__file__).resolve(),
                )
                hook_runtime = latest_hook_runtime_receipt(state_dir)
            print(json.dumps({
                "enabled": enabled,
                "hookInstalled": hook_installed,
                "hookRuntimeVerified": hook_runtime_verified(hook_runtime),
                "hookRuntimeReceipt": hook_runtime,
                "pending": (state_dir / "pending.json").exists(),
                "projectRoot": str(project_root),
                "runtimeContract": HOOK_RUNTIME_CONTRACT,
                "configuredRuntime": DYNAMIC_HOOK_RUNTIME,
                "actualRuntime": str(Path(sys.executable).resolve()),
                "runtimeDriftReason": runtime_drift_reason,
                "remoteConfigured": remote_configured,
                "consent": (
                    _validate_authorization(authorization)
                    if authorization is not None
                    else None
                ),
                "consentPolicyVersion": (
                    authorization.get("policy_version")
                    if authorization is not None
                    else None
                ),
                "syncMode": (
                    authorization.get("sync_mode")
                    if authorization is not None
                    else None
                ),
            }, ensure_ascii=False))
            return 2 if runtime_drift_reason else 0

        project_root, _expected_python = _validated_project_runtime(args.project_root)
        runtime_ready = True
        if args.command == "decline":
            with user_hooks_lock(codex):
                changed = record_native_memories_consent(
                    ledger_path,
                    "declined",
                    confirmed=args.confirmed,
                    remote=None,
                )
            print(f"[memory-sync] native memories declined; changed={str(changed).lower()}")
            return 0
        _real_directory(codex, create=True)
        if args.command == "hook-run":
            return run_hook_event(
                args.event,
                codex,
                memories,
                current_state_dir,
                ledger_path,
                project_root,
            )
        if args.command in {"maintain", "repair-hook"}:
            receipt = repair_user_hooks(
                codex,
                current_state_dir,
                ledger_path,
                codex / "config.toml",
                Path(__file__).resolve(),
                project_root,
            )
            print(
                "[memory-sync] hooks repaired; "
                f"hook_repair={receipt.hook_repair}; "
                f"configured_runtime={receipt.configured_runtime}; "
                f"actual_runtime={receipt.actual_runtime}; "
                f"runtime_drift_reason={receipt.runtime_drift_reason or 'none'}; "
                "remote_reconcile=not_requested"
            )
            return 0 if receipt.hook_repair in {"applied", "unchanged"} else 2
        if args.command in {"mark", "kick"}:
            enabled, _ = memory_switches(codex / "config.toml")
            if enabled:
                state_dir, _authorization = validated_runtime_state(
                    codex,
                    current_state_dir,
                    ledger_path,
                )
                mark_pending(state_dir, args.trigger)
                if args.command == "kick":
                    launch_background_reconcile(args.trigger, project_root)
            return 0
        if args.command == "setup":
            hooks_path = codex / "hooks.json"
            config_path = codex / "config.toml"
            with user_hooks_lock(codex):
                ledger_snapshot = ledger_path.read_bytes()
                managed_ledger(ledger_path)
                hooks_snapshot = _read_optional_bytes(hooks_path)
                _render_user_hooks(hooks_snapshot, hooks_path, Path(__file__).resolve())
                config_snapshot = _read_optional_bytes(config_path)
                enabled, _config = _memory_switches_from_bytes(config_snapshot)
                if not enabled and not args.confirmed_enable:
                    raise SyncError(
                        "native memories remain unchanged without --confirmed-enable"
                    )

            remote, remote_action = ensure_github_repository(
                confirmed_public_to_private=args.confirmed_public_to_private
            )

            with user_hooks_lock(codex):
                local_mutated = False
                try:
                    if (
                        ledger_path.read_bytes() != ledger_snapshot
                        or _read_optional_bytes(hooks_path) != hooks_snapshot
                        or _read_optional_bytes(config_path) != config_snapshot
                    ):
                        raise HookLockConflict("user configuration changed during setup preflight")
                    state_dir = current_state_dir
                    _real_directory(state_dir, create=True)
                    remote_path = state_dir / "remote.txt"
                    remote_snapshot = _read_optional_bytes(remote_path)
                    if not enabled:
                        local_mutated = enable_memories(config_path, confirmed=True) or local_mutated
                    hook_changed = merge_user_hooks(
                        hooks_path,
                        Path(__file__).resolve(),
                        expected_before=hooks_snapshot,
                    )
                    local_mutated = hook_changed or local_mutated
                    _atomic_text(remote_path, remote + "\n")
                    local_mutated = True
                    record_native_memories_consent(
                        ledger_path,
                        "approved",
                        confirmed=True,
                        remote=remote,
                    )
                    if not user_hooks_healthy(hooks_path, Path(__file__).resolve()):
                        raise SyncError("native memories hooks failed post-setup validation")
                except Exception:
                    if local_mutated:
                        _restore_optional_bytes(hooks_path, hooks_snapshot)
                        _restore_optional_bytes(config_path, config_snapshot)
                        _atomic_bytes(ledger_path, ledger_snapshot)
                        if "remote_path" in locals():
                            _restore_optional_bytes(remote_path, remote_snapshot)
                    raise
            print(
                "[memory-sync] configured; "
                f"hook_repair={'applied' if hook_changed else 'unchanged'}; "
                f"configured_runtime={DYNAMIC_HOOK_RUNTIME}; "
                f"actual_runtime={Path(sys.executable).resolve()}; "
                "runtime_drift_reason=none; hook_installed=true; "
                f"remote_configured=true; remote_action={remote_action}; remote={remote}; "
                "review/trust the user hooks in /hooks"
            )
            return 0
        enabled, _ = memory_switches(codex / "config.toml")
        if not enabled:
            return 0
        state_dir, authorization = validated_runtime_state(
            codex,
            current_state_dir,
            ledger_path,
        )
        remote = str(authorization["remote"])
        verify_private_github_repository(remote)
        action = reconcile(memories, state_dir, remote)
        if args.trigger == "bridgeforge":
            print(f"[memory-sync] {action}")
        elif args.trigger == "stop":
            print("{}")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError, SyncError) as exc:
        if runtime_ready and args.command not in {"status", "decline", "setup", "maintain", "repair-hook"}:
            try:
                mark_pending(state_dir, getattr(args, "trigger", args.command))
            except Exception:
                pass
        print(f"[memory-sync] WARNING: {exc}", file=sys.stderr)
        return 2 if (
            not runtime_ready
            or args.command in {"status", "decline", "setup", "maintain", "repair-hook"}
        ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
