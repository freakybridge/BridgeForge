#!/usr/bin/env python3
"""SessionStart hook: Rust target/ 体积治理 (两遍 pass, 后台执行, 不阻塞启动).

背景: cargo-sweep --time 看文件访问时间 (atime), 但 Windows 上 Defender 实时扫描 /
每次 build / 目录遍历都会刷新 atime, 使陈年产物长期"看起来热"而清不动 —— atime 在
开着杀软的 Windows 上不是可靠的冷热信号。所以全部改用可信信号: 文件体积 + 写入时间
(mtime, 不受扫描刷新影响)。

仅 Rust 项目生效 (检测 Cargo.toml), 非 Rust 项目静默 no-op —— 故可无条件挂在
SessionStart, 对其他语言项目零影响; 项目后来新增 Rust crate 也会自动激活。

两遍 pass (共用 INTERVAL_HOURS 节流 + 后台 worker):

  L1 incremental/ 体积触发清理
    incremental/ 通常是 target/ 膨胀的最大头之一且 100% 可再生。总体积 > 阈值时,
    重命名 incremental -> incremental.trash (瞬间, cargo 立刻能建新的), 再后台慢删。
    cargo 下次 build 自动重建 (只重编本地 crate 一次, deps 保留)。

  L2 deps/ 多版本变体裁剪
    deps/ 里同一 crate 的旧 hash 变体会无限堆积 (每次输入变化 cargo 产新 hash, 旧的
    永不回收), 本地 workspace crate 因频繁重编尤甚, 长期可占 target/ 的绝大头。
    按 crate 分组, 每组按 hash 的 max mtime 排序, 只留最新 N 个变体, 删更旧的。
    当前 build 只链最新变体 -> 删旧的下次几乎不重造 (留 N=2 给足安全余量, 当前变体
    即便是第二新也存活; 只动 >=3 变体的 crate, 1-2 变体的稳定 deps 不碰)。
    无 hash 的当前产物 (最终 bin / .d 等) 正则不匹配 -> 永不删。

用法:
  (无参)     SessionStart 生产路径: 节流检查 -> spawn 后台 worker, 跑 L1 + L2
  --worker   内部: 真正执行 L1 + L2 (由生产路径 spawn, 勿手动调)
  --dry-run  自测: 前台报告两遍 pass 会做什么, 不删、不改名、不写时间戳
"""
import os
import re
import sys
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]  # .claude/hooks/ -> 项目根
RUNTIME_DIR = PROJECT_ROOT / ".runtime"
STAMP = RUNTIME_DIR / "last_target_cleanup"
LOG = RUNTIME_DIR / "target_cleanup.log"
INTERVAL_HOURS = 24      # 检查频率(节流)

# --- L1 incremental ---
THRESHOLD_GB = 30        # incremental/ 超过此体积才清,避免白白浪费一次重编
TRASH_SUFFIX = ".trash"

# --- L2 deps 变体裁剪 ---
DEPS_KEEP_VARIANTS = 2   # 每个 crate 保留最新 N 个 hash 变体(mtime 排序),删更旧的
DEPS_MIN_FREE_GB = 5     # deps 可回收量低于此则跳过,避免频繁扰动 live 目录
# 文件名: [lib]<crate>-<16hex hash>[.ext]。crate 可含 - 和 _;hash 锚定在扩展名前。
# 无 hash 的当前产物(最终 bin / .d 等)不匹配 -> 永不删。
DEPS_RE = re.compile(r"^(?:lib)?(.+)-([0-9a-f]{16})(?:\.[0-9A-Za-z.]+)?$")


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


def deps_dirs(ws):
    """workspace 下所有 deps 目录 (与 incremental_dirs 同样 ** 覆盖交叉编译)。"""
    target = ws / "target"
    if not target.exists():
        return []
    return [p for p in target.glob("**/deps") if p.is_dir()]


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


def plan_deps_prune(deps_dir, keep):
    """扫 deps_dir,按 crate 分组,每组保留最新 keep 个 hash 变体,其余进删除列表。

    返回 (to_delete:[(path,size)], freed_bytes:int, stats:{crates,unmatched})。
    一个 hash 变体的代表 mtime = 该 hash 下所有文件(.rlib/.rmeta/.d 等)的最大 mtime,
    保证同一次 build 产物整体保留/整体删除。
    """
    groups = defaultdict(lambda: defaultdict(list))  # crate -> hash -> [(path,size,mtime)]
    unmatched = 0
    try:
        entries = list(os.scandir(deps_dir))
    except OSError:
        return [], 0, {"crates": 0, "unmatched": 0}
    for entry in entries:
        try:
            if not entry.is_file():
                continue
        except OSError:
            continue
        m = DEPS_RE.match(entry.name)
        if not m:
            unmatched += 1
            continue
        try:
            st = entry.stat()
        except OSError:
            continue
        groups[m.group(1)][m.group(2)].append((entry.path, st.st_size, st.st_mtime))

    to_delete = []
    freed = 0
    for _crate, hashes in groups.items():
        if len(hashes) <= keep:
            continue
        ranked = sorted(
            hashes.items(),
            key=lambda kv: max(t for *_rest, t in kv[1]),
            reverse=True,
        )
        for _h, files in ranked[keep:]:
            for path, size, _mt in files:
                to_delete.append((path, size))
                freed += size
    return to_delete, freed, {"crates": len(groups), "unmatched": unmatched}


def _incremental_pass(ws, dry):
    """L1: incremental/ 体积触发清理。返回 True 表示已干净处理(或无需处理),
    False 表示该清但被占用 -> 调用方应跳过写时间戳,下次 session 尽快重试。"""
    dirs = incremental_dirs(ws)
    total = sum(dir_size_bytes(d) for d in dirs)
    total_gb = total / (1024 ** 3)

    if dry:
        listing = ", ".join(str(d.relative_to(ws)) for d in dirs) or "(none)"
        print(f"[target-cleanup] L1 incremental 目录: {listing}")
        print(f"[target-cleanup] L1 incremental 总体积: {total_gb:.1f} GB  (阈值 {THRESHOLD_GB} GB)")
        if total_gb < THRESHOLD_GB:
            print("[target-cleanup] L1 (dry-run) 未达阈值 -> 不清理")
        else:
            print(f"[target-cleanup] L1 (dry-run) 会清掉以上 {total_gb:.1f} GB")
        return True

    if total_gb < THRESHOLD_GB:
        log_line(f"skip incremental: {total_gb:.1f} GB < {THRESHOLD_GB} GB")
        return True

    renamed = []
    for d in dirs:
        trash = d.with_name(d.name + TRASH_SUFFIX)
        shutil.rmtree(trash, ignore_errors=True)  # 清旧残留
        try:
            d.rename(trash)          # 瞬间; build 占用时会抛异常
            renamed.append(trash)
        except OSError as e:
            log_line(f"incremental rename skip {d} (in use?): {e}")

    if not renamed:
        log_line("incremental nothing renamed (all in use?), retry next session")
        return False

    log_line(f"incremental freed ~{total_gb:.1f} GB, deleting {len(renamed)} trash dir(s) in background")
    for trash in renamed:
        shutil.rmtree(trash, ignore_errors=True)
    log_line("incremental trash deletion done")
    return True


def _deps_pass(ws, dry):
    """L2: deps/ 多版本变体裁剪,每库留最新 DEPS_KEEP_VARIANTS 个。"""
    for deps in deps_dirs(ws):
        to_del, freed, stats = plan_deps_prune(deps, DEPS_KEEP_VARIANTS)
        freed_gb = freed / (1024 ** 3)
        rel = deps.relative_to(ws)

        if dry:
            print(
                f"[target-cleanup] L2 {rel}: {stats['crates']} crates, "
                f"删 {len(to_del)} 文件 释放 {freed_gb:.1f} GB "
                f"(每库留最新 {DEPS_KEEP_VARIANTS} 变体, 未匹配 {stats['unmatched']} 文件跳过)"
            )
            continue

        if freed_gb < DEPS_MIN_FREE_GB:
            log_line(f"skip deps {rel}: only {freed_gb:.1f} GB reclaimable < {DEPS_MIN_FREE_GB} GB")
            continue

        deleted = errs = 0
        got = 0
        for path, size in to_del:
            try:
                os.remove(path)
                deleted += 1
                got += size
            except OSError:
                errs += 1  # 当前 build 锁定的最新变体不在删除集,这里多半是残留竞态
        log_line(
            f"deps {rel}: deleted {deleted} files (~{got / (1024 ** 3):.1f} GB), "
            f"{errs} skipped (locked?), kept newest {DEPS_KEEP_VARIANTS}/crate"
        )


def run_worker(dry=False):
    ws = find_workspace()
    if ws is None:
        if dry:
            print("[target-cleanup] 非 Rust 项目 (无 Cargo.toml),跳过")
        return

    clean = _incremental_pass(ws, dry)
    _deps_pass(ws, dry)

    if not dry and clean:
        stamp_now()


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
    print("[target-cleanup] 后台治理 target/ (L1 incremental 超 30GB 清 + L2 deps 每库留最新 2 变体,详见 .runtime/target_cleanup.log)")


if __name__ == "__main__":
    main()
