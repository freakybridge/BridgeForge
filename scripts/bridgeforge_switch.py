#!/usr/bin/env python3
"""Switch a project through an approved semantic-migration manifest.

The script deliberately does not decide semantic equivalence. Without an
approved manifest it only inventories the current project and prints a
proposal. Applying a manifest is mechanical: recheck hashes, build the current
target template in isolation, apply approved target-native projections, verify
the staged target, then commit the switch transactionally.
"""
from __future__ import annotations

import argparse
import base64
import difflib
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AGENTS = ("claude", "codex")
ARCHIVE_ROOT = Path(".bridgeforge") / "archive"
MIGRATION_ROOT = Path(".bridgeforge") / "migrations"
SCHEMA_VERSION = 2
OWNERS = {
    "template-managed",
    "constraint-generated",
    "user-owned",
    "unknown-historical",
}
EVIDENCE_RANK = {
    "text-review": 1,
    "static": 1,
    "contract-smoke": 2,
    "native-host": 3,
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
    config_dirs: tuple[str, ...]
    config_files: tuple[str, ...]


SPECS = {
    "claude": AgentSpec(
        "claude",
        "CLAUDE.md",
        ".claude",
        ("hooks", "memory", "rules", "scripts"),
        (".bridgeforge_version", "settings.json"),
    ),
    "codex": AgentSpec(
        "codex",
        "AGENTS.md",
        ".codex",
        ("agents", "hooks", "memory", "rules", "scripts"),
        (
            ".bridgeforge_version",
            "config.toml",
            "settings.json",
            "skill-routing.json",
            "subscription-tier.toml",
        ),
    ),
}


@dataclass(frozen=True)
class CopyItem:
    src: Path
    rel: str


@dataclass
class Plan:
    agent: str
    old_agent: str
    project_root: Path
    template_root: Path
    template_items: list[CopyItem]
    source_files: dict[str, Path]
    target_archive: Path | None
    archive_files: dict[str, Path]
    receipts: list[dict[str, Any]]
    target_paths: list[Path]
    target_conflicts: list[Path]
    already_target: bool
    python_command: str | None
    source_state: dict[str, str] = field(default_factory=dict)
    snapshots: dict[str, str] = field(default_factory=dict)


class ManifestError(ValueError):
    """Raised when a migration manifest is incomplete or unsafe."""


def _posix(path: Path) -> str:
    return path.as_posix().rstrip("/")


def _rel(path: Path, root: Path) -> str:
    try:
        return _posix(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return _posix(path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _sha_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _state_digest(state: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for rel, value in sorted(state.items()):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _snapshot(files: dict[str, Path]) -> str:
    digest = hashlib.sha256()
    for rel, path in sorted(files.items()):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha_file(path).encode("ascii"))
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _path_state(paths: list[Path], root: Path) -> str:
    files: dict[str, Path] = {}
    markers: list[str] = []
    for path in paths:
        rel = _rel(path, root)
        if path.is_file() or path.is_symlink():
            files[rel] = path
        elif path.is_dir():
            markers.append(rel + "/")
            for directory in sorted(item for item in path.rglob("*") if item.is_dir()):
                markers.append(_rel(directory, root) + "/")
            for child in sorted(item for item in path.rglob("*") if item.is_file()):
                files[_rel(child, root)] = child
        else:
            markers.append(rel + ":absent")
    digest = hashlib.sha256()
    for marker in sorted(markers):
        digest.update(marker.encode("utf-8"))
        digest.update(b"\0")
    digest.update(_snapshot(files).encode("ascii"))
    return "sha256:" + digest.hexdigest()


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


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
        raise ManifestError(f"{label} must not be a symlink or junction: {path}")
    if path.is_dir():
        for child in path.rglob("*"):
            if _is_link_like(child):
                raise ManifestError(
                    f"{label} contains a symlink or junction: {child}"
                )


def _assert_project_local(path: Path, project_root: Path, label: str) -> None:
    root = project_root.resolve()
    current = path
    while current != root and _is_under(current, root):
        if _lexists(current) and _is_link_like(current):
            raise ManifestError(
                f"{label} crosses a symlink or junction: {_rel(current, project_root)}"
            )
        current = current.parent
    resolved = path.resolve(strict=False)
    if not _is_under(resolved, root) and resolved != root:
        raise ManifestError(f"{label} escapes the project root: {path}")


def _windows_path_key(raw: str) -> str:
    rel = _safe_rel(raw)
    canonical: list[str] = []
    for part in Path(rel).parts:
        if part != part.rstrip(" ."):
            raise ManifestError(
                f"Windows-unsafe trailing dot or space in path component: {raw!r}"
            )
        if ":" in part:
            raise ManifestError(f"Windows alternate-data-stream path is forbidden: {raw!r}")
        normalized = unicodedata.normalize("NFC", part).casefold()
        if normalized.split(".", 1)[0] in WINDOWS_RESERVED_NAMES:
            raise ManifestError(f"Windows reserved path component: {raw!r}")
        canonical.append(normalized)
    return "/".join(canonical)


def _safe_rel(raw: str) -> str:
    normalized = raw.replace("\\", "/").strip("/")
    path = Path(normalized)
    if (
        not normalized
        or path.is_absolute()
        or ".." in path.parts
        or normalized.startswith(".bridgeforge/")
    ):
        raise ManifestError(f"unsafe project-relative path: {raw!r}")
    return _posix(path)


def _agent_paths(spec: AgentSpec, project_root: Path) -> list[Path]:
    return [project_root / spec.entry, project_root / spec.config_dir]


def _existing_agent_paths(spec: AgentSpec, project_root: Path) -> list[Path]:
    return [path for path in _agent_paths(spec, project_root) if _lexists(path)]


def _is_complete_agent(spec: AgentSpec, project_root: Path) -> bool:
    paths = _agent_paths(spec, project_root)
    if any(_is_link_like(path) for path in paths):
        return False
    return (
        (project_root / spec.entry).is_file()
        and (project_root / spec.config_dir).is_dir()
        and all(
            (project_root / spec.config_dir / name).is_file()
            for name in spec.config_files
        )
        and all(
            (project_root / spec.config_dir / name).is_dir()
            for name in spec.config_dirs
        )
    )


def _candidate_roots(
    project_root: Path,
    script_path: Path,
    explicit: str | None,
) -> list[Path]:
    raw: list[Path] = []
    if explicit:
        raw.append(Path(explicit))
    home = Path.home()
    raw.extend(
        [
            script_path.parent.parent,
            home / ".bridgeforge",
            home / ".codex" / "skills" / "bridgeforge",
            home / ".claude" / "skills" / "bridgeforge",
        ]
    )
    seen: set[Path] = set()
    roots: list[Path] = []
    for path in raw:
        resolved = path.expanduser().resolve()
        if resolved not in seen:
            seen.add(resolved)
            roots.append(resolved)
    return roots


def find_template_root(
    project_root: Path,
    script_path: Path,
    explicit: str | None,
) -> Path:
    for root in _candidate_roots(project_root, script_path, explicit):
        if (
            (root / "templates" / "claude").is_dir()
            and (root / "templates" / "codex").is_dir()
        ):
            return root
    raise SystemExit(
        "ERROR: cannot find the installed BridgeForge command bundle. "
        "Run no-argument /bridgeforge or pass --template-root explicitly."
    )


def looks_like_bridgeforge_source(root: Path) -> bool:
    return (
        (root / "templates" / "claude").is_dir()
        and (root / "templates" / "codex").is_dir()
        and (root / "SKILL.md").is_file()
    )


def choose_python_command(project_root: Path) -> str | None:
    candidates = [
        (project_root / ".venv" / "Scripts" / "python.exe", ".venv/Scripts/python.exe"),
        (project_root / ".venv" / "bin" / "python", ".venv/bin/python"),
    ]
    for path, command in candidates:
        if path.is_file():
            return command
    if shutil.which("python"):
        return "python"
    return None


def _template_items(
    template_root: Path,
    agent: str,
) -> list[CopyItem]:
    spec = SPECS[agent]
    template = template_root / "templates" / agent
    _assert_no_links(template, f"{agent} target template")
    items: list[CopyItem] = []
    entry = template / spec.entry
    if not entry.is_file():
        raise SystemExit(f"ERROR: target template is missing {spec.entry}")
    items.append(CopyItem(entry, spec.entry))
    for name in spec.config_files:
        source = template_root / "VERSION" if name == ".bridgeforge_version" else template / name
        if not source.is_file():
            raise SystemExit(f"ERROR: target template is missing {agent}/{name}")
        items.append(CopyItem(source, f"{spec.config_dir}/{name}"))
    for name in spec.config_dirs:
        source_dir = template / name
        if not source_dir.is_dir():
            raise SystemExit(f"ERROR: target template is missing {agent}/{name}/")
        for source in sorted(path for path in source_dir.rglob("*") if path.is_file()):
            if "__pycache__" in source.parts or source.suffix == ".pyc":
                continue
            rel = _posix(source.relative_to(source_dir))
            items.append(
                CopyItem(source, f"{spec.config_dir}/{name}/{rel}")
            )
    return items


def template_copy_items(
    template_root: Path,
    project_root: Path,
    agent: str,
) -> list[CopyItem]:
    """Return the complete agent-specific target installation surface."""
    return [
        CopyItem(item.src, _rel(project_root / item.rel, project_root))
        for item in _template_items(template_root, agent)
    ]


def _inventory_paths(paths: list[Path], project_root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in paths:
        _assert_project_local(path, project_root, "agent inventory")
        _assert_no_links(path, "agent inventory")
        if path.is_file():
            files[_rel(path, project_root)] = path
        elif path.is_dir():
            for child in sorted(item for item in path.rglob("*") if item.is_file()):
                if "__pycache__" in child.parts or child.suffix == ".pyc":
                    continue
                files[_rel(child, project_root)] = child
    return files


def _latest_archive(project_root: Path, agent: str) -> Path | None:
    root = project_root / ARCHIVE_ROOT / agent
    _assert_project_local(root, project_root, "archive root")
    _assert_no_links(project_root / ARCHIVE_ROOT, "archive root")
    if not root.is_dir():
        return None
    candidates = sorted(path for path in root.iterdir() if path.is_dir())
    for candidate in candidates:
        _assert_project_local(candidate, project_root, "target archive")
        _assert_no_links(candidate, "target archive")
    return candidates[-1] if candidates else None


def _archive_inventory(archive: Path | None) -> dict[str, Path]:
    if archive is None:
        return {}
    return {
        _posix(path.relative_to(archive)): path
        for path in sorted(item for item in archive.rglob("*") if item.is_file())
        if "__pycache__" not in path.parts and path.suffix != ".pyc"
    }


def _load_receipts(project_root: Path) -> list[dict[str, Any]]:
    root = project_root / MIGRATION_ROOT
    _assert_project_local(root, project_root, "migration root")
    _assert_no_links(root, "migration root")
    if not root.is_dir():
        return []
    receipts: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/receipt.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if (
            isinstance(data, dict)
            and data.get("status") == "success"
            and data.get("schema_version") == SCHEMA_VERSION
        ):
            data["_receipt_path"] = _rel(path, project_root)
            receipts.append(data)
    return receipts


def build_plan(agent: str, project_root: Path, template_root: Path) -> Plan:
    target_spec = SPECS[agent]
    old_agent = "codex" if agent == "claude" else "claude"
    old_spec = SPECS[old_agent]
    old_paths = _existing_agent_paths(old_spec, project_root)
    target_paths = _existing_agent_paths(target_spec, project_root)
    for path in [*old_paths, *target_paths]:
        _assert_project_local(path, project_root, "live agent surface")
        _assert_no_links(path, "live agent surface")
    already_target = _is_complete_agent(target_spec, project_root) and not old_paths
    target_conflicts = target_paths if old_paths or not already_target else []
    template_items = _template_items(template_root, agent)
    source_files = _inventory_paths(old_paths, project_root)
    target_archive = _latest_archive(project_root, agent)
    archive_files = _archive_inventory(target_archive)
    plan = Plan(
        agent=agent,
        old_agent=old_agent,
        project_root=project_root,
        template_root=template_root,
        template_items=template_items,
        source_files=source_files,
        target_archive=target_archive,
        archive_files=archive_files,
        receipts=_load_receipts(project_root),
        target_paths=target_paths,
        target_conflicts=target_conflicts,
        already_target=already_target,
        python_command=choose_python_command(project_root),
    )
    _validate_archive_receipt_inventory(plan)
    plan.source_state = _agent_tree_state(project_root, old_spec)
    template_map = {
        item.rel: item.src
        for item in template_items
    }
    plan.snapshots = {
        "source": _state_digest(plan.source_state),
        "target_template": _snapshot(template_map),
        "target_prestate": _path_state(_agent_paths(target_spec, project_root), project_root),
        "target_archive": (
            _path_state([target_archive], project_root)
            if target_archive is not None
            else _snapshot({})
        ),
    }
    return plan


def _source_template_map(
    plan: Plan,
) -> dict[str, Path]:
    return {
        item.rel: item.src
        for item in _template_items(plan.template_root, plan.old_agent)
    }


def _receipt_target_record(
    plan: Plan,
    rel: str,
    sha256: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for receipt in reversed(plan.receipts):
        if receipt.get("target_agent") != plan.old_agent:
            continue
        for record in receipt.get("target", {}).get("files", []):
            if record.get("path") == rel and record.get("sha256") == sha256:
                return receipt, record
    return None, None


def _archive_receipt(plan: Plan) -> dict[str, Any] | None:
    if plan.target_archive is None:
        return None
    archive_rel = _rel(plan.target_archive, plan.project_root)
    for receipt in reversed(plan.receipts):
        if receipt.get("archive", {}).get("path") == archive_rel:
            return receipt
    return None


def _validate_archive_receipt_inventory(plan: Plan) -> None:
    if plan.target_archive is None:
        return
    receipt = _archive_receipt(plan)
    if receipt is None:
        return
    records = receipt.get("archive", {}).get("files")
    if not isinstance(records, list):
        raise ManifestError("target archive receipt.files is missing or invalid")

    actual: dict[str, str] = {}
    actual_keys: dict[str, str] = {}
    for rel, path in sorted(plan.archive_files.items()):
        key = _windows_path_key(rel)
        if key in actual_keys:
            raise ManifestError(
                "target archive has Windows-equivalent path collision: "
                f"{actual_keys[key]} and {rel}"
            )
        actual_keys[key] = rel
        actual[rel] = _sha_file(path)

    registered: dict[str, str] = {}
    registered_keys: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ManifestError("target archive receipt contains a non-object file record")
        rel = _safe_rel(str(record.get("path", "")))
        key = _windows_path_key(rel)
        if key in registered_keys:
            raise ManifestError(
                "target archive receipt has Windows-equivalent path collision: "
                f"{registered_keys[key]} and {rel}"
            )
        registered_keys[key] = rel
        sha256 = record.get("sha256")
        if not isinstance(sha256, str) or not sha256.startswith("sha256:"):
            raise ManifestError(f"target archive receipt hash is invalid: {rel}")
        registered[rel] = sha256

    missing = sorted(set(registered) - set(actual))
    extra = sorted(set(actual) - set(registered))
    mismatched = sorted(
        rel
        for rel in set(actual) & set(registered)
        if actual[rel] != registered[rel]
    )
    if missing or extra or mismatched:
        details: list[str] = []
        if missing:
            details.append("registered-but-missing=" + ", ".join(missing))
        if extra:
            details.append("unregistered-extra=" + ", ".join(extra))
        if mismatched:
            details.append("hash-mismatch=" + ", ".join(mismatched))
        raise ManifestError(
            "target archive does not exactly match its v2 receipt: "
            + "; ".join(details)
        )


def _archive_record(
    receipt: dict[str, Any] | None,
    rel: str,
    sha256: str,
) -> dict[str, Any] | None:
    if receipt is None:
        return None
    for record in receipt.get("archive", {}).get("files", []):
        if record.get("path") == rel and record.get("sha256") == sha256:
            return record
    return None


def _constraint_id(agent: str, rel: str, sha256: str) -> str:
    raw = f"{agent}\0{rel}\0{sha256}".encode("utf-8")
    return "bf-" + hashlib.sha256(raw).hexdigest()[:20]


def _is_executable(rel: str) -> bool:
    normalized = unicodedata.normalize("NFC", rel.replace("\\", "/")).casefold()
    parts = Path(normalized).parts
    return (
        Path(normalized).suffix in {".py", ".sh", ".ps1", ".bat", ".cmd"}
        or "hooks" in parts
        or "scripts" in parts
    )


def _required_evidence(rel: str, level: str) -> str:
    if level == "hard" and _is_executable(rel):
        return "contract-smoke"
    return "text-review"


def _proposal_item(
    *,
    constraint_id: str,
    source_origin: str,
    source_path: str,
    source_sha: str,
    owner: str,
    level: str,
    classification: str,
    summary: str,
    parent_receipt: str | None = None,
) -> dict[str, Any]:
    not_applicable = level == "platform-detail"
    return {
        "constraint_id": constraint_id,
        "semantic": {
            "summary": summary,
            "classification": classification,
        },
        "constraint_level": level,
        "source": {
            "origin": source_origin,
            "path": source_path,
            "sha256": source_sha,
        },
        "target": {
            "action": "not-applicable" if not_applicable else "unresolved",
            "path": None,
            "base_sha256": None,
            "sha256": None,
            "content": None,
            "diff": "",
        },
        "source_owner": owner,
        "target_owner": None,
        "adapter": {
            "kind": "platform-detail" if not_applicable else "unresolved",
            "source": "inventory",
        },
        "approval": {
            "status": "not-required" if not_applicable else "pending",
            "approved_by": None,
        },
        "evidence": {
            "required_level": _required_evidence(source_path, level),
            "level": "text-review" if not_applicable else None,
            "status": "not-required" if not_applicable else "pending",
            "details": "current source template byte match" if not_applicable else "",
        },
        "status": "not-applicable" if not_applicable else "blocked",
        "parent_receipt": parent_receipt,
    }


def _freeze_expected_fields(item: dict[str, Any]) -> None:
    """Persist the mechanically detected security boundary for later approval."""
    target = item["target"]
    item["expected"] = {
        "source_owner": item["source_owner"],
        "target_owner": item["target_owner"],
        "constraint_level": item["constraint_level"],
        "semantic_classification": item["semantic"]["classification"],
        "target_action": target["action"],
        "target_path": target["path"],
        "target_base_sha256": target["base_sha256"],
    }


def build_proposal(
    plan: Plan,
    migration_id: str | None = None,
) -> dict[str, Any]:
    migration_id = migration_id or (
        f"{_timestamp()}-{plan.old_agent}-to-{plan.agent}-"
        f"{hashlib.sha256(os.urandom(16)).hexdigest()[:8]}"
    )
    source_template = _source_template_map(plan)
    items: list[dict[str, Any]] = []
    parents: set[str] = set()
    live_constraint_ids: set[str] = set()

    for rel, path in sorted(plan.source_files.items()):
        sha256 = _sha_file(path)
        template_path = source_template.get(rel)
        if template_path is not None and _sha_file(template_path) == sha256:
            items.append(
                _proposal_item(
                    constraint_id=_constraint_id(plan.old_agent, rel, sha256),
                    source_origin="live",
                    source_path=rel,
                    source_sha=sha256,
                    owner="template-managed",
                    level="platform-detail",
                    classification="platform-detail",
                    summary="Current source-platform template asset; no cross-platform copy.",
                )
            )
            continue
        receipt, record = _receipt_target_record(plan, rel, sha256)
        parent_id = receipt.get("migration_id") if receipt else None
        if parent_id:
            parents.add(parent_id)
        constraint_id = (
            record.get("constraint_id")
            if record and record.get("constraint_id")
            else _constraint_id(plan.old_agent, rel, sha256)
        )
        live_constraint_ids.add(constraint_id)
        items.append(
            _proposal_item(
                constraint_id=constraint_id,
                source_origin="live",
                source_path=rel,
                source_sha=sha256,
                owner=record.get("target_owner", "unknown-historical") if record else "unknown-historical",
                level=record.get("constraint_level", "hard") if record else "hard",
                classification=(
                    record.get("semantic", {}).get("classification", "unresolved")
                    if record
                    else "unresolved"
                ),
                summary=(
                    record.get("semantic", {}).get("summary", "")
                    if record
                    else ""
                ),
                parent_receipt=parent_id,
            )
        )

    archive_receipt = _archive_receipt(plan)
    if archive_receipt:
        parents.add(archive_receipt.get("migration_id", ""))
    for rel, path in sorted(plan.archive_files.items()):
        sha256 = _sha_file(path)
        record = _archive_record(archive_receipt, rel, sha256)
        if record is None:
            owner = "unknown-historical"
            level = "hard"
            classification = "unresolved"
            summary = ""
            constraint_id = _constraint_id(plan.agent, f"archive:{rel}", sha256)
        else:
            owner = record.get("source_owner", "unknown-historical")
            constraint_id = record.get("constraint_id") or _constraint_id(
                plan.agent,
                f"archive:{rel}",
                sha256,
            )
            level = record.get("constraint_level", "hard")
            classification = record.get("semantic", {}).get(
                "classification",
                "translatable",
            )
            summary = record.get("semantic", {}).get("summary", "")
            if owner == "template-managed":
                level = "platform-detail"
                classification = "platform-detail"
                summary = "Archived managed template asset is superseded by the current template."
            elif constraint_id in live_constraint_ids:
                level = "platform-detail"
                classification = "lineage-duplicate"
                summary = "Archived projection is superseded by the same live constraint lineage."
        item = _proposal_item(
            constraint_id=constraint_id,
            source_origin="target-archive",
            source_path=rel,
            source_sha=sha256,
            owner=owner,
            level=level,
            classification=classification,
            summary=summary,
            parent_receipt=archive_receipt.get("migration_id") if archive_receipt else None,
        )
        if record and owner == "user-owned" and level != "platform-detail":
            item["target"]["action"] = "replay-archive"
            item["target"]["path"] = rel
            item["target"]["sha256"] = sha256
            item["target"]["diff"] = _expected_diff(
                plan,
                rel,
                path.read_bytes(),
            )
            item["target_owner"] = "user-owned"
            item["adapter"] = {
                "kind": "provenance-replay",
                "source": archive_receipt.get("_receipt_path", "prior receipt"),
            }
            item["approval"] = {"status": "pending", "approved_by": None}
            item["evidence"]["status"] = "pending"
            item["status"] = "blocked"
        elif record and owner == "constraint-generated" and level != "platform-detail":
            item["target"]["action"] = "unresolved"
            item["adapter"] = {
                "kind": "unavailable",
                "source": "constraint-generated archive requires a registered adapter",
                "id": record.get("adapter", {}).get("id"),
                "version": record.get("adapter", {}).get("version"),
            }
        if item["target"]["path"]:
            item["target"]["base_sha256"] = _sha_bytes(
                _target_template_bytes(plan, item["target"]["path"])
            )
        _freeze_expected_fields(item)
        items.append(item)

    for item in items:
        if "expected" not in item:
            _freeze_expected_fields(item)

    return {
        "schema_version": SCHEMA_VERSION,
        "migration_id": migration_id,
        "created_at": _now(),
        "source_agent": plan.old_agent,
        "target_agent": plan.agent,
        "parent_migration_ids": sorted(parent for parent in parents if parent),
        "snapshots": dict(plan.snapshots),
        "items": items,
    }


def _target_template_bytes(plan: Plan, rel: str) -> bytes:
    for item in plan.template_items:
        if item.rel == rel:
            return item.src.read_bytes()
    return b""


def _text_diff(before: bytes, after: bytes, rel: str) -> str:
    try:
        before_text = before.decode("utf-8").replace("\r\n", "\n")
        after_text = after.decode("utf-8").replace("\r\n", "\n")
    except UnicodeDecodeError:
        return (
            f"binary {rel}: {_sha_bytes(before)} -> {_sha_bytes(after)}"
        )
    return "".join(
        difflib.unified_diff(
            before_text.splitlines(keepends=True),
            after_text.splitlines(keepends=True),
            fromfile=f"template/{rel}",
            tofile=f"target/{rel}",
        )
    )


def _expected_diff(plan: Plan, rel: str, after: bytes) -> str:
    return _text_diff(_target_template_bytes(plan, rel), after, rel)


def _manifest_bytes(item: dict[str, Any]) -> bytes:
    target = item.get("target", {})
    if target.get("content_base64") is not None:
        try:
            return base64.b64decode(target["content_base64"], validate=True)
        except Exception as exc:
            raise ManifestError(
                f"{item.get('constraint_id')}: invalid target.content_base64"
            ) from exc
    content = target.get("content")
    if not isinstance(content, str):
        raise ManifestError(
            f"{item.get('constraint_id')}: write requires target.content"
        )
    return content.encode("utf-8")


def _target_allowed(plan: Plan, rel: str) -> bool:
    spec = SPECS[plan.agent]
    return rel == spec.entry or rel.startswith(spec.config_dir + "/")


def _inventory_key(item: dict[str, Any]) -> tuple[str, str, str]:
    source = item.get("source", {})
    return (
        str(source.get("origin", "")),
        str(source.get("path", "")),
        str(source.get("sha256", "")),
    )


def _expected_inventory(plan: Plan) -> set[tuple[str, str, str]]:
    expected = {
        ("live", rel, _sha_file(path))
        for rel, path in plan.source_files.items()
    }
    expected.update(
        ("target-archive", rel, _sha_file(path))
        for rel, path in plan.archive_files.items()
    )
    return expected


def _require_string(data: dict[str, Any], key: str, label: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{label}.{key} must be a non-empty string")
    return value.strip()


def validate_manifest(
    plan: Plan,
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError(f"schema_version must be {SCHEMA_VERSION}")
    migration_id = _require_string(manifest, "migration_id", "manifest")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,127}", migration_id):
        raise ManifestError("manifest.migration_id is not path-safe")
    if manifest.get("source_agent") != plan.old_agent:
        raise ManifestError("manifest.source_agent does not match current live source")
    if manifest.get("target_agent") != plan.agent:
        raise ManifestError("manifest.target_agent does not match requested target")
    if manifest.get("snapshots") != plan.snapshots:
        raise ManifestError("manifest snapshots are stale")
    expected_proposal = build_proposal(plan, migration_id=migration_id)
    if manifest.get("parent_migration_ids", []) != expected_proposal["parent_migration_ids"]:
        raise ManifestError("manifest parent lineage is missing or stale")
    raw_items = manifest.get("items")
    if not isinstance(raw_items, list):
        raise ManifestError("manifest.items must be a list")
    if {_inventory_key(item) for item in raw_items if isinstance(item, dict)} != _expected_inventory(plan):
        raise ManifestError("manifest must cover the exact live and target-archive inventory")
    if len(raw_items) != len(_expected_inventory(plan)):
        raise ManifestError("manifest contains duplicate or non-object inventory items")
    expected_items = {
        _inventory_key(item): item
        for item in expected_proposal["items"]
    }

    target_paths: dict[str, str] = {}
    template_paths = {
        _windows_path_key(copy_item.rel): copy_item.rel
        for copy_item in plan.template_items
    }
    checked: list[dict[str, Any]] = []
    for item in raw_items:
        constraint_id = _require_string(item, "constraint_id", "item")
        expected_item = expected_items[_inventory_key(item)]
        if constraint_id != expected_item["constraint_id"]:
            raise ManifestError(
                f"{constraint_id}: constraint_id does not match persisted lineage"
            )
        if item.get("expected") != expected_item.get("expected"):
            raise ManifestError(
                f"{constraint_id}: mechanically detected proposal fields were modified"
            )
        level = item.get("constraint_level")
        if level not in {"hard", "soft", "platform-detail"}:
            raise ManifestError(f"{constraint_id}: invalid constraint_level")
        expected_level = expected_item["constraint_level"]
        if level != expected_level:
            raise ManifestError(
                f"{constraint_id}: constraint_level cannot be downgraded or rewritten"
            )
        source_owner = item.get("source_owner")
        if source_owner not in OWNERS:
            raise ManifestError(f"{constraint_id}: invalid source_owner")
        expected_owner = expected_item["source_owner"]
        if source_owner != expected_owner:
            raise ManifestError(
                f"{constraint_id}: source_owner does not match proven provenance"
            )
        target_owner = item.get("target_owner")
        semantic = item.get("semantic")
        if not isinstance(semantic, dict):
            raise ManifestError(f"{constraint_id}: semantic object is required")
        expected_classification = expected_item["semantic"]["classification"]
        action = item.get("target", {}).get("action")
        if action not in {
            "not-applicable",
            "unresolved",
            "write",
            "replay-archive",
            "keep-template",
        }:
            raise ManifestError(f"{constraint_id}: unsupported target action")
        if expected_owner == "unknown-historical":
            lineage_duplicate = (
                expected_level == "platform-detail"
                and expected_classification == "lineage-duplicate"
            )
            if lineage_duplicate:
                if (
                    action != expected_item["target"]["action"]
                    or semantic.get("classification") != expected_classification
                ):
                    raise ManifestError(
                        f"{constraint_id}: archived lineage duplicate fields changed"
                    )
            elif action != "write":
                raise ManifestError(
                    f"{constraint_id}: unknown ownership requires an approved "
                    "target-native write; archive replay is forbidden"
                )
            elif semantic.get("classification") != "translatable":
                raise ManifestError(
                    f"{constraint_id}: unresolved semantics may only advance to translatable"
                )
        else:
            if semantic.get("classification") != expected_classification:
                raise ManifestError(
                    f"{constraint_id}: semantic classification does not match provenance"
                )
            expected_action = expected_item["target"]["action"]
            generated_lineage_duplicate = (
                expected_level == "platform-detail"
                and expected_classification == "lineage-duplicate"
                and expected_action == "not-applicable"
            )
            if (
                item["source"]["origin"] == "target-archive"
                and expected_owner == "constraint-generated"
                and not generated_lineage_duplicate
            ):
                raise ManifestError(
                    f"{constraint_id}: constraint-generated archive bytes cannot be "
                    "replayed; no registered adapter is available"
                )
            if expected_action == "unresolved":
                if action != "write":
                    raise ManifestError(
                        f"{constraint_id}: unresolved target requires a target-native write"
                    )
            elif action != expected_action:
                raise ManifestError(
                    f"{constraint_id}: target action does not match the proposal"
                )
            if (
                expected_action != "unresolved"
                and item["target"].get("path") != expected_item["target"].get("path")
            ):
                raise ManifestError(
                    f"{constraint_id}: target path does not match the proposal"
                )
        if level == "hard" and (
            semantic.get("classification") in {None, "", "unresolved"}
            or not str(semantic.get("summary", "")).strip()
        ):
            raise ManifestError(f"{constraint_id}: hard constraint semantics are unresolved")
        if level == "hard" and action in {"not-applicable", "keep-template"}:
            raise ManifestError(
                f"{constraint_id}: hard constraint requires a target-native projection"
            )

        approval = item.get("approval", {})
        approval_required = level != "platform-detail" or action not in {
            "not-applicable",
            "keep-template",
        }
        if approval_required and (
            approval.get("status") != "approved"
            or not str(approval.get("approved_by", "")).strip()
        ):
            raise ManifestError(f"{constraint_id}: item is not explicitly approved")

        source = item["source"]
        source_path = _safe_rel(str(source["path"]))
        evidence = item.get("evidence")
        if not isinstance(evidence, dict):
            raise ManifestError(f"{constraint_id}: evidence object is required")
        default_required = _required_evidence(source_path, level)
        target_path_for_evidence = item.get("target", {}).get("path")
        if (
            level == "hard"
            and action in {"write", "replay-archive"}
            and isinstance(target_path_for_evidence, str)
            and _is_executable(target_path_for_evidence)
        ):
            default_required = "contract-smoke"
        requested = evidence.get("required_level") or default_required
        if requested not in EVIDENCE_RANK:
            raise ManifestError(f"{constraint_id}: invalid required evidence level")
        required_rank = max(
            EVIDENCE_RANK[default_required],
            EVIDENCE_RANK[requested],
        )
        actual_level = evidence.get("level")
        if actual_level not in EVIDENCE_RANK:
            if level == "platform-detail" and evidence.get("status") == "not-required":
                actual_level = "text-review"
            else:
                raise ManifestError(f"{constraint_id}: evidence level is missing")
        if EVIDENCE_RANK[actual_level] < required_rank:
            raise ManifestError(f"{constraint_id}: evidence level is below the minimum")
        if actual_level in {"contract-smoke", "native-host"}:
            command = evidence.get("command")
            if command is not None:
                raise ManifestError(
                    f"{constraint_id}: manifest evidence.command is forbidden; "
                    "untrusted external commands are never executed"
                )
            raise ManifestError(
                f"{constraint_id}: {actual_level} evidence is sandbox-unavailable; "
                "executable hard constraints cannot migrate on this host"
            )
        elif approval_required and evidence.get("status") != "passed":
            raise ManifestError(f"{constraint_id}: review evidence is not passed")

        if action in {"write", "replay-archive"}:
            target = item["target"]
            target_rel = _safe_rel(str(target.get("path", "")))
            if not _target_allowed(plan, target_rel):
                raise ManifestError(
                    f"{constraint_id}: target path is outside the target agent surface"
                )
            target_key = _windows_path_key(target_rel)
            template_rel = template_paths.get(target_key)
            if template_rel is not None and template_rel != target_rel:
                raise ManifestError(
                    "Windows path collision with target template: "
                    f"{template_rel} and {target_rel}"
                )
            if target_key in target_paths:
                raise ManifestError(
                    "Windows path collision between target projections: "
                    f"{target_paths[target_key]} and {target_rel}"
                )
            target_paths[target_key] = target_rel
            if action == "write":
                if target_owner != "constraint-generated":
                    raise ManifestError(
                        f"{constraint_id}: translated writes require "
                        "target_owner=constraint-generated"
                    )
                content = _manifest_bytes(item)
                source_file = (
                    plan.source_files.get(source_path)
                    if source.get("origin") == "live"
                    else plan.archive_files.get(source_path)
                )
                if (
                    source.get("origin") == "live"
                    and source_file is not None
                    and content == source_file.read_bytes()
                ):
                    raise ManifestError(
                        f"{constraint_id}: direct cross-platform byte copy is forbidden"
                    )
            else:
                if target_owner != "user-owned":
                    raise ManifestError(
                        f"{constraint_id}: archive replay requires target_owner=user-owned"
                    )
                if source.get("origin") != "target-archive":
                    raise ManifestError(
                        f"{constraint_id}: replay-archive requires target-archive source"
                    )
                if source_owner != "user-owned":
                    raise ManifestError(
                        f"{constraint_id}: archive replay lacks proven ownership"
                    )
                content = plan.archive_files[source_path].read_bytes()
            if target.get("sha256") != _sha_bytes(content):
                raise ManifestError(f"{constraint_id}: target hash does not match content")
            expected_base_sha = _sha_bytes(_target_template_bytes(plan, target_rel))
            if target.get("base_sha256") != expected_base_sha:
                raise ManifestError(
                    f"{constraint_id}: target base hash is missing or stale"
                )
            if target.get("diff") != _expected_diff(plan, target_rel, content):
                raise ManifestError(f"{constraint_id}: target diff is missing or stale")
            adapter = item.get("adapter", {})
            if (
                adapter.get("kind") in {None, "", "unresolved", "platform-detail"}
                or not str(adapter.get("source", "")).strip()
            ):
                raise ManifestError(f"{constraint_id}: adapter provenance is incomplete")
        elif target_owner is not None:
            raise ManifestError(
                f"{constraint_id}: non-writing item must not declare target_owner"
            )
        checked.append(item)
    return checked


def _copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _tree_state(root: Path) -> dict[str, str]:
    state: dict[str, str] = {}
    if not _lexists(root):
        return state
    _assert_no_links(root, "staged target")
    for path in sorted(root.rglob("*")):
        rel = _posix(path.relative_to(root))
        if path.is_dir():
            state[rel] = "directory"
        elif path.is_file():
            state[rel] = "file:" + _sha_file(path)
        else:
            raise ManifestError(f"unsupported staged target path type: {rel}")
    return state


def _agent_tree_state(root: Path, spec: AgentSpec) -> dict[str, str]:
    state: dict[str, str] = {}
    for rel in (spec.entry, spec.config_dir):
        path = root / rel
        if not _lexists(path):
            continue
        _assert_no_links(path, "agent target surface")
        if path.is_file():
            state[rel] = "file:" + _sha_file(path)
            continue
        state[rel] = "directory"
        for child in sorted(path.rglob("*")):
            child_rel = _posix(child.relative_to(root))
            if child.is_dir():
                state[child_rel] = "directory"
            elif child.is_file():
                state[child_rel] = "file:" + _sha_file(child)
            else:
                raise ManifestError(f"unsupported target path type: {child_rel}")
    return state


def _assert_tree_exact(
    expected: dict[str, str],
    root: Path,
    label: str,
    spec: AgentSpec | None = None,
) -> None:
    actual = _agent_tree_state(root, spec) if spec else _tree_state(root)
    if actual == expected:
        return
    added = sorted(set(actual) - set(expected))
    removed = sorted(set(expected) - set(actual))
    changed = sorted(
        rel
        for rel in set(actual) & set(expected)
        if actual[rel] != expected[rel]
    )
    details: list[str] = []
    if added:
        details.append("unregistered=" + ", ".join(added))
    if removed:
        details.append("missing=" + ", ".join(removed))
    if changed:
        details.append("hash/type drift=" + ", ".join(changed))
    raise ManifestError(f"{label} differs from approved staged target: " + "; ".join(details))


def _copy_agent_snapshot(
    spec: AgentSpec,
    source_root: Path,
    snapshot_root: Path,
) -> None:
    for rel in (spec.entry, spec.config_dir):
        source = source_root / rel
        if not _lexists(source):
            continue
        _assert_no_links(source, "source live backup")
        target = snapshot_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(
                source,
                target,
                symlinks=True,
            )
        else:
            shutil.copy2(source, target)


def _restore_agent_snapshot(
    spec: AgentSpec,
    project_root: Path,
    snapshot_root: Path,
) -> None:
    for path in _agent_paths(spec, project_root):
        _remove_path(path)
    _copy_agent_snapshot(spec, snapshot_root, project_root)


def _remove_path(path: Path) -> None:
    if not _lexists(path):
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def adapt_settings(path: Path, python_command: str | None) -> None:
    if not path.is_file() or not python_command:
        return
    original = path.read_text(encoding="utf-8-sig")
    try:
        data = json.loads(original)
    except Exception:
        tokens = r"(?:\.venv/Scripts/python\.exe|\.venv/bin/python|python3|python)"
        text = re.sub(
            rf'("command"\s*:\s*")({tokens})(?=\s)',
            rf"\1{python_command}",
            original,
        )
        path.write_text(text, encoding="utf-8")
        return

    commands = (".venv/Scripts/python.exe", ".venv/bin/python", "python3", "python")

    def adapt(value: Any) -> Any:
        if isinstance(value, str):
            for command in commands:
                if value == command or value.startswith(command + " "):
                    return python_command + value[len(command):]
            return value
        if isinstance(value, list):
            return [adapt(item) for item in value]
        if isinstance(value, dict):
            return {key: adapt(item) for key, item in value.items()}
        return value

    path.write_text(
        json.dumps(adapt(data), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _stage_target(
    plan: Plan,
    items: list[dict[str, Any]],
    stage_root: Path,
) -> None:
    if stage_root.exists():
        shutil.rmtree(stage_root)
    stage_root.mkdir(parents=True)
    for copy_item in plan.template_items:
        _copy_file(copy_item.src, stage_root / copy_item.rel)
    settings = stage_root / SPECS[plan.agent].config_dir / "settings.json"
    adapt_settings(settings, plan.python_command)
    for item in items:
        action = item["target"]["action"]
        if action not in {"write", "replay-archive"}:
            continue
        target = stage_root / _safe_rel(item["target"]["path"])
        if action == "write":
            content = _manifest_bytes(item)
        else:
            content = plan.archive_files[_safe_rel(item["source"]["path"])].read_bytes()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def _validate_target_root(plan: Plan, root: Path) -> list[str]:
    spec = SPECS[plan.agent]
    problems: list[str] = []
    required_files = [spec.entry, *[f"{spec.config_dir}/{name}" for name in spec.config_files]]
    required_dirs = [f"{spec.config_dir}/{name}" for name in spec.config_dirs]
    for rel in required_files:
        if not (root / rel).is_file():
            problems.append(f"missing target file: {rel}")
    for rel in required_dirs:
        if not (root / rel).is_dir():
            problems.append(f"missing target directory: {rel}")
    other = SPECS[plan.old_agent]
    for rel in (other.entry, other.config_dir):
        if (root / rel).exists():
            problems.append(f"source-platform residue in staged target: {rel}")
    return problems


def _run_evidence(
    plan: Plan,
    items: list[dict[str, Any]],
    stage_root: Path,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in items:
        evidence = item["evidence"]
        level = evidence.get("level")
        result = {
            "constraint_id": item["constraint_id"],
            "source": {
                "origin": item["source"]["origin"],
                "path": item["source"]["path"],
                "sha256": item["source"]["sha256"],
            },
            "required_level": evidence.get("required_level"),
            "level": level,
            "status": evidence.get("status"),
            "details": evidence.get("details", ""),
        }
        if level in {"contract-smoke", "native-host"} or "command" in evidence:
            raise ManifestError(
                f"{item['constraint_id']}: executable evidence is sandbox-unavailable"
            )
        results.append(result)
    return results


def _recheck_inputs(plan: Plan) -> None:
    old_paths = _existing_agent_paths(SPECS[plan.old_agent], plan.project_root)
    for path in old_paths:
        _assert_project_local(path, plan.project_root, "source live recheck")
        _assert_no_links(path, "source live recheck")
    for item in plan.template_items:
        _assert_no_links(item.src, "target template recheck")
    if plan.target_archive is not None:
        _assert_project_local(plan.target_archive, plan.project_root, "archive recheck")
        _assert_no_links(plan.target_archive, "archive recheck")
    current = {
        "source": _state_digest(
            _agent_tree_state(plan.project_root, SPECS[plan.old_agent])
        ),
        "target_template": _snapshot(
            {item.rel: item.src for item in plan.template_items}
        ),
        "target_prestate": _path_state(
            _agent_paths(SPECS[plan.agent], plan.project_root),
            plan.project_root,
        ),
        "target_archive": (
            _path_state([plan.target_archive], plan.project_root)
            if plan.target_archive is not None
            else _snapshot({})
        ),
    }
    if current != plan.snapshots:
        changed = [
            key
            for key in sorted(current)
            if current[key] != plan.snapshots.get(key)
        ]
        raise ManifestError("input hash drift before apply: " + ", ".join(changed))


def _fault(label: str) -> None:
    if os.environ.get("BRIDGEFORGE_SWITCH_FAIL_AT") == label:
        raise RuntimeError(f"injected switch failure at {label}")


def _move_agent_paths(
    spec: AgentSpec,
    source_root: Path,
    target_root: Path,
    *,
    fault_after_first: str | None = None,
) -> None:
    for index, rel in enumerate((spec.entry, spec.config_dir)):
        source = source_root / rel
        if not _lexists(source):
            continue
        target = target_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        if index == 0 and fault_after_first:
            _fault(fault_after_first)


def _inventory_records(
    files: dict[str, Path],
    item_by_source: dict[tuple[str, str], dict[str, Any]],
    origin: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for rel, path in sorted(files.items()):
        item = item_by_source.get((origin, rel), {})
        records.append(
            {
                "path": rel,
                "sha256": _sha_file(path),
                "source_owner": item.get("source_owner", "unknown-historical"),
                "constraint_id": item.get("constraint_id"),
                "constraint_level": item.get("constraint_level"),
                "semantic": item.get("semantic", {}),
                "adapter": item.get("adapter", {}),
            }
        )
    return records


def _target_records(
    plan: Plan,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    spec = SPECS[plan.agent]
    files = _inventory_paths(_agent_paths(spec, plan.project_root), plan.project_root)
    projections = {
        item["target"]["path"]: item
        for item in items
        if item["target"]["action"] in {"write", "replay-archive"}
    }
    records: list[dict[str, Any]] = []
    for rel, path in sorted(files.items()):
        item = projections.get(rel)
        records.append(
            {
                "path": rel,
                "sha256": _sha_file(path),
                "target_owner": item.get("target_owner", "template-managed") if item else "template-managed",
                "constraint_id": item.get("constraint_id") if item else None,
                "constraint_level": item.get("constraint_level") if item else "platform-detail",
                "semantic": item.get("semantic", {}) if item else {
                    "classification": "platform-detail",
                    "summary": "Current target template baseline.",
                },
                "adapter": item.get("adapter", {}) if item else {
                    "kind": "template",
                    "source": "current target template",
                },
            }
        )
    return records


def _write_receipt(path: Path, receipt: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def apply_manifest(
    plan: Plan,
    manifest: dict[str, Any],
) -> Path:
    items = validate_manifest(plan, manifest)
    migration_id = manifest["migration_id"]
    migration_dir = plan.project_root / MIGRATION_ROOT / migration_id
    receipt_path = migration_dir / "receipt.json"
    _assert_project_local(migration_dir, plan.project_root, "migration directory")
    _assert_project_local(receipt_path, plan.project_root, "migration receipt")
    if _lexists(receipt_path):
        raise ManifestError(f"migration receipt already exists: {_rel(receipt_path, plan.project_root)}")
    archive_final = (
        plan.project_root
        / ARCHIVE_ROOT
        / plan.old_agent
        / f"{_timestamp()}-{migration_id}"
    )
    _assert_project_local(archive_final, plan.project_root, "archive destination")
    if _lexists(archive_final):
        raise ManifestError(
            f"archive destination already exists: {_rel(archive_final, plan.project_root)}"
        )
    source_spec = SPECS[plan.old_agent]
    target_spec = SPECS[plan.agent]
    evidence_results: list[dict[str, Any]] = []
    target_enable_started = False
    archive_finalized = False
    archive_owned = False
    archive_agent_root_owned = False
    source_backup_complete = False
    preserve_transaction_state = False
    with tempfile.TemporaryDirectory(prefix="bridgeforge-switch-") as temporary:
        temporary_root = Path(temporary)
        stage_root = temporary_root / "stage-target"
        source_backup = temporary_root / "source-backup"
        detached_root = migration_dir / ".detached-old"
        try:
            _recheck_inputs(plan)
            _copy_agent_snapshot(source_spec, plan.project_root, source_backup)
            source_backup_complete = True
            if _agent_tree_state(source_backup, source_spec) != plan.source_state:
                raise ManifestError(
                    "source backup does not match the approved source snapshot"
                )
            if _agent_tree_state(plan.project_root, source_spec) != plan.source_state:
                raise ManifestError(
                    "source live changed while its rollback snapshot was copied"
                )
            _stage_target(plan, items, stage_root)
            stage_problems = _validate_target_root(plan, stage_root)
            if stage_problems:
                raise ManifestError("; ".join(stage_problems))
            approved_stage_state = _tree_state(stage_root)
            evidence_results = _run_evidence(plan, items, stage_root)
            _assert_tree_exact(
                approved_stage_state,
                stage_root,
                "evidence output",
            )
            _recheck_inputs(plan)
            _assert_tree_exact(
                approved_stage_state,
                stage_root,
                "pre-commit staged target",
            )
            if plan.target_conflicts:
                raise ManifestError("target live paths appeared before commit")
            if _lexists(archive_final):
                raise ManifestError(
                    "archive destination appeared before commit: "
                    + _rel(archive_final, plan.project_root)
                )

            migration_dir.mkdir(parents=True, exist_ok=True)
            detached_root.mkdir(parents=True, exist_ok=True)
            _move_agent_paths(source_spec, plan.project_root, detached_root)
            if _agent_tree_state(detached_root, source_spec) != plan.source_state:
                raise ManifestError(
                    "detached source differs from the approved source snapshot"
                )
            _fault("after-old-detach")
            target_enable_started = True
            _move_agent_paths(
                target_spec,
                stage_root,
                plan.project_root,
                fault_after_first="after-target-entry-enable",
            )
            _fault("after-target-enable")
            live_problems = _validate_target_root(plan, plan.project_root)
            if live_problems:
                raise ManifestError("; ".join(live_problems))
            _assert_tree_exact(
                approved_stage_state,
                plan.project_root,
                "enabled live target",
                target_spec,
            )

            if any(
                _lexists(detached_root / rel)
                for rel in (source_spec.entry, source_spec.config_dir)
            ):
                archive_agent_root = archive_final.parent
                archive_agent_root_preexisting = _lexists(archive_agent_root)
                archive_agent_root.mkdir(parents=True, exist_ok=True)
                archive_agent_root_owned = not archive_agent_root_preexisting
                _assert_project_local(
                    archive_agent_root,
                    plan.project_root,
                    "archive parent",
                )
                _assert_no_links(archive_agent_root, "archive parent")
                archive_final.mkdir()
                archive_owned = True
                _move_agent_paths(source_spec, detached_root, archive_final)
                if _tree_state(archive_final) != plan.source_state:
                    raise ManifestError(
                        "transaction-owned archive differs from the approved source snapshot"
                    )
                archive_finalized = True
            _fault("after-archive-finalize")

            item_by_source = {
                (item["source"]["origin"], item["source"]["path"]): item
                for item in items
            }
            archived_files = _archive_inventory(archive_final if archive_finalized else None)
            archive_records = _inventory_records(
                archived_files,
                item_by_source,
                "live",
            )
            evidence_by_id = {
                (
                    result["constraint_id"],
                    result["source"]["origin"],
                    result["source"]["path"],
                ): result
                for result in evidence_results
            }
            receipt_items = json.loads(json.dumps(items, ensure_ascii=False))
            for item in receipt_items:
                result = evidence_by_id.get(
                    (
                        item["constraint_id"],
                        item["source"]["origin"],
                        item["source"]["path"],
                    )
                )
                if result is not None:
                    item["evidence"] = result
                item["status"] = (
                    "not-applicable"
                    if item["target"]["action"] in {"not-applicable", "keep-template"}
                    else "applied"
                )
            receipt = {
                "schema_version": SCHEMA_VERSION,
                "migration_id": migration_id,
                "status": "success",
                "started_from_manifest_created_at": manifest.get("created_at"),
                "completed_at": _now(),
                "source_agent": plan.old_agent,
                "target_agent": plan.agent,
                "parent_migration_ids": manifest.get("parent_migration_ids", []),
                "snapshots": dict(plan.snapshots),
                "manifest_sha256": _sha_bytes(
                    json.dumps(
                        manifest,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ),
                "items": receipt_items,
                "evidence": evidence_results,
                "archive": {
                    "path": (
                        _rel(archive_final, plan.project_root)
                        if archive_finalized
                        else None
                    ),
                    "files": archive_records,
                },
                "target": {
                    "files": _target_records(plan, items),
                },
            }
            _write_receipt(receipt_path, receipt)
            _fault("after-receipt")
            return receipt_path
        except Exception:
            if _lexists(receipt_path):
                receipt_path.unlink()
            if target_enable_started:
                for path in _agent_paths(target_spec, plan.project_root):
                    _remove_path(path)
            backup_valid = (
                source_backup_complete
                and _agent_tree_state(source_backup, source_spec) == plan.source_state
            )
            source_recovered = False
            if backup_valid:
                _restore_agent_snapshot(
                    source_spec,
                    plan.project_root,
                    source_backup,
                )
                source_recovered = (
                    _agent_tree_state(plan.project_root, source_spec)
                    == plan.source_state
                )
            if not source_recovered:
                for recovery_root in (archive_final, detached_root):
                    if _lexists(recovery_root):
                        _move_agent_paths(
                            source_spec,
                            recovery_root,
                            plan.project_root,
                        )
                source_recovered = (
                    _agent_tree_state(plan.project_root, source_spec)
                    == plan.source_state
                )
            if not source_recovered:
                preserve_transaction_state = True
                raise RuntimeError(
                    "source recovery integrity failure: no approved snapshot remains"
                )
            if archive_owned and _lexists(archive_final):
                shutil.rmtree(archive_final)
            archive_agent_root = archive_final.parent
            if (
                archive_agent_root_owned
                and archive_agent_root.exists()
                and not any(archive_agent_root.iterdir())
            ):
                archive_agent_root.rmdir()
            raise
        finally:
            if detached_root.exists() and not preserve_transaction_state:
                shutil.rmtree(detached_root)
            if migration_dir.exists() and not any(migration_dir.iterdir()):
                migration_dir.rmdir()


def _print_proposal(plan: Plan, proposal: dict[str, Any]) -> None:
    unresolved = [
        item
        for item in proposal["items"]
        if item["status"] == "blocked"
    ]
    print(f"BridgeForge semantic switch proposal: {plan.old_agent} -> {plan.agent}")
    print(f"Migration ID: {proposal['migration_id']}")
    print(f"Source assets: {len(plan.source_files)}")
    print(f"Target archive assets: {len(plan.archive_files)}")
    print(f"Blocked items requiring semantic approval: {len(unresolved)}")
    if plan.target_archive and _archive_receipt(plan) is None:
        print("Legacy target archive provenance: missing; every archive item is fail-closed.")
    print("BEGIN_BRIDGEFORGE_MIGRATION_MANIFEST")
    print(json.dumps(proposal, ensure_ascii=False, indent=2))
    print("END_BRIDGEFORGE_MIGRATION_MANIFEST")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Switch BridgeForge project skeleton through an approved semantic manifest."
    )
    parser.add_argument("agent", choices=AGENTS, help="target agent skeleton")
    parser.add_argument(
        "--manifest",
        help="approved semantic migration manifest JSON",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="inventory and validate without changing project files",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="project root to switch (default: current directory)",
    )
    parser.add_argument(
        "--template-root",
        help="BridgeForge repository root containing templates/claude and templates/codex",
    )
    return parser.parse_args(argv)


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ManifestError(f"cannot read manifest {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError("manifest root must be a JSON object")
    return data


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_root).resolve()
    script_path = Path(__file__).resolve()
    if looks_like_bridgeforge_source(project_root):
        raise SystemExit("ERROR: refusing to switch the BridgeForge source repository itself.")
    template_root = find_template_root(project_root, script_path, args.template_root)
    if project_root == template_root:
        raise SystemExit("ERROR: refusing to switch the BridgeForge source repository itself.")

    try:
        plan = build_plan(args.agent, project_root, template_root)
    except ManifestError as exc:
        print(f"ERROR: semantic migration blocked: {exc}", file=sys.stderr)
        print("No live files were changed.", file=sys.stderr)
        return 2
    if plan.already_target:
        print("Already target agent: switch is a no-op; use normal /bridgeforge maintenance.")
        return 0
    if plan.target_conflicts:
        print(
            "ERROR: target live paths already exist; semantic switch requires an absent target surface.",
            file=sys.stderr,
        )
        for path in plan.target_conflicts:
            print(f"  - {_rel(path, project_root)}", file=sys.stderr)
        print("No live files were changed.", file=sys.stderr)
        return 2

    if args.manifest:
        try:
            manifest = _load_manifest(Path(args.manifest).resolve())
            validate_manifest(plan, manifest)
            if args.dry_run:
                print(
                    f"Manifest validated: {manifest['migration_id']} "
                    f"({plan.old_agent} -> {plan.agent})"
                )
                print("Dry-run: no files were changed.")
                return 0
            receipt = apply_manifest(plan, manifest)
        except ManifestError as exc:
            print(f"ERROR: semantic migration blocked: {exc}", file=sys.stderr)
            print("Old live and target pre-state were preserved.", file=sys.stderr)
            return 2
        except Exception as exc:
            print(f"ERROR: semantic migration failed and was rolled back: {exc}", file=sys.stderr)
            print("Old live and target pre-state were restored.", file=sys.stderr)
            return 1
        print(f"Switch completed: {args.agent}")
        print(f"Receipt: {_rel(receipt, project_root)}")
        print("Validation passed.")
        return 0

    proposal = build_proposal(plan)
    if not plan.source_files and not plan.archive_files:
        proposal["items"] = []
        if args.dry_run:
            _print_proposal(plan, proposal)
            return 0
        try:
            receipt = apply_manifest(plan, proposal)
        except Exception as exc:
            print(f"ERROR: target install failed and was rolled back: {exc}", file=sys.stderr)
            return 1
        print(f"Target installed: {args.agent}")
        print(f"Receipt: {_rel(receipt, project_root)}")
        print("Validation passed.")
        return 0

    _print_proposal(plan, proposal)
    print(
        "ERROR: semantic switch requires a user-reviewed manifest passed with --manifest.",
        file=sys.stderr,
    )
    print("No live files were changed.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
