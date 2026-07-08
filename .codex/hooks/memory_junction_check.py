#!/usr/bin/env python3
"""SessionStart hook: memory junction 自愈。

把 memory 纳入项目 git（项目内 `.codex/memory/`），但 Codex 读写走系统路径
`~/.codex/projects/<project-hash>/memory/`。本 hook 在每次 session 开始时静默检查
系统路径是否已是 junction/symlink，不是则恢复链接，让"clone 即恢复"无需人工操作。

三种情形（对齐 portability.md §2.1）：
- 已是 junction/symlink     → noop（稳态，99% 的 session）
- 系统路径不存在 + 项目内有 → 建 junction（场景 B：新机 clone）
- 系统路径是实目录 + 有内容 → 场景 A 首迁：复制进项目 → 系统目录改名 .bak（**不硬删**）→ 建 junction

红线：**绝不硬删可能含数据的目录**。场景 A 用 rename-to-.bak 兜底，任何一步失败即中止并提示人工处理。
非阻塞（始终 exit 0），只在发生动作或异常时打印一行。

可移植：项目无关。repo root 取自 hook 自身路径（`.codex/hooks/` 上两级），
project-hash 按 Codex 编码规则（路径分隔符 + `:` → `-`，Windows 盘符小写）从 repo root 推导。
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

# repo root = 本文件的 .codex/hooks/ 上两级
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PROJECT_MEMORY = REPO_ROOT / ".codex" / "memory"


def _is_link(p: Path) -> bool:
    """junction（Windows）或 symlink（Unix）都算已链接。"""
    if p.is_symlink():
        return True
    # Windows junction：is_symlink() 对 junction 返回 False，需额外判定 —— realpath 解到别处即链接。
    # 两边都过 normcase(abspath) 再比，避免大小写/分隔符未规范化时把实目录误判成链接。
    try:
        norm = os.path.normcase(os.path.abspath(str(p)))
        real = os.path.normcase(os.path.realpath(str(p)))
        return os.path.isdir(p) and real != norm
    except Exception:
        return False


def _project_hash(root: Path) -> str:
    """按 Codex 编码规则把绝对路径转 project-hash。

    实测规则（从 `~/.codex/projects/` 下真实目录名反推）：**每个非字母数字字符替换为
    单个 `-`，字母大小写原样保留**。分隔符、`_`、`.`、空格等都算非字母数字，各映射一个
    `-`（不折叠连续分隔符，故 `d:\\` 段产出 `d--`）。
    例：`d:\\Quant\\setup_agent` → `d--Quant-setup-agent`；`C:\\Users\\bridg` → `C--Users-bridg`。

    注意盘符大小写：Windows 上 `Path.resolve()` 会把盘符规范成**大写**（`D:`），
    而 Codex 建目录时用的是启动 cwd 的原始大小写（可能是小写 `d`）。二者大小写
    可能不一致，但 **Windows 文件系统大小写不敏感**，`exists()`/junction 判定照样命中同一目录，
    故此处不做大小写归一（保留 re.sub 的原样大小写即可）。Unix 无盘符、路径串一致，亦无此问题。

    （旧实现只替换 `: \\ /` 且强制盘符小写 —— 漏了 `_`/`.`（真字符差异，大小写不敏感也救不回），
    在路径含下划线/点的项目上算出错误 hash，hook 静默失效。本仓库 `setup_agent` 正中此坑。）
    """
    return re.sub(r"[^A-Za-z0-9]", "-", str(root))


def _system_memory_path() -> Path | None:
    """推导系统 memory 路径；父目录 `~/.codex/projects/<hash>/` 不存在则返 None（不瞎建）。"""
    h = _project_hash(REPO_ROOT)
    proj_dir = Path.home() / ".codex" / "projects" / h
    if not proj_dir.exists():
        return None
    return proj_dir / "memory"


def _make_junction(link: Path, target: Path) -> bool:
    """建 junction（Windows）/ symlink（Unix）。成功返 True。"""
    try:
        if os.name == "nt":
            import subprocess
            r = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True, text=True, timeout=10,
            )
            return r.returncode == 0
        os.symlink(str(target), str(link))
        return True
    except Exception as e:
        print(f"[memory-junction] 建链接失败: {e}")
        return False


def main() -> int:
    sys_mem = _system_memory_path()
    if sys_mem is None:
        # 项目目录在 ~/.codex/projects 下没有对应 hash → 该机尚未用 Codex 打开过本项目，跳过
        return 0

    # 稳态：已是 junction/symlink → 静默 noop
    if sys_mem.exists() and _is_link(sys_mem):
        return 0

    # 场景 B：系统路径不存在 + 项目内 memory 已存在 → 直接建 junction
    if not sys_mem.exists():
        if not PROJECT_MEMORY.exists():
            return 0  # 两边都没有，无可恢复
        sys_mem.parent.mkdir(parents=True, exist_ok=True)
        if _make_junction(sys_mem, PROJECT_MEMORY):
            print(f"[memory-junction] 已恢复链接（新机 clone）: {sys_mem} → {PROJECT_MEMORY}")
        return 0

    # 系统路径存在但不是链接 = 实目录
    sys_has_content = any(sys_mem.iterdir())
    proj_has_content = PROJECT_MEMORY.exists() and any(PROJECT_MEMORY.iterdir())

    # 场景 A：首迁 — 系统是实目录、项目内尚无（或空）→ 复制进项目，系统改名 .bak，建 junction
    if sys_has_content and not proj_has_content:
        try:
            PROJECT_MEMORY.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(sys_mem, PROJECT_MEMORY, dirs_exist_ok=True)
        except Exception as e:
            print(f"[memory-junction] 场景A 复制失败，已中止（未动原目录）: {e}")
            return 0
        # 不硬删 — 改名 .bak 兜底
        bak = sys_mem.with_name("memory.premigrate.bak")
        try:
            if bak.exists():
                print(f"[memory-junction] {bak} 已存在，请人工清理后重试；本次跳过")
                return 0
            sys_mem.rename(bak)
        except Exception as e:
            print(f"[memory-junction] 系统目录改名失败，已中止: {e}")
            return 0
        if _make_junction(sys_mem, PROJECT_MEMORY):
            print(
                f"[memory-junction] 首次迁移完成: 内容已入项目 {PROJECT_MEMORY}，"
                f"原系统目录备份为 {bak.name}，junction 已建。确认无误后可删 .bak"
            )
        return 0

    # 系统是实目录且项目内也有内容 → 不敢自动合并（可能冲突/丢数据），提示人工
    print(
        "[memory-junction] 系统 memory 与项目 memory 同时有内容，无法安全自动合并 — "
        "请人工核对后手动建 junction（见 rules/portability.md §2.1）"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
