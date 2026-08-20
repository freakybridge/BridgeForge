#!/usr/bin/env python3
"""Verify one bridgeforge-codex current-only project baseline.

The project contract describes only the version installed in that project.
No historical release, retirement, or migration evidence is accepted here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA_VERSION = 3
MINIMUM_CURRENT_BASELINE = (1, 4, 28)
MANAGED_HOOK_PREFIX = "bridgeforge-codex.project-hook.v1:"
FACTORY_MANIFEST = "bridgeforge-codex-manifest.json"
FACTORY_MANIFEST_REMOTE = "https://github.com/freakybridge/BridgeForgeCodex.git"
FACTORY_WITNESSES = (
    "templates/managed-skeleton.json",
    "skills/bridgeforge-codex/SKILL.md",
    "scripts/bridgeforge_codex_project_sync.py",
)
HASH_RE = re.compile(r"sha256:[0-9a-f]{64}")
PROJECT_NAME_CLONE_RE = re.compile(
    r"(?m)^(git clone <repo_url> )"
    r"([A-Za-z0-9._-]+|\{\{PROJECT_NAME\}\})"
    r"( && cd )\2([ \t]*)$"
)


class BaselineError(RuntimeError):
    """The current-only baseline cannot prove the managed project state."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _loads_json(text: str) -> Any:
    return json.loads(text, object_pairs_hook=_unique_object)


@dataclass(frozen=True)
class BaselineReport:
    version: str
    fingerprint: str
    checked_assets: tuple[str, ...]
    skipped_project_assets: tuple[str, ...]


@dataclass(frozen=True)
class RepositoryRole:
    kind: str
    reason: str = ""


@dataclass(frozen=True)
class OwnershipProjection:
    public_sha256: str
    project_sha256: str


def _git_bytes(payload: bytes) -> bytes:
    if b"\0" in payload:
        return payload
    return payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _sha(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(_git_bytes(payload)).hexdigest()


def _canonical_sha(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _semver(value: object, label: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", str(value))
    if match is None:
        raise BaselineError(f"{label} is not MAJOR.MINOR.PATCH: {value!r}")
    return tuple(int(item) for item in match.groups())  # type: ignore[return-value]


def _inside(root: Path, relative: object, label: str) -> Path:
    if not isinstance(relative, str) or not relative or any(char in relative for char in "*?["):
        raise BaselineError(f"{label} must be one explicit relative path")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise BaselineError(f"{label} escapes the project root: {relative}") from exc
    return candidate


def _factory_relative(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise BaselineError(f"{label} must use one explicit POSIX relative path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != value
        or any(char in value for char in "*?[")
    ):
        raise BaselineError(f"{label} is unsafe: {value!r}")
    return path.as_posix()


def _managed_target_key(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise BaselineError(f"{label} must use one explicit POSIX relative path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != value
        or any(char in value for char in "*?[")
    ):
        raise BaselineError(f"{label} is unsafe: {value!r}")
    return path.as_posix().casefold()


def validate_factory_manifest_path(
    manifest_path: Path,
    *,
    repository_root: Path | None = None,
    validate_sources: bool = False,
) -> dict[str, Any]:
    try:
        path = manifest_path.resolve()
        root = (repository_root or path.parent).resolve()
        manifest = _loads_json(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise BaselineError(f"factory manifest is invalid: {exc}") from exc
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema_version", "canonical_remote", "branch", "platforms"
    }:
        raise BaselineError("factory manifest top-level fields are not exact")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("canonical_remote") != FACTORY_MANIFEST_REMOTE
        or manifest.get("branch") != "main"
    ):
        raise BaselineError("factory manifest identity is invalid")
    platforms = manifest.get("platforms")
    if not isinstance(platforms, dict) or set(platforms) != {"codex"}:
        raise BaselineError("factory manifest must expose only codex")
    codex = platforms["codex"]
    if (
        not isinstance(codex, dict)
        or set(codex) != {"target", "skills"}
        or codex.get("target") != "~/.codex/skills"
        or not isinstance(codex.get("skills"), list)
    ):
        raise BaselineError("factory manifest codex platform is invalid")
    names: set[str] = set()
    for skill in codex["skills"]:
        if not isinstance(skill, dict) or set(skill) != {"name", "files"}:
            raise BaselineError("factory manifest skill fields are not exact")
        name = skill.get("name")
        if (
            not isinstance(name, str)
            or re.fullmatch(r"[a-z0-9][a-z0-9-]*", name) is None
            or name.casefold() in names
            or not isinstance(skill.get("files"), list)
            or not skill["files"]
        ):
            raise BaselineError(f"factory manifest skill is invalid: {name!r}")
        names.add(name.casefold())
        targets: set[str] = set()
        for item in skill["files"]:
            if not isinstance(item, dict) or set(item) != {"source", "target", "sha256"}:
                raise BaselineError(f"factory manifest file fields are not exact: {name}")
            source_relative = _factory_relative(item.get("source"), f"{name} source")
            target = _factory_relative(item.get("target"), f"{name} target")
            if target.casefold() in targets:
                raise BaselineError(f"duplicate target path in factory manifest: {name}/{target}")
            targets.add(target.casefold())
            expected = item.get("sha256")
            if not isinstance(expected, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", expected) is None:
                raise BaselineError(f"factory manifest hash is invalid: {name}/{target}")
            if validate_sources:
                source = (root / source_relative).resolve()
                try:
                    source.relative_to(root)
                except ValueError as exc:
                    raise BaselineError(
                        f"factory manifest source escapes root: {source_relative}"
                    ) from exc
                if not source.is_file():
                    raise BaselineError(f"factory manifest source is missing: {source_relative}")
                if _sha(source.read_bytes()) != expected:
                    raise BaselineError(f"factory manifest source hash drifted: {source_relative}")
    if "bridgeforge-codex" not in names:
        raise BaselineError("factory manifest must include bridgeforge-codex")
    return manifest


def _factory_manifest_identity(path: Path) -> None:
    validate_factory_manifest_path(
        path,
        repository_root=path.parent,
        validate_sources=True,
    )


def detect_repository_role(project_root: Path) -> RepositoryRole:
    """Return the single current repository role without version heuristics."""

    root = project_root.resolve()
    manifest = root / FACTORY_MANIFEST
    witness_state = tuple((root / relative).is_file() for relative in FACTORY_WITNESSES)
    if manifest.is_file():
        try:
            _factory_manifest_identity(manifest)
        except BaselineError as exc:
            return RepositoryRole("ambiguous", str(exc))
        if all(witness_state):
            return RepositoryRole("factory")
        missing = [
            relative
            for relative, present in zip(FACTORY_WITNESSES, witness_state)
            if not present
        ]
        return RepositoryRole(
            "ambiguous",
            "factory manifest exists but integrity witnesses are missing: "
            + ", ".join(missing),
        )
    if any(witness_state):
        present = [
            relative
            for relative, exists in zip(FACTORY_WITNESSES, witness_state)
            if exists
        ]
        return RepositoryRole(
            "ambiguous",
            "factory support files exist without the factory manifest: "
            + ", ".join(present),
        )
    return RepositoryRole("downstream")


def _reject_noncurrent(value: Any, path: str = "contract") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if re.search(r"histor|legacy|retir|migration", key, re.I):
                raise BaselineError(f"current-only contract contains non-current key {path}.{key}")
            if key == "strategy" and child == "retirement":
                raise BaselineError(f"current-only contract contains a retirement asset at {path}")
            _reject_noncurrent(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_noncurrent(child, f"{path}[{index}]")


def load_contract(path: Path) -> dict[str, Any]:
    try:
        contract = _loads_json(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise BaselineError(f"current baseline is missing or invalid: {path}: {exc}") from exc
    if not isinstance(contract, dict):
        raise BaselineError("current baseline root must be an object")
    allowed_top = {
        "schema_version", "release_version", "host", "stamp",
        "contract_target", "baseline_model", "assets",
    }
    if set(contract) != allowed_top:
        raise BaselineError("current baseline top-level fields are not schema 3 exact")
    _reject_noncurrent(contract)
    if contract.get("schema_version") != SCHEMA_VERSION:
        raise BaselineError(f"current baseline must use schema_version {SCHEMA_VERSION}")
    if contract.get("baseline_model") != "current-only" or contract.get("host") != "codex":
        raise BaselineError("current baseline identity is invalid")
    version = str(contract.get("release_version", ""))
    if _semver(version, "current baseline release_version") < MINIMUM_CURRENT_BASELINE:
        raise BaselineError("current baseline predates 1.4.28")
    assets = contract.get("assets")
    if not isinstance(assets, list) or not assets:
        raise BaselineError("current baseline has no assets")
    ids: set[str] = set()
    targets: set[str] = set()
    for asset in assets:
        if not isinstance(asset, dict):
            raise BaselineError("current baseline contains a non-object asset")
        allowed_asset = {
            "id", "source", "target", "strategy", "current_sha256", "render",
            "agents_zones", "managed_blocks", "merge_policy", "merge_validation",
            "region",
        }
        unknown_fields = set(asset) - allowed_asset
        if unknown_fields:
            raise BaselineError(
                "current baseline asset has non-schema fields: "
                + ", ".join(sorted(unknown_fields))
            )
        asset_id = asset.get("id")
        source_name = asset.get("source")
        target = asset.get("target")
        strategy = asset.get("strategy")
        if (
            not isinstance(asset_id, str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", asset_id)
            or asset_id in ids
        ):
            raise BaselineError(f"invalid or duplicate asset id: {asset_id!r}")
        target_key = _managed_target_key(target, f"asset {asset_id} target")
        if target_key in targets:
            raise BaselineError(f"invalid or duplicate asset target: {target!r}")
        if not isinstance(source_name, str) or not source_name:
            raise BaselineError(f"asset {asset_id} has no explicit source")
        source_path = PurePosixPath(source_name.replace("\\", "/"))
        if source_path.is_absolute() or ".." in source_path.parts:
            raise BaselineError(f"asset {asset_id} source escapes the project root")
        if strategy not in {"whole", "merge", "region", "seed"}:
            raise BaselineError(f"asset {asset_id} has unsupported strategy {strategy!r}")
        source_hash = asset.get("current_sha256")
        if not isinstance(source_hash, str) or HASH_RE.fullmatch(source_hash) is None:
            raise BaselineError(f"asset {asset_id} has no current source hash")
        managed = asset.get("managed_blocks")
        if isinstance(managed, dict):
            projection_hash = managed.get("current_projection_sha256")
            if not isinstance(projection_hash, str) or HASH_RE.fullmatch(projection_hash) is None:
                raise BaselineError(
                    f"asset {asset_id} has no current Markdown projection"
                )
            if not isinstance(managed.get("headings"), list) or not isinstance(
                managed.get("keyed_tables"), list
            ):
                raise BaselineError(f"asset {asset_id} Markdown ownership is invalid")
            for table in managed["keyed_tables"]:
                if (
                    not isinstance(table, dict)
                    or not isinstance(table.get("heading"), str)
                    or not isinstance(table.get("managed_keys"), list)
                ):
                    raise BaselineError(f"asset {asset_id} Markdown table ownership is invalid")
        zones = asset.get("agents_zones")
        if zones is not None:
            if not isinstance(zones, dict):
                raise BaselineError(f"asset {asset_id} AGENTS ownership is invalid")
            for zone_name in ("public", "project"):
                zone = zones.get(zone_name)
                if (
                    not isinstance(zone, dict)
                    or not isinstance(zone.get("begin"), str)
                    or not isinstance(zone.get("end"), str)
                ):
                    raise BaselineError(f"asset {asset_id} AGENTS {zone_name} zone is invalid")
            public_hash = zones["public"].get("current_sha256")
            if not isinstance(public_hash, str) or HASH_RE.fullmatch(public_hash) is None:
                raise BaselineError(f"asset {asset_id} AGENTS public hash is invalid")
        region = asset.get("region")
        if strategy == "region":
            if (
                not isinstance(region, dict)
                or not isinstance(region.get("begin"), str)
                or not isinstance(region.get("end"), str)
                or not isinstance(region.get("current_sha256"), str)
                or HASH_RE.fullmatch(str(region.get("current_sha256"))) is None
            ):
                raise BaselineError(f"asset {asset_id} region ownership is invalid")
        if strategy == "merge" and asset.get("merge_policy") != "codex-hooks":
            validation = asset.get("merge_validation")
            if (
                not isinstance(validation, dict)
                or validation.get("format") != "json-subset-current-v1"
                or not isinstance(validation.get("required"), dict)
            ):
                raise BaselineError(f"asset {asset_id} has no current merge projection")
        ids.add(asset_id)
        targets.add(target_key)
    return contract


def _marker_block(payload: bytes, begin: str, end: str) -> bytes:
    normalized = _git_bytes(payload)
    begin_line = begin.encode("utf-8")
    end_line = end.encode("utf-8")
    lines = normalized.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.rstrip(b"\n") == begin_line]
    stops = [index for index, line in enumerate(lines) if line.rstrip(b"\n") == end_line]
    if len(starts) != 1 or len(stops) != 1 or starts[0] >= stops[0]:
        raise BaselineError(f"managed markers are missing or duplicated: {begin} / {end}")
    return b"".join(lines[starts[0] : stops[0] + 1])


def _without_marker_blocks(
    payload: bytes,
    markers: list[tuple[str, str]],
) -> bytes:
    normalized = _git_bytes(payload)
    lines = normalized.splitlines(keepends=True)
    owned: set[int] = set()
    for begin, end in markers:
        begin_line = begin.encode("utf-8")
        end_line = end.encode("utf-8")
        starts = [
            index for index, line in enumerate(lines)
            if line.rstrip(b"\n") == begin_line
        ]
        stops = [
            index for index, line in enumerate(lines)
            if line.rstrip(b"\n") == end_line
        ]
        if len(starts) != 1 or len(stops) != 1 or starts[0] >= stops[0]:
            raise BaselineError(
                f"managed markers are missing or duplicated: {begin} / {end}"
            )
        span = set(range(starts[0], stops[0] + 1))
        if owned.intersection(span):
            raise BaselineError("managed marker regions overlap")
        owned.update(span)
    return b"".join(line for index, line in enumerate(lines) if index not in owned)


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value = _loads_json(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise BaselineError(f"managed JSON is invalid: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BaselineError(f"managed JSON root must be an object: {path}")
    return value


def _deep_subset(expected: Any, actual: Any, path: str) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise BaselineError(f"managed JSON value drifted: {path}")
        for key, value in expected.items():
            if key not in actual:
                raise BaselineError(f"managed JSON key is missing: {path}.{key}")
            _deep_subset(value, actual[key], f"{path}.{key}")
        return
    if expected != actual:
        raise BaselineError(f"managed JSON value drifted: {path}")


def _hook_handlers(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    hooks = document.get("hooks")
    if not isinstance(hooks, dict):
        raise BaselineError("hooks.json has no hooks object")
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                continue
            for handler in entry["hooks"]:
                if not isinstance(handler, dict):
                    continue
                handler_id = handler.get("bridgeforgeCodexId")
                if isinstance(handler_id, str):
                    if handler_id in result:
                        raise BaselineError(f"managed hook handler is duplicated: {handler_id}")
                    result[handler_id] = {
                        "event": str(event),
                        "matcher": str(entry.get("matcher", "")),
                        "handler": handler,
                    }
    return result


def _verify_hooks(
    target: Path,
    asset: dict[str, Any],
    source: Path | None = None,
) -> None:
    actual = _json_object(target)
    if source is not None:
        expected_document = _json_object(source)
        expected_handlers = _hook_handlers(expected_document)
        actual_handlers = _hook_handlers(actual)
        expected_managed = {
            item for item in expected_handlers if item.startswith(MANAGED_HOOK_PREFIX)
        }
        actual_managed = {
            item for item in actual_handlers if item.startswith(MANAGED_HOOK_PREFIX)
        }
        if actual_managed != expected_managed:
            raise BaselineError("managed hook handler identity set drifted")
        for handler_id in expected_managed:
            if actual_handlers.get(handler_id) != expected_handlers.get(handler_id):
                raise BaselineError(f"managed hook handler drifted: {handler_id}")
        if "description" in expected_document:
            _deep_subset(
                {"description": expected_document["description"]},
                actual,
                "hooks.json",
            )
        return
    validation = asset.get("merge_validation")
    required = validation.get("required_handlers") if isinstance(validation, dict) else None
    if not isinstance(required, list):
        raise BaselineError("hooks current ownership is missing")
    handlers = _hook_handlers(actual)
    expected_managed = {str(record.get("id")) for record in required}
    actual_managed = {
        item for item in handlers if item.startswith(MANAGED_HOOK_PREFIX)
    }
    if actual_managed != expected_managed:
        raise BaselineError("managed hook handler identity set drifted")
    for record in required:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            raise BaselineError("hooks current ownership contains an invalid handler")
        handler_id = str(record["id"])
        handler_record = handlers.get(handler_id)
        if handler_record is None:
            raise BaselineError(f"managed hook handler is missing: {handler_id}")
        if handler_record["event"] != record.get("event"):
            raise BaselineError(f"managed hook event drifted: {handler_id}")
        if handler_record["matcher"] != record.get("matcher"):
            raise BaselineError(f"managed hook matcher drifted: {handler_id}")
        if _canonical_sha(handler_record["handler"]) != record.get("sha256"):
            raise BaselineError(f"managed hook handler drifted: {handler_id}")
    top = validation.get("managed_top_level")
    if isinstance(top, dict):
        _deep_subset(top, actual, "hooks.json")


def _heading_section(payload: bytes, heading: str) -> bytes:
    normalized = _git_bytes(payload)
    lines = normalized.splitlines(keepends=True)
    wanted = heading.encode("utf-8")
    starts = [index for index, line in enumerate(lines) if line.rstrip(b"\n") == wanted]
    if len(starts) != 1:
        raise BaselineError(f"Markdown heading is missing or duplicated: {heading}")
    level = len(heading) - len(heading.lstrip("#"))
    stop = len(lines)
    for index in range(starts[0] + 1, len(lines)):
        stripped = lines[index].rstrip(b"\n")
        match = re.match(br"^(#{1,6})\s", stripped)
        if match is not None and len(match.group(1)) <= level:
            stop = index
            break
    return b"".join(lines[starts[0] : stop])


def _table_rows(section: bytes) -> dict[str, bytes]:
    lines = section.splitlines(keepends=True)
    table = [line for line in lines if line.lstrip().startswith(b"|")]
    if len(table) < 2:
        raise BaselineError("managed Markdown table is missing")
    result: dict[str, bytes] = {}
    for line in table[2:]:
        cells = [cell.strip() for cell in line.strip().strip(b"|").split(b"|")]
        if not cells:
            continue
        key = cells[0].decode("utf-8").strip()
        link = re.fullmatch(r"\[`[^`]+`\]\(([^)]+)\)", key)
        if link is not None:
            key = link.group(1)
        key = key.strip("`").casefold()
        if key in result:
            raise BaselineError(f"managed Markdown table key is duplicated: {key}")
        result[key] = _git_bytes(line)
    return result


def _markdown_projection(payload: bytes, managed: dict[str, Any]) -> dict[str, Any]:
    headings = {
        str(heading): _sha(_heading_section(payload, str(heading)))
        for heading in managed.get("headings", [])
    }
    tables: dict[str, dict[str, str]] = {}
    for table in managed.get("keyed_tables", []):
        heading = str(table["heading"])
        rows = _table_rows(_heading_section(payload, heading))
        projected: dict[str, str] = {}
        for raw_key in table["managed_keys"]:
            key = str(raw_key).strip().strip("`").casefold()
            if key not in rows:
                raise BaselineError(
                    f"managed Markdown row is missing: {heading} :: {raw_key}"
                )
            projected[key] = _sha(rows[key])
        tables[heading] = projected
    return {"headings": headings, "keyed_tables": tables}


def _json_payload(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = _loads_json(_git_bytes(payload).decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise BaselineError(f"{label} is invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise BaselineError(f"{label} JSON root must be an object")
    return value


def _hooks_ownership_views(document: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    hooks = document.get("hooks")
    if not isinstance(hooks, dict):
        raise BaselineError("hooks.json has no hooks object")
    managed: list[dict[str, Any]] = []
    project: list[dict[str, Any]] = []
    seen_managed: set[str] = set()
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            raise BaselineError(f"hooks.json event is invalid: {event}")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                raise BaselineError(f"hooks.json group is invalid: {event}")
            matcher = str(entry.get("matcher", ""))
            for handler in entry["hooks"]:
                if not isinstance(handler, dict):
                    raise BaselineError(f"hooks.json handler is invalid: {event}")
                record = {
                    "event": str(event),
                    "matcher": matcher,
                    "handler": handler,
                }
                handler_id = handler.get("bridgeforgeCodexId")
                if isinstance(handler_id, str) and handler_id.startswith(
                    MANAGED_HOOK_PREFIX
                ):
                    if handler_id in seen_managed:
                        raise BaselineError(
                            f"managed hook handler is duplicated: {handler_id}"
                        )
                    seen_managed.add(handler_id)
                    managed.append(record)
                else:
                    project.append(record)
    public_view = {
        "description": document.get("description"),
        "handlers": managed,
    }
    project_view = {
        "top_level": {
            key: value
            for key, value in document.items()
            if key not in {"description", "hooks"}
        },
        "handlers": project,
    }
    return public_view, project_view


def _split_json_ownership(
    required: Any,
    actual: Any,
    path: str,
) -> tuple[Any, Any]:
    if not isinstance(required, dict):
        if required != actual:
            raise BaselineError(f"managed JSON value drifted: {path}")
        return actual, None
    if not isinstance(actual, dict):
        raise BaselineError(f"managed JSON value drifted: {path}")
    public: dict[str, Any] = {}
    project: dict[str, Any] = {
        key: value for key, value in actual.items() if key not in required
    }
    for key, expected in required.items():
        if key not in actual:
            raise BaselineError(f"managed JSON key is missing: {path}.{key}")
        public_value, project_value = _split_json_ownership(
            expected,
            actual[key],
            f"{path}.{key}",
        )
        public[key] = public_value
        if project_value not in (None, {}, []):
            project[key] = project_value
    return public, project


def _markdown_project_payload(payload: bytes, managed: dict[str, Any]) -> bytes:
    project = _git_bytes(payload)
    for heading in managed.get("headings", []):
        section = _heading_section(project, str(heading))
        project = project.replace(section, b"", 1)
    for table in managed.get("keyed_tables", []):
        heading = str(table["heading"])
        section = _heading_section(project, heading)
        rows = _table_rows(section)
        project_section = section
        for raw_key in table["managed_keys"]:
            key = str(raw_key).strip().strip("`").casefold()
            if key not in rows:
                raise BaselineError(
                    f"managed Markdown row is missing: {heading} :: {raw_key}"
                )
            project_section = project_section.replace(rows[key], b"", 1)
        project = project.replace(section, project_section, 1)
    return project


def ownership_projection(
    asset: dict[str, Any],
    payload: bytes,
    project_root: Path,
) -> OwnershipProjection:
    """Project one managed target into stable public and project views."""

    del project_root
    empty = _canonical_sha({})
    zones = asset.get("agents_zones")
    if isinstance(zones, dict):
        public = zones["public"]
        project = zones["project"]
        public_block = _marker_block(payload, public["begin"], public["end"])
        project_block = _marker_block(payload, project["begin"], project["end"])
        outside = _without_marker_blocks(
            payload,
            [
                (public["begin"], public["end"]),
                (project["begin"], project["end"]),
            ],
        )
        return OwnershipProjection(
            _sha(public_block),
            _canonical_sha({"project": _sha(project_block), "outside": _sha(outside)}),
        )
    managed_blocks = asset.get("managed_blocks")
    if isinstance(managed_blocks, dict):
        return OwnershipProjection(
            _canonical_sha(_markdown_projection(payload, managed_blocks)),
            _sha(_markdown_project_payload(payload, managed_blocks)),
        )
    strategy = str(asset.get("strategy"))
    if strategy == "region":
        region = asset.get("region")
        if not isinstance(region, dict):
            raise BaselineError("managed region ownership is missing")
        block = _marker_block(payload, region["begin"], region["end"])
        outside = _without_marker_blocks(payload, [(region["begin"], region["end"])])
        return OwnershipProjection(_sha(block), _sha(outside))
    if strategy == "merge":
        document = _json_payload(payload, str(asset.get("target", "managed JSON")))
        if asset.get("merge_policy") == "codex-hooks":
            public, project = _hooks_ownership_views(document)
        else:
            validation = asset.get("merge_validation")
            required = validation.get("required") if isinstance(validation, dict) else None
            if not isinstance(required, dict):
                raise BaselineError("managed JSON ownership is missing")
            public, project = _split_json_ownership(required, document, "managed JSON")
        return OwnershipProjection(_canonical_sha(public), _canonical_sha(project))
    if strategy == "seed":
        return OwnershipProjection(empty, _sha(payload))
    if strategy == "whole":
        return OwnershipProjection(_sha(payload), empty)
    raise BaselineError(f"unsupported ownership strategy: {strategy}")


def _verify_markdown(
    target: Path,
    source: Path | None,
    managed: dict[str, Any],
) -> None:
    actual = target.read_bytes()
    if source is None:
        if _canonical_sha(_markdown_projection(actual, managed)) != managed.get(
            "current_projection_sha256"
        ):
            raise BaselineError(f"managed Markdown projection drifted: {target}")
        return
    canonical = source.read_bytes()
    for heading in managed.get("headings", []):
        if _heading_section(actual, str(heading)) != _heading_section(canonical, str(heading)):
            raise BaselineError(f"managed Markdown heading drifted: {heading}")
    for table in managed.get("keyed_tables", []):
        heading = str(table["heading"])
        actual_rows = _table_rows(_heading_section(actual, heading))
        canonical_rows = _table_rows(_heading_section(canonical, heading))
        for raw_key in table["managed_keys"]:
            key = str(raw_key).strip().strip("`").casefold()
            if actual_rows.get(key) != canonical_rows.get(key):
                raise BaselineError(f"managed Markdown row drifted: {heading} :: {raw_key}")


def _normalized_render_hash(payload: bytes, asset: dict[str, Any], project_root: Path) -> str:
    del project_root
    if asset.get("render") != "project-name":
        return _sha(payload)
    try:
        text = _git_bytes(payload).decode("utf-8-sig")
    except UnicodeDecodeError:
        return _sha(payload)
    text = PROJECT_NAME_CLONE_RE.sub(
        r"\1{{PROJECT_NAME}}\3{{PROJECT_NAME}}\4",
        text,
    )
    return _sha(text.encode("utf-8"))


def _head_contract_bytes(project_root: Path) -> bytes | None:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=project_root,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if head.returncode != 0:
            return None
        result = subprocess.run(
            ["git", "show", "HEAD:.codex/managed-skeleton.json"],
            cwd=project_root,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise BaselineError(f"cannot read trusted HEAD baseline: {exc}") from exc
    return result.stdout if result.returncode == 0 else None


def _verify_contract_anchor(contract_bytes: bytes, anchor_bytes: bytes | None) -> None:
    if anchor_bytes is None or _git_bytes(contract_bytes) == _git_bytes(anchor_bytes):
        return
    try:
        current = _loads_json(contract_bytes.decode("utf-8-sig"))
        anchor = _loads_json(anchor_bytes.decode("utf-8-sig"))
        current_version = _semver(current.get("release_version"), "current release")
        anchor_version = _semver(anchor.get("release_version"), "HEAD release")
    except (UnicodeDecodeError, ValueError, AttributeError) as exc:
        raise BaselineError(f"trusted HEAD baseline is unreadable: {exc}") from exc
    if current_version <= anchor_version:
        raise BaselineError(
            "current contract differs from trusted HEAD without a forward release transition"
        )


def _verify_source_contract(
    source: Path,
    asset: dict[str, Any],
    project_root: Path,
) -> None:
    asset_id = str(asset["id"])
    payload = source.read_bytes()
    if _normalized_render_hash(payload, asset, project_root) != asset.get("current_sha256"):
        raise BaselineError(f"current contract source hash is stale: {asset_id}")
    if asset.get("agents_zones") is not None:
        public = asset["agents_zones"]["public"]
        if _sha(_marker_block(payload, public["begin"], public["end"])) != public.get(
            "current_sha256"
        ):
            raise BaselineError(f"current AGENTS projection is stale: {asset_id}")
    managed = asset.get("managed_blocks")
    if isinstance(managed, dict):
        if _canonical_sha(_markdown_projection(payload, managed)) != managed.get(
            "current_projection_sha256"
        ):
            raise BaselineError(f"current Markdown projection is stale: {asset_id}")
    if asset.get("strategy") == "region":
        region = asset["region"]
        if _sha(_marker_block(payload, region["begin"], region["end"])) != region.get(
            "current_sha256"
        ):
            raise BaselineError(f"current region projection is stale: {asset_id}")
    if asset.get("strategy") == "merge":
        if asset.get("merge_policy") == "codex-hooks":
            _verify_hooks(source, asset)
        else:
            _deep_subset(
                asset["merge_validation"]["required"],
                _json_object(source),
                str(asset["source"]),
            )


def verify_current_baseline(
    project_root: Path,
    *,
    expected_version: str | None = None,
    contract_path: Path | None = None,
    prospective_version: str | None = None,
    anchor_contract: bytes | None = None,
    use_git_anchor: bool = True,
) -> BaselineReport:
    root = project_root.resolve()
    path = contract_path or root / ".codex" / "managed-skeleton.json"
    contract = load_contract(path)
    _verify_contract_anchor(
        path.read_bytes(),
        _head_contract_bytes(root) if use_git_anchor and anchor_contract is None else anchor_contract,
    )
    version = str(contract["release_version"])
    stamp = _inside(root, contract.get("stamp"), "current baseline stamp")
    repository_role = detect_repository_role(root)
    if repository_role.kind == "ambiguous":
        raise BaselineError(f"repository role is ambiguous: {repository_role.reason}")
    factory = repository_role.kind == "factory"
    if prospective_version is not None:
        stamp_version = prospective_version
    elif stamp.is_file():
        stamp_version = stamp.read_text(encoding="utf-8-sig").strip()
    elif factory and (root / "VERSION").is_file():
        stamp_version = (root / "VERSION").read_text(
            encoding="utf-8-sig"
        ).strip()
    else:
        raise BaselineError("current baseline version stamp is missing")
    if stamp_version != version or (expected_version is not None and version != expected_version):
        raise BaselineError(
            f"current baseline identity mismatch: contract={version}, stamp={stamp_version}, expected={expected_version}"
        )
    checked: list[str] = []
    skipped: list[str] = []
    for asset in contract["assets"]:
        asset_id = str(asset["id"])
        target = _inside(root, asset["target"], f"asset {asset_id} target")
        strategy = str(asset["strategy"])
        if strategy == "seed":
            skipped.append(asset_id)
            continue
        if not target.is_file():
            raise BaselineError(f"managed asset is missing: {asset_id}: {asset['target']}")
        source: Path | None = None
        raw_source = asset.get("source")
        factory_source = (
            _inside(root, raw_source, f"asset {asset_id} source")
            if isinstance(raw_source, str)
            else None
        )
        if factory_source is not None and factory_source.is_file():
            source = factory_source
            _verify_source_contract(source, asset, root)
        if asset.get("agents_zones") is not None:
            zones = asset["agents_zones"]
            public = zones["public"]
            actual_block = _marker_block(target.read_bytes(), public["begin"], public["end"])
            if source is not None:
                expected_block = _marker_block(source.read_bytes(), public["begin"], public["end"])
                if _normalized_render_hash(
                    actual_block, asset, root
                ) != _normalized_render_hash(expected_block, asset, root):
                    raise BaselineError(f"managed AGENTS public zone drifted: {asset_id}")
            elif _normalized_render_hash(
                actual_block, asset, root
            ) != public.get("current_sha256"):
                raise BaselineError(f"managed AGENTS public zone drifted: {asset_id}")
        elif (
            isinstance(asset.get("managed_blocks"), dict)
            and factory
            and asset_id == "codex.doc.readme"
        ):
            # The factory index catalogs product-delivery records rather than the
            # downstream starter rows; its template source hash is still checked.
            skipped.append(asset_id)
            continue
        elif isinstance(asset.get("managed_blocks"), dict):
            _verify_markdown(target, source, asset["managed_blocks"])
        elif strategy == "merge":
            if asset.get("merge_policy") == "codex-hooks":
                _verify_hooks(target, asset, source)
            elif source is not None:
                _deep_subset(_json_object(source), _json_object(target), str(asset["target"]))
            else:
                validation = asset["merge_validation"]
                _deep_subset(
                    validation["required"],
                    _json_object(target),
                    str(asset["target"]),
                )
        elif strategy == "region":
            region = asset.get("region")
            if not isinstance(region, dict):
                raise BaselineError(f"managed region ownership is missing: {asset_id}")
            block = _marker_block(target.read_bytes(), str(region["begin"]), str(region["end"]))
            expected_block = (
                _marker_block(source.read_bytes(), str(region["begin"]), str(region["end"]))
                if source is not None
                else None
            )
            if (
                expected_block is not None and block != expected_block
            ) or (
                expected_block is None and _sha(block) != region.get("current_sha256")
            ):
                raise BaselineError(f"managed region drifted: {asset_id}")
        else:
            expected_hash = (
                _normalized_render_hash(source.read_bytes(), asset, root)
                if source is not None
                else str(asset.get("current_sha256"))
            )
            if _normalized_render_hash(target.read_bytes(), asset, root) != expected_hash:
                raise BaselineError(f"managed asset drifted: {asset_id}: {asset['target']}")
        checked.append(asset_id)
    fingerprint = _canonical_sha({
        "version": version,
        "contract": _sha(path.read_bytes()),
        "checked": checked,
    })
    return BaselineReport(version, fingerprint, tuple(checked), tuple(skipped))


def verify_index_baseline(
    project_root: Path,
    *,
    expected_version: str | None = None,
) -> BaselineReport:
    """Verify the exact Git index tree without reading unstaged worktree bytes."""

    root = project_root.resolve()
    anchor = _head_contract_bytes(root)
    with tempfile.TemporaryDirectory(prefix="bridgeforge-current-index-") as raw:
        export_root = Path(raw) / "index"
        export_root.mkdir()
        prefix = export_root.as_posix().rstrip("/") + "/"
        try:
            result = subprocess.run(
                ["git", "checkout-index", "--all", f"--prefix={prefix}"],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BaselineError(f"cannot export Git index: {exc}") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            raise BaselineError(f"cannot export Git index: {detail}")
        return verify_current_baseline(
            export_root,
            expected_version=expected_version,
            anchor_contract=anchor,
            use_git_anchor=False,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--expected-version")
    parser.add_argument(
        "--index",
        action="store_true",
        help="verify the exact staged Git index tree",
    )
    args = parser.parse_args(argv)
    try:
        verifier = verify_index_baseline if args.index else verify_current_baseline
        report = verifier(args.project_root, expected_version=args.expected_version)
    except (
        BaselineError,
        OSError,
        UnicodeDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"[current-baseline] BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": "passed",
        "version": report.version,
        "fingerprint": report.fingerprint,
        "checked_assets": list(report.checked_assets),
        "skipped_project_assets": list(report.skipped_project_assets),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
