#!/usr/bin/env python3
"""Plan and apply one current-only Codex skeleton transaction."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable


HASH_RE = re.compile(r"sha256:[0-9a-f]{64}")
SEMVER_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
PROJECT_NAME_CLONE_RE = re.compile(
    br"(?m)^(git clone <repo_url> )"
    br"([A-Za-z0-9._-]+|\{\{PROJECT_NAME\}\})"
    br"( && cd )\2([ \t]*)$"
)
PROJECT_HOOK_PATH_RE = re.compile(
    rb"\.codex/(?:hooks|scripts)/[A-Za-z0-9_./-]+\.py"
)


class SyncBlocked(RuntimeError):
    """The transaction cannot safely continue."""


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SyncBlocked(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _loads_json(text: str) -> Any:
    return json.loads(text, object_pairs_hook=_unique_json_object)


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

@dataclass(frozen=True)
class Receipt:
    status: str
    readiness: str
    execution_status: str
    mode: str
    previous_version: str | None
    current_version: str
    aggregate_fingerprint: str
    applied: tuple[str, ...]
    preserved_project_asset_ids: tuple[str, ...]
    stamp_written_last: bool
    rollback_performed: bool
    timings_ms: dict[str, float]


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
        normalized = PROJECT_NAME_CLONE_RE.sub(
            br"\1{{PROJECT_NAME}}\3{{PROJECT_NAME}}\4",
            _git_blob_bytes(payload),
        ).decode("utf-8-sig")
    except UnicodeDecodeError:
        return _sha256_bytes(payload)
    for suffix in ("文档索引", "开发备忘"):
        normalized = re.sub(
            rf"(?m)^# {re.escape(project_root.name)} {suffix}$",
            f"# {{{{PROJECT_NAME}}}} {suffix}",
            normalized,
        )
    return _sha256_bytes(normalized.encode("utf-8"))


def load_contract(template_root: Path) -> tuple[dict[str, Any], Path]:
    contract_path = template_root / "templates" / "managed-skeleton.json"
    checker = _trusted_current_baseline_module(template_root)
    try:
        contract = checker.load_contract(contract_path)
    except Exception as exc:
        raise SyncBlocked(f"cannot read current-only Codex asset contract: {exc}") from exc
    release = str(contract.get("release_version", ""))
    if _semver(release, "contract release version") < (1, 4, 28):
        raise SyncBlocked("current-only contract must start at 1.4.28")
    for asset in contract["assets"]:
        source = _inside(
            template_root,
            str(asset["source"]),
            f"asset {asset['id']} source",
        )
        if not source.is_file() or _is_reparse(source):
            raise SyncBlocked(f"asset {asset['id']} source is missing or unsafe")
        if _sha256_path(source) != asset["current_sha256"]:
            raise SyncBlocked(f"asset {asset['id']} current source hash is stale")
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
            safe_after, _missing, conflicts = _merge_keyed_table(
                safe_after,
                desired,
                heading=heading,
                managed_keys=managed_keys,
                selected_keys=set(),
            )
            all_after, _all_missing, _all_conflicts = _merge_keyed_table(
                all_after,
                desired,
                heading=heading,
                managed_keys=managed_keys,
                selected_keys=set(conflicts),
            )
            del conflicts
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
    if all_after != before:
        actions.append(_action(
            asset,
            target,
            "advance-current-managed-markdown",
            "safe",
            "advance the verified managed Markdown projection to the current baseline",
            before,
            all_after,
            project_root,
            keyed_table_contracts=keyed_contracts,
            local_impact="project-owned headings and table rows are preserved",
        ))
    return actions, ordinary_gaps


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


OBSOLETE_STAMP = ".codex/.bridgeforge_version"
CURRENT_STAMP = ".codex/.bridgeforge_codex_version"
CURRENT_BASELINE = (1, 4, 28)


def _detect_mode(project_root: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    if (
        (project_root / CURRENT_STAMP).is_file()
        or (project_root / OBSOLETE_STAMP).is_file()
    ):
        return "update"
    if (project_root / ".codex").is_dir() or (project_root / "AGENTS.md").is_file():
        return "adopt"
    return "init"


def _trusted_current_baseline_module(template_root: Path) -> Any:
    path = template_root / "templates" / "scripts" / "current_baseline.py"
    if not path.is_file():
        raise SyncBlocked(f"current baseline checker is missing: {path}")
    module_name = "_bridgeforge_codex_current_baseline"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise SyncBlocked("current baseline checker cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise SyncBlocked(f"current baseline checker cannot be loaded: {exc}") from exc
    finally:
        sys.dont_write_bytecode = previous
    return module


def _marker_block(payload: bytes, begin: str, end: str) -> tuple[int, int, bytes]:
    normalized = _git_blob_bytes(payload)
    lines = normalized.splitlines(keepends=True)
    begin_bytes = begin.encode("utf-8")
    end_bytes = end.encode("utf-8")
    starts = [index for index, line in enumerate(lines) if line.rstrip(b"\n") == begin_bytes]
    stops = [index for index, line in enumerate(lines) if line.rstrip(b"\n") == end_bytes]
    if len(starts) != 1 or len(stops) != 1 or starts[0] >= stops[0]:
        raise SyncBlocked(f"managed markers are missing or duplicated: {begin} / {end}")
    start = sum(len(line) for line in lines[: starts[0]])
    stop = sum(len(line) for line in lines[: stops[0] + 1])
    return start, stop, normalized[start:stop]


def _merge_agents_current(
    source: bytes,
    current: bytes | None,
    asset: dict[str, Any],
    project_root: Path,
) -> bytes:
    canonical = _render_source(source, asset, project_root)
    if current is None:
        return canonical
    zones = asset["agents_zones"]
    project = zones["project"]
    canonical_start, canonical_stop, _canonical_project = _marker_block(
        canonical,
        str(project["begin"]),
        str(project["end"]),
    )
    _current_start, _current_stop, project_block = _marker_block(
        current,
        str(project["begin"]),
        str(project["end"]),
    )
    return canonical[:canonical_start] + project_block + canonical[canonical_stop:]


def _deep_merge_current(current: Any, canonical: Any) -> Any:
    if isinstance(current, dict) and isinstance(canonical, dict):
        result = copy.deepcopy(current)
        for key, value in canonical.items():
            result[key] = _deep_merge_current(result.get(key), value)
        return result
    return copy.deepcopy(canonical)


def _merge_hooks_current(source: bytes, current: bytes | None) -> bytes:
    canonical = _loads_json(source.decode("utf-8-sig"))
    if current is None:
        return json.dumps(canonical, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    try:
        local = _loads_json(current.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyncBlocked(f"project hooks.json is invalid: {exc}") from exc
    if not isinstance(local, dict) or not isinstance(local.get("hooks"), dict):
        raise SyncBlocked("project hooks.json has no hooks object")
    external: dict[str, list[dict[str, Any]]] = {}
    for event, entries in local["hooks"].items():
        if not isinstance(entries, list):
            raise SyncBlocked(f"project hooks event is invalid: {event}")
        kept: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                raise SyncBlocked(f"project hooks group is invalid: {event}")
            handlers = [
                handler
                for handler in entry["hooks"]
                if not (
                    isinstance(handler, dict)
                    and isinstance(handler.get("bridgeforgeCodexId"), str)
                    and handler["bridgeforgeCodexId"].startswith(
                        "bridgeforge-codex.project-hook.v1:"
                    )
                )
            ]
            if handlers:
                kept.append({**entry, "hooks": handlers})
        if kept:
            external[str(event)] = kept
    result = copy.deepcopy(canonical)
    for event, entries in external.items():
        result.setdefault("hooks", {}).setdefault(event, []).extend(entries)
    return json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def _replace_region(source: bytes, current: bytes | None, region: dict[str, Any]) -> bytes:
    if current is None:
        return _git_blob_bytes(source)
    begin = str(region["begin"])
    end = str(region["end"])
    source_start, source_stop, source_block = _marker_block(source, begin, end)
    del source_start, source_stop
    current_start, current_stop, _current_block = _marker_block(current, begin, end)
    normalized = _git_blob_bytes(current)
    return normalized[:current_start] + source_block + normalized[current_stop:]


def _preserve_selected_region(
    source: bytes,
    current: bytes,
    region: dict[str, Any],
) -> bytes:
    canonical = _git_blob_bytes(source)
    source_start, source_stop, _source_block = _marker_block(
        canonical,
        str(region["begin"]),
        str(region["end"]),
    )
    _current_start, _current_stop, current_block = _marker_block(
        current,
        str(region["begin"]),
        str(region["end"]),
    )
    return canonical[:source_start] + current_block + canonical[source_stop:]


def _desired_payload(
    asset: dict[str, Any],
    source: bytes,
    current: bytes | None,
    project_root: Path,
) -> bytes | None:
    strategy = str(asset["strategy"])
    if strategy == "seed" and current is not None:
        return current
    if asset.get("agents_zones") is not None:
        return _merge_agents_current(source, current, asset, project_root)
    if isinstance(asset.get("managed_blocks"), dict) and current is not None:
        target = _inside(
            project_root,
            str(asset["target"]),
            "managed Markdown target",
        )
        actions, gaps = _plan_managed_markdown_blocks(
            asset,
            source,
            current,
            target,
            project_root,
        )
        if gaps:
            raise SyncBlocked(gaps[0].reason)
        if not actions or actions[0].payload is None:
            return current
        candidate = actions[0].payload
        return current if _git_blob_bytes(candidate) == _git_blob_bytes(current) else candidate
    if strategy == "merge":
        if asset.get("merge_policy") == "codex-hooks":
            return _merge_hooks_current(source, current)
        canonical = _loads_json(source.decode("utf-8-sig"))
        local = _loads_json(current.decode("utf-8-sig")) if current is not None else {}
        return json.dumps(
            _deep_merge_current(local, canonical),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8") + b"\n"
    if strategy == "region":
        return _replace_region(source, current, asset["region"])
    return _render_source(source, asset, project_root)


def _project_asset_candidates(
    root: Path,
    agents_asset: dict[str, Any],
    desired_targets: set[str],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    dependency_paths: set[str] = set()
    agents = root / "AGENTS.md"
    if agents.is_file():
        try:
            _start, _stop, block = _marker_block(
                agents.read_bytes(),
                str(agents_asset["agents_zones"]["project"]["begin"]),
                str(agents_asset["agents_zones"]["project"]["end"]),
            )
            candidates.append({
                "id": "W:agents-project-zone",
                "kind": "agents-project-zone",
                "target": "AGENTS.md",
                "sha256": _sha256_bytes(block),
                "recommended": "preserve",
            })
        except SyncBlocked:
            candidates.append({
                "id": "W:agents-project-zone",
                "kind": "agents-project-zone",
                "target": "AGENTS.md",
                "recommended": "manual-review",
                "affects_readiness": True,
            })
    hooks_json = root / ".codex" / "hooks.json"
    if hooks_json.is_file():
        canonical = _merge_hooks_current(b'{"hooks": {}}', hooks_json.read_bytes())
        external = json.loads(canonical.decode("utf-8"))["hooks"]
        if external:
            external_payload = _canonical_json(external)
            dependencies = sorted(
                match.decode("utf-8")
                for match in PROJECT_HOOK_PATH_RE.findall(external_payload)
            )
            dependency_paths.update(dependencies)
            candidates.append({
                "id": "W:hook-registration:.codex/hooks.json",
                "kind": "hook-registration",
                "target": ".codex/hooks.json",
                "sha256": _sha256_bytes(external_payload),
                "dependencies": dependencies,
                "recommended": "preserve",
            })
    precommit = root / ".githooks" / "pre-commit"
    if precommit.is_file():
        extension = {
            "begin": "# >>> PROJECT_EXTENSION_BEGIN",
            "end": "# <<< PROJECT_EXTENSION_END",
        }
        try:
            _start, _stop, block = _marker_block(
                precommit.read_bytes(), extension["begin"], extension["end"]
            )
        except SyncBlocked:
            pass
        else:
            if block not in {
                b"# >>> PROJECT_EXTENSION_BEGIN\n# <<< PROJECT_EXTENSION_END\n",
                b"# >>> PROJECT_EXTENSION_BEGIN\n# <<< PROJECT_EXTENSION_END",
            }:
                dependencies = sorted(
                    match.decode("utf-8")
                    for match in PROJECT_HOOK_PATH_RE.findall(block)
                )
                dependency_paths.update(dependencies)
                candidates.append({
                    "id": "W:hook-extension:.githooks/pre-commit",
                    "kind": "hook-extension",
                    "target": ".githooks/pre-commit",
                    "sha256": _sha256_bytes(block),
                    "dependencies": dependencies,
                    "recommended": "preserve",
                })
    for kind, folder in (("rule", root / ".codex" / "rules"), ("hook", root / ".codex" / "hooks")):
        if not folder.is_dir() or _is_reparse(folder):
            continue
        for path in sorted(item for item in folder.rglob("*") if item.is_file()):
            relative = path.relative_to(root).as_posix()
            if relative in desired_targets:
                continue
            candidates.append({
                "id": f"W:{kind}:{relative}",
                "kind": kind,
                "target": relative,
                "sha256": _sha256_path(path),
                "recommended": "preserve" if kind == "hook" else "review",
            })
    existing_targets = {str(item["target"]) for item in candidates}
    for relative in sorted(dependency_paths - desired_targets - existing_targets):
        path = _inside(root, relative, "project hook dependency")
        if path.is_file() and not _is_reparse(path):
            candidates.append({
                "id": f"W:hook-dependency:{relative}",
                "kind": "hook-dependency",
                "target": relative,
                "sha256": _sha256_path(path),
                "recommended": "preserve",
            })
    return candidates


def _validate_preserved_knowledge(root: Path, template_root: Path) -> None:
    memory = root / ".codex" / "memory"
    lint = root / ".codex" / "hooks" / "memory_lint.py"
    if memory.is_dir() and lint.is_file():
        result = subprocess.run(
            [
                sys.executable,
                str(lint),
                "--organize",
                "--project-root",
                str(root),
            ],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if result.returncode not in {0}:
            raise SyncBlocked(
                "project memory compatibility check failed: "
                + (result.stderr or result.stdout).strip()
            )
    skills = root / ".codex" / "skills"
    if skills.is_dir() and not _is_reparse(skills):
        validator_path = template_root / "templates" / "hooks" / "skill_metadata_check.py"
        module_name = "_bridgeforge_codex_project_skill_metadata"
        spec = importlib.util.spec_from_file_location(module_name, validator_path)
        if spec is None or spec.loader is None:
            raise SyncBlocked("trusted project Skill validator cannot be loaded")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
            issues, _warnings = module.validate_skill_tree(skills)
        except Exception as exc:
            raise SyncBlocked(f"project Skill compatibility check failed: {exc}") from exc
        finally:
            sys.modules.pop(module_name, None)
        if issues:
            raise SyncBlocked(
                "project Skill compatibility check failed: " + "; ".join(issues)
            )


def _trusted_project_runtime_module(template_root: Path) -> Any:
    path = template_root / "templates" / "scripts" / "project_runtime.py"
    if not path.is_file():
        raise SyncBlocked(f"trusted project runtime validator is missing: {path}")
    module_name = "_bridgeforge_codex_trusted_project_runtime"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise SyncBlocked(f"trusted project runtime validator cannot be loaded: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    previous_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise SyncBlocked(
            f"trusted project runtime validator cannot be loaded: {exc}"
        ) from exc
    finally:
        sys.dont_write_bytecode = previous_dont_write_bytecode
    return module


def build_plan(project_root: Path, template_root: Path, mode: str = "auto") -> Plan:
    root = _plain_root(project_root, "project root")
    template = _plain_root(template_root, "template root")
    contract, contract_path = load_contract(template)
    selected_mode = _detect_mode(root, mode)
    current_version = (template / "VERSION").read_text(
        encoding="utf-8-sig"
    ).strip()
    if current_version != contract["release_version"]:
        raise SyncBlocked(
            "bridgeforge-codex VERSION does not match current-only contract"
        )
    stamp = _inside(root, CURRENT_STAMP, "version stamp")
    old_stamp = _inside(root, OBSOLETE_STAMP, "obsolete version stamp")
    blockers: list[str] = []
    previous_version: str | None = None
    force_rebuild = False
    if selected_mode == "init" and (
        (root / ".codex").exists()
        or (root / "AGENTS.md").exists()
        or (root / ".githooks" / "pre-commit").exists()
    ):
        blockers.append(
            "init requires a project with no existing skeleton identity; zero writes performed"
        )
    if stamp.exists() and old_stamp.exists():
        blockers.append(
            "both current and obsolete version stamps exist; zero writes performed"
        )
    elif old_stamp.is_file():
        previous_version = old_stamp.read_text(encoding="utf-8-sig").strip()
        force_rebuild = True
    elif stamp.is_file():
        previous_version = stamp.read_text(encoding="utf-8-sig").strip()
    elif selected_mode != "init":
        blockers.append(
            "existing project has no recognized version stamp; zero writes performed"
        )
    previous_semver: tuple[int, int, int] | None = None
    if previous_version is not None:
        try:
            previous_semver = _semver(
                previous_version,
                "project bridgeforge-codex version",
            )
        except SyncBlocked as exc:
            blockers.append(str(exc))
    rebuild = force_rebuild or (
        previous_semver is not None and previous_semver < CURRENT_BASELINE
    )
    if previous_semver is not None and previous_semver > _semver(
        current_version,
        "current bridgeforge-codex version",
    ):
        blockers.append(
            f"project version {previous_version} is newer than {current_version}"
        )
    if previous_semver is not None and not rebuild and not blockers:
        checker = _trusted_current_baseline_module(template)
        try:
            checker.verify_current_baseline(root)
        except Exception as exc:
            blockers.append(
                f"current baseline drifted; zero writes performed: {exc}"
            )
    _validate_preserved_knowledge(root, template)

    actions: list[Action] = []
    gaps: list[Gap] = []
    desired_targets: set[str] = {
        str(contract["contract_target"]),
        CURRENT_STAMP,
    }
    for asset in contract["assets"]:
        target_relative = str(asset["target"])
        desired_targets.add(target_relative)
        target = _inside(root, target_relative, f"asset {asset['id']} target")
        _assert_plain_ancestors(root, target)
        source = _inside(
            template,
            str(asset["source"]),
            f"asset {asset['id']} source",
        ).read_bytes()
        current = target.read_bytes() if target.is_file() else None
        merge_current = current if not rebuild or asset.get("strategy") == "seed" else None
        try:
            desired = _desired_payload(asset, source, merge_current, root)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SyncBlocked(f"cannot render {asset['id']}: {exc}") from exc
        if desired == current:
            continue
        actions.append(Action(
            asset_id=str(asset["id"]),
            target=target_relative,
            action="create" if current is None else "replace",
            classification="safe",
            reason=(
                "install current 1.4.28+ public asset"
                if rebuild
                else "advance verified current baseline"
            ),
            before_sha256=None if current is None else _sha256_bytes(current),
            after_sha256=None if desired is None else _sha256_bytes(desired),
            payload=desired,
        ))
    contract_target = str(contract["contract_target"])
    installed_contract = (
        json.dumps(contract, ensure_ascii=False, indent=2).encode("utf-8")
        + b"\n"
    )
    current_contract_path = _inside(
        root,
        contract_target,
        "installed current baseline",
    )
    current_contract = (
        current_contract_path.read_bytes()
        if current_contract_path.is_file()
        else None
    )
    if current_contract != installed_contract:
        actions.append(Action(
            asset_id="contract.current-baseline",
            target=contract_target,
            action="create" if current_contract is None else "replace",
            classification="safe",
            reason="seal one current-only project baseline",
            before_sha256=(
                None
                if current_contract is None
                else _sha256_bytes(current_contract)
            ),
            after_sha256=_sha256_bytes(installed_contract),
            payload=installed_contract,
        ))
    candidates: list[dict[str, Any]] = []
    if rebuild:
        agents_asset = next(
            asset
            for asset in contract["assets"]
            if asset["id"] == "root.agents"
        )
        candidates = _project_asset_candidates(root, agents_asset, desired_targets)
        codex_root = root / ".codex"
        if codex_root.is_dir() and not _is_reparse(codex_root):
            candidate_targets = {
                str(item["target"])
                for item in candidates
                if item.get("kind") in {"rule", "hook", "hook-dependency"}
            }
            for path in sorted(
                item for item in codex_root.rglob("*") if item.is_file()
            ):
                relative = path.relative_to(root).as_posix()
                if (
                    relative in desired_targets
                    or relative.startswith(".codex/memory/")
                    or relative.startswith(".codex/skills/")
                ):
                    continue
                classification = (
                    "risk" if relative in candidate_targets else "safe"
                )
                actions.append(Action(
                    asset_id=f"rebuild.remove.{relative.replace('/', '.')}",
                    target=relative,
                    action="delete",
                    classification=classification,
                    reason=(
                        "remove old skeleton content during destructive rebuild"
                    ),
                    before_sha256=_sha256_path(path),
                    after_sha256=None,
                    payload=None,
                ))
        selected_mode = "rebuild"
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
        project_requirements=candidates,
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
        path.unlink(missing_ok=True)

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


def _verify_actions(
    project_root: Path,
    actions: Iterable[Action],
    *,
    mutable_targets: set[str] | None = None,
) -> None:
    mutable = mutable_targets or set()
    for action in actions:
        target = _inside(project_root, action.target, f"receipt target {action.asset_id}")
        if action.action == "delete":
            if target.exists():
                raise SyncBlocked(f"deleted asset still exists: {action.target}")
            continue
        if action.target in mutable:
            if not target.is_file():
                raise SyncBlocked(f"project-owned seed is missing: {action.target}")
            continue
        if not target.is_file() or _sha256_path(target) != action.after_sha256:
            # Rendered assets use a normalized plan hash; exact payload is the
            # authoritative postcondition for every write.
            if action.payload is None or not target.is_file() or target.read_bytes() != action.payload:
                raise SyncBlocked(f"managed asset verification failed: {action.target}")


def _run_current_validators(project_root: Path, actions: Iterable[Action]) -> None:
    for action in actions:
        if action.action == "delete" or action.payload is None or b"\0" in action.payload:
            continue
        try:
            text = action.payload.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise SyncBlocked(f"managed text is not UTF-8: {action.target}") from exc
        for line_number, line in enumerate(text.splitlines(), start=1):
            if line.rstrip(" \t") != line:
                raise SyncBlocked(
                    f"managed text has trailing whitespace: {action.target}:{line_number}"
                )
            if line.startswith(("<<<<<<< ", "=======", ">>>>>>> ")):
                raise SyncBlocked(
                    f"managed text has a conflict marker: {action.target}:{line_number}"
                )
    health = project_root / ".codex" / "hooks" / "config_health_check.py"
    if not health.is_file():
        raise SyncBlocked("current config health validator is missing")
    result = subprocess.run(
        [sys.executable, str(health), "--strict", "--post-apply"],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if result.returncode != 0:
        raise SyncBlocked(
            "current config health validation failed: "
            + (result.stderr or result.stdout).strip()
        )


def _preserved_knowledge_snapshots(project_root: Path) -> dict[Path, bytes]:
    snapshots: dict[Path, bytes] = {}
    memory_derived = {"MEMORY.md", "MEMORY_COLD.md", "_stats.json"}
    for folder_name in ("memory", "skills"):
        folder = project_root / ".codex" / folder_name
        if not folder.is_dir() or _is_reparse(folder):
            continue
        for target in sorted(item for item in folder.rglob("*") if item.is_file()):
            if _is_reparse(target):
                raise SyncBlocked(f"project knowledge contains a linked file: {target}")
            if folder_name == "memory" and target.name in memory_derived:
                continue
            snapshots[target] = target.read_bytes()
    return snapshots


def _verify_preserved_knowledge(snapshots: dict[Path, bytes]) -> None:
    changed = [str(path) for path, payload in snapshots.items() if not path.is_file() or path.read_bytes() != payload]
    if changed:
        raise SyncBlocked(
            "project memory or Skill semantics changed during update: "
            + ", ".join(changed)
        )


def apply_plan(
    planned: Plan,
    *,
    plan_fingerprint: str,
    confirmed_risk: bool = False,
    confirmed_whitelist: bool = False,
    preserved_project_asset_ids: tuple[str, ...] = (),
    checkpoint: Callable[[str], None] | None = None,
) -> Receipt:
    started = time.perf_counter()
    replan_started = time.perf_counter()
    rebuilt = build_plan(
        Path(planned.project_root),
        Path(planned.template_root),
        planned.mode,
    )
    replan_ms = (time.perf_counter() - replan_started) * 1000
    return _apply_rebuilt_plan(
        planned,
        rebuilt,
        plan_fingerprint=plan_fingerprint,
        confirmed_risk=confirmed_risk,
        confirmed_whitelist=confirmed_whitelist,
        preserved_project_asset_ids=preserved_project_asset_ids,
        checkpoint=checkpoint,
        replan_ms=replan_ms,
        apply_started=started,
    )


def _apply_rebuilt_plan(
    planned: Plan,
    rebuilt: Plan,
    *,
    plan_fingerprint: str,
    confirmed_risk: bool = False,
    confirmed_whitelist: bool = False,
    preserved_project_asset_ids: tuple[str, ...] = (),
    checkpoint: Callable[[str], None] | None = None,
    replan_ms: float,
    apply_started: float,
) -> Receipt:
    if planned.blockers or rebuilt.blockers:
        raise SyncBlocked("plan contains blockers")
    if plan_fingerprint != planned.aggregate_fingerprint:
        raise SyncBlocked(
            "supplied aggregate fingerprint does not match the displayed plan"
        )
    if rebuilt.aggregate_fingerprint != plan_fingerprint:
        raise SyncBlocked("aggregate fingerprint drifted; zero writes performed")
    if rebuilt.gaps:
        raise SyncBlocked("plan contains unresolved gaps; zero writes performed")
    candidate_by_id = {
        str(item["id"]): item
        for item in rebuilt.project_requirements
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    preserve_ids = tuple(dict.fromkeys(preserved_project_asset_ids))
    unknown = sorted(set(preserve_ids) - set(candidate_by_id))
    if unknown:
        raise SyncBlocked(
            "unknown project asset whitelist IDs: " + ", ".join(unknown)
        )
    if rebuilt.mode == "rebuild":
        if not confirmed_whitelist:
            raise SyncBlocked(
                "destructive rebuild requires --confirmed-whitelist after independent audit"
            )
        if not confirmed_risk:
            raise SyncBlocked(
                "destructive rebuild requires the single --confirmed-risk decision"
            )
    elif confirmed_whitelist or preserve_ids:
        raise SyncBlocked("project asset whitelist is only valid for old-project rebuild")
    elif rebuilt.risk_actions:
        raise SyncBlocked("current-only update cannot contain risk actions")

    selected_targets = {
        str(candidate_by_id[item_id]["target"])
        for item_id in preserve_ids
        if candidate_by_id[item_id].get("kind")
        in {"rule", "hook", "hook-dependency"}
    }
    required_targets = {
        str(dependency)
        for item_id in preserve_ids
        for dependency in candidate_by_id[item_id].get("dependencies", [])
    }
    actions = [
        action
        for action in rebuilt.actions
        if not (
            rebuilt.mode == "rebuild"
            and action.action == "delete"
            and action.target in selected_targets
        )
    ]
    root = Path(rebuilt.project_root)
    template = Path(rebuilt.template_root)
    contract, _contract_path = load_contract(template)
    desired_targets = {str(asset["target"]) for asset in contract["assets"]}
    missing_dependencies = sorted(
        required_targets - desired_targets - selected_targets
    )
    if missing_dependencies:
        raise SyncBlocked(
            "selected project hook requires unselected dependencies: "
            + ", ".join(missing_dependencies)
        )
    asset_by_id = {str(asset["id"]): asset for asset in contract["assets"]}

    def preserve_action(asset_id: str, payload: bytes) -> None:
        for index, action in enumerate(actions):
            if action.asset_id == asset_id:
                actions[index] = replace(
                    action,
                    after_sha256=_sha256_bytes(payload),
                    payload=payload,
                )
                return
        raise SyncBlocked(f"selected project asset has no rebuild action: {asset_id}")

    if rebuilt.mode == "rebuild":
        special = {
            str(candidate_by_id[item_id].get("kind"))
            for item_id in preserve_ids
        }
        if "agents-project-zone" in special:
            asset = asset_by_id["root.agents"]
            source = _inside(template, asset["source"], "AGENTS source").read_bytes()
            current = _inside(root, asset["target"], "AGENTS target").read_bytes()
            preserve_action(
                "root.agents",
                _merge_agents_current(source, current, asset, root),
            )
        if "hook-registration" in special:
            asset = asset_by_id["codex.hooks-config"]
            source = _inside(template, asset["source"], "hooks source").read_bytes()
            current = _inside(root, asset["target"], "hooks target").read_bytes()
            preserve_action(
                "codex.hooks-config",
                _merge_hooks_current(source, current),
            )
        if "hook-extension" in special:
            asset = asset_by_id["codex.precommit"]
            source = _inside(template, asset["source"], "pre-commit source").read_bytes()
            current = _inside(root, asset["target"], "pre-commit target").read_bytes()
            preserve_action(
                "codex.precommit",
                _preserve_selected_region(
                    source,
                    current,
                    {
                        "begin": "# >>> PROJECT_EXTENSION_BEGIN",
                        "end": "# <<< PROJECT_EXTENSION_END",
                    },
                ),
            )
    seed_targets = {
        str(asset["target"])
        for asset in contract["assets"]
        if isinstance(asset, dict) and asset.get("strategy") == "seed"
    }
    knowledge_before = _preserved_knowledge_snapshots(root)
    transaction = _Transaction(root)
    memory_root = root / ".codex" / "memory"
    transaction.snapshot_tree(memory_root)
    stamp = _inside(root, CURRENT_STAMP, "version stamp")
    stamp_written = False
    rollback_performed = False
    try:
        for action in actions:
            target = _inside(root, action.target, f"action {action.asset_id}")
            if checkpoint is not None:
                checkpoint(f"before-action:{action.asset_id}")
            if action.action == "delete":
                transaction.delete(target)
            elif action.payload is not None:
                transaction.write(target, action.payload)
            else:
                raise SyncBlocked(
                    f"action has no deterministic payload: {action.asset_id}"
                )
            if checkpoint is not None:
                checkpoint(f"after-action:{action.asset_id}")
        rebuild_index = root / ".codex" / "scripts" / "memory_rebuild_index.py"
        if memory_root.is_dir() and rebuild_index.is_file():
            result = subprocess.run(
                [sys.executable, str(rebuild_index)],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            if result.returncode != 0:
                raise SyncBlocked(
                    "project memory derived-index rebuild failed: "
                    + (result.stderr or result.stdout).strip()
                )
        if checkpoint is not None:
            checkpoint("after-memory-index")
        _verify_actions(root, actions, mutable_targets=seed_targets)
        _verify_preserved_knowledge(knowledge_before)
        _run_current_validators(root, actions)
        checker = _trusted_current_baseline_module(template)
        checker.verify_current_baseline(
            root,
            expected_version=rebuilt.current_version,
            prospective_version=rebuilt.current_version,
        )
        transaction.write(
            stamp,
            (rebuilt.current_version + "\n").encode("utf-8"),
        )
        stamp_written = True
        if stamp.read_text(encoding="utf-8-sig").strip() != rebuilt.current_version:
            raise SyncBlocked("current baseline version stamp verification failed")
    except Exception as exc:
        transaction.rollback()
        rollback_performed = True
        raise SyncBlocked(
            f"transaction failed and was rolled back: {exc}"
        ) from exc
    timings = {
        "replan": round(replan_ms, 1),
        "total": round((time.perf_counter() - apply_started) * 1000, 1),
    }
    applied = tuple(action.asset_id for action in actions)
    return Receipt(
        status="completed",
        readiness="ready",
        execution_status="completed",
        mode=rebuilt.mode,
        previous_version=rebuilt.previous_version,
        current_version=rebuilt.current_version,
        aggregate_fingerprint=rebuilt.aggregate_fingerprint,
        applied=applied,
        preserved_project_asset_ids=preserve_ids,
        stamp_written_last=stamp_written,
        rollback_performed=rollback_performed,
        timings_ms=timings,
    )


def _plan_payload(
    plan: Plan,
    *,
    timings_ms: dict[str, float] | None = None,
) -> dict[str, Any]:
    payload = {
        "status": "blocked" if plan.blockers else "planned",
        "readiness": "blocked" if plan.blockers else "ready",
        "execution_status": "failed" if plan.blockers else "planned",
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
        "gaps": [asdict(item) for item in plan.gaps],
        "blockers": plan.blockers,
        "project_asset_whitelist": plan.project_requirements,
        "confirmation_required": plan.mode == "rebuild",
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
    parser.add_argument(
        "--confirmed-whitelist",
        action="store_true",
        help="confirm the independently audited old-project asset decisions",
    )
    parser.add_argument(
        "--preserve-project-asset",
        action="append",
        default=[],
        metavar="WID",
        help="repeat an exact W ID from the old-project whitelist",
    )
    parser.add_argument("--confirmed-risk", action="store_true")
    args = parser.parse_args(argv)

    try:
        runtime_root = _plain_root(args.project_root, "project root")
        runtime_template = _plain_root(args.template_root, "template root")
        runtime_contract = _trusted_project_runtime_module(runtime_template)
        try:
            runtime_contract.validate_project_runtime(
                runtime_root,
                executable=sys.executable,
            )
        except runtime_contract.ProjectRuntimeError as exc:
            raise SyncBlocked(f"project runtime contract rejected: {exc}") from exc
        except Exception as exc:
            raise SyncBlocked(
                "project runtime contract validation failed closed: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
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
        receipt = apply_plan(
            plan,
            plan_fingerprint=args.plan_fingerprint,
            confirmed_risk=args.confirmed_risk,
            confirmed_whitelist=args.confirmed_whitelist,
            preserved_project_asset_ids=tuple(args.preserve_project_asset),
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
