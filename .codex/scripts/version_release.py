#!/usr/bin/env python3
"""Plan and apply deterministic repository version releases for git-sync."""
from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath


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
AUTO_EXCLUDED_PATHS = {"VERSION", "CHANGELOG.md", "shared-skill-manifest.json"}


class ReleaseError(RuntimeError):
    """Fail-closed release planning error."""


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
    finish = payload.index(end_bytes, start) + len(end_bytes)
    outside = payload[:start] + b"<BRIDGEFORGE_MANAGED_REGION>" + payload[finish:]
    return payload[start:finish], outside


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
        marker = f"<BRIDGEFORGE_MANAGED_MARKDOWN:{heading}>".encode("utf-8")
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
    project_table = b"<BRIDGEFORGE_MANAGED_KEYED_TABLE>\n" + b"".join(project_rows)
    project = payload[:table_start] + project_table + payload[table_end:]
    return managed, project


def _managed_markdown_parts(
    payload: bytes | None,
    headings: list[str],
    additive_headings: list[str],
    keyed_tables: list[dict[str, object]],
) -> tuple[bytes | None, bytes | None]:
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


def _load_managed_configs(repo: Path) -> list[tuple[Path, dict[str, object]]]:
    configs: list[tuple[Path, dict[str, object]]] = []
    for host in (".codex", ".claude"):
        path = repo / host / "managed-skeleton.json"
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReleaseError(f"invalid managed skeleton config {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ReleaseError(f"unsupported managed skeleton config: {path}")
        schema_version = value.get("schema_version")
        if schema_version == 1:
            configs.append((path, value))
            continue
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
        for asset in assets:
            if not isinstance(asset, dict):
                raise ReleaseError(f"invalid schema v2 asset in {path}")
            target = asset.get("target")
            strategy = asset.get("strategy")
            if not isinstance(target, str) or not isinstance(strategy, str):
                raise ReleaseError(f"invalid schema v2 asset in {path}")
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
            if not isinstance(begin, str) or not isinstance(end, str):
                raise ReleaseError(f"invalid schema v2 managed region in {path}")
            managed_regions.append({"path": target, "begin": begin, "end": end})
        configs.append(
            (
                path,
                {
                    "schema_version": 1,
                    "stamp": stamp,
                    "whole_files": sorted(set(whole_files)),
                    "managed_regions": managed_regions,
                    "managed_markdown": managed_markdown,
                },
            )
        )
    return configs


def _change_ownership(
    repo: Path, path: str, configs: list[tuple[Path, dict[str, object]]]
) -> tuple[Path | None, bool, bool]:
    current_path = repo / path
    current = current_path.read_bytes() if current_path.is_file() else None
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
            if not isinstance(begin, str) or not isinstance(end, str):
                raise ReleaseError(f"invalid managed region in {config_path}")
            before_managed, before_project = _region_parts(before, begin, end)
            current_managed, current_project = _region_parts(current, begin, end)
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
            if not isinstance(headings, list) or not all(
                isinstance(item, str) for item in headings
            ) or not isinstance(additive_headings, list) or not all(
                isinstance(item, str) for item in additive_headings
            ) or not isinstance(keyed_tables, list):
                raise ReleaseError(f"invalid managed Markdown headings in {config_path}")
            before_managed, before_project = _managed_markdown_parts(
                before, headings, additive_headings, keyed_tables
            )
            current_managed, current_project = _managed_markdown_parts(
                current, headings, additive_headings, keyed_tables
            )
            return (
                config_path,
                before_managed != current_managed,
                before_project != current_project,
            )
    return None, False, True


def is_bridgeforge_factory(repo: Path) -> bool:
    return (
        (repo / "templates" / "codex").is_dir()
        and (repo / "templates" / "claude").is_dir()
        and (repo / "skills" / "bridgeforge" / "SKILL.md").is_file()
    )


def classify_changes(repo: Path, changed_paths: set[str]) -> str:
    if is_bridgeforge_factory(repo):
        return "factory"
    configs = _load_managed_configs(repo)
    if not configs:
        return "project"

    changed_stamps: set[Path] = set()
    for config_path, config in configs:
        stamp = config.get("stamp")
        if isinstance(stamp, str) and stamp in changed_paths:
            changed_stamps.add(config_path)

    managed: set[str] = set()
    project: set[str] = set()
    owners_with_changes: set[Path] = set()
    for path in changed_paths:
        owner, managed_changed, project_changed = _change_ownership(repo, path, configs)
        if managed_changed:
            managed.add(path)
            if owner is not None:
                owners_with_changes.add(owner)
        if project_changed:
            project.add(path)

    unauthorized = owners_with_changes - changed_stamps
    if unauthorized:
        labels = ", ".join(str(path.relative_to(repo)) for path in sorted(unauthorized))
        raise ReleaseError(
            "managed skeleton files changed outside /bridgeforge; missing updated skeleton stamp for "
            + labels
        )
    if managed and not project:
        return "skeleton-only"
    if managed and project:
        return "mixed"
    return "project"


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
        if any(item.startswith((".codex/", ".claude/", "scripts/", "tests/")) for item in source_paths):
            tags.append("repo")
        if any(item.startswith("doc/") or item in {"README.md", "AGENTS.md", "CLAUDE.md"} for item in source_paths):
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


def build_release_plan(repo: Path, message: str, changed_paths: set[str]) -> ReleasePlan | None:
    info = parse_commit_message(message)
    classification = classify_changes(repo, changed_paths)
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
