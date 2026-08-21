# BUG：Windows Codex Hook 弹出可见终端窗口

**状态**：fix-in-progress  
**发现日期**：2026-08-22  
**影响版本**：BridgeForge `1.5.1` 及更早版本  
**影响范围**：Windows Codex App 中的用户级 Native Memory Hook 与项目级受管 Hook

## 结论

Windows Codex App 派发后台 Hook 时，BridgeForge 的 Windows 命令入口会直接启动
`cmd.exe` 或控制台版 PowerShell。终端继承当前项目工作目录，因此用户会偶发看到标题为当前
worktree 路径的空白黑色窗口；耗时数秒的 `Stop` 同步会让窗口更容易被观察到。

这不是项目资产被删除，也不是 Codex 随机关闭终端。根因是后台 Hook 使用了可见控制台入口，
且骨架此前没有禁止此类 GUI 后台命令弹窗的公共红线。

## 现场证据

- 用户级 `hooks.json` 的 Native Memory `SessionStart`、`Stop`、`SessionEnd` 使用
  `cmd.exe /d /c call ...codex_memory_sync_hook.cmd`。
- wrapper 以 `@echo off` 隐藏文本，但不能隐藏承载它的 Windows Terminal 窗口。
- `hook-dispatch.log` 记录到多次耗时约 3～12 秒的 `Stop` 运行，和“偶发、短暂、空白窗口”的
  现场表现一致。
- 截图中的终端标题是 M2 worktree 当前目录，与 Hook 继承会话工作目录的行为一致。

以上证据把根因定位到 BridgeForge Windows Hook 启动方式；Codex App 内部创建终端窗口的
具体实现未验证。

## 修复设计

1. 公共 `AGENTS.md` 增加 Windows 非交互、无人值守命令必须使用无可见控制台窗口入口的红线，
   同时保留用户明确要求可见交互终端的例外。
2. 用户级 Native Memory 改用独立 PowerShell wrapper，并以
   `-NoProfile -NonInteractive -WindowStyle Hidden` 启动。
3. 仅自动迁移内容完全匹配的官方旧 `cmd.exe` handler；第三方或人工修改的 handler 继续
   fail-closed，不静默覆盖。
4. 项目级模板与工厂 dogfood Hook 统一使用隐藏 PowerShell，并显式
   `exit $LASTEXITCODE`，保持原 Python 退出码。
5. 旧 `.cmd` wrapper 暂时保留为精确迁移识别资产；本次不删除任何项目资产。

## 验收标准

- Template 与 dogfood 的全部 Windows Hook 都声明 `NonInteractive`、`WindowStyle Hidden`，
  并原样透传 Python 退出码。
- Native Memory 新 handler 不再直接启动 `cmd.exe`，旧官方 handler 可确定性迁移，漂移
  handler 保持拒绝覆盖。
- Windows 真实子进程测试证明隐藏 PowerShell 能透传非零退出码。
- manifest、fixture、完整自动测试与 dogfood 一致性检查通过。
- 修复版安装到真实用户环境后，Codex App 生命周期 Hook 不再弹出可见终端窗口。

## 六类关闭证据

| 类别 | 当前状态 |
|---|---|
| 源码 | 无窗口 Native Memory launcher、旧版精确迁移、项目 Hook 退出码透传与公共红线已实现；定向 72 项与完整 287 项自动测试通过 |
| 产品传播 | Template 已修改；版本、CHANGELOG、commit 与发布尚未生成 |
| dogfood | 工厂 hooks、AGENTS 与 managed-skeleton 镜像一致；manifest `--check` unchanged |
| fixture | 下游 fixture 3/3 通过：current init 幂等、旧项目确认重建、当前漂移零写入阻断 |
| 真实下游 | 未更新；本轮不直接修改 Stratus、M2、ClaudeBridgeAssist 或 causis_risk_suite |
| runtime | 未验证；需发布并刷新用户级 Hook 后，在真实 Codex App 生命周期中观察 |

本 Bug 保持开放，直到六类证据齐全；禁止只凭单元测试宣称用户桌面弹窗已消失。
