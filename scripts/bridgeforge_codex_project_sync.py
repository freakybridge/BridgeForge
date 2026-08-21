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
PROJECT_HOOK_BUNDLE_RE = re.compile(r"project_[A-Za-z0-9][A-Za-z0-9_-]*")
PROJECT_HOOK_COMMAND_RE = re.compile(
    r"^\.venv/Scripts/python\.exe "
    r"\.codex/hooks/(project_[A-Za-z0-9][A-Za-z0-9_-]*)/entrypoint\.py$"
)
REQUIRED_PROJECT_MAPS = (
    ("R:project-map:find-doc", ".codex/find-doc.map.md"),
    ("R:project-map:sync-docs", ".codex/sync-docs.map.md"),
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
    current_stamp_before_sha256: str | None
    contract_sha256: str
    actions: list[Action]
    gaps: list[Gap]
    blockers: list[str]
    preservation_entries: list[dict[str, Any]]
    aggregate_fingerprint: str = ""

    @property
    def safe_actions(self) -> list[Action]:
        return [item for item in self.actions if item.classification == "safe"]

    @property
    def risk_actions(self) -> list[Action]:
        return [item for item in self.actions if item.classification == "risk"]


@dataclass
class PreservationManifest:
    """One-transaction project-asset decisions; never serialized to disk."""

    plan_fingerprint: str
    dispositions: dict[str, str]
    required_preserve: tuple[str, ...]
    cleared: bool = False

    def clear(self) -> None:
        self.dispositions.clear()
        self.required_preserve = ()
        self.plan_fingerprint = ""
        self.cleared = True


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
    deleted_project_asset_ids: tuple[str, ...]
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


def _sha256_tree(path: Path) -> str:
    if not path.is_dir() or _is_reparse(path):
        raise SyncBlocked(f"project asset bundle is not a plain directory: {path}")
    entries: list[tuple[str, str]] = []
    for current, dirnames, filenames in os.walk(path, followlinks=False):
        current_path = Path(current)
        if _is_reparse(current_path):
            raise SyncBlocked(f"project asset bundle contains a reparse directory: {current_path}")
        for name in tuple(dirnames):
            candidate = current_path / name
            if _is_reparse(candidate):
                raise SyncBlocked(
                    f"project asset bundle contains a reparse directory: {candidate}"
                )
        for name in filenames:
            candidate = current_path / name
            if not candidate.is_file() or _is_reparse(candidate):
                raise SyncBlocked(f"project asset bundle contains a non-plain file: {candidate}")
            entries.append(
                (candidate.relative_to(path).as_posix(), _sha256_path(candidate))
            )
    return _sha256_bytes(_canonical_json(sorted(entries)))


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


def _lexical_inside(root: Path, relative: str, label: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or not relative or any(
        part in {"", ".", ".."} for part in candidate.parts
    ):
        raise SyncBlocked(f"{label} is not a safe relative path: {relative!r}")
    target = root / candidate
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise SyncBlocked(f"{label} escapes its root: {relative!r}") from exc
    return target


def _inside(root: Path, relative: str, label: str) -> Path:
    resolved = _lexical_inside(root, relative, label).resolve()
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


def _optional_plain_file(
    root: Path,
    target: Path,
    label: str,
) -> bool:
    _assert_plain_ancestors(root, target)
    try:
        os.lstat(target)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise SyncBlocked(f"cannot inspect {label}: {target}") from exc
    if not target.is_file() or _is_reparse(target):
        raise SyncBlocked(f"{label} is not a plain file: {target}")
    return True


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
    minimum_baseline = _minimum_current_baseline(checker)
    try:
        contract = checker.load_contract(contract_path)
    except Exception as exc:
        raise SyncBlocked(f"cannot read current-only Codex asset contract: {exc}") from exc
    release = str(contract.get("release_version", ""))
    if _semver(release, "contract release version") < minimum_baseline:
        rendered = ".".join(str(item) for item in minimum_baseline)
        raise SyncBlocked(f"current-only contract must start at {rendered}")
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
        "current_stamp_before_sha256": plan.current_stamp_before_sha256,
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
        "preservation_entries": plan.preservation_entries,
    }
    return _sha256_bytes(_canonical_json(payload))


OBSOLETE_STAMP = ".codex/.bridgeforge_version"
CURRENT_STAMP = ".codex/.bridgeforge_codex_version"


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


def _minimum_current_baseline(checker: Any) -> tuple[int, int, int]:
    value = getattr(checker, "MINIMUM_CURRENT_BASELINE", None)
    if (
        not isinstance(value, tuple)
        or len(value) != 3
        or any(not isinstance(item, int) or item < 0 for item in value)
    ):
        raise SyncBlocked("current baseline checker has an invalid minimum baseline")
    return value


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


def _project_hook_projection(
    current: bytes,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    try:
        local = _loads_json(current.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SyncBlocked(f"project hooks.json is invalid: {exc}") from exc
    if not isinstance(local, dict) or not isinstance(local.get("hooks"), dict):
        raise SyncBlocked("project hooks.json has no hooks object")
    external: dict[str, list[dict[str, Any]]] = {}
    registrations: dict[str, int] = {}
    for event, entries in local["hooks"].items():
        if not isinstance(event, str) or not event or not isinstance(entries, list):
            raise SyncBlocked(f"project hooks event is invalid: {event}")
        kept: list[dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                raise SyncBlocked(f"project hooks group is invalid: {event}")
            handlers: list[dict[str, Any]] = []
            for handler in entry["hooks"]:
                if not isinstance(handler, dict):
                    raise SyncBlocked(f"project hook handler is invalid: {event}")
                managed_id = handler.get("bridgeforgeCodexId")
                if isinstance(managed_id, str) and managed_id.startswith(
                    "bridgeforge-codex.project-hook.v1:"
                ):
                    continue
                if managed_id is not None:
                    raise SyncBlocked(
                        f"project hook registration has a non-canonical identity: {event}"
                    )
                if handler.get("type") != "command" or "commandWindows" in handler:
                    raise SyncBlocked(
                        f"project hook registration is not a canonical Python command: {event}"
                    )
                command = handler.get("command")
                match = (
                    PROJECT_HOOK_COMMAND_RE.fullmatch(command)
                    if isinstance(command, str)
                    else None
                )
                if match is None:
                    raise SyncBlocked(
                        f"project hook registration is not a canonical Python command: {event}"
                    )
                bundle = match.group(1)
                registrations[bundle] = registrations.get(bundle, 0) + 1
                handlers.append(copy.deepcopy(handler))
            if handlers:
                kept.append({**entry, "hooks": handlers})
        if kept:
            external[str(event)] = kept
    return external, registrations


def _project_hook_bundle_name(handler: dict[str, Any]) -> str:
    command = handler.get("command")
    match = (
        PROJECT_HOOK_COMMAND_RE.fullmatch(command)
        if isinstance(command, str)
        else None
    )
    if match is None:
        raise SyncBlocked("project hook command lost its canonical bundle identity")
    return match.group(1)


def _merge_hooks_current(
    source: bytes,
    current: bytes | None,
    *,
    preserved_bundles: set[str] | None = None,
) -> bytes:
    canonical = _loads_json(source.decode("utf-8-sig"))
    if current is None:
        return json.dumps(canonical, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    external, _registrations = _project_hook_projection(current)
    if preserved_bundles is not None:
        filtered: dict[str, list[dict[str, Any]]] = {}
        for event, entries in external.items():
            kept: list[dict[str, Any]] = []
            for entry in entries:
                handlers = [
                    handler
                    for handler in entry["hooks"]
                    if _project_hook_bundle_name(handler) in preserved_bundles
                ]
                if handlers:
                    kept.append({**entry, "hooks": handlers})
            if kept:
                filtered[event] = kept
        external = filtered
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
) -> tuple[list[dict[str, Any]], list[str]]:
    candidates: list[dict[str, Any]] = []
    blockers: list[str] = []
    agents = root / "AGENTS.md"
    try:
        agents_present = _optional_plain_file(
            root,
            agents,
            "AGENTS project asset",
        )
    except SyncBlocked as exc:
        blockers.append(str(exc))
        agents_present = False
    if agents_present:
        try:
            _start, _stop, block = _marker_block(
                agents.read_bytes(),
                str(agents_asset["agents_zones"]["project"]["begin"]),
                str(agents_asset["agents_zones"]["project"]["end"]),
            )
            candidates.append({
                "id": "P:agents-project-zone",
                "kind": "agents-project-zone",
                "target": "AGENTS.md",
                "sha256": _sha256_bytes(block),
                "recommended": "preserve",
                "disposition": "user-decision",
            })
        except SyncBlocked as exc:
            blockers.append(f"AGENTS project markers are invalid: {exc}")

    external_hooks: dict[str, list[dict[str, Any]]] = {}
    registrations: dict[str, int] = {}
    hooks_json = root / ".codex" / "hooks.json"
    if hooks_json.is_file():
        try:
            external_hooks, registrations = _project_hook_projection(
                hooks_json.read_bytes()
            )
        except SyncBlocked as exc:
            blockers.append(str(exc))

    bundle_paths: dict[str, Path] = {}
    hooks_root = root / ".codex" / "hooks"
    if hooks_root.exists():
        if not hooks_root.is_dir() or _is_reparse(hooks_root):
            blockers.append("project hooks root is not a plain directory")
        else:
            for child in sorted(hooks_root.iterdir(), key=lambda item: item.name):
                relative = child.relative_to(root).as_posix()
                if child.is_file() and relative in desired_targets:
                    continue
                if not child.is_dir() or not PROJECT_HOOK_BUNDLE_RE.fullmatch(child.name):
                    blockers.append(
                        f"non-canonical project hook asset must be normalized first: {relative}"
                    )
                    continue
                if _is_reparse(child):
                    blockers.append(f"project hook bundle is a reparse directory: {relative}")
                    continue
                entrypoint = child / "entrypoint.py"
                if not entrypoint.is_file() or _is_reparse(entrypoint):
                    blockers.append(
                        f"project hook bundle has no plain entrypoint.py: {relative}"
                    )
                    continue
                try:
                    bundle_hash = _sha256_tree(child)
                except SyncBlocked as exc:
                    blockers.append(str(exc))
                    continue
                bundle_paths[child.name] = child
                registration_projection: dict[str, list[dict[str, Any]]] = {}
                for event, entries in external_hooks.items():
                    projected_entries: list[dict[str, Any]] = []
                    for entry in entries:
                        handlers = [
                            handler
                            for handler in entry["hooks"]
                            if _project_hook_bundle_name(handler) == child.name
                        ]
                        if handlers:
                            projected_entries.append({**entry, "hooks": handlers})
                    if projected_entries:
                        registration_projection[event] = projected_entries
                candidates.append({
                    "id": f"P:project-hook-bundle:{relative}",
                    "kind": "project-hook-bundle",
                    "target": relative,
                    "sha256": bundle_hash,
                    "registration_sha256": _sha256_bytes(
                        _canonical_json(registration_projection)
                    ),
                    "recommended": "preserve",
                    "disposition": "user-decision",
                })
    missing_bundles = sorted(set(registrations) - set(bundle_paths))
    if missing_bundles:
        blockers.append(
            "project hook registration has no canonical bundle: "
            + ", ".join(missing_bundles)
        )
    unregistered_bundles = sorted(set(bundle_paths) - set(registrations))
    if unregistered_bundles:
        blockers.append(
            "project hook bundle has no hooks.json registration: "
            + ", ".join(unregistered_bundles)
        )

    precommit = root / ".githooks" / "pre-commit"
    try:
        precommit_present = _optional_plain_file(
            root,
            precommit,
            "pre-commit project asset",
        )
    except SyncBlocked as exc:
        blockers.append(str(exc))
        precommit_present = False
    if precommit_present:
        extension = {
            "begin": "# >>> PROJECT_EXTENSION_BEGIN",
            "end": "# <<< PROJECT_EXTENSION_END",
        }
        try:
            _start, _stop, block = _marker_block(
                precommit.read_bytes(), extension["begin"], extension["end"]
            )
        except SyncBlocked as exc:
            blockers.append(f"pre-commit project-extension markers are invalid: {exc}")
        else:
            if block not in {
                b"# >>> PROJECT_EXTENSION_BEGIN\n# <<< PROJECT_EXTENSION_END\n",
                b"# >>> PROJECT_EXTENSION_BEGIN\n# <<< PROJECT_EXTENSION_END",
            }:
                candidates.append({
                    "id": "P:hook-extension:.githooks/pre-commit",
                    "kind": "hook-extension",
                    "target": ".githooks/pre-commit",
                    "sha256": _sha256_bytes(block),
                    "recommended": "preserve",
                    "disposition": "user-decision",
                })

    for asset_id, relative in REQUIRED_PROJECT_MAPS:
        if relative in desired_targets:
            continue
        target = root / relative
        try:
            target_present = _optional_plain_file(
                root,
                target,
                f"required project mapping {relative}",
            )
        except SyncBlocked as exc:
            blockers.append(str(exc))
            continue
        if target_present:
            candidates.append({
                "id": asset_id,
                "kind": "project-map",
                "target": relative,
                "sha256": _sha256_path(target),
                "recommended": "preserve",
                "disposition": "required-preserve",
            })

    rules = root / ".codex" / "rules"
    if rules.is_dir() and not _is_reparse(rules):
        for path in sorted(item for item in rules.rglob("*") if item.is_file()):
            relative = path.relative_to(root).as_posix()
            if relative in desired_targets:
                continue
            candidates.append({
                "id": f"P:rule:{relative}",
                "kind": "rule",
                "target": relative,
                "sha256": _sha256_path(path),
                "recommended": "review",
                "disposition": "user-decision",
            })

    for kind in ("memory", "skills"):
        folder = root / ".codex" / kind
        if folder.exists():
            try:
                tree_hash = _sha256_tree(folder)
            except SyncBlocked as exc:
                blockers.append(str(exc))
                continue
            candidates.append({
                "id": f"R:{kind}",
                "kind": kind,
                "target": f".codex/{kind}",
                "sha256": tree_hash,
                "recommended": "preserve",
                "disposition": "required-preserve",
            })
    return candidates, blockers


def _validate_preserved_knowledge(root: Path, template_root: Path) -> None:
    memory = root / ".codex" / "memory"
    if memory.is_dir():
        lint = template_root / "templates" / "hooks" / "memory_lint.py"
        if not lint.is_file() or _is_reparse(lint):
            raise SyncBlocked("trusted project memory validator is missing or unsafe")
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
        if result.returncode != 0:
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
        previous_dont_write_bytecode = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            spec.loader.exec_module(module)
            issues, _warnings = module.validate_skill_tree(skills)
        except Exception as exc:
            raise SyncBlocked(f"project Skill compatibility check failed: {exc}") from exc
        finally:
            sys.dont_write_bytecode = previous_dont_write_bytecode
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


def _contract_targets(
    root: Path,
    contract: dict[str, Any],
    label: str,
) -> dict[str, dict[str, Any]]:
    targets: dict[str, dict[str, Any]] = {}
    for asset in contract.get("assets", []):
        if not isinstance(asset, dict) or not isinstance(asset.get("target"), str):
            raise SyncBlocked(f"{label} contains an invalid asset target")
        relative = str(asset["target"])
        target = _inside(root, relative, f"{label} asset target")
        normalized = target.relative_to(root).as_posix().casefold()
        if normalized in targets:
            raise SyncBlocked(
                f"{label} contains duplicate normalized target: {relative}"
            )
        targets[normalized] = asset
    return targets


def _current_contract_removals(
    root: Path,
    installed_contract: dict[str, Any],
    incoming_contract: dict[str, Any],
) -> tuple[list[Action], list[str], set[str]]:
    try:
        installed = _contract_targets(root, installed_contract, "installed contract")
        incoming = _contract_targets(root, incoming_contract, "incoming contract")
    except SyncBlocked as exc:
        return [], [str(exc)], set()
    actions: list[Action] = []
    blockers: list[str] = []
    removed_targets: set[str] = set()
    for normalized in sorted(set(installed) - set(incoming)):
        asset = installed[normalized]
        asset_id = str(asset.get("id", "<unknown>"))
        target = _inside(root, str(asset["target"]), f"removed asset {asset_id}")
        relative = target.relative_to(root).as_posix()
        removed_targets.add(relative)
        has_partial_ownership = any(
            asset.get(key) is not None
            for key in (
                "agents_zones",
                "managed_blocks",
                "merge_policy",
                "merge_validation",
                "region",
            )
        )
        if asset.get("strategy") != "whole" or has_partial_ownership:
            blockers.append(
                f"removed current asset is not whole-owned: {asset_id}: {relative}"
            )
            continue
        if not target.is_file() or _is_reparse(target):
            blockers.append(
                f"removed current whole asset is missing or unsafe: {asset_id}: {relative}"
            )
            continue
        current = target.read_bytes()
        if _target_hash(current, asset, root) != asset.get("current_sha256"):
            blockers.append(
                f"removed current whole asset drifted: {asset_id}: {relative}"
            )
            continue
        actions.append(Action(
            asset_id=f"current.remove.{asset_id}",
            target=relative,
            action="delete",
            classification="safe",
            reason="delete an unchanged whole asset absent from the incoming contract",
            before_sha256=_sha256_bytes(current),
            after_sha256=None,
            payload=None,
        ))
    return actions, blockers, removed_targets


def build_plan(project_root: Path, template_root: Path, mode: str = "auto") -> Plan:
    root = _plain_root(project_root, "project root")
    template = _plain_root(template_root, "template root")
    contract, contract_path = load_contract(template)
    checker = _trusted_current_baseline_module(template)
    minimum_baseline = _minimum_current_baseline(checker)
    selected_mode = _detect_mode(root, mode)
    current_version = (template / "VERSION").read_text(
        encoding="utf-8-sig"
    ).strip()
    if current_version != contract["release_version"]:
        raise SyncBlocked(
            "bridgeforge-codex VERSION does not match current-only contract"
        )
    stamp = _lexical_inside(root, CURRENT_STAMP, "version stamp")
    old_stamp = _lexical_inside(root, OBSOLETE_STAMP, "obsolete version stamp")
    blockers: list[str] = []
    previous_version: str | None = None
    current_stamp_before_sha256: str | None = None

    def blocked_plan() -> Plan:
        plan = Plan(
            project_root=str(root),
            template_root=str(template),
            mode=selected_mode,
            current_version=current_version,
            previous_version=previous_version,
            current_stamp_before_sha256=current_stamp_before_sha256,
            contract_sha256=_sha256_path(contract_path),
            actions=[],
            gaps=[],
            blockers=blockers,
            preservation_entries=[],
        )
        plan.aggregate_fingerprint = _fingerprint(plan)
        return plan

    if selected_mode == "init" and (
        (root / ".codex").exists()
        or (root / "AGENTS.md").exists()
        or (root / ".githooks" / "pre-commit").exists()
    ):
        blockers.append(
            "init requires a project with no existing skeleton identity; zero writes performed"
        )
    try:
        stamp_present = _optional_plain_file(root, stamp, "version stamp path")
    except SyncBlocked as exc:
        blockers.append(str(exc))
        stamp_present = False
    if stamp_present:
        current_stamp_before_sha256 = _sha256_path(stamp)
    try:
        old_stamp_present = _optional_plain_file(
            root,
            old_stamp,
            "obsolete version stamp path",
        )
    except SyncBlocked as exc:
        blockers.append(str(exc))
        old_stamp_present = False
    if stamp_present and old_stamp_present:
        blockers.append(
            "both current and obsolete version stamps exist; zero writes performed"
        )
    elif old_stamp_present:
        previous_version = old_stamp.read_text(encoding="utf-8-sig").strip()
    elif stamp_present:
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
    current_semver = _semver(current_version, "current bridgeforge-codex version")
    if previous_semver is not None:
        if previous_semver > current_semver:
            blockers.append(
                f"project version {previous_version} is newer than {current_version}"
            )
    rebuild = bool(
        previous_semver is not None
        and previous_semver < minimum_baseline
    )
    if blockers:
        return blocked_plan()
    if previous_semver is not None and not rebuild and not blockers:
        try:
            checker.verify_current_baseline(
                root,
                prospective_version=(
                    previous_version if old_stamp_present else None
                ),
            )
        except Exception as exc:
            blockers.append(
                f"current baseline drifted; zero writes performed: {exc}"
            )
    if blockers:
        return blocked_plan()
    try:
        _validate_preserved_knowledge(root, template)
    except SyncBlocked as exc:
        blockers.append(str(exc))
    if blockers:
        return blocked_plan()

    actions: list[Action] = []
    gaps: list[Gap] = []
    if old_stamp_present:
        actions.append(Action(
            asset_id="stamp.remove-obsolete",
            target=OBSOLETE_STAMP,
            action="delete",
            classification="safe",
            reason="replace the obsolete stamp with the current stamp in one transaction",
            before_sha256=_sha256_path(old_stamp),
            after_sha256=None,
            payload=None,
        ))
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
        merge_current = (
            current
            if (
                not rebuild
                or asset.get("strategy") == "seed"
                or isinstance(asset.get("managed_blocks"), dict)
            )
            else None
        )
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
                "install the clean current public baseline"
                if rebuild
                else "advance verified current baseline"
            ),
            before_sha256=None if current is None else _sha256_bytes(current),
            after_sha256=None if desired is None else _sha256_bytes(desired),
            payload=desired,
        ))
    contract_target = str(contract["contract_target"])
    incoming_contract_bytes = (
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
    removed_current_targets: set[str] = set()
    if current_contract is not None and not rebuild:
        try:
            installed_contract = checker.load_contract(current_contract_path)
        except Exception as exc:
            blockers.append(
                f"installed current contract is invalid; zero writes performed: {exc}"
            )
        else:
            removal_actions, removal_blockers, removed_current_targets = (
                _current_contract_removals(root, installed_contract, contract)
            )
            actions.extend(removal_actions)
            blockers.extend(removal_blockers)
    if current_contract != incoming_contract_bytes:
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
            after_sha256=_sha256_bytes(incoming_contract_bytes),
            payload=incoming_contract_bytes,
        ))
    agents_asset = next(
        asset
        for asset in contract["assets"]
        if asset["id"] == "root.agents"
    )
    inspected_candidates, candidate_blockers = _project_asset_candidates(
        root,
        agents_asset,
        desired_targets | removed_current_targets,
    )
    blockers.extend(candidate_blockers)
    candidates: list[dict[str, Any]] = inspected_candidates if rebuild else []
    if rebuild:
        codex_root = root / ".codex"
        if codex_root.is_dir() and not _is_reparse(codex_root):
            candidate_targets = {
                str(item["target"])
                for item in candidates
            }
            user_decision_targets = {
                str(item["target"])
                for item in candidates
                if item.get("disposition") == "user-decision"
            }
            required_preserve_targets = {
                str(item["target"])
                for item in candidates
                if item.get("disposition") == "required-preserve"
            }
            known_targets = (
                desired_targets
                | candidate_targets
                | {
                    OBSOLETE_STAMP,
                    ".codex/memory",
                    ".codex/skills",
                    ".codex/rules",
                }
            )

            def known_structure(relative: str) -> bool:
                return any(
                    relative == target
                    or relative.startswith(target + "/")
                    or target.startswith(relative + "/")
                    for target in known_targets
                )

            for path in sorted(codex_root.rglob("*")):
                relative = path.relative_to(root).as_posix()
                if _is_reparse(path):
                    blockers.append(
                        "unknown or unsafe .codex structure blocks rebuild: "
                        + relative
                    )
                    continue
                if path.is_dir():
                    if not known_structure(relative):
                        blockers.append(
                            "unknown .codex structure must be classified before rebuild: "
                            + relative
                        )
                    continue
                if not path.is_file():
                    blockers.append(
                        "unknown or unsafe .codex structure blocks rebuild: "
                        + relative
                    )
                    continue
                if (
                    relative in desired_targets
                    or relative == OBSOLETE_STAMP
                    or relative.startswith(".codex/memory/")
                    or relative.startswith(".codex/skills/")
                    or any(
                        relative == target or relative.startswith(target + "/")
                        for target in required_preserve_targets
                    )
                ):
                    continue
                selected_project_asset = any(
                    relative == target or relative.startswith(target + "/")
                    for target in user_decision_targets
                )
                if not selected_project_asset:
                    blockers.append(
                        "unknown .codex structure must be classified before rebuild: "
                        + relative
                    )
                    continue
                actions.append(Action(
                    asset_id=f"rebuild.remove.{relative.replace('/', '.')}",
                    target=relative,
                    action="delete",
                    classification="risk",
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
        current_stamp_before_sha256=current_stamp_before_sha256,
        contract_sha256=_sha256_path(contract_path),
        actions=actions,
        gaps=gaps,
        blockers=blockers,
        preservation_entries=candidates,
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

    def delete_tree(self, tree: Path) -> None:
        self.snapshot_tree(tree)
        if not tree.exists():
            return
        for current, dirnames, filenames in os.walk(
            tree,
            topdown=False,
            followlinks=False,
        ):
            current_path = Path(current)
            if _is_reparse(current_path):
                raise SyncBlocked(
                    f"transaction tree contains a reparse directory: {current_path}"
                )
            for name in filenames:
                candidate = current_path / name
                if not candidate.is_file() or _is_reparse(candidate):
                    raise SyncBlocked(
                        f"transaction tree contains a non-plain file: {candidate}"
                    )
                candidate.unlink()
            for name in dirnames:
                (current_path / name).rmdir()
            current_path.rmdir()

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
        for tree, (files, directories) in reversed(tuple(self.tree_before.items())):
            try:
                self._rollback_tree(tree, files, directories)
            except OSError as exc:
                failures.append(f"{tree}: {exc}")
        for path, payload in reversed(tuple(self.before.items())):
            try:
                if payload is None:
                    path.unlink(missing_ok=True)
                else:
                    _atomic_write(path, payload, self.root)
            except OSError as exc:
                failures.append(f"{path}: {exc}")
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


def _build_preservation_manifest(
    plan: Plan,
    preserved_project_asset_ids: tuple[str, ...],
    deleted_project_asset_ids: tuple[str, ...],
) -> PreservationManifest:
    candidates = {
        str(item["id"]): item
        for item in plan.preservation_entries
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    user_decisions = {
        item_id
        for item_id, item in candidates.items()
        if item.get("disposition") == "user-decision"
    }
    required_preserve = tuple(sorted(
        item_id
        for item_id, item in candidates.items()
        if item.get("disposition") == "required-preserve"
    ))
    preserve = set(preserved_project_asset_ids)
    delete = set(deleted_project_asset_ids)
    overlap = sorted(preserve & delete)
    if overlap:
        raise SyncBlocked(
            "project asset has both preserve and delete dispositions: "
            + ", ".join(overlap)
        )
    unknown = sorted((preserve | delete) - user_decisions)
    if unknown:
        raise SyncBlocked(
            "unknown or non-selectable project asset decision IDs: "
            + ", ".join(unknown)
        )
    missing = sorted(user_decisions - preserve - delete)
    if missing:
        raise SyncBlocked(
            "every project asset requires an explicit preserve/delete disposition: "
            + ", ".join(missing)
        )
    dispositions = {
        item_id: ("preserve" if item_id in preserve else "delete")
        for item_id in sorted(user_decisions)
    }
    for item_id in required_preserve:
        dispositions[item_id] = "required-preserve"
    manifest_payload = {
        "plan_fingerprint": plan.aggregate_fingerprint,
        "dispositions": dispositions,
    }
    return PreservationManifest(
        plan_fingerprint=_sha256_bytes(_canonical_json(manifest_payload)),
        dispositions=dispositions,
        required_preserve=required_preserve,
    )


def _verify_required_preserve_files(
    root: Path,
    candidates: Iterable[dict[str, Any]],
) -> None:
    for item in candidates:
        if (
            item.get("disposition") != "required-preserve"
            or item.get("kind") != "project-map"
        ):
            continue
        relative = str(item["target"])
        target = _inside(root, relative, "required-preserve project file")
        if not _optional_plain_file(
            root,
            target,
            f"required-preserve project file {relative}",
        ):
            raise SyncBlocked(
                f"required-preserve project file disappeared: {relative}"
            )
        if _sha256_path(target) != str(item["sha256"]):
            raise SyncBlocked(
                f"required-preserve project file drifted: {relative}"
            )


def apply_plan(
    planned: Plan,
    *,
    plan_fingerprint: str,
    confirmed_risk: bool = False,
    confirmed_preservation_manifest: bool = False,
    preserved_project_asset_ids: tuple[str, ...] = (),
    deleted_project_asset_ids: tuple[str, ...] = (),
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
        confirmed_preservation_manifest=confirmed_preservation_manifest,
        preserved_project_asset_ids=preserved_project_asset_ids,
        deleted_project_asset_ids=deleted_project_asset_ids,
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
    confirmed_preservation_manifest: bool = False,
    preserved_project_asset_ids: tuple[str, ...] = (),
    deleted_project_asset_ids: tuple[str, ...] = (),
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
        for item in rebuilt.preservation_entries
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    preserve_ids = tuple(dict.fromkeys(preserved_project_asset_ids))
    delete_ids = tuple(dict.fromkeys(deleted_project_asset_ids))
    preservation_manifest: PreservationManifest | None = None
    if rebuilt.mode == "rebuild":
        if not confirmed_preservation_manifest:
            raise SyncBlocked(
                "destructive rebuild requires --confirmed-preservation-manifest "
                "after independent audit"
            )
        if not confirmed_risk:
            raise SyncBlocked(
                "destructive rebuild requires the single --confirmed-risk decision"
            )
    elif confirmed_preservation_manifest or preserve_ids or delete_ids:
        raise SyncBlocked("project asset decisions are only valid for old-project rebuild")
    elif rebuilt.risk_actions:
        raise SyncBlocked("current-only update cannot contain risk actions")

    if rebuilt.mode == "rebuild":
        preservation_manifest = _build_preservation_manifest(
            rebuilt,
            preserve_ids,
            delete_ids,
        )

    selected_targets = {
        str(candidate_by_id[item_id]["target"])
        for item_id in preserve_ids
        if item_id in candidate_by_id
    }
    actions = [
        action
        for action in rebuilt.actions
        if not (
            rebuilt.mode == "rebuild"
            and action.action == "delete"
            and any(
                action.target == target or action.target.startswith(target + "/")
                for target in selected_targets
            )
        )
    ]
    root = Path(rebuilt.project_root)
    template = Path(rebuilt.template_root)
    contract, _contract_path = load_contract(template)
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
        selected_bundles = {
            Path(str(candidate_by_id[item_id]["target"])).name
            for item_id in preserve_ids
            if candidate_by_id[item_id].get("kind") == "project-hook-bundle"
        }
        if any(
            item.get("kind") == "project-hook-bundle"
            for item in candidate_by_id.values()
        ):
            asset = asset_by_id["codex.hooks-config"]
            source = _inside(template, asset["source"], "hooks source").read_bytes()
            current = _inside(root, asset["target"], "hooks target").read_bytes()
            preserve_action(
                "codex.hooks-config",
                _merge_hooks_current(
                    source,
                    current,
                    preserved_bundles=selected_bundles,
                ),
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
    _verify_required_preserve_files(root, candidate_by_id.values())
    deleted_bundle_paths = tuple(
        _inside(
            root,
            str(candidate_by_id[item_id]["target"]),
            "project hook bundle deletion",
        )
        for item_id in delete_ids
        if candidate_by_id[item_id].get("kind") == "project-hook-bundle"
    )
    for bundle_path in deleted_bundle_paths:
        transaction.snapshot_tree(bundle_path)
    stamp = _lexical_inside(root, CURRENT_STAMP, "version stamp")
    stamp_present = _optional_plain_file(root, stamp, "version stamp path")
    stamp_before_sha256 = _sha256_path(stamp) if stamp_present else None
    if stamp_before_sha256 != rebuilt.current_stamp_before_sha256:
        raise SyncBlocked(
            "current version stamp drifted after replan; zero writes performed"
        )
    stamp_written = False
    rollback_performed = False
    try:
        for action in actions:
            if action.asset_id == "stamp.remove-obsolete":
                target = _lexical_inside(
                    root,
                    action.target,
                    f"action {action.asset_id}",
                )
                _optional_plain_file(
                    root,
                    target,
                    "obsolete version stamp path",
                )
            else:
                target = _inside(root, action.target, f"action {action.asset_id}")
            if checkpoint is not None:
                checkpoint(f"before-action:{action.asset_id}")
            if action.before_sha256 is None:
                if target.exists():
                    raise SyncBlocked(
                        f"action target appeared after planning: {action.target}"
                    )
            elif not target.is_file() or _sha256_path(target) != action.before_sha256:
                raise SyncBlocked(
                    f"action target drifted after planning: {action.target}"
                )
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
        for bundle_path in deleted_bundle_paths:
            transaction.delete_tree(bundle_path)
        if checkpoint is not None:
            checkpoint("after-project-hook-bundle-deletions")
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
        remaining_bundles = [
            str(path.relative_to(root))
            for path in deleted_bundle_paths
            if path.exists()
        ]
        if remaining_bundles:
            raise SyncBlocked(
                "deleted project hook bundle still exists: "
                + ", ".join(remaining_bundles)
            )
        _verify_preserved_knowledge(knowledge_before)
        _run_current_validators(root, actions)
        checker = _trusted_current_baseline_module(template)
        checker.verify_current_baseline(
            root,
            expected_version=rebuilt.current_version,
            prospective_version=rebuilt.current_version,
        )
        _verify_required_preserve_files(root, candidate_by_id.values())
        if preservation_manifest is not None:
            preservation_manifest.clear()
            if (
                not preservation_manifest.cleared
                or preservation_manifest.dispositions
                or preservation_manifest.required_preserve
                or preservation_manifest.plan_fingerprint
            ):
                raise SyncBlocked("temporary preservation manifest cleanup failed")
        if checkpoint is not None:
            checkpoint("after-preservation-manifest-clear")
        _verify_required_preserve_files(root, candidate_by_id.values())
        stamp_present = _optional_plain_file(root, stamp, "version stamp path")
        stamp_before_sha256 = _sha256_path(stamp) if stamp_present else None
        if stamp_before_sha256 != rebuilt.current_stamp_before_sha256:
            raise SyncBlocked("current version stamp drifted during apply")
        transaction.write(
            stamp,
            (rebuilt.current_version + "\n").encode("utf-8"),
        )
        stamp_written = True
        if stamp.read_text(encoding="utf-8-sig").strip() != rebuilt.current_version:
            raise SyncBlocked("current baseline version stamp verification failed")
        _verify_required_preserve_files(root, candidate_by_id.values())
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
        deleted_project_asset_ids=delete_ids,
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
        "current_stamp_before_sha256": plan.current_stamp_before_sha256,
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
        "preservation_manifest": plan.preservation_entries,
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
        "--confirmed-preservation-manifest",
        action="store_true",
        help="confirm the independently audited one-time PreservationManifest",
    )
    parser.add_argument(
        "--preserve-project-asset",
        action="append",
        default=[],
        metavar="WID",
        help="repeat an exact P ID approved for preservation",
    )
    parser.add_argument(
        "--delete-project-asset",
        action="append",
        default=[],
        metavar="WID",
        help="repeat an exact user-decision ID approved for deletion",
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
            confirmed_preservation_manifest=args.confirmed_preservation_manifest,
            preserved_project_asset_ids=tuple(args.preserve_project_asset),
            deleted_project_asset_ids=tuple(args.delete_project_asset),
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
