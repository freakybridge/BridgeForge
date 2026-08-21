---
status: fix-in-progress
severity: high
scope: bridgeforge-codex old-project destructive rebuild
reported_at: 2026-08-21
downstream: D:\Quant\StratusAgent; D:\Quant\CodexWorktree\1d62\StratusAgent
target_product_version: 1.5.1
---

# BUG：旧项目重建无法保留项目映射文件

## 现象

StratusAgent 1.4.11 与 M2 worktree 1.4.25 进入 destructive rebuild 时，Planner 将
`.codex/find-doc.map.md` 和 `.codex/sync-docs.map.md` 报为未知 `.codex` 结构并零写阻断。

两个文件分别承载 `$find-doc` 的项目 topic/rule 数据和 `$sync-docs` 的源码/文档映射。删除会
造成项目能力损失；临时移出、重建后补回会绕过 `PreservationManifest` 事务合同。

## 根因

`_project_asset_candidates()` 只识别 AGENTS 项目区、canonical Hook bundle、pre-commit 项目
扩展、rules、memory 与 Skills。rebuild inventory 因而没有稳定 asset id 能表达两个合法项目
映射，只能按未知结构 fail-closed。

## 修复

- 为两个精确路径增加稳定 `R:project-map:*` asset id；
- 两者只在实际存在且为安全普通文件时进入 `required-preserve`；
- inventory 自动保留其原始 bytes，不生成删除 action；
- reparse、目录或其他不安全对象继续零写阻断；
- 禁止用 glob 扩大到其他 `.codex/*.map.md`。

## 验证与关闭条件

- 单元测试覆盖 required-preserve、字节级不变、不安全路径零写阻断；
- downstream fixture 覆盖旧项目 rebuild、Apply 与 no-op replan；
- 工厂完整测试、manifest、结构与 mirror drift 硬闸通过；
- 独立 agent 审计代码、测试、文档和传播面；
- StratusAgent 真实下游完成 rebuild 后，两个映射 hash 与升级前一致；
- M2 另行串行验证，不与 StratusAgent 主工作区并发写入。
