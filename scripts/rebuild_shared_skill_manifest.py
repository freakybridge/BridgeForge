#!/usr/bin/env python3
"""Rebuild bridgeforge-codex shared-skill hashes and managed lineage.

The shared updater verifies raw file bytes. bridgeforge-codex ships from GitHub,
whose text blobs use LF because of .gitattributes, so this script must not hash
the local Windows checkout verbatim when it happens to use CRLF.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_MANIFEST = REPOSITORY_ROOT / "bridgeforge-codex-manifest.json"
COMPATIBILITY_MANIFEST = REPOSITORY_ROOT / "shared-skill-manifest.json"
DEFAULT_MANIFEST = ACTIVE_MANIFEST
LEGACY_DISTRIBUTION_REVISION = "1e4124358a5d0c6cee9dd73bcb7b18bc904515c9"
LEGACY_HARVEST_REVISION = "1af7d55b429c847558768241c28a49dda1d0a8f9"
COMPATIBILITY_ASSET_ROOT = REPOSITORY_ROOT / "scripts" / "compat" / "legacy-shared-skills"
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
    known_hashes = {value for values in history.values() for value in values}
    for version, revision in baselines.items():
        payload = _git_blob_at(root, revision, source)
        if payload is None:
            continue
        digest = f"sha256:{hashlib.sha256(git_blob_bytes_from_bytes(payload)).hexdigest()}"
        if digest not in known_hashes:
            history.setdefault(version, [])
            history[version].append(digest)
            history[version].sort()
            known_hashes.add(digest)
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


def _merge_region_history(
    existing: Any,
    root: Path,
    source: str,
    baselines: dict[str, str],
    begin: str,
    end: str,
) -> dict[str, list[str]]:
    history = _merge_history(existing, root, "__no_region_history__", {})
    known = {value for values in history.values() for value in values}
    for version, revision in baselines.items():
        payload = _git_blob_at(root, revision, source)
        if payload is None:
            continue
        block = _managed_region_block(payload, begin, end)
        if block is None:
            continue
        digest = f"sha256:{hashlib.sha256(block).hexdigest()}"
        if digest in known:
            continue
        history.setdefault(version, []).append(digest)
        history[version].sort()
        known.add(digest)
    return dict(
        sorted(history.items(), key=lambda item: _stable_semver(item[0]) or (0, 0, 0))
    )


def _merge_agents_public_history(
    existing: Any,
    root: Path,
    source: str,
    baselines: dict[str, str],
    begin: str,
    end: str,
) -> dict[str, list[str]]:
    history = _merge_history(existing, root, "__no_whole_file_history__", {})
    known = {value for values in history.values() for value in values}
    for version, revision in baselines.items():
        payload = _git_blob_at(root, revision, source)
        if payload is None:
            continue
        public = _agents_public_block(payload, begin, end)
        if public is None:
            continue
        digest = f"sha256:{hashlib.sha256(public).hexdigest()}"
        if digest not in known:
            history.setdefault(version, []).append(digest)
            history[version].sort()
            known.add(digest)
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
        known = {digest for values in by_version.values() for digest in values}
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
            if digest in known:
                continue
            by_version.setdefault(version, []).append(digest)
            by_version[version].sort()
            known.add(digest)
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
    known = {digest for values in history.values() for digest in values}
    for version, revision in baselines.items():
        payload = _git_blob_at(root, revision, source)
        if payload is None:
            continue
        residual = PROJECT_TITLE_RE.sub(
            PROJECT_TITLE_NORMALIZED,
            _layout_residual_bytes(payload, layout),
        )
        digest = f"sha256:{hashlib.sha256(residual).hexdigest()}"
        if digest in known:
            continue
        history.setdefault(version, []).append(digest)
        history[version].sort()
        known.add(digest)
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
            if not isinstance(layout, dict):
                raise ValueError("Codex AGENTS zones require a legacy section layout")
            residual_history = _merge_layout_residual_history(
                layout.get("trusted_residual_sha256"),
                root,
                source,
                baselines,
                layout,
            )
            if layout.get("trusted_residual_sha256") != residual_history:
                layout["trusted_residual_sha256"] = residual_history
                changed = True
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
            region_history = _merge_region_history(
                region.get("historical_sha256"),
                root,
                source,
                baselines,
                begin,
                end,
            )
            if region.get("historical_sha256") != region_history:
                region["historical_sha256"] = region_history
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
    manifest_missing = not manifest_path.is_file()
    if manifest_path == ACTIVE_MANIFEST.resolve() and manifest_missing:
        seed = json.loads(
            COMPATIBILITY_MANIFEST.read_text(encoding="utf-8-sig")
        )
        codex = seed["platforms"]["codex"]
        manifest = {
            "schema_version": 1,
            "canonical_remote": "https://github.com/freakybridge/BridgeForgeCodex.git",
            "branch": "main",
            "platforms": {
                "codex": {
                    "target": codex["target"],
                    "skills": [
                        item
                        for item in codex["skills"]
                        if not item.get("legacy_transition")
                    ],
                }
            },
        }
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    changed = manifest_missing

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
        active_skills = [
            item
            for item in codex_platform["skills"]
            if not item.get("legacy_transition")
        ]
        if codex_platform["skills"] != active_skills:
            codex_platform["skills"] = active_skills
            changed = True
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


def _compatibility_asset(
    platform: str,
    skill: str,
    target: str,
    payload: bytes,
    *,
    write: bool,
) -> tuple[dict[str, str], bool]:
    relative = Path("scripts/compat/legacy-shared-skills") / platform / skill / target
    destination = REPOSITORY_ROOT / relative
    changed = not destination.is_file() or destination.read_bytes() != payload
    if changed and write:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    return {
        "source": relative.as_posix(),
        "target": Path(target).as_posix(),
        "sha256": f"sha256:{hashlib.sha256(payload).hexdigest()}",
    }, changed


def rebuild_compatibility_manifest(*, write: bool = True) -> bool:
    raw = _git_blob_at(
        REPOSITORY_ROOT,
        LEGACY_DISTRIBUTION_REVISION,
        "shared-skill-manifest.json",
    )
    if raw is None:
        raise ValueError("Cannot read the pinned legacy distribution manifest")
    legacy = json.loads(raw.decode("utf-8-sig"))
    active = json.loads(ACTIVE_MANIFEST.read_text(encoding="utf-8-sig"))
    active_command = next(
        item
        for item in active["platforms"]["codex"]["skills"]
        if item.get("name") == "bridgeforge-codex"
    )
    legacy_entry = REPOSITORY_ROOT / "scripts/bridgeforge_codex_legacy_entry.SKILL.md"
    bridge = {
        "name": "bridgeforge",
        "legacy_transition": True,
        "files": [{
            "source": "scripts/bridgeforge_codex_legacy_entry.SKILL.md",
            "target": "SKILL.md",
            "sha256": manifest_sha256(legacy_entry),
        }],
    }
    harvest_payload = _git_blob_at(
        REPOSITORY_ROOT,
        LEGACY_HARVEST_REVISION,
        "skills/harvest/SKILL.md",
    )
    if harvest_payload is None:
        raise ValueError("Cannot read the last managed harvest payload")

    changed = False
    platforms: dict[str, dict[str, Any]] = {}
    for platform in ("codex", "claude"):
        frozen: list[dict[str, Any]] = []
        for skill in legacy["platforms"][platform]["skills"]:
            name = str(skill["name"])
            if name == "bridgeforge":
                continue
            files: list[dict[str, str]] = []
            for item in skill["files"]:
                payload = _git_blob_at(
                    REPOSITORY_ROOT,
                    LEGACY_DISTRIBUTION_REVISION,
                    str(item["source"]),
                )
                if payload is None:
                    raise ValueError(
                        f"Cannot read pinned legacy payload: {platform}/{name}/{item['target']}"
                    )
                rebuilt, file_changed = _compatibility_asset(
                    platform,
                    name,
                    str(item["target"]),
                    payload,
                    write=write,
                )
                changed = changed or file_changed
                files.append(rebuilt)
            frozen.append({
                "name": name,
                "legacy_transition": True,
                "files": files,
            })
        harvest_file, harvest_changed = _compatibility_asset(
            platform,
            "harvest",
            "SKILL.md",
            harvest_payload,
            write=write,
        )
        changed = changed or harvest_changed
        skills = [bridge, *frozen, {
            "name": "harvest",
            "legacy_transition": True,
            "files": [harvest_file],
        }]
        if platform == "codex":
            skills.append(active_command)
        platforms[platform] = {
            "target": legacy["platforms"][platform]["target"],
            "retired_compatibility_surface": True,
            "skills": skills,
        }
    manifest = {
        "schema_version": 1,
        "canonical_remote": "https://github.com/freakybridge/BridgeForge.git",
        "product_remote": "https://github.com/freakybridge/BridgeForgeCodex.git",
        "branch": "main",
        "platforms": platforms,
    }
    serialized = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    manifest_changed = (
        not COMPATIBILITY_MANIFEST.is_file()
        or COMPATIBILITY_MANIFEST.read_text(encoding="utf-8-sig") != serialized
    )
    if manifest_changed and write:
        COMPATIBILITY_MANIFEST.write_text(serialized, encoding="utf-8")
    return changed or manifest_changed


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
        compatibility_changed = False
        if args.manifest.resolve() == DEFAULT_MANIFEST.resolve():
            contract_changed = rebuild_managed_contract(write=not args.check)
        changed = rebuild_manifest(args.manifest, write=not args.check)
        if args.manifest.resolve() == DEFAULT_MANIFEST.resolve():
            compatibility_changed = rebuild_compatibility_manifest(
                write=not args.check
            )
    except (FileNotFoundError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"[manifest] {exc}", file=sys.stderr)
        return 2

    if (changed or contract_changed or compatibility_changed) and args.check:
        print(f"[manifest] stale: {args.manifest}", file=sys.stderr)
        return 1
    any_changed = changed or contract_changed or compatibility_changed
    print(f"[manifest] {'rebuilt' if any_changed else 'already current'}: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
