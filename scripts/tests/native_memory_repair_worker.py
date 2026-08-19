#!/usr/bin/env python3
"""Subprocess fixture for competing Native Memory hook repair writers."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        raise SystemExit("usage: native_memory_repair_worker.py SOURCE CODEX_HOME PROJECT_ROOT")
    source = Path(sys.argv[1]).resolve()
    os.environ["CODEX_HOME"] = str(Path(sys.argv[2]).resolve())
    project_root = Path(sys.argv[3]).resolve()
    spec = importlib.util.spec_from_file_location("native_memory_repair_worker_runtime", source)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.main(["repair-hook", "--project-root", str(project_root)])


if __name__ == "__main__":
    raise SystemExit(main())
