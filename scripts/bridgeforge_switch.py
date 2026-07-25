#!/usr/bin/env python3
"""Synchronize the other BridgeForge skeleton into the current host.

Both host skeletons remain live.  BridgeForge stores only deterministic
ownership metadata inside the target skeleton and never reads or writes a
project-root ``.bridgeforge`` directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


AGENTS = ("claude", "codex")
SCHEMA_VERSION = 3
MAP_NAME = ".bridgeforge-map.json"
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._:-]{0,199}$")
REASON_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")
STATUSES = {
    "generated",
    "created_unowned",
    "untranslated",
    "conflict",
    "forked_projection",
    "echo_suppressed",
}
ASSET_TYPES = {"portable-text", "shared-json", "host-specific"}
ADAPTERS = {
    ("whole-file", 1),
    ("json-pointer", 1),
    ("none", 1),
}
WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *{f"com{index}" for index in range(1, 10)},
    *{f"lpt{index}" for index in range(1, 10)},
}


@dataclass(frozen=True)
class AgentSpec:
    name: str
    entry: str
    config_dir: str


SPECS = {
    "claude": AgentSpec("claude", "CLAUDE.md", ".claude"),
    "codex": AgentSpec("codex", "AGENTS.md", ".codex"),
}


@dataclass
class LoadedMap:
    path: Path
    state: str
    data: dict[str, Any] | None = None
    error: str | None = None
    raw_sha256: str | None = None


@dataclass
class SyncPlan:
    current_host: str
    source_host: str
    project_root: Path
    template_root: Path
    source_map: LoadedMap
    target_map: LoadedMap
    source_snapshot: dict[str, str]
    source_map_state: tuple[str, str | None]
    target_map_state: tuple[str, str | None]
    target_prestate: dict[str, str | None] = field(default_factory=dict)
    writes: dict[str, bytes] = field(default_factory=dict)
    deletes: set[str] = field(default_factory=set)
    assets: list[dict[str, Any]] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    map_bytes: bytes | None = None

    @property
    def degraded(self) -> bool:
        return any(
            asset["status"] in {
                "created_unowned",
                "untranslated",
                "conflict",
                "forked_projection",
            }
            for asset in self.assets
        ) or any(message.startswith("map-error:") for message in self.messages)


class SyncError(ValueError):
    """Raised when direct synchronization cannot proceed safely."""


class ApplyRolledBackError(RuntimeError):
    """Raised when apply failed and every touched path was restored."""


class RollbackIncompleteError(RuntimeError):
    """Raised when apply failed and rollback evidence is not fully clean."""

    def __init__(self, message: str, evidence: list[str]) -> None:
        super().__init__(message)
        self.evidence = tuple(evidence)


def _sha_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _hash_json(value: Any) -> str:
    return _sha_bytes(_canonical_json(value))


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SyncError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json_bytes(data: bytes, label: str) -> Any:
    try:
        return json.loads(
            data.decode("utf-8-sig"),
            object_pairs_hook=_strict_object,
        )
    except (UnicodeError, json.JSONDecodeError, SyncError) as exc:
        raise SyncError(f"{label} is not strict UTF-8 JSON: {exc}") from exc


def _posix(path: Path) -> str:
    return path.as_posix().rstrip("/")


def _rel(path: Path, root: Path) -> str:
    try:
        return _posix(path.resolve(strict=False).relative_to(root.resolve()))
    except ValueError:
        return _posix(path)


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _is_link_like(path: Path) -> bool:
    if not _lexists(path):
        return False
    if path.is_symlink():
        return True
    try:
        attributes = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _assert_no_links(path: Path, label: str) -> None:
    if not _lexists(path):
        return
    if _is_link_like(path):
        raise SyncError(f"{label} must not be a symlink or junction: {path}")
    if path.is_dir():
        for child in path.rglob("*"):
            if _is_link_like(child):
                raise SyncError(
                    f"{label} contains a symlink or junction: {child}"
                )


def _assert_project_local(path: Path, root: Path, label: str) -> None:
    root = root.resolve()
    resolved = path.resolve(strict=False)
    if resolved != root and not _is_under(resolved, root):
        raise SyncError(f"{label} escapes project root: {path}")
    current = path
    while current != root and _is_under(current, root):
        if _lexists(current) and _is_link_like(current):
            raise SyncError(
                f"{label} crosses a symlink or junction: {_rel(current, root)}"
            )
        current = current.parent


def _safe_rel(raw: str) -> str:
    if not isinstance(raw, str) or "\x00" in raw:
        raise SyncError("path must be a non-empty string")
    normalized = raw.replace("\\", "/").strip("/")
    path = Path(normalized)
    if (
        not normalized
        or path.is_absolute()
        or ".." in path.parts
        or normalized == ".bridgeforge"
        or normalized.startswith(".bridgeforge/")
    ):
        raise SyncError(f"unsafe project-relative path: {raw!r}")
    return _posix(path)


def _windows_path_key(raw: str) -> str:
    rel = _safe_rel(raw)
    result: list[str] = []
    for part in Path(rel).parts:
        if part != part.rstrip(" ."):
            raise SyncError(
                f"Windows-unsafe trailing dot/space component: {raw!r}"
            )
        if ":" in part:
            raise SyncError(f"Windows ADS path is forbidden: {raw!r}")
        normalized = unicodedata.normalize("NFC", part).casefold()
        if normalized.split(".", 1)[0] in WINDOWS_RESERVED_NAMES:
            raise SyncError(f"Windows reserved path component: {raw!r}")
        result.append(normalized)
    return "/".join(result)


def _surface_ok(path: str, host: str) -> bool:
    spec = SPECS[host]
    return path == spec.entry or path.startswith(spec.config_dir + "/")


def _portable_text_path(path: str, host: str) -> bool:
    prefix = SPECS[host].config_dir + "/memory/"
    return path.startswith(prefix) and path.endswith(".md")


def _shared_json_member(member: dict[str, Any], host: str) -> bool:
    return (
        member["path"] == f"{SPECS[host].config_dir}/settings.json"
        and member.get("selector") == "/permissions"
    )


def _map_path(root: Path, host: str) -> Path:
    return root / SPECS[host].config_dir / MAP_NAME


def _member_key(member: dict[str, Any]) -> tuple[str, str]:
    return member["path"], member.get("selector", "")


def _pointer_tokens(pointer: str) -> tuple[str, ...]:
    if not isinstance(pointer, str) or not pointer.startswith("/") or pointer == "/":
        raise SyncError(f"JSON Pointer selector must be non-root: {pointer!r}")
    tokens: list[str] = []
    for raw in pointer[1:].split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if re.search(r"~(?![01])", raw):
            raise SyncError(f"invalid JSON Pointer escape: {pointer!r}")
        tokens.append(token)
    return tuple(tokens)


def _pointer_get(document: Any, pointer: str) -> Any:
    current = document
    for token in _pointer_tokens(pointer):
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit():
            index = int(token)
            if index >= len(current):
                raise KeyError(pointer)
            current = current[index]
        else:
            raise KeyError(pointer)
    return current


def _pointer_set(document: Any, pointer: str, value: Any) -> None:
    tokens = _pointer_tokens(pointer)
    current = document
    for token in tokens[:-1]:
        if isinstance(current, dict):
            child = current.get(token)
            if child is None:
                child = {}
                current[token] = child
            if not isinstance(child, (dict, list)):
                raise SyncError(f"JSON Pointer parent is scalar: {pointer}")
            current = child
        elif isinstance(current, list) and token.isdigit():
            index = int(token)
            if index >= len(current):
                raise SyncError(f"JSON Pointer index is absent: {pointer}")
            current = current[index]
        else:
            raise SyncError(f"JSON Pointer parent is absent: {pointer}")
    leaf = tokens[-1]
    if isinstance(current, dict):
        current[leaf] = value
    elif isinstance(current, list) and leaf.isdigit():
        index = int(leaf)
        if index >= len(current):
            raise SyncError(f"JSON Pointer index is absent: {pointer}")
        current[index] = value
    else:
        raise SyncError(f"JSON Pointer target is not assignable: {pointer}")


def _pointer_delete(document: Any, pointer: str) -> None:
    tokens = _pointer_tokens(pointer)
    current = document
    for token in tokens[:-1]:
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit():
            index = int(token)
            if index >= len(current):
                raise KeyError(pointer)
            current = current[index]
        else:
            raise KeyError(pointer)
    leaf = tokens[-1]
    if isinstance(current, dict) and leaf in current:
        del current[leaf]
    elif isinstance(current, list) and leaf.isdigit():
        index = int(leaf)
        if index >= len(current):
            raise KeyError(pointer)
        del current[index]
    else:
        raise KeyError(pointer)


def _selectors_overlap(first: str, second: str) -> bool:
    a = _pointer_tokens(first)
    b = _pointer_tokens(second)
    return a[: len(b)] == b or b[: len(a)] == a


def _validate_member(
    member: Any,
    host: str,
    *,
    target: bool,
) -> dict[str, Any]:
    if not isinstance(member, dict):
        raise SyncError("map member must be an object")
    required = {"path"} if target else {"path", "sha256"}
    allowed = required | {"selector", "last_generated_sha256"}
    if not target:
        allowed.discard("last_generated_sha256")
    if set(member) - allowed or not required.issubset(member):
        raise SyncError("map member has unknown or missing fields")
    path = _safe_rel(member["path"])
    _windows_path_key(path)
    if not _surface_ok(path, host) or path.endswith("/" + MAP_NAME):
        raise SyncError(f"map member is outside {host} host surface: {path}")
    result = {"path": path}
    hash_key = "last_generated_sha256" if target else "sha256"
    if hash_key in member:
        digest = member[hash_key]
        if not isinstance(digest, str) or not HASH_RE.fullmatch(digest):
            raise SyncError(f"invalid member hash: {path}")
        result[hash_key] = digest
    if "selector" in member:
        _pointer_tokens(member["selector"])
        result["selector"] = member["selector"]
    return result


def _validate_map(data: Any, expected_target: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise SyncError("map root must be an object")
    if set(data) != {"schema_version", "source_host", "target_host", "assets"}:
        raise SyncError("map root fields do not match schema")
    if data["schema_version"] != SCHEMA_VERSION:
        raise SyncError("unsupported map schema_version")
    target_host = data["target_host"]
    source_host = data["source_host"]
    if target_host != expected_target or source_host not in AGENTS:
        raise SyncError("map host surface does not match its location")
    if source_host == target_host:
        raise SyncError("map source_host and target_host must differ")
    if not isinstance(data["assets"], list):
        raise SyncError("map assets must be an array")
    assets: list[dict[str, Any]] = []
    ids: set[str] = set()
    source_keys: set[tuple[str, str]] = set()
    target_keys: set[tuple[str, str]] = set()
    for raw in data["assets"]:
        if not isinstance(raw, dict):
            raise SyncError("map asset must be an object")
        required = {
            "asset_id",
            "asset_type",
            "adapter",
            "source_members",
            "target_members",
            "status",
        }
        if set(raw) - (required | {"reason"}) or not required.issubset(raw):
            raise SyncError("map asset has unknown or missing fields")
        asset_id = raw["asset_id"]
        if not isinstance(asset_id, str) or not ID_RE.fullmatch(asset_id):
            raise SyncError("invalid asset_id")
        if asset_id in ids:
            raise SyncError(f"duplicate asset_id: {asset_id}")
        ids.add(asset_id)
        asset_type = raw["asset_type"]
        status = raw["status"]
        if asset_type not in ASSET_TYPES or status not in STATUSES:
            raise SyncError(f"invalid asset type/status: {asset_id}")
        adapter = raw["adapter"]
        if (
            not isinstance(adapter, dict)
            or set(adapter) != {"id", "version"}
            or (adapter["id"], adapter["version"]) not in ADAPTERS
        ):
            raise SyncError(f"adapter is not allowlisted: {asset_id}")
        if not isinstance(raw["source_members"], list) or not isinstance(
            raw["target_members"], list
        ):
            raise SyncError(f"asset members must be arrays: {asset_id}")
        sources = [
            _validate_member(member, source_host, target=False)
            for member in raw["source_members"]
        ]
        targets = [
            _validate_member(member, target_host, target=True)
            for member in raw["target_members"]
        ]
        for key in map(_member_key, sources):
            if key in source_keys:
                raise SyncError(f"duplicate source member: {key}")
            source_keys.add(key)
        for key in map(_member_key, targets):
            if key in target_keys:
                raise SyncError(f"duplicate target member: {key}")
            target_keys.add(key)
        if adapter["id"] == "whole-file":
            if any("selector" in member for member in [*sources, *targets]):
                raise SyncError(f"whole-file member has selector: {asset_id}")
            if any(
                not _portable_text_path(member["path"], source_host)
                for member in sources
            ) or any(
                not _portable_text_path(member["path"], target_host)
                for member in targets
            ):
                raise SyncError(
                    f"whole-file is limited to portable memory Markdown: {asset_id}"
                )
        if adapter["id"] == "json-pointer":
            if any("selector" not in member for member in [*sources, *targets]):
                raise SyncError(f"json-pointer member lacks selector: {asset_id}")
            if any(
                not _shared_json_member(member, source_host)
                for member in sources
            ) or any(
                not _shared_json_member(member, target_host)
                for member in targets
            ):
                raise SyncError(
                    f"json-pointer selector is not allowlisted: {asset_id}"
                )
            for members in (sources, targets):
                for index, left in enumerate(members):
                    for right in members[index + 1 :]:
                        if (
                            left["path"] == right["path"]
                            and _selectors_overlap(
                                left["selector"], right["selector"]
                            )
                        ):
                            raise SyncError(
                                f"overlapping JSON selectors: {asset_id}"
                            )
        if status == "generated" and (
            not sources
            or not targets
            or adapter["id"] == "none"
            or any("last_generated_sha256" not in member for member in targets)
        ):
            raise SyncError(f"generated asset must have both sides: {asset_id}")
        reason = raw.get("reason")
        if reason is not None and (
            not isinstance(reason, str) or not REASON_RE.fullmatch(reason)
        ):
            raise SyncError(f"invalid reason: {asset_id}")
        asset = {
            "asset_id": asset_id,
            "asset_type": asset_type,
            "adapter": {
                "id": adapter["id"],
                "version": adapter["version"],
            },
            "source_members": sources,
            "target_members": targets,
            "status": status,
        }
        if reason is not None:
            asset["reason"] = reason
        assets.append(asset)
    return {
        "schema_version": SCHEMA_VERSION,
        "source_host": source_host,
        "target_host": target_host,
        "assets": sorted(assets, key=lambda item: item["asset_id"]),
    }


def _file_state(path: Path) -> tuple[str, str | None]:
    if not _lexists(path):
        return "missing", None
    if _is_link_like(path):
        return "link", None
    if not path.is_file():
        return "non-file", None
    return "file", _sha_file(path)


def _load_map(root: Path, host: str) -> LoadedMap:
    path = _map_path(root, host)
    state, digest = _file_state(path)
    if state == "missing":
        return LoadedMap(path, state)
    if state != "file":
        return LoadedMap(path, "invalid", error=f"map path is {state}")
    try:
        data = _validate_map(
            _load_json_bytes(path.read_bytes(), f"{host} map"),
            host,
        )
    except SyncError as exc:
        return LoadedMap(path, "invalid", error=str(exc), raw_sha256=digest)
    return LoadedMap(path, "valid", data=data, raw_sha256=digest)


def _inventory_host(root: Path, host: str) -> dict[str, Path]:
    spec = SPECS[host]
    paths = [root / spec.entry, root / spec.config_dir]
    result: dict[str, Path] = {}
    keys: dict[str, str] = {}
    for path in paths:
        _assert_project_local(path, root, f"{host} surface")
        _assert_no_links(path, f"{host} surface")
        candidates: list[Path] = []
        if path.is_file():
            candidates.append(path)
        elif path.is_dir():
            candidates.extend(
                item
                for item in path.rglob("*")
                if item.is_file()
                and "__pycache__" not in item.parts
                and item.suffix != ".pyc"
            )
        for item in sorted(candidates):
            rel = _rel(item, root)
            if rel.endswith("/" + MAP_NAME):
                continue
            key = _windows_path_key(rel)
            if key in keys:
                raise SyncError(
                    "Windows-equivalent path collision: "
                    f"{keys[key]} and {rel}"
                )
            keys[key] = rel
            result[rel] = item
    return result


def _template_inventory(template_root: Path, host: str) -> dict[str, str]:
    spec = SPECS[host]
    host_root = template_root / "templates" / host
    _assert_no_links(host_root, f"{host} template")
    result: dict[str, str] = {}
    entry = host_root / spec.entry
    if entry.is_file():
        result[spec.entry] = _sha_file(entry)
    config = host_root
    if config.is_dir():
        for path in sorted(item for item in config.rglob("*") if item.is_file()):
            rel = _posix(path.relative_to(config))
            result[f"{spec.config_dir}/{rel}"] = _sha_file(path)
    version = template_root / "VERSION"
    if version.is_file():
        result[f"{spec.config_dir}/.bridgeforge_version"] = _sha_file(version)
    return result


def _asset_id(kind: str, rel: str) -> str:
    safe = re.sub(r"[^a-z0-9._:-]+", "-", rel.casefold()).strip("-")
    digest = hashlib.sha256(rel.encode("utf-8")).hexdigest()[:12]
    return f"{kind}:{safe[:140]}:{digest}"


def _portable_target_path(path: str, source: str, target: str) -> str | None:
    prefix = SPECS[source].config_dir + "/memory/"
    if not path.startswith(prefix) or not path.endswith(".md"):
        return None
    suffix = path[len(prefix) :]
    return f"{SPECS[target].config_dir}/memory/{suffix}"


def _read_member(root: Path, member: dict[str, Any]) -> tuple[Any, str]:
    path = root / member["path"]
    if not path.is_file() or _is_link_like(path):
        raise KeyError(member["path"])
    if "selector" not in member:
        data = path.read_bytes()
        return data, _sha_bytes(data)
    document = _load_json_bytes(path.read_bytes(), member["path"])
    value = _pointer_get(document, member["selector"])
    return value, _hash_json(value)


def _generated_projection_state(
    root: Path,
    asset: dict[str, Any],
) -> str:
    for member in asset["target_members"]:
        try:
            _, digest = _read_member(root, member)
        except (KeyError, SyncError):
            return "forked"
        if digest != member["last_generated_sha256"]:
            return "forked"
    return "clean"


def _new_asset(
    asset_id: str,
    asset_type: str,
    adapter_id: str,
    sources: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    status: str,
    reason: str | None = None,
) -> dict[str, Any]:
    asset = {
        "asset_id": asset_id,
        "asset_type": asset_type,
        "adapter": {"id": adapter_id, "version": 1},
        "source_members": sorted(sources, key=_member_key),
        "target_members": sorted(targets, key=_member_key),
        "status": status,
    }
    if reason:
        asset["reason"] = reason
    return asset


def _source_member(root: Path, path: str, selector: str | None = None) -> dict[str, Any]:
    member: dict[str, Any] = {"path": path}
    if selector is not None:
        member["selector"] = selector
    _, digest = _read_member(root, member)
    member["sha256"] = digest
    return member


def _target_baselines(asset: dict[str, Any]) -> dict[tuple[str, str], str]:
    return {
        _member_key(member): member["last_generated_sha256"]
        for member in asset["target_members"]
    }


def _target_is_owned_clean(
    root: Path,
    desired_targets: list[dict[str, Any]],
    previous: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    baselines = _target_baselines(previous) if previous else {}
    previous_keys = set(baselines)
    desired_keys = set(map(_member_key, desired_targets))
    if previous and previous_keys != desired_keys:
        return False, "stale-map-topology"
    for member in desired_targets:
        key = _member_key(member)
        path = root / member["path"]
        try:
            _, digest = _read_member(root, member)
        except KeyError:
            if previous and key in baselines:
                return False, "interrupted-or-modified"
            if "selector" in member and (
                not _lexists(path) or path.is_file()
            ):
                continue
            if _lexists(path):
                return False, "unowned-existing-target"
            continue
        except SyncError:
            return False, "unowned-existing-target"
        if not previous or key not in baselines:
            return False, "unowned-existing-target"
        if digest != baselines[key]:
            return False, "interrupted-or-modified"
    return True, None


def _whole_file_outputs(
    root: Path,
    sources: list[dict[str, Any]],
    targets: list[dict[str, Any]],
) -> dict[tuple[str, str], Any]:
    values = [_read_member(root, member)[0] for member in sources]
    if not values or any(value != values[0] for value in values[1:]):
        raise SyncError("whole-file many-to-one sources must be byte-identical")
    return {_member_key(member): values[0] for member in targets}


def _json_pointer_outputs(
    root: Path,
    sources: list[dict[str, Any]],
    targets: list[dict[str, Any]],
) -> dict[tuple[str, str], Any]:
    values = [_read_member(root, member)[0] for member in sources]
    if not values:
        raise SyncError("json-pointer adapter needs a source")
    if len(values) == 1:
        values *= len(targets)
    if len(values) != len(targets):
        raise SyncError("json-pointer group must be 1:N or N:N")
    return {
        _member_key(member): value
        for member, value in zip(targets, values)
    }


def _prepare_target_bytes(
    root: Path,
    groups: list[
        tuple[dict[str, Any], dict[tuple[str, str], Any], dict[str, Any] | None]
    ],
) -> tuple[dict[str, bytes], dict[str, dict[tuple[str, str], str]]]:
    whole: dict[str, bytes] = {}
    json_edits: dict[str, list[tuple[str, Any]]] = {}
    for asset, outputs, _ in groups:
        for member in asset["target_members"]:
            key = _member_key(member)
            value = outputs[key]
            if "selector" in member:
                if member["path"] in whole:
                    raise SyncError("whole-file/selector target collision")
                json_edits.setdefault(member["path"], []).append(
                    (member["selector"], value)
                )
            else:
                if member["path"] in whole or member["path"] in json_edits:
                    raise SyncError("target member collision")
                if not isinstance(value, bytes):
                    raise SyncError("whole-file adapter produced non-bytes")
                whole[member["path"]] = value
    writes = dict(whole)
    target_hashes: dict[str, dict[tuple[str, str], str]] = {}
    for path, edits in json_edits.items():
        for index, (left, _) in enumerate(edits):
            for right, _ in edits[index + 1 :]:
                if _selectors_overlap(left, right):
                    raise SyncError(f"overlapping target selectors: {path}")
        live = root / path
        if live.is_file():
            document = _load_json_bytes(live.read_bytes(), path)
        elif not _lexists(live):
            document = {}
        else:
            raise SyncError(f"target JSON path is not a file: {path}")
        for selector, value in edits:
            _pointer_set(document, selector, value)
        writes[path] = (
            json.dumps(
                document,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    for asset, outputs, _ in groups:
        hashes: dict[tuple[str, str], str] = {}
        for member in asset["target_members"]:
            key = _member_key(member)
            hashes[key] = (
                _hash_json(outputs[key])
                if "selector" in member
                else _sha_bytes(outputs[key])
            )
        target_hashes[asset["asset_id"]] = hashes
    return writes, target_hashes


def _map_state_tuple(loaded: LoadedMap) -> tuple[str, str | None]:
    return loaded.state, loaded.raw_sha256


def build_plan(
    current_host: str,
    project_root: Path,
    template_root: Path,
) -> SyncPlan:
    source_host = "codex" if current_host == "claude" else "claude"
    for host in AGENTS:
        spec = SPECS[host]
        _assert_project_local(project_root / spec.config_dir, project_root, "host")
        _assert_no_links(project_root / spec.config_dir, f"{host} host")
    source_map = _load_map(project_root, source_host)
    target_map = _load_map(project_root, current_host)
    source_files = _inventory_host(project_root, source_host)
    source_snapshot = {
        path: _sha_file(file_path) for path, file_path in source_files.items()
    }
    plan = SyncPlan(
        current_host=current_host,
        source_host=source_host,
        project_root=project_root,
        template_root=template_root,
        source_map=source_map,
        target_map=target_map,
        source_snapshot=source_snapshot,
        source_map_state=_map_state_tuple(source_map),
        target_map_state=_map_state_tuple(target_map),
    )
    if source_map.state == "invalid":
        plan.messages.append(f"map-error:source:{source_map.error}")
    if target_map.state == "invalid":
        plan.messages.append(f"map-error:target:{target_map.error}")
    target_map_trusted = target_map.state == "valid"

    suppressed: set[tuple[str, str]] = set()
    if source_map.data:
        for asset in source_map.data["assets"]:
            if asset["status"] != "generated":
                continue
            state = _generated_projection_state(project_root, asset)
            for member in asset["target_members"]:
                suppressed.add(_member_key(member))
            if state == "forked":
                fork_sources: list[dict[str, Any]] = []
                for member in asset["target_members"]:
                    try:
                        fork_sources.append(
                            _source_member(
                                project_root,
                                member["path"],
                                member.get("selector"),
                            )
                        )
                    except (KeyError, SyncError):
                        continue
                plan.assets.append(
                    _new_asset(
                        asset["asset_id"],
                        asset["asset_type"],
                        asset["adapter"]["id"],
                        fork_sources,
                        [],
                        "forked_projection",
                        "interrupted-or-modified",
                    )
                )

    previous_assets = {
        asset["asset_id"]: asset
        for asset in (target_map.data or {}).get("assets", [])
        if asset["status"] == "generated"
    }
    template = _template_inventory(template_root, source_host)
    desired: list[dict[str, Any]] = []
    claimed: set[tuple[str, str]] = set()

    for asset_id, previous in sorted(previous_assets.items()):
        if previous["adapter"]["id"] not in {"whole-file", "json-pointer"}:
            continue
        try:
            sources = []
            for member in previous["source_members"]:
                current = _source_member(
                    project_root,
                    member["path"],
                    member.get("selector"),
                )
                sources.append(current)
            if not sources:
                continue
        except (KeyError, SyncError):
            continue
        if any(_member_key(member) in suppressed for member in sources):
            continue
        claimed.update(map(_member_key, sources))
        targets = [
            {
                key: value
                for key, value in member.items()
                if key in {"path", "selector"}
            }
            for member in previous["target_members"]
        ]
        desired.append(
            _new_asset(
                asset_id,
                previous["asset_type"],
                previous["adapter"]["id"],
                sources,
                targets,
                "generated",
            )
        )

    for path in sorted(source_files):
        if (path, "") in claimed or (path, "") in suppressed:
            continue
        digest = source_snapshot[path]
        if template.get(path) == digest:
            continue
        target_path = _portable_target_path(
            path,
            source_host,
            current_host,
        )
        if target_path:
            desired.append(
                _new_asset(
                    _asset_id("portable-memory", path.split("/memory/", 1)[1]),
                    "portable-text",
                    "whole-file",
                    [_source_member(project_root, path)],
                    [{"path": target_path}],
                    "generated",
                )
            )
            claimed.add((path, ""))
            continue
        settings = f"{SPECS[source_host].config_dir}/settings.json"
        if (
            path == settings
            and (path, "/permissions") not in suppressed
            and (path, "/permissions") not in claimed
        ):
            try:
                source = _source_member(project_root, path, "/permissions")
            except (KeyError, SyncError):
                source = None
            if source:
                target_settings = (
                    f"{SPECS[current_host].config_dir}/settings.json"
                )
                desired.append(
                    _new_asset(
                        "shared-settings:permissions",
                        "shared-json",
                        "json-pointer",
                        [source],
                        [
                            {
                                "path": target_settings,
                                "selector": "/permissions",
                            }
                        ],
                        "generated",
                    )
                )
                claimed.add((path, "/permissions"))
        plan.assets.append(
            _new_asset(
                _asset_id("untranslated", path),
                "host-specific",
                "none",
                [_source_member(project_root, path)],
                [],
                "untranslated",
                "no-equivalent-adapter",
            )
        )

    if source_map.state == "invalid":
        for asset in desired:
            plan.assets.append(
                _new_asset(
                    asset["asset_id"],
                    asset["asset_type"],
                    asset["adapter"]["id"],
                    asset["source_members"],
                    [],
                    "conflict",
                    "source-map-invalid",
                )
            )
        desired = []

    applicable: list[
        tuple[dict[str, Any], dict[tuple[str, str], Any], dict[str, Any] | None]
    ] = []
    desired_ids: set[str] = set()
    for asset in desired:
        desired_ids.add(asset["asset_id"])
        previous = previous_assets.get(asset["asset_id"])
        if not target_map_trusted and any(
            _lexists(project_root / member["path"])
            for member in asset["target_members"]
        ):
            plan.assets.append(
                _new_asset(
                    asset["asset_id"],
                    asset["asset_type"],
                    asset["adapter"]["id"],
                    asset["source_members"],
                    asset["target_members"],
                    "conflict",
                    "target-map-untrusted",
                )
            )
            continue
        clean, reason = _target_is_owned_clean(
            project_root,
            asset["target_members"],
            previous,
        )
        if not clean:
            plan.assets.append(
                _new_asset(
                    asset["asset_id"],
                    asset["asset_type"],
                    asset["adapter"]["id"],
                    asset["source_members"],
                    asset["target_members"],
                    "conflict",
                    reason,
                )
            )
            continue
        try:
            outputs = (
                _whole_file_outputs(
                    project_root,
                    asset["source_members"],
                    asset["target_members"],
                )
                if asset["adapter"]["id"] == "whole-file"
                else _json_pointer_outputs(
                    project_root,
                    asset["source_members"],
                    asset["target_members"],
                )
            )
        except (KeyError, SyncError) as exc:
            plan.assets.append(
                _new_asset(
                    asset["asset_id"],
                    asset["asset_type"],
                    asset["adapter"]["id"],
                    asset["source_members"],
                    asset["target_members"],
                    "conflict",
                    "adapter-input-invalid",
                )
            )
            plan.messages.append(f"adapter-error:{asset['asset_id']}:{exc}")
            continue
        applicable.append((asset, outputs, previous))

    for asset_id, previous in sorted(previous_assets.items()):
        if asset_id in desired_ids:
            continue
        clean = _generated_projection_state(project_root, previous) == "clean"
        if not clean or source_map.state == "invalid":
            plan.assets.append(
                _new_asset(
                    asset_id,
                    previous["asset_type"],
                    previous["adapter"]["id"],
                    previous["source_members"],
                    previous["target_members"],
                    "conflict",
                    "interrupted-or-modified",
                )
            )
            continue
        if previous["adapter"]["id"] == "whole-file":
            for member in previous["target_members"]:
                plan.deletes.add(member["path"])
        else:
            json_by_path: dict[str, Any] = {}
            failed = False
            for member in previous["target_members"]:
                path = member["path"]
                try:
                    document = json_by_path.setdefault(
                        path,
                        _load_json_bytes(
                            (project_root / path).read_bytes(),
                            path,
                        ),
                    )
                    _pointer_delete(document, member["selector"])
                except (OSError, KeyError, SyncError):
                    failed = True
                    break
            if failed:
                plan.assets.append(
                    _new_asset(
                        asset_id,
                        previous["asset_type"],
                        previous["adapter"]["id"],
                        previous["source_members"],
                        previous["target_members"],
                        "conflict",
                        "interrupted-or-modified",
                    )
                )
            else:
                for path, document in json_by_path.items():
                    plan.writes[path] = (
                        json.dumps(
                            document,
                            ensure_ascii=False,
                            indent=2,
                            sort_keys=True,
                        )
                        + "\n"
                    ).encode("utf-8")

    generated_writes, target_hashes = _prepare_target_bytes(
        project_root,
        applicable,
    )
    for path in set(plan.writes) & set(generated_writes):
        if plan.writes[path] != generated_writes[path]:
            raise SyncError(f"target write collision: {path}")
    plan.writes.update(generated_writes)
    for asset, _, _ in applicable:
        targets = []
        for member in asset["target_members"]:
            target = {"path": member["path"]}
            if target_map_trusted:
                target["last_generated_sha256"] = target_hashes[
                    asset["asset_id"]
                ][_member_key(member)]
            if "selector" in member:
                target["selector"] = member["selector"]
            targets.append(target)
        plan.assets.append(
            _new_asset(
                asset["asset_id"],
                asset["asset_type"],
                asset["adapter"]["id"],
                asset["source_members"],
                targets,
                "generated" if target_map_trusted else "created_unowned",
                None if target_map_trusted else "target-map-untrusted",
            )
        )

    plan.assets.sort(key=lambda item: item["asset_id"])
    document = {
        "schema_version": SCHEMA_VERSION,
        "source_host": source_host,
        "target_host": current_host,
        "assets": plan.assets,
    }
    _validate_map(document, current_host)
    if target_map.state != "invalid":
        plan.map_bytes = (
            json.dumps(
                document,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    touched = set(plan.writes) | set(plan.deletes)
    if plan.map_bytes is not None:
        touched.add(_rel(_map_path(project_root, current_host), project_root))
    for rel in touched:
        path = project_root / rel
        _assert_project_local(path, project_root, "target")
        state, digest = _file_state(path)
        if state not in {"missing", "file"}:
            raise SyncError(f"target path is unsafe ({state}): {rel}")
        plan.target_prestate[rel] = digest
    return plan


def _assert_target_commit_path(
    plan: SyncPlan,
    rel: str,
    label: str,
) -> Path:
    rel = _safe_rel(rel)
    if not _surface_ok(rel, plan.current_host):
        raise SyncError(f"{label} is outside target host surface: {rel}")
    path = plan.project_root / rel
    _assert_project_local(path, plan.project_root, label)
    _assert_project_local(path.parent, plan.project_root, f"{label} parent")
    if _is_link_like(path.parent):
        raise SyncError(f"{label} parent is a symlink or junction: {rel}")
    if _lexists(path):
        _assert_no_links(path, label)
    return path


def _recheck_plan(plan: SyncPlan) -> None:
    source = _inventory_host(plan.project_root, plan.source_host)
    current_source = {path: _sha_file(value) for path, value in source.items()}
    if current_source != plan.source_snapshot:
        raise SyncError("source input drift before apply")
    _inventory_host(plan.project_root, plan.current_host)
    map_rel = _rel(
        _map_path(plan.project_root, plan.current_host),
        plan.project_root,
    )
    _assert_target_commit_path(plan, map_rel, "target map")
    if _map_state_tuple(_load_map(plan.project_root, plan.source_host)) != (
        plan.source_map_state
    ):
        raise SyncError("source map drift before apply")
    if _map_state_tuple(_load_map(plan.project_root, plan.current_host)) != (
        plan.target_map_state
    ):
        raise SyncError("target map drift before apply")
    for rel, expected in plan.target_prestate.items():
        path = _assert_target_commit_path(plan, rel, "target commit path")
        state, digest = _file_state(path)
        if state not in {"missing", "file"} or digest != expected:
            raise SyncError(f"target input drift before apply: {rel}")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(
        prefix=".bridgeforge-switch-",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(raw)
    mode: int | None = None
    if path.is_file():
        mode = stat.S_IMODE(path.stat().st_mode)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if _lexists(temporary):
            temporary.unlink()


def _fault(label: str) -> None:
    labels = {
        item.strip()
        for item in os.environ.get("BRIDGEFORGE_SWITCH_FAIL_AT", "").split(",")
        if item.strip()
    }
    if label in labels:
        raise RuntimeError(f"injected switch failure at {label}")


def apply_plan(plan: SyncPlan) -> None:
    _recheck_plan(plan)
    touched = sorted(set(plan.writes) | set(plan.deletes))
    map_rel = _rel(
        _map_path(plan.project_root, plan.current_host),
        plan.project_root,
    )
    all_touched = [*touched]
    if plan.map_bytes is not None:
        all_touched.append(map_rel)
    with tempfile.TemporaryDirectory(prefix="bridgeforge-switch-") as raw_backup:
        backup_root = Path(raw_backup)
        absent: set[str] = set()
        created_dirs: list[Path] = []
        for rel in all_touched:
            source = plan.project_root / rel
            if source.is_file():
                destination = backup_root / rel
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            else:
                absent.add(rel)
        _recheck_plan(plan)
        try:
            write_count = 0
            for rel, data in sorted(plan.writes.items()):
                path = _assert_target_commit_path(
                    plan,
                    rel,
                    "target write",
                )
                state, digest = _file_state(path)
                if (
                    state not in {"missing", "file"}
                    or digest != plan.target_prestate[rel]
                ):
                    raise SyncError(
                        f"target write drift before replace: {rel}"
                    )
                parent = path.parent
                missing_parents: list[Path] = []
                while parent != plan.project_root and not parent.exists():
                    missing_parents.append(parent)
                    parent = parent.parent
                _atomic_write(path, data)
                created_dirs.extend(reversed(missing_parents))
                write_count += 1
                if write_count == 1:
                    _fault("after-first-write")
            for rel in sorted(plan.deletes):
                path = _assert_target_commit_path(
                    plan,
                    rel,
                    "target delete",
                )
                state, digest = _file_state(path)
                if state != "file" or digest != plan.target_prestate[rel]:
                    raise SyncError(
                        f"delete target drift before commit: {rel}"
                    )
                if path.is_file() and not _is_link_like(path):
                    path.unlink()
                else:
                    raise SyncError(f"delete target changed before commit: {rel}")
            _fault("after-deletes")
            if plan.map_bytes is not None:
                map_path = _assert_target_commit_path(
                    plan,
                    map_rel,
                    "target map replace",
                )
                state, digest = _file_state(map_path)
                if (
                    state not in {"missing", "file"}
                    or digest != plan.target_prestate[map_rel]
                ):
                    raise SyncError("target map drift before replace")
                _fault("before-map-replace")
                _atomic_write(map_path, plan.map_bytes)
                _fault("after-map-replace")
                loaded = _load_map(plan.project_root, plan.current_host)
                if loaded.state != "valid":
                    raise SyncError("written map failed validation")
                for asset in loaded.data["assets"]:
                    if asset["status"] != "generated":
                        continue
                    if (
                        _generated_projection_state(plan.project_root, asset)
                        != "clean"
                    ):
                        raise SyncError(
                            "map/live verification failed: "
                            + asset["asset_id"]
                        )
            for rel, data in sorted(plan.writes.items()):
                if _file_state(plan.project_root / rel) != (
                    "file",
                    _sha_bytes(data),
                ):
                    raise SyncError(
                        f"written target failed verification: {rel}"
                    )
            _fault("before-final-verify")
        except Exception as original:
            evidence: list[str] = [f"apply-error:{type(original).__name__}:{original}"]
            restore_allowed = True
            try:
                _fault("rollback-before-restore")
            except Exception as exc:
                restore_allowed = False
                evidence.append(
                    f"rollback-fault:{type(exc).__name__}:{exc}"
                )
            if restore_allowed:
                for rel in reversed(all_touched):
                    live = plan.project_root / rel
                    backup = backup_root / rel
                    try:
                        if backup.is_file():
                            _atomic_write(live, backup.read_bytes())
                        elif rel in absent and _lexists(live):
                            if live.is_file() and not _is_link_like(live):
                                live.unlink()
                            else:
                                raise RuntimeError(
                                    f"cannot remove unsafe path: {rel}"
                                )
                    except Exception as exc:
                        evidence.append(
                            "restore-error:"
                            f"{rel}:{type(exc).__name__}:{exc}"
                        )
                for directory in reversed(created_dirs):
                    try:
                        if directory.is_dir() and not any(directory.iterdir()):
                            directory.rmdir()
                    except Exception as exc:
                        evidence.append(
                            "cleanup-error:"
                            f"{_rel(directory, plan.project_root)}:"
                            f"{type(exc).__name__}:{exc}"
                        )
            verification_allowed = True
            try:
                _fault("rollback-before-verify")
            except Exception as exc:
                verification_allowed = False
                evidence.append(
                    f"rollback-verify-fault:{type(exc).__name__}:{exc}"
                )
            if verification_allowed:
                for rel, expected in plan.target_prestate.items():
                    state, digest = _file_state(plan.project_root / rel)
                    if state not in {"missing", "file"} or digest != expected:
                        evidence.append(
                            "rollback-mismatch:"
                            f"{rel}:expected={expected}:"
                            f"actual-state={state}:actual={digest}"
                        )
                for directory in created_dirs:
                    if _lexists(directory):
                        evidence.append(
                            "rollback-directory-remains:"
                            + _rel(directory, plan.project_root)
                        )
            if len(evidence) > 1:
                raise RollbackIncompleteError(
                    "direct sync apply failed and rollback is incomplete",
                    evidence,
                ) from original
            raise ApplyRolledBackError(str(original)) from original


def _candidate_roots(script_path: Path, explicit: str | None) -> list[Path]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    home = Path.home()
    candidates.extend(
        [
            script_path.parent.parent,
            home / ".bridgeforge",
            home / ".codex" / "skills" / "bridgeforge",
            home / ".claude" / "skills" / "bridgeforge",
        ]
    )
    result: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def find_template_root(script_path: Path, explicit: str | None) -> Path:
    for root in _candidate_roots(script_path, explicit):
        if (
            (root / "templates" / "claude").is_dir()
            and (root / "templates" / "codex").is_dir()
        ):
            return root
    raise SyncError(
        "cannot find BridgeForge templates; pass --template-root"
    )


def looks_like_bridgeforge_source(root: Path) -> bool:
    return (
        (root / "templates" / "claude").is_dir()
        and (root / "templates" / "codex").is_dir()
        and (root / "skills" / "bridgeforge" / "SKILL.md").is_file()
    )


def template_copy_items(
    template_root: Path,
    project_root: Path,
    agent: str,
) -> list[Any]:
    """Compatibility helper: direct-sync never installs a target template."""
    del template_root, project_root, agent
    return []


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Direct-sync the other BridgeForge skeleton into this host."
    )
    parser.add_argument("agent", choices=AGENTS, help="current/target host")
    parser.add_argument(
        "--current-host",
        required=True,
        choices=AGENTS,
        help="host attestation supplied by the current BridgeForge entry",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="plan and validate without changing project files",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="project root (default: current directory)",
    )
    parser.add_argument(
        "--template-root",
        help="BridgeForge repository root containing templates/",
    )
    return parser.parse_args(argv)


def _print_summary(plan: SyncPlan, dry_run: bool) -> None:
    counts = {
        status: sum(asset["status"] == status for asset in plan.assets)
        for status in sorted(STATUSES)
    }
    status = "completed_with_gaps" if plan.degraded else "completed"
    readiness = "degraded" if plan.degraded else "ready"
    prefix = "Dry-run" if dry_run else "Switch"
    print(f"{prefix} {status}: {plan.current_host}")
    print(f"readiness={readiness}")
    print(
        "assets="
        + ",".join(f"{key}:{value}" for key, value in counts.items() if value)
    )
    for message in plan.messages:
        print(f"NOTICE: {message}")
    if plan.target_map.state == "invalid":
        print(
            "Target map is invalid and was preserved; only entirely absent "
            "target paths were eligible for unowned creation."
        )
    else:
        print(
            "Map: "
            + _rel(
                _map_path(plan.project_root, plan.current_host),
                plan.project_root,
            )
        )
    legacy = plan.project_root / ".bridgeforge"
    if _lexists(legacy):
        print(
            "NOTICE: legacy project-root .bridgeforge/ was not read, "
            "written, or removed; delete it manually after review."
        )


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.current_host != args.agent:
        print(
            "ERROR: --current-host must match the switch target; "
            "no project files were changed.",
            file=sys.stderr,
        )
        return 2
    project_root = Path(args.project_root).resolve()
    try:
        if looks_like_bridgeforge_source(project_root):
            raise SyncError(
                "refusing to switch the BridgeForge source repository itself"
            )
        template_root = find_template_root(
            Path(__file__).resolve(),
            args.template_root,
        )
        if project_root == template_root:
            raise SyncError(
                "refusing to switch the BridgeForge source repository itself"
            )
        plan = build_plan(args.current_host, project_root, template_root)
        if not args.dry_run:
            apply_plan(plan)
    except SyncError as exc:
        print(f"ERROR: direct sync blocked: {exc}", file=sys.stderr)
        print("No project files were changed.", file=sys.stderr)
        return 2
    except RollbackIncompleteError as exc:
        print(
            f"ERROR: direct sync failed; rollback incomplete: {exc}",
            file=sys.stderr,
        )
        for item in exc.evidence:
            print(f"RECOVERY: {item}", file=sys.stderr)
        print(
            "Project state requires manual review before retrying.",
            file=sys.stderr,
        )
        return 1
    except ApplyRolledBackError as exc:
        print(
            f"ERROR: direct sync failed and was fully rolled back: {exc}",
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        print(
            f"ERROR: direct sync failed; rollback status was not confirmed: {exc}",
            file=sys.stderr,
        )
        return 1
    _print_summary(plan, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
