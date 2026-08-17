#!/usr/bin/env python3
"""Executable bridgeforge-codex Codex-only downstream regression fixture."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
CURRENT_VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sync = load("bridgeforge_codex_project_sync_fixture", ROOT / "scripts/bridgeforge_codex_project_sync.py")
merge = load("bridgeforge_codex_precommit_merge_fixture", ROOT / "templates/scripts/precommit_merge.py")
manifest_builder = load(
    "bridgeforge_codex_manifest_builder_fixture",
    ROOT / "scripts/rebuild_shared_skill_manifest.py",
)


def _git_blob(revision: str, source: str) -> bytes | None:
    result = subprocess.run(
        ["git", "show", f"{revision}:{source}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def _materialize_published_project(
    project: Path,
    *,
    version: str,
    revision: str,
    contract: dict[str, object],
) -> None:
    project.mkdir()
    assets = contract["assets"]
    assert isinstance(assets, list)
    for raw_asset in assets:
        assert isinstance(raw_asset, dict)
        source = raw_asset.get("historical_source") or raw_asset.get("source")
        target = raw_asset.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        payload = _git_blob(revision, source)
        if payload is None:
            continue
        if target == "AGENTS.md":
            payload = payload.replace(b"{{PROJECT_NAME}}", project.name.encode("utf-8"))
        destination = project / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    historical_contract = _git_blob(revision, "templates/codex/managed-skeleton.json")
    if historical_contract is not None:
        destination = project / ".codex/managed-skeleton.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(historical_contract)
    stamp = project / ".codex/.bridgeforge_version"
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(version + "\n", encoding="utf-8")


def _published_lineage_check(contract: dict[str, object]) -> dict[str, object]:
    baselines = manifest_builder._baseline_revisions(ROOT)
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory() as raw:
        base = Path(raw)
        for version, revision in baselines.items():
            project = base / f"published-{version.replace('.', '-')}"
            try:
                _materialize_published_project(
                    project,
                    version=version,
                    revision=revision,
                    contract=contract,
                )
                plan = sync.build_plan(project, ROOT, "update")
                if plan.blockers or plan.gaps:
                    results.append({
                        "version": version,
                        "ok": False,
                        "blockers": list(plan.blockers),
                        "gaps": list(plan.gaps),
                    })
                    continue
                receipt = sync.apply_plan(
                    plan,
                    plan_fingerprint=plan.aggregate_fingerprint,
                    confirmed_risk=True,
                )
                repeated = sync.build_plan(project, ROOT, "update")
                results.append({
                    "version": version,
                    "ok": (
                        receipt.stamp_written_last
                        and (project / ".codex/.bridgeforge_codex_version").read_text(
                            encoding="utf-8"
                        ).strip() == CURRENT_VERSION
                        and not (project / ".codex/.bridgeforge_version").exists()
                        and not repeated.safe_actions
                        and not repeated.risk_actions
                        and not repeated.absorption_actions
                        and not repeated.gaps
                        and not repeated.blockers
                    ),
                    "status": receipt.status,
                })
            except Exception as exc:
                results.append({"version": version, "ok": False, "error": str(exc)})
    return {
        "name": "published-lineage-executable",
        "ok": bool(results) and all(bool(item["ok"]) for item in results),
        "migrated_count": sum(bool(item["ok"]) for item in results),
        "expected_count": len(baselines),
        "results": results,
    }


def main() -> int:
    checks: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory() as raw:
        project = Path(raw)
        legacy_claude = project / ".claude/private.txt"
        legacy_claude.parent.mkdir()
        legacy_claude.write_text("must stay opaque\n", encoding="utf-8")

        original_read_text = Path.read_text
        original_read_bytes = Path.read_bytes

        def guarded_text(path: Path, *args, **kwargs):
            if path == legacy_claude or legacy_claude.parent in path.parents:
                raise AssertionError("Claude legacy content was read")
            return original_read_text(path, *args, **kwargs)

        def guarded_bytes(path: Path, *args, **kwargs):
            if path == legacy_claude or legacy_claude.parent in path.parents:
                raise AssertionError("Claude legacy content was read")
            return original_read_bytes(path, *args, **kwargs)

        with mock.patch.object(Path, "read_text", guarded_text), mock.patch.object(
            Path, "read_bytes", guarded_bytes
        ):
            plan = sync.build_plan(project, ROOT, "init")
        notice = [
            item
            for item in plan.project_requirements
            if item.get("category") == "unsupported_legacy_notice"
        ]
        checks.append({"name": "claude-existence-only", "ok": len(notice) == 1})
        receipt = sync.apply_plan(plan, plan_fingerprint=plan.aggregate_fingerprint)
        checks.append({
            "name": "codex-init-stamp-last",
            "ok": (
                receipt.stamp_written_last
                and (project / ".codex/.bridgeforge_codex_version").read_text(
                    encoding="utf-8"
                ).strip() == CURRENT_VERSION
                and legacy_claude.read_text(encoding="utf-8") == "must stay opaque\n"
            ),
        })

        legacy_hook = (
            b"#!/bin/sh\n"
            b"# >>> BRIDGEFORGE_MANAGED_BEGIN\nold-managed\n"
            b"# <<< BRIDGEFORGE_MANAGED_END\n"
            b"# >>> PROJECT_EXTENSION_BEGIN\nlocal-extension\n"
            b"# <<< PROJECT_EXTENSION_END\n"
        )
        hook_path = project / ".githooks/pre-commit"
        hook_path.parent.mkdir(exist_ok=True)
        hook_path.write_bytes(legacy_hook)
        merged = merge.build_plan(
            project,
            ROOT / "templates/.githooks/pre-commit",
        )
        checks.append({
            "name": "legacy-marker-migration",
            "ok": (
                b"BRIDGEFORGE_CODEX_MANAGED_BEGIN" in merged.after
                and b"BRIDGEFORGE_MANAGED_BEGIN" not in merged.after
                and b"local-extension" in merged.after
            ),
        })

    contract = json.loads(
        (ROOT / "templates/managed-skeleton.json").read_text(encoding="utf-8-sig")
    )
    versions = set(contract["contract_historical_sha256"])
    published = re.findall(
        r"(?m)^## \[(0\.(?:8[6-9]|9\d)\.\d+)\]",
        (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"),
    )
    lineage = _published_lineage_check(contract)
    lineage["ok"] = bool(lineage["ok"]) and (
        contract["minimum_supported_version"] == "0.86.0"
        and len(set(published)) >= 19
        and "0.86.0" in versions
    )
    lineage["versions"] = sorted(versions)
    lineage["published_count"] = len(set(published))
    checks.append(lineage)
    status = "passed" if all(bool(item["ok"]) for item in checks) else "failed"
    print(json.dumps({"status": status, "checks": checks}, ensure_ascii=False, indent=2))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
