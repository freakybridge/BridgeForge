#!/usr/bin/env python3
"""Plan and apply one deterministic Codex skeleton transaction.

The asset contract is the ownership source of truth.  Unknown or edited
content is preserved as a gap; only proven managed state is replaced or
retired.  Apply always replans, compares the aggregate fingerprint, validates
the resulting skeleton, and writes the BridgeForge stamp last only when the
result is ready rather than degraded.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable


MIN_PYTHON = (3, 11)
HASH_RE = re.compile(r"sha256:[0-9a-f]{64}")
SEMVER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class SyncBlocked(RuntimeError):
    """The transaction cannot safely continue."""


@dataclass(frozen=True)
class Gap:
    asset_id: str
    target: str
    reason: str


@dataclass(frozen=True)
class Action:
    asset_id: str
    target: str
    action: str
    classification: str
    reason: str
    before_sha256: str | None
    after_sha256: str | None
    payload: bytes | None = field(default=None, repr=False, compare=False)


@dataclass
class Plan:
    project_root: str
    template_root: str
    mode: str
    current_version: str
    previous_version: str | None
    contract_sha256: str
    actions: list[Action]
    gaps: list[Gap]
    blockers: list[str]
    aggregate_fingerprint: str = ""

    @property
    def safe_actions(self) -> list[Action]:
        return [item for item in self.actions if item.classification == "safe"]

    @property
    def risk_actions(self) -> list[Action]:
        return [item for item in self.actions if item.classification == "risk"]


@dataclass(frozen=True)
class Receipt:
    status: str
    readiness: str
    execution_status: str
    target_readiness: str
    mode: str
    previous_version: str | None
    current_version: str
    aggregate_fingerprint: str
    safe_applied: tuple[str, ...]
    risk_applied: tuple[str, ...]
    risk_declined: tuple[str, ...]
    selected_action_ids: tuple[str, ...]
    selection_fingerprint: str | None
    required_actions: tuple[dict[str, Any], ...]
    optional_actions: tuple[dict[str, Any], ...]
    manual_steps: tuple[dict[str, Any], ...]
    blockers: tuple[dict[str, Any], ...]
    recommended_selection: tuple[str, ...]
    gaps: tuple[dict[str, str], ...]
    stamp_written_last: bool
    rollback_performed: bool
    timings_ms: dict[str, float]


MEMORY_ACTION_ID = "codex.memory-schema-organize"


def _git_blob_bytes(payload: bytes) -> bytes:
    if b"\0" in payload:
        return payload
    return payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(_git_blob_bytes(payload)).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _risk_catalog(plan: Plan) -> list[tuple[str, Action]]:
    ordered = sorted(
        plan.risk_actions,
        key=lambda item: (item.asset_id, item.target, item.action),
    )
    return [(f"R{index}", action) for index, action in enumerate(ordered, 1)]


def _action_item(item_id: str, action: Action) -> dict[str, Any]:
    target_state = "absent" if action.action == "retire" else action.after_sha256
    return {
        "id": item_id,
        "asset_id": action.asset_id,
        "title": f"{action.action}: {action.target}",
        "category": "required",
        "current_state": action.before_sha256 or "missing",
        "target_state": target_state,
        "affects_readiness": True,
        "action": action.action,
        "target": action.target,
        "impact": action.reason,
        "recoverability": "transaction rollback before completion",
        "executor": "bridgeforge",
        "recommended": True,
        "recommendation_reason": "required to reach the published managed state",
        "completion_criteria": (
            f"target is {target_state}"
            if target_state == "absent"
            else f"target sha256 equals {target_state}"
        ),
        "platform_permission": False,
    }


def _manual_items(gaps: list[Gap]) -> list[dict[str, Any]]:
    ordered = sorted(gaps, key=lambda item: (item.asset_id, item.target, item.reason))
    return [
        {
            "id": f"M{index}",
            "asset_id": gap.asset_id,
            "title": f"manual review: {gap.target}",
            "category": "manual",
            "current_state": "preserved gap",
            "target_state": "reviewed and resolved or explicitly preserved",
            "affects_readiness": True,
            "action": "manual-review",
            "target": gap.target,
            "impact": gap.reason,
            "recoverability": "original content is preserved",
            "executor": "user",
            "recommended": True,
            "recommendation_reason": "BridgeForge cannot safely decide this gap",
            "completion_criteria": "a later plan no longer reports this gap",
            "platform_permission": False,
        }
        for index, gap in enumerate(ordered, 1)
    ]


def _blocker_items(blockers: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "id": f"B{index}",
            "title": "update blocker",
            "category": "blocker",
            "affects_readiness": True,
            "executor": "user",
            "impact": reason,
            "completion_criteria": "planner no longer reports this blocker",
        }
        for index, reason in enumerate(blockers, 1)
    ]


def _target_readiness(
    *,
    required_actions: list[dict[str, Any]],
    optional_actions: list[dict[str, Any]],
    manual_steps: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
) -> str:
    if blockers:
        return "blocked"
    if required_actions or any(item.get("affects_readiness") for item in manual_steps):
        return "action_required"
    if optional_actions:
        return "ready_with_advisories"
    return "ready"


def _selection_fingerprint(plan: Plan, selected_ids: tuple[str, ...]) -> str:
    return _sha256_bytes(_canonical_json({
        "aggregate_fingerprint": plan.aggregate_fingerprint,
        "selected_action_ids": list(selected_ids),
    }))


def _select_risk_actions(
    plan: Plan,
    *,
    confirmed_risk: bool,
    decline_risk: bool,
    selected_risk_ids: tuple[str, ...] | None,
) -> tuple[list[tuple[str, Action]], list[tuple[str, Action]]]:
    decisions = sum((confirmed_risk, decline_risk, selected_risk_ids is not None))
    if decisions > 1:
        raise SyncBlocked("risk decision must be exactly one of all, selected, or declined")
    catalog = _risk_catalog(plan)
    if not catalog:
        if selected_risk_ids is not None:
            raise SyncBlocked("--selected-risk was supplied but the current plan has no risk actions")
        return [], []
    if decisions == 0:
        raise SyncBlocked(
            "risk actions require the single --confirmed-risk, --selected-risk, or --decline-risk decision"
        )
    if confirmed_risk:
        return catalog, []
    if decline_risk:
        return [], catalog
    assert selected_risk_ids is not None
    if not selected_risk_ids:
        raise SyncBlocked("partial confirmation requires at least one --selected-risk ID")
    if len(set(selected_risk_ids)) != len(selected_risk_ids):
        raise SyncBlocked("partial confirmation contains duplicate risk IDs")
    by_id = dict(catalog)
    unknown = sorted(set(selected_risk_ids) - set(by_id))
    if unknown:
        raise SyncBlocked("unknown selected risk IDs: " + ", ".join(unknown))
    chosen = set(selected_risk_ids)
    return (
        [(item_id, action) for item_id, action in catalog if item_id in chosen],
        [(item_id, action) for item_id, action in catalog if item_id not in chosen],
    )


def _semver(value: str, label: str) -> tuple[int, int, int]:
    match = SEMVER_RE.fullmatch(value.strip())
    if not match:
        raise SyncBlocked(f"{label} is not stable SemVer: {value!r}")
    return tuple(int(item) for item in match.groups())  # type: ignore[return-value]


def _inside(root: Path, relative: str, label: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or not relative or any(
        part in {"", ".", ".."} for part in candidate.parts
    ):
        raise SyncBlocked(f"{label} is not a safe relative path: {relative!r}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SyncBlocked(f"{label} escapes its root: {relative!r}") from exc
    return resolved


def _is_reparse(path: Path) -> bool:
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return True
    return path.is_symlink() or bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)


def _assert_plain_ancestors(root: Path, target: Path) -> None:
    current = root
    if _is_reparse(current):
        raise SyncBlocked(f"project root is a link or reparse point: {root}")
    relative = target.relative_to(root)
    for part in relative.parts[:-1]:
        current = current / part
        if current.exists() and _is_reparse(current):
            raise SyncBlocked(f"managed target has a link or reparse ancestor: {current}")


def _plain_root(path: Path, label: str) -> Path:
    lexical = Path(os.path.abspath(path))
    if not lexical.is_dir():
        raise SyncBlocked(f"{label} is missing: {lexical}")
    current = Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current = current / part
        if current.exists() and _is_reparse(current):
            raise SyncBlocked(f"{label} passes through a link or reparse point: {current}")
    return lexical.resolve()


def _history_hashes(asset: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    raw = asset.get("historical_sha256", {})
    if not isinstance(raw, dict):
        raise SyncBlocked(f"asset {asset.get('id')!r} historical_sha256 must be an object")
    for version, hashes in raw.items():
        _semver(str(version), "historical version")
        values = hashes if isinstance(hashes, list) else [hashes]
        for value in values:
            if not isinstance(value, str) or not HASH_RE.fullmatch(value):
                raise SyncBlocked(f"asset {asset.get('id')!r} has an invalid historical hash")
            result.add(value)
    return result


def _render_source(payload: bytes, asset: dict[str, Any], project_root: Path) -> bytes:
    if asset.get("render") != "project-name":
        return payload
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SyncBlocked(f"asset {asset['id']!r} render source is not UTF-8") from exc
    return text.replace("{{PROJECT_NAME}}", project_root.name).encode("utf-8")


def _target_hash(payload: bytes, asset: dict[str, Any], project_root: Path) -> str:
    if asset.get("render") != "project-name":
        return _sha256_bytes(payload)
    try:
        text = _git_blob_bytes(payload).decode("utf-8-sig")
    except UnicodeDecodeError:
        return _sha256_bytes(payload)
    normalized = text.replace(project_root.name, "{{PROJECT_NAME}}")
    return _sha256_bytes(normalized.encode("utf-8"))


def load_contract(template_root: Path) -> tuple[dict[str, Any], Path]:
    contract_path = template_root / "templates" / "codex" / "managed-skeleton.json"
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncBlocked(f"cannot read Codex asset contract: {exc}") from exc
    if not isinstance(contract, dict) or contract.get("schema_version") != 2:
        raise SyncBlocked("Codex asset contract must use schema_version 2")
    if contract.get("host") != "codex":
        raise SyncBlocked("Codex asset contract has the wrong host")
    _semver(str(contract.get("minimum_supported_version", "")), "minimum supported version")
    assets = contract.get("assets")
    if not isinstance(assets, list) or not assets:
        raise SyncBlocked("Codex asset contract has no assets")
    seen_ids: set[str] = set()
    seen_targets: set[str] = set()
    allowed_strategies = {"whole", "merge", "region", "retirement"}
    for asset in assets:
        if not isinstance(asset, dict):
            raise SyncBlocked("Codex asset contract contains a non-object asset")
        asset_id = asset.get("id")
        target = asset.get("target")
        strategy = asset.get("strategy")
        if not isinstance(asset_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", asset_id):
            raise SyncBlocked(f"invalid stable asset id: {asset_id!r}")
        if asset_id in seen_ids:
            raise SyncBlocked(f"duplicate asset id: {asset_id}")
        if not isinstance(target, str) or any(char in target for char in "*?["):
            raise SyncBlocked(f"asset {asset_id!r} must have one explicit target")
        _inside(Path("C:/bridgeforge-contract-root"), target, f"asset {asset_id} target")
        if target.casefold() in seen_targets:
            raise SyncBlocked(f"duplicate asset target: {target}")
        if strategy not in allowed_strategies:
            raise SyncBlocked(f"asset {asset_id!r} has an invalid strategy: {strategy!r}")
        if strategy == "retirement":
            if asset.get("source") is not None or asset.get("current_sha256") is not None:
                raise SyncBlocked(f"retired asset {asset_id!r} must not declare a current source/hash")
            if not _history_hashes(asset):
                raise SyncBlocked(f"retired asset {asset_id!r} needs historical hashes")
        else:
            source = asset.get("source")
            current_hash = asset.get("current_sha256")
            if not isinstance(source, str) or any(char in source for char in "*?["):
                raise SyncBlocked(f"asset {asset_id!r} must have one explicit source")
            if not isinstance(current_hash, str) or not HASH_RE.fullmatch(current_hash):
                raise SyncBlocked(f"asset {asset_id!r} has an invalid current hash")
            source_path = _inside(template_root, source, f"asset {asset_id} source")
            if not source_path.is_file() or _is_reparse(source_path):
                raise SyncBlocked(f"asset {asset_id!r} source is missing or unsafe: {source}")
            if _sha256_path(source_path) != current_hash:
                raise SyncBlocked(f"asset {asset_id!r} current hash is stale")
            _history_hashes(asset)
        seen_ids.add(asset_id)
        seen_targets.add(target.casefold())
    return contract, contract_path


def _action(
    asset: dict[str, Any],
    target: Path,
    kind: str,
    classification: str,
    reason: str,
    before: bytes | None,
    after: bytes | None,
    project_root: Path,
) -> Action:
    return Action(
        asset_id=str(asset["id"]),
        target=target.relative_to(project_root).as_posix(),
        action=kind,
        classification=classification,
        reason=reason,
        before_sha256=_target_hash(before, asset, project_root) if before is not None else None,
        after_sha256=_target_hash(after, asset, project_root) if after is not None else None,
        payload=after,
    )


def _plan_whole(
    asset: dict[str, Any],
    source: bytes,
    target: Path,
    project_root: Path,
) -> tuple[list[Action], list[Gap]]:
    desired = _render_source(source, asset, project_root)
    if not target.exists():
        return [_action(asset, target, "create", "safe", "target is missing", None, desired, project_root)], []
    if not target.is_file() or _is_reparse(target):
        return [], [Gap(asset["id"], asset["target"], "target is not a regular file")]
    before = target.read_bytes()
    actual_hash = _target_hash(before, asset, project_root)
    current_hash = str(asset["current_sha256"])
    if actual_hash == current_hash:
        return [], []
    if actual_hash in _history_hashes(asset):
        return [
            _action(
                asset,
                target,
                "replace",
                "safe",
                "target matches a published 0.86.0+ managed hash",
                before,
                desired,
                project_root,
            )
        ], []
    return [], [Gap(asset["id"], asset["target"], "whole-file target is modified or has no trusted historical hash")]


def _merge_generic(current: Any, canonical: Any, path: str, conflicts: list[str]) -> Any:
    if isinstance(current, dict) and isinstance(canonical, dict):
        merged = copy.deepcopy(current)
        for key, expected in canonical.items():
            child = f"{path}.{key}" if path else str(key)
            if key not in merged:
                merged[key] = copy.deepcopy(expected)
            else:
                merged[key] = _merge_generic(merged[key], expected, child, conflicts)
        return merged
    if isinstance(current, list) and isinstance(canonical, list):
        merged = copy.deepcopy(current)
        for value in canonical:
            if value not in merged:
                merged.append(copy.deepcopy(value))
        return merged
    if current != canonical:
        conflicts.append(path or "<root>")
    return current


def _dispatcher_stage(handler: Any) -> str | None:
    if not isinstance(handler, dict):
        return None
    command = str(handler.get("commandWindows") or handler.get("command") or "")
    normalized = command.replace("\\", "/").casefold()
    if ".codex/hooks/hook_dispatcher.py" not in normalized:
        return None
    match = re.search(
        r"hook_dispatcher\.py(?:['\"\)]|\s)+(pre-tool|post-read|post-edit|post-shell|post-compact|stop|user-prompt|session-start)",
        normalized,
    )
    return match.group(1) if match else "unknown"


def _merge_codex_hooks(current: Any, canonical: Any, conflicts: list[str]) -> Any:
    if not isinstance(current, dict) or not isinstance(canonical, dict):
        conflicts.append("<root>")
        return current
    merged = copy.deepcopy(current)
    if "description" not in merged:
        merged["description"] = canonical.get("description")
    target_hooks = merged.get("hooks")
    source_hooks = canonical.get("hooks")
    if not isinstance(target_hooks, dict) or not isinstance(source_hooks, dict):
        conflicts.append("hooks")
        return merged
    for event, canonical_groups in source_hooks.items():
        if event not in target_hooks:
            target_hooks[event] = copy.deepcopy(canonical_groups)
            continue
        target_groups = target_hooks[event]
        if not isinstance(target_groups, list) or not isinstance(canonical_groups, list):
            conflicts.append(f"hooks.{event}")
            continue
        for canonical_group in canonical_groups:
            if not isinstance(canonical_group, dict):
                conflicts.append(f"hooks.{event}")
                continue
            matcher = canonical_group.get("matcher")
            matching = [
                group
                for group in target_groups
                if isinstance(group, dict) and group.get("matcher") == matcher
            ]
            if not matching:
                target_groups.append(copy.deepcopy(canonical_group))
                continue
            group = matching[0]
            target_handlers = group.get("hooks")
            canonical_handlers = canonical_group.get("hooks")
            if not isinstance(target_handlers, list) or not isinstance(canonical_handlers, list):
                conflicts.append(f"hooks.{event}[matcher={matcher!r}]")
                continue
            for expected in canonical_handlers:
                stage = _dispatcher_stage(expected)
                candidates = [item for item in target_handlers if _dispatcher_stage(item) == stage]
                if not candidates:
                    target_handlers.append(copy.deepcopy(expected))
                elif len(candidates) == 1 and candidates[0] == expected:
                    continue
                else:
                    conflicts.append(f"hooks.{event}.dispatcher[{stage}]")
    return merged


def _plan_merge(
    asset: dict[str, Any],
    source: bytes,
    target: Path,
    project_root: Path,
) -> tuple[list[Action], list[Gap]]:
    whole_actions, whole_gaps = _plan_whole(asset, source, target, project_root)
    if whole_actions or not target.exists() or not whole_gaps:
        return whole_actions, whole_gaps
    if not target.is_file() or _is_reparse(target):
        return [], whole_gaps
    before = target.read_bytes()
    desired_source = _render_source(source, asset, project_root)
    try:
        current = json.loads(before.decode("utf-8-sig"))
        canonical = json.loads(desired_source.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return [], [Gap(asset["id"], asset["target"], "merge target is not valid UTF-8 JSON")]
    conflicts: list[str] = []
    if asset.get("merge_policy") == "codex-hooks":
        merged = _merge_codex_hooks(current, canonical, conflicts)
    else:
        merged = _merge_generic(current, canonical, "", conflicts)
    after = (json.dumps(merged, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    actions: list[Action] = []
    if _git_blob_bytes(after) != _git_blob_bytes(before):
        actions.append(
            _action(
                asset,
                target,
                "merge",
                "safe",
                "deterministic merge adds only missing managed values",
                before,
                after,
                project_root,
            )
        )
    gaps = [
        Gap(asset["id"], asset["target"], f"preserved conflicting JSON field: {item}")
        for item in sorted(set(conflicts))
    ]
    return actions, gaps


def _marker_slice(payload: bytes, begin: bytes, end: bytes) -> tuple[int, int]:
    if payload.count(begin) != 1 or payload.count(end) != 1:
        raise SyncBlocked("managed region markers are missing or duplicated")
    start = payload.index(begin)
    line_end = payload.find(b"\n", start)
    if line_end < 0:
        raise SyncBlocked("managed begin marker has no line ending")
    finish = payload.index(end, line_end)
    finish_end = payload.find(b"\n", finish)
    if finish_end < 0:
        finish_end = len(payload)
    else:
        finish_end += 1
    if finish <= start:
        raise SyncBlocked("managed region markers are out of order")
    return start, finish_end


def _plan_region(
    asset: dict[str, Any],
    source: bytes,
    target: Path,
    project_root: Path,
) -> tuple[list[Action], list[Gap]]:
    desired_source = _render_source(source, asset, project_root)
    region = asset.get("region")
    if not isinstance(region, dict):
        raise SyncBlocked(f"asset {asset['id']!r} region strategy has no marker contract")
    begin = str(region.get("begin", "")).encode("utf-8")
    end = str(region.get("end", "")).encode("utf-8")
    try:
        source_start, source_end = _marker_slice(desired_source, begin, end)
    except SyncBlocked as exc:
        raise SyncBlocked(f"asset {asset['id']!r} source region is invalid: {exc}") from exc
    if not target.exists():
        return [_action(asset, target, "create", "safe", "target is missing", None, desired_source, project_root)], []
    if not target.is_file() or _is_reparse(target):
        return [], [Gap(asset["id"], asset["target"], "region target is not a regular file")]
    before = target.read_bytes()
    try:
        target_start, target_end = _marker_slice(before, begin, end)
    except SyncBlocked as exc:
        return [], [Gap(asset["id"], asset["target"], f"region ownership is ambiguous: {exc}")]
    after = before[:target_start] + desired_source[source_start:source_end] + before[target_end:]
    if _git_blob_bytes(after) == _git_blob_bytes(before):
        return [], []
    return [
        _action(
            asset,
            target,
            "replace-region",
            "safe",
            "managed region is explicit; project extension is preserved byte-for-byte",
            before,
            after,
            project_root,
        )
    ], []


def _plan_retirement(
    asset: dict[str, Any],
    target: Path,
    project_root: Path,
) -> tuple[list[Action], list[Gap]]:
    if not target.exists():
        return [], []
    if not target.is_file() or _is_reparse(target):
        return [], [Gap(asset["id"], asset["target"], "retirement target is not a regular file")]
    before = target.read_bytes()
    actual_hash = _target_hash(before, asset, project_root)
    if actual_hash not in _history_hashes(asset):
        return [], [Gap(asset["id"], asset["target"], "retired asset was modified or is not a published managed copy")]
    return [
        _action(
            asset,
            target,
            "retire",
            "risk",
            "published no-op asset can be removed; deletion requires the single risk confirmation",
            before,
            None,
            project_root,
        )
    ], []


def _plan_contract_self(
    contract: dict[str, Any],
    contract_path: Path,
    project_root: Path,
) -> tuple[list[Action], list[Gap]]:
    pseudo = {
        "id": "contract.managed-skeleton",
        "target": str(contract["contract_target"]),
        "current_sha256": _sha256_path(contract_path),
        "historical_sha256": contract.get("contract_historical_sha256", {}),
    }
    target = _inside(project_root, str(contract["contract_target"]), "contract target")
    return _plan_whole(pseudo, contract_path.read_bytes(), target, project_root)


def _run_memory_lint(
    project_root: Path,
    template_root: Path,
    *,
    apply: bool = False,
) -> subprocess.CompletedProcess[str]:
    memory_root = project_root / ".codex" / "memory"
    if memory_root.exists() and _is_reparse(memory_root):
        raise SyncBlocked(f"project memory root is a link or reparse point: {memory_root}")
    lint = template_root / "templates" / "codex" / "hooks" / "memory_lint.py"
    if not lint.is_file() or _is_reparse(lint):
        raise SyncBlocked(f"canonical memory schema auditor is missing or unsafe: {lint}")
    command = [
        sys.executable,
        str(lint),
        "--organize",
        "--project-root",
        str(project_root),
        "--host",
        "codex",
    ]
    if apply:
        command.extend(("--apply", "--confirmed"))
    try:
        return subprocess.run(
            command,
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SyncBlocked(f"memory schema audit could not complete: {exc}") from exc


def _plan_memory_schema(
    project_root: Path,
    template_root: Path,
) -> tuple[list[Action], list[Gap]]:
    result = _run_memory_lint(project_root, template_root)
    output = (result.stdout + result.stderr).strip()
    if result.returncode == 0:
        return [], []
    if result.returncode != 1:
        raise SyncBlocked(
            f"memory schema audit failed with exit {result.returncode}: {output}"
        )
    if "[invalid]" in result.stdout:
        return [], [
            Gap(
                MEMORY_ACTION_ID,
                ".codex/memory",
                "memory ownership or canonical destination is ambiguous; original files preserved",
            )
        ]
    if not any(marker in result.stdout for marker in ("[explicit]", "[high-confidence]")):
        raise SyncBlocked(f"memory schema audit returned an unclassified plan: {output}")
    fingerprint = _memory_plan_fingerprint(result.stdout)
    return [
        Action(
            asset_id=MEMORY_ACTION_ID,
            target=".codex/memory",
            action="memory-organize",
            classification="risk",
            reason="canonical memory auditor produced explicit or high-confidence moves; filesystem moves require the single risk confirmation",
            before_sha256=fingerprint,
            after_sha256=None,
        )
    ], []


def _memory_plan_fingerprint(output: str) -> str:
    planned = [
        line.strip()
        for line in output.splitlines()
        if line.startswith(("[explicit]", "[high-confidence]", "[invalid]"))
    ]
    return _sha256_bytes("\n".join(planned).encode("utf-8"))


def _fingerprint(plan: Plan) -> str:
    payload = {
        "project_root": plan.project_root,
        "template_root": plan.template_root,
        "mode": plan.mode,
        "current_version": plan.current_version,
        "previous_version": plan.previous_version,
        "contract_sha256": plan.contract_sha256,
        "actions": [
            {key: value for key, value in asdict(item).items() if key != "payload"}
            for item in plan.actions
        ],
        "gaps": [asdict(item) for item in plan.gaps],
        "blockers": plan.blockers,
    }
    return _sha256_bytes(_canonical_json(payload))


def _detect_mode(project_root: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    if (project_root / ".codex" / ".bridgeforge_version").is_file():
        return "update"
    if (project_root / ".codex").is_dir() or (project_root / "AGENTS.md").is_file():
        return "adopt"
    return "init"


def build_plan(project_root: Path, template_root: Path, mode: str = "auto") -> Plan:
    root = _plain_root(project_root, "project root")
    template = _plain_root(template_root, "template root")
    contract, contract_path = load_contract(template)
    selected_mode = _detect_mode(root, mode)
    current_version = (template / "VERSION").read_text(encoding="utf-8-sig").strip()
    current_semver = _semver(current_version, "BridgeForge VERSION")
    minimum = _semver(str(contract["minimum_supported_version"]), "minimum supported version")
    stamp = _inside(root, str(contract["stamp"]), "version stamp")
    previous_version = stamp.read_text(encoding="utf-8-sig").strip() if stamp.is_file() else None
    blockers: list[str] = []
    if selected_mode == "update" and previous_version is None:
        blockers.append("update mode requires an existing .codex/.bridgeforge_version")
    if previous_version is not None:
        try:
            previous_semver = _semver(previous_version, "project BridgeForge version")
            if previous_semver < minimum:
                blockers.append(
                    f"project version {previous_version} predates the automatic migration baseline "
                    f"{contract['minimum_supported_version']}"
                )
            if previous_semver > current_semver:
                blockers.append(
                    f"project version {previous_version} is newer than this BridgeForge {current_version}"
                )
        except SyncBlocked as exc:
            blockers.append(str(exc))

    actions: list[Action] = []
    gaps: list[Gap] = []
    self_actions, self_gaps = _plan_contract_self(contract, contract_path, root)
    actions.extend(self_actions)
    gaps.extend(self_gaps)
    for asset in contract["assets"]:
        target = _inside(root, asset["target"], f"asset {asset['id']} target")
        _assert_plain_ancestors(root, target)
        strategy = asset["strategy"]
        if strategy == "retirement":
            asset_actions, asset_gaps = _plan_retirement(asset, target, root)
        else:
            source_path = _inside(template, asset["source"], f"asset {asset['id']} source")
            source = source_path.read_bytes()
            if strategy == "whole":
                asset_actions, asset_gaps = _plan_whole(asset, source, target, root)
            elif strategy == "merge":
                asset_actions, asset_gaps = _plan_merge(asset, source, target, root)
            else:
                asset_actions, asset_gaps = _plan_region(asset, source, target, root)
        actions.extend(asset_actions)
        gaps.extend(asset_gaps)
    memory_actions, memory_gaps = _plan_memory_schema(root, template)
    actions.extend(memory_actions)
    gaps.extend(memory_gaps)
    plan = Plan(
        project_root=str(root),
        template_root=str(template),
        mode=selected_mode,
        current_version=current_version,
        previous_version=previous_version,
        contract_sha256=_sha256_path(contract_path),
        actions=actions,
        gaps=gaps,
        blockers=blockers,
    )
    plan.aggregate_fingerprint = _fingerprint(plan)
    return plan


class _Transaction:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.before: dict[Path, bytes | None] = {}
        self.created_directories: list[Path] = []
        self.tree_before: dict[Path, tuple[dict[Path, bytes], set[Path]]] = {}

    def _record(self, path: Path) -> None:
        if path not in self.before:
            self.before[path] = path.read_bytes() if path.exists() else None

    def write(self, path: Path, payload: bytes) -> None:
        self._record(path)
        missing: list[Path] = []
        current = path.parent
        while current != self.root and not current.exists():
            missing.append(current)
            current = current.parent
        for directory in reversed(missing):
            directory.mkdir()
            self.created_directories.append(directory)
        _atomic_write(path, payload, self.root)

    def delete(self, path: Path) -> None:
        self._record(path)
        path.unlink()

    def snapshot_tree(self, tree: Path) -> None:
        if tree in self.tree_before:
            return
        files: dict[Path, bytes] = {}
        directories: set[Path] = set()
        if tree.exists():
            if not tree.is_dir() or _is_reparse(tree):
                raise SyncBlocked(f"transaction tree is not a plain directory: {tree}")
            for current, dirnames, filenames in os.walk(tree, followlinks=False):
                current_path = Path(current)
                if _is_reparse(current_path):
                    raise SyncBlocked(f"transaction tree contains a reparse directory: {current_path}")
                directories.add(current_path.relative_to(tree))
                for name in tuple(dirnames):
                    candidate = current_path / name
                    if _is_reparse(candidate):
                        raise SyncBlocked(f"transaction tree contains a reparse directory: {candidate}")
                for name in filenames:
                    candidate = current_path / name
                    if not candidate.is_file() or _is_reparse(candidate):
                        raise SyncBlocked(f"transaction tree contains a non-plain file: {candidate}")
                    files[candidate.relative_to(tree)] = candidate.read_bytes()
        self.tree_before[tree] = (files, directories)

    def _rollback_tree(
        self,
        tree: Path,
        files: dict[Path, bytes],
        directories: set[Path],
    ) -> None:
        if tree.exists() and (not tree.is_dir() or _is_reparse(tree)):
            raise OSError(f"rollback tree became unsafe: {tree}")
        if tree.exists():
            for current, dirnames, filenames in os.walk(tree, topdown=False, followlinks=False):
                current_path = Path(current)
                if _is_reparse(current_path):
                    raise OSError(f"rollback tree contains a reparse directory: {current_path}")
                for name in filenames:
                    candidate = current_path / name
                    relative = candidate.relative_to(tree)
                    if relative not in files:
                        if _is_reparse(candidate):
                            raise OSError(f"rollback tree contains a reparse file: {candidate}")
                        candidate.unlink(missing_ok=True)
                for name in dirnames:
                    candidate = current_path / name
                    relative = candidate.relative_to(tree)
                    if relative not in directories:
                        candidate.rmdir()
        for relative in sorted(directories, key=lambda item: len(item.parts)):
            (tree / relative).mkdir(exist_ok=True)
        for relative, payload in files.items():
            _atomic_write(tree / relative, payload, self.root)

    def rollback(self) -> None:
        failures: list[str] = []
        for path, payload in reversed(tuple(self.before.items())):
            try:
                if payload is None:
                    path.unlink(missing_ok=True)
                else:
                    _atomic_write(path, payload, self.root)
            except OSError as exc:
                failures.append(f"{path}: {exc}")
        for tree, (files, directories) in reversed(tuple(self.tree_before.items())):
            try:
                self._rollback_tree(tree, files, directories)
            except OSError as exc:
                failures.append(f"{tree}: {exc}")
        for directory in reversed(self.created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        if failures:
            raise SyncBlocked("rollback incomplete: " + "; ".join(failures))


def _atomic_write(path: Path, payload: bytes, staging_root: Path) -> None:
    descriptor, raw = tempfile.mkstemp(prefix=".bridgeforge-sync-", dir=staging_root)
    temporary = Path(raw)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _run_validation(
    project_root: Path,
    template_root: Path,
    *,
    allow_memory_gap: bool,
) -> dict[str, float]:
    memory_lint = template_root / "templates" / "codex" / "hooks" / "memory_lint.py"
    health = template_root / "templates" / "codex" / "hooks" / "config_health_check.py"
    validators = (
        (
            memory_lint,
            [
                sys.executable,
                str(memory_lint),
                "--organize",
                "--project-root",
                str(project_root),
                "--host",
                "codex",
            ],
            "memory schema audit",
        ),
        (
            health,
            [sys.executable, str(health), "--strict"],
            "config health check",
        ),
    )
    for path, _command, label in validators:
        if not path.is_file():
            raise SyncBlocked(f"{label} executable is missing after apply: {path}")

    def run_validator(
        command: list[str],
        label: str,
    ) -> tuple[str, subprocess.CompletedProcess[str], float]:
        started = time.perf_counter()
        try:
            result = subprocess.run(
                command,
                cwd=project_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SyncBlocked(f"{label} could not complete: {exc}") from exc
        return label, result, (time.perf_counter() - started) * 1000

    with ThreadPoolExecutor(max_workers=len(validators)) as executor:
        futures = [
            executor.submit(run_validator, command, label)
            for _path, command, label in validators
        ]
        results = [future.result() for future in futures]

    timings: dict[str, float] = {}
    for label, result, elapsed_ms in results:
        key = "memory_validation" if label == "memory schema audit" else "config_validation"
        timings[key] = round(elapsed_ms, 1)
        expected_memory_gap = (
            label == "memory schema audit"
            and allow_memory_gap
            and result.returncode == 1
        )
        if result.returncode != 0 and not expected_memory_gap:
            detail = (result.stdout + result.stderr).strip()
            raise SyncBlocked(f"{label} failed with exit {result.returncode}: {detail}")
    return timings


def _verify_actions(project_root: Path, actions: Iterable[Action]) -> None:
    for action in actions:
        if action.action == "memory-organize":
            continue
        target = _inside(project_root, action.target, f"receipt target {action.asset_id}")
        if action.action == "retire":
            if target.exists():
                raise SyncBlocked(f"retired asset still exists: {action.target}")
            continue
        if not target.is_file() or _sha256_path(target) != action.after_sha256:
            # Rendered assets use a normalized plan hash; exact payload is the
            # authoritative postcondition for every write.
            if action.payload is None or not target.is_file() or target.read_bytes() != action.payload:
                raise SyncBlocked(f"managed asset verification failed: {action.target}")


def apply_plan(
    planned: Plan,
    *,
    plan_fingerprint: str,
    confirmed_risk: bool = False,
    decline_risk: bool = False,
    selected_risk_ids: tuple[str, ...] | None = None,
    checkpoint: Callable[[str], None] | None = None,
) -> Receipt:
    apply_started = time.perf_counter()
    replan_started = time.perf_counter()
    rebuilt = build_plan(Path(planned.project_root), Path(planned.template_root), planned.mode)
    replan_ms = (time.perf_counter() - replan_started) * 1000
    return _apply_rebuilt_plan(
        planned,
        rebuilt,
        plan_fingerprint=plan_fingerprint,
        confirmed_risk=confirmed_risk,
        decline_risk=decline_risk,
        selected_risk_ids=selected_risk_ids,
        checkpoint=checkpoint,
        replan_ms=replan_ms,
        apply_started=apply_started,
    )


def _apply_rebuilt_plan(
    planned: Plan,
    rebuilt: Plan,
    *,
    plan_fingerprint: str,
    confirmed_risk: bool = False,
    decline_risk: bool = False,
    selected_risk_ids: tuple[str, ...] | None = None,
    checkpoint: Callable[[str], None] | None = None,
    replan_ms: float,
    apply_started: float,
) -> Receipt:
    timings: dict[str, float] = {}
    if planned.blockers:
        raise SyncBlocked("plan contains blockers")
    if planned.aggregate_fingerprint != plan_fingerprint:
        raise SyncBlocked("supplied aggregate fingerprint does not match the displayed plan")
    timings["replan"] = round(replan_ms, 1)
    if rebuilt.aggregate_fingerprint != plan_fingerprint:
        raise SyncBlocked("aggregate fingerprint drifted; zero writes performed")
    selected_risks, declined_risks = _select_risk_actions(
        rebuilt,
        confirmed_risk=confirmed_risk,
        decline_risk=decline_risk,
        selected_risk_ids=selected_risk_ids,
    )
    selected = list(rebuilt.safe_actions)
    selected.extend(action for _item_id, action in selected_risks)
    selected_action_ids = tuple(item_id for item_id, _action in selected_risks)
    risk_declined = tuple(action.asset_id for _item_id, action in declined_risks)

    root = Path(rebuilt.project_root)
    contract, _contract_path = load_contract(Path(rebuilt.template_root))
    stamp = _inside(root, str(contract["stamp"]), "version stamp")
    transaction = _Transaction(root)
    stamp_written = False
    try:
        action_started = time.perf_counter()
        if checkpoint:
            checkpoint("before-apply")
        memory_actions = [item for item in selected if item.action == "memory-organize"]
        if memory_actions:
            transaction.snapshot_tree(root / ".codex" / "memory")
        for action in selected:
            if action.action == "memory-organize":
                continue
            target = _inside(root, action.target, f"asset {action.asset_id} target")
            _assert_plain_ancestors(root, target)
            if action.action == "retire":
                transaction.delete(target)
            else:
                if action.payload is None:
                    raise SyncBlocked(f"action {action.asset_id} has no payload")
                transaction.write(target, action.payload)
            if checkpoint:
                checkpoint(f"after-action:{action.asset_id}")
        timings["asset_apply"] = round(
            (time.perf_counter() - action_started) * 1000,
            1,
        )
        memory_started = time.perf_counter()
        for action in memory_actions:
            dry_run = _run_memory_lint(root, Path(rebuilt.template_root))
            if (
                dry_run.returncode != 1
                or _memory_plan_fingerprint(dry_run.stdout) != action.before_sha256
            ):
                raise SyncBlocked("memory schema plan drifted after asset apply")
            applied = _run_memory_lint(root, Path(rebuilt.template_root), apply=True)
            if applied.returncode != 0:
                detail = (applied.stdout + applied.stderr).strip()
                raise SyncBlocked(f"memory schema apply failed with exit {applied.returncode}: {detail}")
            if checkpoint:
                checkpoint(f"after-action:{action.asset_id}")
        timings["memory_apply"] = round(
            (time.perf_counter() - memory_started) * 1000,
            1,
        )
        _verify_actions(root, selected)
        if checkpoint:
            checkpoint("before-validate")
        validation_started = time.perf_counter()
        timings.update(_run_validation(
            root,
            Path(rebuilt.template_root),
            allow_memory_gap=(
                any(item.asset_id == MEMORY_ACTION_ID for item in rebuilt.gaps)
                or MEMORY_ACTION_ID in risk_declined
            ),
        ))
        timings["validation_wall"] = round(
            (time.perf_counter() - validation_started) * 1000,
            1,
        )
        if checkpoint:
            checkpoint("before-stamp")
        if not rebuilt.gaps and not risk_declined:
            transaction.write(stamp, (rebuilt.current_version + "\n").encode("utf-8"))
            stamp_written = True
            if checkpoint:
                checkpoint("after-stamp")
    except Exception as exc:
        try:
            transaction.rollback()
        except SyncBlocked as rollback_exc:
            raise SyncBlocked(f"transaction failed ({exc}); {rollback_exc}") from exc
        raise SyncBlocked(f"transaction failed and was rolled back: {exc}") from exc

    receipt_gaps = [asdict(item) for item in rebuilt.gaps]
    receipt_gaps.extend(
        {
            "asset_id": item.asset_id,
            "target": item.target,
            "reason": "risk action declined; original content preserved",
        }
        for item in rebuilt.risk_actions
        if item.asset_id in risk_declined
    )
    remaining_required = [
        _action_item(item_id, action)
        for item_id, action in declined_risks
    ]
    manual_steps = _manual_items(rebuilt.gaps)
    blockers: list[dict[str, Any]] = []
    optional_actions: list[dict[str, Any]] = []
    target_readiness = _target_readiness(
        required_actions=remaining_required,
        optional_actions=optional_actions,
        manual_steps=manual_steps,
        blockers=blockers,
    )
    catalog = _risk_catalog(rebuilt)
    degraded = bool(receipt_gaps)
    timings["total"] = round((time.perf_counter() - apply_started) * 1000, 1)
    return Receipt(
        status="completed_with_gaps" if degraded else "completed",
        readiness="degraded" if degraded else "ready",
        execution_status="completed",
        target_readiness=target_readiness,
        mode=rebuilt.mode,
        previous_version=rebuilt.previous_version,
        current_version=rebuilt.current_version,
        aggregate_fingerprint=rebuilt.aggregate_fingerprint,
        safe_applied=tuple(item.asset_id for item in rebuilt.safe_actions),
        risk_applied=tuple(action.asset_id for _item_id, action in selected_risks),
        risk_declined=risk_declined,
        selected_action_ids=selected_action_ids,
        selection_fingerprint=(
            _selection_fingerprint(rebuilt, selected_action_ids) if catalog else None
        ),
        required_actions=tuple(remaining_required),
        optional_actions=tuple(optional_actions),
        manual_steps=tuple(manual_steps),
        blockers=tuple(blockers),
        recommended_selection=tuple(item_id for item_id, _action in catalog),
        gaps=tuple(receipt_gaps),
        stamp_written_last=stamp_written,
        rollback_performed=False,
        timings_ms=timings,
    )


def _plan_payload(
    plan: Plan,
    *,
    timings_ms: dict[str, float] | None = None,
) -> dict[str, Any]:
    catalog = _risk_catalog(plan)
    required_actions = [_action_item(item_id, action) for item_id, action in catalog]
    optional_actions: list[dict[str, Any]] = []
    manual_steps = _manual_items(plan.gaps)
    blockers = _blocker_items(plan.blockers)
    payload = {
        "status": "blocked" if plan.blockers else ("completed_with_gaps" if plan.gaps else "planned"),
        "readiness": "blocked" if plan.blockers else ("degraded" if plan.gaps else "ready"),
        "execution_status": "failed" if plan.blockers else "planned",
        "target_readiness": _target_readiness(
            required_actions=required_actions,
            optional_actions=optional_actions,
            manual_steps=manual_steps,
            blockers=blockers,
        ),
        "mode": plan.mode,
        "previous_version": plan.previous_version,
        "current_version": plan.current_version,
        "safe": [
            {key: value for key, value in asdict(item).items() if key != "payload"}
            for item in plan.safe_actions
        ],
        "risk": [
            {key: value for key, value in asdict(item).items() if key != "payload"}
            for item in plan.risk_actions
        ],
        "gaps": [asdict(item) for item in plan.gaps],
        "blockers": plan.blockers,
        "required_actions": required_actions,
        "optional_actions": optional_actions,
        "manual_steps": manual_steps,
        "blocker_items": blockers,
        "recommended_selection": [item_id for item_id, _action in catalog],
        "confirmation": (
            {
                "business_confirmation_count": "one",
                "all": [item_id for item_id, _action in catalog],
                "partial_syntax": "B: R1,R3",
                "decline": "C",
                "aggregate_fingerprint": plan.aggregate_fingerprint,
            }
            if catalog
            else {
                "business_confirmation_count": "zero",
                "all": [],
            }
        ),
        "aggregate_fingerprint": plan.aggregate_fingerprint,
    }
    if timings_ms is not None:
        payload["timings_ms"] = timings_ms
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--template-root", required=True, type=Path)
    parser.add_argument("--mode", choices=("auto", "init", "adopt", "update"), default="auto")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--plan-fingerprint")
    risk = parser.add_mutually_exclusive_group()
    risk.add_argument("--confirmed-risk", action="store_true")
    risk.add_argument(
        "--selected-risk",
        action="append",
        dest="selected_risk_ids",
        metavar="ID",
        help="repeat a displayed Rn ID for the single partial-confirmation decision",
    )
    risk.add_argument("--decline-risk", action="store_true")
    args = parser.parse_args(argv)

    if sys.version_info < MIN_PYTHON:
        print("BLOCKED: bridgeforge_project_sync requires Python 3.11+", file=sys.stderr)
        return 2
    try:
        plan_started = time.perf_counter()
        plan = build_plan(args.project_root, args.template_root, args.mode)
        plan_ms = round((time.perf_counter() - plan_started) * 1000, 1)
        if not args.apply:
            print(
                json.dumps(
                    _plan_payload(plan, timings_ms={"plan": plan_ms}),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 2 if plan.blockers else 0
        if not args.plan_fingerprint:
            raise SyncBlocked("--apply requires --plan-fingerprint from the immediately preceding plan")
        receipt = _apply_rebuilt_plan(
            plan,
            plan,
            plan_fingerprint=args.plan_fingerprint,
            confirmed_risk=args.confirmed_risk,
            decline_risk=args.decline_risk,
            selected_risk_ids=(
                tuple(args.selected_risk_ids)
                if args.selected_risk_ids is not None
                else None
            ),
            replan_ms=plan_ms,
            apply_started=plan_started,
        )
        print(json.dumps(asdict(receipt), ensure_ascii=False, indent=2))
        return 0
    except (OSError, SyncBlocked, KeyError, TypeError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "readiness": "blocked",
                    "execution_status": "failed",
                    "target_readiness": "blocked",
                    "error": str(exc),
                    "rollback_performed": "rolled back" in str(exc),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
