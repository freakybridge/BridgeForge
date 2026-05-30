#!/usr/bin/env python3
"""SessionStart hook: Rust target/ 增量缓存 (incremental/) 体积触发式清理.

背景: cargo-sweep --time 看文件访问时间 (atime), 但 Windows 上 Defender 实时扫描 /
每次 build / 目录遍历都会刷新 atime, 使陈年产物长期"看起来热"而清不动 —— atime 在
开着杀软的 Windows 上不是可靠的冷热信号。所以改用可信信号: incremental/ 子目录体积。
它通常是 target/ 膨胀的最大头且 100% 可再生, 删整个目录绝对安全 —— cargo 下次 build
自动重建 (只重编本地 crate 一次, deps 保留)。

仅 Rust 项目生效 (检测 Cargo.toml), 非 Rust 项目静默 no-op —— 故可无条件挂在
SessionStart, 对其他语言项目零影响; 项目后来新增 Rust crate 也会自动激活。

策略:
- 每次 SessionStart 检查 (INTERVAL_HOURS 节流), incremental/ 总体积 > THRESHOLD_GB 才动手。
- 重命名 incremental -> incremental.trash (瞬间, cargo 立刻能建新的), 再后台慢删 .trash。
- 量体积 + 删除都在后台 worker 进程, 不阻塞 session 启动。

用法:
  (无参)     SessionStart 生产路径: 节流检查 -> spawn 后台 worker
  --worker   内部: 真正量体积 + 重命名 + 删除 (由生产路径 spawn, 勿手动调)
  --dry-run  自测: 前台量体积 + 报告会删什么, 不删、不改名、不写时间戳
"""
import os
import sys
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .claude/hooks/ -> 项目根
RUNTIME_DIR = PROJECT_ROOT / ".runtime"
STAMP = RUNTIME_DIR / "last_target_cleanup"
LOG = RUNTIME_DIR / "target_cleanup.log"
INTERVAL_HOURS = 24      # 检查频率(节流)
THRESHOLD_GB = 30        # incremental/ 超过此体积才清,避免白白浪费一次重编
TRASH_SUFFIX = ".trash"


def find_workspace():
    """返回含 Cargo.toml 的目录 (项目根优先,再扫一层子目录)。非 Rust 项目返回 None。"""
    if (PROJECT_ROOT / "Cargo.toml").exists():
        return PROJECT_ROOT
    for sub in sorted(PROJECT_ROOT.glob("*/Cargo.toml")):
        return sub.parent
    return None


def incremental_dirs(ws):
    """workspace 下所有 incremental 目录。

    用 ** 递归挖到底,既覆盖普通编译 (target/debug|release/incremental),
    也覆盖交叉编译 (target/<triple>/debug/incremental, 多埋一层)。
    """
    target = ws / "target"
    if not target.exists():
        return []
    return [p for p in target.glob("**/incremental") if p.is_dir()]


def dir_size_bytes(path):
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.stat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total


def due():
    if not STAMP.exists():
        return True
    try:
        last = datetime.fromisoformat(STAMP.read_text().strip())
    except Exception:
        return True
    return datetime.now(timezone.utc) - last >= timedelta(hours=INTERVAL_HOURS)


def log_line(msg):
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(f"{ts} {msg}\n")
    except OSError:
        pass


def stamp_now():
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    STAMP.write_text(datetime.now(timezone.utc).isoformat())


def run_worker(dry=False):
    ws = find_workspace()
    if ws is None:
        if dry:
            print("[target-cleanup] 非 Rust 项目 (无 Cargo.toml),跳过")
        return

    dirs = incremental_dirs(ws)
    total = sum(dir_size_bytes(d) for d in dirs)
    total_gb = total / (1024 ** 3)

    if dry:
        listing = ", ".join(str(d.relative_to(ws)) for d in dirs) or "(none)"
        print(f"[target-cleanup] incremental 目录: {listing}")
        print(f"[target-cleanup] incremental 总体积: {total_gb:.1f} GB  (阈值 {THRESHOLD_GB} GB)")
        if total_gb < THRESHOLD_GB:
            print("[target-cleanup] (dry-run) 未达阈值 -> 不会清理,未删任何文件、未写时间戳")
        else:
            print(f"[target-cleanup] (dry-run) 会清掉以上 {total_gb:.1f} GB,未删任何文件、未写时间戳")
        return

    # 生产 worker
    if total_gb < THRESHOLD_GB:
        log_line(f"skip: incremental {total_gb:.1f} GB < {THRESHOLD_GB} GB")
        stamp_now()
        return

    renamed = []
    for d in dirs:
        trash = d.with_name(d.name + TRASH_SUFFIX)
        shutil.rmtree(trash, ignore_errors=True)  # 清旧残留
        try:
            d.rename(trash)          # 瞬间; build 占用时会抛异常
            renamed.append(trash)
        except OSError as e:
            log_line(f"rename skip {d} (in use?): {e}")

    if not renamed:
        log_line("nothing renamed (all in use?), will retry next session")
        return  # 不写时间戳 -> 下次 session 再试

    stamp_now()
    log_line(f"freed ~{total_gb:.1f} GB, deleting {len(renamed)} trash dir(s) in background")
    for trash in renamed:
        shutil.rmtree(trash, ignore_errors=True)
    log_line("trash deletion done")


def main():
    if "--dry-run" in sys.argv:
        run_worker(dry=True)
        return
    if "--worker" in sys.argv:
        run_worker(dry=False)
        return

    # 生产路径 (SessionStart 无参): 快速节流检查 -> spawn 后台 worker -> 立即返回
    ws = find_workspace()
    if ws is None:
        return
    if not due():
        return

    cmd = [sys.executable, str(Path(__file__).resolve()), "--worker"]
    try:
        kwargs = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
        else:
            kwargs["start_new_session"] = True
        subprocess.Popen(cmd, **kwargs)
    except Exception as e:
        print(f"[target-cleanup] worker 启动失败: {e}")
        return
    print("[target-cleanup] 后台检查 incremental 缓存 (超 30GB 则清,详见 .runtime/target_cleanup.log)")


if __name__ == "__main__":
    main()
