#!/usr/bin/env python3
"""Plan and apply the one-time BridgeForge to bridgeforge-codex user migration.

Only ledger/hash-proven assets are retired.  The plan is fingerprinted and
rebuilt immediately before apply.  Every move is reversible until the new
ledger has been written and verified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


LEGACY_CODEX_LEDGER = ".codex/bridgeforge-managed.json"
CURRENT_CODEX_LEDGER = ".codex/bridgeforge-codex-managed.json"
LEGACY_CLAUDE_LEDGER = ".claude/bridgeforge-managed.json"
LEGACY_HOME = ".bridgeforge"
CURRENT_HOME = ".bridgeforge-codex"
CURRENT_SKILL = "bridgeforge-codex"
LEGACY_SKILL = "bridgeforge"
LEGACY_REMOTE = "https://github.com/freakybridge/BridgeForge.git"
CURRENT_REMOTE = "https://github.com/freakybridge/BridgeForgeCodex.git"
HASH_RE = "sha256:"
FILE_ATTRIBUTE_REPARSE_POINT = 0x400


class MigrationBlocked(RuntimeError):
    """The migration cannot continue without risking unmanaged content."""


@dataclass(frozen=True)
class Action:
    kind: str
    target: str
    expected_sha256: str | None
    reason: str


@dataclass
class Plan:
    user_profile: str
    source_root: str
    actions: list[Action]
    gaps: list[str]
    blockers: list[str]
    manifest_hashes: dict[str, str]
    new_ledger: dict[str, Any] | None
    fingerprint: str = ""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return HASH_RE + hashlib.sha256(payload).hexdigest()


def _file_hash(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return bool(
        stat.S_ISLNK(info.st_mode)
        or getattr(info, "st_file_attributes", 0)
        & FILE_ATTRIBUTE_REPARSE_POINT
    )


def _safe_child(root: Path, relative: str) -> Path:
    if not relative or Path(relative).is_absolute():
        raise MigrationBlocked(f"unsafe relative path: {relative!r}")
    parts = Path(relative).parts
    if any(item in {"", ".", ".."} for item in parts):
        raise MigrationBlocked(f"unsafe relative path: {relative!r}")
    candidate = root.joinpath(*parts)
    root_full = os.path.abspath(root)
    candidate_full = os.path.abspath(candidate)
    if os.path.commonpath((root_full, candidate_full)) != root_full:
        raise MigrationBlocked(f"path escapes root: {relative!r}")
    return Path(candidate_full)


def _directory_hash(root: Path) -> str:
    if not root.is_dir() or _is_reparse(root):
        raise MigrationBlocked(f"managed directory is missing or reparse: {root}")
    lines: list[str] = []
    stack = [root]
    while stack:
        current = stack.pop()
        for item in current.iterdir():
            if _is_reparse(item):
                raise MigrationBlocked(f"managed directory contains reparse entry: {item}")
            if item.is_dir():
                stack.append(item)
            elif item.is_file():
                relative = item.relative_to(root).as_posix()
                lines.append(f"{relative}\n{_file_hash(item).removeprefix(HASH_RE)}")
            else:
                raise MigrationBlocked(f"managed directory contains special entry: {item}")
    payload = ("\n".join(sorted(lines)) + "\n").encode("utf-8")
    return _sha256_bytes(payload)


def _normalized_remote(value: str) -> str:
    result = value.strip().rstrip("/").lower()
    return result[:-4] if result.endswith(".git") else result


def _git_output(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise MigrationBlocked(f"cannot inspect Git repository {root}: {detail}")
    return result.stdout.strip()


def _repository_identity(root: Path, expected_remote: str) -> dict[str, Any]:
    if not root.is_dir() or _is_reparse(root):
        raise MigrationBlocked(f"repository is missing or reparse: {root}")
    remote = _git_output(root, "config", "--get", "remote.origin.url")
    if _normalized_remote(remote) != _normalized_remote(expected_remote):
        raise MigrationBlocked(f"repository origin is not trusted: {root}")
    head = _git_output(root, "rev-parse", "HEAD").lower()
    if len(head) != 40 or any(character not in "0123456789abcdef" for character in head):
        raise MigrationBlocked(f"repository HEAD is invalid: {root}")
    status = _git_output(root, "status", "--porcelain", "--untracked-files=all")
    return {
        "remote": _normalized_remote(remote),
        "head": head,
        "status": status.splitlines() if status else [],
    }


def _repository_fingerprint(root: Path, expected_remote: str) -> str:
    return _sha256_bytes(_canonical_json(_repository_identity(root, expected_remote)))


def _legacy_home_fingerprint(root: Path) -> str:
    if _is_reparse(root):
        try:
            target = root.resolve(strict=True)
        except OSError as exc:
            raise MigrationBlocked(f"legacy home link target is unavailable: {root}") from exc
        identity = _repository_identity(target, LEGACY_REMOTE)
        payload = {
            "kind": "reparse",
            "target": os.path.normcase(str(target)),
            "identity": identity,
        }
        return _sha256_bytes(_canonical_json(payload))
    identity = _repository_identity(root, LEGACY_REMOTE)
    if identity["status"]:
        raise MigrationBlocked("legacy product home contains local changes")
    return _sha256_bytes(_canonical_json(identity))


def _remove_tree(root: Path) -> None:
    def make_writable_and_retry(function: Any, path: str, _error: Any) -> None:
        os.chmod(path, stat.S_IWRITE)
        function(path)

    shutil.rmtree(root, onerror=make_writable_and_retry)


def _read_ledger(path: Path, platform: str) -> dict[str, Any] | None:
    if not path.exists():
        return None
    if not path.is_file() or _is_reparse(path):
        raise MigrationBlocked(f"ledger is not a regular file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MigrationBlocked(f"invalid legacy ledger {path}: {exc}") from exc
    if (
        value.get("schema_version") != 1
        or value.get("platform") != platform
        or not isinstance(value.get("records"), dict)
    ):
        raise MigrationBlocked(f"invalid legacy ledger contract: {path}")
    for name, record in value["records"].items():
        if (
            not isinstance(name, str)
            or not isinstance(record, dict)
            or not isinstance(record.get("content_hash"), str)
            or not record["content_hash"].startswith(HASH_RE)
        ):
            raise MigrationBlocked(f"invalid legacy ledger record: {platform}/{name}")
    consents = value.get("consents")
    if consents is not None and (
        platform != "codex"
        or not isinstance(consents, dict)
        or set(consents) != {"native_memories"}
        or consents.get("native_memories") not in {"approved", "declined"}
    ):
        raise MigrationBlocked(f"invalid managed ledger consents: {path}")
    return value


def _manifest_codex_skills(
    source_root: Path,
) -> tuple[list[dict[str, Any]], set[str], dict[str, str]]:
    manifest_path = source_root / "bridgeforge-codex-manifest.json"
    compatibility_path = source_root / "shared-skill-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        codex = manifest["platforms"]["codex"]
        compatibility = json.loads(
            compatibility_path.read_text(encoding="utf-8-sig")
        )
        compatibility_codex = compatibility["platforms"]["codex"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise MigrationBlocked(f"invalid bridgeforge-codex manifest: {exc}") from exc
    active = [
        item
        for item in codex.get("skills", [])
        if isinstance(item, dict) and not item.get("legacy_transition")
    ]
    transitions = {
        str(item.get("name"))
        for item in compatibility_codex.get("skills", [])
        if isinstance(item, dict)
        and item.get("legacy_transition")
        and isinstance(item.get("name"), str)
    }
    if CURRENT_SKILL not in {item.get("name") for item in active}:
        raise MigrationBlocked("manifest does not contain the bridgeforge-codex bundle")
    if LEGACY_SKILL not in transitions:
        raise MigrationBlocked("manifest does not contain the one-time legacy transition")
    return active, transitions, {
        "bridgeforge-codex-manifest.json": _file_hash(manifest_path),
        "shared-skill-manifest.json": _file_hash(compatibility_path),
    }


def _fingerprint(plan: Plan) -> str:
    payload = {
        "user_profile": plan.user_profile,
        "source_root": plan.source_root,
        "actions": [asdict(item) for item in plan.actions],
        "gaps": plan.gaps,
        "blockers": plan.blockers,
        "manifest_hashes": plan.manifest_hashes,
        "new_ledger": plan.new_ledger,
    }
    return _sha256_bytes(_canonical_json(payload))


def build_plan(user_profile: Path, source_root: Path) -> Plan:
    profile = Path(os.path.abspath(user_profile))
    source = Path(os.path.abspath(source_root))
    if not profile.is_dir() or _is_reparse(profile):
        raise MigrationBlocked("USERPROFILE must be an existing plain directory")
    if not source.is_dir() or _is_reparse(source):
        raise MigrationBlocked("source root must be an existing plain directory")
    expected_source = _safe_child(profile, CURRENT_HOME)
    if os.path.normcase(str(source)) != os.path.normcase(str(expected_source)):
        raise MigrationBlocked(
            f"source root must be the managed bridgeforge-codex home: {expected_source}"
        )
    source_identity = _repository_identity(source, CURRENT_REMOTE)
    if source_identity["status"]:
        raise MigrationBlocked("bridgeforge-codex home contains local changes")

    legacy_codex_path = _safe_child(profile, LEGACY_CODEX_LEDGER)
    current_codex_path = _safe_child(profile, CURRENT_CODEX_LEDGER)
    legacy_claude_path = _safe_child(profile, LEGACY_CLAUDE_LEDGER)
    old_codex = _read_ledger(legacy_codex_path, "codex")
    current_codex = _read_ledger(current_codex_path, "codex")
    old_claude = _read_ledger(legacy_claude_path, "claude")

    actions: list[Action] = []
    gaps: list[str] = []
    blockers: list[str] = []
    manifest_hashes: dict[str, str] = {}
    new_ledger: dict[str, Any] | None = None

    if old_codex is not None:
        active, transition_names, manifest_hashes = _manifest_codex_skills(source)
        records: dict[str, Any] = {}
        installed_at = None
        source_commit = None
        for skill in active:
            name = str(skill["name"])
            target = _safe_child(profile, f".codex/skills/{name}")
            if not target.is_dir() or _is_reparse(target):
                blockers.append(f"new managed skill is missing or unsafe: {target}")
                continue
            actual = _directory_hash(target)
            manifest_lines = []
            for file in skill.get("files", []):
                digest = str(file.get("sha256", "")).removeprefix(HASH_RE)
                manifest_lines.append(f"{file['target']}\n{digest}")
            desired = _sha256_bytes(
                ("\n".join(sorted(manifest_lines)) + "\n").encode("utf-8")
            )
            if actual != desired:
                blockers.append(f"new managed skill failed manifest verification: {target}")
                continue
            legacy_record = old_codex["records"].get(name)
            if isinstance(legacy_record, dict):
                source_commit = source_commit or legacy_record.get("source_commit")
                installed_at = installed_at or legacy_record.get("installed_at")
            records[name] = {
                "source_commit": source_commit or "0" * 40,
                "content_hash": desired,
                "installed_at": installed_at or "migration",
            }
        old_consents = old_codex.get("consents")
        current_consents = (
            current_codex.get("consents")
            if current_codex is not None
            else None
        )
        if (
            isinstance(old_consents, dict)
            and isinstance(current_consents, dict)
            and old_consents != current_consents
        ):
            blockers.append(
                "legacy and current Codex ledgers disagree on native memories consent"
            )
        if not blockers and current_codex is None:
            new_ledger = {
                "schema_version": 1,
                "platform": "codex",
                "records": dict(sorted(records.items())),
            }
            if isinstance(old_consents, dict):
                new_ledger["consents"] = old_consents
            actions.append(Action(
                "write-ledger",
                CURRENT_CODEX_LEDGER,
                None,
                "create a fresh bridgeforge-codex ledger from manifest-verified targets",
            ))
        elif not blockers and current_codex is not None:
            for name, record in records.items():
                current_record = current_codex["records"].get(name)
                if not isinstance(current_record, dict) or (
                    current_record.get("content_hash") != record["content_hash"]
                ):
                    blockers.append(
                        f"current bridgeforge-codex ledger does not own verified skill: {name}"
                    )
            if not blockers and current_consents is None and isinstance(old_consents, dict):
                new_ledger = json.loads(json.dumps(current_codex))
                new_ledger["consents"] = old_consents
                actions.append(Action(
                    "write-ledger",
                    CURRENT_CODEX_LEDGER,
                    _file_hash(current_codex_path),
                    "preserve native memories consent while adopting the current ledger",
                ))

        for name, record in sorted(old_codex["records"].items()):
            if name not in transition_names:
                continue
            target = _safe_child(profile, f".codex/skills/{name}")
            if not target.exists():
                continue
            try:
                actual = _directory_hash(target)
            except MigrationBlocked as exc:
                gaps.append(str(exc))
                continue
            if actual != record["content_hash"]:
                gaps.append(f"preserved modified legacy Codex skill: {target}")
            else:
                actions.append(Action(
                    "retire-tree",
                    f".codex/skills/{name}",
                    actual,
                    "retire a ledger-proven legacy transition bundle",
                ))
        if not gaps:
            actions.append(Action(
                "retire-file",
                LEGACY_CODEX_LEDGER,
                _file_hash(legacy_codex_path),
                "retire the legacy Codex ledger after the new ledger is verified",
            ))

    if old_claude is not None:
        claude_gaps = False
        for name, record in sorted(old_claude["records"].items()):
            target = _safe_child(profile, f".claude/skills/{name}")
            if not target.exists():
                continue
            try:
                actual = _directory_hash(target)
            except MigrationBlocked as exc:
                gaps.append(str(exc))
                claude_gaps = True
                continue
            if actual != record["content_hash"]:
                gaps.append(f"preserved modified Claude skill: {target}")
                claude_gaps = True
                continue
            actions.append(Action(
                "retire-tree",
                f".claude/skills/{name}",
                actual,
                "retire a ledger-proven Claude skill",
            ))
        if not claude_gaps:
            actions.append(Action(
                "retire-file",
                LEGACY_CLAUDE_LEDGER,
                _file_hash(legacy_claude_path),
                "retire the empty BridgeForge Claude ledger",
            ))

    legacy_home = _safe_child(profile, LEGACY_HOME)
    if legacy_home.exists() or _is_reparse(legacy_home):
        try:
            legacy_fingerprint = _legacy_home_fingerprint(legacy_home)
        except MigrationBlocked as exc:
            gaps.append(f"preserved unproven legacy home: {legacy_home} ({exc})")
        else:
            actions.append(Action(
                "retire-legacy-home",
                LEGACY_HOME,
                legacy_fingerprint,
                "retire the trusted legacy BridgeForge product home",
            ))

    plan = Plan(
        str(profile),
        str(source),
        actions,
        gaps,
        blockers,
        manifest_hashes,
        new_ledger,
    )
    plan.fingerprint = _fingerprint(plan)
    return plan


class Transaction:
    def __init__(self, profile: Path) -> None:
        self.profile = profile
        self.backup = Path(tempfile.mkdtemp(prefix=".bridgeforge-codex-migrate-", dir=profile))
        self.moves: list[tuple[Path, Path]] = []
        self.created: list[Path] = []

    def retire(self, target: Path) -> None:
        relative = target.relative_to(self.profile)
        backup = self.backup / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        os.replace(target, backup)
        self.moves.append((target, backup))

    def write_json(self, target: Path, value: dict[str, Any]) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, target)
        self.created.append(target)

    def rollback(self) -> None:
        for path in reversed(self.created):
            if path.exists():
                path.unlink()
        for target, backup in reversed(self.moves):
            target.parent.mkdir(parents=True, exist_ok=True)
            if backup.exists():
                os.replace(backup, target)
        if self.backup.exists():
            _remove_tree(self.backup)

    def commit(self) -> None:
        for _target, backup in self.moves:
            if backup.exists() and _is_reparse(backup):
                os.rmdir(backup)
        _remove_tree(self.backup)


def apply_plan(
    planned: Plan,
    fingerprint: str,
    *,
    confirmed: bool,
    fail_after: int = 0,
) -> dict[str, Any]:
    if not confirmed:
        raise MigrationBlocked("migration risk card was not confirmed")
    if planned.blockers:
        raise MigrationBlocked("plan contains blockers")
    if planned.fingerprint != fingerprint:
        raise MigrationBlocked("supplied fingerprint does not match the displayed plan")
    rebuilt = build_plan(Path(planned.user_profile), Path(planned.source_root))
    if rebuilt.fingerprint != fingerprint:
        raise MigrationBlocked("migration fingerprint drifted; zero writes performed")

    profile = Path(rebuilt.user_profile)
    transaction = Transaction(profile)
    completed = 0
    try:
        for action in rebuilt.actions:
            if action.kind == "write-ledger":
                if rebuilt.new_ledger is None:
                    raise MigrationBlocked("new ledger payload is missing")
                transaction.write_json(
                    _safe_child(profile, action.target),
                    rebuilt.new_ledger,
                )
            else:
                target = _safe_child(profile, action.target)
                if action.expected_sha256 is not None:
                    if action.kind == "retire-legacy-home":
                        actual = _legacy_home_fingerprint(target)
                    else:
                        actual = (
                            _directory_hash(target)
                            if target.is_dir()
                            else _file_hash(target)
                        )
                    if actual != action.expected_sha256:
                        raise MigrationBlocked(f"target drifted after planning: {target}")
                transaction.retire(target)
            completed += 1
            if fail_after and completed >= fail_after:
                raise MigrationBlocked("injected migration failure")
        current = _safe_child(profile, CURRENT_CODEX_LEDGER)
        if rebuilt.new_ledger is not None:
            parsed = json.loads(current.read_text(encoding="utf-8"))
            if parsed != rebuilt.new_ledger:
                raise MigrationBlocked("new ledger verification failed")
        transaction.commit()
    except Exception as exc:
        transaction.rollback()
        raise MigrationBlocked(f"migration failed and was rolled back: {exc}") from exc
    return {
        "status": "completed_with_gaps" if rebuilt.gaps else "completed",
        "fingerprint": rebuilt.fingerprint,
        "applied": [asdict(item) for item in rebuilt.actions],
        "gaps": rebuilt.gaps,
        "rollback_performed": False,
    }


def _plan_json(plan: Plan) -> dict[str, Any]:
    return {
        "user_profile": plan.user_profile,
        "source_root": plan.source_root,
        "actions": [asdict(item) for item in plan.actions],
        "gaps": plan.gaps,
        "blockers": plan.blockers,
        "fingerprint": plan.fingerprint,
        "requires_confirmation": bool(plan.actions),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-profile", type=Path, default=os.environ.get("USERPROFILE"))
    parser.add_argument("--source-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirmed", action="store_true")
    parser.add_argument("--plan-fingerprint")
    parser.add_argument("--test-fail-after", type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        if args.user_profile is None:
            raise MigrationBlocked("USERPROFILE is not set")
        plan = build_plan(args.user_profile, args.source_root)
        if not args.apply:
            print(json.dumps(_plan_json(plan), ensure_ascii=False, indent=2))
            return 2 if plan.blockers else 0
        if not args.plan_fingerprint:
            raise MigrationBlocked("--apply requires --plan-fingerprint")
        receipt = apply_plan(
            plan,
            args.plan_fingerprint,
            confirmed=args.confirmed,
            fail_after=args.test_fail_after,
        )
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 0
    except MigrationBlocked as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
