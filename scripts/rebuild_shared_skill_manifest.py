#!/usr/bin/env python3
"""Rebuild current-only skeleton and shared-skill manifests."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_MANIFEST = REPOSITORY_ROOT / "bridgeforge-codex-manifest.json"
DEFAULT_MANIFEST = ACTIVE_MANIFEST
MANAGED_CONTRACT = REPOSITORY_ROOT / "templates" / "managed-skeleton.json"
DOGFOOD_MANAGED_CONTRACT = REPOSITORY_ROOT / ".codex" / "managed-skeleton.json"
MANAGED_HOOK_PREFIX = "bridgeforge-codex.project-hook.v1:"
CANONICAL_REMOTE = "https://github.com/freakybridge/BridgeForgeCodex.git"


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _loads_json(text: str) -> Any:
    return json.loads(text, object_pairs_hook=_unique_object)


def _managed_target_key(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{label} must use one explicit POSIX relative path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != value
        or any(char in value for char in "*?[")
    ):
        raise ValueError(f"{label} is unsafe: {value!r}")
    return path.as_posix().casefold()


def validate_manifest_path(
    manifest_path: Path,
    *,
    repository_root: Path | None = None,
    validate_sources: bool = False,
) -> dict[str, Any]:
    contract_path = REPOSITORY_ROOT / "templates" / "scripts" / "current_baseline.py"
    module_name = "_bridgeforge_factory_manifest_contract"
    spec = importlib.util.spec_from_file_location(module_name, contract_path)
    if spec is None or spec.loader is None:
        raise ValueError("factory manifest contract cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    previous_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
        return module.validate_factory_manifest_path(
            manifest_path,
            repository_root=repository_root,
            validate_sources=validate_sources,
        )
    except Exception as exc:
        raise ValueError(str(exc)) from exc
    finally:
        sys.dont_write_bytecode = previous_dont_write_bytecode
        sys.modules.pop(module_name, None)


def git_blob_bytes(path: Path) -> bytes:
    payload = path.read_bytes()
    if b"\0" in payload:
        return payload
    return payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def manifest_sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(git_blob_bytes(path)).hexdigest()


def _payload_sha256(payload: bytes) -> str:
    normalized = payload if b"\0" in payload else payload.replace(
        b"\r\n", b"\n"
    ).replace(b"\r", b"\n")
    return "sha256:" + hashlib.sha256(normalized).hexdigest()


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _source_path(root: Path, source: object) -> Path:
    if not isinstance(source, str) or not source:
        raise ValueError("managed asset source must be an explicit path")
    path = (root / source).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"managed asset source escapes repository root: {source}") from exc
    if not path.is_file():
        raise FileNotFoundError(f"managed asset source is missing: {source}")
    return path


def _marker_block(payload: bytes, begin: str, end: str) -> bytes:
    normalized = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    lines = normalized.splitlines(keepends=True)
    begin_bytes = begin.encode("utf-8")
    end_bytes = end.encode("utf-8")
    starts = [index for index, line in enumerate(lines) if line.rstrip(b"\n") == begin_bytes]
    stops = [index for index, line in enumerate(lines) if line.rstrip(b"\n") == end_bytes]
    if len(starts) != 1 or len(stops) != 1 or starts[0] >= stops[0]:
        raise ValueError(f"managed markers are missing or duplicated: {begin} / {end}")
    return b"".join(lines[starts[0] : stops[0] + 1])


def _heading_section(payload: bytes, heading: str) -> bytes:
    normalized = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    lines = normalized.splitlines(keepends=True)
    wanted = heading.encode("utf-8")
    starts = [index for index, line in enumerate(lines) if line.rstrip(b"\n") == wanted]
    if len(starts) != 1:
        raise ValueError(f"Markdown heading is missing or duplicated: {heading}")
    level = len(heading) - len(heading.lstrip("#"))
    stop = len(lines)
    for index in range(starts[0] + 1, len(lines)):
        match = re.match(br"^(#{1,6})\s", lines[index].rstrip(b"\n"))
        if match is not None and len(match.group(1)) <= level:
            stop = index
            break
    return b"".join(lines[starts[0] : stop])


def _table_rows(section: bytes) -> dict[str, bytes]:
    table = [line for line in section.splitlines(keepends=True) if line.lstrip().startswith(b"|")]
    if len(table) < 2:
        raise ValueError("managed Markdown table is missing")
    rows: dict[str, bytes] = {}
    for line in table[2:]:
        cells = [cell.strip() for cell in line.strip().strip(b"|").split(b"|")]
        if not cells:
            continue
        key = cells[0].decode("utf-8").strip()
        link = re.fullmatch(r"\[`[^`]+`\]\(([^)]+)\)", key)
        if link is not None:
            key = link.group(1)
        key = key.strip("`").casefold()
        if key in rows:
            raise ValueError(f"managed Markdown table key is duplicated: {key}")
        rows[key] = line.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return rows


def _markdown_projection(payload: bytes, managed: dict[str, Any]) -> dict[str, Any]:
    headings = {
        str(heading): "sha256:" + hashlib.sha256(
            _heading_section(payload, str(heading))
        ).hexdigest()
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
                raise ValueError(f"managed Markdown row is missing: {heading} :: {raw_key}")
            projected[key] = "sha256:" + hashlib.sha256(rows[key]).hexdigest()
        tables[heading] = projected
    return {"headings": headings, "keyed_tables": tables}


def _hook_stage(handler: dict[str, Any]) -> str:
    command = str(handler.get("commandWindows") or handler.get("command") or "")
    match = re.search(
        r"hook_dispatcher\.py(?:['\"\)]|\s)+"
        r"(pre-tool|post-read|post-edit|post-shell|post-compact|stop|user-prompt|session-start)",
        command.replace("\\", "/").casefold(),
    )
    return match.group(1) if match else "unknown"


def _hooks_validation(payload: bytes) -> dict[str, Any]:
    try:
        document = _loads_json(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"templates/hooks.json is invalid: {exc}") from exc
    if not isinstance(document, dict) or not isinstance(document.get("hooks"), dict):
        raise ValueError("templates/hooks.json has no hooks object")
    required: list[dict[str, str]] = []
    seen: set[str] = set()
    for event, entries in document["hooks"].items():
        if not isinstance(entries, list):
            raise ValueError(f"templates/hooks.json event is invalid: {event}")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                raise ValueError(f"templates/hooks.json group is invalid: {event}")
            matcher = entry.get("matcher", "")
            for handler in entry["hooks"]:
                if not isinstance(handler, dict):
                    raise ValueError(f"templates/hooks.json handler is invalid: {event}")
                handler_id = handler.get("bridgeforgeCodexId")
                if not isinstance(handler_id, str) or not handler_id.startswith(MANAGED_HOOK_PREFIX):
                    continue
                if handler_id in seen:
                    raise ValueError(f"managed hook id is duplicated: {handler_id}")
                seen.add(handler_id)
                required.append({
                    "id": handler_id,
                    "event": str(event),
                    "matcher": str(matcher),
                    "stage": _hook_stage(handler),
                    "sha256": _canonical_sha256(handler),
                })
    if not required:
        raise ValueError("templates/hooks.json has no managed handlers")
    required.sort(key=lambda item: (item["event"], item["matcher"], item["id"]))
    return {
        "format": "codex-hooks-current-v1",
        "required_handlers": required,
        "managed_top_level": {"description": document.get("description")},
    }


def render_managed_contract(
    contract_path: Path = MANAGED_CONTRACT,
    *,
    release_version: str | None = None,
) -> bytes:
    try:
        contract = _loads_json(contract_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read current-only managed contract: {exc}") from exc
    if (
        not isinstance(contract, dict)
        or contract.get("schema_version") != 3
        or contract.get("baseline_model") != "current-only"
        or not isinstance(contract.get("assets"), list)
    ):
        raise ValueError("managed-skeleton.json must use the current-only schema")
    allowed_top = {
        "schema_version", "release_version", "host", "stamp",
        "contract_target", "baseline_model", "assets",
    }
    if set(contract) != allowed_top:
        raise ValueError("managed-skeleton.json top-level fields are not schema 3 exact")
    current_release = release_version or (REPOSITORY_ROOT / "VERSION").read_text(
        encoding="utf-8-sig"
    ).strip()
    if re.fullmatch(r"\d+\.\d+\.\d+", current_release) is None:
        raise ValueError("root VERSION must be MAJOR.MINOR.PATCH")
    contract["release_version"] = current_release
    seen_ids: set[str] = set()
    seen_targets: set[str] = set()
    for asset in contract["assets"]:
        if not isinstance(asset, dict):
            raise ValueError("managed contract contains a non-object asset")
        allowed_asset = {
            "id", "source", "target", "strategy", "current_sha256", "render",
            "agents_zones", "managed_blocks", "merge_policy", "merge_validation",
            "region",
        }
        unknown_fields = set(asset) - allowed_asset
        if unknown_fields:
            raise ValueError(
                "managed contract asset has non-schema fields: "
                + ", ".join(sorted(unknown_fields))
            )
        asset_id = asset.get("id")
        target = asset.get("target")
        if not isinstance(asset_id, str) or asset_id in seen_ids:
            raise ValueError(f"managed contract asset id is invalid: {asset_id!r}")
        target_key = _managed_target_key(target, f"asset {asset_id} target")
        if target_key in seen_targets:
            raise ValueError(f"managed contract asset target is invalid: {target!r}")
        if asset.get("strategy") not in {"whole", "merge", "region", "seed"}:
            raise ValueError(f"managed contract asset strategy is invalid: {asset_id}")
        source = _source_path(REPOSITORY_ROOT, asset.get("source"))
        asset["current_sha256"] = manifest_sha256(source)
        asset.pop("current_projection_sha256", None)
        managed = asset.get("managed_blocks")
        if isinstance(managed, dict):
            managed.pop("current_projection_sha256", None)
        if asset.get("merge_policy") == "codex-hooks":
            asset["merge_validation"] = _hooks_validation(source.read_bytes())
        elif asset.get("strategy") == "merge":
            try:
                required = _loads_json(source.read_text(encoding="utf-8-sig"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"managed merge source must be JSON: {asset_id}: {exc}") from exc
            if not isinstance(required, dict):
                raise ValueError(f"managed merge source must be an object: {asset_id}")
            asset["merge_validation"] = {
                "format": "json-subset-current-v1",
                "required": required,
            }
        if isinstance(managed, dict):
            managed["current_projection_sha256"] = _canonical_sha256(
                _markdown_projection(source.read_bytes(), managed)
            )
        zones = asset.get("agents_zones")
        if isinstance(zones, dict) and isinstance(zones.get("public"), dict):
            public = zones["public"]
            block = _marker_block(
                source.read_bytes(),
                str(public.get("begin", "")),
                str(public.get("end", "")),
            )
            public["current_sha256"] = (
                "sha256:" + hashlib.sha256(block).hexdigest()
            )
        region = asset.get("region")
        if isinstance(region, dict):
            block = _marker_block(
                source.read_bytes(),
                str(region.get("begin", "")),
                str(region.get("end", "")),
            )
            region["current_sha256"] = (
                "sha256:" + hashlib.sha256(block).hexdigest()
            )
        seen_ids.add(asset_id)
        seen_targets.add(target_key)
    serialized = json.dumps(contract, ensure_ascii=False, indent=2) + "\n"
    return serialized.encode("utf-8")


def rebuild_managed_contract(
    contract_path: Path = MANAGED_CONTRACT,
    *,
    write: bool = True,
) -> bool:
    encoded = render_managed_contract(contract_path)
    current = contract_path.read_bytes()
    mirror_changed = (
        contract_path.resolve() == MANAGED_CONTRACT.resolve()
        and (
            not DOGFOOD_MANAGED_CONTRACT.is_file()
            or DOGFOOD_MANAGED_CONTRACT.read_bytes() != encoded
        )
    )
    changed = current != encoded
    if write and (changed or mirror_changed):
        contract_path.write_bytes(encoded)
        if (
            contract_path.resolve() == MANAGED_CONTRACT.resolve()
            and (
                not DOGFOOD_MANAGED_CONTRACT.is_file()
                or DOGFOOD_MANAGED_CONTRACT.read_bytes() != encoded
            )
        ):
            DOGFOOD_MANAGED_CONTRACT.write_bytes(encoded)
    return changed or mirror_changed


def render_manifest(
    manifest_path: Path,
    *,
    overlays: dict[Path, bytes] | None = None,
) -> bytes:
    path = manifest_path.resolve()
    root = path.parent
    manifest = validate_manifest_path(path, repository_root=root)
    for platform in manifest["platforms"].values():
        for skill in platform["skills"]:
            for item in skill["files"]:
                source = _source_path(root, item["source"])
                overlay = (overlays or {}).get(source.resolve())
                expected = (
                    _payload_sha256(overlay)
                    if overlay is not None
                    else manifest_sha256(source)
                )
                item["sha256"] = expected
    return (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def rebuild_manifest(manifest_path: Path, *, write: bool = True) -> bool:
    path = manifest_path.resolve()
    encoded = render_manifest(path)
    changed = path.read_bytes() != encoded
    if changed and write:
        path.write_bytes(encoded)
    return changed


def render_all_outputs(
    manifest_path: Path = DEFAULT_MANIFEST,
    *,
    release_version: str | None = None,
) -> dict[Path, bytes]:
    path = manifest_path.resolve()
    outputs: dict[Path, bytes] = {}
    overlays: dict[Path, bytes] = {}
    if path == DEFAULT_MANIFEST.resolve():
        contract = render_managed_contract(
            MANAGED_CONTRACT,
            release_version=release_version,
        )
        outputs[MANAGED_CONTRACT.resolve()] = contract
        outputs[DOGFOOD_MANAGED_CONTRACT.resolve()] = contract
        overlays[MANAGED_CONTRACT.resolve()] = contract
        overlays[DOGFOOD_MANAGED_CONTRACT.resolve()] = contract
    outputs[path] = render_manifest(path, overlays=overlays)
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        outputs = render_all_outputs(args.manifest)
    except (FileNotFoundError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"[manifest] {exc}", file=sys.stderr)
        return 2
    changed = {
        path: payload
        for path, payload in outputs.items()
        if not path.is_file() or path.read_bytes() != payload
    }
    if args.check and changed:
        print(f"[manifest] stale: {args.manifest}", file=sys.stderr)
        return 2
    if changed:
        for path, payload in changed.items():
            path.write_bytes(payload)
        print(f"[manifest] updated: {args.manifest}")
    else:
        print(f"[manifest] unchanged: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
