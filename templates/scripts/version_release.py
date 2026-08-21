#!/usr/bin/env python3
"""Plan and apply deterministic repository version releases for git-sync."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from current_baseline import (  # noqa: E402
    BaselineError,
    detect_repository_role,
    load_contract,
    ownership_projection,
    verify_current_baseline,
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


def _head_payload(repo: Path, relative: str) -> bytes | None:
    try:
        result = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={repo.resolve().as_posix()}",
                "show",
                f"HEAD:{relative}",
            ],
            cwd=repo,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReleaseError(f"cannot read HEAD ownership payload: {relative}: {exc}") from exc
    return result.stdout if result.returncode == 0 else None


def _verify_prospective_factory_baseline(
    repo: Path,
    contract_path: Path,
    prospective_version: str,
) -> None:
    contract = load_contract(contract_path)
    contract["release_version"] = prospective_version
    with tempfile.TemporaryDirectory() as raw:
        prospective = Path(raw) / "managed-skeleton.json"
        prospective.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        verify_current_baseline(
            repo,
            expected_version=prospective_version,
            contract_path=prospective,
            prospective_version=prospective_version,
        )

def evaluate_release_transition(
    repo: Path,
    *,
    changed_paths: set[str] | None = None,
    prospective_version: str | None = None,
) -> tuple[str, set[str]]:
    """Evaluate the live or prospective current-only ownership state."""
    paths = (
        collect_changed_paths(repo)
        if changed_paths is None
        else {item.replace("\\", "/") for item in changed_paths}
    )
    role = detect_repository_role(repo)
    if role.kind == "ambiguous":
        raise TransitionBlocked([{
            "asset_id": "repository.role",
            "target": "bridgeforge-codex-manifest.json",
            "reason": role.reason,
        }])
    contract_path = repo / ".codex" / "managed-skeleton.json"
    if contract_path.is_file():
        try:
            if role.kind == "factory" and prospective_version is not None:
                _verify_prospective_factory_baseline(
                    repo,
                    contract_path,
                    prospective_version,
                )
            else:
                verify_current_baseline(repo)
        except (BaselineError, OSError, UnicodeDecodeError) as exc:
            raise TransitionBlocked([{
                "asset_id": "contract.current-baseline",
                "target": ".codex/managed-skeleton.json",
                "reason": str(exc),
            }]) from exc
    elif role.kind != "factory":
        raise TransitionBlocked([{
            "asset_id": "contract.current-baseline",
            "target": ".codex/managed-skeleton.json",
            "reason": "current-only baseline is missing",
        }])
    if role.kind == "factory":
        return "factory", paths
    try:
        contract = load_contract(contract_path)
    except (BaselineError, OSError, UnicodeDecodeError, ValueError) as exc:
        raise ReleaseError(f"cannot read current-only baseline: {exc}") from exc
    assets = {
        str(asset["target"]).replace("\\", "/"): asset
        for asset in contract["assets"]
        if isinstance(asset, dict) and isinstance(asset.get("target"), str)
    }
    relevant = paths - AUTO_EXCLUDED_PATHS
    public_changed = False
    project_changed = False
    for relative in sorted(relevant):
        asset = assets.get(relative)
        if asset is None:
            project_changed = True
            continue
        target = repo / Path(relative)
        current = target.read_bytes() if target.is_file() else b""
        before = _head_payload(repo, relative)
        if before is None:
            if asset.get("strategy") == "whole" and not asset.get("agents_zones") and not asset.get("managed_blocks"):
                public_changed = True
            elif asset.get("strategy") == "seed":
                project_changed = True
            else:
                project_changed = True
            continue
        try:
            old_projection = ownership_projection(asset, before, repo)
            new_projection = ownership_projection(asset, current, repo)
        except BaselineError as exc:
            raise TransitionBlocked([{
                "asset_id": str(asset.get("id", relative)),
                "target": relative,
                "reason": str(exc),
            }]) from exc
        public_changed = public_changed or (
            old_projection.public_sha256 != new_projection.public_sha256
        )
        project_changed = project_changed or (
            old_projection.project_sha256 != new_projection.project_sha256
        )
    classification = (
        "mixed"
        if public_changed and project_changed
        else "project-only" if project_changed or not public_changed else "skeleton-only"
    )
    return classification, paths

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
    data = _load_json_object(path, "JSON manifest")
    version = data.get("version")
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


def _load_json_object(path: Path, label: str) -> dict[str, object]:
    try:
        data = json.loads(
            path.read_text(encoding="utf-8-sig"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError(f"invalid {label} {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ReleaseError(f"invalid {label} {path}: top level must be an object")
    return data

def _candidate_manifests(repo: Path) -> list[Path]:
    config_path = repo / ".bridgeforge-version.json"
    if config_path.is_file():
        config = _load_json_object(config_path, "version sync config")
        manifests = config.get("manifests")
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
    data = _load_json_object(path, "JSON manifest")
    if not isinstance(data.get("version"), str):
        raise ReleaseError(f"missing top-level version in {path}")
    data["version"] = new
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

def _render_package_lock(path: Path, old: str, new: str) -> bytes:
    data = _load_json_object(path, "package-lock")
    if data.get("lockfileVersion") not in (2, 3):
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
) -> ReleasePlan | None:
    info = parse_commit_message(message)
    role = detect_repository_role(repo)
    factory_old_version: str | None = None
    factory_new_version: str | None = None
    if role.kind == "factory":
        factory_version = repo / "VERSION"
        if not factory_version.is_file():
            raise ReleaseError("factory root VERSION is missing")
        factory_old_version = factory_version.read_text(
            encoding="utf-8-sig"
        ).strip()
        parse_semver(factory_old_version)
        factory_new_version = bump_semver(factory_old_version, info.level)
    classification = evaluate_release_transition(
        repo,
        changed_paths=changed_paths,
        prospective_version=factory_new_version,
    )[0]
    if classification == "skeleton-only":
        return None

    version_path = repo / "VERSION"
    native = _discover_native_targets(repo)
    writes: dict[Path, bytes] = {}
    if factory_old_version is not None:
        old_version = factory_old_version
    elif version_path.is_file():
        old_version = version_path.read_text(encoding="utf-8-sig").strip()
        parse_semver(old_version)
    else:
        if not native:
            raise ReleaseError("root VERSION is missing and no unique supported native version exists")
        values = {value for _path, value, _keys, _format in native}
        if len(values) != 1:
            raise ReleaseError("root VERSION is missing and native version candidates conflict")
        old_version = next(iter(values))
    new_version = factory_new_version or bump_semver(old_version, info.level)
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
