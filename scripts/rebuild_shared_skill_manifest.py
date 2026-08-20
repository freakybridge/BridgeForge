#!/usr/bin/env python3
"""Rebuild bridgeforge-codex shared-skill hashes and managed lineage.

The shared updater verifies raw file bytes. bridgeforge-codex ships from GitHub,
whose text blobs use LF because of .gitattributes, so this script must not hash
the local Windows checkout verbatim when it happens to use CRLF.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_MANIFEST = REPOSITORY_ROOT / "bridgeforge-codex-manifest.json"
DEFAULT_MANIFEST = ACTIVE_MANIFEST
MANAGED_CONTRACT = REPOSITORY_ROOT / "templates" / "managed-skeleton.json"
DOGFOOD_MANAGED_CONTRACT = REPOSITORY_ROOT / ".codex" / "managed-skeleton.json"
MINIMUM_MANAGED_VERSION = (0, 86, 0)
PRE_FLATTEN_VERSION = "1.0.0"
PRE_FLATTEN_CONTRACT_SHA256 = (
    "sha256:ec461d15122b625493ae079e19a01557c1a0606126463ccf40b12021e36cb9d7"
)
PRE_FLATTEN_ASSET_SHA256 = {
    "codex.hook.mirror-drift-check": (
        "sha256:10feaf89afdb7350470fd9821ffe2247a8fce27797871c3a146e52dab9494f0f"
    ),
    "codex.hook.skill-metadata-check": (
        "sha256:86a3581eea765ec04177686be137c1c1156b5e5cc4c1569cfa4107373ff84a45"
    ),
    "codex.rule.portability": (
        "sha256:70c741475267f630e6a6f6628a5bca71ee471b81cd52ba74e9ec5e7564beb9c9"
    ),
    "codex.script.project-memory-writer": (
        "sha256:8f4df93ce943e635bdec3004e0a102c5b1ce828bb89975ce1d320e7c4c8f1575"
    ),
    "codex.script.version-release": (
        "sha256:88f99d960515239dd04fc08fd822c43e17b7a5b2c0982c11deb6793416c5c300"
    ),
}
PROJECT_ZONE_TRANSITION_VERSION = "1.1.0"
PROJECT_ZONE_TRANSITION_ASSET_SHA256 = {
    "codex.hook.instruction-source-check": (
        "sha256:9ba1d893f564442d706cb78aa7afec33948251cfc51801a238affcc21bcdbd13"
    ),
}
PROJECT_TITLE_RE = re.compile(
    r"(?m)^# ([A-Za-z0-9._-]+|\{\{PROJECT_NAME\}\}) 项目开发规范[ \t]*$".encode(
        "utf-8"
    )
)
PROJECT_TITLE_NORMALIZED = "# {{PROJECT_NAME}} 项目开发规范".encode("utf-8")


def git_blob_bytes(path: Path) -> bytes:
    """Return bytes matching the LF text blob that bridgeforge-codex publishes.

    Git treats NUL-containing files as binary under ``text=auto``. Those files
    are intentionally left byte-for-byte unchanged; every current manifest
    source is text.
    """
    payload = path.read_bytes()
    if b"\0" in payload:
        return payload
    return payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def manifest_sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(git_blob_bytes(path)).hexdigest()}"


def _canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _dispatcher_stage(handler: Any) -> str | None:
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


def _codex_hooks_merge_validation(payload: bytes) -> dict[str, Any]:
    try:
        module = _version_release_module(REPOSITORY_ROOT)
        document = module._load_hooks_document(payload, "templates/hooks.json")
        groups = module._expected_hooks_groups(
            document,
            managed_prefix="bridgeforge-codex.project-hook.v1:",
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RuntimeError) as exc:
        raise ValueError(f"Codex hooks source is invalid JSON: {exc}") from exc
    required = [
        {
            "id": str(item["id"]),
            "event": str(item["event"]),
            "matcher": str(item["matcher"]),
            "stage": str(_dispatcher_stage(item["handler"])),
            "sha256": str(item["handler_sha256"]),
        }
        for item in groups
    ]
    if not required:
        raise ValueError("Codex hooks source has no managed dispatcher handlers")
    required.sort(key=lambda item: (item["event"], item["matcher"], item["stage"]))
    if len({(item["event"], item["matcher"], item["stage"]) for item in required}) != len(required):
        raise ValueError("Codex hooks source contains duplicate managed dispatcher stages")
    return {
        "format": "codex-hooks-zones-v2",
        "required_handlers": required,
        "managed_top_level": {"description": document.get("description")},
    }


def _source_path(repository_root: Path, source: str) -> Path:
    candidate = (repository_root / source).resolve()
    try:
        candidate.relative_to(repository_root)
    except ValueError as exc:
        raise ValueError(f"Manifest source escapes repository root: {source}") from exc
    if not candidate.is_file():
        raise FileNotFoundError(f"Manifest source is missing: {source}")
    return candidate


def _git_blob_at(repository_root: Path, revision: str, source: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{revision}:{source}"],
        cwd=repository_root,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout
    if source.startswith("templates/") and not source.startswith("templates/codex/"):
        legacy_source = "templates/codex/" + source.removeprefix("templates/")
        legacy = subprocess.run(
            ["git", "show", f"{revision}:{legacy_source}"],
            cwd=repository_root,
            capture_output=True,
            check=False,
        )
        if legacy.returncode == 0:
            return legacy.stdout
    return None


def _stable_semver(value: str) -> tuple[int, int, int] | None:
    parts = value.strip().split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def _baseline_revisions(root: Path) -> dict[str, str]:
    """Return every published 0.86.0+ release reachable from HEAD.

    The working VERSION is excluded: its files are represented by current_sha256.
    On the next release bump it becomes a historical baseline automatically.
    """
    current_version = (root / "VERSION").read_text(encoding="utf-8-sig").strip()
    result = subprocess.run(
        ["git", "log", "--format=%H", "HEAD", "--", "VERSION"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(
                "Cannot enumerate bridgeforge-codex release history: "
            + result.stderr.strip()
        )
    baselines: dict[str, str] = {}
    for revision in result.stdout.splitlines():
        payload = _git_blob_at(root, revision.strip(), "VERSION")
        if payload is None:
            continue
        version = payload.decode("utf-8-sig").strip()
        parsed = _stable_semver(version)
        if (
            parsed is None
            or parsed < MINIMUM_MANAGED_VERSION
            or version == current_version
        ):
            continue
        baselines.setdefault(version, revision.strip())
    return dict(
        sorted(
            baselines.items(),
            key=lambda item: _stable_semver(item[0]) or (0, 0, 0),
        )
    )


def _codex_hooks_top_level_history(
    root: Path,
    source: str,
    baselines: dict[str, str],
    current: dict[str, Any],
) -> dict[str, list[Any]]:
    history: dict[str, list[Any]] = {key: [] for key in current}
    for revision in baselines.values():
        payload = _git_blob_at(root, revision, source)
        if payload is None:
            continue
        try:
            document = json.loads(payload.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Historical Codex hooks source is invalid JSON: {revision}: {exc}"
            ) from exc
        if not isinstance(document, dict):
            raise ValueError(
                f"Historical Codex hooks source is not an object: {revision}"
            )
        for key, current_value in current.items():
            if key in document and document[key] != current_value:
                candidate = document[key]
                if candidate not in history[key]:
                    history[key].append(candidate)
    return {
        key: sorted(values, key=lambda item: json.dumps(item, ensure_ascii=False))
        for key, values in history.items()
        if values
    }


def _codex_hooks_handler_history(
    root: Path,
    source: str,
    baselines: dict[str, str],
    current_required: list[dict[str, str]],
) -> dict[str, dict[str, list[str]]]:
    """Bind each legacy dispatcher to the release that published it."""
    module = _version_release_module(root)
    current_by_key = {
        (item["event"], item["matcher"], item["stage"]): item["id"]
        for item in current_required
    }
    history: dict[str, dict[str, list[str]]] = {
        item["id"]: {} for item in current_required
    }
    for version, revision in baselines.items():
        payload = _git_blob_at(root, revision, source)
        if payload is None:
            continue
        try:
            document = module._load_hooks_document(
                payload,
                f"{source}@{version}",
            )
        except Exception as exc:
            raise ValueError(
                f"Historical Codex hooks source is invalid: {version}: {exc}"
            ) from exc
        hooks = document.get("hooks")
        if not isinstance(hooks, dict):
            raise ValueError(
                f"Historical Codex hooks source has no hooks object: {version}"
            )
        seen: set[tuple[str, str, str]] = set()
        for event, groups in hooks.items():
            if not isinstance(event, str) or not isinstance(groups, list):
                raise ValueError(
                    f"Historical Codex hooks groups are invalid: {version}"
                )
            for group in groups:
                if not isinstance(group, dict):
                    raise ValueError(
                        f"Historical Codex hooks group is invalid: {version}"
                    )
                matcher = str(group.get("matcher", ""))
                handlers = group.get("hooks")
                if not isinstance(handlers, list):
                    raise ValueError(
                        f"Historical Codex hooks handlers are invalid: {version}"
                    )
                for handler in handlers:
                    stage = _dispatcher_stage(handler)
                    if stage is None:
                        continue
                    key = (event, matcher, stage)
                    managed_id = current_by_key.get(key)
                    if managed_id is None:
                        continue
                    if key in seen:
                        raise ValueError(
                            "Historical Codex hooks source contains duplicate "
                            f"dispatcher stages: {version}:{key}"
                        )
                    seen.add(key)
                    digest = module._handler_without_managed_id_hash(handler)
                    values = history[managed_id].setdefault(version, [])
                    if digest not in values:
                        values.append(digest)
                        values.sort()
    return {
        managed_id: dict(
            sorted(
                versions.items(),
                key=lambda item: _stable_semver(item[0]) or (0, 0, 0),
            )
        )
        for managed_id, versions in history.items()
        if versions
    }


def _merge_history(
    existing: Any,
    root: Path,
    source: str,
    baselines: dict[str, str],
) -> dict[str, list[str]]:
    history: dict[str, list[str]] = {}
    if isinstance(existing, dict):
        for version, values in existing.items():
            candidates = values if isinstance(values, list) else [values]
            valid = sorted(
                {
                    value
                    for value in candidates
                    if isinstance(value, str)
                    and value.startswith("sha256:")
                    and len(value) == 71
                }
            )
            if valid:
                history[str(version)] = valid
    for version, revision in baselines.items():
        payload = _git_blob_at(root, revision, source)
        if payload is None:
            continue
        digest = f"sha256:{hashlib.sha256(git_blob_bytes_from_bytes(payload)).hexdigest()}"
        history.setdefault(version, [])
        if digest not in history[version]:
            history[version].append(digest)
            history[version].sort()
    return dict(
        sorted(history.items(), key=lambda item: _stable_semver(item[0]) or (0, 0, 0))
    )


_VERSION_RELEASE_MODULE: Any | None = None


def _version_release_module(root: Path) -> Any:
    global _VERSION_RELEASE_MODULE
    if _VERSION_RELEASE_MODULE is not None:
        return _VERSION_RELEASE_MODULE
    module_path = root / "templates" / "scripts" / "version_release.py"
    spec = importlib.util.spec_from_file_location(
        "bridgeforge_contract_version_release",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load managed projection source: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    previous_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous_dont_write_bytecode
    _VERSION_RELEASE_MODULE = module
    return module


def _managed_markdown_projection_sha256(
    root: Path,
    asset: dict[str, Any],
    payload: bytes,
) -> str:
    module = _version_release_module(root)
    managed, _project = module._managed_blocks_parts(
        payload,
        asset,
        str(asset.get("target", "<managed-markdown>")),
    )
    return module._sha256_bytes(managed or b"")


def _historical_contract_asset(
    root: Path,
    revision: str,
    asset_id: str,
    *,
    strict: bool = False,
) -> dict[str, Any] | None:
    payload = _git_blob_at(root, revision, "templates/managed-skeleton.json")
    if payload is None:
        if strict:
            raise ValueError(
                f"Historical managed contract is missing: {asset_id}@{revision}"
            )
        return None
    try:
        contract = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        if strict:
            raise ValueError(
                f"Historical managed contract is invalid: {asset_id}@{revision}"
            )
        return None
    if not isinstance(contract, dict):
        if strict:
            raise ValueError(
                f"Historical managed contract is invalid: {asset_id}@{revision}"
            )
        return None
    if contract.get("schema_version") == 1:
        return None
    if strict and contract.get("schema_version") != 2:
        raise ValueError(
            f"Historical managed contract schema is unsupported: {asset_id}@{revision}"
        )
    assets = contract.get("assets")
    if not isinstance(assets, list):
        if strict:
            raise ValueError(
                f"Historical managed contract assets are invalid: {asset_id}@{revision}"
            )
        return None
    if strict:
        stable_ids: list[str] = []
        for item in assets:
            stable_id = item.get("id") if isinstance(item, dict) else None
            if not isinstance(stable_id, str) or not stable_id:
                raise ValueError(
                    f"Historical managed contract asset is invalid: {asset_id}@{revision}"
                )
            stable_ids.append(stable_id)
        if len(stable_ids) != len(set(stable_ids)):
            raise ValueError(
                f"Historical managed contract has duplicate asset ids: {asset_id}@{revision}"
            )
    matches = [
        dict(item)
        for item in assets
        if isinstance(item, dict) and item.get("id") == asset_id
    ]
    return matches[0] if matches else None


def _managed_markdown_projection_history(
    existing: Any,
    root: Path,
    current_asset: dict[str, Any],
    baselines: dict[str, str],
) -> dict[str, list[str]]:
    history = _merge_history(existing, root, "__no_projection_history__", {})
    asset_id = str(current_asset.get("id", ""))
    for version, revision in baselines.items():
        history.pop(version, None)
        historical_asset = _historical_contract_asset(root, revision, asset_id)
        if historical_asset is None or not isinstance(
            historical_asset.get("managed_blocks"),
            dict,
        ):
            continue
        source = historical_asset.get("source")
        if not isinstance(source, str):
            continue
        payload = _git_blob_at(root, revision, source)
        if payload is None:
            continue
        try:
            digest = _managed_markdown_projection_sha256(
                root,
                historical_asset,
                payload,
            )
        except (TypeError, ValueError):
            continue
        history[version] = [digest]
    return dict(
        sorted(history.items(), key=lambda item: _stable_semver(item[0]) or (0, 0, 0))
    )


def _agents_public_block(payload: bytes, begin: str, end: str) -> bytes | None:
    normalized = git_blob_bytes_from_bytes(payload)
    begin_bytes = begin.encode("utf-8")
    end_bytes = end.encode("utf-8")
    if normalized.count(begin_bytes) != 1 or normalized.count(end_bytes) != 1:
        return None
    start = normalized.index(begin_bytes)
    finish_start = normalized.index(end_bytes, start + len(begin_bytes))
    finish = normalized.find(b"\n", finish_start)
    return normalized[start:] if finish < 0 else normalized[start:finish + 1]


def _managed_region_block(payload: bytes, begin: str, end: str) -> bytes | None:
    normalized = git_blob_bytes_from_bytes(payload)
    begin_bytes = begin.encode("utf-8")
    end_bytes = end.encode("utf-8")
    if normalized.count(begin_bytes) != 1 or normalized.count(end_bytes) != 1:
        return None
    start = normalized.index(begin_bytes)
    finish = normalized.index(end_bytes, start + len(begin_bytes)) + len(end_bytes)
    return normalized[start:finish]


def _merge_agents_public_history(
    existing: Any,
    root: Path,
    source: str,
    baselines: dict[str, str],
    begin: str,
    end: str,
) -> dict[str, list[str]]:
    history = _merge_history(existing, root, "__no_whole_file_history__", {})
    for version, revision in baselines.items():
        payload = _git_blob_at(root, revision, source)
        if payload is None:
            continue
        public = _agents_public_block(payload, begin, end)
        if public is None:
            continue
        digest = f"sha256:{hashlib.sha256(public).hexdigest()}"
        history.setdefault(version, [])
        if digest not in history[version]:
            history[version].append(digest)
            history[version].sort()
    return dict(
        sorted(history.items(), key=lambda item: _stable_semver(item[0]) or (0, 0, 0))
    )


def _markdown_section(payload: bytes, heading: str) -> bytes | None:
    payload = git_blob_bytes_from_bytes(payload)
    lines = payload.splitlines(keepends=True)
    offsets: list[int] = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)
    heading_re = re.compile(br"^ {0,3}(#{1,6}) [^\r\n]+$")
    fence_re = re.compile(br"^ {0,3}(`{3,}|~{3,})[^\r\n]*$")
    visible: list[tuple[int, int, bytes]] = []
    fence_char: bytes | None = None
    fence_length = 0
    for index, line in enumerate(lines):
        stripped = line.rstrip(b"\r\n")
        if fence_char is not None:
            close = re.fullmatch(
                br" {0,3}" + re.escape(fence_char) + br"{" +
                str(fence_length).encode("ascii") + br",}[ \t]*",
                stripped,
            )
            if close:
                fence_char = None
                fence_length = 0
            continue
        fence = fence_re.fullmatch(stripped)
        if fence:
            marker = fence.group(1)
            fence_char = marker[:1]
            fence_length = len(marker)
            continue
        match = heading_re.fullmatch(stripped)
        if match:
            visible.append((offsets[index], len(match.group(1)), stripped.lstrip()))
    if fence_char is not None:
        raise ValueError("Managed Markdown history contains an unclosed fence")
    encoded = heading.encode("utf-8")
    matches = [index for index, item in enumerate(visible) if item[2] == encoded]
    if len(matches) > 1:
        raise ValueError(f"Managed Markdown history duplicates heading: {heading}")
    if not matches:
        return None
    position = matches[0]
    start, level, _raw = visible[position]
    finish = len(payload)
    for later_start, later_level, _later in visible[position + 1:]:
        if later_level <= level:
            finish = later_start
            break
    return payload[start:finish]


def _merge_layout_history(
    existing: Any,
    root: Path,
    source: str,
    baselines: dict[str, str],
    headings: list[str],
    hash_normalizer: str | None = None,
) -> dict[str, dict[str, list[str]]]:
    history: dict[str, dict[str, list[str]]] = {}
    if isinstance(existing, dict):
        for heading, versions in existing.items():
            if not isinstance(heading, str) or not isinstance(versions, dict):
                continue
            cleaned: dict[str, list[str]] = {}
            for version, values in versions.items():
                candidates = values if isinstance(values, list) else [values]
                valid = sorted({
                    value for value in candidates
                    if isinstance(value, str)
                    and value.startswith("sha256:")
                    and len(value) == 71
                })
                if valid:
                    cleaned[str(version)] = valid
            if cleaned:
                history[heading] = cleaned
    for heading in headings:
        by_version = history.setdefault(heading, {})
        for version, revision in baselines.items():
            payload = _git_blob_at(root, revision, source)
            if payload is None:
                continue
            block = _markdown_section(payload, heading)
            if block is None:
                continue
            normalized = git_blob_bytes_from_bytes(block).rstrip(b" \t\r\n")
            if hash_normalizer == "project-name-clone-command":
                normalized = re.sub(
                    br"(?m)^(git clone <repo_url> )"
                    br"([A-Za-z0-9._-]+|\{\{PROJECT_NAME\}\})"
                    br"( && cd )\2([ \t]*)$",
                    br"\1{{PROJECT_NAME}}\3{{PROJECT_NAME}}\4",
                    normalized,
                )
            digest = f"sha256:{hashlib.sha256(normalized).hexdigest()}"
            by_version.setdefault(version, [])
            if digest not in by_version[version]:
                by_version[version].append(digest)
                by_version[version].sort()
        history[heading] = dict(sorted(
            by_version.items(),
            key=lambda item: _stable_semver(item[0]) or (0, 0, 0),
        ))
    return {heading: history[heading] for heading in headings if history.get(heading)}


def _layout_entries(layout: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for group in layout.get("groups", []):
        children = group.get("sections")
        result.extend(children if isinstance(children, list) else [group])
    return result


def _layout_residual_bytes(payload: bytes, layout: dict[str, Any]) -> bytes:
    normalized = git_blob_bytes_from_bytes(payload)
    headings: list[str] = []
    for entry in _layout_entries(layout):
        headings.append(str(entry["heading"]))
        headings.extend(str(item) for item in entry.get("legacy_headings", []))
    for entry in layout.get("retired_sections", []):
        headings.extend(str(item) for item in entry.get("legacy_headings", []))
    spans: list[tuple[int, int]] = []
    for heading in dict.fromkeys(headings):
        block = _markdown_section(normalized, heading)
        if block is None:
            continue
        start = normalized.find(block)
        if start < 0:
            raise ValueError(f"Cannot locate managed Markdown block: {heading}")
        spans.append((start, start + len(block)))
    for group in layout["groups"]:
        if not isinstance(group.get("sections"), list):
            continue
        pattern = re.compile(
            br"(?m)^" + re.escape(str(group["heading"]).encode("utf-8")) + br"\n?"
        )
        matches = list(pattern.finditer(normalized))
        if len(matches) > 1:
            raise ValueError(
                f"Managed Markdown group heading is duplicated: {group['heading']}"
            )
        spans.extend((match.start(), match.end()) for match in matches)
    merged: list[tuple[int, int]] = []
    for start, finish in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], finish))
        else:
            merged.append((start, finish))
    parts: list[bytes] = []
    cursor = 0
    for start, finish in merged:
        parts.append(normalized[cursor:start])
        cursor = finish
    parts.append(normalized[cursor:])
    return b"".join(parts)


def _merge_layout_residual_history(
    existing: Any,
    root: Path,
    source: str,
    baselines: dict[str, str],
    layout: dict[str, Any],
) -> dict[str, list[str]]:
    history = _merge_history(existing, root, "__no_residual_history__", {})
    for version, revision in baselines.items():
        payload = _git_blob_at(root, revision, source)
        if payload is None:
            continue
        residual = PROJECT_TITLE_RE.sub(
            PROJECT_TITLE_NORMALIZED,
            _layout_residual_bytes(payload, layout),
        )
        digest = f"sha256:{hashlib.sha256(residual).hexdigest()}"
        history.setdefault(version, [])
        if digest not in history[version]:
            history[version].append(digest)
            history[version].sort()
    return dict(
        sorted(history.items(), key=lambda item: _stable_semver(item[0]) or (0, 0, 0))
    )


def rebuild_managed_contract(
    contract_path: Path = MANAGED_CONTRACT,
    *,
    write: bool = True,
) -> bool:
    """Refresh current and supported-baseline hashes without changing ownership."""
    contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
    if contract.get("schema_version") != 2 or not isinstance(contract.get("assets"), list):
        raise ValueError("Codex managed-skeleton.json must use schema v2 before rebuild")
    for asset in contract["assets"]:
        if not isinstance(asset, dict):
            raise ValueError("Codex managed contract asset is invalid")
        zones = asset.get("agents_zones")
        if zones is not None:
            project = zones.get("project") if isinstance(zones, dict) else None
            if (
                not isinstance(zones, dict)
                or zones.get("format") != "bridgeforge-agents-zones"
                or not isinstance(zones.get("public"), dict)
                or not isinstance(project, dict)
                or asset.get("managed_blocks") is not None
                or asset.get("section_layout") is not None
                or "legacy_section_migrations" in project
            ):
                raise ValueError(
                    "Codex AGENTS must use agents_zones as its only ownership rule"
                )
        managed = asset.get("managed_blocks") if isinstance(asset, dict) else None
        if managed is None:
            continue
        headings = managed.get("headings") if isinstance(managed, dict) else None
        additive_headings = (
            managed.get("additive_headings", []) if isinstance(managed, dict) else None
        )
        keyed_tables = managed.get("keyed_tables", []) if isinstance(managed, dict) else None
        if (
            not isinstance(managed, dict)
            or managed.get("format") != "markdown-headings"
            or not isinstance(headings, list)
            or not isinstance(additive_headings, list)
            or any(not isinstance(item, str) or not item for item in additive_headings)
            or len(set(additive_headings)) != len(additive_headings)
            or not isinstance(keyed_tables, list)
            or (not headings and not additive_headings and not keyed_tables)
            or set(headings).intersection(additive_headings)
        ):
            raise ValueError("Codex managed Markdown ownership is invalid")
        seen_table_headings: set[str] = set()
        for table in keyed_tables:
            if not isinstance(table, dict):
                raise ValueError("Codex managed keyed-table ownership is invalid")
            heading = table.get("heading")
            managed_keys = table.get("managed_keys")
            if (
                not isinstance(heading, str)
                or heading in seen_table_headings
                or heading in headings
                or heading in additive_headings
                or table.get("key_column") != 0
                or not isinstance(managed_keys, list)
                or not managed_keys
                or any(not isinstance(key, str) or not key.strip() for key in managed_keys)
                or len({key.casefold() for key in managed_keys}) != len(managed_keys)
            ):
                raise ValueError("Codex managed keyed-table ownership is invalid")
            seen_table_headings.add(heading)
        layout = asset.get("section_layout") if isinstance(asset, dict) else None
        if layout is not None and (
            not isinstance(layout, dict)
            or layout.get("format") != "markdown-section-layout"
            or not isinstance(layout.get("groups"), list)
        ):
            raise ValueError("Codex managed Markdown section layout is invalid")
        zones = asset.get("agents_zones") if isinstance(asset, dict) else None
        if zones is not None and (
            not isinstance(zones, dict)
            or zones.get("format") != "bridgeforge-agents-zones"
            or not isinstance(zones.get("public"), dict)
            or not isinstance(zones.get("project"), dict)
        ):
            raise ValueError("Codex AGENTS zone ownership is invalid")
    changed = False
    root = REPOSITORY_ROOT
    release_version = (root / "VERSION").read_text(encoding="utf-8-sig").strip()
    if _stable_semver(release_version) is None:
        raise ValueError("root VERSION must be a stable MAJOR.MINOR.PATCH release")
    if contract.get("release_version") != release_version:
        contract["release_version"] = release_version
        changed = True
    baselines = _baseline_revisions(root)
    contract_source = contract_path.relative_to(root).as_posix()
    historical_contract = _merge_history(
        contract.get("contract_historical_sha256"),
        root,
        contract_source,
        baselines,
    )
    transition_contract_hashes = historical_contract.setdefault(
        PRE_FLATTEN_VERSION,
        [],
    )
    if PRE_FLATTEN_CONTRACT_SHA256 not in transition_contract_hashes:
        transition_contract_hashes.append(PRE_FLATTEN_CONTRACT_SHA256)
        transition_contract_hashes.sort()
    if contract.get("contract_historical_sha256") != historical_contract:
        contract["contract_historical_sha256"] = historical_contract
        changed = True

    for asset in contract["assets"]:
        source = asset.get("source")
        if isinstance(source, str) and source.startswith("templates/codex/"):
            source = "templates/" + source.removeprefix("templates/codex/")
            asset["source"] = source
            changed = True
        if source:
            current = manifest_sha256(_source_path(root, source))
            if asset.get("current_sha256") != current:
                asset["current_sha256"] = current
                changed = True
            if asset.get("merge_policy") == "codex-hooks":
                validation = _codex_hooks_merge_validation(
                    _source_path(root, source).read_bytes()
                )
                current_projection_sha256 = _canonical_json_sha256(
                    validation["required_handlers"]
                )
                handler_history = _codex_hooks_handler_history(
                    root,
                    source,
                    baselines,
                    validation["required_handlers"],
                )
                if handler_history:
                    validation["historical_handler_sha256"] = handler_history
                validation["managed_top_level_historical"] = (
                    _codex_hooks_top_level_history(
                        root,
                        source,
                        baselines,
                        validation["managed_top_level"],
                    )
                )
                validation["current_projection_sha256"] = (
                    current_projection_sha256
                )
                if asset.get("merge_validation") != validation:
                    asset["merge_validation"] = validation
                    changed = True
            managed = asset.get("managed_blocks")
            if isinstance(managed, dict):
                payload = _source_path(root, source).read_bytes()
                projection = _managed_markdown_projection_sha256(
                    root,
                    asset,
                    payload,
                )
                if managed.get("current_projection_sha256") != projection:
                    managed["current_projection_sha256"] = projection
                    changed = True
                projection_history = _managed_markdown_projection_history(
                    managed.get("historical_projection_sha256"),
                    root,
                    asset,
                    baselines,
                )
                if managed.get("historical_projection_sha256") != projection_history:
                    managed["historical_projection_sha256"] = projection_history
                    changed = True
        if asset.get("strategy") == "region":
            if "historical_sha256" in asset:
                asset.pop("historical_sha256")
                changed = True
        else:
            history_source = source or asset.get("historical_source")
            history: dict[str, list[str]] = {}
            if history_source:
                history = _merge_history(
                    asset.get("historical_sha256"),
                    root,
                    history_source,
                    baselines,
                )
            transition_hash = PRE_FLATTEN_ASSET_SHA256.get(str(asset.get("id")))
            if transition_hash is not None:
                transition_hashes = history.setdefault(PRE_FLATTEN_VERSION, [])
                if transition_hash not in transition_hashes:
                    transition_hashes.append(transition_hash)
                    transition_hashes.sort()
            project_zone_transition = PROJECT_ZONE_TRANSITION_ASSET_SHA256.get(
                str(asset.get("id"))
            )
            if project_zone_transition is not None:
                transition_hashes = history.setdefault(
                    PROJECT_ZONE_TRANSITION_VERSION, []
                )
                if project_zone_transition not in transition_hashes:
                    transition_hashes.append(project_zone_transition)
                    transition_hashes.sort()
            if asset.get("historical_sha256") != history:
                asset["historical_sha256"] = history
                changed = True
        layout = asset.get("section_layout") if isinstance(asset, dict) else None
        if isinstance(layout, dict) and isinstance(source, str):
            history_entries = [
                entry
                for entry in _layout_entries(layout)
                if entry.get("ownership") == "managed"
            ]
            history_entries.extend(layout.get("retired_sections", []))
            for entry in history_entries:
                headings = [str(item) for item in entry.get("legacy_headings", [])]
                merged = _merge_layout_history(
                    entry.get("trusted_legacy_sha256"),
                    root,
                    source,
                    baselines,
                    headings,
                    entry.get("hash_normalizer"),
                )
                if entry.get("trusted_legacy_sha256") != merged:
                    entry["trusted_legacy_sha256"] = merged
                    changed = True
        zones = asset.get("agents_zones") if isinstance(asset, dict) else None
        if isinstance(zones, dict) and isinstance(source, str):
            public = zones["public"]
            source_payload = _source_path(root, source).read_bytes()
            public_payload = _agents_public_block(
                source_payload, str(public["begin"]), str(public["end"])
            )
            if public_payload is None:
                raise ValueError("Codex AGENTS public zone markers are invalid")
            current_public = f"sha256:{hashlib.sha256(public_payload).hexdigest()}"
            if public.get("current_sha256") != current_public:
                public["current_sha256"] = current_public
                changed = True
            public_history = _merge_agents_public_history(
                public.get("historical_sha256"), root, source, baselines,
                str(public["begin"]), str(public["end"]),
            )
            if public.get("historical_sha256") != public_history:
                public["historical_sha256"] = public_history
                changed = True
        region = asset.get("region") if isinstance(asset, dict) else None
        if isinstance(region, dict) and isinstance(source, str):
            begin = str(region.get("begin", ""))
            end = str(region.get("end", ""))
            source_payload = _source_path(root, source).read_bytes()
            current_region = _managed_region_block(source_payload, begin, end)
            if current_region is None:
                raise ValueError("Codex managed region markers are invalid")
            current_region_hash = f"sha256:{hashlib.sha256(current_region).hexdigest()}"
            if region.get("current_sha256") != current_region_hash:
                region["current_sha256"] = current_region_hash
                changed = True
            if "historical_sha256" in region:
                region.pop("historical_sha256")
                changed = True

    serialized = json.dumps(contract, ensure_ascii=False, indent=2) + "\n"
    mirror_changed = False
    mirror_path: Path | None = None
    if contract_path.resolve() == MANAGED_CONTRACT.resolve():
        mirror_path = DOGFOOD_MANAGED_CONTRACT
        mirror_changed = (
            not mirror_path.is_file()
            or mirror_path.read_text(encoding="utf-8-sig") != serialized
        )
    if write and (changed or mirror_changed):
        contract_path.write_text(serialized, encoding="utf-8")
        if mirror_path is not None:
            mirror_path.write_text(serialized, encoding="utf-8")
    return changed or mirror_changed


def git_blob_bytes_from_bytes(payload: bytes) -> bytes:
    if b"\0" in payload:
        return payload
    return payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def rebuild_manifest(manifest_path: Path, *, write: bool = True) -> bool:
    manifest_path = manifest_path.resolve()
    repository_root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    changed = False

    reconcile_inventory = manifest_path == ACTIVE_MANIFEST.resolve()
    expected_bundle: set[str] = set()
    if reconcile_inventory:
        # The Codex skill shelf is only a bootstrap/entry surface.  The full,
        # canonical product repository lives in ~/.bridgeforge-codex so that
        # templates and runtime scripts have one user-level source of truth.
        expected_bundle.update(
            {
                "skills/bridgeforge-codex/agents/openai.yaml",
                "skills/bridgeforge-codex/SKILL.md",
                "skills/bridgeforge-codex/references/adopt.md",
                "skills/bridgeforge-codex/references/init.md",
                "skills/bridgeforge-codex/references/update.md",
                "skills/bridgeforge-codex/references/user-skill-maintenance.md",
                "scripts/bridgeforge_codex_shared_update.ps1",
            }
        )
        expected_remote = "https://github.com/freakybridge/BridgeForgeCodex.git"
        if manifest.get("canonical_remote") != expected_remote:
            manifest["canonical_remote"] = expected_remote
            changed = True
        if "product_remote" in manifest:
            del manifest["product_remote"]
            changed = True
        codex_platform = manifest["platforms"]["codex"]
        if set(manifest["platforms"]) != {"codex"}:
            manifest["platforms"] = {"codex": codex_platform}
            changed = True
    for platform in manifest["platforms"].values():
        for skill in platform["skills"]:
            if reconcile_inventory and skill.get("name") == "bridgeforge-codex":
                current = {item["source"]: item for item in skill["files"]}
                rebuilt = []
                for source in sorted(expected_bundle):
                    item = current.get(source, {"source": source, "target": source})
                    skill_prefix = "skills/bridgeforge-codex/"
                    if source.startswith(skill_prefix):
                        item["target"] = source.removeprefix(skill_prefix)
                    else:
                        item["target"] = source
                    rebuilt.append(item)
                if rebuilt != skill["files"]:
                    skill["files"] = rebuilt
                    changed = True
            for item in skill["files"]:
                expected = manifest_sha256(_source_path(repository_root, item["source"]))
                if item.get("sha256") != expected:
                    item["sha256"] = expected
                    changed = True

    if changed and write:
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Manifest to rebuild (default: repository shared-skill manifest).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero instead of writing when the manifest is stale.",
    )
    args = parser.parse_args()

    try:
        contract_changed = False
        if args.manifest.resolve() == DEFAULT_MANIFEST.resolve():
            contract_changed = rebuild_managed_contract(write=not args.check)
        changed = rebuild_manifest(args.manifest, write=not args.check)
    except (FileNotFoundError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"[manifest] {exc}", file=sys.stderr)
        return 2

    if (changed or contract_changed) and args.check:
        print(f"[manifest] stale: {args.manifest}", file=sys.stderr)
        return 1
    any_changed = changed or contract_changed
    print(f"[manifest] {'rebuilt' if any_changed else 'already current'}: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
