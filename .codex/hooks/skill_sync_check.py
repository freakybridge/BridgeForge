"""用户级 skill 漂移自检 — SessionStart hook（支柱 B / 开机自检）

机制:
1. 定位上游骨架库的 skill 源: ~/.bridgeforge/skills/（旧安装路径仅作 fallback）
   找不到 = 本机没装 bridgeforge → 静默 no-op (对非 bridgeforge 用户零影响,
   范式同 target_cleanup.py 的自门控)。
2. 逐个比对"用户级架子" ~/.agents/skills/<skill> 与上游源的内容哈希:
   - 上游有、架子没        → 缺失 (missing)
   - 两边内容不一致        → 漂移 (divergent: 旧版镜像 or 你的定制)
   只遍历上游出品的 skill, 故架子上的项目专属 skill (如 causis-api) 自然不被波及。
3. 读 repo 根 RETIRED.md 墓碑名单: 已下架却仍赖在架子上的 → 已退役 (retired)。
4. 有任何一类时打印一行 [skill-sync] 到 stdout (SessionStart 注入上下文),
   建议跑 /bridgeforge 同步。

本 hook 只"检测 + 通知", 绝不改任何文件 —— 真正的补/更/删由 /bridgeforge
Step 0 在用户确认下执行 (绝不静默覆盖定制 / 静默删退役)。设计见
docs/skill-distribution-gaps.md「支柱 B」。

范围 (v1, 有意收窄):
- 离线比对本机上游 clone 的工作区, 不 git fetch —— SessionStart 必须快且不能因
  联网失败而拖慢/报错。上游 clone 自身是否落后 GitHub 由用户手动 pull, 另算。
- "已退役"靠 repo 根 RETIRED.md 墓碑名单 (支柱 B 第二块: 退役检测)。退役的 hook
  (项目级, 如 memory_guard) 不在此列, 仍靠手动删。

自产自用: bridgeforge 自身 .codex/ 也挂此 hook。完整 BridgeForge 工厂位于
~/.bridgeforge, 因此它检测的是"工厂源头与 Codex 用户级通用 skill 货架"之间的漂移。
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

# Windows 终端默认不是 UTF-8，中文注入会乱码 → 强制 stdout 用 UTF-8（全 hook 统一约定）
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

# 跳过的目录名 (字节码缓存 / git 元数据 / 隐藏目录另行判)
_SKIP_DIRS = {"__pycache__", ".git"}


def dir_content_hash(root: Path) -> str:
    """对一个 skill 目录的全部文件做内容哈希。

    忽略隐藏文件 / __pycache__ / mtime —— 只认"内容"是否一致, 不被复印产生的
    时间戳差异误报。隐藏的 provenance 标记 (.开头) 也被跳过, 为后续预留。
    """
    h = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")
        )
        for fn in sorted(filenames):
            if fn.startswith("."):
                continue
            fp = Path(dirpath) / fn
            rel = fp.relative_to(root).as_posix()
            h.update(rel.encode("utf-8"))
            try:
                h.update(fp.read_bytes())
            except Exception:
                h.update(b"<unreadable>")
    return h.hexdigest()


def read_retired(upstream_root: Path) -> list[str]:
    """读 repo 根 RETIRED.md 墓碑名单, 返回已退役 skill 名 (每行只取第一列)。

    格式见 RETIRED.md: 每行 `- <name> | <版本> | <日期> | <原因>`。
    缺文件 / 解析失败 → 返回 [] (退役检测降级 no-op, 不影响缺失/漂移检测)。
    """
    names: list[str] = []
    try:
        text = (upstream_root / "RETIRED.md").read_text(encoding="utf-8")
    except Exception:
        return names
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        body = line[2:].split("|")[0].strip()
        if body:
            names.append(body.split()[0])
    return names


def find_upstream(shelf: Path) -> Path | None:
    """定位 BridgeForge 工厂源头，优先新布局，旧布局只作迁移期兼容。"""
    home = Path.home()
    candidates = [
        home / ".bridgeforge" / "skills",
        home / ".agents" / "bridgeforge-home" / "skills",
        home / ".claude" / "skills" / "bridgeforge" / "skills",
        shelf / "bridgeforge" / "skills",
    ]
    for path in candidates:
        if path.is_dir():
            return path
    return None


def main() -> None:
    shelf = Path.home() / ".agents" / "skills"
    upstream = find_upstream(shelf)

    # 自门控: 本机没装 bridgeforge 上游 → 静默退出
    if upstream is None or not shelf.is_dir():
        return

    missing: list[str] = []
    divergent: list[str] = []
    for src in sorted(upstream.iterdir()):
        if not src.is_dir() or src.name in _SKIP_DIRS or src.name.startswith("."):
            continue
        dst = shelf / src.name
        if not dst.is_dir():
            missing.append(src.name)
            continue
        try:
            if dir_content_hash(src) != dir_content_hash(dst):
                divergent.append(src.name)
        except Exception:
            continue

    # 退役: RETIRED.md 墓碑名单里、却还赖在用户级架子上的 skill
    retired = [n for n in read_retired(upstream.parent) if (shelf / n).is_dir()]

    if not missing and not divergent and not retired:
        return

    parts: list[str] = []
    if divergent:
        parts.append(f"{len(divergent)} 个内容不一致（{', '.join(divergent)}）")
    if missing:
        parts.append(f"{len(missing)} 个缺失（{', '.join(missing)}）")
    if retired:
        parts.append(f"{len(retired)} 个已退役待删（{', '.join(retired)}）")
    print(
        "[skill-sync] 用户级通用 skill 与上游骨架不一致："
        + "；".join(parts)
        + "。跑 /bridgeforge 同步（Step 0 逐个给 diff/问删，你的定制不会被静默覆盖或删除）。"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # SessionStart hook 绝不能炸 —— 任何异常都静默放行, 不拖累 session 启动
        sys.exit(0)
