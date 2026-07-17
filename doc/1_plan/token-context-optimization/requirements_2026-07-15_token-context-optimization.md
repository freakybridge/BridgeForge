# 需求：Codex token 与 skill 上下文优化
> 日期：2026-07-15
> 状态：awaiting_trial
> 入口：用户要求降低新任务启动和长对话后期 token 消耗，并将 BridgeForge 产品内全部 skill 按统一标准整理。
> 调用来源：`develop` → `confirm` → `collab`
> 后续交接：并行实现、独立验证、用户试用

## 背景与目标

- 修复 Codex 当前 session 日志 token 读取失真，区分真实新任务、长任务恢复与 cache miss。
- 在上下文达到高成本区间前提醒交接，使用短 snapshot 在新任务中接续。
- 将启动 memory 从“携带历史正文”改为“短索引 + 按需检索”。
- 整理根 `bridgeforge` 与 `skills/*` 共 19 个产品 skill，统一触发描述、正文结构和渐进加载。

## 非目标

- 不修改系统内置、插件或仓库外部 skill（例如 `causis-api`）。
- 不为 skill 新增 `agents/openai.yaml`。
- 不删除原始 memory，不改变 skill 的业务能力。
- 不自动执行 git add、commit 或 push。

## 已核实事实

- 真正新任务首轮约 26k input tokens；曾被判断为 26 万“新增输入”的案例实际是旧长任务跨日恢复后 cache miss。
- 当前 Codex session 使用 `event_msg.token_count.payload.info.last_token_usage`；现有 `context_warning.py` 只识别旧 `assistant.usage`，会退化为 transcript 文件大小估算。
- 根 `SKILL.md` 约 785 行、9.7k tokens；其余 18 个通用 skill 单体均低于约 1k tokens。
- 当前自动注入 memory 约 4.2k tokens，skills 清单约 3.5k tokens。

## 已确认规则

- token 预警支持 `ECONOMY`、`HANDOFF`、`CRITICAL`、`CACHE_MISS`，cached token 不重复计数。
- snapshot 交接摘要目标不超过约 1,200 tokens；新任务只读取短交接卡，不继承完整 transcript。
- memory 启动层只保留稳定偏好、仓库定位、关键词和详细资料指针。
- 19 个产品 skill 全部按 BridgeForge 兼容标准整理；保留 `user_invocable` / `argument`，需要时保留 `model`。
- 不新增 `agents/openai.yaml`。

## 拟修改

- `templates/codex/hooks/` 与 dogfood `.codex/hooks/` 的 token、skill metadata 检查。
- `templates/codex/AGENTS.md`、根 `AGENTS.md` 与相关 rule 契约。
- `skills/snapshot`、`skills/resume`、根 `SKILL.md` 与全部 `skills/*/SKILL.md`。
- Codex memory 索引脚本、测试、版本、CHANGELOG 与本需求包。

## 验收清单

- [x] 当前 Codex token 日志读取准确，cached 不重复计数，窗口优先使用日志值。
- [x] 80k / 140k / 200k 与 cache miss 样例产生正确级别。
- [x] 新任务首轮不误报，旧长任务恢复不再误判为新任务启动。
- [x] snapshot 交接内容受控，`resume latest` 在状态一致时不额外空转一轮。
- [x] memory 热区受字符预算约束，完整历史仍可按需定位。
- [ ] 全局 `memory_summary.md` 压缩请求已提交，但仍需在后续新任务确认已生效并重新测首轮成本。
- [x] 根 `bridgeforge` + 18 个通用 skill 全部通过 metadata、reference、触发与停止场景检查。
- [x] 根 `bridgeforge` 入口降至 200-300 行目标区间，复杂分支按需读取 references。
- [x] 模板 / dogfood 镜像、downstream fixture 与相关脚本验证通过。

## 暂缓项

- 平台固定基础提示、动态工具 schema 和插件内部 skill 不在 BridgeForge 控制范围内。
- `agents/openai.yaml` UI 元数据明确不进入本轮。

## 合理假设与风险

- UserPromptSubmit 只能读取上一轮用量，预警天然晚一轮。
- skill description 过度压缩会损害自动触发，必须配正反触发用例。
- 根 `bridgeforge` 拆分是最高风险项，必须在其他批次稳定后单独整合验证。
- 个人 Codex memory 只能按平台规定提交更新说明，不能直接覆盖生成文件。

## 实施计划

1. 并行整理互不重叠的 skill 批次与根 `bridgeforge` 入口。
2. 主线修复 token 读取、成本档位、memory 索引、metadata 检查和测试。
3. 汇总镜像、文档、版本、CHANGELOG，运行完整验证。
4. 独立 review agent 依据本卡和真实 diff 复核。

## 实施记录

- 2026-07-15：用户确认完整需求卡并选择开始实施。
- 2026-07-15：三个并行批次完成 19 个 skill 标准化；主线完成 token、memory、metadata、报告脚本、镜像、版本与测试整合。
- 2026-07-15：已按平台约束向个人 memory 更新收件箱提交摘要压缩请求；未直接覆盖生成的 memory 文件。

## 验证记录

- `python -B tests/harness/test_context_warning.py`：6 项通过，覆盖当前/旧日志、cached 口径、档位、cache miss、动态窗口、命令豁免、stdin/stdout、尾部读取与 fallback。
- `python -B tests/harness/test_context_cost_report.py`：通过，确认首轮真实 token 可读且不输出 prompt 正文。
- `python -B tests/harness/test_memory_rebuild_index.py`：通过，确认 pinned + Active + 索引外壳整体不超过 6000 字符，单条摘要不超过 180 字。
- `python -B tests/harness/test_bridgeforge_root_skill.py`：3 项通过，覆盖变量赋值顺序、Codex 产品清单和一层 reference。
- `python -B tests/harness/run_downstream_fixture.py`：27 项全部通过。
- `python -B .codex/hooks/skill_metadata_check.py`：通过，19 个 skill 及根 reference 无硬错误。
- 当前任务实测：首轮 26,166 tokens（cached 10,496）；可见项中仓库 AGENTS 约 1.3k、全局 memory 摘要约 5.6k，其余约 18.8k 为运行时基础提示、完整工具/skill schema 等未逐项记录内容。
- 独立 review 首轮发现根 skill 路径展开错误、init/update 产品清单遗漏和 pinned 预算盲区；均已修复并补回归测试。全局 memory 是否生效保留为用户试用项。

## 用户试用反馈

- 待交付后填写。
