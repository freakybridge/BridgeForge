#!/usr/bin/env python3
"""SessionStart hook: 骨架必要配置开机体检（只读，不自动修）。

每次 session 开始照一份「骨架约定的必要配置」清单逐项核对，发现不达标只**报告**
（纯 ASCII，一行一条 + 修复提示），**绝不自动改任何文件** —— 修不修由用户决定。
全部达标时静默（不刷屏）。

为什么只读不自动修：本 hook 会被复印进所有下游项目、每次开机在每台机器上跑。
一个「会自动改你配置」的 hook 复印出去就是埋雷（在别人机器上自作主张改错 / 写坏）。
故定位为「体检仪」：测温报数，开药留给人。（与 2026-06-25 encoding-fix-scope debate 同源决策。）

为什么输出纯 ASCII：万一缺的恰好是 PYTHONUTF8（UTF-8 Mode 没生效），用中文报警，
警报自己会在 GBK 控制台糊成乱码 —— 正是它要查的病。故护栏文本一律英文 ASCII。

单一事实源：下面 ACTIVE_CHECKS + DELEGATED 两张表就是「骨架要求哪些配置 + 谁来保证」
的唯一清单。新增必要配置只改这里：本 hook 亲测的加进 ACTIVE_CHECKS；已有专职 hook
兜的登记进 DELEGATED（本 hook 不重复测，避免双重刷屏 / 时序竞争）。

非阻塞：始终 exit 0；任何单项检查抛异常都吞掉，绝不拖垮 session 启动。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

USER_SETTINGS = Path.home() / ".codex" / "settings.json"
PROJECT_SETTINGS = Path(".codex") / "settings.json"          # SessionStart hook cwd = 项目根
PROJECT_SETTINGS_LOCAL = Path(".codex") / "settings.local.json"
PROJECT_HOOKS = Path(".codex") / "hooks.json"
PROJECT_CONFIG = Path(".codex") / "config.toml"
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
try:
    from hook_config_policy import TomlHeaderError, has_hooks_table
    POLICY_IMPORT_ERROR = ""
except Exception as exc:  # strict mode must fail closed when shared policy is unavailable
    TomlHeaderError = ValueError  # type: ignore[assignment,misc]
    has_hooks_table = None  # type: ignore[assignment]
    POLICY_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
try:
    from project_runtime import ProjectRuntimeError, validate_project_runtime
    PROJECT_RUNTIME_IMPORT_ERROR = ""
except Exception as exc:  # strict mode must fail closed when runtime proof is unavailable
    ProjectRuntimeError = RuntimeError  # type: ignore[assignment,misc]
    validate_project_runtime = None  # type: ignore[assignment]
    PROJECT_RUNTIME_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


# --- 各体检项：返回 None=通过，返回字符串=不达标（一行纯 ASCII，含修复提示） ---

def _check_python_version(version_info: object = sys.version_info) -> "str | None":
    """All bridgeforge-codex hooks require Python 3.11+ and stdlib tomllib."""
    major = int(getattr(version_info, "major", version_info[0]))  # type: ignore[index]
    minor = int(getattr(version_info, "minor", version_info[1]))  # type: ignore[index]
    if (major, minor) >= (3, 11):
        return None
    return (
        f"PYTHON_VERSION: {major}.{minor} is unsupported. "
        "FIX: create or upgrade the project .venv with Python 3.11+, then rerun $bridgeforge-codex."
    )


def _check_project_runtime() -> "str | None":
    """The running hook must belong to this project's proven CPython .venv."""
    if PROJECT_RUNTIME_IMPORT_ERROR or validate_project_runtime is None:
        return (
            "PROJECT_RUNTIME: shared runtime validator is unavailable "
            f"({PROJECT_RUNTIME_IMPORT_ERROR}). FIX: rerun $bridgeforge-codex."
        )
    try:
        validate_project_runtime(Path.cwd(), executable=sys.executable)
    except ProjectRuntimeError as exc:
        return (
            f"PROJECT_RUNTIME: {exc}. FIX: create or repair the project .venv "
            "with CPython 3.11+, then rerun $bridgeforge-codex."
        )
    except Exception as exc:
        return (
            "PROJECT_RUNTIME: validation failed closed "
            f"({type(exc).__name__}). FIX: rerun $bridgeforge-codex."
        )
    return None

def _check_pythonutf8() -> "str | None":
    """承重柱：UTF-8 Mode 真生效没。查 sys.flags.utf8_mode（事实，不被 stdout.reconfigure 掩盖）。

    GBK Windows 上若 OFF，hook 的中文输出 / open() 读文件会糊成 U+FFFD 注入 context
    （曾高频致 agent 跑偏，见 memory utf8-garble-rootcause）。原 utf8-guard 即此项，已归位到这。
    """
    if not sys.flags.utf8_mode:
        return ("PYTHONUTF8: OFF (Python UTF-8 Mode not active). On GBK Windows this can "
                "corrupt Chinese hook output into the context. "
                "FIX: add \"env\":{\"PYTHONUTF8\":\"1\",\"PYTHONIOENCODING\":\"utf-8\"} "
                "to ~/.codex/settings.json, then restart the session.")
    return None


def _check_settings_json_valid() -> "str | None":
    """user / project settings.json 必须是合法 JSON —— 坏掉会静默架空 hooks/permissions。"""
    bad = []
    for label, p in (("~/.codex/settings.json", USER_SETTINGS),
                     (".codex/settings.json", PROJECT_SETTINGS),
                     (".codex/settings.local.json", PROJECT_SETTINGS_LOCAL)):
        if not p.is_file():
            continue
        try:
            with open(p, encoding="utf-8") as f:
                json.load(f)
        except Exception as e:
            bad.append("%s (%s)" % (label, type(e).__name__))
    if bad:
        return ("settings.json invalid JSON: %s. "
                "FIX: repair the JSON syntax (a broken settings file silently disables "
                "hooks/permissions)." % ", ".join(bad))
    return None


def _check_single_hook_source() -> "str | None":
    """bridgeforge-codex projects register lifecycle hooks only in hooks.json."""
    failures: list[str] = []
    if POLICY_IMPORT_ERROR or has_hooks_table is None:
        failures.append(f"shared hook policy unavailable ({POLICY_IMPORT_ERROR})")
    for label, path in (
        (".codex/settings.json", PROJECT_SETTINGS),
        (".codex/settings.local.json", PROJECT_SETTINGS_LOCAL),
    ):
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue  # syntax is owned by settings-json-valid
        if isinstance(value, dict) and "hooks" in value:
            failures.append(f"{label} contains hooks")

    if PROJECT_CONFIG.is_file():
        try:
            text = PROJECT_CONFIG.read_text(encoding="utf-8")
        except Exception:
            text = ""
        if has_hooks_table is not None:
            try:
                if has_hooks_table(text):
                    failures.append(".codex/config.toml contains a hooks table")
            except TomlHeaderError as exc:
                failures.append(f".codex/config.toml table header invalid ({exc})")

    try:
        hooks = json.loads(PROJECT_HOOKS.read_text(encoding="utf-8"))
        if not isinstance(hooks, dict) or not isinstance(hooks.get("hooks"), dict):
            failures.append(".codex/hooks.json has no hooks object")
    except Exception as exc:
        failures.append(f".codex/hooks.json invalid JSON ({type(exc).__name__})")

    if not failures:
        return None
    return (
        "Codex hook registration is not single-source: "
        + "; ".join(failures)
        + ". FIX: merge project hooks into .codex/hooks.json and remove all other hook blocks."
    )


def _check_memory_schema() -> "str | None":
    """Project memory must already match the canonical bridgeforge-codex layout."""
    lint = Path(__file__).resolve().parent / "memory_lint.py"
    if not lint.is_file():
        return "MEMORY_SCHEMA: memory_lint.py is missing. FIX: rerun $bridgeforge-codex."
    try:
        result = subprocess.run(
            [sys.executable, str(lint), "--organize"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
            check=False,
        )
    except Exception as exc:
        return (
            f"MEMORY_SCHEMA: audit failed ({type(exc).__name__}). "
            "FIX: rerun $bridgeforge-codex."
        )
    if result.returncode == 0:
        return None
    return (
        "MEMORY_SCHEMA: project memory needs migration. "
        "FIX: run $bridgeforge-codex and review the complete memory plan."
    )


# 本 hook 亲测 + 报告的项（单一事实源之一）。
ACTIVE_CHECKS = (
    ("project-runtime", _check_project_runtime),
    ("python-version", _check_python_version),
    ("pythonutf8", _check_pythonutf8),
    ("settings-json-valid", _check_settings_json_valid),
    ("single-hook-source", _check_single_hook_source),
    ("memory-schema", _check_memory_schema),
)

# 已有专职 hook 保证的必要配置 —— 本 hook **不重复测**（避免双重刷屏 / 时序竞争），仅在此
# 登记备查，让本文件成为「骨架要求哪些配置 + 谁来保证」的完整单一事实源。新增「已有 owner」
# 的必要配置登记到这；若要本 hook 亲测，则改放 ACTIVE_CHECKS。
DELEGATED = (
    ("project-memory-context", "memory_context.py after memory_rebuild_index.py"),
    ("no-project-effortlevel", "enforce_no_effortlevel.py (strips + reports on action)"),
    ("user-skill-sync", "skill_sync_check.py (reports drift)"),
)


def main(
    version_info: object = sys.version_info,
    strict: bool | None = None,
) -> int:
    failures: list[tuple[str, str]] = []
    for name, fn in ACTIVE_CHECKS:
        try:
            msg = fn(version_info) if name == "python-version" else fn()
        except Exception:
            continue  # 单项检查异常绝不拖垮启动
        if msg:
            failures.append((name, msg))

    if not failures:
        return 0  # 全绿静默

    print("[health-check] %d skeleton setting(s) need attention "
          "(check-only, nothing changed):" % len(failures))
    for _name, msg in failures:
        print("  - %s" % msg)
    strict_failures = {
        "project-runtime",
        "python-version",
        "settings-json-valid",
        "single-hook-source",
        "memory-schema",
    }
    if "--post-apply" in sys.argv:
        # The sync CLI validates the project runtime before planning. Its
        # transaction validator reuses this hook only for on-disk config.
        strict_failures.discard("project-runtime")
    strict_mode = "--strict" in sys.argv if strict is None else strict
    return 2 if strict_mode and any(
        name in strict_failures for name, _msg in failures
    ) else 0


if __name__ == "__main__":
    sys.exit(main())
