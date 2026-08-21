#!/usr/bin/env python3
"""Read-only preflight and state control for bridgeforge-codex batch runs."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Sequence


SCHEMA_VERSION = 2
CANONICAL_REMOTE = "https://github.com/freakybridge/BridgeForgeCodex.git"
FACTORY_WITNESSES = (
    "bridgeforge-codex-manifest.json",
    "templates/managed-skeleton.json",
    "skills/bridgeforge-codex/SKILL.md",
    "scripts/bridgeforge_codex_project_sync.py",
    ".codex/scripts/current_baseline.py",
)
TARGET_WITNESSES = (
    ".venv/Scripts/python.exe",
    ".codex/.bridgeforge_codex_version",
    ".codex/scripts/current_baseline.py",
    ".codex/scripts/codex_git_sync.py",
)
SEMVER_RE = re.compile(r"\d+\.\d+\.\d+")
BATCH_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{5,63}")
SIGNATURE_RE = re.compile(r"[a-z0-9][a-z0-9._:-]{2,127}")
SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}")
PROBLEM_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|(?:^|\s)/(?:[^\s/]+))")
INTERNAL_TERMS = (
    "traceback",
    "problem_signature",
    "common_git_dir",
    "mutex_group",
    "execution_status",
    "blockers=",
)


class BatchError(RuntimeError):
    """The requested batch transition is unsafe or invalid."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _git(root: Path, *arguments: str, allow_failure: bool = False) -> str:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *arguments],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode and not allow_failure:
        detail = result.stderr.strip() or result.stdout.strip() or "Git command failed"
        raise BatchError(detail)
    return result.stdout.strip() if result.returncode == 0 else ""


def _resolved_directory(value: str | Path, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise BatchError(f"{label}不存在或不是目录：{path}")
    return path


def _exact_git_root(path: Path, label: str) -> None:
    git_root = Path(_git(path, "rev-parse", "--show-toplevel")).resolve()
    if git_root != path:
        raise BatchError(f"{label}必须直接指向 Git 工作区根目录：{path}")


def _validate_factory_baseline(root: Path) -> dict[str, Any]:
    checker = root / ".codex/scripts/current_baseline.py"
    python = root / ".venv/Scripts/python.exe"
    if not python.is_file():
        raise BatchError("bridgeforge-codex 项目虚拟环境不可用")
    result = subprocess.run(
        [str(python), "-B", str(checker), "--project-root", str(root)],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise BatchError(f"本地骨架检查未通过：{detail}")
    try:
        receipt = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise BatchError("本地骨架检查没有返回可验证收据") from exc
    if (
        not isinstance(receipt, dict)
        or receipt.get("status") != "passed"
        or not SEMVER_RE.fullmatch(str(receipt.get("version", "")))
        or not isinstance(receipt.get("fingerprint"), str)
    ):
        raise BatchError("本地骨架检查收据不完整")
    return receipt


def _validate_target_baseline(root: Path) -> dict[str, Any]:
    checker = root / ".codex/scripts/current_baseline.py"
    python = root / ".venv/Scripts/python.exe"
    version = _target_version(root)
    result = subprocess.run(
        [
            str(python),
            "-B",
            str(checker),
            "--project-root",
            str(root),
            "--expected-version",
            version,
        ],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise BatchError(f"下游骨架检查未通过：{detail}")
    try:
        receipt = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise BatchError("下游骨架检查没有返回可验证收据") from exc
    if (
        not isinstance(receipt, dict)
        or receipt.get("status") != "passed"
        or receipt.get("version") != version
    ):
        raise BatchError("下游骨架检查结果与版本标记不一致")
    return receipt


def inspect_factory(factory_root: str | Path) -> dict[str, Any]:
    """Prove that the clean local factory matches its local origin/main evidence."""

    root = _resolved_directory(factory_root, "bridgeforge-codex 根目录")
    _exact_git_root(root, "bridgeforge-codex 根目录")
    missing = [relative for relative in FACTORY_WITNESSES if not (root / relative).is_file()]
    if missing:
        raise BatchError("当前仓库不是完整的 bridgeforge-codex 工厂")
    if _git(root, "remote", "get-url", "origin") != CANONICAL_REMOTE:
        raise BatchError("bridgeforge-codex origin 不是官方 GitHub 仓库")
    if _git(root, "branch", "--show-current") != "main":
        raise BatchError("bridgeforge-codex 必须位于 main 分支")
    if _git(root, "rev-parse", "--abbrev-ref", "@{upstream}") != "origin/main":
        raise BatchError("bridgeforge-codex main 没有跟踪 origin/main")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise BatchError("bridgeforge-codex 仍有未提交更改")
    head = _git(root, "rev-parse", "HEAD")
    origin_main = _git(root, "rev-parse", "refs/remotes/origin/main")
    counts = _git(root, "rev-list", "--left-right", "--count", "HEAD...origin/main").split()
    if head != origin_main or counts != ["0", "0"]:
        raise BatchError("bridgeforge-codex 本地尚未与 GitHub 完全一致")
    baseline = _validate_factory_baseline(root)
    return {
        "root": str(root),
        "head": head,
        "origin_main": origin_main,
        "version": baseline.get("version"),
        "fingerprint": baseline.get("fingerprint"),
    }


def _target_version(root: Path) -> str:
    value = (root / ".codex/.bridgeforge_codex_version").read_text(
        encoding="utf-8-sig"
    ).strip()
    if not SEMVER_RE.fullmatch(value):
        raise BatchError(f"骨架版本标记无效：{root}")
    return value


def _git_common_dir(root: Path) -> Path:
    value = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _git_bytes(root: Path, *arguments: str) -> bytes:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", *arguments],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).decode("utf-8", errors="replace")
        raise BatchError(detail.strip() or "Git 命令未完成")
    return result.stdout


def _dirty_digest(root: Path) -> tuple[bool, str]:
    status_bytes = _git_bytes(
        root,
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
    )
    diff_bytes = _git_bytes(root, "diff", "--binary", "--no-ext-diff", "HEAD", "--")
    untracked = _git_bytes(root, "ls-files", "--others", "--exclude-standard", "-z")
    digest = hashlib.sha256(status_bytes + b"\0DIFF\0" + diff_bytes)
    for raw_relative in sorted(filter(None, untracked.split(b"\0"))):
        relative = raw_relative.decode("utf-8", errors="surrogateescape")
        candidate = root / relative
        digest.update(b"\0UNTRACKED\0" + raw_relative + b"\0")
        try:
            if candidate.is_symlink():
                digest.update(
                    os.readlink(candidate).encode("utf-8", errors="surrogateescape")
                )
            elif candidate.is_file():
                digest.update(candidate.read_bytes())
            else:
                digest.update(str(candidate.lstat().st_mode).encode("ascii"))
        except OSError as exc:
            raise BatchError(f"无法稳定读取下游改动摘要：{root.name}") from exc
    return bool(status_bytes), "sha256:" + digest.hexdigest()


def _target_snapshot(root: Path) -> dict[str, Any]:
    dirty, dirty_digest = _dirty_digest(root)
    return {
        "path": str(root),
        "head": _git(root, "rev-parse", "HEAD"),
        "branch": _git(root, "branch", "--show-current", allow_failure=True) or None,
        "upstream": _git(
            root,
            "rev-parse",
            "--abbrev-ref",
            "@{upstream}",
            allow_failure=True,
        )
        or None,
        "version": _target_version(root),
        "common_git_dir": str(_git_common_dir(root)),
        "dirty": dirty,
        "dirty_digest": dirty_digest,
    }


def inspect_targets(targets: Sequence[str | Path]) -> list[dict[str, Any]]:
    """Inspect only the target paths explicitly supplied for this batch."""

    if not targets:
        raise BatchError("至少需要输入一个下游项目路径")
    inspected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_target in enumerate(targets, start=1):
        root = _resolved_directory(raw_target, "下游项目路径")
        key = os.path.normcase(str(root))
        if key in seen:
            raise BatchError(f"下游项目路径重复：{root}")
        seen.add(key)
        _exact_git_root(root, "下游项目路径")
        if any(not (root / relative).is_file() for relative in TARGET_WITNESSES):
            raise BatchError(f"下游项目缺少批量维护入口：{root}")
        inspected.append(
            {
                "id": f"target-{index}",
                "path": str(root),
                "name": root.name,
                "display_name": root.name,
                "snapshot": _target_snapshot(root),
            }
        )
    name_counts: dict[str, int] = {}
    for item in inspected:
        name_key = item["name"].casefold()
        name_counts[name_key] = name_counts.get(name_key, 0) + 1
    used: set[str] = set()
    for index, item in enumerate(inspected, start=1):
        if name_counts[item["name"].casefold()] > 1:
            branch = item["snapshot"]["branch"] or "detached"
            display_name = f"{item['name']}（{branch}）"
            if display_name.casefold() in used:
                display_name = f"{display_name} #{index}"
            item["display_name"] = display_name
        used.add(item["display_name"].casefold())
    return inspected


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _plan_payload(
    factory: dict[str, Any],
    targets: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "factory": {
            "head": factory["head"],
            "fingerprint": factory["fingerprint"],
        },
        "targets": [item["snapshot"] for item in targets],
    }


def create_plan(factory_root: str | Path, targets: Sequence[str | Path]) -> dict[str, Any]:
    factory = inspect_factory(factory_root)
    inspected = inspect_targets(targets)
    return {
        "factory": factory,
        "targets": inspected,
        "plan_fingerprint": _canonical_hash(_plan_payload(factory, inspected)),
    }


def _new_batch_id() -> str:
    return datetime.now(timezone.utc).strftime("batch-%Y%m%d-%H%M%S-") + secrets.token_hex(3)


def _is_reparse(path: Path) -> bool:
    try:
        details = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(details, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return path.is_symlink() or bool(attributes & reparse_flag)


def _runtime_root(factory_root: Path, *, create: bool) -> Path:
    root = Path(os.path.abspath(factory_root))
    runtime = root / ".runtime"
    batch_root = runtime / "bridgeforge-codex-batch"
    for candidate in (root, runtime, batch_root):
        if _is_reparse(candidate):
            raise BatchError("批次运行时路径不能经过符号链接或 junction")
    if create:
        runtime.mkdir(exist_ok=True)
        batch_root.mkdir(exist_ok=True)
        if _is_reparse(runtime) or _is_reparse(batch_root):
            raise BatchError("批次运行时路径不能经过符号链接或 junction")
    try:
        batch_root.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise BatchError("批次运行时路径逃逸工厂仓库") from exc
    return batch_root


def _state_path(factory_root: Path, batch_id: str, *, create_root: bool = False) -> Path:
    if not BATCH_ID_RE.fullmatch(batch_id):
        raise BatchError("批次编号格式无效")
    return _runtime_root(factory_root, create=create_root) / f"{batch_id}.json"


def _lock_path(state_path: Path) -> Path:
    return state_path.with_suffix(".lock")


@contextlib.contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    if _is_reparse(path.parent) or _is_reparse(path):
        raise BatchError("批次锁路径不安全")
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise BatchError("另一个批次操作正在进行，请稍后重试") from exc
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode("ascii"))
        yield
    finally:
        os.close(descriptor)
        with contextlib.suppress(FileNotFoundError):
            path.unlink()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    if _is_reparse(path.parent) or _is_reparse(path):
        raise BatchError("批次状态路径不安全")
    temporary = path.with_suffix(path.suffix + f".{secrets.token_hex(4)}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _active_path(factory_root: Path) -> Path:
    return _runtime_root(factory_root, create=True) / "active.json"


def _control_lock(factory_root: Path) -> Path:
    return _runtime_root(factory_root, create=True) / "control.lock"


def _validate_snapshot(snapshot: Any) -> None:
    fields = {
        "path",
        "head",
        "branch",
        "upstream",
        "version",
        "common_git_dir",
        "dirty",
        "dirty_digest",
    }
    if not isinstance(snapshot, dict) or set(snapshot) != fields:
        raise BatchError("批次目标快照结构无效")
    required_strings = ("path", "head", "version", "common_git_dir", "dirty_digest")
    if not all(isinstance(snapshot[key], str) and snapshot[key] for key in required_strings):
        raise BatchError("批次目标快照字段无效")
    if not isinstance(snapshot["dirty"], bool) or not SHA256_RE.fullmatch(
        snapshot["dirty_digest"]
    ):
        raise BatchError("批次目标改动摘要无效")
    for optional in ("branch", "upstream"):
        if snapshot[optional] is not None and not isinstance(snapshot[optional], str):
            raise BatchError("批次目标 Git 字段无效")


def _validate_state(state: Any) -> None:
    state_fields = {
        "schema_version",
        "batch_id",
        "factory_root",
        "factory_snapshot",
        "plan_fingerprint",
        "generation",
        "phase",
        "created_at",
        "updated_at",
        "common_problem",
        "history",
        "targets",
    }
    factory_fields = {"root", "head", "origin_main", "version", "fingerprint"}
    target_fields = {
        "id",
        "path",
        "name",
        "display_name",
        "snapshot",
        "status",
        "attempts",
        "result",
    }
    result_fields = {
        "version",
        "github_saved",
        "problem_summary",
        "problem_signature",
    }
    common_fields = {
        "signature",
        "target_ids",
        "confirmed_by",
        "detected_at",
        "bug_doc",
        "blocked_factory_head",
        "blocked_factory_fingerprint",
    }
    if not isinstance(state, dict) or set(state) != state_fields:
        raise BatchError("批次状态结构无效")
    if state["schema_version"] != SCHEMA_VERSION:
        raise BatchError("批次状态版本不受支持")
    if not BATCH_ID_RE.fullmatch(str(state["batch_id"])):
        raise BatchError("批次编号无效")
    if not isinstance(state["factory_snapshot"], dict) or set(
        state["factory_snapshot"]
    ) != factory_fields:
        raise BatchError("批次工厂快照无效")
    factory = state["factory_snapshot"]
    if (
        not isinstance(state["factory_root"], str)
        or not state["factory_root"]
        or factory["root"] != state["factory_root"]
        or not all(
            isinstance(factory[key], str) and factory[key]
            for key in ("head", "origin_main", "version", "fingerprint")
        )
        or not SEMVER_RE.fullmatch(factory["version"])
        or not SHA256_RE.fullmatch(factory["fingerprint"])
    ):
        raise BatchError("批次工厂快照字段无效")
    if not SHA256_RE.fullmatch(str(state["plan_fingerprint"])):
        raise BatchError("批次计划指纹无效")
    phases = {"running", "common_pending_bug", "common_blocked", "completed"}
    if state["phase"] not in phases:
        raise BatchError("批次阶段无效")
    if not isinstance(state["generation"], int) or state["generation"] < 1:
        raise BatchError("批次 generation 无效")
    if not isinstance(state["targets"], list) or not state["targets"]:
        raise BatchError("批次目标列表无效")
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for item in state["targets"]:
        if not isinstance(item, dict) or set(item) != target_fields:
            raise BatchError("批次目标结构无效")
        if not all(
            isinstance(item[key], str) and item[key]
            for key in ("id", "path", "name", "display_name")
        ):
            raise BatchError("批次目标身份字段无效")
        if item["status"] not in {"pending", "running", "succeeded", "deferred"}:
            raise BatchError("批次目标状态无效")
        if not isinstance(item["attempts"], list):
            raise BatchError("批次尝试记录无效")
        for attempt in item["attempts"]:
            attempt_fields = {"generation", "started_at", "finished_at"}
            if not isinstance(attempt, dict) or set(attempt) != attempt_fields:
                raise BatchError("批次尝试记录结构无效")
        if item["result"] is not None and (
            not isinstance(item["result"], dict)
            or set(item["result"]) != result_fields
        ):
            raise BatchError("批次结果结构无效")
        _validate_snapshot(item["snapshot"])
        if item["path"] != item["snapshot"]["path"]:
            raise BatchError("批次目标路径与快照不一致")
        result = item["result"]
        if item["status"] in {"pending", "running"} and result is not None:
            raise BatchError("未完成目标不能带有终态结果")
        if item["status"] in {"succeeded", "deferred"} and result is None:
            raise BatchError("目标终态缺少结果")
        if item["status"] == "succeeded" and (
            not SEMVER_RE.fullmatch(str(result["version"]))
            or result["github_saved"] is not True
            or result["problem_summary"] is not None
            or result["problem_signature"] is not None
        ):
            raise BatchError("成功结果收据无效")
        if item["status"] == "deferred" and (
            result["version"] is not None
            or result["github_saved"] is not False
            or _problem_summary(result["problem_summary"]) != result["problem_summary"]
            or _stable_signature(result["problem_signature"])
            != result["problem_signature"]
        ):
            raise BatchError("暂缓结果收据无效")
        normalized = os.path.normcase(item["path"])
        if item["id"] in seen_ids or normalized in seen_paths:
            raise BatchError("批次目标身份重复")
        seen_ids.add(item["id"])
        seen_paths.add(normalized)
    common = state["common_problem"]
    if common is not None and (
        not isinstance(common, dict) or set(common) != common_fields
    ):
        raise BatchError("批次共性问题结构无效")
    if state["phase"] == "common_blocked" and (
        common is None or not isinstance(common.get("bug_doc"), str)
    ):
        raise BatchError("共性阻断缺少 Bug 文档关联")
    if common is not None:
        if (
            not isinstance(common["signature"], str)
            or _stable_signature(common["signature"], bridgeforge_only=True)
            != common["signature"]
            or not isinstance(common["target_ids"], list)
            or not common["target_ids"]
            or any(target_id not in seen_ids for target_id in common["target_ids"])
            or common["confirmed_by"]
            not in {"repeated_targets", "main_conversation_evidence"}
            or not isinstance(common["blocked_factory_head"], str)
            or not isinstance(common["blocked_factory_fingerprint"], str)
            or not SHA256_RE.fullmatch(common["blocked_factory_fingerprint"])
        ):
            raise BatchError("批次共性问题字段无效")
    if state["phase"] == "common_pending_bug" and (
        common is None or common["bug_doc"] is not None
    ):
        raise BatchError("待落盘共性问题状态无效")
    if state["phase"] in {"running", "completed"} and common is not None:
        raise BatchError("当前批次阶段不能携带共性问题")
    if not isinstance(state["history"], list):
        raise BatchError("批次历史结构无效")
    for entry in state["history"]:
        if not isinstance(entry, dict) or set(entry) != {
            "generation",
            "factory_snapshot",
            "common_problem",
            "closed_at",
        }:
            raise BatchError("批次历史条目结构无效")
    expected = _canonical_hash(_plan_payload(state["factory_snapshot"], state["targets"]))
    if expected != state["plan_fingerprint"]:
        raise BatchError("批次状态与计划指纹不一致")


def _load_state_unlocked(state_path: str | Path) -> tuple[Path, dict[str, Any]]:
    lexical = Path(os.path.abspath(Path(state_path).expanduser()))
    if _is_reparse(lexical) or _is_reparse(lexical.parent):
        raise BatchError("批次状态路径不能是符号链接或 junction")
    try:
        state = json.loads(lexical.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BatchError(f"批次状态不可读：{lexical}") from exc
    _validate_state(state)
    expected = _state_path(Path(state["factory_root"]), state["batch_id"])
    if os.path.normcase(str(lexical)) != os.path.normcase(str(expected)):
        raise BatchError("批次状态文件不在工厂运行时目录")
    return lexical, state


def _load_state(state_path: str | Path) -> tuple[Path, dict[str, Any]]:
    return _load_state_unlocked(state_path)


def _write_state(path: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = _now()
    _validate_state(state)
    _write_json(path, state)


def _assert_active(factory_root: Path, batch_id: str, state_path: Path) -> None:
    active = _active_path(factory_root)
    if _is_reparse(active):
        raise BatchError("工厂 active batch 路径不安全")
    try:
        value = json.loads(active.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BatchError("工厂没有可验证的 active batch") from exc
    expected = {"batch_id": batch_id, "state": str(state_path)}
    if not isinstance(value, dict) or set(value) != set(expected) or value != expected:
        raise BatchError("工厂 active batch 与当前状态不一致")


def _release_active(factory_root: Path, batch_id: str, state_path: Path) -> None:
    with _exclusive_lock(_control_lock(factory_root)):
        active = _active_path(factory_root)
        if not active.is_file():
            return
        _assert_active(factory_root, batch_id, state_path)
        active.unlink()


def start_batch(
    factory_root: str | Path,
    targets: Sequence[str | Path],
    plan_fingerprint: str,
    batch_id: str | None = None,
) -> Path:
    """Start the one active batch only if the confirmed plan still matches."""

    root = _resolved_directory(factory_root, "bridgeforge-codex 根目录")
    identifier = batch_id or _new_batch_id()
    state_path = _state_path(root, identifier, create_root=True)
    with _exclusive_lock(_control_lock(root)):
        active = _active_path(root)
        if active.exists():
            raise BatchError("bridgeforge-codex 已有未结束的批次")
        plan = create_plan(root, targets)
        if plan["plan_fingerprint"] != plan_fingerprint:
            raise BatchError("项目状态已变化，需要重新展示计划并确认")
        state = {
            "schema_version": SCHEMA_VERSION,
            "batch_id": identifier,
            "factory_root": str(root),
            "factory_snapshot": plan["factory"],
            "plan_fingerprint": plan["plan_fingerprint"],
            "generation": 1,
            "phase": "running",
            "created_at": _now(),
            "updated_at": _now(),
            "common_problem": None,
            "history": [],
            "targets": [
                {
                    **item,
                    "status": "pending",
                    "attempts": [],
                    "result": None,
                }
                for item in plan["targets"]
            ],
        }
        _write_state(state_path, state)
        _write_json(active, {"batch_id": identifier, "state": str(state_path)})
    return state_path


def _target(state: dict[str, Any], reference: str) -> dict[str, Any]:
    normalized = os.path.normcase(str(Path(reference).expanduser().resolve()))
    for item in state["targets"]:
        if item["id"] == reference or os.path.normcase(item["path"]) == normalized:
            return item
    raise BatchError(f"批次中没有该项目：{reference}")


def _assert_factory_locked(state: dict[str, Any]) -> None:
    current = inspect_factory(state["factory_root"])
    locked = state["factory_snapshot"]
    if current["head"] != locked["head"] or current["fingerprint"] != locked["fingerprint"]:
        raise BatchError("bridgeforge-codex 已变化，当前批次禁止继续分发")


def _next_target(state: dict[str, Any]) -> dict[str, Any] | None:
    for status in ("pending", "deferred"):
        for item in state["targets"]:
            if item["status"] == status:
                return item
    return None


def begin_target(state_path: str | Path, reference: str) -> None:
    lexical = Path(os.path.abspath(Path(state_path).expanduser()))
    with _exclusive_lock(_lock_path(lexical)):
        path, state = _load_state_unlocked(lexical)
        _assert_active(Path(state["factory_root"]), state["batch_id"], path)
        if state["phase"] != "running":
            raise BatchError("当前批次已阻断或结束，不能继续分发")
        if any(item["status"] == "running" for item in state["targets"]):
            raise BatchError("已有项目正在处理；批次禁止并行")
        item = _target(state, reference)
        expected = _next_target(state)
        if expected is None or item["id"] != expected["id"]:
            raise BatchError("必须按确认时的项目顺序处理")
        _assert_factory_locked(state)
        if _target_snapshot(Path(item["path"])) != item["snapshot"]:
            raise BatchError("该项目状态已变化，需要重新展示异常计划并确认")
        item["status"] = "running"
        item["result"] = None
        item["attempts"].append(
            {"generation": state["generation"], "started_at": _now(), "finished_at": None}
        )
        _write_state(path, state)


def _stable_signature(value: str | None, *, bridgeforge_only: bool = False) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold()
    if not SIGNATURE_RE.fullmatch(normalized):
        raise BatchError("问题签名必须是稳定类别，不能包含路径或报错正文")
    if bridgeforge_only and not normalized.startswith("bridgeforge:"):
        raise BatchError("共性骨架问题签名必须属于 bridgeforge 命名空间")
    return normalized


def _problem_summary(value: str | None) -> str:
    if value is None:
        raise BatchError("暂缓项目必须记录一句结论式原因")
    summary = value.strip()
    lowered = summary.casefold()
    if (
        not summary
        or len(summary) > 180
        or "\n" in summary
        or "\r" in summary
        or "/" in summary
        or "\\" in summary
        or PROBLEM_PATH_RE.search(summary)
        or any(term in lowered for term in INTERNAL_TERMS)
    ):
        raise BatchError("异常说明必须是单行白话结论，不能包含路径或内部技术信息")
    return summary


def _verified_success(root: Path) -> dict[str, Any]:
    receipt = _validate_target_baseline(root)
    version = _target_version(root)
    if receipt.get("version") != version:
        raise BatchError("骨架检查结果与项目版本不一致")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise BatchError("项目仍有尚未保存的改动")
    upstream = _git(root, "rev-parse", "--abbrev-ref", "@{upstream}", allow_failure=True)
    if not upstream:
        raise BatchError("项目没有可验证的 GitHub 同步目标")
    counts = _git(root, "rev-list", "--left-right", "--count", f"HEAD...{upstream}")
    if counts.split() != ["0", "0"]:
        raise BatchError("项目尚未与 GitHub 完全一致")
    return {
        "version": version,
        "github_saved": True,
        "problem_summary": None,
        "problem_signature": None,
    }


def _common_candidate(state: dict[str, Any]) -> tuple[str, list[str]] | None:
    signatures: dict[str, list[str]] = {}
    for item in state["targets"]:
        result = item.get("result") or {}
        signature = result.get("problem_signature")
        if (
            item["status"] == "deferred"
            and isinstance(signature, str)
            and signature.startswith("bridgeforge:")
        ):
            signatures.setdefault(signature, []).append(item["id"])
    return next(
        ((signature, ids) for signature, ids in signatures.items() if len(ids) >= 2),
        None,
    )


def finish_target(
    state_path: str | Path,
    reference: str,
    *,
    outcome: str,
    problem_summary: str | None = None,
    problem_signature: str | None = None,
) -> None:
    lexical = Path(os.path.abspath(Path(state_path).expanduser()))
    completed_identity: tuple[Path, str, Path] | None = None
    with _exclusive_lock(_lock_path(lexical)):
        path, state = _load_state_unlocked(lexical)
        _assert_active(Path(state["factory_root"]), state["batch_id"], path)
        if state["phase"] != "running":
            raise BatchError("当前批次已阻断或结束，不能记录项目结果")
        item = _target(state, reference)
        if item["status"] != "running":
            raise BatchError("该项目尚未开始处理")
        if outcome == "succeeded":
            result = _verified_success(Path(item["path"]))
        elif outcome == "deferred":
            result = {
                "version": None,
                "github_saved": False,
                "problem_summary": _problem_summary(problem_summary),
                "problem_signature": _stable_signature(problem_signature),
            }
        else:
            raise BatchError("项目结果只能是 succeeded 或 deferred")
        item["status"] = outcome
        item["result"] = result
        item["attempts"][-1]["finished_at"] = _now()
        repeated = _common_candidate(state)
        if repeated:
            signature, target_ids = repeated
            factory = state["factory_snapshot"]
            state["phase"] = "common_pending_bug"
            state["common_problem"] = {
                "signature": signature,
                "target_ids": target_ids,
                "confirmed_by": "repeated_targets",
                "detected_at": _now(),
                "bug_doc": None,
                "blocked_factory_head": factory["head"],
                "blocked_factory_fingerprint": factory["fingerprint"],
            }
        elif all(target["status"] == "succeeded" for target in state["targets"]):
            state["phase"] = "completed"
            completed_identity = (Path(state["factory_root"]), state["batch_id"], path)
        _write_state(path, state)
    if completed_identity is not None:
        _release_active(*completed_identity)


def _bug_doc_relative(factory_root: Path, value: str) -> str:
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.parent.as_posix() != "doc/2_bugs"
        or path.suffix.casefold() != ".md"
        or path.name in {"", ".", ".."}
    ):
        raise BatchError("共性问题必须关联 doc/2_bugs 下的一份 Markdown 文档")
    candidate = factory_root / Path(*path.parts)
    if not candidate.is_file() or _is_reparse(candidate):
        raise BatchError("关联的共性 Bug 文档不存在或路径不安全")
    return path.as_posix()


def link_common_problem(state_path: str | Path, bug_doc: str) -> None:
    lexical = Path(os.path.abspath(Path(state_path).expanduser()))
    with _exclusive_lock(_lock_path(lexical)):
        path, state = _load_state_unlocked(lexical)
        _assert_active(Path(state["factory_root"]), state["batch_id"], path)
        if state["phase"] != "common_pending_bug" or state["common_problem"] is None:
            raise BatchError("当前批次没有待关联文档的共性问题")
        state["common_problem"]["bug_doc"] = _bug_doc_relative(
            Path(state["factory_root"]), bug_doc
        )
        state["phase"] = "common_blocked"
        _write_state(path, state)


def confirm_common_problem(
    state_path: str | Path,
    signature: str,
    target_reference: str,
    bug_doc: str,
) -> None:
    lexical = Path(os.path.abspath(Path(state_path).expanduser()))
    with _exclusive_lock(_lock_path(lexical)):
        path, state = _load_state_unlocked(lexical)
        _assert_active(Path(state["factory_root"]), state["batch_id"], path)
        if state["phase"] != "running" or any(
            item["status"] == "running" for item in state["targets"]
        ):
            raise BatchError("必须先结束当前项目处理，再确认共性问题")
        item = _target(state, target_reference)
        factory = state["factory_snapshot"]
        state["phase"] = "common_blocked"
        state["common_problem"] = {
            "signature": _stable_signature(signature, bridgeforge_only=True),
            "target_ids": [item["id"]],
            "confirmed_by": "main_conversation_evidence",
            "detected_at": _now(),
            "bug_doc": _bug_doc_relative(Path(state["factory_root"]), bug_doc),
            "blocked_factory_head": factory["head"],
            "blocked_factory_fingerprint": factory["fingerprint"],
        }
        _write_state(path, state)


def refresh_plan(state_path: str | Path, target_reference: str) -> dict[str, Any]:
    lexical = Path(os.path.abspath(Path(state_path).expanduser()))
    with _exclusive_lock(_lock_path(lexical)):
        path, state = _load_state_unlocked(lexical)
        _assert_active(Path(state["factory_root"]), state["batch_id"], path)
        _assert_factory_locked(state)
        if any(item["status"] in {"pending", "running"} for item in state["targets"]):
            raise BatchError("必须先按顺序处理完首次计划，再重新确认异常项目")
        item = _target(state, target_reference)
        if item["status"] != "deferred":
            raise BatchError("只有尚未完成的项目可以重新确认")
        snapshot = _target_snapshot(Path(item["path"]))
        targets = [
            {**candidate, "snapshot": snapshot}
            if candidate["id"] == item["id"]
            else candidate
            for candidate in state["targets"]
        ]
        fingerprint = _canonical_hash(_plan_payload(state["factory_snapshot"], targets))
        return {
            "target": item["display_name"],
            "snapshot": snapshot,
            "plan_fingerprint": fingerprint,
        }


def reconfirm_target(
    state_path: str | Path,
    target_reference: str,
    plan_fingerprint: str,
) -> None:
    proposal = refresh_plan(state_path, target_reference)
    if proposal["plan_fingerprint"] != plan_fingerprint:
        raise BatchError("异常项目状态已再次变化，需要重新展示并确认")
    lexical = Path(os.path.abspath(Path(state_path).expanduser()))
    with _exclusive_lock(_lock_path(lexical)):
        path, state = _load_state_unlocked(lexical)
        _assert_active(Path(state["factory_root"]), state["batch_id"], path)
        _assert_factory_locked(state)
        item = _target(state, target_reference)
        if item["status"] != "deferred" or any(
            target["status"] in {"pending", "running"} for target in state["targets"]
        ):
            raise BatchError("异常项目已不满足重新确认条件")
        current = _target_snapshot(Path(item["path"]))
        targets = [
            {**candidate, "snapshot": current}
            if candidate["id"] == item["id"]
            else candidate
            for candidate in state["targets"]
        ]
        current_fingerprint = _canonical_hash(
            _plan_payload(state["factory_snapshot"], targets)
        )
        if current_fingerprint != plan_fingerprint:
            raise BatchError("异常项目状态已再次变化，需要重新展示并确认")
        item["snapshot"] = current
        state["plan_fingerprint"] = current_fingerprint
        _write_state(path, state)


def restart_batch(state_path: str | Path) -> None:
    lexical = Path(os.path.abspath(Path(state_path).expanduser()))
    with _exclusive_lock(_lock_path(lexical)):
        path, state = _load_state_unlocked(lexical)
        _assert_active(Path(state["factory_root"]), state["batch_id"], path)
        if state["phase"] != "common_blocked" or state["common_problem"] is None:
            raise BatchError("只有已关联 Bug 文档的共性问题才能全量重启")
        common = state["common_problem"]
        factory = inspect_factory(state["factory_root"])
        if (
            factory["head"] == common["blocked_factory_head"]
            or factory["fingerprint"] == common["blocked_factory_fingerprint"]
        ):
            raise BatchError("工厂源码和骨架均须修复并保存后才能重启")
        bug_doc = common["bug_doc"]
        exists = subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{bug_doc}"],
            cwd=state["factory_root"],
            capture_output=True,
            check=False,
        )
        if exists.returncode:
            raise BatchError("共性 Bug 文档尚未进入新的 GitHub 版本")
        refreshed = inspect_targets([item["path"] for item in state["targets"]])
        state["history"].append(
            {
                "generation": state["generation"],
                "factory_snapshot": state["factory_snapshot"],
                "common_problem": common,
                "closed_at": _now(),
            }
        )
        state["generation"] += 1
        state["factory_snapshot"] = factory
        state["phase"] = "running"
        state["common_problem"] = None
        for current, fresh in zip(state["targets"], refreshed):
            current["name"] = fresh["name"]
            current["display_name"] = fresh["display_name"]
            current["snapshot"] = fresh["snapshot"]
            current["status"] = "pending"
            current["result"] = None
        state["plan_fingerprint"] = _canonical_hash(
            _plan_payload(factory, state["targets"])
        )
        _write_state(path, state)


def close_batch(state_path: str | Path) -> None:
    lexical = Path(os.path.abspath(Path(state_path).expanduser()))
    with _exclusive_lock(_lock_path(lexical)):
        path, state = _load_state_unlocked(lexical)
        if state["phase"] != "completed":
            raise BatchError("只有已完成批次可以清理状态")
        _release_active(Path(state["factory_root"]), state["batch_id"], path)
        path.unlink()


def summary_text(state_path: str | Path) -> str:
    _, state = _load_state(state_path)
    lines = [f"本批次共 {len(state['targets'])} 个项目。"]
    for item in state["targets"]:
        result = item.get("result") or {}
        name = item["display_name"]
        if item["status"] == "succeeded":
            lines.append(f"- {name}：骨架 {result['version']}，已保存到 GitHub。")
        elif item["status"] == "deferred":
            lines.append(f"- {name}：尚未完成，现场已保留。{result['problem_summary']}")
        elif item["status"] == "running":
            lines.append(f"- {name}：正在处理。")
        else:
            lines.append(f"- {name}：尚未开始。")
    if state["phase"] in {"common_pending_bug", "common_blocked"}:
        lines.append("下一步：先修复并保存 bridgeforge-codex，再从头检查全部项目。")
    elif state["phase"] == "completed":
        lines.append("本批次已完成，无需继续处理。")
    elif any(item["status"] == "deferred" for item in state["targets"]):
        lines.append("下一步：继续处理尚未完成的项目。")
    else:
        lines.append("下一步：继续按顺序处理剩余项目。")
    return "\n".join(lines)


def _print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    factory = subparsers.add_parser("factory-check")
    factory.add_argument("--factory-root", type=Path, required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--factory-root", type=Path, required=True)
    plan.add_argument("--target", action="append", required=True)
    start = subparsers.add_parser("start")
    start.add_argument("--factory-root", type=Path, required=True)
    start.add_argument("--target", action="append", required=True)
    start.add_argument("--plan-fingerprint", required=True)
    start.add_argument("--batch-id")
    for name in ("begin", "refresh-plan", "reconfirm"):
        command = subparsers.add_parser(name)
        command.add_argument("--state", type=Path, required=True)
        command.add_argument("--target", required=True)
        if name == "reconfirm":
            command.add_argument("--plan-fingerprint", required=True)
    finish = subparsers.add_parser("finish")
    finish.add_argument("--state", type=Path, required=True)
    finish.add_argument("--target", required=True)
    finish.add_argument("--outcome", choices=("succeeded", "deferred"), required=True)
    finish.add_argument("--problem-summary")
    finish.add_argument("--problem-signature")
    common = subparsers.add_parser("confirm-common")
    common.add_argument("--state", type=Path, required=True)
    common.add_argument("--signature", required=True)
    common.add_argument("--target", required=True)
    common.add_argument("--bug-doc", required=True)
    link = subparsers.add_parser("link-common")
    link.add_argument("--state", type=Path, required=True)
    link.add_argument("--bug-doc", required=True)
    for name in ("restart", "close"):
        command = subparsers.add_parser(name)
        command.add_argument("--state", type=Path, required=True)
    summary = subparsers.add_parser("summary")
    summary.add_argument("--state", type=Path, required=True)
    summary.add_argument("--technical", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "factory-check":
            _print_json(inspect_factory(args.factory_root))
        elif args.command == "plan":
            _print_json(create_plan(args.factory_root, args.target))
        elif args.command == "start":
            print(
                start_batch(
                    args.factory_root,
                    args.target,
                    args.plan_fingerprint,
                    args.batch_id,
                )
            )
        elif args.command == "begin":
            begin_target(args.state, args.target)
            print("项目已进入处理阶段。")
        elif args.command == "finish":
            finish_target(
                args.state,
                args.target,
                outcome=args.outcome,
                problem_summary=args.problem_summary,
                problem_signature=args.problem_signature,
            )
            print(summary_text(args.state))
        elif args.command == "confirm-common":
            confirm_common_problem(
                args.state,
                args.signature,
                args.target,
                args.bug_doc,
            )
            print(summary_text(args.state))
        elif args.command == "link-common":
            link_common_problem(args.state, args.bug_doc)
            print(summary_text(args.state))
        elif args.command == "refresh-plan":
            _print_json(refresh_plan(args.state, args.target))
        elif args.command == "reconfirm":
            reconfirm_target(args.state, args.target, args.plan_fingerprint)
            print("异常项目的新现场已确认。")
        elif args.command == "restart":
            restart_batch(args.state)
            print("bridgeforge-codex 已恢复可分发状态，全部项目将从头重新检查。")
        elif args.command == "close":
            close_batch(args.state)
            print("本批次状态已清理。")
        elif args.command == "summary":
            if args.technical:
                _, state = _load_state(args.state)
                _print_json(state)
            else:
                print(summary_text(args.state))
    except BatchError as exc:
        print(f"批次控制未完成：{exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
