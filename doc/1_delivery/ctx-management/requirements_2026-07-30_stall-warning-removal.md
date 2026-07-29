---
status: implemented
topic: ctx-management
source: downstream JSONL compatibility proposal, superseded by user decision
---

# Stall Warning 移除确认卡

## 目标

从 BridgeForge 的 Codex 与 Claude 骨架中完全移除 `stall_warning.py`，不采纳下游提出的 Codex JSONL 兼容增强。

下游项目执行骨架更新时，也必须删除项目级 `.codex/hooks/stall_warning.py` 与 `.claude/hooks/stall_warning.py`，并撤销对应 hook 注册和 `[stall]` 使用说明。

## 已核实事实

- Codex 模板与 dogfood 都注册了 `stall_warning.py`。
- 当前 Codex 脚本只理解 legacy transcript 结构；下游建议是为其增加 JSONL 兼容。
- 该提醒是非阻断软提醒，不是交易、风控或提交硬闸。

## 已确认规则

- Codex 与 Claude 两套骨架都移除该能力。
- 下游更新强制删除现存脚本，即使项目方曾人工修改。
- 不保留兼容实现、开关、空壳注册或 JSONL fixture。

## 非目标

- 不以其他提醒替代 `[stall]`。
- 不修改其他上下文预算、`[ctx-budget]` 或进度提示机制。

## 计划改动

- 删除两套模板及 BridgeForge dogfood 的脚本，移除 settings/hooks 注册与文档引用。
- 扩展下游更新的受管删除清单，使更新强制移除项目级残留。
- 更新专项 fixture、产品版本记录、CHANGELOG 与原下游提议状态。

## 验收

- Codex / Claude 模板和 dogfood 不再含脚本、注册或 `[stall]` 响应契约。
- 下游 update fixture 证明，即使已有修改过的项目级脚本，更新后也被删除。
- 相关 JSON/配置解析、专项 fixture、全量 downstream harness 与 `git diff --check` 通过。

## 风险

下游项目中人工改过的 `stall_warning.py` 会被更新不可逆删除；这是用户明确确认的强制删除策略。

## 实施与验证记录

- 已移除 Codex / Claude 模板及 BridgeForge dogfood 的脚本、注册和 `[stall]` 入口说明。
- 五份 `bridgeforge_switch.py` 增加受管退役清单；只删除目标宿主的 `stall_warning.py`，链接或目录保持 fail-closed，其他 hook 不受影响。
- 已验证：`.venv\Scripts\python.exe tests\harness\run_downstream_fixture.py --case switch-retired-stall-warning --case switch-script-mirrors`；断言双宿主都会删除人工修改脚本、保留无关 hook 且五份脚本镜像一致。
- 已验证：`.venv\Scripts\python.exe tests\harness\run_downstream_fixture.py` 全量通过。
