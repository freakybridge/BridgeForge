#!/usr/bin/env python3
"""Plan and apply deterministic repository version releases for git-sync."""
from __future__ import annotations

import base64
import copy
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from hooks_ownership import (  # noqa: E402
    HooksOwnershipError,
    canonical_json_sha256 as _hooks_canonical_json_sha256,
    canonicalize as _canonicalize_hooks_zones,
    expected_groups as _expected_hooks_groups,
    load_document as _load_hooks_document,
    validate_current as _validate_current_hooks_zones,
)


SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
HEADER_RE = re.compile(
    r"^(feat|fix|docs|refactor|chore|perf)(?:\([^)\r\n]+\))?(!)?:\s+(.+?)\s*$"
)
BREAKING_RE = re.compile(r"(?m)^BREAKING CHANGE:\s*\S")
TYPE_LEVEL = {
    "feat": "minor",
    "fix": "patch",
    "docs": "patch",
    "refactor": "patch",
    "chore": "patch",
    "perf": "patch",
}
TYPE_SECTION = {
    "feat": "Added",
    "fix": "Fixed",
    "docs": "Changed",
    "refactor": "Changed",
    "chore": "Changed",
    "perf": "Changed",
}
AUTO_EXCLUDED_PATHS = {"VERSION", "CHANGELOG.md"}


class ReleaseError(RuntimeError):
    """Fail-closed release planning error."""


class TransitionBlocked(ReleaseError):
    """A contract transition failed with stable per-asset evidence."""

    def __init__(self, issues: list[dict[str, str]]) -> None:
        self.issues = tuple(dict(item) for item in issues)
        detail = "; ".join(
            f"{item['asset_id']}: {item['reason']}" for item in self.issues
        )
        super().__init__("ownership contract transition is blocked: " + detail)


@dataclass(frozen=True)
class CommitInfo:
    kind: str
    description: str
    level: str
    section: str
    breaking: bool


@dataclass(frozen=True)
class ReleasePlan:
    old_version: str
    new_version: str
    classification: str
    writes: dict[Path, bytes]


def parse_semver(value: str) -> tuple[int, int, int]:
    match = SEMVER_RE.fullmatch(value.strip())
    if not match:
        raise ReleaseError(f"unsupported version {value!r}; expected stable MAJOR.MINOR.PATCH")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def bump_semver(value: str, level: str) -> str:
    major, minor, patch = parse_semver(value)
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    if level == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ReleaseError(f"unknown bump level: {level}")


def parse_commit_message(message: str) -> CommitInfo:
    lines = message.replace("\r\n", "\n").split("\n")
    match = HEADER_RE.fullmatch(lines[0].strip() if lines else "")
    if not match:
        raise ReleaseError(
            "commit message must use feat/fix/docs/refactor/chore/perf with Conventional Commits"
        )
    kind, bang, description = match.groups()
    breaking = bool(bang) or bool(BREAKING_RE.search(message.replace("\r\n", "\n")))
    level = "major" if breaking else TYPE_LEVEL[kind]
    return CommitInfo(kind, description, level, TYPE_SECTION[kind], breaking)


def _git(repo: Path, args: list[str], *, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-c", f"safe.directory={repo.as_posix()}", *args],
        cwd=repo,
        input=input_bytes,
        capture_output=True,
        check=False,
        timeout=30,
    )


def _head_bytes(repo: Path, path: str) -> bytes | None:
    result = _git(repo, ["show", f"HEAD:{path}"])
    return result.stdout if result.returncode == 0 else None


def _normalized_snapshot(
    snapshot: dict[str, bytes | None] | None,
) -> dict[str, bytes | None]:
    normalized: dict[str, bytes | None] = {}
    for raw_path, payload in (snapshot or {}).items():
        path = PurePosixPath(str(raw_path).replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
            raise ReleaseError(f"invalid prospective snapshot path: {raw_path!r}")
        if payload is not None and not isinstance(payload, bytes):
            raise ReleaseError(f"invalid prospective snapshot payload: {raw_path!r}")
        canonical_path = path.as_posix()
        if canonical_path in normalized:
            raise ReleaseError(
                f"prospective snapshot path is duplicated: {canonical_path}"
            )
        normalized[canonical_path] = payload
    return normalized


def _current_bytes(
    repo: Path,
    path: str | Path,
    snapshot: dict[str, bytes | None] | None = None,
) -> bytes | None:
    relative = (
        path.relative_to(repo).as_posix()
        if isinstance(path, Path)
        else PurePosixPath(path.replace("\\", "/")).as_posix()
    )
    if snapshot is not None and relative in snapshot:
        return snapshot[relative]
    target = repo / relative
    return target.read_bytes() if target.is_file() else None


def _current_before_bytes(
    repo: Path,
    path: str | Path,
    before_snapshot: dict[str, bytes | None] | None,
) -> bytes | None:
    if before_snapshot is None:
        return _current_bytes(repo, path, {})
    normalized = _normalized_snapshot(before_snapshot)
    relative = (
        path.relative_to(repo).as_posix()
        if isinstance(path, Path)
        else PurePosixPath(path.replace("\\", "/")).as_posix()
    )
    if relative not in normalized:
        raise ReleaseError(
            f"explicit adaptation before snapshot is incomplete: {relative}"
        )
    return normalized[relative]


def _lexical_entry_exists(repo: Path, path: str) -> bool:
    relative = PurePosixPath(path.replace("\\", "/"))
    if relative.is_absolute() or ".." in relative.parts or str(relative) in {"", "."}:
        raise ReleaseError(f"invalid lexical target path: {path!r}")
    target = repo.joinpath(*relative.parts)
    try:
        os.lstat(target)
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


def _git_blob_bytes(payload: bytes) -> bytes:
    if b"\0" in payload:
        return payload
    return payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _sha256_bytes(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(_git_blob_bytes(payload)).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _path_matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern) or PurePosixPath(path).match(pattern)


def _region_parts(
    payload: bytes | None, begin: str, end: str
) -> tuple[bytes | None, bytes | None]:
    if payload is None:
        return None, None
    payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    begin_bytes = begin.encode("utf-8")
    end_bytes = end.encode("utf-8")
    if payload.count(begin_bytes) != 1 or payload.count(end_bytes) != 1:
        raise ReleaseError(f"managed region markers are missing or ambiguous: {begin} / {end}")
    start = payload.index(begin_bytes)
    finish_start = payload.index(end_bytes)
    if finish_start < start:
        raise ReleaseError(f"managed region markers are reversed: {begin} / {end}")
    finish = finish_start + len(end_bytes)
    outside = payload[:start] + b"<BRIDGEFORGE_CODEX_MANAGED_REGION>" + payload[finish:]
    return payload[start:finish], outside


def _region_transition_parts(
    payload: bytes | None, begin: str, end: str
) -> tuple[bytes | None, bytes | None]:
    if payload is None:
        return None, None
    normalized = _git_blob_bytes(payload)
    begin_count = normalized.count(begin.encode("utf-8"))
    end_count = normalized.count(end.encode("utf-8"))
    if begin_count == 0 and end_count == 0:
        return None, normalized
    return _region_parts(normalized, begin, end)


def _markdown_heading_spans(
    payload: bytes,
    headings: list[str],
) -> dict[str, tuple[int, int]]:
    try:
        payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ReleaseError("managed Markdown file is not valid UTF-8") from exc
    if len(set(headings)) != len(headings):
        raise ReleaseError("managed Markdown headings must be unique and non-empty")

    configured = {heading.encode("utf-8"): heading for heading in headings}
    lines = payload.splitlines(keepends=True)
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)
    matches: dict[str, list[tuple[int, int]]] = {heading: [] for heading in headings}
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
        raise ReleaseError("managed Markdown contains an unclosed fenced code block")

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
        raise ReleaseError(
            "managed Markdown headings are duplicated: " + ", ".join(duplicate)
        )

    return {heading: entries[0] for heading, entries in matches.items() if entries}


def _markdown_heading_parts(
    payload: bytes | None, headings: list[str]
) -> tuple[bytes | None, bytes | None]:
    if payload is None:
        return None, None
    payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if not headings:
        raise ReleaseError("managed Markdown headings must be unique and non-empty")
    matches = _markdown_heading_spans(payload, headings)
    spans = [
        (start, finish, heading)
        for heading, (start, finish) in matches.items()
    ]
    spans.sort()
    for previous, current in zip(spans, spans[1:]):
        if previous[1] > current[0]:
            raise ReleaseError("managed Markdown heading spans overlap")
    document_order = [heading for _start, _finish, heading in spans]
    managed_chunks = ["order=" + "|".join(document_order)]
    for heading in headings:
        span = matches.get(heading)
        if span is None:
            managed_chunks.append(heading + "=<MISSING>")
            continue
        start, finish = span
        block = payload[start:finish].rstrip(b" \t\n").decode("utf-8-sig")
        managed_chunks.append(heading + "=" + block)

    outside = payload
    for start, finish, heading in reversed(spans):
        marker = f"<BRIDGEFORGE_CODEX_MANAGED_MARKDOWN:{heading}>".encode("utf-8")
        outside = outside[:start] + marker + outside[finish:]
    return "\n\0".join(managed_chunks).encode("utf-8"), outside


def _table_cells(line: bytes) -> tuple[str, ...]:
    text = line.rstrip(b"\r\n").decode("utf-8-sig").strip()
    if not text.startswith("|") or not text.endswith("|"):
        raise ReleaseError("managed Markdown table row is ambiguous")
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
        raise ReleaseError("managed Markdown table row has an empty cell")
    return cells


def _table_key(cell: str) -> str:
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
        raise ReleaseError("managed Markdown table key is empty")
    return value.casefold()


def _keyed_table_parts(
    payload: bytes | None,
    heading: str,
    managed_keys: list[str],
) -> tuple[bytes | None, bytes | None]:
    if payload is None:
        return None, None
    payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    lines = payload.splitlines(keepends=True)
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)
    heading_spans = _markdown_heading_spans(payload, [heading])
    span = heading_spans.get(heading)
    if span is None:
        return f"{heading}=<MISSING>".encode("utf-8"), payload
    section_start, section_end = span
    heading_index = next(
        index for index, offset in enumerate(offsets) if offset == section_start
    )
    section_end_index = next(
        (index for index, offset in enumerate(offsets) if offset == section_end),
        len(lines),
    )

    candidates: list[int] = []
    for index in range(heading_index + 1, section_end_index - 1):
        try:
            header_cells = _table_cells(lines[index])
            separator_cells = _table_cells(lines[index + 1])
        except (ReleaseError, UnicodeDecodeError):
            continue
        if (
            len(header_cells) == len(separator_cells)
            and all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator_cells)
        ):
            candidates.append(index)
    if len(candidates) != 1:
        raise ReleaseError(
            f"managed Markdown heading must contain exactly one table: {heading}"
        )
    table_index = candidates[0]
    header_cells = _table_cells(lines[table_index])
    normalized_keys = [_table_key(item) for item in managed_keys]
    if len(set(normalized_keys)) != len(normalized_keys):
        raise ReleaseError(f"managed Markdown table contract has duplicate keys: {heading}")
    managed_set = set(normalized_keys)
    managed_rows: list[str] = []
    project_rows: list[bytes] = []
    seen: set[str] = set()
    data_end = table_index + 2
    while data_end < section_end_index:
        if not lines[data_end].rstrip(b"\r\n").lstrip().startswith(b"|"):
            break
        cells = _table_cells(lines[data_end])
        if len(cells) != len(header_cells):
            raise ReleaseError(f"managed Markdown table row has wrong columns: {heading}")
        key = _table_key(cells[0])
        if key in seen:
            raise ReleaseError(f"managed Markdown table has duplicate key: {heading} :: {key}")
        seen.add(key)
        if key in managed_set:
            managed_rows.append(key + "=" + "|".join(cells))
        else:
            project_rows.append(lines[data_end])
        data_end += 1
    managed = (
        heading
        + "\nheader="
        + "|".join(header_cells)
        + "\n"
        + "\n".join(managed_rows)
    ).encode("utf-8")
    table_start = offsets[table_index]
    table_end = offsets[data_end] if data_end < len(lines) else len(payload)
    project_table = b"<BRIDGEFORGE_CODEX_MANAGED_KEYED_TABLE>\n" + b"".join(project_rows)
    project = payload[:table_start] + project_table + payload[table_end:]
    return managed, project


def _managed_markdown_parts(
    payload: bytes | None,
    headings: list[str],
    additive_headings: list[str],
    keyed_tables: list[dict[str, object]],
    section_layout: dict[str, object] | None = None,
) -> tuple[bytes | None, bytes | None]:
    if section_layout is not None:
        groups = section_layout.get("groups")
        if not isinstance(groups, list):
            raise ReleaseError("invalid managed Markdown section layout")
        managed_layout_headings: list[str] = []
        structural_headings: list[str] = []
        for group in groups:
            if not isinstance(group, dict):
                raise ReleaseError("invalid managed Markdown section layout group")
            children = group.get("sections")
            entries = children if isinstance(children, list) else [group]
            if isinstance(children, list):
                structural = group.get("heading")
                if not isinstance(structural, str):
                    raise ReleaseError("invalid managed Markdown structural heading")
                structural_headings.append(structural)
            for entry in entries:
                if (
                    not isinstance(entry, dict)
                    or not isinstance(entry.get("heading"), str)
                    or entry.get("ownership") not in {"managed", "project", "keyed"}
                ):
                    raise ReleaseError("invalid managed Markdown section layout entry")
                if entry["ownership"] == "managed":
                    managed_layout_headings.append(str(entry["heading"]))
        managed, project = _managed_markdown_parts(
            payload,
            managed_layout_headings,
            [],
            keyed_tables,
            None,
        )
        if project is None:
            return managed, None
        spans = _markdown_heading_spans(project, structural_headings)
        ordered = [
            heading
            for heading, _span in sorted(spans.items(), key=lambda item: item[1][0])
        ]
        signature = ["layout-order=" + "|".join(ordered)]
        for heading in structural_headings:
            span = spans.get(heading)
            signature.append(
                heading + ("=<MISSING>" if span is None else "=" + heading)
            )
        for heading, (start, _finish) in sorted(
            spans.items(), key=lambda item: item[1][0], reverse=True
        ):
            newline = project.find(b"\n", start)
            line_end = len(project) if newline < 0 else newline + 1
            marker = f"<BRIDGEFORGE_CODEX_MANAGED_LAYOUT:{heading}>\n".encode("utf-8")
            project = project[:start] + marker + project[line_end:]
        return b"\n\0".join([managed or b"", "\n".join(signature).encode("utf-8")]), project
    all_headings = headings + additive_headings
    if all_headings:
        managed_headings, project = _markdown_heading_parts(payload, all_headings)
    else:
        managed_headings, project = b"order=", payload
    managed_chunks = [managed_headings or b""]
    for table in keyed_tables:
        heading = table.get("heading")
        managed_keys = table.get("managed_keys")
        if not isinstance(heading, str) or not isinstance(managed_keys, list):
            raise ReleaseError("invalid managed keyed-table contract")
        table_managed, project = _keyed_table_parts(project, heading, managed_keys)
        managed_chunks.append(table_managed or b"")
    return b"\n\0".join(managed_chunks), project


def _agents_zone_release_parts(
    payload: bytes | None,
    zones: dict[str, object],
) -> tuple[bytes | None, bytes | None]:
    if payload is None:
        return None, None
    payload = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    public = zones.get("public")
    project = zones.get("project")
    if not isinstance(public, dict) or not isinstance(project, dict):
        raise ReleaseError("invalid AGENTS zone ownership")
    markers = [
        public.get("begin"), public.get("end"),
        project.get("begin"), project.get("end"),
    ]
    if any(not isinstance(marker, str) for marker in markers):
        raise ReleaseError("invalid AGENTS zone markers")
    encoded = [str(marker).encode("utf-8") for marker in markers]
    if any(payload.count(marker) != 1 for marker in encoded):
        raise ReleaseError("AGENTS zone markers are missing or duplicated")
    positions = [payload.index(marker) for marker in encoded]
    if positions != sorted(positions):
        raise ReleaseError("AGENTS zone markers are reversed or nested")
    public_finish = payload.find(b"\n", positions[1])
    project_finish = payload.find(b"\n", positions[3])
    public_finish = len(payload) if public_finish < 0 else public_finish + 1
    project_finish = len(payload) if project_finish < 0 else project_finish + 1
    outside = (
        payload[:positions[0]]
        + payload[public_finish:positions[2]]
        + payload[project_finish:]
    )
    if outside.strip():
        raise ReleaseError("AGENTS content exists outside declared ownership zones")
    return (
        payload[positions[0]:public_finish],
        payload[positions[2]:project_finish],
    )


def _managed_config_from_value(
    path: Path,
    value: object,
    *,
    allow_region_history: bool = False,
) -> dict[str, object]:
        if not isinstance(value, dict):
            raise ReleaseError(f"unsupported managed skeleton config: {path}")
        schema_version = value.get("schema_version")
        if schema_version == 1:
            return dict(value)
        if schema_version != 2:
            raise ReleaseError(f"unsupported managed skeleton config: {path}")
        stamp = value.get("stamp")
        contract_target = value.get("contract_target")
        assets = value.get("assets")
        if (
            not isinstance(stamp, str)
            or not isinstance(contract_target, str)
            or not isinstance(assets, list)
        ):
            raise ReleaseError(f"invalid schema v2 managed skeleton config: {path}")
        whole_files = [stamp, contract_target]
        managed_regions: list[dict[str, str]] = []
        managed_markdown: list[dict[str, object]] = []
        agents_zones: list[dict[str, object]] = []
        for asset in assets:
            if not isinstance(asset, dict):
                raise ReleaseError(f"invalid schema v2 asset in {path}")
            target = asset.get("target")
            strategy = asset.get("strategy")
            if not isinstance(target, str) or not isinstance(strategy, str):
                raise ReleaseError(f"invalid schema v2 asset in {path}")
            if strategy == "whole" and asset.get("agents_zones") is not None:
                zones = asset.get("agents_zones")
                if not isinstance(zones, dict):
                    raise ReleaseError(f"invalid schema v2 AGENTS zones in {path}")
                agents_zones.append({"path": target, "zones": zones})
                continue
            if strategy == "whole" and asset.get("managed_blocks") is not None:
                managed_blocks = asset.get("managed_blocks")
                if (
                    not isinstance(managed_blocks, dict)
                    or managed_blocks.get("format") != "markdown-headings"
                    or not isinstance(managed_blocks.get("headings"), list)
                    or not all(isinstance(item, str) and item for item in managed_blocks["headings"])
                    or not isinstance(managed_blocks.get("additive_headings", []), list)
                    or not all(
                        isinstance(item, str) and item
                        for item in managed_blocks.get("additive_headings", [])
                    )
                    or not isinstance(managed_blocks.get("keyed_tables", []), list)
                    or (
                        not managed_blocks["headings"]
                        and not managed_blocks.get("additive_headings", [])
                        and not managed_blocks.get("keyed_tables", [])
                    )
                ):
                    raise ReleaseError(f"invalid schema v2 managed blocks in {path}")
                managed_markdown.append(
                    {
                        "path": target,
                        "headings": list(managed_blocks["headings"]),
                        "additive_headings": list(
                            managed_blocks.get("additive_headings", [])
                        ),
                        "keyed_tables": list(managed_blocks.get("keyed_tables", [])),
                        "section_layout": asset.get("section_layout"),
                    }
                )
                continue
            if strategy == "seed":
                continue
            if strategy in {"whole", "merge", "retirement"}:
                whole_files.append(target)
                continue
            if strategy != "region" or not isinstance(asset.get("region"), dict):
                raise ReleaseError(f"unsupported schema v2 asset strategy in {path}")
            region = asset["region"]
            begin = region.get("begin")
            end = region.get("end")
            current_sha256 = region.get("current_sha256")
            if (
                not isinstance(begin, str)
                or not isinstance(end, str)
                or begin == end
                or (
                    not allow_region_history
                    and (
                        not isinstance(current_sha256, str)
                        or "historical_sha256" in asset
                        or "historical_sha256" in region
                    )
                )
            ):
                raise ReleaseError(f"invalid schema v2 managed region in {path}")
            managed_regions.append({
                "path": target,
                "begin": begin,
                "end": end,
                "current_sha256": current_sha256,
            })
        return {
            "schema_version": 1,
            "stamp": stamp,
            "whole_files": sorted(set(whole_files)),
            "managed_regions": managed_regions,
            "managed_markdown": managed_markdown,
            "agents_zones": agents_zones,
            "raw_contract": value,
        }


def _parse_managed_config(
    path: Path,
    payload: bytes,
    *,
    allow_region_history: bool = False,
) -> dict[str, object]:
    try:
        value = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"invalid managed skeleton config {path}: {exc}") from exc
    return _managed_config_from_value(
        path,
        value,
        allow_region_history=allow_region_history,
    )


def _load_managed_configs(
    repo: Path,
    snapshot: dict[str, bytes | None] | None = None,
) -> list[tuple[Path, dict[str, object]]]:
    configs: list[tuple[Path, dict[str, object]]] = []
    for host in (".codex",):
        path = repo / host / "managed-skeleton.json"
        payload = _current_bytes(repo, path, snapshot)
        if payload is None:
            continue
        configs.append((path, _parse_managed_config(path, payload)))
    return configs


def _change_ownership(
    repo: Path,
    path: str,
    configs: list[tuple[Path, dict[str, object]]],
    snapshot: dict[str, bytes | None] | None = None,
) -> tuple[Path | None, bool, bool]:
    current = _current_bytes(repo, path, snapshot)
    before = _head_bytes(repo, path)
    for config_path, config in configs:
        for pattern in config.get("whole_files", []):  # type: ignore[union-attr]
            if isinstance(pattern, str) and _path_matches(path, pattern):
                return config_path, True, False
        for raw_region in config.get("managed_regions", []):  # type: ignore[union-attr]
            if not isinstance(raw_region, dict) or raw_region.get("path") != path:
                continue
            begin = raw_region.get("begin")
            end = raw_region.get("end")
            current_expected = raw_region.get("current_sha256")
            if (
                not isinstance(begin, str)
                or not isinstance(end, str)
                or not isinstance(current_expected, str)
            ):
                raise ReleaseError(f"invalid managed region in {config_path}")
            before_managed, before_project = _region_transition_parts(before, begin, end)
            current_managed, current_project = _region_parts(current, begin, end)
            if (
                current_managed is None
                or _sha256_bytes(current_managed) != current_expected
            ):
                raise ReleaseError(
                    f"current managed region does not match its declared hash: {path}"
                )
            if (
                before_managed is not None
                and _sha256_bytes(before_managed) != current_expected
            ):
                raise ReleaseError(
                    f"HEAD managed region does not match the current ownership rule: {path}"
                )
            return (
                config_path,
                before_managed != current_managed,
                before_project != current_project,
            )
        for raw_zones in config.get("agents_zones", []):  # type: ignore[union-attr]
            if not isinstance(raw_zones, dict) or raw_zones.get("path") != path:
                continue
            zones = raw_zones.get("zones")
            if not isinstance(zones, dict):
                raise ReleaseError(f"invalid AGENTS zones in {config_path}")
            before_managed, before_project = _agents_zone_release_parts(before, zones)
            current_managed, current_project = _agents_zone_release_parts(current, zones)
            return (
                config_path,
                before_managed != current_managed,
                before_project != current_project,
            )
        for raw_markdown in config.get("managed_markdown", []):  # type: ignore[union-attr]
            if not isinstance(raw_markdown, dict) or raw_markdown.get("path") != path:
                continue
            headings = raw_markdown.get("headings")
            additive_headings = raw_markdown.get("additive_headings", [])
            keyed_tables = raw_markdown.get("keyed_tables", [])
            section_layout = raw_markdown.get("section_layout")
            if not isinstance(headings, list) or not all(
                isinstance(item, str) for item in headings
            ) or not isinstance(additive_headings, list) or not all(
                isinstance(item, str) for item in additive_headings
            ) or not isinstance(keyed_tables, list) or (
                section_layout is not None and not isinstance(section_layout, dict)
            ):
                raise ReleaseError(f"invalid managed Markdown headings in {config_path}")
            before_managed, before_project = _managed_markdown_parts(
                before, headings, additive_headings, keyed_tables, section_layout
            )
            current_managed, current_project = _managed_markdown_parts(
                current, headings, additive_headings, keyed_tables, section_layout
            )
            return (
                config_path,
                before_managed != current_managed,
                before_project != current_project,
            )
    return None, False, True


def _raw_contract(config_path: Path, config: dict[str, object]) -> dict[str, object]:
    raw = config.get("raw_contract")
    if not isinstance(raw, dict) or raw.get("schema_version") != 2:
        raise ReleaseError(
            f"ownership contract transition requires schema v2: {config_path}"
        )
    assets = raw.get("assets")
    if not isinstance(assets, list):
        raise ReleaseError(f"invalid current ownership contract: {config_path}")
    for asset in assets:
        if not isinstance(asset, dict) or asset.get("agents_zones") is None:
            continue
        zones = asset.get("agents_zones")
        project = zones.get("project") if isinstance(zones, dict) else None
        if (
            asset.get("managed_blocks") is not None
            or asset.get("section_layout") is not None
            or not isinstance(project, dict)
            or "legacy_section_migrations" in project
        ):
            raise ReleaseError(
                "current AGENTS contract must use agents_zones as its only ownership rule"
            )
    return raw


def _transition_source_contract(
    config_path: Path,
    config: dict[str, object],
) -> tuple[dict[str, object], bool]:
    raw = config.get("raw_contract")
    if isinstance(raw, dict) and raw.get("schema_version") == 2:
        return raw, False
    if config.get("schema_version") == 1:
        return config, True
    raise ReleaseError(f"unsupported transition contract: {config_path}")


def _contract_assets(
    config_path: Path,
    contract: dict[str, object],
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    raw_assets = contract.get("assets")
    if not isinstance(raw_assets, list):
        raise ReleaseError(f"invalid schema v2 asset list in {config_path}")
    by_id: dict[str, dict[str, object]] = {}
    by_target: dict[str, dict[str, object]] = {}
    for raw_asset in raw_assets:
        if not isinstance(raw_asset, dict):
            raise ReleaseError(f"invalid schema v2 asset in {config_path}")
        asset_id = raw_asset.get("id")
        target = raw_asset.get("target")
        if not isinstance(asset_id, str) or not asset_id:
            raise ReleaseError(f"invalid stable asset id in {config_path}")
        if not isinstance(target, str) or not target:
            raise ReleaseError(f"invalid asset target in {config_path}")
        if asset_id in by_id or target in by_target:
            raise ReleaseError(f"duplicate asset id or target in {config_path}")
        asset = dict(raw_asset)
        by_id[asset_id] = asset
        by_target[target] = asset
    return by_id, by_target


def _legacy_contract_assets(
    repo: Path,
    config_path: Path,
    legacy_contract: dict[str, object],
    current_contract: dict[str, object],
    old_version: str,
    *,
    explicit_retirements: set[tuple[str, str]] | None = None,
    snapshot: dict[str, bytes | None] | None = None,
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    raw_patterns = legacy_contract.get("whole_files")
    raw_regions = legacy_contract.get("managed_regions")
    if (
        not isinstance(raw_patterns, list)
        or not all(isinstance(item, str) and item for item in raw_patterns)
        or not isinstance(raw_regions, list)
    ):
        raise ReleaseError(f"invalid schema v1 ownership contract: {config_path}")

    current_by_id, _current_by_target = _contract_assets(
        config_path,
        current_contract,
    )
    by_id: dict[str, dict[str, object]] = {}
    by_target: dict[str, dict[str, object]] = {}
    issues: list[dict[str, str]] = []
    for asset_id, current_asset in current_by_id.items():
        target = str(current_asset["target"])
        strategy = current_asset.get("strategy")
        old_asset = dict(current_asset)
        old_asset["_legacy_schema_v1"] = True
        old_asset.pop("current_sha256", None)
        history = current_asset.get("historical_sha256")
        old_history = history.get(old_version) if isinstance(history, dict) else None
        old_asset["historical_sha256"] = (
            {old_version: old_history} if old_history is not None else {}
        )
        merge_validation = old_asset.get("merge_validation")
        if isinstance(merge_validation, dict):
            old_validation = dict(merge_validation)
            old_validation.pop("current_projection_sha256", None)
            old_validation.pop("required_handlers", None)
            projection_history = merge_validation.get(
                "historical_projection_sha256"
            )
            old_projection_history = (
                projection_history.get(old_version)
                if isinstance(projection_history, dict)
                else None
            )
            old_validation["historical_projection_sha256"] = (
                {old_version: old_projection_history}
                if old_projection_history is not None
                else {}
            )
            old_asset["merge_validation"] = old_validation
        managed_blocks = old_asset.get("managed_blocks")
        if isinstance(managed_blocks, dict):
            old_blocks = dict(managed_blocks)
            old_blocks.pop("current_projection_sha256", None)
            projection_history = managed_blocks.get(
                "historical_projection_sha256"
            )
            old_projection_history = (
                projection_history.get(old_version)
                if isinstance(projection_history, dict)
                else None
            )
            old_blocks["historical_projection_sha256"] = (
                {old_version: old_projection_history}
                if old_projection_history is not None
                else {}
            )
            old_asset["managed_blocks"] = old_blocks
        matched_whole = any(
            _path_matches(target, pattern)
            for pattern in raw_patterns
            if isinstance(pattern, str)
        )
        if not matched_whole:
            before = _head_bytes(repo, target)
            projection_managed = (
                strategy == "region"
                or isinstance(current_asset.get("managed_blocks"), dict)
                or isinstance(current_asset.get("agents_zones"), dict)
                or (
                    strategy == "merge"
                    and current_asset.get("merge_policy") == "codex-hooks"
                )
            )
            if before is None or strategy == "seed":
                continue
            trusted_whole = (
                _asset_target_hash(before, old_asset, repo)
                in _declared_asset_hashes(old_asset)
            )
            if not projection_managed and not trusted_whole:
                current = _current_bytes(repo, target, snapshot)
                expected_current = current_asset.get("current_sha256")
                exact_current = (
                    current is not None
                    and isinstance(expected_current, str)
                    and (
                        _sha256_bytes(current)
                        if strategy == "merge"
                        else _asset_target_hash(current, current_asset, repo)
                    )
                    == expected_current
                )
                if (
                    strategy == "retirement"
                    and (asset_id, target) in (explicit_retirements or set())
                    and current is None
                ):
                    old_asset["historical_sha256"] = {
                        old_version: [_asset_target_hash(before, old_asset, repo)]
                    }
                    old_asset["_explicit_untrusted_retirement"] = True
                    by_id[asset_id] = old_asset
                    by_target[target] = old_asset
                    continue
                if (
                    strategy in {"merge", "whole"}
                    and (asset_id, target) in (explicit_retirements or set())
                    and exact_current
                ):
                    old_asset["historical_sha256"] = {
                        old_version: [_asset_target_hash(before, old_asset, repo)]
                    }
                    old_asset["_explicit_untrusted_current"] = True
                    by_id[asset_id] = old_asset
                    by_target[target] = old_asset
                    continue
                issues.append({
                    "asset_id": asset_id,
                    "target": target,
                    "reason": (
                        "pre-existing whole-file target is not trusted for "
                        f"schema v1 baseline {old_version}"
                    ),
                })
                continue
        if matched_whole and strategy in {"region", "seed"}:
            issues.append({
                "asset_id": asset_id,
                "target": target,
                "reason": (
                    "schema v1 whole-file ownership cannot map to "
                    f"schema v2 strategy {strategy!r}"
                ),
            })
            continue

        by_id[asset_id] = old_asset
        by_target[target] = old_asset
    if issues:
        raise TransitionBlocked(issues)
    return by_id, by_target


def _declared_asset_hashes(asset: dict[str, object]) -> set[str]:
    result: set[str] = set()
    current = asset.get("current_sha256")
    if isinstance(current, str):
        result.add(current)
    history = asset.get("historical_sha256", {})
    if isinstance(history, dict):
        for raw_values in history.values():
            values = raw_values if isinstance(raw_values, list) else [raw_values]
            result.update(value for value in values if isinstance(value, str))
    return result


def _asset_ownership_signature(asset: dict[str, object] | None) -> object:
    if asset is None:
        return None

    def scrub(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: scrub(item)
                for key, item in value.items()
                if "sha256" not in key and key not in {"source", "historical_source"}
            }
        if isinstance(value, list):
            return [scrub(item) for item in value]
        return value

    return scrub(asset)


def _asset_content_signature(asset: dict[str, object] | None) -> object:
    if asset is None:
        return None
    region = asset.get("region")
    zones = asset.get("agents_zones")
    public = zones.get("public") if isinstance(zones, dict) else None
    return (
        asset.get("current_sha256"),
        region.get("current_sha256") if isinstance(region, dict) else None,
        public.get("current_sha256") if isinstance(public, dict) else None,
    )


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _codex_hooks_merge_parts(
    payload: bytes,
    target: str,
) -> tuple[list[dict[str, str]], bytes]:
    try:
        document = json.loads(
            payload.decode("utf-8-sig"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"current merge target is invalid JSON: {target}: {exc}") from exc
    hooks = document.get("hooks") if isinstance(document, dict) else None
    if not isinstance(document, dict) or not isinstance(hooks, dict):
        raise ReleaseError(f"current merge target has no hooks object: {target}")

    project_document = copy.deepcopy(document)
    project_hooks = project_document["hooks"]
    required: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for event, groups in list(hooks.items()):
        if not isinstance(event, str) or not isinstance(groups, list):
            raise ReleaseError(f"current merge target has invalid hook groups: {target}")
        project_groups: list[object] = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise ReleaseError(f"current merge target has invalid matcher groups: {target}")
            matcher = group.get("matcher")
            if matcher is not None and not isinstance(matcher, str):
                raise ReleaseError(f"current merge target has invalid matcher: {target}")
            project_handlers: list[object] = []
            for handler in group["hooks"]:
                stage = _dispatcher_stage(handler)
                if stage is None:
                    project_handlers.append(copy.deepcopy(handler))
                    continue
                key = (event, matcher if isinstance(matcher, str) else "", stage)
                if key in seen:
                    raise ReleaseError(
                        "current merge target managed dispatcher drifted: "
                        f"{event}/{key[1]}/{stage}: {target}"
                    )
                seen.add(key)
                required.append({
                    "event": event,
                    "matcher": key[1],
                    "stage": stage,
                    "sha256": _canonical_json_sha256(handler),
                })
            if project_handlers:
                project_group = copy.deepcopy(group)
                project_group["hooks"] = project_handlers
                project_groups.append(project_group)
        if project_groups:
            project_hooks[event] = project_groups
        else:
            project_hooks.pop(event, None)
    required.sort(key=lambda item: (item["event"], item["matcher"], item["stage"]))
    return required, json.dumps(
        project_document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _dispatcher_stage(handler: object) -> str | None:
    if not isinstance(handler, dict):
        return None
    command = str(handler.get("commandWindows") or handler.get("command") or "")
    normalized = command.replace("\\", "/").casefold()
    if ".codex/hooks/hook_dispatcher.py" not in normalized:
        return None
    match = re.search(
        r"hook_dispatcher\.py(?:['\"\)]|\s)+"
        r"(pre-tool|post-read|post-edit|post-shell|post-compact|stop|user-prompt|session-start)",
        normalized,
    )
    return match.group(1) if match else "unknown"


def _validate_codex_hooks_merge_target(
    payload: bytes,
    asset: dict[str, object],
    target: str,
) -> None:
    validation = asset.get("merge_validation")
    if (
        not isinstance(validation, dict)
        or validation.get("format") != "codex-hooks-zones-v2"
        or not isinstance(validation.get("required_handlers"), list)
        or not validation["required_handlers"]
        or not isinstance(validation.get("managed_top_level"), dict)
        or (
            validation.get("managed_top_level_historical") is not None
            and not isinstance(
                validation.get("managed_top_level_historical"),
                dict,
            )
        )
    ):
        raise ReleaseError(f"current merge contract has no trusted managed projection: {target}")
    _current_codex_hooks_zones_parts(payload, asset, target)


def _current_codex_hooks_zones_parts(
    payload: bytes,
    asset: dict[str, object],
    target: str,
) -> tuple[list[dict[str, str]], bytes]:
    validation = asset.get("merge_validation")
    if not isinstance(validation, dict):
        raise ReleaseError(f"current merge contract is invalid: {target}")
    try:
        document = _load_hooks_document(payload, target)
        groups = _expected_hooks_groups(
            document,
            managed_prefix="bridgeforge-codex.project-hook.v1:",
        )
        external = _validate_current_hooks_zones(
            document,
            groups,
            managed_prefixes=("bridgeforge-codex.project-hook.v1:",),
            label=target,
            managed_looking=lambda handler: _dispatcher_stage(handler) is not None,
            managed_top_level=validation.get("managed_top_level"),
            managed_top_level_historical=validation.get(
                "managed_top_level_historical"
            ),
        )
    except HooksOwnershipError as exc:
        raise ReleaseError(str(exc)) from exc
    actual = [
        {
            "id": str(item["id"]),
            "event": str(item["event"]),
            "matcher": str(item["matcher"]),
            "stage": str(_dispatcher_stage(item["handler"])),
            "sha256": str(item["handler_sha256"]),
        }
        for item in groups
    ]
    actual.sort(
        key=lambda item: (
            item["event"],
            item["matcher"],
            item["stage"],
            item["id"],
        )
    )
    expected = validation.get("required_handlers")
    if actual != expected:
        raise ReleaseError(f"current merge target managed projection drifted: {target}")
    projection = _hooks_canonical_json_sha256(actual)
    if projection != validation.get("current_projection_sha256"):
        raise ReleaseError(f"current merge contract projection hash is invalid: {target}")
    return actual, json.dumps(
        external,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _validate_unchanged_merge_transition(
    repo: Path,
    target: str,
    asset: dict[str, object],
    snapshot: dict[str, bytes | None] | None = None,
) -> None:
    before = _head_bytes(repo, target)
    current = _current_bytes(repo, target, snapshot)
    if before is None or current is None:
        raise ReleaseError(f"unchanged merge target is missing: {target}")
    if _git_blob_bytes(before) != _git_blob_bytes(current):
        raise ReleaseError(f"merge target changed without being reported: {target}")
    if asset.get("merge_policy") != "codex-hooks":
        raise ReleaseError(f"merge transition has no supported no-op validator: {target}")
    _validate_codex_hooks_merge_target(current, asset, target)


def _projection_history(
    validation: object,
    version: str,
) -> set[str]:
    if not isinstance(validation, dict):
        return set()
    history = validation.get("historical_projection_sha256")
    if not isinstance(history, dict):
        return set()
    return _history_values_for_version(history, version)


def _history_values_for_version(raw: object, version: str) -> set[str]:
    if not isinstance(raw, dict):
        return set()
    values = raw.get(version)
    candidates = values if isinstance(values, list) else [values]
    return {value for value in candidates if isinstance(value, str)}


def _managed_blocks_parts(
    payload: bytes | None,
    asset: dict[str, object],
    target: str,
) -> tuple[bytes | None, bytes | None]:
    managed = asset.get("managed_blocks")
    if not isinstance(managed, dict):
        raise ReleaseError(f"managed Markdown contract is missing: {target}")
    headings = managed.get("headings")
    additive = managed.get("additive_headings", [])
    keyed = managed.get("keyed_tables", [])
    layout = asset.get("section_layout")
    if (
        not isinstance(headings, list)
        or not all(isinstance(item, str) for item in headings)
        or not isinstance(additive, list)
        or not all(isinstance(item, str) for item in additive)
        or not isinstance(keyed, list)
        or (layout is not None and not isinstance(layout, dict))
    ):
        raise ReleaseError(f"managed Markdown contract is invalid: {target}")
    return _managed_markdown_parts(payload, headings, additive, keyed, layout)


def _current_projection_hash(
    contract: object,
    label: str,
) -> str:
    if not isinstance(contract, dict):
        raise ReleaseError(f"{label} contract is invalid")
    expected = contract.get("current_projection_sha256")
    if not isinstance(expected, str):
        raise ReleaseError(f"{label} contract has no current managed projection")
    return expected


def _asset_target_hash(payload: bytes, asset: dict[str, object], repo: Path) -> str:
    normalized = _git_blob_bytes(payload)
    if asset.get("render") == "project-name":
        try:
            text = normalized.decode("utf-8-sig")
        except UnicodeDecodeError:
            return _sha256_bytes(normalized)
        normalized = text.replace(repo.name, "{{PROJECT_NAME}}").encode("utf-8")
    return _sha256_bytes(normalized)


def _agents_public_hash(payload: bytes) -> str:
    project_clone = re.compile(
        br"(?m)^(git clone <repo_url> )"
        br"([A-Za-z0-9._-]+|\{\{PROJECT_NAME\}\})"
        br"( && cd )\2([ \t]*)$"
    )
    normalized = project_clone.sub(
        br"\1{{PROJECT_NAME}}\3{{PROJECT_NAME}}\4",
        _git_blob_bytes(payload),
    )
    return _sha256_bytes(normalized)


def _accepted_public_hashes(asset: dict[str, object]) -> set[str]:
    zones = asset.get("agents_zones")
    if not isinstance(zones, dict):
        return set()
    public = zones.get("public")
    if not isinstance(public, dict):
        return set()
    result: set[str] = set()
    current = public.get("current_sha256")
    if isinstance(current, str):
        result.add(current)
    history = public.get("historical_sha256", {})
    if isinstance(history, dict):
        for raw_values in history.values():
            values = raw_values if isinstance(raw_values, list) else [raw_values]
            result.update(value for value in values if isinstance(value, str))
    return result


def _transition_agents_zone_ownership(
    before: bytes | None,
    current: bytes | None,
    old_asset: dict[str, object] | None,
    current_asset: dict[str, object],
    current_path: str | None,
) -> tuple[bool, bool]:
    zones = current_asset.get("agents_zones")
    if not isinstance(zones, dict):
        raise ReleaseError(
            f"current AGENTS ownership contract is invalid: {current_path}"
        )
    try:
        current_public, current_project = _agents_zone_release_parts(current, zones)
    except ReleaseError as exc:
        raise ReleaseError(f"current AGENTS ownership is invalid: {exc}") from exc
    public = zones.get("public")
    expected_public = public.get("current_sha256") if isinstance(public, dict) else None
    if (
        current_public is None
        or current_project is None
        or not isinstance(expected_public, str)
        or _agents_public_hash(current_public) != expected_public
    ):
        raise ReleaseError(
            "current AGENTS public zone does not match the exact current contract"
        )
    if before is None:
        return True, False
    if (
        old_asset is None
        or old_asset.get("_legacy_schema_v1") is True
        or not isinstance(old_asset.get("agents_zones"), dict)
    ):
        return True, True
    old_zones = old_asset["agents_zones"]
    try:
        old_public, old_project = _agents_zone_release_parts(before, old_zones)
    except ReleaseError as exc:
        raise ReleaseError(f"HEAD AGENTS ownership is invalid: {exc}") from exc
    accepted_old_public = _accepted_public_hashes(old_asset)
    if (
        old_public is None
        or old_project is None
        or _agents_public_hash(old_public) not in accepted_old_public
    ):
        raise ReleaseError(
            "HEAD AGENTS public zone does not match its trusted contract"
        )
    return old_public != current_public, old_project != current_project


def _read_stamp(payload: bytes | None, label: str) -> str:
    if payload is None:
        raise ReleaseError(f"{label} skeleton stamp is missing")
    try:
        value = payload.decode("utf-8-sig").strip()
    except UnicodeDecodeError as exc:
        raise ReleaseError(f"{label} skeleton stamp is not UTF-8") from exc
    parse_semver(value)
    return value


def _transition_asset_ownership(
    repo: Path,
    old_path: str | None,
    current_path: str | None,
    old_asset: dict[str, object] | None,
    current_asset: dict[str, object] | None,
    old_version: str,
    snapshot: dict[str, bytes | None] | None = None,
) -> tuple[bool, bool]:
    before = _head_bytes(repo, old_path) if old_path is not None else None
    current = (
        _current_bytes(repo, current_path, snapshot)
        if current_path is not None
        else None
    )
    if current_asset is None:
        if old_asset is None:
            return False, True
        if before is None or _asset_target_hash(before, old_asset, repo) not in _declared_asset_hashes(old_asset):
            raise ReleaseError(
                f"retired asset does not match its trusted HEAD hash: {old_path}"
            )
        return True, False

    strategy = current_asset.get("strategy")
    if strategy == "seed":
        return False, before != current
    if strategy == "merge" and current_asset.get("merge_policy") == "codex-hooks":
        if before is None or current is None:
            raise ReleaseError(f"merge transition target is missing: {current_path}")
        current_validation = current_asset.get("merge_validation")
        current_required, current_project = _current_codex_hooks_zones_parts(
            current,
            current_asset,
            str(current_path),
        )
        current_projection = _canonical_json_sha256(current_required)
        if current_projection != _current_projection_hash(
            current_validation,
            f"current merge {current_path}",
        ):
            raise ReleaseError(
                f"current merge target does not match its managed projection: {current_path}"
            )
        old_validation = old_asset.get("merge_validation") if old_asset is not None else None
        old_required = (
            old_validation.get("required_handlers")
            if isinstance(old_validation, dict)
            else None
        )
        if not isinstance(old_required, list) or not old_required:
            if (
                old_asset is None
                or _asset_target_hash(before, old_asset, repo)
                not in _declared_asset_hashes(old_asset)
            ):
                raise ReleaseError(
                    f"HEAD merge contract has no trusted managed projection: {old_path}"
                )
            old_project = json.dumps(
                {"hooks": {}},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            return True, old_project != current_project
        try:
            current_document = _load_hooks_document(current, str(current_path))
            current_groups = _expected_hooks_groups(
                current_document,
                managed_prefix="bridgeforge-codex.project-hook.v1:",
            )
            current_ids = {
                (
                    str(item["event"]),
                    str(item["matcher"]),
                    str(_dispatcher_stage(item["handler"])),
                ): str(item["id"])
                for item in current_groups
            }
            legacy_handlers: list[dict[str, str]] = []
            for item in old_required:
                if not isinstance(item, dict):
                    raise HooksOwnershipError("HEAD merge contract handler is invalid")
                key = (
                    str(item.get("event", "")),
                    str(item.get("matcher", "")),
                    str(item.get("stage", "")),
                )
                managed_id = item.get("id") or current_ids.get(key)
                digest = item.get("sha256") or item.get("handler_sha256")
                if not isinstance(managed_id, str) or not isinstance(digest, str):
                    raise HooksOwnershipError("HEAD merge contract handler cannot map to current id")
                legacy_handlers.append({
                    "id": managed_id,
                    "event": key[0],
                    "matcher": key[1],
                    "handler_sha256": digest,
                })
            old_document = _load_hooks_document(before, str(old_path))
            _canonical_old, old_external, receipts = _canonicalize_hooks_zones(
                old_document,
                current_groups,
                managed_prefixes=("bridgeforge-codex.project-hook.v1:",),
                label=str(old_path),
                managed_looking=lambda handler: _dispatcher_stage(handler) is not None,
                legacy_handlers=legacy_handlers,
                managed_top_level=current_validation.get("managed_top_level")
                if isinstance(current_validation, dict)
                else None,
                managed_top_level_historical=current_validation.get(
                    "managed_top_level_historical"
                )
                if isinstance(current_validation, dict)
                else None,
            )
        except HooksOwnershipError as exc:
            raise ReleaseError(str(exc)) from exc
        if any(item["action"] == "add-missing" for item in receipts):
            raise ReleaseError(f"HEAD merge target is missing a trusted managed handler: {old_path}")
        old_project = json.dumps(
            old_external,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        old_projection = _canonical_json_sha256(old_required)
        return old_projection != current_projection, old_project != current_project
    if current_asset.get("agents_zones") is not None:
        return _transition_agents_zone_ownership(
            before,
            current,
            old_asset,
            current_asset,
            current_path,
        )
    if isinstance(current_asset.get("managed_blocks"), dict):
        if current is None:
            raise ReleaseError(f"current managed Markdown asset is missing: {current_path}")
        current_managed, current_project = _managed_blocks_parts(
            current, current_asset, str(current_path)
        )
        current_contract = current_asset["managed_blocks"]
        current_projection = _sha256_bytes(current_managed or b"")
        if current_projection != _current_projection_hash(
            current_contract,
            f"current managed Markdown {current_path}",
        ):
            raise ReleaseError(
                f"current managed Markdown does not match its managed projection: {current_path}"
            )
        old_parser = (
            old_asset
            if old_asset is not None and isinstance(old_asset.get("managed_blocks"), dict)
            else current_asset
        )
        old_managed, old_project = _managed_blocks_parts(
            before, old_parser, str(old_path)
        )
        old_projection = _sha256_bytes(old_managed or b"")
        accepted_old = _projection_history(current_contract, old_version)
        if old_asset is not None:
            old_contract = old_asset.get("managed_blocks")
            if isinstance(old_contract, dict):
                old_current = old_contract.get("current_projection_sha256")
                if isinstance(old_current, str):
                    accepted_old.add(old_current)
            if before is not None and _asset_target_hash(before, old_asset, repo) in _declared_asset_hashes(old_asset):
                accepted_old.add(old_projection)
        if old_projection not in accepted_old:
            raise ReleaseError(
                f"HEAD managed Markdown does not match trusted transition history: {old_path}"
            )
        return old_projection != current_projection, old_project != current_project
    if strategy in {"whole", "merge", "retirement"}:
        if before is not None and (
            old_asset is None
            or _asset_target_hash(before, old_asset, repo)
            not in _declared_asset_hashes(old_asset)
        ):
            raise ReleaseError(
                f"HEAD asset does not match its trusted contract hash: {old_path}"
            )
        if (
            strategy == "retirement"
            and old_asset is not None
            and old_asset.get("_explicit_untrusted_retirement") is True
        ):
            raise ReleaseError("explicit retirement adaptation is required")
        if current is not None:
            expected = current_asset.get("current_sha256")
            if not isinstance(expected, str) or _asset_target_hash(
                current, current_asset, repo
            ) != expected:
                raise ReleaseError(
                    f"current asset does not match its declared hash: {current_path}"
                )
        elif strategy != "retirement":
            raise ReleaseError(f"current managed asset is missing: {current_path}")
        return True, False
    if strategy == "region":
        current_region = current_asset.get("region")
        if not isinstance(current_region, dict):
            raise ReleaseError(
                f"current managed region contract is invalid: {current_path}"
            )
        current_parts = _region_parts(
            current,
            str(current_region.get("begin")),
            str(current_region.get("end")),
        )
        current_expected = current_region.get("current_sha256")
        if (
            current_parts[0] is None
            or not isinstance(current_expected, str)
            or _sha256_bytes(current_parts[0]) != current_expected
        ):
            raise ReleaseError(
                f"current managed region does not match its declared hash: {current_path}"
            )
        old_parts = _region_transition_parts(
            before,
            str(current_region.get("begin")),
            str(current_region.get("end")),
        )
        if old_parts[0] is None:
            return True, True
        if _sha256_bytes(old_parts[0]) != current_expected:
            raise ReleaseError(
                f"HEAD managed region does not match the current ownership rule: {old_path}"
            )
        return old_parts[0] != current_parts[0], old_parts[1] != current_parts[1]
    raise ReleaseError(
        f"unsupported transition asset strategy for {current_path}: {strategy!r}"
    )


def _classify_contract_transition(
    repo: Path,
    changed_paths: set[str],
    config_path: Path,
    current_config: dict[str, object],
    head_payload: bytes,
    prospective_skeleton_version: str | None = None,
    snapshot: dict[str, bytes | None] | None = None,
    explicit_adaptations: dict[tuple[str, str], dict[str, object]] | None = None,
    consumed_adaptations: set[tuple[str, str]] | None = None,
) -> str:
    current_contract = _raw_contract(config_path, current_config)
    head_config = _parse_managed_config(
        config_path,
        head_payload,
        allow_region_history=True,
    )
    head_contract, legacy_head = _transition_source_contract(
        config_path,
        head_config,
    )
    relative_config = config_path.relative_to(repo).as_posix()
    current_target = current_contract.get("contract_target")
    head_target = (
        relative_config if legacy_head else head_contract.get("contract_target")
    )
    if current_target != relative_config or head_target != relative_config:
        raise ReleaseError("ownership contract target does not match its repository path")
    if relative_config not in changed_paths:
        raise ReleaseError("ownership contract changed without staging its contract target")

    old_stamp = head_contract.get("stamp")
    new_stamp = current_contract.get("stamp")
    if not isinstance(old_stamp, str) or not isinstance(new_stamp, str):
        raise ReleaseError("ownership contract transition has an invalid stamp path")
    old_version = _read_stamp(_head_bytes(repo, old_stamp), "HEAD")
    if legacy_head:
        minimum_version = current_contract.get("minimum_supported_version")
        if not isinstance(minimum_version, str):
            raise ReleaseError(
                "current ownership contract has no minimum_supported_version"
            )
        parse_semver(minimum_version)
        if parse_semver(old_version) < parse_semver(minimum_version):
            raise ReleaseError(
                "HEAD schema v1 skeleton version "
                f"{old_version} is below minimum supported {minimum_version}"
            )

    history = current_contract.get("contract_historical_sha256")
    raw_history = history.get(old_version) if isinstance(history, dict) else None
    historical = raw_history if isinstance(raw_history, list) else [raw_history]
    head_hash = _sha256_bytes(head_payload)
    if head_hash not in {value for value in historical if isinstance(value, str)}:
        raise ReleaseError(
            f"HEAD ownership contract {head_hash} is not trusted for skeleton {old_version}"
        )

    if prospective_skeleton_version is None:
        new_version = _read_stamp(
            _current_bytes(repo, new_stamp, snapshot),
            "current",
        )
    else:
        new_version = _read_stamp(
            (prospective_skeleton_version + "\n").encode("utf-8"),
            "prospective current",
        )
    if parse_semver(new_version) <= parse_semver(old_version):
        raise ReleaseError("current skeleton stamp must be newer than the HEAD stamp")
    contract_release = current_contract.get("release_version")
    if not isinstance(contract_release, str):
        raise ReleaseError("current ownership contract has no release_version binding")
    parse_semver(contract_release)
    if contract_release != new_version:
        raise ReleaseError(
            "current skeleton stamp does not match the ownership contract release_version"
        )
    required_stamp_paths = {old_stamp, new_stamp}
    if not required_stamp_paths.issubset(changed_paths):
        missing = ", ".join(sorted(required_stamp_paths - changed_paths))
        raise ReleaseError(f"ownership contract transition is missing changed stamp paths: {missing}")

    if legacy_head:
        old_by_id, _old_by_target = _legacy_contract_assets(
            repo,
            config_path,
            head_contract,
            current_contract,
            old_version,
            explicit_retirements=set(explicit_adaptations or {}),
            snapshot=snapshot,
        )
    else:
        old_by_id, _old_by_target = _contract_assets(config_path, head_contract)
    current_by_id, _current_by_target = _contract_assets(config_path, current_contract)
    managed: set[str] = {relative_config, old_stamp, new_stamp}
    project: set[str] = set()
    issues: list[dict[str, str]] = []
    handled_paths = set(managed)
    for asset_id in sorted(set(old_by_id) | set(current_by_id)):
        old_asset = old_by_id.get(asset_id)
        current_asset = current_by_id.get(asset_id)
        old_target = str(old_asset["target"]) if old_asset is not None else None
        current_target = (
            str(current_asset["target"]) if current_asset is not None else None
        )
        asset_paths = {item for item in (old_target, current_target) if item is not None}
        changed_asset_paths = asset_paths & changed_paths
        identity_transition = (
            old_asset is None
            or current_asset is None
            or old_target != current_target
        )
        metadata_transition = (
            _asset_ownership_signature(old_asset)
            != _asset_ownership_signature(current_asset)
        )
        content_transition = (
            _asset_content_signature(old_asset)
            != _asset_content_signature(current_asset)
        )
        if (
            not changed_asset_paths
            and not identity_transition
            and not metadata_transition
            and not content_transition
        ):
            continue
        managed_strategy = (
            current_asset.get("strategy") if current_asset is not None
            else old_asset.get("strategy") if old_asset is not None
            else None
        )
        legal_merge_noop = (
            not changed_asset_paths
            and not identity_transition
            and managed_strategy == "merge"
            and current_asset is not None
            and (metadata_transition or content_transition)
        )
        if legal_merge_noop:
            handled_paths.update(asset_paths)
            try:
                _validate_unchanged_merge_transition(
                    repo,
                    str(current_target),
                    current_asset,
                    snapshot,
                )
            except ReleaseError as exc:
                adaptation_key = (asset_id, str(current_target))
                if adaptation_key in (explicit_adaptations or {}):
                    if consumed_adaptations is not None:
                        consumed_adaptations.add(adaptation_key)
                    continue
                issues.append({
                    "asset_id": asset_id,
                    "target": str(current_target),
                    "reason": str(exc),
                })
            continue
        legal_agents_noop = (
            not changed_asset_paths
            and not identity_transition
            and current_asset is not None
            and old_asset is not None
            and old_asset.get("_legacy_schema_v1") is not True
            and isinstance(current_asset.get("agents_zones"), dict)
            and (metadata_transition or content_transition)
        )
        if legal_agents_noop:
            handled_paths.update(asset_paths)
            try:
                _managed_changed, project_changed = _transition_asset_ownership(
                    repo,
                    old_target,
                    current_target,
                    old_asset,
                    current_asset,
                    old_version,
                    snapshot,
                )
                if project_changed:
                    raise ReleaseError(
                        "unchanged AGENTS target has inconsistent project-zone ownership"
                    )
            except ReleaseError as exc:
                adaptation_key = (asset_id, str(current_target))
                if adaptation_key in (explicit_adaptations or {}):
                    if consumed_adaptations is not None:
                        consumed_adaptations.add(adaptation_key)
                    continue
                issues.append({
                    "asset_id": asset_id,
                    "target": str(current_target),
                    "reason": str(exc),
                })
            continue
        if (
            (identity_transition or metadata_transition or content_transition)
            and managed_strategy != "seed"
            and changed_asset_paths != asset_paths
        ):
            adaptation_key = (
                asset_id,
                str(current_target or old_target or relative_config),
            )
            if adaptation_key in (explicit_adaptations or {}):
                if consumed_adaptations is not None:
                    consumed_adaptations.add(adaptation_key)
                handled_paths.update(asset_paths)
                managed.update(asset_paths)
                continue
            missing = ", ".join(sorted(asset_paths - changed_asset_paths))
            issues.append({
                "asset_id": asset_id,
                "target": str(current_target or old_target or relative_config),
                "reason": f"target migration is missing changed paths: {missing}",
            })
            continue
        handled_paths.update(asset_paths)
        try:
            managed_changed, project_changed = _transition_asset_ownership(
                repo,
                old_target,
                current_target,
                old_asset,
                current_asset,
                old_version,
                snapshot,
            )
        except ReleaseError as exc:
            adaptation_key = (
                asset_id,
                str(current_target or old_target or relative_config),
            )
            if adaptation_key in (explicit_adaptations or {}):
                if consumed_adaptations is not None:
                    consumed_adaptations.add(adaptation_key)
                managed.update(changed_asset_paths)
                continue
            issues.append({
                "asset_id": asset_id,
                "target": str(current_target or old_target or relative_config),
                "reason": str(exc),
            })
            continue
        if managed_changed:
            managed.update(changed_asset_paths)
        if project_changed:
            project.update(changed_asset_paths)
    project.update(changed_paths - handled_paths)
    if issues:
        raise TransitionBlocked(issues)
    if managed and project:
        return "mixed"
    if managed:
        return "skeleton-only"
    return "project"


def is_bridgeforge_factory(repo: Path) -> bool:
    return (
        (repo / "templates" / "managed-skeleton.json").is_file()
        and (repo / "skills" / "bridgeforge-codex" / "SKILL.md").is_file()
    )


def _classify_snapshot(
    repo: Path,
    changed_paths: set[str],
    *,
    prospective_skeleton_version: str | None = None,
    snapshot: dict[str, bytes | None] | None = None,
    explicit_adaptations: dict[tuple[str, str], dict[str, object]] | None = None,
    consumed_adaptations: set[tuple[str, str]] | None = None,
) -> str:
    if is_bridgeforge_factory(repo):
        return "factory"
    configs = _load_managed_configs(repo, snapshot)
    if not configs:
        return "project"

    transitions: list[tuple[Path, dict[str, object], bytes]] = []
    for config_path, config in configs:
        relative = config_path.relative_to(repo).as_posix()
        head_payload = _head_bytes(repo, relative)
        if head_payload is None:
            continue
        current_payload = _current_bytes(repo, config_path, snapshot)
        if current_payload is None:
            continue
        if _git_blob_bytes(head_payload) != _git_blob_bytes(current_payload):
            transitions.append((config_path, config, head_payload))
    if transitions:
        if len(transitions) != 1 or len(configs) != 1:
            raise ReleaseError("multiple simultaneous ownership contract transitions are unsupported")
        return _classify_contract_transition(
            repo,
            changed_paths,
            transitions[0][0],
            transitions[0][1],
            transitions[0][2],
            prospective_skeleton_version,
            snapshot,
            explicit_adaptations,
            consumed_adaptations,
        )

    changed_stamps: set[Path] = set()
    for config_path, config in configs:
        stamp = config.get("stamp")
        if isinstance(stamp, str) and stamp in changed_paths:
            changed_stamps.add(config_path)

    managed: set[str] = set()
    project: set[str] = set()
    owners_with_changes: set[Path] = set()
    managed_owners: dict[str, Path] = {}
    for path in changed_paths:
        matching_adaptations = [
            key
            for key in (explicit_adaptations or {})
            if key[1] == path
        ]
        try:
            owner, managed_changed, project_changed = _change_ownership(
                repo,
                path,
                configs,
                snapshot,
            )
        except ReleaseError as exc:
            if len(matching_adaptations) != 1:
                asset_id = "contract.managed-skeleton"
                for config_path, config in configs:
                    try:
                        _by_id, by_target = _contract_assets(
                            config_path,
                            _raw_contract(config_path, config),
                        )
                    except ReleaseError:
                        continue
                    asset = by_target.get(path)
                    if isinstance(asset, dict) and isinstance(asset.get("id"), str):
                        asset_id = str(asset["id"])
                        break
                raise TransitionBlocked([{
                    "asset_id": asset_id,
                    "target": path,
                    "reason": str(exc),
                }]) from exc
            if consumed_adaptations is not None:
                consumed_adaptations.add(matching_adaptations[0])
            owner, managed_changed, project_changed = None, True, False
        if managed_changed:
            managed.add(path)
            if owner is not None and not matching_adaptations:
                owners_with_changes.add(owner)
                managed_owners[path] = owner
            elif matching_adaptations:
                if consumed_adaptations is not None:
                    consumed_adaptations.add(matching_adaptations[0])
        if project_changed:
            project.add(path)

    unauthorized = owners_with_changes - changed_stamps
    if unauthorized:
        config_assets: dict[Path, dict[str, dict[str, object]]] = {}
        for config_path, config in configs:
            if config_path not in unauthorized:
                continue
            try:
                config_assets[config_path] = _contract_assets(
                    config_path,
                    _raw_contract(config_path, config),
                )[1]
            except ReleaseError:
                config_assets[config_path] = {}
        issues: list[dict[str, str]] = []
        for path in sorted(managed):
            owner = managed_owners.get(path)
            if owner not in unauthorized:
                continue
            asset = config_assets.get(owner, {}).get(path)
            issues.append({
                "asset_id": str(
                    asset.get("id")
                    if isinstance(asset, dict)
                    else "contract.managed-skeleton"
                ),
                "target": path,
                "reason": (
                    "managed skeleton files changed outside $bridgeforge-codex; "
                    "missing updated skeleton stamp for "
                    + str(owner.relative_to(repo))
                ),
            })
        raise TransitionBlocked(issues)
    if managed and not project:
        return "skeleton-only"
    if managed and project:
        return "mixed"
    return "project"


def collect_changed_paths(repo: Path) -> set[str]:
    """Return the same unstaged, staged, and untracked path union used by git-sync."""

    paths: set[str] = set()
    commands = (
        ("diff", "--name-only"),
        ("diff", "--cached", "--name-only"),
        ("ls-files", "--others", "--exclude-standard"),
    )
    for command in commands:
        try:
            result = subprocess.run(
                [
                    "git",
                    "-c",
                    f"safe.directory={repo.resolve().as_posix()}",
                    *command,
                ],
                cwd=repo,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ReleaseError(f"git changed-path scan could not complete: {exc}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise ReleaseError(f"git changed-path scan failed: {detail}")
        paths.update(
            line.strip().replace("\\", "/")
            for line in result.stdout.splitlines()
            if line.strip()
        )
    return paths


def _head_commit(repo: Path) -> str:
    result = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={repo.resolve().as_posix()}",
            "rev-parse",
            "--verify",
            "HEAD",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ReleaseError(f"explicit adaptation cannot inspect HEAD: {detail}")
    return result.stdout.strip()


def _optional_payload_hash(payload: bytes | None) -> str | None:
    return None if payload is None else _sha256_bytes(payload)


def _explicit_adaptation_context(
    repo: Path,
    snapshot: dict[str, bytes | None],
    before_snapshot: dict[str, bytes | None] | None,
    asset_id: str,
    target: str,
    allowed_adaptations: set[tuple[str, str]],
) -> tuple[
    str | None,
    str | None,
    dict[str, object] | None,
    dict[str, object] | None,
    str,
    dict[str, object] | None,
]:
    matches: list[
        tuple[
            str | None,
            str | None,
            dict[str, object] | None,
            dict[str, object] | None,
            str,
            dict[str, object] | None,
        ]
    ] = []
    for config_path, current_config in _load_managed_configs(repo, snapshot):
        current_contract = _raw_contract(config_path, current_config)
        current_by_id, _current_by_target = _contract_assets(
            config_path,
            current_contract,
        )
        head_payload = _head_bytes(repo, config_path.relative_to(repo).as_posix())
        current_payload = _current_bytes(repo, config_path, snapshot)
        old_by_id = current_by_id
        old_version = str(current_contract.get("release_version", ""))
        if (
            head_payload is not None
            and current_payload is not None
            and _git_blob_bytes(head_payload) != _git_blob_bytes(current_payload)
        ):
            head_config = _parse_managed_config(
                config_path,
                head_payload,
                allow_region_history=True,
            )
            head_contract, legacy_head = _transition_source_contract(
                config_path,
                head_config,
            )
            old_stamp = head_contract.get("stamp")
            if not isinstance(old_stamp, str):
                raise ReleaseError("explicit adaptation HEAD contract has no stamp")
            old_version = _read_stamp(_head_bytes(repo, old_stamp), "HEAD")
            if legacy_head:
                old_by_id, _old_by_target = _legacy_contract_assets(
                    repo,
                    config_path,
                    head_contract,
                    current_contract,
                    old_version,
                    explicit_retirements=allowed_adaptations,
                    snapshot=snapshot,
                )
            else:
                old_by_id, _old_by_target = _contract_assets(
                    config_path,
                    head_contract,
                )
        old_asset = old_by_id.get(asset_id)
        current_asset = current_by_id.get(asset_id)
        old_target = str(old_asset["target"]) if old_asset is not None else None
        current_target = (
            str(current_asset["target"]) if current_asset is not None else None
        )
        if target not in {old_target, current_target}:
            continue
        current_before_asset = None
        if (
            current_asset is not None
            and current_payload is not None
            and (
                current_asset.get("strategy") == "merge"
                or isinstance(current_asset.get("managed_blocks"), dict)
            )
        ):
            current_before_asset = _trusted_current_before_contract_asset(
                repo,
                config_path,
                current_contract,
                current_payload,
                asset_id,
                target,
                snapshot,
                before_snapshot,
            )
        matches.append(
            (
                old_target,
                current_target,
                old_asset,
                current_asset,
                old_version,
                current_before_asset,
            )
        )
    if len(matches) != 1:
        raise ReleaseError(
            f"explicit adaptation asset context is ambiguous: {asset_id}:{target}"
        )
    return matches[0]


def _schema_v1_handler_map(
    payload: bytes | None,
    target: str,
) -> dict[tuple[str, str, str], dict[str, object]]:
    document = _load_hooks_document(payload, target)
    hooks = document.get("hooks")
    if not isinstance(hooks, dict):
        raise ReleaseError("explicit adaptation schema v1 hooks are invalid")
    result: dict[tuple[str, str, str], dict[str, object]] = {}
    for event, groups in hooks.items():
        if not isinstance(event, str) or not isinstance(groups, list):
            raise ReleaseError(
                "explicit adaptation schema v1 hook groups are invalid"
            )
        for group in groups:
            if not isinstance(group, dict) or not isinstance(
                group.get("hooks"), list
            ):
                raise ReleaseError(
                    "explicit adaptation schema v1 hook group is invalid"
                )
            matcher = str(group.get("matcher", ""))
            for handler in group["hooks"]:
                if not isinstance(handler, dict):
                    raise ReleaseError(
                        "explicit adaptation schema v1 handler is invalid"
                    )
                stage = _dispatcher_stage(handler)
                if stage is None:
                    continue
                key = (event, matcher, stage)
                if key in result:
                    raise ReleaseError(
                        "explicit adaptation schema v1 dispatcher is duplicated"
                    )
                result[key] = copy.deepcopy(handler)
    return result


def _handler_without_managed_id_hash(handler: dict[str, object]) -> str:
    normalized = copy.deepcopy(handler)
    normalized.pop("bridgeforgeCodexId", None)
    return _canonical_json_sha256(normalized)


def _keyed_projection_rows(payload: bytes, heading: str) -> tuple[str, dict[str, str]]:
    text = payload.decode("utf-8-sig")
    lines = text.splitlines()
    if len(lines) < 2 or not lines[1].startswith("header="):
        raise ReleaseError(
            f"explicit adaptation schema v1 keyed projection is invalid: {heading}"
        )
    return lines[1], {
        line.split("=", 1)[0]: line
        for line in lines[2:]
        if line and "=" in line
    }


def _schema_v1_markdown_projection_hash(
    current_before: bytes | None,
    prospective: bytes | None,
    asset: dict[str, object],
    target: str,
) -> str:
    if current_before is None or prospective is None:
        raise ReleaseError(
            "explicit adaptation schema v1 current-before Markdown is missing"
        )
    managed_blocks = asset.get("managed_blocks")
    if not isinstance(managed_blocks, dict) or asset.get("section_layout") is not None:
        raise ReleaseError(
            "explicit adaptation schema v1 Markdown ownership is unsupported"
        )
    headings = managed_blocks.get("headings", [])
    additive = managed_blocks.get("additive_headings", [])
    keyed = managed_blocks.get("keyed_tables", [])
    if (
        not isinstance(headings, list)
        or not isinstance(additive, list)
        or not isinstance(keyed, list)
    ):
        raise ReleaseError(
            "explicit adaptation schema v1 Markdown contract is invalid"
        )
    owned_headings = [str(item) for item in headings + additive]
    before_spans = _markdown_heading_spans(current_before, owned_headings)
    prospective_spans = _markdown_heading_spans(prospective, owned_headings)
    before_order = [
        heading
        for heading, _span in sorted(
            before_spans.items(), key=lambda item: item[1][0]
        )
    ]
    prospective_order = [
        heading
        for heading, _span in sorted(
            prospective_spans.items(), key=lambda item: item[1][0]
        )
    ]
    if before_order != [
        heading for heading in prospective_order if heading in set(before_order)
    ]:
        raise ReleaseError(
            "explicit adaptation schema v1 Markdown heading order drifted"
        )
    for heading, (start, finish) in before_spans.items():
        prospective_span = prospective_spans.get(heading)
        if prospective_span is None:
            raise ReleaseError(
                "explicit adaptation schema v1 Markdown heading is not current"
            )
        current_start, current_finish = prospective_span
        if _git_blob_bytes(current_before[start:finish]).rstrip() != _git_blob_bytes(
            prospective[current_start:current_finish]
        ).rstrip():
            raise ReleaseError(
                "explicit adaptation schema v1 Markdown managed heading drifted"
            )
    for table in keyed:
        if not isinstance(table, dict) or not isinstance(table.get("heading"), str):
            raise ReleaseError(
                "explicit adaptation schema v1 keyed-table contract is invalid"
            )
        heading = str(table["heading"])
        managed_keys = table.get("managed_keys")
        if not isinstance(managed_keys, list):
            raise ReleaseError(
                "explicit adaptation schema v1 keyed-table keys are invalid"
            )
        before_projection, _before_project = _keyed_table_parts(
            current_before, heading, [str(item) for item in managed_keys]
        )
        current_projection, _current_project = _keyed_table_parts(
            prospective, heading, [str(item) for item in managed_keys]
        )
        if before_projection is None or current_projection is None:
            raise ReleaseError(
                "explicit adaptation schema v1 keyed-table target is missing"
            )
        if before_projection == f"{heading}=<MISSING>".encode("utf-8"):
            continue
        before_header, before_rows = _keyed_projection_rows(
            before_projection, heading
        )
        current_header, current_rows = _keyed_projection_rows(
            current_projection, heading
        )
        if before_header != current_header or any(
            current_rows.get(key) != value for key, value in before_rows.items()
        ):
            raise ReleaseError(
                "explicit adaptation schema v1 keyed-table managed row drifted"
            )
    managed, project = _managed_blocks_parts(current_before, asset, target)
    if managed is None or project is None:
        raise ReleaseError(
            "explicit adaptation schema v1 current-before Markdown is invalid"
        )
    return _sha256_bytes(managed)


def _trusted_current_before_contract_asset(
    repo: Path,
    config_path: Path,
    prospective_contract: dict[str, object],
    prospective_payload: bytes,
    asset_id: str,
    target: str,
    snapshot: dict[str, bytes | None],
    before_snapshot: dict[str, bytes | None] | None = None,
) -> dict[str, object]:
    relative = config_path.relative_to(repo).as_posix()
    current_before_payload = _current_before_bytes(
        repo,
        relative,
        before_snapshot,
    )
    if current_before_payload is None:
        raise ReleaseError("explicit adaptation current-before contract is missing")
    current_before_config = _parse_managed_config(
        config_path,
        current_before_payload,
        allow_region_history=True,
    )
    current_before_contract, current_before_legacy = _transition_source_contract(
        config_path,
        current_before_config,
    )
    stamp = current_before_contract.get("stamp")
    if not isinstance(stamp, str):
        raise ReleaseError(
            "explicit adaptation current-before contract binding is incomplete"
        )
    release_version = current_before_contract.get("release_version")
    if current_before_legacy:
        release_version = _read_stamp(
            _current_before_bytes(repo, stamp, before_snapshot),
            "current-before",
        )
    elif (
        current_before_contract.get("contract_target") != relative
        or not isinstance(release_version, str)
    ):
        raise ReleaseError(
            "explicit adaptation current-before contract target is invalid"
        )
    assert isinstance(release_version, str)
    installed_version = _read_stamp(
        _current_before_bytes(repo, stamp, before_snapshot),
        "current-before",
    )
    if installed_version != release_version:
        raise ReleaseError(
            "explicit adaptation current-before contract stamp drifted"
        )
    current_before_hash = _sha256_bytes(current_before_payload)
    if _git_blob_bytes(current_before_payload) != _git_blob_bytes(prospective_payload):
        history = prospective_contract.get("contract_historical_sha256")
        raw_history = history.get(installed_version) if isinstance(history, dict) else None
        accepted = raw_history if isinstance(raw_history, list) else [raw_history]
        if current_before_hash not in {
            item for item in accepted if isinstance(item, str)
        }:
            raise ReleaseError(
                "explicit adaptation current-before contract is not trusted "
                "by the prospective contract"
            )
    contract_for_assets = (
        prospective_contract if current_before_legacy else current_before_contract
    )
    current_before_by_id, _current_before_by_target = _contract_assets(
        config_path,
        contract_for_assets,
    )
    asset = current_before_by_id.get(asset_id)
    if asset is None or asset.get("target") != target:
        raise ReleaseError(
            "explicit adaptation current-before asset is invalid"
        )
    result = copy.deepcopy(asset)
    if current_before_legacy:
        current_target_payload = _current_before_bytes(
            repo,
            target,
            before_snapshot,
        )
        prospective_target_payload = _current_bytes(repo, target, snapshot)
        validation = result.get("merge_validation")
        if (
            result.get("strategy") == "merge"
            and isinstance(validation, dict)
            and validation.get("format") == "codex-hooks-zones-v2"
        ):
            expected_required = validation.get("required_handlers")
            if not isinstance(expected_required, list):
                raise ReleaseError(
                    "explicit adaptation schema v1 current-before hooks contract is invalid"
                )
            expected_ids = {
                (
                    str(item.get("event", "")),
                    str(item.get("matcher", "")),
                    str(item.get("stage", "")),
                ): str(item.get("id", ""))
                for item in expected_required
                if isinstance(item, dict)
            }
            current_handlers = _schema_v1_handler_map(
                current_target_payload, target
            )
            prospective_handlers = _schema_v1_handler_map(
                prospective_target_payload, target
            )
            handler_history = validation.get("historical_handler_sha256")
            observed: list[dict[str, str]] = []
            seen_ids: set[str] = set()
            for key, handler in current_handlers.items():
                managed_id = handler.get("bridgeforgeCodexId")
                if not isinstance(managed_id, str):
                    continue
                if expected_ids.get(key) != managed_id or managed_id in seen_ids:
                    raise ReleaseError(
                        "explicit adaptation schema v1 current-before managed handler drifted"
                    )
                stripped_hash = _handler_without_managed_id_hash(handler)
                accepted_hashes = {
                    _handler_without_managed_id_hash(candidate)
                    for candidate in (prospective_handlers.get(key),)
                    if isinstance(candidate, dict)
                }
                historical_by_version = (
                    handler_history.get(managed_id)
                    if isinstance(handler_history, dict)
                    else None
                )
                if isinstance(historical_by_version, dict):
                    accepted_hashes.update(
                        _history_values_for_version(
                            historical_by_version,
                            installed_version,
                        )
                    )
                if stripped_hash not in accepted_hashes:
                    raise ReleaseError(
                        "explicit adaptation schema v1 current-before managed handler "
                        "does not match a trusted published or current canonical handler"
                    )
                seen_ids.add(managed_id)
                observed.append({
                    "id": managed_id,
                    "event": key[0],
                    "matcher": key[1],
                    "stage": key[2],
                    "handler_sha256": _canonical_json_sha256(handler),
                })
            observed.sort(
                key=lambda item: (
                    item["event"], item["matcher"], item["stage"], item["id"]
                )
            )
            current_validation = copy.deepcopy(validation)
            current_validation["required_handlers"] = observed
            current_validation["current_projection_sha256"] = (
                _canonical_json_sha256(observed)
            )
            result["merge_validation"] = current_validation
        managed_blocks = result.get("managed_blocks")
        if isinstance(managed_blocks, dict):
            projection_hash = _schema_v1_markdown_projection_hash(
                current_target_payload,
                prospective_target_payload,
                result,
                target,
            )
            current_managed_blocks = copy.deepcopy(managed_blocks)
            current_managed_blocks["current_projection_sha256"] = projection_hash
            result["managed_blocks"] = current_managed_blocks
    result["_trusted_release_version"] = release_version
    return result


def _adaptation_legacy_handlers(
    required: list[object],
    current_ids: dict[tuple[str, str, str], str],
    *,
    label: str,
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    current_id_values = set(current_ids.values())
    for item in required:
        if not isinstance(item, dict):
            raise ReleaseError(f"{label} handler is invalid")
        key = (
            str(item.get("event", "")),
            str(item.get("matcher", "")),
            str(item.get("stage", "")),
        )
        managed_id = item.get("id") or current_ids.get(key)
        digest = item.get("sha256") or item.get("handler_sha256")
        if (
            key in seen
            or not isinstance(managed_id, str)
            or not isinstance(digest, str)
            or managed_id not in current_id_values
        ):
            raise ReleaseError(f"{label} handler cannot map to current id")
        seen.add(key)
        result.append({
            "id": managed_id,
            "event": key[0],
            "matcher": key[1],
            "handler_sha256": digest,
        })
    return result


def _adaptation_hooks_project_parts(
    before: bytes | None,
    current_before: bytes | None,
    current: bytes | None,
    old_asset: dict[str, object] | None,
    current_before_asset: dict[str, object] | None,
    current_asset: dict[str, object],
    old_release_version: str,
    old_path: str,
    current_path: str,
) -> tuple[bytes, bytes]:
    if (
        before is None
        or current_before is None
        or current is None
        or old_asset is None
        or current_before_asset is None
    ):
        raise ReleaseError("explicit hooks adaptation target is missing")
    current_required, prospective_project = _current_codex_hooks_zones_parts(
        current,
        current_asset,
        current_path,
    )
    old_validation = old_asset.get("merge_validation")
    old_required = (
        old_validation.get("required_handlers")
        if isinstance(old_validation, dict)
        else None
    )
    current_ids = {
        (
            str(item["event"]),
            str(item["matcher"]),
            str(item["stage"]),
        ): str(item["id"])
        for item in current_required
    }
    legacy_handlers: list[dict[str, str]] = []
    try:
        prospective_document = _load_hooks_document(current, current_path)
        current_groups = _expected_hooks_groups(
            prospective_document,
            managed_prefix="bridgeforge-codex.project-hook.v1:",
        )
        prospective_handlers = _schema_v1_handler_map(current, current_path)
        old_document = _load_hooks_document(before, old_path)
        if isinstance(old_required, list) and old_required:
            legacy_handlers = _adaptation_legacy_handlers(
                old_required,
                current_ids,
                label="explicit hooks adaptation HEAD",
            )
        else:
            hooks = old_document.get("hooks")
            if not isinstance(hooks, dict):
                raise ReleaseError(
                    "explicit hooks adaptation HEAD document has no hooks object"
                )
            observed_keys: set[tuple[str, str, str]] = set()
            for event, groups in hooks.items():
                if not isinstance(event, str) or not isinstance(groups, list):
                    raise ReleaseError(
                        "explicit hooks adaptation HEAD groups are invalid"
                    )
                for group in groups:
                    if not isinstance(group, dict):
                        raise ReleaseError(
                            "explicit hooks adaptation HEAD group is invalid"
                        )
                    matcher = str(group.get("matcher", ""))
                    handlers = group.get("hooks")
                    if not isinstance(handlers, list):
                        raise ReleaseError(
                            "explicit hooks adaptation HEAD handlers are invalid"
                        )
                    for handler in handlers:
                        if not isinstance(handler, dict):
                            raise ReleaseError(
                                "explicit hooks adaptation HEAD handler is invalid"
                            )
                        stage = _dispatcher_stage(handler)
                        if stage is None:
                            continue
                        key = (event, matcher, str(stage))
                        managed_id = current_ids.get(key)
                        if managed_id is None or key in observed_keys:
                            raise ReleaseError(
                                "explicit hooks adaptation found ambiguous legacy dispatcher"
                            )
                        observed_keys.add(key)
                        canonical_handler = prospective_handlers.get(key)
                        trusted_hashes = {
                            _handler_without_managed_id_hash(canonical_handler)
                        } if isinstance(canonical_handler, dict) else set()
                        current_validation = current_asset.get(
                            "merge_validation"
                        )
                        handler_history = (
                            current_validation.get(
                                "historical_handler_sha256"
                            )
                            if isinstance(current_validation, dict)
                            else None
                        )
                        historical_by_version = (
                            handler_history.get(managed_id)
                            if isinstance(handler_history, dict)
                            else None
                        )
                        if (
                            isinstance(historical_by_version, dict)
                        ):
                            trusted_hashes.update(
                                _history_values_for_version(
                                    historical_by_version,
                                    old_release_version,
                                )
                            )
                        if (
                            _handler_without_managed_id_hash(handler)
                            not in trusted_hashes
                        ):
                            raise ReleaseError(
                                "explicit hooks adaptation HEAD dispatcher does not "
                                "match a trusted published or current canonical handler"
                            )
                        legacy_handlers.append({
                            "id": managed_id,
                            "event": event,
                            "matcher": matcher,
                            "handler_sha256": _canonical_json_sha256(handler),
                        })
            if not legacy_handlers:
                raise ReleaseError(
                    "explicit hooks adaptation found no recognizable legacy dispatcher"
                )
        _canonical_old, _old_external, old_receipts = _canonicalize_hooks_zones(
            old_document,
            current_groups,
            managed_prefixes=("bridgeforge-codex.project-hook.v1:",),
            label=old_path,
            managed_looking=lambda handler: _dispatcher_stage(handler) is not None,
            legacy_handlers=legacy_handlers,
            managed_top_level=(
                current_asset.get("merge_validation", {}).get("managed_top_level")
                if isinstance(current_asset.get("merge_validation"), dict)
                else None
            ),
            managed_top_level_historical=(
                current_asset.get("merge_validation", {}).get(
                    "managed_top_level_historical"
                )
                if isinstance(current_asset.get("merge_validation"), dict)
                else None
            ),
        )
        trusted_head_ids = {item["id"] for item in legacy_handlers}
        observed_head_ids = {
            item["id"]
            for item in old_receipts
            if item["action"] != "add-missing"
        }
        if not trusted_head_ids.issubset(observed_head_ids):
            raise ReleaseError(
                "explicit hooks adaptation HEAD is missing a trusted managed handler"
            )
        current_before_document = _load_hooks_document(
            current_before,
            current_path,
        )
        current_before_validation = current_before_asset.get("merge_validation")
        current_before_required = (
            current_before_validation.get("required_handlers")
            if isinstance(current_before_validation, dict)
            else None
        )
        if not isinstance(current_before_required, list):
            raise ReleaseError(
                "explicit hooks adaptation current-before handlers are invalid"
            )
        declared_current_before_projection = current_before_validation.get(
            "current_projection_sha256"
        )
        if (
            declared_current_before_projection is not None
            and (
                not isinstance(declared_current_before_projection, str)
                or _canonical_json_sha256(current_before_required)
                != declared_current_before_projection
            )
        ):
            raise ReleaseError(
                "explicit hooks adaptation current-before contract projection drifted"
            )
        current_before_handlers = _adaptation_legacy_handlers(
            current_before_required,
            current_ids,
            label="explicit hooks adaptation current-before",
        )
        current_validation = current_asset.get("merge_validation")
        current_managed_top_level = (
            current_validation.get("managed_top_level")
            if isinstance(current_validation, dict)
            else None
        )
        current_managed_top_level_historical = (
            current_validation.get("managed_top_level_historical")
            if isinstance(current_validation, dict)
            else None
        )
        if isinstance(current_managed_top_level, dict):
            for key, value in current_managed_top_level.items():
                historical = (
                    current_managed_top_level_historical.get(key, [])
                    if isinstance(current_managed_top_level_historical, dict)
                    else []
                )
                if (
                    not isinstance(historical, list)
                    or (
                        current_before_document.get(key) != value
                        and current_before_document.get(key) not in historical
                    )
                ):
                    raise ReleaseError(
                        "explicit hooks adaptation current-before managed top-level "
                        f"field drifted: {key}"
                    )
        (
            _canonical_current_before,
            current_before_external,
            current_before_receipts,
        ) = _canonicalize_hooks_zones(
            current_before_document,
            current_groups,
            managed_prefixes=("bridgeforge-codex.project-hook.v1:",),
            label=current_path,
            managed_looking=lambda handler: _dispatcher_stage(handler) is not None,
            legacy_handlers=current_before_handlers,
            managed_top_level=current_managed_top_level,
            managed_top_level_historical=current_managed_top_level_historical,
        )
        trusted_current_before_ids = {
            item["id"] for item in current_before_handlers
        }
        observed_current_before_ids = {
            item["id"]
            for item in current_before_receipts
            if item["action"] != "add-missing"
        }
        if not trusted_current_before_ids.issubset(observed_current_before_ids):
            raise ReleaseError(
                "explicit hooks adaptation current-before target is missing a "
                "trusted managed handler"
            )
    except HooksOwnershipError as exc:
        raise ReleaseError(str(exc)) from exc
    current_before_project = json.dumps(
        current_before_external,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return current_before_project, prospective_project


def _explicit_adaptation_ownership_evidence(
    repo: Path,
    snapshot: dict[str, bytes | None],
    asset_id: str,
    target: str,
    category: str,
    allowed_adaptations: set[tuple[str, str]],
    require_lexical_absence: bool,
    before_snapshot: dict[str, bytes | None] | None = None,
) -> tuple[str, str]:
    if require_lexical_absence and _lexical_entry_exists(repo, target):
        raise ReleaseError(
            "explicit no-target retirement has a lexical directory entry"
        )
    (
        old_target,
        current_target,
        old_asset,
        current_asset,
        old_version,
        current_before_asset,
    ) = _explicit_adaptation_context(
        repo,
        snapshot,
        (
            None
            if before_snapshot is None
            else _normalized_snapshot(before_snapshot)
        ),
        asset_id,
        target,
        allowed_adaptations,
    )
    before = _head_bytes(repo, old_target) if old_target is not None else None
    current_before = (
        _current_before_bytes(repo, current_target, before_snapshot)
        if current_target is not None
        else None
    )
    current = (
        _current_bytes(repo, current_target, snapshot)
        if current_target is not None
        else None
    )
    empty = _sha256_bytes(b"")
    if current_asset is None:
        if current is not None:
            raise ReleaseError("explicit retirement adaptation target still exists")
        return empty, empty

    strategy = current_asset.get("strategy")
    if isinstance(current_asset.get("agents_zones"), dict):
        zones = current_asset["agents_zones"]
        current_public, current_project = _agents_zone_release_parts(current, zones)
        public = zones.get("public")
        expected = public.get("current_sha256") if isinstance(public, dict) else None
        if (
            current_public is None
            or current_project is None
            or not isinstance(expected, str)
            or _agents_public_hash(current_public) != expected
        ):
            raise ReleaseError(
                "explicit AGENTS adaptation public zone is not current"
            )
        if category == "agents_ownership_review":
            if before is None:
                raise ReleaseError("explicit AGENTS adaptation HEAD target is missing")
            legacy = _git_blob_bytes(before)
            if current_project.count(legacy) != 1:
                raise ReleaseError(
                    "explicit AGENTS adaptation did not preserve HEAD bytes exactly once"
                )
            digest = _sha256_bytes(legacy)
            return digest, digest
        if old_asset is None or not isinstance(old_asset.get("agents_zones"), dict):
            raise ReleaseError("explicit AGENTS transition has no zoned HEAD contract")
        _old_public, old_project = _agents_zone_release_parts(
            before,
            old_asset["agents_zones"],
        )
        if old_project is None or old_project != current_project:
            raise ReleaseError("explicit AGENTS adaptation changed the project zone")
        return _sha256_bytes(old_project), _sha256_bytes(current_project)

    if strategy == "region":
        region = current_asset.get("region")
        if not isinstance(region, dict):
            raise ReleaseError("explicit region adaptation contract is invalid")
        begin = region.get("begin")
        end = region.get("end")
        expected = region.get("current_sha256")
        if not all(isinstance(item, str) for item in (begin, end, expected)):
            raise ReleaseError("explicit region adaptation contract is incomplete")
        current_managed, current_project = _region_parts(current, str(begin), str(end))
        old_managed, old_project = _region_transition_parts(
            before,
            str(begin),
            str(end),
        )
        if (
            current_managed is None
            or _sha256_bytes(current_managed) != expected
            or old_managed is None
            or old_project != current_project
        ):
            raise ReleaseError(
                "explicit region adaptation changed its project extension"
            )
        return _sha256_bytes(old_project or b""), _sha256_bytes(current_project or b"")

    if strategy == "merge" and current_asset.get("merge_policy") == "codex-hooks":
        old_project, current_project = _adaptation_hooks_project_parts(
            before,
            current_before,
            current,
            old_asset,
            current_before_asset,
            current_asset,
            old_version,
            str(old_target),
            str(current_target),
        )
        if old_project != current_project:
            raise ReleaseError("explicit hooks adaptation changed external handlers")
        return _sha256_bytes(old_project), _sha256_bytes(current_project)

    if isinstance(current_asset.get("managed_blocks"), dict):
        if (
            current_before is None
            or current is None
            or current_before_asset is None
            or not isinstance(current_before_asset.get("managed_blocks"), dict)
        ):
            raise ReleaseError("explicit managed Markdown adaptation target is missing")
        current_managed, current_project = _managed_blocks_parts(
            current,
            current_asset,
            str(current_target),
        )
        expected = _current_projection_hash(
            current_asset["managed_blocks"],
            f"explicit managed Markdown {current_target}",
        )
        if _sha256_bytes(current_managed or b"") != expected:
            raise ReleaseError(
                "explicit managed Markdown adaptation is not current"
            )
        current_before_managed, current_before_project = _managed_blocks_parts(
            current_before,
            current_before_asset,
            str(current_target),
        )
        current_before_projection = _sha256_bytes(current_before_managed or b"")
        current_before_contract = current_before_asset["managed_blocks"]
        current_before_expected = current_before_contract.get(
            "current_projection_sha256"
        )
        accepted_current_before = (
            {current_before_expected}
            if isinstance(current_before_expected, str)
            else _history_values_for_version(
                current_asset["managed_blocks"].get(
                    "historical_projection_sha256"
                ),
                str(current_before_asset.get("_trusted_release_version", "")),
            )
        )
        if current_before_projection not in accepted_current_before:
            raise ReleaseError(
                "explicit managed Markdown current-before projection drifted"
            )
        if current_before_project != current_project:
            raise ReleaseError(
                "explicit managed Markdown adaptation changed project content"
            )
        return (
            _sha256_bytes(current_before_project or b""),
            _sha256_bytes(current_project or b""),
        )

    if strategy in {"whole", "retirement"}:
        if current is None:
            if strategy != "retirement":
                raise ReleaseError("explicit whole-file adaptation target is missing")
        else:
            expected = current_asset.get("current_sha256")
            if (
                not isinstance(expected, str)
                or _asset_target_hash(current, current_asset, repo) != expected
            ):
                raise ReleaseError("explicit whole-file adaptation is not current")
        return empty, empty

    if strategy == "merge":
        if current is None:
            raise ReleaseError("explicit merge adaptation target is missing")
        expected = current_asset.get("current_sha256")
        if not isinstance(expected, str) or _sha256_bytes(current) != expected:
            raise ReleaseError(
                "explicit generic merge adaptation is not exact current content"
            )
        return empty, empty

    raise ReleaseError(
        f"unsupported explicit adaptation ownership strategy: {strategy!r}"
    )


def _contract_snapshot_targets(
    config_path: Path,
    payload: bytes | None,
    selected_ids: set[str],
    selected_targets: set[str],
) -> set[str]:
    if payload is None:
        return set()
    config = _parse_managed_config(
        config_path,
        payload,
        allow_region_history=True,
    )
    contract, legacy = _transition_source_contract(config_path, config)
    targets: set[str] = set()
    stamp = contract.get("stamp")
    if isinstance(stamp, str):
        targets.add(stamp)
    if not legacy:
        by_id, _by_target = _contract_assets(config_path, contract)
        targets.update(
            str(asset["target"])
            for asset_id, asset in by_id.items()
            if asset_id in selected_ids
            or str(asset["target"]) in selected_targets
        )
    return targets


def freeze_explicit_adaptation_before_snapshot(
    repo: Path,
    snapshot: dict[str, bytes | None] | None,
    raw_items: list[dict[str, object]],
) -> dict[str, bytes | None]:
    """Freeze every managed input needed to replay current-before evidence."""

    normalized = _normalized_snapshot(snapshot)
    selected_targets = {
        str(raw["target"])
        for raw in raw_items
        if isinstance(raw, dict) and isinstance(raw.get("target"), str)
    }
    selected_ids = {
        str(raw["asset_id"])
        for raw in raw_items
        if isinstance(raw, dict) and isinstance(raw.get("asset_id"), str)
    }
    targets = set(selected_targets)
    for config_path, current_config in _load_managed_configs(repo, normalized):
        relative = config_path.relative_to(repo).as_posix()
        targets.add(relative)
        current_payload = _current_bytes(repo, config_path, normalized)
        targets.update(
            _contract_snapshot_targets(
                config_path,
                current_payload,
                selected_ids,
                selected_targets,
            )
        )
        targets.update(
            _contract_snapshot_targets(
                config_path,
                _current_bytes(repo, config_path, {}),
                selected_ids,
                selected_targets,
            )
        )
        targets.update(
            _contract_snapshot_targets(
                config_path,
                _head_bytes(repo, relative),
                selected_ids,
                selected_targets,
            )
        )
        current_contract = _raw_contract(config_path, current_config)
        current_by_id, _current_by_target = _contract_assets(
            config_path,
            current_contract,
        )
        targets.update(
            str(asset["target"])
            for asset_id, asset in current_by_id.items()
            if asset_id in selected_ids
        )
    return {
        target: _current_bytes(repo, target, {})
        for target in sorted(targets)
    }


def encode_explicit_adaptation_before_snapshot(
    snapshot: dict[str, bytes | None],
) -> dict[str, str | None]:
    normalized = _normalized_snapshot(snapshot)
    return {
        path: (
            None
            if payload is None
            else base64.b64encode(payload).decode("ascii")
        )
        for path, payload in sorted(normalized.items())
    }


def decode_explicit_adaptation_before_snapshot(
    raw: object,
) -> dict[str, bytes | None]:
    if not isinstance(raw, dict):
        raise ReleaseError("explicit adaptation proof before snapshot is missing")
    decoded: dict[str, bytes | None] = {}
    for raw_path, payload in raw.items():
        if not isinstance(raw_path, str) or (
            payload is not None and not isinstance(payload, str)
        ):
            raise ReleaseError("explicit adaptation proof before snapshot is invalid")
        if payload is None:
            value = None
        else:
            try:
                value = base64.b64decode(payload.encode("ascii"), validate=True)
            except (UnicodeEncodeError, ValueError) as exc:
                raise ReleaseError(
                    "explicit adaptation proof before snapshot payload is invalid"
                ) from exc
            if base64.b64encode(value).decode("ascii") != payload:
                raise ReleaseError(
                    "explicit adaptation proof before snapshot payload is not canonical"
                )
        normalized_entry = _normalized_snapshot({raw_path: value})
        path, value = next(iter(normalized_entry.items()))
        if path in decoded:
            raise ReleaseError(
                "explicit adaptation proof before snapshot path is duplicated"
            )
        decoded[path] = value
    return decoded


def explicit_adaptation_before_snapshot_fingerprint(
    encoded: dict[str, str | None],
) -> str:
    return _sha256_bytes(_canonical_json(encoded))


def build_explicit_adaptation_evidence(
    repo: Path,
    snapshot: dict[str, bytes | None] | None,
    raw_items: list[dict[str, object]],
    before_snapshot: dict[str, bytes | None] | None = None,
) -> dict[str, object]:
    normalized = _normalized_snapshot(snapshot)
    normalized_before = (
        None
        if before_snapshot is None
        else _normalized_snapshot(before_snapshot)
    )
    allowed_adaptations = {
        (str(raw.get("asset_id")), str(raw.get("target")))
        for raw in raw_items
        if isinstance(raw, dict)
        and isinstance(raw.get("asset_id"), str)
        and isinstance(raw.get("target"), str)
    }
    items: list[dict[str, object]] = []
    for raw in raw_items:
        asset_id = raw.get("asset_id")
        target = raw.get("target")
        category = raw.get("category")
        if (
            not isinstance(asset_id, str)
            or not isinstance(target, str)
            or not isinstance(category, str)
        ):
            raise ReleaseError("explicit adaptation evidence item is invalid")
        project_before, project_after = _explicit_adaptation_ownership_evidence(
            repo,
            normalized,
            asset_id,
            target,
            category,
            allowed_adaptations,
            raw.get("before_sha256") is None
            and raw.get("after_sha256") is None,
            normalized_before,
        )
        if project_before != project_after:
            raise ReleaseError("explicit adaptation changed project-owned content")
        items.append({
            **raw,
            "project_before_sha256": project_before,
            "project_after_sha256": project_after,
        })
    transition_fingerprint = _sha256_bytes(_canonical_json({
        "head": _head_commit(repo),
        "items": items,
    }))
    return {
        "items": items,
        "transition_fingerprint": transition_fingerprint,
    }


def _validated_explicit_adaptations(
    repo: Path,
    snapshot: dict[str, bytes | None],
    proof: dict[str, object] | None,
    before_snapshot: dict[str, bytes | None] | None = None,
) -> dict[tuple[str, str], dict[str, object]]:
    if proof is None:
        return {}
    if not isinstance(proof, dict) or proof.get("schema_version") != 2:
        raise ReleaseError("explicit adaptation proof must use schema_version=2")
    if proof.get("project_root") != str(repo.resolve()):
        raise ReleaseError("explicit adaptation proof belongs to another project")
    if proof.get("head") != _head_commit(repo):
        raise ReleaseError("explicit adaptation proof HEAD drifted")
    contract_target = proof.get("contract_target")
    contract_sha256 = proof.get("contract_sha256")
    if not isinstance(contract_target, str) or not isinstance(contract_sha256, str):
        raise ReleaseError("explicit adaptation proof has no contract binding")
    contract_payload = _current_bytes(repo, contract_target, snapshot)
    if _optional_payload_hash(contract_payload) != contract_sha256:
        raise ReleaseError("explicit adaptation proof contract hash drifted")
    aggregate = proof.get("aggregate_fingerprint")
    transition_fingerprint = proof.get("transition_fingerprint")
    selection = proof.get("selection_fingerprint")
    encoded_before = proof.get("before_snapshot")
    before_fingerprint = proof.get("before_snapshot_fingerprint")
    frozen_before = decode_explicit_adaptation_before_snapshot(encoded_before)
    if (
        not isinstance(encoded_before, dict)
        or not isinstance(before_fingerprint, str)
        or explicit_adaptation_before_snapshot_fingerprint(encoded_before)
        != before_fingerprint
    ):
        raise ReleaseError("explicit adaptation proof before snapshot drifted")
    if before_snapshot is not None and _normalized_snapshot(before_snapshot) != frozen_before:
        raise ReleaseError("explicit adaptation evaluator before snapshot drifted")
    raw_items = proof.get("items")
    if (
        not isinstance(aggregate, str)
        or not isinstance(transition_fingerprint, str)
        or not isinstance(selection, str)
        or not isinstance(raw_items, list)
        or not raw_items
    ):
        raise ReleaseError("explicit adaptation proof selection is incomplete")
    selected_ids: list[str] = []
    items: dict[tuple[str, str], dict[str, object]] = {}
    canonical_items: list[dict[str, object]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ReleaseError("explicit adaptation proof item is invalid")
        item_id = raw.get("id")
        asset_id = raw.get("asset_id")
        target = raw.get("target")
        category = raw.get("category")
        before_sha256 = raw.get("before_sha256")
        after_sha256 = raw.get("after_sha256")
        project_before_sha256 = raw.get("project_before_sha256")
        project_after_sha256 = raw.get("project_after_sha256")
        if (
            not isinstance(item_id, str)
            or re.fullmatch(r"G[1-9][0-9]*", item_id) is None
            or not isinstance(asset_id, str)
            or not isinstance(target, str)
            or category not in {
                "release_transition_review",
                "agents_ownership_review",
            }
            or (before_sha256 is not None and not isinstance(before_sha256, str))
            or (after_sha256 is not None and not isinstance(after_sha256, str))
            or not isinstance(project_before_sha256, str)
            or not isinstance(project_after_sha256, str)
        ):
            raise ReleaseError("explicit adaptation proof item binding is invalid")
        key = (asset_id, target)
        if item_id in selected_ids or key in items:
            raise ReleaseError("explicit adaptation proof contains duplicate items")
        if _optional_payload_hash(_head_bytes(repo, target)) != before_sha256:
            raise ReleaseError(f"explicit adaptation proof HEAD target drifted: {target}")
        if _optional_payload_hash(_current_bytes(repo, target, snapshot)) != after_sha256:
            raise ReleaseError(f"explicit adaptation proof current target drifted: {target}")
        selected_ids.append(item_id)
        canonical = {
            "id": item_id,
            "asset_id": asset_id,
            "target": target,
            "category": category,
            "before_sha256": before_sha256,
            "after_sha256": after_sha256,
            "project_before_sha256": project_before_sha256,
            "project_after_sha256": project_after_sha256,
        }
        canonical_items.append(canonical)
        items[key] = canonical
    evidence = build_explicit_adaptation_evidence(
        repo,
        snapshot,
        canonical_items,
        frozen_before,
    )
    if (
        evidence.get("items") != canonical_items
        or evidence.get("transition_fingerprint") != transition_fingerprint
    ):
        raise ReleaseError("explicit adaptation ownership evidence drifted")
    expected_selection = _sha256_bytes(_canonical_json({
        "aggregate_fingerprint": aggregate,
        "transition_fingerprint": transition_fingerprint,
        "before_snapshot_fingerprint": before_fingerprint,
        "selected_adaptation_ids": selected_ids,
        "items": canonical_items,
    }))
    if selection != expected_selection:
        raise ReleaseError("explicit adaptation proof selection fingerprint drifted")
    return items


def evaluate_release_transition(
    repo: Path,
    snapshot: dict[str, bytes | None] | None = None,
    prospective_version: str | None = None,
    *,
    changed_paths: set[str] | None = None,
    adaptation_proof: dict[str, object] | None = None,
    before_snapshot: dict[str, bytes | None] | None = None,
) -> tuple[str, set[str]]:
    """Evaluate one transition standard over a real or prospective snapshot."""

    normalized = _normalized_snapshot(snapshot)
    if prospective_version is not None:
        for _config_path, current_config in _load_managed_configs(
            repo,
            normalized,
        ):
            current_contract = _raw_contract(_config_path, current_config)
            current_stamp = current_contract.get("stamp")
            if isinstance(current_stamp, str):
                normalized.setdefault(
                    current_stamp,
                    (prospective_version + "\n").encode("utf-8"),
                )
    explicit_adaptations = _validated_explicit_adaptations(
        repo,
        normalized,
        adaptation_proof,
        before_snapshot,
    )
    consumed_adaptations: set[tuple[str, str]] = set()
    paths = (
        collect_changed_paths(repo)
        if changed_paths is None
        else {item.replace("\\", "/") for item in changed_paths}
    )
    paths.update(normalized)
    if prospective_version is not None:
        configs = _load_managed_configs(repo, normalized)
        for config_path, current_config in configs:
            current_contract = _raw_contract(config_path, current_config)
            current_stamp = current_contract.get("stamp")
            if isinstance(current_stamp, str):
                paths.add(current_stamp)
            relative = config_path.relative_to(repo).as_posix()
            head_payload = _head_bytes(repo, relative)
            if head_payload is None:
                continue
            current_payload = _current_bytes(repo, config_path, normalized)
            if current_payload is None:
                continue
            if _git_blob_bytes(head_payload) == _git_blob_bytes(current_payload):
                continue
            head_config = _parse_managed_config(
                config_path,
                head_payload,
                allow_region_history=True,
            )
            head_contract, _legacy_head = _transition_source_contract(
                config_path,
                head_config,
            )
            head_stamp = head_contract.get("stamp")
            if isinstance(head_stamp, str):
                paths.add(head_stamp)
    classification = _classify_snapshot(
            repo,
            paths,
            prospective_skeleton_version=prospective_version,
            snapshot=normalized,
            explicit_adaptations=explicit_adaptations,
            consumed_adaptations=consumed_adaptations,
        )
    unused = sorted(set(explicit_adaptations) - consumed_adaptations)
    if unused:
        raise ReleaseError(
            "explicit adaptation proof did not match a blocked transition: "
            + ", ".join(f"{asset_id}:{target}" for asset_id, target in unused)
        )
    return (
        classification,
        paths,
    )


def classify_changes(
    repo: Path,
    changed_paths: set[str],
    *,
    prospective_skeleton_version: str | None = None,
) -> str:
    """Compatibility wrapper; all decisions come from the single evaluator."""

    return evaluate_release_transition(
        repo,
        prospective_version=prospective_skeleton_version,
        changed_paths=changed_paths,
    )[0]


def preflight_contract_transition(
    repo: Path,
    prospective_skeleton_version: str | None = None,
) -> tuple[str, set[str]]:
    """Compatibility wrapper for callers installed before the unified evaluator."""

    return evaluate_release_transition(
        repo,
        prospective_version=prospective_skeleton_version,
    )


def _toml_version(path: Path) -> tuple[str, tuple[str, ...], str] | None:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ReleaseError(f"invalid TOML {path}: {exc}") from exc
    candidates: list[tuple[tuple[str, ...], object]] = []
    if path.name == "Cargo.toml":
        candidates.extend(
            [
                (("package", "version"), data.get("package", {}).get("version") if isinstance(data.get("package"), dict) else None),
                (("workspace", "package", "version"), data.get("workspace", {}).get("package", {}).get("version") if isinstance(data.get("workspace"), dict) and isinstance(data.get("workspace", {}).get("package"), dict) else None),
            ]
        )
    elif path.name == "pyproject.toml":
        project = data.get("project")
        if isinstance(project, dict):
            dynamic = project.get("dynamic", [])
            if isinstance(dynamic, list) and "version" in dynamic:
                raise ReleaseError(f"dynamic Python version is unsupported: {path}")
            candidates.append((("project", "version"), project.get("version")))
    found = [(keys, value) for keys, value in candidates if isinstance(value, str)]
    if not found:
        return None
    values = {value for _keys, value in found}
    if len(values) != 1 or len(found) != 1:
        raise ReleaseError(f"ambiguous version fields in {path}")
    keys, value = found[0]
    parse_semver(value)
    return value, keys, "toml"


def _json_version(path: Path) -> tuple[str, tuple[str, ...], str] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_reject_duplicate_keys)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"invalid JSON {path}: {exc}") from exc
    version = data.get("version") if isinstance(data, dict) else None
    if not isinstance(version, str):
        return None
    parse_semver(version)
    return version, ("version",), "json"


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise json.JSONDecodeError(f"duplicate key {key}", key, 0)
        result[key] = value
    return result


def _candidate_manifests(repo: Path) -> list[Path]:
    config_path = repo / ".bridgeforge-version.json"
    if config_path.is_file():
        try:
            config = json.loads(
                config_path.read_text(encoding="utf-8-sig"),
                object_pairs_hook=_reject_duplicate_keys,
            )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReleaseError(f"invalid version sync config {config_path}: {exc}") from exc
        manifests = config.get("manifests") if isinstance(config, dict) else None
        if config.get("schema_version") != 1 or not isinstance(manifests, list) or not manifests:
            raise ReleaseError(
                ".bridgeforge-version.json must contain schema_version=1 and non-empty manifests"
            )
        paths: list[Path] = []
        for raw_path in manifests:
            if not isinstance(raw_path, str) or not raw_path or "\\" in raw_path:
                raise ReleaseError("configured manifest paths must be non-empty POSIX paths")
            relative = PurePosixPath(raw_path)
            if relative.is_absolute() or ".." in relative.parts:
                raise ReleaseError(f"configured manifest escapes repository: {raw_path}")
            path = repo.joinpath(*relative.parts)
            if path.name not in {"package.json", "Cargo.toml", "pyproject.toml"} or not path.is_file():
                raise ReleaseError(f"unsupported or missing configured manifest: {raw_path}")
            paths.append(path)
        if len(set(paths)) != len(paths):
            raise ReleaseError("configured manifests contain duplicates")
        return paths

    paths: list[Path] = []
    for name in ("package.json", "Cargo.toml", "pyproject.toml"):
        direct = repo / name
        if direct.is_file():
            paths.append(direct)
    for child in sorted(repo.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        for name in ("package.json", "Cargo.toml", "pyproject.toml"):
            candidate = child / name
            if candidate.is_file():
                paths.append(candidate)
    return paths


def _discover_native_targets(repo: Path) -> list[tuple[Path, str, tuple[str, ...], str]]:
    found: list[tuple[Path, str, tuple[str, ...], str]] = []
    for path in _candidate_manifests(repo):
        parsed = _json_version(path) if path.name == "package.json" else _toml_version(path)
        if parsed is not None:
            value, keys, format_name = parsed
            found.append((path, value, keys, format_name))
    configured = (repo / ".bridgeforge-version.json").is_file()
    if len(found) > 1 and not configured:
        labels = ", ".join(path.relative_to(repo).as_posix() for path, *_rest in found)
        raise ReleaseError(f"multiple native version manifests require explicit project configuration: {labels}")
    if configured and len(found) != len(_candidate_manifests(repo)):
        raise ReleaseError("every configured manifest must contain one supported static version field")
    if configured and len({value for _path, value, _keys, _format in found}) > 1:
        raise ReleaseError("configured native manifests disagree before automatic version sync")
    return found


def _replace_toml_value(payload: str, keys: tuple[str, ...], old: str, new: str) -> str:
    table = ".".join(keys[:-1])
    key = re.escape(keys[-1])
    header = re.compile(rf"(?m)^\s*\[{re.escape(table)}\]\s*(?:#.*)?$")
    match = header.search(payload)
    if match is None:
        raise ReleaseError(f"missing TOML table [{table}]")
    next_header = re.search(r"(?m)^\s*\[", payload[match.end():])
    end = match.end() + (next_header.start() if next_header else len(payload[match.end():]))
    body = payload[match.end():end]
    value_re = re.compile(rf'(?m)^(\s*{key}\s*=\s*)["\']{re.escape(old)}["\'](\s*(?:#.*)?)$')
    replaced, count = value_re.subn(rf'\g<1>"{new}"\g<2>', body)
    if count != 1:
        raise ReleaseError(f"expected one {'.'.join(keys)} field, found {count}")
    return payload[:match.end()] + replaced + payload[end:]


def _render_json_version(path: Path, new: str) -> bytes:
    data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_reject_duplicate_keys)
    if not isinstance(data, dict) or not isinstance(data.get("version"), str):
        raise ReleaseError(f"missing top-level version in {path}")
    data["version"] = new
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _render_package_lock(path: Path, old: str, new: str) -> bytes:
    data = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_reject_duplicate_keys)
    if not isinstance(data, dict) or data.get("lockfileVersion") not in (2, 3):
        raise ReleaseError(f"unsupported package-lock schema: {path}")
    packages = data.get("packages")
    root_package = packages.get("") if isinstance(packages, dict) else None
    if data.get("version") != old or not isinstance(root_package, dict) or root_package.get("version") != old:
        raise ReleaseError(f"package-lock root version is missing or inconsistent: {path}")
    data["version"] = new
    root_package["version"] = new
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _render_cargo_lock(path: Path, old: str, new: str) -> bytes:
    text = path.read_text(encoding="utf-8-sig")
    parts = re.split(r"(?m)(?=^\[\[package\]\]\s*$)", text)
    changed = 0
    rendered: list[str] = []
    for part in parts:
        if not part.startswith("[[package]]") or re.search(r"(?m)^source\s*=", part):
            rendered.append(part)
            continue
        version_re = re.compile(rf'(?m)^(version\s*=\s*)"{re.escape(old)}"(\s*)$')
        updated, count = version_re.subn(rf'\g<1>"{new}"\g<2>', part)
        changed += count
        rendered.append(updated)
    if changed == 0:
        raise ReleaseError(f"Cargo.lock has no local package at version {old}: {path}")
    return "".join(rendered).encode("utf-8")


def _render_changelog(
    path: Path,
    version: str,
    info: CommitInfo,
    classification: str,
    changed_paths: set[str],
) -> bytes:
    text = path.read_text(encoding="utf-8-sig") if path.is_file() else "# Changelog\n"
    if re.search(rf"(?m)^## \[{re.escape(version)}\](?:\s|$)", text):
        raise ReleaseError(f"CHANGELOG already contains version {version}: {path}")
    prefix = ""
    if classification == "factory":
        tags: list[str] = []
        source_paths = changed_paths - AUTO_EXCLUDED_PATHS
        if any(item.startswith(("templates/", "skills/")) for item in source_paths):
            tags.append("product")
        if any(item.startswith((".codex/", "scripts/")) for item in source_paths):
            tags.append("repo")
        if any(item.startswith("doc/") or item in {"README.md", "AGENTS.md"} for item in source_paths):
            tags.append("meta")
        if not tags:
            tags.append("repo")
        prefix = "".join(f"[{tag}]" for tag in tags) + " "
    breaking = " **BREAKING:**" if info.breaking else ""
    entry = (
        f"## [{version}] - {date.today().isoformat()}\n\n"
        f"### {info.section}\n\n"
        f"- {prefix}{info.description}{breaking}\n\n"
    )
    headings = list(re.finditer(r"(?m)^## \[", text))
    if headings:
        if text[headings[0].start():].startswith("## [Unreleased]"):
            insert_at = headings[1].start() if len(headings) > 1 else len(text)
        else:
            insert_at = headings[0].start()
        text = text[:insert_at].rstrip() + "\n\n" + entry + text[insert_at:]
    else:
        text = text.rstrip() + "\n\n" + entry
    return text.encode("utf-8")


def build_release_plan(
    repo: Path,
    message: str,
    changed_paths: set[str],
    *,
    adaptation_proof: dict[str, object] | None = None,
) -> ReleasePlan | None:
    info = parse_commit_message(message)
    classification = evaluate_release_transition(
        repo,
        changed_paths=changed_paths,
        adaptation_proof=adaptation_proof,
    )[0]
    if classification == "skeleton-only":
        return None

    version_path = repo / "VERSION"
    native = _discover_native_targets(repo)
    writes: dict[Path, bytes] = {}
    if version_path.is_file():
        old_version = version_path.read_text(encoding="utf-8-sig").strip()
        parse_semver(old_version)
    else:
        if not native:
            raise ReleaseError("root VERSION is missing and no unique supported native version exists")
        values = {value for _path, value, _keys, _format in native}
        if len(values) != 1:
            raise ReleaseError("root VERSION is missing and native version candidates conflict")
        old_version = next(iter(values))
    new_version = bump_semver(old_version, info.level)
    writes[version_path] = f"{new_version}\n".encode("utf-8")

    for path, current, keys, format_name in native:
        if format_name == "json":
            writes[path] = _render_json_version(path, new_version)
            lock = path.with_name("package-lock.json")
            if lock.is_file():
                writes[lock] = _render_package_lock(lock, current, new_version)
            for unsupported in ("pnpm-lock.yaml", "yarn.lock"):
                if path.with_name(unsupported).is_file():
                    raise ReleaseError(f"unsupported JavaScript lock file: {path.with_name(unsupported)}")
        else:
            payload = path.read_text(encoding="utf-8-sig")
            writes[path] = _replace_toml_value(payload, keys, current, new_version).encode("utf-8")
            if path.name == "Cargo.toml":
                lock = path.with_name("Cargo.lock")
                if lock.is_file():
                    writes[lock] = _render_cargo_lock(lock, current, new_version)
            else:
                for unsupported in ("poetry.lock", "uv.lock", "pdm.lock"):
                    if path.with_name(unsupported).is_file():
                        raise ReleaseError(f"unsupported Python lock file: {path.with_name(unsupported)}")

    changelog = repo / "CHANGELOG.md"
    writes[changelog] = _render_changelog(
        changelog, new_version, info, classification, changed_paths
    )
    return ReleasePlan(old_version, new_version, classification, writes)


def apply_release_plan(plan: ReleasePlan) -> None:
    for path, payload in plan.writes.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, raw_temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
        temporary = Path(raw_temporary)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
