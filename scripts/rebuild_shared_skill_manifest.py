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
import sys
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPOSITORY_ROOT / "shared-skill-manifest.json"


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


def rebuild_manifest(manifest_path: Path) -> bool:
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
                "scripts/bridgeforge_switch.py",
                "scripts/bridgeforge_migrate_layout.py",
                "scripts/bridgeforge_shared_update.ps1",
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

    if changed:
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
        changed = rebuild_manifest(args.manifest)
    except (FileNotFoundError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"[manifest] {exc}", file=sys.stderr)
        return 2

    if changed and args.check:
        print(f"[manifest] stale: {args.manifest}", file=sys.stderr)
        return 1
    print(f"[manifest] {'rebuilt' if changed else 'already current'}: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
