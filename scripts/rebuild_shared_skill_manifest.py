#!/usr/bin/env python3
"""Rebuild shared-skill SHA-256 values from GitHub-equivalent source bytes.

The shared updater verifies raw file bytes. BridgeForge ships from GitHub,
whose text blobs use LF because of .gitattributes, so this script must not hash
the local Windows checkout verbatim when it happens to use CRLF.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPOSITORY_ROOT / "shared-skill-manifest.json"
MANAGED_CONTRACT = REPOSITORY_ROOT / "templates" / "codex" / "managed-skeleton.json"
DOGFOOD_MANAGED_CONTRACT = REPOSITORY_ROOT / ".codex" / "managed-skeleton.json"
MINIMUM_MANAGED_VERSION = (0, 86, 0)


def git_blob_bytes(path: Path) -> bytes:
    """Return bytes matching the LF text blob that BridgeForge publishes.

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
    return result.stdout if result.returncode == 0 else None


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
            "Cannot enumerate BridgeForge release history: "
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
        keyed_tables = managed.get("keyed_tables", []) if isinstance(managed, dict) else None
        if (
            not isinstance(managed, dict)
            or managed.get("format") != "markdown-headings"
            or not isinstance(headings, list)
            or not isinstance(keyed_tables, list)
            or (not headings and not keyed_tables)
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
                or table.get("key_column") != 0
                or not isinstance(managed_keys, list)
                or not managed_keys
                or any(not isinstance(key, str) or not key.strip() for key in managed_keys)
                or len({key.casefold() for key in managed_keys}) != len(managed_keys)
            ):
                raise ValueError("Codex managed keyed-table ownership is invalid")
            seen_table_headings.add(heading)
    changed = False
    root = contract_path.parents[2]
    baselines = _baseline_revisions(root)
    contract_source = contract_path.relative_to(root).as_posix()
    historical_contract = _merge_history(
        contract.get("contract_historical_sha256"),
        root,
        contract_source,
        baselines,
    )
    if contract.get("contract_historical_sha256") != historical_contract:
        contract["contract_historical_sha256"] = historical_contract
        changed = True

    for asset in contract["assets"]:
        source = asset.get("source")
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
        if asset.get("historical_sha256") != history:
            asset["historical_sha256"] = history
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
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    changed = False

    reconcile_inventory = manifest_path == DEFAULT_MANIFEST.resolve()
    expected_bundle: set[str] = set()
    if reconcile_inventory:
        expected_bundle.update(
            {
                "VERSION",
                "CHANGELOG.md",
                "skills/bridgeforge/SKILL.md",
                "skills/bridgeforge/references/adopt.md",
                "skills/bridgeforge/references/init.md",
                "skills/bridgeforge/references/switch.md",
                "skills/bridgeforge/references/update.md",
                "skills/bridgeforge/references/user-skill-maintenance.md",
                ".githooks/pre-commit",
                "scripts/bridgeforge_project_sync.py",
                "scripts/bridgeforge_switch.py",
                "scripts/bridgeforge_migrate_layout.py",
                "scripts/bridgeforge_project_finalize.py",
                "scripts/bridgeforge_shared_update.ps1",
                "scripts/bridgeforge_user_maintenance.ps1",
                "scripts/codex_memory_sync.py",
            }
        )
        expected_bundle.update(
            path.relative_to(repository_root).as_posix()
            for path in (repository_root / "templates").rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        )
    for platform in manifest["platforms"].values():
        for skill in platform["skills"]:
            if reconcile_inventory and skill.get("name") == "bridgeforge":
                current = {item["source"]: item for item in skill["files"]}
                rebuilt = []
                for source in sorted(expected_bundle):
                    item = current.get(source, {"source": source, "target": source})
                    item["target"] = source if source.startswith(("templates/", "scripts/")) else item["target"]
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
