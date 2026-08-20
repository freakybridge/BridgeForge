#!/usr/bin/env python3
"""Factory-only ownership and canonicalization helpers for Codex hooks.json files."""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Callable, Iterable

MANAGED_ID_KEY = "bridgeforgeCodexId"


class HooksOwnershipError(RuntimeError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise HooksOwnershipError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json_object(payload: bytes | str, label: str) -> dict[str, Any]:
    try:
        text = payload.decode("utf-8-sig") if isinstance(payload, bytes) else payload
        value = json.loads(text, object_pairs_hook=_reject_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HooksOwnershipError(f"invalid hooks JSON: {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise HooksOwnershipError(f"JSON root must be an object: {label}")
    return value


def load_document(payload: bytes | str, label: str) -> dict[str, Any]:
    value = load_json_object(payload, label)
    hooks = value.get("hooks")
    if not isinstance(hooks, dict):
        raise HooksOwnershipError(f"hooks JSON has no hooks object: {label}")
    return value


def canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def render_document(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def expected_groups(
    document: dict[str, Any],
    *,
    managed_prefix: str,
) -> list[dict[str, Any]]:
    hooks = document.get("hooks")
    if not isinstance(hooks, dict):
        raise HooksOwnershipError("canonical hooks document has no hooks object")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event, groups in hooks.items():
        if not isinstance(event, str) or not isinstance(groups, list):
            raise HooksOwnershipError("canonical hooks document has invalid event groups")
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise HooksOwnershipError("canonical hooks document has invalid matcher group")
            matcher = group.get("matcher", "")
            if not isinstance(matcher, str):
                raise HooksOwnershipError("canonical hooks document has invalid matcher")
            handlers = group["hooks"]
            marked = [
                handler
                for handler in handlers
                if isinstance(handler, dict)
                and isinstance(handler.get(MANAGED_ID_KEY), str)
                and handler[MANAGED_ID_KEY].startswith(managed_prefix)
            ]
            if not marked:
                continue
            if len(handlers) != 1 or len(marked) != 1:
                raise HooksOwnershipError(
                    "canonical managed hook group must contain exactly one handler"
                )
            managed_id = marked[0].get(MANAGED_ID_KEY)
            if not isinstance(managed_id, str) or not managed_id.startswith(managed_prefix):
                raise HooksOwnershipError(
                    f"canonical managed handler has no valid {MANAGED_ID_KEY}: {event}"
                )
            if managed_id in seen:
                raise HooksOwnershipError(f"duplicate canonical managed id: {managed_id}")
            seen.add(managed_id)
            result.append({
                "id": managed_id,
                "event": event,
                "matcher": matcher,
                "handler_sha256": canonical_json_sha256(marked[0]),
                "handler": copy.deepcopy(marked[0]),
                "group": copy.deepcopy(group),
            })
    if not result:
        raise HooksOwnershipError("canonical hooks document has no managed handlers")
    return result


def _validate_shape(document: dict[str, Any], label: str) -> None:
    hooks = document.get("hooks")
    if not isinstance(hooks, dict):
        raise HooksOwnershipError(f"hooks JSON has no hooks object: {label}")
    for event, groups in hooks.items():
        if not isinstance(event, str) or not isinstance(groups, list):
            raise HooksOwnershipError(f"invalid hook groups: {event}: {label}")
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise HooksOwnershipError(f"invalid matcher group: {event}: {label}")
            matcher = group.get("matcher", "")
            if not isinstance(matcher, str):
                raise HooksOwnershipError(f"invalid matcher: {event}: {label}")
            if any(not isinstance(handler, dict) for handler in group["hooks"]):
                raise HooksOwnershipError(f"invalid hook handler: {event}: {label}")


def canonicalize(
    document: dict[str, Any],
    expected: Iterable[dict[str, Any]],
    *,
    managed_prefixes: tuple[str, ...],
    label: str,
    managed_looking: Callable[[dict[str, Any]], bool] | None = None,
    replace_marked_drift: bool = False,
    managed_top_level: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, str]]]:
    """Return the canonical document, external projection, and current receipts."""
    _validate_shape(document, label)
    specs = [copy.deepcopy(item) for item in expected]
    expected_by_id = {str(item["id"]): item for item in specs}
    if len(expected_by_id) != len(specs):
        raise HooksOwnershipError("expected hooks contain duplicate managed ids")
    external = copy.deepcopy(document)
    external_hooks = external["hooks"]
    receipts: list[dict[str, str]] = []
    found: dict[str, int] = {}
    original_hooks = document["hooks"]
    for event, groups in list(original_hooks.items()):
        external_groups: list[dict[str, Any]] = []
        for group in groups:
            matcher = group.get("matcher", "")
            kept_handlers: list[dict[str, Any]] = []
            managed_count = 0
            for handler in group["hooks"]:
                digest = canonical_json_sha256(handler)
                raw_id = handler.get(MANAGED_ID_KEY)
                managed_id: str | None = None
                if isinstance(raw_id, str) and raw_id in expected_by_id:
                    managed_id = raw_id
                elif isinstance(raw_id, str) and raw_id.startswith(managed_prefixes):
                    raise HooksOwnershipError(f"unknown managed hook id: {raw_id}: {label}")
                if managed_id is None:
                    if managed_looking is not None and managed_looking(handler):
                        raise HooksOwnershipError(
                            f"managed-looking handler has no trusted ownership: {event}/{matcher}: {label}"
                        )
                    kept_handlers.append(copy.deepcopy(handler))
                    continue

                spec = expected_by_id[managed_id]
                if event != spec["event"] or matcher != spec["matcher"]:
                    raise HooksOwnershipError(
                        f"managed hook is registered in the wrong group: {managed_id}: {label}"
                    )
                if digest != spec["handler_sha256"] and not replace_marked_drift:
                    raise HooksOwnershipError(f"managed hook content drifted: {managed_id}: {label}")
                found[managed_id] = found.get(managed_id, 0) + 1
                managed_count += 1
                receipts.append({
                    "id": managed_id,
                    "event": event,
                    "matcher": matcher,
                    "action": "canonicalize",
                })
            if kept_handlers:
                kept_group = copy.deepcopy(group)
                kept_group["hooks"] = kept_handlers
                external_groups.append(kept_group)
            elif managed_count == 0:
                external_groups.append(copy.deepcopy(group))
        if external_groups:
            external_hooks[event] = external_groups
        else:
            external_hooks.pop(event, None)

    canonical = copy.deepcopy(external)
    canonical_hooks = canonical["hooks"]
    for spec in specs:
        bucket = canonical_hooks.setdefault(str(spec["event"]), [])
        if not isinstance(bucket, list):
            raise HooksOwnershipError(f"invalid canonical event: {spec['event']}: {label}")
        bucket.append(copy.deepcopy(spec["group"]))
    if managed_top_level:
        for key, value in managed_top_level.items():
            if (
                key in document
                and document[key] != value
            ):
                raise HooksOwnershipError(
                    f"managed top-level field has no trusted ownership: {key}: {label}"
                )
            canonical[key] = copy.deepcopy(value)
            external.pop(key, None)
    for managed_id in expected_by_id:
        if found.get(managed_id, 0) == 0:
            receipts.append({
                "id": managed_id,
                "event": str(expected_by_id[managed_id]["event"]),
                "matcher": str(expected_by_id[managed_id]["matcher"]),
                "action": "add-missing",
            })
    return canonical, external, receipts


def validate_current(
    document: dict[str, Any],
    expected: Iterable[dict[str, Any]],
    *,
    managed_prefixes: tuple[str, ...],
    label: str,
    managed_looking: Callable[[dict[str, Any]], bool] | None = None,
    managed_top_level: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical, external, _receipts = canonicalize(
        document,
        expected,
        managed_prefixes=managed_prefixes,
        label=label,
        managed_looking=managed_looking,
        managed_top_level=managed_top_level,
    )
    if document != canonical:
        raise HooksOwnershipError(f"managed hooks zones are not canonical: {label}")
    return external
