#!/usr/bin/env python3
"""Shared full-document TOML policy for Codex hook registration surfaces."""
from __future__ import annotations

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 and earlier must fail closed.
    tomllib = None  # type: ignore[assignment]


class TomlHeaderError(ValueError):
    """The TOML policy could not safely decide whether hooks are registered."""


def load_config(text: str) -> dict[str, object]:
    """Parse the complete TOML document, failing closed without stdlib tomllib."""
    if tomllib is None:
        raise TomlHeaderError(
            "Python 3.11+ standard-library tomllib is required to inspect config.toml"
        )
    try:
        return tomllib.loads(text)
    except Exception as exc:
        raise TomlHeaderError(f"invalid TOML: {exc}") from exc


def has_hooks_table(text: str) -> bool:
    """Return true when the fully parsed document has a top-level hooks key."""
    return "hooks" in load_config(text)
