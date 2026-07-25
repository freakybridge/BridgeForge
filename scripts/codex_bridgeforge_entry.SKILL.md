---
name: bridgeforge
description: 将旧 Codex /bridgeforge 入口转交给已安装在用户级 Codex skills 目录的完整 BridgeForge command bundle。
version: 0.64.0
user_invocable: true
user-invocable: true
argument: 仅支持无参数，或 switch claude|codex
model: sonnet
---

# BridgeForge Codex 兼容入口

本文件只用于旧入口兼容，不包含运行时模板，也不执行 Git 操作。

1. 若当前平台不是 Windows，立即停止，禁止下载或写入。
2. 只接受无参数 `/bridgeforge` 或 `/bridgeforge switch <claude|codex>`；其他参数直接报错。
3. 将完整安装包固定为：

```text
%USERPROFILE%\.codex\skills\bridgeforge
```

4. 确认该目录同时包含 `SKILL.md`、`doc/runtime/`、`templates/` 与 `scripts/bridgeforge_shared_update.ps1`，然后读取其中的 `SKILL.md`，按其说明继续，并原样传递合法参数。

任一文件缺失都停止，并要求重新运行 Windows 首次安装脚本。

禁止回退到 `%USERPROFILE%\.agents`、`%USERPROFILE%\.bridgeforge`、其他本机 clone、当前项目或本地 BridgeForge 工作副本；禁止执行 `git pull` / `git clone` 猜测内容源。
