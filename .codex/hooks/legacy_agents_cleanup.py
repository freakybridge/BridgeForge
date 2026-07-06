"""SessionStart hook: remove an empty legacy .agents workspace directory.

Some agent runtimes still probe legacy `.agents/` paths during session setup.
BridgeForge does not use a project-root `.agents/` directory, and an empty one
is just workspace noise. This hook only removes the ordinary empty directory;
content, symlinks, junctions, and any error case are left untouched.
"""

from __future__ import annotations

import stat
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LEGACY_AGENTS_DIR = REPO_ROOT / ".agents"


def _is_reparse_point(path: Path) -> bool:
    try:
        attrs = path.lstat().st_file_attributes
    except (AttributeError, OSError):
        return False
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _is_plain_empty_dir(path: Path) -> bool:
    if path.is_symlink() or _is_reparse_point(path):
        return False
    if not path.is_dir():
        return False
    try:
        next(path.iterdir())
    except StopIteration:
        return True
    except OSError:
        return False
    return False


def main() -> int:
    try:
        if _is_plain_empty_dir(LEGACY_AGENTS_DIR):
            LEGACY_AGENTS_DIR.rmdir()
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
