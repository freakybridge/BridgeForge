#!/usr/bin/env python3
"""Plan and apply one deterministic Codex skeleton transaction.

The asset contract is the ownership source of truth.  Unknown or edited
content is preserved as a gap; only proven managed state is replaced or
retired.  Apply always replans, compares the aggregate fingerprint, validates
the resulting skeleton, and writes the bridgeforge-codex stamp last only when the
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
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable


MIN_PYTHON = (3, 11)
HASH_RE = re.compile(r"sha256:[0-9a-f]{64}")
SEMVER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
PROJECT_NAME_CLONE_NORMALIZER = "project-name-clone-command"
PROJECT_NAME_CLONE_RE = re.compile(
    br"(?m)^(git clone <repo_url> )"
    br"([A-Za-z0-9._-]+|\{\{PROJECT_NAME\}\})"
    br"( && cd )\2([ \t]*)$"
)
PROJECT_TITLE_RE = re.compile(
    r"(?m)^# ([A-Za-z0-9._-]+|\{\{PROJECT_NAME\}\}) 项目开发规范[ \t]*$".encode(
        "utf-8"
    )
)
PROJECT_TITLE_NORMALIZED = "# {{PROJECT_NAME}} 项目开发规范".encode("utf-8")


class SyncBlocked(RuntimeError):
    """The transaction cannot safely continue."""


@dataclass(frozen=True)
class Gap:
    asset_id: str
    target: str
    reason: str
    review_items: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class Action:
    asset_id: str
    target: str
    action: str
    classification: str
    reason: str
    before_sha256: str | None
    after_sha256: str | None
    managed_blocks: tuple[str, ...] = ()
    managed_item_details: tuple[tuple[str, str, str, str], ...] = ()
    keyed_table_contracts: tuple[tuple[str, tuple[str, ...]], ...] = ()
    local_impact: str | None = None
    payload: bytes | None = field(default=None, repr=False, compare=False)
    source_payload: bytes | None = field(default=None, repr=False, compare=False)


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
    project_requirements: list[dict[str, Any]]
    aggregate_fingerprint: str = ""

    @property
    def safe_actions(self) -> list[Action]:
        return [item for item in self.actions if item.classification == "safe"]

    @property
    def risk_actions(self) -> list[Action]:
        return [item for item in self.actions if item.classification == "risk"]

    @property
    def absorption_actions(self) -> list[Action]:
        return [item for item in self.actions if item.classification == "absorb"]


@dataclass(frozen=True)
class Receipt:
    status: str
    readiness: str
    execution_status: str
    target_readiness: str
    project_readiness: str
    mode: str
    previous_version: str | None
    current_version: str
    aggregate_fingerprint: str
    safe_applied: tuple[str, ...]
    risk_applied: tuple[str, ...]
    risk_declined: tuple[str, ...]
    upstream_absorption_applied: tuple[str, ...]
    upstream_absorption_declined: tuple[str, ...]
    selected_absorption_ids: tuple[str, ...]
    selected_action_ids: tuple[str, ...]
    selection_fingerprint: str | None
    custom_absorption_directives: tuple[str, ...]
    conflict_file_items: tuple[dict[str, Any], ...]
    managed_block_effects: tuple[dict[str, Any], ...]
    required_actions: tuple[dict[str, Any], ...]
    optional_actions: tuple[dict[str, Any], ...]
    manual_steps: tuple[dict[str, Any], ...]
    action_required_items: tuple[dict[str, Any], ...]
    blockers: tuple[dict[str, Any], ...]
    recommended_selection: tuple[str, ...]
    gaps: tuple[dict[str, Any], ...]
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


CatalogEntry = tuple[str, Action, str | None]


def _managed_item_detail(
    action: Action,
    selection_label: str | None,
) -> tuple[str, str | None, str | None]:
    if selection_label is None:
        return "replace_block", None, None
    detail = next(
        (
            item
            for item in action.managed_item_details
            if item[0] == selection_label
        ),
        None,
    )
    if detail is None:
        return "replace_block", selection_label, None
    return detail[1], detail[2], detail[3]


def _risk_catalog(plan: Plan) -> list[CatalogEntry]:
    ordered = sorted(
        plan.risk_actions,
        key=lambda item: (item.asset_id, item.target, item.action),
    )
    return [
        (f"R{index}", action, None)
        for index, action in enumerate(ordered, 1)
    ]


def _absorption_catalog(plan: Plan) -> list[CatalogEntry]:
    ordered = sorted(
        (
            (action, block)
            for action in plan.absorption_actions
            for block in action.managed_blocks
        ),
        key=lambda item: (item[0].asset_id, item[0].target, item[1]),
    )
    return [
        (f"U{index}", action, block)
        for index, (action, block) in enumerate(ordered, 1)
    ]


def _executable_catalog(plan: Plan) -> list[CatalogEntry]:
    return _risk_catalog(plan) + _absorption_catalog(plan)


def _action_item(
    item_id: str,
    action: Action,
    managed_block: str | None = None,
) -> dict[str, Any]:
    merge_mode, managed_heading, managed_key = _managed_item_detail(
        action,
        managed_block,
    )
    target_state = (
        (
            f"upstream managed table row: {managed_heading} :: {managed_key}"
            if managed_key is not None
            else f"upstream managed block: {managed_heading}"
        )
        if managed_block is not None
        else ("absent" if action.action == "retire" else action.after_sha256)
    )
    return {
        "id": item_id,
        "asset_id": action.asset_id,
        "title": (
            f"{action.action}: {action.target} :: {managed_block}"
            if managed_block is not None
            else f"{action.action}: {action.target}"
        ),
        "category": (
            "upstream_absorption"
            if action.classification == "absorb"
            else "required"
        ),
        "current_state": action.before_sha256 or "missing",
        "target_state": target_state,
        "affects_readiness": True,
        "action": action.action,
        "target": action.target,
        "impact": action.reason,
        "managed_blocks": (
            [managed_heading]
            if managed_block is not None
            else list(action.managed_blocks)
        ),
        "merge_mode": merge_mode if managed_block is not None else None,
        "managed_key": managed_key,
        "local_impact": action.local_impact,
        "recoverability": "transaction rollback before completion",
        "executor": "bridgeforge-codex",
        "recommended": True,
        "recommendation_reason": (
            (
                "aggressive mode resolves this same-key conflict in favor of upstream"
                if merge_mode == "keyed_table"
                else "aggressive mode absorbs the current upstream managed blocks"
            )
            if action.classification == "absorb"
            else "required to reach the published managed state"
        ),
        "completion_criteria": (
            (
                f"managed table row matches current upstream: {managed_key}"
                if managed_key is not None
                else f"managed block matches current upstream: {managed_heading}"
            )
            if managed_block is not None
            else (
                f"target is {target_state}"
                if target_state == "absent"
                else f"target sha256 equals {target_state}"
            )
        ),
        "platform_permission": False,
    }


def _managed_block_effect(
    item_id: str,
    action: Action,
    selection_label: str | None,
    *,
    selected: bool,
    custom_decision: str | None,
) -> dict[str, Any]:
    merge_mode, managed_heading, managed_key = _managed_item_detail(
        action,
        selection_label,
    )
    return {
        "id": item_id,
        "asset_id": action.asset_id,
        "target": action.target,
        "managed_block": managed_heading,
        "merge_mode": merge_mode,
        "managed_key": managed_key,
        "decision": custom_decision or ("absorb" if selected else "preserve"),
        "effect": "absorbed_upstream" if selected else "preserved_local",
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
            "recommendation_reason": "bridgeforge-codex cannot safely decide this gap",
            "completion_criteria": "a later plan no longer reports this gap",
            "platform_permission": False,
        }
        for index, gap in enumerate(ordered, 1)
    ]


def _action_required_items(gaps: list[Gap]) -> list[dict[str, Any]]:
    ordered = sorted(
        (
            (gap.asset_id, gap.target, item)
            for gap in gaps
            for item in gap.review_items
        ),
        key=lambda entry: (
            entry[0],
            entry[1],
            entry[2].get("source_location", ""),
            entry[2].get("content_sha256", ""),
        ),
    )
    return [
        {
            "id": f"G{index}",
            "asset_id": asset_id,
            "target": target,
            "category": "agents_ownership_review",
            "affects_readiness": True,
            "current_state": "original AGENTS content preserved",
            "target_state": item["recommended_owner"],
            "action": "review-agents-ownership",
            "source_location": item["source_location"],
            "content_summary": item["content_summary"],
            "content_sha256": item["content_sha256"],
            "classification_reason": item["classification_reason"],
            "recommended_owner": item["recommended_owner"],
            "recommended_action": item["recommended_action"],
            "recoverability": "original AGENTS.md remains byte-for-byte unchanged",
            "executor": "user",
            "recommended": True,
            "completion_criteria": (
                "the reviewed content has an explicit public/project decision and "
                "a later plan no longer reports this item"
            ),
            "platform_permission": False,
        }
        for index, (asset_id, target, item) in enumerate(ordered, 1)
    ]


RETIRED_RULE_MIGRATION_TARGETS = {
    ".codex/rules/architecture.md": "AGENTS.md project zone: 项目架构红线 / 项目目录地图",
    ".codex/rules/modules.md": "AGENTS.md project zone: 项目架构红线 / 项目目录地图",
    ".codex/rules/anti_fabrication.md": "AGENTS.md §1.3",
    ".codex/rules/debugging.md": "AGENTS.md §5 and $escalate/$debate",
    ".codex/rules/workflow.md": "AGENTS.md §2.3 and workflow skills",
    ".codex/rules/portability.md": "AGENTS.md §1.3 and project operating guide",
    ".codex/rules/anti_drift_hooks.md": "AGENTS.md §4.4-§4.5",
    ".codex/rules/meta_rule_design.md": "AGENTS.md §2.1",
}


def _retirement_gap_reason(asset: dict[str, Any]) -> str:
    target = str(asset["target"])
    migration = RETIRED_RULE_MIGRATION_TARGETS.get(target)
    base = "retired asset was modified or is not a published managed copy"
    if migration is None:
        return base
    return f"{base}; preserve verbatim and migrate manually to {migration}"


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


def _selection_fingerprint(
    plan: Plan,
    selected_ids: tuple[str, ...],
    custom_directives: tuple[str, ...] = (),
) -> str:
    return _sha256_bytes(_canonical_json({
        "aggregate_fingerprint": plan.aggregate_fingerprint,
        "selected_action_ids": list(selected_ids),
        "custom_absorption_directives": list(custom_directives),
    }))


def _select_risk_actions(
    plan: Plan,
    *,
    confirmed_risk: bool,
    decline_risk: bool,
    selected_risk_ids: tuple[str, ...] | None,
) -> tuple[list[CatalogEntry], list[CatalogEntry]]:
    decisions = sum((confirmed_risk, decline_risk, selected_risk_ids is not None))
    if decisions > 1:
        raise SyncBlocked("risk decision must be exactly one of all, selected, or declined")
    catalog = _executable_catalog(plan)
    if not catalog:
        if selected_risk_ids is not None:
            raise SyncBlocked("--selected-risk was supplied but the current plan has no executable actions")
        return [], []
    if decisions == 0:
        raise SyncBlocked(
            "executable actions require the single --confirmed-risk, --selected-risk, or --decline-risk decision"
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
    by_id = {item_id: (action, block) for item_id, action, block in catalog}
    unknown = sorted(set(selected_risk_ids) - set(by_id))
    if unknown:
        raise SyncBlocked("unknown selected risk IDs: " + ", ".join(unknown))
    chosen = set(selected_risk_ids)
    return (
        [entry for entry in catalog if entry[0] in chosen],
        [entry for entry in catalog if entry[0] not in chosen],
    )


_PRESERVE_DIRECTIVE_RE = re.compile(
    r"(?:禁止|不要|不再|不|拒绝|跳过)\s*(?:继续\s*)?(?:吸收|采用|覆盖)"
    r"|保留(?:本地|当前|现有)?|保持(?:本地|当前|现有)?"
    r"|\b(?:preserve|keep|skip)\b"
    r"|\b(?:do\s+not|don't)\s+(?:absorb|apply|use)\b",
    re.IGNORECASE,
)
_ABSORB_DIRECTIVE_RE = re.compile(
    r"吸收|采用上游|使用上游|以上游为准|覆盖本地"
    r"|\babsorb\b|\bapply\s+upstream\b|\buse\s+upstream\b",
    re.IGNORECASE,
)
_ABSORPTION_ID_RE = re.compile(r"(?<![A-Z0-9])U[1-9][0-9]*(?![0-9])", re.IGNORECASE)


def _apply_custom_absorption_directives(
    selected: list[CatalogEntry],
    declined: list[CatalogEntry],
    directives: tuple[str, ...],
) -> tuple[list[CatalogEntry], list[CatalogEntry], dict[str, str]]:
    if not directives:
        return selected, declined, {}
    selected_uids = {
        item_id
        for item_id, action, _block in selected
        if action.classification == "absorb"
    }
    if not selected_uids:
        raise SyncBlocked(
            "custom absorption directives require at least one selected U ID"
        )
    decisions: dict[str, str] = {}
    for directive in directives:
        referenced = tuple(dict.fromkeys(
            item.upper() for item in _ABSORPTION_ID_RE.findall(directive)
        ))
        if len(referenced) != 1:
            raise SyncBlocked(
                "custom absorption directive must name exactly one selected U ID: "
                + directive
            )
        item_id = referenced[0]
        if item_id not in selected_uids:
            raise SyncBlocked(
                "custom absorption directive does not name a selected U ID: "
                + directive
            )
        if item_id in decisions:
            raise SyncBlocked(
                "custom absorption directives contain duplicate U ID: " + item_id
            )
        preserve = bool(_PRESERVE_DIRECTIVE_RE.search(directive))
        positive_text = _PRESERVE_DIRECTIVE_RE.sub("", directive)
        absorb = bool(_ABSORB_DIRECTIVE_RE.search(positive_text))
        if preserve == absorb:
            raise SyncBlocked(
                "custom absorption directive is ambiguous or unsupported; "
                "state exactly absorb upstream or preserve local for "
                + item_id
            )
        decisions[item_id] = "preserve" if preserve else "absorb"

    preserved_ids = {
        item_id for item_id, decision in decisions.items() if decision == "preserve"
    }
    if preserved_ids:
        moved = [entry for entry in selected if entry[0] in preserved_ids]
        selected = [entry for entry in selected if entry[0] not in preserved_ids]
        declined = declined + moved
        declined.sort(key=lambda entry: (entry[0][0], int(entry[0][1:])))
    return selected, declined, decisions


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


def _declared_hashes(raw: Any, label: str) -> set[str]:
    if not isinstance(raw, dict):
        raise SyncBlocked(f"{label} must be an object")
    result: set[str] = set()
    for version, hashes in raw.items():
        _semver(str(version), f"{label} version")
        values = hashes if isinstance(hashes, list) else [hashes]
        for value in values:
            if not isinstance(value, str) or not HASH_RE.fullmatch(value):
                raise SyncBlocked(f"{label} contains an invalid hash")
            result.add(value)
    return result


def _agents_zone_parts(
    payload: bytes,
    zones: dict[str, Any],
) -> tuple[bytes, bytes, bytes, bytes, bytes]:
    public = zones["public"]
    project = zones["project"]
    markers = tuple(
        str(value).encode("utf-8")
        for value in (
            public["begin"], public["end"], project["begin"], project["end"]
        )
    )
    public_begin, public_end, project_begin, project_end = markers
    if any(payload.count(marker) != 1 for marker in markers):
        raise SyncBlocked("AGENTS zone markers are missing or duplicated")
    positions = tuple(payload.index(marker) for marker in markers)
    if positions != tuple(sorted(positions)):
        raise SyncBlocked("AGENTS zone markers are reversed or nested")

    def marker_end(start: int, marker: bytes) -> int:
        line_end = payload.find(b"\n", start + len(marker))
        return len(payload) if line_end < 0 else line_end + 1

    public_finish = marker_end(positions[1], public_end)
    project_finish = marker_end(positions[3], project_end)
    prefix = payload[:positions[0]]
    public_block = payload[positions[0]:public_finish]
    between = payload[public_finish:positions[2]]
    project_block = payload[positions[2]:project_finish]
    suffix = payload[project_finish:]
    if prefix.strip() or between.strip() or suffix.strip():
        raise SyncBlocked("AGENTS content exists outside the declared public/project zones")
    return prefix, public_block, between, project_block, suffix


def _agents_zone_hash(
    payload: bytes,
    asset: dict[str, Any],
    project_root: Path,
) -> str:
    return _target_hash(_git_blob_bytes(payload), asset, project_root)


def _agents_public_zone_hash(
    payload: bytes,
    asset: dict[str, Any],
    project_root: Path,
) -> str:
    normalized = PROJECT_NAME_CLONE_RE.sub(
        br"\1{{PROJECT_NAME}}\3{{PROJECT_NAME}}\4",
        _git_blob_bytes(payload),
    )
    return _sha256_bytes(normalized)


def _layout_sections(layout: dict[str, Any]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for group in layout.get("groups", []):
        children = group.get("sections")
        if isinstance(children, list):
            sections.extend(children)
        else:
            sections.append(group)
    return sections


def _layout_residual_segments(
    payload: bytes,
    layout: dict[str, Any],
) -> tuple[bytes, list[tuple[int, int]]]:
    normalized = _git_blob_bytes(payload)
    candidates: list[str] = []
    for entry in _layout_sections(layout):
        candidates.append(str(entry["heading"]))
        candidates.extend(str(item) for item in entry.get("legacy_headings", []))
    for entry in layout.get("retired_sections", []):
        candidates.extend(str(item) for item in entry.get("legacy_headings", []))
    unique_candidates = tuple(dict.fromkeys(candidates))
    sections = _markdown_heading_sections(normalized, unique_candidates)
    spans = list(sections.values())
    visible = _markdown_visible_headings(normalized)
    for group in layout["groups"]:
        if not isinstance(group.get("sections"), list):
            continue
        heading = str(group["heading"]).encode("utf-8")
        matches = [start for _index, start, _level, raw in visible if raw == heading]
        if len(matches) > 1:
            raise SyncBlocked(
                f"managed Markdown group heading is duplicated: {group['heading']}"
            )
        if matches:
            start = matches[0]
            finish = normalized.find(b"\n", start)
            spans.append((start, len(normalized) if finish < 0 else finish + 1))
    merged: list[tuple[int, int]] = []
    for start, finish in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], finish))
        else:
            merged.append((start, finish))
    residual_spans: list[tuple[int, int]] = []
    cursor = 0
    for start, finish in merged:
        if cursor < start:
            residual_spans.append((cursor, start))
        cursor = finish
    if cursor < len(normalized):
        residual_spans.append((cursor, len(normalized)))
    return normalized, residual_spans


def _layout_residual_bytes(payload: bytes, layout: dict[str, Any]) -> bytes:
    normalized, residual_spans = _layout_residual_segments(payload, layout)
    return b"".join(normalized[start:finish] for start, finish in residual_spans)


def _layout_residual_hash(payload: bytes, layout: dict[str, Any]) -> str:
    residual = PROJECT_TITLE_RE.sub(
        PROJECT_TITLE_NORMALIZED,
        _layout_residual_bytes(payload, layout),
    )
    return _sha256_bytes(residual)


def _trusted_layout_hashes(entry: dict[str, Any], heading: str) -> set[str]:
    result: set[str] = set()
    history = entry.get("trusted_legacy_sha256", {})
    if not isinstance(history, dict):
        return result
    by_heading = history.get(heading, {})
    if not isinstance(by_heading, dict):
        return result
    for values in by_heading.values():
        candidates = values if isinstance(values, list) else [values]
        result.update(
            value
            for value in candidates
            if isinstance(value, str) and HASH_RE.fullmatch(value)
        )
    return result


def _normalize_layout_rendered_tokens(
    payload: bytes,
    entry: dict[str, Any],
) -> bytes:
    normalizer = entry.get("hash_normalizer")
    if normalizer is None:
        return payload
    if normalizer != PROJECT_NAME_CLONE_NORMALIZER:
        raise SyncBlocked(f"unsupported section layout hash normalizer: {normalizer!r}")
    return PROJECT_NAME_CLONE_RE.sub(
        br"\1{{PROJECT_NAME}}\3{{PROJECT_NAME}}\4",
        _git_blob_bytes(payload),
    )


def _preserve_layout_rendered_tokens(
    source_block: bytes,
    target_block: bytes,
    entry: dict[str, Any],
) -> bytes:
    if entry.get("hash_normalizer") != PROJECT_NAME_CLONE_NORMALIZER:
        return source_block
    matches = list(PROJECT_NAME_CLONE_RE.finditer(_git_blob_bytes(target_block)))
    if len(matches) != 1:
        return source_block
    project_name = matches[0].group(2)
    normalized_source = _normalize_layout_rendered_tokens(source_block, entry)
    return PROJECT_NAME_CLONE_RE.sub(
        lambda match: (
            match.group(1)
            + project_name
            + match.group(3)
            + project_name
            + match.group(4)
        ),
        normalized_source,
    )


def _layout_block_hash(
    payload: bytes,
    entry: dict[str, Any],
    asset: dict[str, Any],
    project_root: Path,
) -> str:
    normalized = _normalize_layout_rendered_tokens(
        _normalized_managed_block(payload),
        entry,
    )
    return _target_hash(normalized, asset, project_root)


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
    contract_path = template_root / "templates" / "managed-skeleton.json"
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncBlocked(f"cannot read Codex asset contract: {exc}") from exc
    if not isinstance(contract, dict) or contract.get("schema_version") != 2:
        raise SyncBlocked("Codex asset contract must use schema_version 2")
    if contract.get("host") != "codex":
        raise SyncBlocked("Codex asset contract has the wrong host")
    if contract.get("release_version") is not None:
        _semver(str(contract["release_version"]), "contract release version")
    _semver(str(contract.get("minimum_supported_version", "")), "minimum supported version")
    assets = contract.get("assets")
    if not isinstance(assets, list) or not assets:
        raise SyncBlocked("Codex asset contract has no assets")
    seen_ids: set[str] = set()
    seen_targets: set[str] = set()
    allowed_strategies = {"whole", "merge", "region", "seed", "retirement"}
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
        _inside(Path("C:/bridgeforge-codex-contract-root"), target, f"asset {asset_id} target")
        if target.casefold() in seen_targets:
            raise SyncBlocked(f"duplicate asset target: {target}")
        if strategy not in allowed_strategies:
            raise SyncBlocked(f"asset {asset_id!r} has an invalid strategy: {strategy!r}")
        managed_blocks = asset.get("managed_blocks")
        if managed_blocks is not None:
            if strategy != "whole" or not isinstance(managed_blocks, dict):
                raise SyncBlocked(
                    f"asset {asset_id!r} managed_blocks requires whole strategy"
                )
            if managed_blocks.get("format") != "markdown-headings":
                raise SyncBlocked(
                    f"asset {asset_id!r} managed_blocks has an invalid format"
                )
            headings = managed_blocks.get("headings")
            additive_headings = managed_blocks.get("additive_headings", [])
            if (
                not isinstance(headings, list)
                or any(
                    not isinstance(heading, str)
                    or not re.fullmatch(r"#{1,6} [^\r\n]+", heading)
                    for heading in headings
                )
                or len(set(headings)) != len(headings)
            ):
                raise SyncBlocked(
                    f"asset {asset_id!r} managed_blocks headings are invalid"
                )
            if (
                not isinstance(additive_headings, list)
                or any(
                    not isinstance(heading, str)
                    or not re.fullmatch(r"#{1,6} [^\r\n]+", heading)
                    for heading in additive_headings
                )
                or len(set(additive_headings)) != len(additive_headings)
            ):
                raise SyncBlocked(
                    f"asset {asset_id!r} additive managed headings are invalid"
                )
            keyed_tables = managed_blocks.get("keyed_tables", [])
            if not isinstance(keyed_tables, list):
                raise SyncBlocked(
                    f"asset {asset_id!r} managed_blocks keyed_tables are invalid"
                )
            keyed_headings: list[str] = []
            for table in keyed_tables:
                if not isinstance(table, dict):
                    raise SyncBlocked(
                        f"asset {asset_id!r} keyed table contract is invalid"
                    )
                heading = table.get("heading")
                key_column = table.get("key_column")
                managed_keys = table.get("managed_keys")
                if (
                    not isinstance(heading, str)
                    or not re.fullmatch(r"#{1,6} [^\r\n]+", heading)
                    or key_column != 0
                    or not isinstance(managed_keys, list)
                    or not managed_keys
                    or any(not isinstance(key, str) or not key.strip() for key in managed_keys)
                    or len({_markdown_table_key(key) for key in managed_keys})
                    != len(managed_keys)
                ):
                    raise SyncBlocked(
                        f"asset {asset_id!r} keyed table contract is invalid: {heading!r}"
                    )
                keyed_headings.append(heading)
            if (
                not headings and not additive_headings and not keyed_tables
                or len(set(keyed_headings)) != len(keyed_headings)
                or set(headings).intersection(keyed_headings)
                or set(additive_headings).intersection(keyed_headings)
                or set(headings).intersection(additive_headings)
            ):
                raise SyncBlocked(
                    f"asset {asset_id!r} managed block ownership overlaps or is empty"
                )
        section_layout = asset.get("section_layout")
        agents_zones = asset.get("agents_zones")
        if agents_zones is not None:
            if (
                strategy != "whole"
                or not isinstance(agents_zones, dict)
                or agents_zones.get("format") != "bridgeforge-agents-zones"
            ):
                raise SyncBlocked(
                    f"asset {asset_id!r} agents_zones requires whole strategy"
                )
            public_zone = agents_zones.get("public")
            project_zone = agents_zones.get("project")
            if not isinstance(public_zone, dict) or not isinstance(project_zone, dict):
                raise SyncBlocked(f"asset {asset_id!r} agents_zones is invalid")
            marker_values = [
                public_zone.get("begin"), public_zone.get("end"),
                project_zone.get("begin"), project_zone.get("end"),
            ]
            required_headings = project_zone.get("required_headings")
            required_content = project_zone.get("required_content_headings", [])
            migrations = project_zone.get("legacy_section_migrations", [])
            if (
                any(not isinstance(value, str) or "\n" in value for value in marker_values)
                or len(set(marker_values)) != 4
                or not isinstance(public_zone.get("current_sha256"), str)
                or not HASH_RE.fullmatch(str(public_zone.get("current_sha256")))
                or not isinstance(required_headings, list)
                or not required_headings
                or any(
                    not isinstance(heading, str)
                    or not re.fullmatch(r"#{1,6} [^\r\n]+", heading)
                    for heading in required_headings
                )
                or len(set(required_headings)) != len(required_headings)
                or not isinstance(required_content, list)
                or any(item not in required_headings for item in required_content)
                or len(set(required_content)) != len(required_content)
                or not isinstance(migrations, list)
            ):
                raise SyncBlocked(f"asset {asset_id!r} agents_zones is invalid")
            _declared_hashes(
                public_zone.get("historical_sha256", {}),
                f"asset {asset_id!r} public zone history",
            )
            migration_sources: set[str] = set()
            migration_targets: set[str] = set()
            for migration in migrations:
                if not isinstance(migration, dict):
                    raise SyncBlocked(f"asset {asset_id!r} zone migration is invalid")
                legacy_heading = migration.get("legacy_heading")
                project_heading = migration.get("project_heading")
                if (
                    not isinstance(legacy_heading, str)
                    or not isinstance(project_heading, str)
                    or project_heading not in required_headings
                    or legacy_heading in migration_sources
                    or project_heading in migration_targets
                ):
                    raise SyncBlocked(f"asset {asset_id!r} zone migration is invalid")
                migration_sources.add(legacy_heading)
                migration_targets.add(project_heading)
        if section_layout is not None:
            if (
                strategy != "whole"
                or not isinstance(section_layout, dict)
                or section_layout.get("format") != "markdown-section-layout"
            ):
                raise SyncBlocked(
                    f"asset {asset_id!r} section_layout requires whole strategy"
                )
            groups = section_layout.get("groups")
            retired_sections = section_layout.get("retired_sections", [])
            if (
                not isinstance(groups, list)
                or not groups
                or not isinstance(retired_sections, list)
            ):
                raise SyncBlocked(f"asset {asset_id!r} section_layout is invalid")
            canonical_headings: list[str] = []
            legacy_headings: list[str] = []
            keyed_layout_headings: list[str] = []
            for group in groups:
                if not isinstance(group, dict):
                    raise SyncBlocked(f"asset {asset_id!r} section layout group is invalid")
                group_heading = group.get("heading")
                if (
                    not isinstance(group_heading, str)
                    or not re.fullmatch(r"#{1,6} [^\r\n]+", group_heading)
                ):
                    raise SyncBlocked(f"asset {asset_id!r} section layout heading is invalid")
                canonical_headings.append(group_heading)
                children = group.get("sections")
                entries = children if isinstance(children, list) else [group]
                if isinstance(children, list) and not children:
                    raise SyncBlocked(f"asset {asset_id!r} section layout group is empty")
                for entry in entries:
                    if not isinstance(entry, dict):
                        raise SyncBlocked(f"asset {asset_id!r} section layout entry is invalid")
                    heading = entry.get("heading")
                    aliases = entry.get("legacy_headings", [])
                    ownership = entry.get("ownership")
                    hash_normalizer = entry.get("hash_normalizer")
                    if (
                        not isinstance(heading, str)
                        or not re.fullmatch(r"#{1,6} [^\r\n]+", heading)
                        or not isinstance(aliases, list)
                        or any(
                            not isinstance(alias, str)
                            or not re.fullmatch(r"#{1,6} [^\r\n]+", alias)
                            for alias in aliases
                        )
                        or len(set(aliases)) != len(aliases)
                        or ownership not in {"managed", "project", "keyed"}
                        or (entry.get("required", False) and ownership != "project")
                        or hash_normalizer not in {None, PROJECT_NAME_CLONE_NORMALIZER}
                        or (hash_normalizer is not None and ownership != "managed")
                    ):
                        raise SyncBlocked(f"asset {asset_id!r} section layout entry is invalid")
                    if entry is not group:
                        canonical_headings.append(heading)
                    legacy_headings.extend(str(alias) for alias in aliases)
                    if ownership == "keyed":
                        keyed_layout_headings.append(heading)
                    if ownership == "managed":
                        for alias in aliases:
                            if not _trusted_layout_hashes(entry, str(alias)):
                                raise SyncBlocked(
                                    f"asset {asset_id!r} managed layout alias has no trusted history: {alias}"
                                )
            for retired in retired_sections:
                if not isinstance(retired, dict):
                    raise SyncBlocked(f"asset {asset_id!r} retired section is invalid")
                aliases = retired.get("legacy_headings")
                if (
                    not isinstance(aliases, list)
                    or not aliases
                    or any(
                        not isinstance(alias, str)
                        or not re.fullmatch(r"#{1,6} [^\r\n]+", alias)
                        or not _trusted_layout_hashes(retired, alias)
                        for alias in aliases
                    )
                ):
                    raise SyncBlocked(f"asset {asset_id!r} retired section history is invalid")
                legacy_headings.extend(str(alias) for alias in aliases)
            if (
                len(set(canonical_headings)) != len(canonical_headings)
                or len(set(legacy_headings)) != len(legacy_headings)
                or set(canonical_headings).intersection(legacy_headings)
            ):
                raise SyncBlocked(f"asset {asset_id!r} section layout headings overlap")
            keyed_contract_headings = [
                str(item["heading"])
                for item in (managed_blocks or {}).get("keyed_tables", [])
            ]
            if keyed_layout_headings != keyed_contract_headings:
                raise SyncBlocked(
                    f"asset {asset_id!r} keyed layout headings do not match managed tables"
                )
            if agents_zones is not None and not _declared_hashes(
                section_layout.get("trusted_residual_sha256", {}),
                f"asset {asset_id!r} layout residual history",
            ):
                raise SyncBlocked(
                    f"asset {asset_id!r} layout residual history is empty"
                )
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
            if managed_blocks is not None:
                headings = tuple(str(item) for item in managed_blocks.get("headings", []))
                additive_headings = tuple(
                    str(item) for item in managed_blocks.get("additive_headings", [])
                )
                keyed_tables = tuple(managed_blocks.get("keyed_tables", []))
                registered = headings + additive_headings + tuple(
                    str(item["heading"])
                    for item in keyed_tables
                )
                source_payload = source_path.read_bytes()
                sections = _markdown_heading_sections(source_payload, registered)
                missing = [heading for heading in registered if heading not in sections]
                if missing:
                    raise SyncBlocked(
                        f"asset {asset_id!r} source is missing managed headings: "
                        + ", ".join(missing)
                    )
                for table in keyed_tables:
                    parsed = _parse_keyed_table(source_payload, str(table["heading"]))
                    parsed_keys = tuple(key for key, _row, _cells in parsed.rows)
                    contract_keys = tuple(
                        _markdown_table_key(str(key))
                        for key in table["managed_keys"]
                    )
                    if parsed_keys != contract_keys:
                        raise SyncBlocked(
                            f"asset {asset_id!r} keyed table source keys do not match contract: "
                            + str(table["heading"])
                        )
            if section_layout is not None:
                source_payload = source_path.read_bytes()
                zone_migrations = {
                    str(item["legacy_heading"]): str(item["project_heading"])
                    for item in (
                        agents_zones.get("project", {}).get(
                            "legacy_section_migrations", []
                        )
                        if isinstance(agents_zones, dict)
                        else []
                    )
                }
                expected_headings: list[str] = []
                for group in section_layout["groups"]:
                    if isinstance(group.get("sections"), list):
                        expected_headings.extend(
                            zone_migrations.get(
                                str(item["heading"]), str(item["heading"])
                            )
                            for item in group["sections"]
                        )
                    else:
                        expected_headings.append(
                            zone_migrations.get(
                                str(group["heading"]), str(group["heading"])
                            )
                        )
                source_sections = _markdown_heading_sections(
                    source_payload,
                    tuple(expected_headings),
                )
                missing_layout = [
                    heading for heading in expected_headings if heading not in source_sections
                ]
                if missing_layout:
                    raise SyncBlocked(
                        f"asset {asset_id!r} source is missing layout headings: "
                        + ", ".join(missing_layout)
                    )
            if agents_zones is not None:
                source_payload = _render_source(
                    source_path.read_bytes(), asset, Path("C:/bridgeforge-codex-contract-root")
                )
                try:
                    _prefix, public_block, _between, project_block, _suffix = (
                        _agents_zone_parts(source_payload, agents_zones)
                    )
                    project_sections = _markdown_heading_sections(
                        project_block,
                        tuple(str(item) for item in agents_zones["project"]["required_headings"]),
                    )
                except SyncBlocked as exc:
                    raise SyncBlocked(
                        f"asset {asset_id!r} source AGENTS zones are invalid: {exc}"
                    ) from exc
                expected_public = str(agents_zones["public"]["current_sha256"])
                if _agents_public_zone_hash(
                    public_block,
                    asset,
                    Path("C:/bridgeforge-codex-contract-root"),
                ) != expected_public:
                    raise SyncBlocked(f"asset {asset_id!r} public zone hash is stale")
                if len(project_sections) != len(agents_zones["project"]["required_headings"]):
                    raise SyncBlocked(
                        f"asset {asset_id!r} project zone headings are incomplete"
                    )
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
    *,
    managed_blocks: tuple[str, ...] = (),
    managed_item_details: tuple[tuple[str, str, str, str], ...] = (),
    keyed_table_contracts: tuple[tuple[str, tuple[str, ...]], ...] = (),
    local_impact: str | None = None,
    source_payload: bytes | None = None,
) -> Action:
    return Action(
        asset_id=str(asset["id"]),
        target=target.relative_to(project_root).as_posix(),
        action=kind,
        classification=classification,
        reason=reason,
        before_sha256=_target_hash(before, asset, project_root) if before is not None else None,
        after_sha256=_target_hash(after, asset, project_root) if after is not None else None,
        managed_blocks=managed_blocks,
        managed_item_details=managed_item_details,
        keyed_table_contracts=keyed_table_contracts,
        local_impact=local_impact,
        payload=after,
        source_payload=source_payload,
    )


def _markdown_visible_headings(
    payload: bytes,
) -> list[tuple[int, int, int, bytes]]:
    try:
        payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SyncBlocked("managed Markdown target is not valid UTF-8") from exc
    lines = payload.splitlines(keepends=True)
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)
    heading_re = re.compile(br"^ {0,3}(#{1,6}) [^\r\n]+$")
    fence_open_re = re.compile(br"^ {0,3}(`{3,}|~{3,})[^\r\n]*$")
    visible_headings: list[tuple[int, int, int, bytes]] = []
    fence_char: bytes | None = None
    fence_length = 0
    for index, line in enumerate(lines):
        stripped = line.rstrip(b"\r\n")
        if fence_char is not None:
            close = re.fullmatch(
                br" {0,3}"
                + re.escape(fence_char)
                + br"{"
                + str(fence_length).encode("ascii")
                + br",}[ \t]*",
                stripped,
            )
            if close:
                fence_char = None
                fence_length = 0
            continue
        fence = fence_open_re.fullmatch(stripped)
        if fence:
            marker = fence.group(1)
            fence_char = marker[:1]
            fence_length = len(marker)
            continue
        match = heading_re.fullmatch(stripped)
        if match:
            visible_headings.append(
                (index, offsets[index], len(match.group(1)), stripped.lstrip(b" "))
            )
    if fence_char is not None:
        raise SyncBlocked("managed Markdown contains an unclosed fenced code block")
    return visible_headings


def _content_review_item(
    payload: bytes,
    start: int,
    finish: int,
    *,
    reason: str,
    recommended_owner: str = "project zone after user review",
    recommended_action: str = "review, classify, then rerun bridgeforge-codex",
) -> dict[str, str]:
    bounded_start = max(0, min(start, len(payload)))
    bounded_finish = max(bounded_start, min(finish, len(payload)))
    block = payload[bounded_start:bounded_finish]
    start_line = payload[:bounded_start].count(b"\n") + 1
    end_line = start_line + max(0, block.count(b"\n"))
    text = block.decode("utf-8", errors="replace")
    summary = re.sub(r"\s+", " ", text).strip()
    if len(summary) > 180:
        summary = summary[:177] + "..."
    return {
        "source_location": f"AGENTS.md lines {start_line}-{end_line}",
        "content_summary": summary or "<blank or formatting-only content>",
        "content_sha256": _sha256_bytes(block),
        "classification_reason": reason,
        "recommended_owner": recommended_owner,
        "recommended_action": recommended_action,
    }


def _unclosed_fence_review_item(payload: bytes) -> dict[str, str] | None:
    lines = payload.splitlines(keepends=True)
    fence_open_re = re.compile(br"^ {0,3}(`{3,}|~{3,})[^\r\n]*$")
    fence_char: bytes | None = None
    fence_length = 0
    fence_start = 0
    cursor = 0
    for line in lines:
        stripped = line.rstrip(b"\r\n")
        if fence_char is not None:
            close = re.fullmatch(
                br" {0,3}"
                + re.escape(fence_char)
                + br"{"
                + str(fence_length).encode("ascii")
                + br",}[ \t]*",
                stripped,
            )
            if close:
                fence_char = None
                fence_length = 0
            cursor += len(line)
            continue
        fence = fence_open_re.fullmatch(stripped)
        if fence:
            marker = fence.group(1)
            fence_char = marker[:1]
            fence_length = len(marker)
            fence_start = cursor
        cursor += len(line)
    if fence_char is None:
        return None
    return _content_review_item(
        payload,
        fence_start,
        len(payload),
        reason=(
            "an unclosed Markdown fence makes later headings ambiguous; "
            "bridgeforge-codex cannot distinguish project rules from obsolete public text"
        ),
        recommended_action=(
            "close the fence, classify the listed content, remove only trusted obsolete "
            "public text, and rerun bridgeforge-codex"
        ),
    )


def _markdown_heading_sections(
    payload: bytes,
    headings: tuple[str, ...],
) -> dict[str, tuple[int, int]]:
    configured = {heading.encode("utf-8"): heading for heading in headings}
    visible_headings = _markdown_visible_headings(payload)
    matches: dict[str, list[tuple[int, int]]] = {heading: [] for heading in headings}
    for position, (_index, start, level, canonical) in enumerate(visible_headings):
        heading = configured.get(canonical)
        if heading is None:
            continue
        finish = len(payload)
        for _later_index, later_start, later_level, _later_heading in visible_headings[position + 1:]:
            if later_level <= level:
                finish = later_start
                break
        matches[heading].append((start, finish))
    duplicate = [heading for heading, spans in matches.items() if len(spans) > 1]
    if duplicate:
        raise SyncBlocked(
            "managed Markdown headings are duplicated: " + ", ".join(duplicate)
        )
    return {heading: spans[0] for heading, spans in matches.items() if spans}


@dataclass(frozen=True)
class _MarkdownTable:
    heading: str
    start: int
    end: int
    header: bytes
    separator: bytes
    rows: tuple[tuple[str, bytes, tuple[str, ...]], ...]
    newline: bytes


def _markdown_table_cells(line: bytes) -> tuple[str, ...]:
    try:
        text = line.rstrip(b"\r\n").decode("utf-8-sig").strip()
    except UnicodeDecodeError as exc:
        raise SyncBlocked("managed Markdown table is not valid UTF-8") from exc
    if not text.startswith("|") or not text.endswith("|"):
        raise SyncBlocked("managed Markdown table row is ambiguous")
    cells_list: list[str] = []
    cell: list[str] = []
    escaped = False
    for char in text[1:-1]:
        if escaped:
            if char == "|":
                cell.append("|")
            else:
                cell.extend(("\\", char))
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells_list.append("".join(cell).strip())
            cell = []
        else:
            cell.append(char)
    if escaped:
        cell.append("\\")
    cells_list.append("".join(cell).strip())
    cells = tuple(cells_list)
    if not cells or any(not item for item in cells):
        raise SyncBlocked("managed Markdown table row has an empty cell")
    return cells


def _markdown_table_key(cell: str) -> str:
    value = cell.strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()
    link = re.fullmatch(r"\[(?:[^\]]+)\]\(([^)]+)\)", value)
    if link:
        value = link.group(1).strip()
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        value = value[1:-1].strip()
    value = value.replace("\\", "/").strip()
    if not value:
        raise SyncBlocked("managed Markdown table key is empty")
    return value.casefold()


def _parse_keyed_table(payload: bytes, heading: str) -> _MarkdownTable:
    sections = _markdown_heading_sections(payload, (heading,))
    span = sections.get(heading)
    if span is None:
        raise SyncBlocked(f"managed Markdown table heading is missing: {heading}")
    section_start, section_end = span
    section = payload[section_start:section_end]
    lines = section.splitlines(keepends=True)
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)

    candidates: list[int] = []
    for index in range(len(lines) - 1):
        try:
            header_cells = _markdown_table_cells(lines[index])
            separator_cells = _markdown_table_cells(lines[index + 1])
        except SyncBlocked:
            continue
        if len(header_cells) != len(separator_cells):
            continue
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator_cells):
            candidates.append(index)
    if len(candidates) != 1:
        raise SyncBlocked(
            f"managed Markdown heading must contain exactly one unambiguous table: {heading}"
        )

    header_index = candidates[0]
    header_cells = _markdown_table_cells(lines[header_index])
    row_entries: list[tuple[str, bytes, tuple[str, ...]]] = []
    seen: set[str] = set()
    data_end = header_index + 2
    while data_end < len(lines):
        if not lines[data_end].rstrip(b"\r\n").lstrip().startswith(b"|"):
            break
        cells = _markdown_table_cells(lines[data_end])
        if len(cells) != len(header_cells):
            raise SyncBlocked(
                f"managed Markdown table row has the wrong column count: {heading}"
            )
        key = _markdown_table_key(cells[0])
        if key in seen:
            raise SyncBlocked(f"managed Markdown table has a duplicate key: {heading} :: {key}")
        seen.add(key)
        row_entries.append((key, lines[data_end], cells))
        data_end += 1

    newline = b"\r\n" if lines[header_index].endswith(b"\r\n") else b"\n"
    table_start = section_start + offsets[header_index]
    table_end = (
        section_start + offsets[data_end]
        if data_end < len(lines)
        else section_end
    )
    return _MarkdownTable(
        heading=heading,
        start=table_start,
        end=table_end,
        header=lines[header_index],
        separator=lines[header_index + 1],
        rows=tuple(row_entries),
        newline=newline,
    )


def _render_table_row(row: bytes, newline: bytes) -> bytes:
    return row.rstrip(b"\r\n") + newline


def _merge_keyed_table(
    before: bytes,
    desired: bytes,
    *,
    heading: str,
    managed_keys: tuple[str, ...],
    selected_keys: set[str],
) -> tuple[bytes, tuple[str, ...], tuple[str, ...]]:
    source = _parse_keyed_table(desired, heading)
    target = _parse_keyed_table(before, heading)
    source_header = _markdown_table_cells(source.header)
    target_header = _markdown_table_cells(target.header)
    if source_header != target_header:
        raise SyncBlocked(f"managed Markdown table header drifted: {heading}")

    normalized_contract = tuple(_markdown_table_key(item) for item in managed_keys)
    if len(set(normalized_contract)) != len(normalized_contract):
        raise SyncBlocked(f"managed Markdown table contract has duplicate keys: {heading}")
    source_rows = {key: (row, cells) for key, row, cells in source.rows}
    target_rows = {key: (row, cells) for key, row, cells in target.rows}
    if tuple(key for key, _row, _cells in source.rows) != normalized_contract:
        raise SyncBlocked(
            f"managed Markdown table source keys do not match the contract: {heading}"
        )
    unknown_selected = selected_keys - set(normalized_contract)
    if unknown_selected:
        raise SyncBlocked(
            f"selected managed Markdown table keys are unknown: {heading} :: "
            + ", ".join(sorted(unknown_selected))
        )

    missing = tuple(key for key in normalized_contract if key not in target_rows)
    conflicts = tuple(
        key
        for key in normalized_contract
        if key in target_rows and target_rows[key][1] != source_rows[key][1]
    )
    rows: list[bytes] = []
    for key in normalized_contract:
        if key in selected_keys or key not in target_rows:
            rows.append(_render_table_row(source_rows[key][0], target.newline))
        else:
            rows.append(_render_table_row(target_rows[key][0], target.newline))
    managed_set = set(normalized_contract)
    rows.extend(
        _render_table_row(row, target.newline)
        for key, row, _cells in target.rows
        if key not in managed_set
    )
    rendered = target.header + target.separator + b"".join(rows)
    after = before[:target.start] + rendered + before[target.end:]
    return after, missing, conflicts


def _normalized_managed_block(payload: bytes) -> bytes:
    return _git_blob_bytes(payload).rstrip(b" \t\r\n")


def _render_managed_block(payload: bytes, *, terminal: bool) -> bytes:
    body = _normalized_managed_block(payload)
    return body + (b"\n" if terminal else b"\n\n")


def _rename_layout_block(payload: bytes, heading: str) -> bytes:
    normalized = _git_blob_bytes(payload)
    _old_heading, separator, body = normalized.partition(b"\n")
    if not separator:
        body = b""
    body = body.lstrip(b"\n")
    body = re.sub(
        br"(?:\n[ \t]*)*\n?---[ \t]*(?:\n[ \t]*)*\Z",
        b"",
        body,
    ).rstrip(b"\n")
    rendered = heading.encode("utf-8")
    if body:
        rendered += b"\n\n" + body
    return rendered + b"\n"


def _plan_section_layout(
    asset: dict[str, Any],
    desired: bytes,
    before: bytes,
    project_root: Path,
) -> tuple[bytes, list[Gap]]:
    layout = asset["section_layout"]
    entries = _layout_sections(layout)
    retired = list(layout.get("retired_sections", []))
    section_candidates: list[str] = []
    for entry in entries:
        section_candidates.append(str(entry["heading"]))
        section_candidates.extend(str(item) for item in entry.get("legacy_headings", []))
    retired_candidates = [
        str(heading)
        for entry in retired
        for heading in entry.get("legacy_headings", [])
    ]
    candidates = tuple(section_candidates + retired_candidates)
    review_payload = _git_blob_bytes(before)
    try:
        target_sections = _markdown_heading_sections(before, candidates)
        source_sections = _markdown_heading_sections(
            desired,
            tuple(str(entry["heading"]) for entry in entries),
        )
        visible = _markdown_visible_headings(before)
    except SyncBlocked as exc:
        review = _unclosed_fence_review_item(review_payload)
        if review is None:
            review = _content_review_item(
                review_payload,
                0,
                len(review_payload),
                reason=f"legacy AGENTS structure cannot be parsed safely: {exc}",
                recommended_owner="project zone after structural repair",
                recommended_action=(
                    "repair duplicate headings or encoding, classify every remaining "
                    "section, then rerun bridgeforge-codex"
                ),
            )
        return before, [
            Gap(
                str(asset["id"]),
                str(asset["target"]),
                f"section layout ownership is ambiguous: {exc}",
                (review,),
            )
        ]

    gaps: list[Gap] = []
    if asset.get("agents_zones") is not None:
        accepted_residuals = _declared_hashes(
            layout.get("trusted_residual_sha256", {}),
            f"asset {asset['id']!r} layout residual history",
        )
        accepted_residuals.add(_layout_residual_hash(desired, layout))
        observed_residual = _layout_residual_hash(before, layout)
        if observed_residual not in accepted_residuals:
            residual_payload, residual_spans = _layout_residual_segments(before, layout)
            review_items = tuple(
                _content_review_item(
                    residual_payload,
                    start,
                    finish,
                    reason=(
                        "content outside every recognized legacy section does not match "
                        "a trusted layout residual"
                    ),
                    recommended_action=(
                        "classify this exact span as project-owned or obsolete public "
                        "content, then rerun bridgeforge-codex"
                    ),
                )
                for start, finish in residual_spans
                if residual_payload[start:finish].strip()
            )
            return before, [Gap(
                str(asset["id"]),
                str(asset["target"]),
                "legacy AGENTS contains unclassified content outside recognized "
                f"sections; original file preserved (observed {observed_residual})",
                review_items,
            )]
    rendered: dict[str, bytes] = {}
    matched_spans: list[tuple[int, int]] = []
    for entry in entries:
        heading = str(entry["heading"])
        source_span = source_sections.get(heading)
        if source_span is None:
            raise SyncBlocked(
                f"asset {asset['id']!r} source layout section is missing: {heading}"
            )
        source_block = desired[slice(*source_span)]
        aliases = tuple(str(item) for item in entry.get("legacy_headings", []))
        present = [
            candidate
            for candidate in (heading,) + aliases
            if candidate in target_sections
        ]
        matched_spans.extend(target_sections[candidate] for candidate in present)
        ownership = str(entry["ownership"])
        if ownership in {"project", "keyed"}:
            if len(present) > 1:
                gaps.append(Gap(
                    str(asset["id"]),
                    str(asset["target"]),
                    f"section layout has multiple candidates for {heading}: "
                    + ", ".join(present),
                    tuple(
                        _content_review_item(
                            review_payload,
                            target_sections[candidate][0],
                            target_sections[candidate][1],
                            reason=(
                                f"multiple sections claim the same project ownership slot: {heading}"
                            ),
                            recommended_owner="one canonical project-zone section",
                            recommended_action=(
                                "merge unique project rules, remove only exact or trusted "
                                "duplicates, then keep one canonical section"
                            ),
                        )
                        for candidate in present
                    ),
                ))
                continue
            block = (
                before[slice(*target_sections[present[0]])]
                if present
                else source_block
            )
            rendered[heading] = _rename_layout_block(block, heading)
            continue

        if heading in present and len(present) > 1:
            gaps.append(Gap(
                str(asset["id"]),
                str(asset["target"]),
                f"section layout mixes current and legacy headings for {heading}",
                tuple(
                    _content_review_item(
                        review_payload,
                        target_sections[candidate][0],
                        target_sections[candidate][1],
                        reason=(
                            f"current and legacy headings both claim the managed slot: {heading}"
                        ),
                        recommended_owner="public instructions after exact deduplication",
                        recommended_action=(
                            "compare both sections, retain the trusted current public section, "
                            "and move only unique project rules to the project zone"
                        ),
                    )
                    for candidate in present
                ),
            ))
            continue
        if heading in present:
            target_block = before[slice(*target_sections[heading])]
            if (
                _normalize_layout_rendered_tokens(
                    _normalized_managed_block(target_block),
                    entry,
                )
                != _normalize_layout_rendered_tokens(
                    _normalized_managed_block(source_block),
                    entry,
                )
            ):
                gaps.append(Gap(
                    str(asset["id"]),
                    str(asset["target"]),
                    f"managed layout section drifted; local content preserved: {heading}",
                    (_content_review_item(
                        review_payload,
                        target_sections[heading][0],
                        target_sections[heading][1],
                        reason=(
                            "the heading matches a managed section but its body is not "
                            "byte-identical to the trusted public content"
                        ),
                        recommended_owner="review before public/project classification",
                        recommended_action=(
                            "compare this section with current public instructions; remove "
                            "only exact or trusted duplicates and move unique project rules "
                            "to the project zone"
                        ),
                    ),),
                ))
                continue
        else:
            untrusted = [
                alias
                for alias in present
                if _layout_block_hash(
                    before[slice(*target_sections[alias])],
                    entry,
                    asset,
                    project_root,
                ) not in _trusted_layout_hashes(entry, alias)
            ]
            if untrusted:
                gaps.append(Gap(
                    str(asset["id"]),
                    str(asset["target"]),
                    "managed legacy section drifted; local content preserved: "
                    + ", ".join(untrusted),
                    tuple(
                        _content_review_item(
                            review_payload,
                            target_sections[alias][0],
                            target_sections[alias][1],
                            reason=(
                                "the legacy managed heading is recognized but its body does "
                                "not match any trusted historical block"
                            ),
                            recommended_owner="review before public/project classification",
                            recommended_action=(
                                "compare with current public instructions; move unique project "
                                "rules to the project zone and remove only exact or trusted duplicates"
                            ),
                        )
                        for alias in untrusted
                    ),
                ))
                continue
        target_block = (
            before[slice(*target_sections[present[0]])]
            if present
            else source_block
        )
        source_block = _preserve_layout_rendered_tokens(
            source_block,
            target_block,
            entry,
        )
        rendered[heading] = _render_managed_block(source_block, terminal=False)

    for entry in retired:
        for alias in (str(item) for item in entry.get("legacy_headings", [])):
            span = target_sections.get(alias)
            if span is None:
                continue
            matched_spans.append(span)
            digest = _target_hash(
                _normalized_managed_block(before[slice(*span)]),
                asset,
                project_root,
            )
            if digest not in _trusted_layout_hashes(entry, alias):
                gaps.append(Gap(
                    str(asset["id"]),
                    str(asset["target"]),
                    f"retired legacy section drifted; local content preserved: {alias}",
                    (_content_review_item(
                        review_payload,
                        span[0],
                        span[1],
                        reason=(
                            "the section is retired upstream but contains content that does "
                            "not match the trusted retired version"
                        ),
                        recommended_owner="project zone if unique; otherwise retire",
                        recommended_action=(
                            "map unique project rules into the project zone; retire the section "
                            "only after every remaining line is an exact or trusted duplicate"
                        ),
                    ),),
                ))

    known_headings = set(candidates)
    known_headings.update(str(group["heading"]) for group in layout["groups"])
    structural_starts = [span[0] for span in matched_spans]
    group_headings = {str(group["heading"]) for group in layout["groups"]}
    structural_starts.extend(
        start
        for _index, start, _level, raw_heading in visible
        if raw_heading.decode("utf-8") in group_headings
    )
    preamble_end = min(structural_starts) if structural_starts else len(before)
    for _index, start, _level, raw_heading in visible:
        heading = raw_heading.decode("utf-8")
        if heading in known_headings:
            continue
        if start < preamble_end:
            continue
        if any(span_start < start < span_end for span_start, span_end in matched_spans):
            continue
        finish = len(before)
        current_level = next(
            level
            for _visible_index, visible_start, level, _visible_heading in visible
            if visible_start == start
        )
        for _later_index, later_start, later_level, _later_heading in visible:
            if later_start > start and later_level <= current_level:
                finish = later_start
                break
        gaps.append(Gap(
            str(asset["id"]),
            str(asset["target"]),
            f"unrecognized top-level layout heading; original file preserved: {heading}",
            (_content_review_item(
                review_payload,
                start,
                finish,
                reason=f"the heading is not declared by the legacy ownership map: {heading}",
                recommended_action=(
                    "classify this section as project-owned or obsolete public content, "
                    "then rerun bridgeforge-codex"
                ),
            ),),
        ))

    if gaps:
        return before, gaps

    preamble = _git_blob_bytes(before[:preamble_end]).rstrip(b"\n")
    blocks: list[bytes] = [preamble] if preamble else []
    for group in layout["groups"]:
        children = group.get("sections")
        if isinstance(children, list):
            group_parts = [str(group["heading"]).encode("utf-8")]
            group_parts.extend(
                rendered[str(entry["heading"])].rstrip(b"\n")
                for entry in children
            )
            blocks.append(b"\n\n".join(group_parts))
        else:
            blocks.append(rendered[str(group["heading"])].rstrip(b"\n"))
    return b"\n\n".join(blocks).rstrip(b"\n") + b"\n", []


def _project_requirement_items(
    project_root: Path,
    contract: dict[str, Any],
    actions: Iterable[Action] = (),
) -> list[dict[str, Any]]:
    planned_payloads = {
        (action.asset_id, action.target): action.payload
        for action in actions
        if action.classification == "safe" and action.payload is not None
    }
    missing: list[tuple[str, str]] = []
    for asset in contract["assets"]:
        zones = asset.get("agents_zones") if isinstance(asset, dict) else None
        layout = asset.get("section_layout") if isinstance(asset, dict) else None
        if not isinstance(layout, dict) and not isinstance(zones, dict):
            continue
        relative = str(asset["target"])
        target = _inside(project_root, relative, f"required project content {asset['id']}")
        payload = planned_payloads.get((str(asset["id"]), relative))
        if payload is None and target.is_file() and not _is_reparse(target):
            payload = target.read_bytes()
        if isinstance(zones, dict):
            required_entries = [
                {"heading": heading}
                for heading in zones["project"].get("required_content_headings", [])
            ]
        else:
            required_entries = [
                entry
                for entry in _layout_sections(layout)
                if entry.get("required") is True
            ]
        if payload is None:
            missing.extend((str(entry["heading"]), relative) for entry in required_entries)
            continue
        headings = tuple(str(entry["heading"]) for entry in required_entries)
        try:
            sections = _markdown_heading_sections(payload, headings)
        except SyncBlocked:
            missing.extend((heading, relative) for heading in headings)
            continue
        for heading in headings:
            span = sections.get(heading)
            if span is None:
                missing.append((heading, relative))
                continue
            block = _git_blob_bytes(payload[slice(*span)])
            _line, _separator, body = block.partition(b"\n")
            body = re.sub(br"<!--.*?-->", b"", body, flags=re.DOTALL)
            if not body.strip(b" \t\r\n"):
                missing.append((heading, relative))
    items = [
        {
            "id": f"P{index}",
            "title": f"填写项目自定义区域：{heading}",
            "category": "project_required_content",
            "affects_readiness": True,
            "executor": "user",
            "impact": "bridgeforge-codex 骨架已更新，但项目专属事实仍是空占位",
            "completion_criteria": f"{target} 中 {heading} 含有项目真实内容且已删除占位注释",
        }
        for index, (heading, target) in enumerate(missing, 1)
    ]
    for legacy_name in ("test", "tests"):
        legacy = project_root / legacy_name
        if not os.path.lexists(legacy):
            continue
        items.append({
            "id": f"P{len(items) + 1}",
            "title": f"迁移旧测试目录：{legacy_name}/ -> scripts/tests/",
            "category": "project_layout_migration",
            "affects_readiness": True,
            "executor": "user",
            "impact": (
                "bridgeforge-codex 不会自动移动项目测试；请同时更新 imports、测试发现配置、"
                "CI 和语言工具链路径"
            ),
            "completion_criteria": (
                f"项目根不再存在 {legacy_name}/，测试代码和 fixture 已迁入 scripts/tests/**"
            ),
        })
    if os.path.lexists(project_root / ".claude") or os.path.lexists(
        project_root / "CLAUDE.md"
    ):
        items.append({
            "id": f"N{len(items) + 1}",
            "title": "检测到已停止支持的 Claude 项目资产",
            "category": "unsupported_legacy_notice",
            "affects_readiness": False,
            "executor": "user",
            "impact": (
                "bridgeforge-codex 只报告路径存在；不会读取、迁移、删除，"
                "也不会阻止 Codex 更新"
            ),
            "completion_criteria": "无需操作；如需清理请由用户在本轮之外自行审阅",
        })
    return items


def _project_needs_user_action(items: Iterable[dict[str, Any]]) -> bool:
    return any(
        item.get("affects_readiness") is True
        and item.get("category") in {
            "project_required_content",
            "project_layout_migration",
        }
        for item in items
    )


def _append_managed_blocks(payload: bytes, blocks: list[bytes]) -> bytes:
    if not blocks:
        return payload
    if payload.endswith((b"\n\n", b"\r\n\r\n")):
        separator = b""
    elif payload.endswith((b"\n", b"\r")):
        separator = b"\n"
    else:
        separator = b"\n\n"
    rendered = b"\n\n".join(_normalized_managed_block(block) for block in blocks)
    return payload + separator + rendered + b"\n"


def _insert_managed_block_in_source_order(
    before: bytes,
    desired: bytes,
    heading: str,
    registered: tuple[str, ...],
) -> bytes:
    source_sections = _markdown_heading_sections(desired, registered)
    target_sections = _markdown_heading_sections(before, registered)
    source_span = source_sections.get(heading)
    if source_span is None:
        raise SyncBlocked(f"additive heading is missing from source: {heading}")
    source_order = [
        item
        for item, _span in sorted(
            source_sections.items(),
            key=lambda entry: entry[1][0],
        )
    ]
    position = source_order.index(heading)
    for following in source_order[position + 1:]:
        target_span = target_sections.get(following)
        if target_span is None:
            continue
        block = _render_managed_block(
            desired[slice(*source_span)],
            terminal=False,
        )
        return before[:target_span[0]] + block + before[target_span[0]:]
    return _append_managed_blocks(before, [desired[slice(*source_span)]])


def _replace_heading_items(
    before: bytes,
    desired: bytes,
    headings: tuple[str, ...],
) -> bytes:
    if not headings:
        return before
    desired_sections = _markdown_heading_sections(desired, headings)
    current_sections = _markdown_heading_sections(before, headings)
    replacements: list[tuple[int, int, bytes]] = []
    for heading in headings:
        desired_span = desired_sections.get(heading)
        if desired_span is None:
            raise SyncBlocked(f"selected absorption block is missing from source: {heading}")
        desired_start, desired_end = desired_span
        desired_block = desired[desired_start:desired_end]
        current_span = current_sections.get(heading)
        if current_span is None:
            raise SyncBlocked(
                f"selected replace-block heading is missing from target: {heading}"
            )
        current_start, current_end = current_span
        replacements.append(
            (
                current_start,
                current_end,
                _render_managed_block(
                    desired_block,
                    terminal=current_end == len(before),
                ),
            )
        )
    after = before
    for start, finish, replacement in sorted(replacements, reverse=True):
        after = after[:start] + replacement + after[finish:]
    return after


def _plan_managed_markdown_blocks(
    asset: dict[str, Any],
    desired: bytes,
    before: bytes,
    target: Path,
    project_root: Path,
) -> tuple[list[Action], list[Gap]]:
    block_contract = asset.get("managed_blocks")
    headings = tuple(str(item) for item in block_contract.get("headings", []))
    additive_headings = tuple(
        str(item) for item in block_contract.get("additive_headings", [])
    )
    keyed_tables = tuple(block_contract.get("keyed_tables", []))
    keyed_contracts = tuple(
        (
            str(item["heading"]),
            tuple(str(key) for key in item["managed_keys"]),
        )
        for item in keyed_tables
    )
    registered = (
        headings
        + additive_headings
        + tuple(heading for heading, _keys in keyed_contracts)
    )
    try:
        source_sections = _markdown_heading_sections(desired, registered)
        target_sections = _markdown_heading_sections(before, registered)
    except SyncBlocked as exc:
        return [], [
            Gap(
                asset["id"],
                asset["target"],
                f"managed block ownership is ambiguous: {exc}",
            )
        ]
    missing_source = [heading for heading in registered if heading not in source_sections]
    if missing_source:
        raise SyncBlocked(
            f"asset {asset['id']!r} source is missing managed headings: "
            + ", ".join(missing_source)
        )
    safe_replacements: list[tuple[int, int, bytes]] = []
    missing_additive: list[str] = []
    ordinary_gaps: list[Gap] = []
    for heading in headings:
        source_start, source_end = source_sections[heading]
        source_block = desired[source_start:source_end]
        target_span = target_sections.get(heading)
        if target_span is None:
            ordinary_gaps.append(Gap(
                asset["id"],
                asset["target"],
                f"ordinary managed heading is missing; original file preserved: {heading}",
            ))
            continue
        target_start, target_end = target_span
        target_block = before[target_start:target_end]
        same_content = (
            _normalized_managed_block(target_block)
            == _normalized_managed_block(source_block)
        )
        if same_content and target_end != len(before):
            continue
        rendered = _render_managed_block(
            source_block,
            terminal=target_end == len(before),
        )
        if same_content and _git_blob_bytes(target_block) == rendered:
            continue
        if same_content:
            safe_replacements.append((target_start, target_end, rendered))
        else:
            ordinary_gaps.append(Gap(
                asset["id"],
                asset["target"],
                f"ordinary managed heading drifted; local content preserved: {heading}",
            ))

    for heading in additive_headings:
        source_start, source_end = source_sections[heading]
        source_block = desired[source_start:source_end]
        target_span = target_sections.get(heading)
        if target_span is None:
            missing_additive.append(heading)
            continue
        target_start, target_end = target_span
        target_block = before[target_start:target_end]
        same_content = (
            _normalized_managed_block(target_block)
            == _normalized_managed_block(source_block)
        )
        if same_content:
            rendered = _render_managed_block(
                source_block,
                terminal=target_end == len(before),
            )
            if _git_blob_bytes(target_block) != rendered:
                safe_replacements.append((target_start, target_end, rendered))
        else:
            ordinary_gaps.append(Gap(
                asset["id"],
                asset["target"],
                f"additive managed heading already exists with local drift; preserved: {heading}",
            ))

    safe_after = before
    keyed_safe_changed = False
    for start, finish, replacement in sorted(safe_replacements, reverse=True):
        safe_after = safe_after[:start] + replacement + safe_after[finish:]
    for heading in sorted(
        missing_additive,
        key=lambda item: source_sections[item][0],
    ):
        safe_after = _insert_managed_block_in_source_order(
            safe_after,
            desired,
            heading,
            registered,
        )
    all_after = safe_after

    item_labels: list[str] = []
    item_details: list[tuple[str, str, str, str]] = []
    try:
        for heading, managed_keys in keyed_contracts:
            current_sections = _markdown_heading_sections(safe_after, (heading,))
            if heading not in current_sections:
                ordinary_gaps.append(Gap(
                    asset["id"],
                    asset["target"],
                    f"managed keyed-table heading is missing; original file preserved: {heading}",
                ))
                continue
            before_safe_merge = safe_after
            safe_after, _missing, conflicts = _merge_keyed_table(
                safe_after,
                desired,
                heading=heading,
                managed_keys=managed_keys,
                selected_keys=set(),
            )
            keyed_safe_changed = keyed_safe_changed or safe_after != before_safe_merge
            all_after, _all_missing, _all_conflicts = _merge_keyed_table(
                all_after,
                desired,
                heading=heading,
                managed_keys=managed_keys,
                selected_keys=set(conflicts),
            )
            display_keys = {
                _markdown_table_key(key): key
                for key in managed_keys
            }
            for key in conflicts:
                display_key = display_keys[key]
                label = f"{heading} :: {display_key}"
                item_labels.append(label)
                item_details.append((label, "keyed_table", heading, display_key))
    except SyncBlocked as exc:
        return [], [
            Gap(
                asset["id"],
                asset["target"],
                f"managed keyed-table ownership is ambiguous: {exc}",
            )
        ]

    if ordinary_gaps:
        return [], ordinary_gaps

    actions: list[Action] = []
    if safe_after != before:
        actions.append(_action(
            asset,
            target,
            (
                "merge-managed-markdown-safe"
                if keyed_safe_changed
                else "normalize-managed-block-boundary"
            ),
            "safe",
            "add missing managed table keys and normalize managed block boundaries",
            before,
            safe_after,
            project_root,
            keyed_table_contracts=keyed_contracts,
            local_impact="project-owned headings and table rows are preserved",
        ))
    if item_labels:
        actions.append(_action(
            asset,
            target,
            "absorb-upstream-items",
            "absorb",
            "upstream wins only for the selected managed block or same-key table row conflicts",
            before,
            all_after,
            project_root,
            managed_blocks=tuple(item_labels),
            managed_item_details=tuple(item_details),
            keyed_table_contracts=keyed_contracts,
            source_payload=desired,
            local_impact=(
                "selected replace-block content may be overwritten; keyed tables replace only "
                "same-key conflicts and preserve downstream-only rows"
            ),
        ))
    return actions, ordinary_gaps


def _agents_project_sections(
    project_block: bytes,
    zones: dict[str, Any],
) -> dict[str, tuple[int, int]]:
    headings = tuple(str(item) for item in zones["project"]["required_headings"])
    sections = _markdown_heading_sections(project_block, headings)
    missing = [heading for heading in headings if heading not in sections]
    if missing:
        raise SyncBlocked("project zone is missing required headings: " + ", ".join(missing))
    actual_order = [
        heading
        for heading, _span in sorted(sections.items(), key=lambda item: item[1][0])
    ]
    if actual_order != list(headings):
        raise SyncBlocked("project zone headings are duplicated or out of order")
    return sections


def _legacy_agents_source(
    asset: dict[str, Any],
    desired: bytes,
) -> bytes:
    zones = asset["agents_zones"]
    migrations = {
        str(item["legacy_heading"]): str(item["project_heading"])
        for item in zones["project"]["legacy_section_migrations"]
    }
    source_headings = tuple(
        migrations.get(str(entry["heading"]), str(entry["heading"]))
        for entry in _layout_sections(asset["section_layout"])
    )
    source_sections = _markdown_heading_sections(desired, source_headings)
    blocks: list[bytes] = []
    for group in asset["section_layout"]["groups"]:
        children = group.get("sections")
        entries = children if isinstance(children, list) else [group]
        group_parts: list[bytes] = []
        if isinstance(children, list):
            group_parts.append(str(group["heading"]).encode("utf-8"))
        for entry in entries:
            legacy_heading = str(entry["heading"])
            source_heading = migrations.get(legacy_heading, legacy_heading)
            span = source_sections.get(source_heading)
            if span is None:
                raise SyncBlocked(
                    f"AGENTS zone source is missing migration heading: {source_heading}"
                )
            group_parts.append(
                _rename_layout_block(desired[slice(*span)], legacy_heading).rstrip(b"\n")
            )
        blocks.append(b"\n\n".join(group_parts))
    legacy = b"\n\n".join(blocks).rstrip(b"\n") + b"\n"
    for marker in (
        zones["public"]["begin"],
        zones["public"]["end"],
        zones["project"]["begin"],
        zones["project"]["end"],
    ):
        legacy = re.sub(
            br"(?m)^" + re.escape(str(marker).encode("utf-8")) + br"\n?",
            b"",
            legacy,
        )
    return legacy.rstrip(b"\n") + b"\n"


def _preserve_agents_public_rendered_tokens(
    source_public: bytes,
    target_public: bytes,
    asset: dict[str, Any],
) -> bytes:
    rendered_entries = [
        entry
        for entry in _layout_sections(asset["section_layout"])
        if entry.get("hash_normalizer") is not None
    ]
    if not rendered_entries:
        return source_public
    headings = tuple(str(entry["heading"]) for entry in rendered_entries)
    source_sections = _markdown_heading_sections(source_public, headings)
    target_sections = _markdown_heading_sections(target_public, headings)
    replacements: list[tuple[int, int, bytes]] = []
    for entry in rendered_entries:
        heading = str(entry["heading"])
        source_span = source_sections.get(heading)
        target_span = target_sections.get(heading)
        if source_span is None or target_span is None:
            raise SyncBlocked(f"AGENTS rendered token migration is incomplete: {heading}")
        replacements.append((
            source_span[0],
            source_span[1],
            _preserve_layout_rendered_tokens(
                source_public[slice(*source_span)],
                target_public[slice(*target_span)],
                entry,
            ),
        ))
    result = source_public
    for start, finish, replacement in sorted(replacements, reverse=True):
        result = result[:start] + replacement + result[finish:]
    return result


def _plan_agents_zones(
    asset: dict[str, Any],
    desired: bytes,
    before: bytes,
    target: Path,
    project_root: Path,
) -> tuple[list[Action], list[Gap]]:
    zones = asset["agents_zones"]
    marker_values = tuple(
        str(value).encode("utf-8")
        for value in (
            zones["public"]["begin"], zones["public"]["end"],
            zones["project"]["begin"], zones["project"]["end"],
        )
    )
    marker_count = sum(before.count(marker) for marker in marker_values)
    try:
        desired_parts = _agents_zone_parts(desired, zones)
        _agents_project_sections(desired_parts[3], zones)
    except SyncBlocked as exc:
        raise SyncBlocked(f"canonical AGENTS zones are invalid: {exc}") from exc

    if marker_count == 0:
        try:
            legacy_source = _legacy_agents_source(asset, desired)
            migrated, gaps = _plan_section_layout(
                asset, legacy_source, before, project_root
            )
        except SyncBlocked as exc:
            return [], [Gap(
                str(asset["id"]), str(asset["target"]),
                f"legacy AGENTS migration is ambiguous: {exc}",
                (_content_review_item(
                    _git_blob_bytes(before),
                    0,
                    len(_git_blob_bytes(before)),
                    reason=f"legacy AGENTS structure cannot be parsed safely: {exc}",
                    recommended_owner="project zone after structural repair",
                    recommended_action=(
                        "repair the listed structure, classify every remaining section, "
                        "then rerun bridgeforge-codex"
                    ),
                ),),
            )]
        if gaps:
            return [], gaps
        migrations = tuple(
            (
                str(item["legacy_heading"]),
                str(item["project_heading"]),
            )
            for item in zones["project"]["legacy_section_migrations"]
        )
        legacy_sections = _markdown_heading_sections(
            migrated, tuple(item[0] for item in migrations)
        )
        public_after = _preserve_agents_public_rendered_tokens(
            desired_parts[1], migrated, asset
        )
        project_after = desired_parts[3]
        replacements: list[tuple[int, int, bytes]] = []
        project_sections = _agents_project_sections(project_after, zones)
        for legacy_heading, project_heading in migrations:
            legacy_span = legacy_sections.get(legacy_heading)
            project_span = project_sections.get(project_heading)
            if legacy_span is None or project_span is None:
                raise SyncBlocked(
                    f"AGENTS migration mapping is incomplete: {legacy_heading} -> {project_heading}"
                )
            replacements.append((
                project_span[0], project_span[1],
                _rename_layout_block(
                    migrated[slice(*legacy_span)], project_heading
                ),
            ))
        for start, finish, replacement in sorted(replacements, reverse=True):
            project_after = project_after[:start] + replacement + project_after[finish:]
        after = b"".join((
            desired_parts[0], public_after, desired_parts[2],
            project_after, desired_parts[4],
        ))
        return [
            _action(
                asset, target, "migrate-agents-zones", "safe",
                "migrate verified legacy project sections into the project-owned zone",
                before, after, project_root,
                local_impact=(
                    "recognized project section bodies are preserved; unclassified legacy content blocks migration"
                ),
            )
        ], []

    try:
        before_parts = _agents_zone_parts(before, zones)
        _agents_project_sections(before_parts[3], zones)
    except SyncBlocked as exc:
        return [], [Gap(
            str(asset["id"]), str(asset["target"]),
            f"AGENTS zone ownership is ambiguous: {exc}; original file preserved",
            (_content_review_item(
                _git_blob_bytes(before),
                0,
                len(_git_blob_bytes(before)),
                reason=f"project/public zone markers or required headings are ambiguous: {exc}",
                recommended_owner="existing project zone after marker repair",
                recommended_action=(
                    "repair marker uniqueness and order without changing project content, "
                    "then rerun bridgeforge-codex"
                ),
            ),),
        )]
    public_hash = _agents_public_zone_hash(before_parts[1], asset, project_root)
    accepted = {str(zones["public"]["current_sha256"])} | _declared_hashes(
        zones["public"].get("historical_sha256", {}),
        f"asset {asset['id']!r} public zone history",
    )
    if public_hash not in accepted:
        public_start = len(before_parts[0])
        return [], [Gap(
            str(asset["id"]), str(asset["target"]),
            "BridgeForge public zone drifted; move project constraints to the project zone "
            f"and restore an official public block (observed {public_hash})",
            (_content_review_item(
                _git_blob_bytes(before),
                public_start,
                public_start + len(before_parts[1]),
                reason="the public zone does not match current or trusted historical content",
                recommended_owner="public zone after project-only rules are extracted",
                recommended_action=(
                    "move unique project rules to the project zone and restore the exact "
                    "current public block"
                ),
            ),),
        )]
    public_after = _preserve_agents_public_rendered_tokens(
        desired_parts[1], before_parts[1], asset
    )
    after = b"".join((
        desired_parts[0], public_after, desired_parts[2],
        before_parts[3], desired_parts[4],
    ))
    if after == before:
        return [], []
    return [
        _action(
            asset, target, "replace-agents-public-zone", "safe",
            "public zone matches an exact published hash; project zone is preserved byte-for-byte",
            before, after, project_root,
            local_impact="project zone bytes are unchanged",
        )
    ], []


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
    if asset.get("agents_zones") is not None:
        return _plan_agents_zones(asset, desired, before, target, project_root)
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
    if asset.get("section_layout") is not None:
        layout_after, layout_gaps = _plan_section_layout(
            asset,
            desired,
            before,
            project_root,
        )
        if layout_gaps:
            return [], layout_gaps
        block_actions, block_gaps = _plan_managed_markdown_blocks(
            asset,
            desired,
            layout_after,
            target,
            project_root,
        )
        if block_gaps:
            return [], block_gaps
        safe_after = layout_after
        safe_block = next(
            (item for item in block_actions if item.classification == "safe"),
            None,
        )
        if safe_block is not None and safe_block.payload is not None:
            safe_after = safe_block.payload
        combined: list[Action] = []
        if safe_after != before:
            combined.append(_action(
                asset,
                target,
                "migrate-section-layout",
                "safe",
                "migrate exact published headings, preserve project sections, and apply safe keyed rows",
                before,
                safe_after,
                project_root,
                keyed_table_contracts=(
                    safe_block.keyed_table_contracts if safe_block is not None else ()
                ),
                local_impact="project-owned section bodies and downstream-only table rows are preserved",
            ))
        for item in block_actions:
            if item.classification != "absorb":
                continue
            combined.append(_action(
                asset,
                target,
                item.action,
                item.classification,
                item.reason,
                before,
                item.payload,
                project_root,
                managed_blocks=item.managed_blocks,
                managed_item_details=item.managed_item_details,
                keyed_table_contracts=item.keyed_table_contracts,
                local_impact=item.local_impact,
                source_payload=item.source_payload,
            ))
        return combined, []
    if asset.get("managed_blocks") is not None:
        return _plan_managed_markdown_blocks(
            asset,
            desired,
            before,
            target,
            project_root,
        )
    return [], [Gap(asset["id"], asset["target"], "whole-file target is modified or has no trusted historical hash")]


def _plan_seed(
    asset: dict[str, Any],
    source: bytes,
    target: Path,
    project_root: Path,
) -> tuple[list[Action], list[Gap]]:
    desired = _render_source(source, asset, project_root)
    if not target.exists():
        return [
            _action(
                asset,
                target,
                "create",
                "safe",
                "project-owned seed is missing",
                None,
                desired,
                project_root,
            )
        ], []
    if not target.is_file() or _is_reparse(target):
        return [], [Gap(asset["id"], asset["target"], "seed target is not a regular file")]
    return [], []


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
    target_begin = begin
    target_end_marker = end
    legacy_begin = b"# >>> BRIDGEFORGE_MANAGED_BEGIN"
    legacy_end = b"# <<< BRIDGEFORGE_MANAGED_END"
    if (
        before.count(legacy_begin) == 1
        and before.count(legacy_end) == 1
        and begin not in before
        and end not in before
    ):
        target_begin = legacy_begin
        target_end_marker = legacy_end
    try:
        target_start, target_end = _marker_slice(
            before,
            target_begin,
            target_end_marker,
        )
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
        return [], [Gap(asset["id"], asset["target"], _retirement_gap_reason(asset))]
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
    lint = template_root / "templates" / "hooks" / "memory_lint.py"
    if not lint.is_file() or _is_reparse(lint):
        raise SyncBlocked(f"canonical memory schema auditor is missing or unsafe: {lint}")
    command = [
        sys.executable,
        str(lint),
        "--organize",
        "--project-root",
        str(project_root),
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
            {
                key: value
                for key, value in asdict(item).items()
                if key not in {"payload", "source_payload"}
            }
            for item in plan.actions
        ],
        "gaps": [asdict(item) for item in plan.gaps],
        "blockers": plan.blockers,
        "project_requirements": plan.project_requirements,
    }
    return _sha256_bytes(_canonical_json(payload))


LEGACY_STAMP = ".codex/.bridgeforge_version"
CURRENT_STAMP = ".codex/.bridgeforge_codex_version"


def _detect_mode(project_root: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    if (
        (project_root / CURRENT_STAMP).is_file()
        or (project_root / LEGACY_STAMP).is_file()
    ):
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
    current_semver = _semver(current_version, "bridgeforge-codex VERSION")
    if (
        contract.get("release_version") is not None
        and contract.get("release_version") != current_version
    ):
        raise SyncBlocked(
            "bridgeforge-codex VERSION does not match the asset contract release_version"
        )
    minimum = _semver(str(contract["minimum_supported_version"]), "minimum supported version")
    stamp = _inside(root, str(contract["stamp"]), "version stamp")
    legacy_stamp = _inside(root, LEGACY_STAMP, "legacy version stamp")
    if stamp.exists() and legacy_stamp.exists():
        previous_version = None
        stamp_conflict = True
    else:
        source_stamp = stamp if stamp.is_file() else legacy_stamp
        previous_version = (
            source_stamp.read_text(encoding="utf-8-sig").strip()
            if source_stamp.is_file()
            else None
        )
        stamp_conflict = False
    previous_semver: tuple[int, int, int] | None = None
    blockers: list[str] = []
    if stamp_conflict:
        blockers.append(
            "both legacy and bridgeforge-codex version stamps exist; zero writes performed"
        )
    elif selected_mode == "update" and previous_version is None:
        blockers.append(
            "update mode requires an existing .codex/.bridgeforge_codex_version "
            "or a migratable legacy stamp"
        )
    if previous_version is not None:
        try:
            previous_semver = _semver(previous_version, "project bridgeforge-codex version")
            if previous_semver < minimum:
                blockers.append(
                    f"project version {previous_version} predates the automatic migration baseline "
                    f"{contract['minimum_supported_version']}"
                )
            if previous_semver > current_semver:
                blockers.append(
                    f"project version {previous_version} is newer than this bridgeforge-codex {current_version}"
                )
        except SyncBlocked as exc:
            blockers.append(str(exc))

    actions: list[Action] = []
    if legacy_stamp.is_file() and not stamp.exists() and previous_version is not None:
        actions.append(Action(
            asset_id="codex.legacy-version-stamp-migration",
            target=LEGACY_STAMP,
            action="migrate-stamp",
            classification="risk",
            reason=(
                "replace the verified legacy version stamp with "
                ".codex/.bridgeforge_codex_version after validation"
            ),
            before_sha256=_sha256_path(legacy_stamp),
            after_sha256=_sha256_bytes((current_version + "\n").encode("utf-8")),
            payload=(current_version + "\n").encode("utf-8"),
        ))
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
            elif strategy == "seed":
                asset_actions, asset_gaps = _plan_seed(asset, source, target, root)
            else:
                asset_actions, asset_gaps = _plan_region(asset, source, target, root)
        actions.extend(asset_actions)
        gaps.extend(asset_gaps)
    root_agents_gap = any(gap.asset_id == "root.agents" for gap in gaps)
    if root_agents_gap:
        retained_actions: list[Action] = []
        for action in actions:
            migration = RETIRED_RULE_MIGRATION_TARGETS.get(action.target)
            if action.action != "retire" or migration is None:
                retained_actions.append(action)
                continue
            gaps.append(Gap(
                action.asset_id,
                action.target,
                "retirement blocked because the native AGENTS instruction migration "
                f"is incomplete; original file preserved and must remain until {migration} "
                "is verified",
            ))
        actions = retained_actions
    structural_gap_targets = sorted({
        gap.target
        for gap in gaps
        if gap.target.startswith(".codex/rules/")
        or "seed" in gap.reason.casefold()
    })
    existing_rule_seed_targets: list[str] = []
    for asset in contract["assets"]:
        if not isinstance(asset, dict) or asset.get("strategy") != "seed":
            continue
        seed_target_relative = str(asset.get("target", ""))
        if not seed_target_relative.startswith(".codex/rules/"):
            continue
        seed_target = _inside(
            root,
            seed_target_relative,
            f"seed asset {asset['id']} target",
        )
        if seed_target.is_file() and not _is_reparse(seed_target):
            existing_rule_seed_targets.append(seed_target_relative)
    existing_rule_seed_targets.sort()
    if (
        selected_mode == "update"
        and previous_semver is not None
        and previous_semver < current_semver
        and structural_gap_targets
    ):
        current_assets_present: list[str] = []
        for asset in contract["assets"]:
            if not isinstance(asset, dict) or asset.get("strategy") == "retirement":
                continue
            target = _inside(root, str(asset["target"]), f"asset {asset['id']} target")
            if not target.is_file() or _is_reparse(target):
                continue
            source_path = _inside(template, str(asset["source"]), f"asset {asset['id']} source")
            desired = _render_source(source_path.read_bytes(), asset, root)
            if _target_hash(target.read_bytes(), asset, root) == _target_hash(desired, asset, root):
                current_assets_present.append(str(asset["target"]))
        if current_assets_present:
            recovery_targets = sorted(
                set(structural_gap_targets) | set(existing_rule_seed_targets)
            )
            gaps.append(Gap(
                "codex.partial-upgrade-advisory",
                str(contract["stamp"]),
                "suspected partial prior upgrade; version stamp is blocked and no Git recovery was attempted; "
                "compare these targets with a trusted pre-upgrade snapshot and restore if needed: "
                + ", ".join(recovery_targets),
            ))
    memory_actions, memory_gaps = _plan_memory_schema(root, template)
    actions.extend(memory_actions)
    gaps.extend(memory_gaps)
    project_requirements = _project_requirement_items(root, contract, actions)
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
        project_requirements=project_requirements,
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
    descriptor, raw = tempfile.mkstemp(prefix=".bridgeforge-codex-sync-", dir=staging_root)
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
    changed_targets: tuple[str, ...] = (),
) -> dict[str, float]:
    memory_lint = template_root / "templates" / "hooks" / "memory_lint.py"
    health = template_root / "templates" / "hooks" / "config_health_check.py"
    validators = (
        (
            memory_lint,
            [
                sys.executable,
                str(memory_lint),
                "--organize",
                "--project-root",
                str(project_root),
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
    if changed_targets and (project_root / ".git").exists():
        head_probe = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        if head_probe.returncode == 0:
            label, result, elapsed_ms = run_validator(
                ["git", "diff", "--check", "HEAD", "--", *changed_targets],
                "managed git diff check",
            )
            timings["git_diff_check"] = round(elapsed_ms, 1)
            if result.returncode != 0:
                detail = (result.stdout + result.stderr).strip()
                raise SyncBlocked(
                    f"{label} failed with exit {result.returncode}: {detail}"
                )
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


def _validate_changed_markdown(
    project_root: Path,
    template_root: Path,
    contract: dict[str, Any],
    changed_targets: set[str],
) -> None:
    assets = {
        str(asset["target"]): asset
        for asset in contract["assets"]
        if isinstance(asset, dict) and isinstance(asset.get("target"), str)
    }
    for relative in sorted(changed_targets):
        if not relative.casefold().endswith(".md"):
            continue
        target = _inside(project_root, relative, "Markdown validation target")
        if not target.exists():
            continue
        payload = target.read_bytes()
        # Empty configuration still performs the fail-closed fence scan.
        _markdown_heading_sections(payload, ())
        asset = assets.get(relative)
        zones = asset.get("agents_zones") if isinstance(asset, dict) else None
        if isinstance(zones, dict):
            _prefix, public_block, _between, project_block, _suffix = (
                _agents_zone_parts(payload, zones)
            )
            _agents_project_sections(project_block, zones)
            public_hash = _agents_public_zone_hash(public_block, asset, project_root)
            if public_hash != str(zones["public"]["current_sha256"]):
                raise SyncBlocked(
                    f"managed AGENTS public zone is not current after apply: {relative}"
                )
        layout = asset.get("section_layout") if isinstance(asset, dict) else None
        if isinstance(layout, dict) and not isinstance(zones, dict):
            canonical: list[str] = []
            legacy: list[str] = []
            for group in layout["groups"]:
                canonical.append(str(group["heading"]))
                entries = group.get("sections")
                if isinstance(entries, list):
                    canonical.extend(str(item["heading"]) for item in entries)
                else:
                    entries = [group]
                for entry in entries:
                    legacy.extend(
                        str(item) for item in entry.get("legacy_headings", [])
                    )
            legacy.extend(
                str(item)
                for entry in layout.get("retired_sections", [])
                for item in entry.get("legacy_headings", [])
            )
            canonical_sections = _markdown_heading_sections(payload, tuple(canonical))
            missing_layout = [item for item in canonical if item not in canonical_sections]
            if missing_layout:
                raise SyncBlocked(
                    f"migrated Markdown layout is incomplete: {relative} :: "
                    + ", ".join(missing_layout)
                )
            legacy_sections = _markdown_heading_sections(payload, tuple(legacy))
            if legacy_sections:
                raise SyncBlocked(
                    f"migrated Markdown still contains legacy headings: {relative} :: "
                    + ", ".join(legacy_sections)
                )
            if [
                heading
                for heading, _span in sorted(
                    canonical_sections.items(), key=lambda item: item[1][0]
                )
            ] != canonical:
                raise SyncBlocked(
                    f"migrated Markdown layout is out of source order: {relative}"
                )
        managed = asset.get("managed_blocks") if isinstance(asset, dict) else None
        if not isinstance(managed, dict):
            continue
        headings = tuple(str(item) for item in managed.get("headings", []))
        additive = tuple(str(item) for item in managed.get("additive_headings", []))
        keyed = tuple(
            str(item["heading"])
            for item in managed.get("keyed_tables", [])
        )
        registered = headings + additive + keyed
        target_sections = _markdown_heading_sections(payload, registered)
        source_path = _inside(
            template_root,
            str(asset["source"]),
            f"asset {asset['id']} Markdown validation source",
        )
        source_payload = _render_source(source_path.read_bytes(), asset, project_root)
        source_sections = _markdown_heading_sections(source_payload, registered)
        expected_order = [
            heading
            for heading, _span in sorted(
                source_sections.items(),
                key=lambda item: item[1][0],
            )
            if heading in target_sections
        ]
        actual_order = [
            heading
            for heading, _span in sorted(
                target_sections.items(),
                key=lambda item: item[1][0],
            )
        ]
        if actual_order != expected_order:
            raise SyncBlocked(
                f"managed Markdown headings are out of explicit source order: {relative}"
            )
        for table in managed.get("keyed_tables", []):
            heading = str(table["heading"])
            if heading in target_sections:
                _parse_keyed_table(payload, heading)


def _seed_snapshots(
    project_root: Path,
    contract: dict[str, Any],
) -> dict[Path, bytes]:
    snapshots: dict[Path, bytes] = {}
    for asset in contract["assets"]:
        if not isinstance(asset, dict) or asset.get("strategy") != "seed":
            continue
        target = _inside(
            project_root,
            str(asset["target"]),
            f"seed asset {asset['id']}",
        )
        if target.is_file() and not _is_reparse(target):
            snapshots[target] = target.read_bytes()
    return snapshots


def _verify_seed_snapshots(snapshots: dict[Path, bytes]) -> None:
    changed = [str(path) for path, payload in snapshots.items() if not path.is_file() or path.read_bytes() != payload]
    if changed:
        raise SyncBlocked(
            "project-owned seed changed during update: " + ", ".join(changed)
        )


def _materialize_selected_actions(
    project_root: Path,
    entries: list[CatalogEntry],
    *,
    base_payloads: dict[tuple[str, str], bytes] | None = None,
) -> list[Action]:
    base_payloads = base_payloads or {}
    materialized = [
        action
        for _item_id, action, block in entries
        if block is None
    ]
    grouped: dict[tuple[str, str], tuple[Action, list[str]]] = {}
    for _item_id, action, block in entries:
        if block is None:
            continue
        key = (action.asset_id, action.target)
        if key not in grouped:
            grouped[key] = (action, [])
        grouped[key][1].append(block)
    for key in sorted(grouped):
        action, selected_blocks = grouped[key]
        if action.payload is None:
            raise SyncBlocked(f"absorption action {action.asset_id} has no payload")
        target = _inside(
            project_root,
            action.target,
            f"absorption target {action.asset_id}",
        )
        before = base_payloads.get(key, target.read_bytes())
        details = {
            label: (mode, heading, managed_key)
            for label, mode, heading, managed_key in action.managed_item_details
        }
        replace_headings = tuple(
            block
            for block in selected_blocks
            if block not in details
        )
        desired_source = action.source_payload or action.payload
        after = _replace_heading_items(before, desired_source, replace_headings)
        selected_by_heading: dict[str, set[str]] = {}
        for block in selected_blocks:
            detail = details.get(block)
            if detail is None:
                continue
            mode, heading, managed_key = detail
            if mode != "keyed_table":
                raise SyncBlocked(f"unsupported managed item mode: {mode}")
            selected_by_heading.setdefault(heading, set()).add(
                _markdown_table_key(managed_key)
            )
        for heading, managed_keys in action.keyed_table_contracts:
            selected_keys = selected_by_heading.get(heading)
            if not selected_keys:
                continue
            after, _missing, _conflicts = _merge_keyed_table(
                after,
                desired_source,
                heading=heading,
                managed_keys=managed_keys,
                selected_keys=selected_keys,
            )
        materialized.append(
            replace(
                action,
                after_sha256=_sha256_bytes(after),
                managed_blocks=tuple(selected_blocks),
                managed_item_details=tuple(
                    detail
                    for detail in action.managed_item_details
                    if detail[0] in selected_blocks
                ),
                payload=after,
            )
        )
    return materialized


def apply_plan(
    planned: Plan,
    *,
    plan_fingerprint: str,
    confirmed_risk: bool = False,
    decline_risk: bool = False,
    selected_risk_ids: tuple[str, ...] | None = None,
    custom_absorption_directives: tuple[str, ...] = (),
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
        custom_absorption_directives=custom_absorption_directives,
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
    custom_absorption_directives: tuple[str, ...] = (),
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
    if custom_absorption_directives and selected_risk_ids is None:
        raise SyncBlocked(
            "custom absorption directives require the single partial selection decision"
        )
    selected_executable, declined_executable = _select_risk_actions(
        rebuilt,
        confirmed_risk=confirmed_risk,
        decline_risk=decline_risk,
        selected_risk_ids=selected_risk_ids,
    )
    selected_executable, declined_executable, custom_decisions = (
        _apply_custom_absorption_directives(
            selected_executable,
            declined_executable,
            custom_absorption_directives,
        )
    )
    selected_risks = [
        item for item in selected_executable if item[1].classification == "risk"
    ]
    selected_absorptions = [
        item for item in selected_executable if item[1].classification == "absorb"
    ]
    declined_risks = [
        item for item in declined_executable if item[1].classification == "risk"
    ]
    declined_absorptions = [
        item for item in declined_executable if item[1].classification == "absorb"
    ]
    root = Path(rebuilt.project_root)
    safe_payloads = {
        (action.asset_id, action.target): action.payload
        for action in rebuilt.safe_actions
        if action.payload is not None
    }
    materialized = _materialize_selected_actions(
        root,
        selected_executable,
        base_payloads=safe_payloads,
    )
    materialized_targets = {
        (action.asset_id, action.target)
        for action in materialized
    }
    selected = [
        action
        for action in rebuilt.safe_actions
        if (action.asset_id, action.target) not in materialized_targets
    ]
    selected.extend(materialized)
    selected_action_ids = tuple(item_id for item_id, _action, _block in selected_executable)
    selected_absorption_ids = tuple(
        item_id for item_id, _action, _block in selected_absorptions
    )
    risk_declined = tuple(
        action.asset_id for _item_id, action, _block in declined_risks
    )
    absorption_declined = tuple(
        item_id for item_id, _action, _block in declined_absorptions
    )

    contract, _contract_path = load_contract(Path(rebuilt.template_root))
    stamp = _inside(root, str(contract["stamp"]), "version stamp")
    seed_before = _seed_snapshots(root, contract)
    transaction = _Transaction(root)
    stamp_written = False
    try:
        action_started = time.perf_counter()
        if checkpoint:
            checkpoint("before-apply")
        memory_actions = [item for item in selected if item.action == "memory-organize"]
        if memory_actions:
            transaction.snapshot_tree(root / ".codex" / "memory")
        stamp_migrations = [
            item for item in selected if item.action == "migrate-stamp"
        ]
        for action in selected:
            if action.action == "migrate-stamp":
                continue
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
        _verify_actions(
            root,
            [item for item in selected if item.action != "migrate-stamp"],
        )
        changed_targets = {
            action.target
            for action in selected
            if action.action not in {"memory-organize", "migrate-stamp"}
        }
        _validate_changed_markdown(
            root,
            Path(rebuilt.template_root),
            contract,
            changed_targets,
        )
        _verify_seed_snapshots(seed_before)
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
            changed_targets=tuple(sorted(changed_targets)),
        ))
        timings["validation_wall"] = round(
            (time.perf_counter() - validation_started) * 1000,
            1,
        )
        if checkpoint:
            checkpoint("before-stamp")
        _verify_seed_snapshots(seed_before)
        expected_stamp = (rebuilt.current_version + "\n").encode("utf-8")
        if (
            not rebuilt.gaps
            and not declined_executable
            and (not stamp.is_file() or stamp.read_bytes() != expected_stamp)
        ):
            if stamp_migrations:
                transaction.delete(_inside(root, LEGACY_STAMP, "legacy version stamp"))
            transaction.write(stamp, expected_stamp)
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
    receipt_gaps.extend(
        {
            "asset_id": action.asset_id,
            "target": action.target,
            "reason": (
                "upstream absorption declined; local managed block preserved: "
                + str(block)
            ),
        }
        for _item_id, action, block in declined_absorptions
    )
    remaining_required = _project_requirement_items(root, contract)
    remaining_required.extend([
        _action_item(item_id, action, block)
        for item_id, action, block in declined_executable
    ])
    manual_steps = _manual_items(rebuilt.gaps)
    action_required_items = _action_required_items(rebuilt.gaps)
    blockers: list[dict[str, Any]] = []
    optional_actions: list[dict[str, Any]] = []
    target_readiness = _target_readiness(
        required_actions=remaining_required,
        optional_actions=optional_actions,
        manual_steps=manual_steps,
        blockers=blockers,
    )
    catalog = _executable_catalog(rebuilt)
    selected_absorption_id_set = set(selected_absorption_ids)
    conflict_file_items = tuple(
        _action_item(item_id, action, block)
        for item_id, action, block in _absorption_catalog(rebuilt)
    )
    managed_block_effects = tuple(
        _managed_block_effect(
            item_id,
            action,
            block,
            selected=item_id in selected_absorption_id_set,
            custom_decision=custom_decisions.get(item_id),
        )
        for item_id, action, block in _absorption_catalog(rebuilt)
    )
    degraded = bool(receipt_gaps)
    timings["total"] = round((time.perf_counter() - apply_started) * 1000, 1)
    return Receipt(
        status="completed_with_gaps" if degraded else "completed",
        readiness="degraded" if degraded else "ready",
        execution_status="completed",
        target_readiness=target_readiness,
        project_readiness=(
            "needs_user_action"
            if _project_needs_user_action(remaining_required)
            else "ready"
        ),
        mode=rebuilt.mode,
        previous_version=rebuilt.previous_version,
        current_version=rebuilt.current_version,
        aggregate_fingerprint=rebuilt.aggregate_fingerprint,
        safe_applied=tuple(item.asset_id for item in rebuilt.safe_actions),
        risk_applied=tuple(
            action.asset_id for _item_id, action, _block in selected_risks
        ),
        risk_declined=risk_declined,
        upstream_absorption_applied=tuple(dict.fromkeys(
            action.asset_id for _item_id, action, _block in selected_absorptions
        )),
        upstream_absorption_declined=absorption_declined,
        selected_absorption_ids=selected_absorption_ids,
        selected_action_ids=selected_action_ids,
        selection_fingerprint=(
            _selection_fingerprint(
                rebuilt,
                selected_action_ids,
                custom_absorption_directives,
            )
            if catalog
            else None
        ),
        custom_absorption_directives=custom_absorption_directives,
        conflict_file_items=conflict_file_items,
        managed_block_effects=managed_block_effects,
        required_actions=tuple(remaining_required),
        optional_actions=tuple(optional_actions),
        manual_steps=tuple(manual_steps),
        action_required_items=tuple(action_required_items),
        blockers=tuple(blockers),
        recommended_selection=tuple(
            item_id for item_id, _action, _block in catalog
        ),
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
    catalog = _executable_catalog(plan)
    required_actions = list(plan.project_requirements)
    required_actions.extend([
        _action_item(item_id, action, block)
        for item_id, action, block in catalog
    ])
    upstream_absorption_actions = [
        _action_item(item_id, action, block)
        for item_id, action, block in _absorption_catalog(plan)
    ]
    conflict_groups: dict[str, list[dict[str, Any]]] = {}
    for item in upstream_absorption_actions:
        block = item["managed_blocks"][0]
        conflict_groups.setdefault(item["target"], []).append({
            "id": item["id"],
            "managed_block": block,
            "merge_mode": item["merge_mode"],
            "managed_key": item["managed_key"],
            "upstream_effect": (
                "replace only this same-key managed table row with current upstream"
                if item["merge_mode"] == "keyed_table"
                else "replace this managed block with current upstream bytes"
            ),
            "local_impact": item["local_impact"],
            "recoverability": item["recoverability"],
        })
    selected_ids = [item_id for item_id, _action, _block in catalog]
    optional_actions: list[dict[str, Any]] = []
    manual_steps = _manual_items(plan.gaps)
    action_required_items = _action_required_items(plan.gaps)
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
        "project_readiness": (
            "needs_user_action"
            if _project_needs_user_action(plan.project_requirements)
            else "ready"
        ),
        "mode": plan.mode,
        "previous_version": plan.previous_version,
        "current_version": plan.current_version,
        "safe": [
            {
                key: value
                for key, value in asdict(item).items()
                if key not in {"payload", "source_payload"}
            }
            for item in plan.safe_actions
        ],
        "risk": [
            {
                key: value
                for key, value in asdict(item).items()
                if key not in {"payload", "source_payload"}
            }
            for item in plan.risk_actions
        ],
        "upstream_absorption": [
            {
                key: value
                for key, value in asdict(item).items()
                if key not in {"payload", "source_payload"}
            }
            for item in plan.absorption_actions
        ],
        "gaps": [asdict(item) for item in plan.gaps],
        "blockers": plan.blockers,
        "required_actions": required_actions,
        "upstream_absorption_actions": upstream_absorption_actions,
        "conflict_file_items": [
            {
                "id": item["id"],
                "target": item["target"],
                "managed_blocks": item["managed_blocks"],
                "merge_mode": item["merge_mode"],
                "managed_key": item["managed_key"],
                "local_impact": item["local_impact"],
                "recoverability": item["recoverability"],
            }
            for item in upstream_absorption_actions
        ],
        "conflict_file_groups": [
            {"target": target, "items": items}
            for target, items in conflict_groups.items()
        ],
        "optional_actions": optional_actions,
        "manual_steps": manual_steps,
        "action_required_items": action_required_items,
        "blocker_items": blockers,
        "recommended_selection": selected_ids,
        "confirmation": (
            {
                "business_confirmation_count": "one",
                "warning": (
                    "A 为激进模式（aggressive）：只吸收逐项列明的可信冲突；普通 Markdown "
                    "标题的本地内容不会因 A 被覆盖；keyed table 只覆盖同键冲突行，下游独有行"
                    "会保留；事务失败会回滚。"
                ),
                "all": selected_ids,
                "partial_syntax": "B: R1,U2; U3 only absorb the named managed block",
                "decline": "C",
                "options": [
                    {
                        "id": "A",
                        "text": "A. 激进更新：执行全部 safe/R/C/U，并默认吸收全部 U 项",
                    },
                    {
                        "id": "B",
                        "text": (
                            "B. 温和更新：执行全部 safe；只执行本回复选中的 R/C/U，"
                            "并接受逐 U 的 absorb/preserve 指令"
                        ),
                    },
                    {
                        "id": "C",
                        "text": (
                            "C. 保守更新：执行全部 safe；不执行任何 R/C/U，"
                            "冲突区块保持原样"
                        ),
                    },
                ],
                "rendering_contract": {
                    "options_must_be_verbatim": True,
                    "must_expand_every_conflict": True,
                    "path_must_be_full_project_relative": True,
                    "required_conflict_fields": [
                        "id",
                        "target",
                        "managed_block",
                        "upstream_effect",
                        "local_impact",
                        "recoverability",
                    ],
                },
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
        "--selected-action",
        action="append",
        dest="selected_risk_ids",
        metavar="ID",
        help="repeat a displayed Rn/Un ID for the single partial-confirmation decision",
    )
    risk.add_argument("--decline-risk", action="store_true")
    parser.add_argument(
        "--custom-absorption-directive",
        action="append",
        default=[],
        help="preserve the user's same-reply B directive in the transaction receipt",
    )
    args = parser.parse_args(argv)

    if sys.version_info < MIN_PYTHON:
        print("BLOCKED: bridgeforge_codex_project_sync requires Python 3.11+", file=sys.stderr)
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
            custom_absorption_directives=tuple(args.custom_absorption_directive),
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
