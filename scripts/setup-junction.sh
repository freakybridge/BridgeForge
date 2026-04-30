#!/usr/bin/env bash
# Setup memory symlink: ~/.claude/projects/<hash>/memory/ -> <project>/.claude/memory/
#
# Creates a symlink so Claude Code's per-project memory directory (under user
# home) transparently redirects to a directory inside the project (under git
# management). This makes memory clone-recoverable across machines.
#
# Usage:
#   ./setup-junction.sh /abs/path/to/project
#
# Tested on macOS / Linux. Windows users should use setup-junction.ps1.

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <project-abs-path>" >&2
    exit 1
fi

PROJECT_PATH="$1"

# 1. Validate project path
if [[ ! -d "$PROJECT_PATH" ]]; then
    echo "Error: project path not found or not a directory: $PROJECT_PATH" >&2
    exit 1
fi

# Resolve to absolute path
PROJECT_ABS="$(cd "$PROJECT_PATH" && pwd)"
PROJECT_MEMORY_DIR="$PROJECT_ABS/.claude/memory"

# 2. Ensure project-side .claude/memory/ exists
if [[ ! -d "$PROJECT_MEMORY_DIR" ]]; then
    echo "Creating project memory dir: $PROJECT_MEMORY_DIR"
    mkdir -p "$PROJECT_MEMORY_DIR"
fi

# 3. Compute project hash (Claude Code's convention)
#    Replace path separators with dashes; on Unix drop leading slash and use no drive prefix.
#    Example: /home/user/dev/MyProject -> -home-user-dev-MyProject
#    NOTE: this should match Claude Code's actual hashing convention. If your
#    Claude Code uses a different convention, adjust here.
PROJECT_HASH="$(echo "$PROJECT_ABS" | sed 's|/|-|g')"

# 4. Compute system memory paths
SYSTEM_MEMORY_PARENT="$HOME/.claude/projects/$PROJECT_HASH"
SYSTEM_MEMORY_DIR="$SYSTEM_MEMORY_PARENT/memory"

echo "Project hash:        $PROJECT_HASH"
echo "System memory path:  $SYSTEM_MEMORY_DIR"
echo "Project memory path: $PROJECT_MEMORY_DIR"

mkdir -p "$SYSTEM_MEMORY_PARENT"

# 5. Handle existing system memory dir
if [[ -L "$SYSTEM_MEMORY_DIR" ]]; then
    EXISTING_TARGET="$(readlink "$SYSTEM_MEMORY_DIR")"
    if [[ "$EXISTING_TARGET" == "$PROJECT_MEMORY_DIR" ]]; then
        echo "Symlink already exists and points to the right target. Skipping."
        exit 0
    else
        echo "Symlink exists but points to: $EXISTING_TARGET" >&2
        echo "Will replace with target: $PROJECT_MEMORY_DIR" >&2
        read -p "Continue? [y/N] " -n 1 -r
        echo
        [[ $REPLY =~ ^[Yy]$ ]] || exit 1
        rm "$SYSTEM_MEMORY_DIR"
    fi
elif [[ -d "$SYSTEM_MEMORY_DIR" ]]; then
    if [[ -n "$(ls -A "$SYSTEM_MEMORY_DIR" 2>/dev/null)" ]]; then
        echo "Error: system memory dir is non-empty (regular dir): $SYSTEM_MEMORY_DIR" >&2
        echo "Manually backup its content into $PROJECT_MEMORY_DIR, then delete the system dir, then re-run." >&2
        exit 1
    else
        echo "System memory dir is empty. Removing and creating symlink."
        rmdir "$SYSTEM_MEMORY_DIR"
    fi
elif [[ -e "$SYSTEM_MEMORY_DIR" ]]; then
    echo "Error: unexpected file at system memory path: $SYSTEM_MEMORY_DIR" >&2
    exit 1
fi

# 6. Create symlink
echo "Creating symlink..."
ln -s "$PROJECT_MEMORY_DIR" "$SYSTEM_MEMORY_DIR"

# 7. Verify
if [[ -L "$SYSTEM_MEMORY_DIR" ]] && [[ "$(readlink "$SYSTEM_MEMORY_DIR")" == "$PROJECT_MEMORY_DIR" ]]; then
    echo "Symlink created successfully:"
    echo "  $SYSTEM_MEMORY_DIR  ->  $PROJECT_MEMORY_DIR"
else
    echo "Error: symlink verification failed." >&2
    exit 1
fi
