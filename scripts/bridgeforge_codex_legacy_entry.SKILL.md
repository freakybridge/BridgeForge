---
name: bridgeforge
description: 一次性迁移旧 /bridgeforge 入口到 bridgeforge-codex；安装新入口后停止，不执行项目更新。
user_invocable: true
user-invocable: true
argument: 仅支持无参数
---

# bridgeforge-codex 一次性迁移入口

本文件只用于旧入口兼容，不包含运行时模板，也不再次执行 updater。

1. 若当前平台不是 Windows，立即停止，禁止下载或写入。
2. 只接受无参数 `/bridgeforge`；其他参数在任何写入前报错。
3. 到达本文件表示已发布旧 updater 已完成兼容 manifest 事务。只读验证新的薄入口：

```text
%USERPROFILE%\.codex\skills\bridgeforge-codex
```

4. 从 `%USERPROFILE%\.bridgeforge\shared-skill-manifest.json` 读取 `bridgeforge-codex` 条目，逐文件核对新目录中的相对路径与 SHA-256；必须包含 `SKILL.md`、`references/` 与 `scripts/bridgeforge_codex_shared_update.ps1`，禁止接受 manifest 外文件代替。
5. 立即停止本轮，不读取项目状态，不执行项目写入，不清理旧资产。明确提示用户新开一轮运行 `$bridgeforge-codex`；新入口会先安装完整 `~/.bridgeforge-codex` 产品 home，再统一展示旧资产退休风险卡。旧入口不会长期保留。

manifest 缺失、目标缺失或任一 hash 不符都停止并报告迁移未完成；禁止再次调用已经退役的 `bridgeforge_shared_update.ps1`。

禁止回退到 `%USERPROFILE%\.agents`、其他本机 clone、当前项目或本地工作副本；禁止绕过受管 updater 手工复制。
