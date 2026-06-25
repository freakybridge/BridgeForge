# -*- coding: utf-8 -*-
"""SessionStart hook: 从项目 .claude/settings.json 强制剔除 effortLevel。

为什么是 hook 而非 rule：项目级 effortLevel 合并优先级高于用户级全局（Project > User），
一旦下游项目流入它，就会顶掉"顺手的 /config slider / /effort"全局调节入口、把全套
"全局统一管 effort + SessionEnd 自动还原"机制架空。散文 rule 拦不住"流入"（sync/clone/手加），
必须机检强制——这是本骨架的特征：能机检的红线一律 hook 化，不留主观空间。
（覆盖关系与决策全图见 memory effort-config-layering。）

自愈式（仿 memory_junction_check）：每次 SessionStart 跑，发现项目 settings.json 有
effortLevel 就原子删除（json 读改写 + temp+os.replace + .bak），其余键一字不动；没有则静默 no-op。
仅作用于 git 跟踪的项目 settings.json；settings.local.json（个人本机覆盖）不碰。
"""
import json, os, shutil, tempfile

SETTINGS = os.path.join(".claude", "settings.json")  # 相对项目根（SessionStart hook 的 cwd）


def main():
    if not os.path.isfile(SETTINGS):
        return
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return  # 解析失败 → 不动，绝不阻塞会话启动
    if "effortLevel" not in data:
        return  # 没有 → 静默 no-op（绝大多数会话走这里）

    removed = data.pop("effortLevel")
    try:
        shutil.copy2(SETTINGS, SETTINGS + ".bak")
        d = os.path.dirname(SETTINGS) or "."
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, SETTINGS)
        # ASCII-only 通知（避免中文在某些环境糊码）：effort 一律全局管，项目级被剔除
        print("[enforce-no-effortlevel] removed project-level effortLevel='%s' from "
              ".claude/settings.json (effort is governed at user-global level only)." % removed)
    except Exception:
        return  # 写失败 → .bak 保有改前状态


if __name__ == "__main__":
    main()
