# Stall Warning 的 Codex JSONL 兼容增强建议

> 状态：已拒绝并由 `requirements_2026-07-30_stall-warning-removal.md` 取代；该能力从双宿主骨架及下游更新中移除。  
> 候选目标：`templates/codex/hooks/stall_warning.py`  
> 来源：下游长期运行项目的 Codex transcript 兼容实践，已脱敏

## 1. 结论

建议 BridgeForge 吸收下游 `stall_warning.py` 对 Codex JSONL 的事件兼容能力，
但禁止整文件覆盖。`event_msg`、`response_item` 和多种文本 block 的解析具有明确
通用价值；`token_count` 与 message usage 的合并语义尚未验证，必须先用 fixture
证明不会双计数。

本提案保持现有产品边界：stall warning 只能是非阻塞软提醒，解析失败必须
fail-open，禁止升级成 Stop hook 或提交硬闸。

## 2. 传播四问

1. **属于哪一层**：本文件是元文档需求；采纳后的实现属于
   `templates/codex/hooks/` 产品层。
2. **是否应进入模板**：Codex transcript 兼容是跨项目通用能力，应进入模板；
   下游项目注释、路径和历史背景不得进入。
3. **是否需要版本与 CHANGELOG**：本提案不 bump；产品实现落地时必须 bump，
   并新增 `[product]` CHANGELOG 条目。
4. **是否需要 dogfood**：本提案不改 hook；实现落地时必须同步
   `.codex/hooks/stall_warning.py`，并在真实 Codex fixture 上验证。

## 3. 当前差异

### 3.1 上游模板

当前模板主要解析旧式：

```text
{"message": {"role": "...", "content": [...], "usage": {...}}}
```

它依赖 `message.content` 中的 `text` 和 `tool_use` block。若 Codex transcript
主要输出 `event_msg` 与 `response_item`，模板可能无法还原完整 turn。

### 3.2 下游增强版

下游版另外识别：

- `event_msg.user_message`
- `event_msg.token_count.info.last_token_usage.output_tokens`
- `response_item.type=message`
- `response_item.type=* _call` 形式的工具调用
- 字符串 content
- `text`、`input_text`、`output_text` block

下游版也删除了具体模型名称，使提示保持 Codex 宿主中性。

## 4. 建议直接吸收

### 4.1 统一文本提取

建议保留单一 `_content_text()`：

- content 是字符串时直接返回。
- content 是 block 数组时读取 `text`、`input_text`、`output_text`。
- 非字符串 text 安全忽略。
- 纯 `tool_result` 载体不应被当成新的真实用户 prompt。

可见正文字符数必须复用同一提取函数，禁止解析 turn 和估算 thinking 比例使用
两套不同规则。

### 4.2 支持 `event_msg.user_message`

将其转换成统一的：

```text
("user", text, is_real_prompt)
```

空文本、工具结果载体和缺字段事件不得开启新 turn。

### 4.3 支持 `response_item`

- `type=message`：按 role 和 content 解析。
- `type` 以 `_call` 结尾：记录该 turn 已发生工具调用。
- 其他类型：忽略。

工具调用事件即使没有 assistant 文本，也必须阻止该 turn 被误判为“零工具空转”。

### 4.4 删除具体模型绑定

提示不得写死某个模型名称或版本。Hook 检测的是行为信号，不应把未验证的模型行为
写成产品事实。

### 4.5 保持 fail-open

- 非法 JSON、截断半行、未知事件、缺字段：跳过。
- 文件不存在或读取失败：不阻断。
- 始终 exit `0`。
- 只输出 `[stall]` 软提醒。

## 5. 必须 fixture 后吸收

### 5.1 Usage 来源优先级

下游版同时接受：

1. `message.usage.output_tokens`
2. `event_msg.token_count.info.last_token_usage.output_tokens`

这两个值可能描述同一轮，也可能一个是轮次增量、另一个是累计值。当前没有足够证据
证明二者可以直接相加。

正式实现必须先确定语义，并采用确定性优先级：

```text
同一 turn 有 message usage -> 使用 message usage
否则有 token_count -> 使用经语义确认的 token_count
两者同时存在 -> 禁止相加
```

若真实日志证明 `token_count` 是累计值，必须做差分或只取最后值，禁止逐事件累加。

### 5.2 混合日志的 Turn 聚合

同一 transcript 可能同时出现旧式 `message`、`event_msg` 和 `response_item`。
实现必须证明：

- 同一用户输入只开启一个 turn。
- 同一 assistant 输出只计一次 usage。
- 独立 `*_call` 能归属正确 turn。
- `token_count` 不会错配到下一轮用户输入。

在这些断言通过前，不应把 usage 兼容接入产品模板。

## 6. Fixture 测试矩阵

| 场景 | 断言 |
|---|---|
| 旧式 `message` JSONL | 行为与现模板一致 |
| `event_msg.user_message` | 正确开启一个新 turn |
| `response_item.message` | 正确解析 role 与正文 |
| `response_item.function_call` | 标记 tool use |
| 其他 `*_call` | 标记 tool use |
| 字符串 content | 正确计算正文字符数 |
| `text` / `input_text` / `output_text` 混合 | 文本只计一次 |
| 纯 `tool_result` user event | 不开启真实 turn |
| 仅 message usage | usage 只计一次 |
| 仅 token_count usage | usage 只计一次 |
| 两种 usage 同轮出现 | 不得双计数 |
| 多条累计 token_count | 不得逐条累加 |
| 截断半行或非法 JSON | 静默跳过、exit `0` |
| 缺 role/content/usage | 静默跳过、exit `0` |
| 两轮高 output、零工具、连续 nudge | 触发 `[stall]` |
| 任一轮存在工具调用 | 不触发 |
| 用户给出新实质指令 | 不触发 |
| 可见正文占比高 | 不触发 |

Fixture 必须分别覆盖单格式和混合格式，并把事件序列、预期 turn 列表及最终触发结果
作为确定性断言保存。

## 7. 性能与误报验收

- tail-read 上限保持有界，禁止扫描完整历史 transcript。
- 解析时间必须随读取字节数线性增长。
- 合法长分析不得仅因 usage 双计数触发。
- 工具调用不能因事件独立成行而丢失。
- 新字段缺失时必须退化到旧格式，而不是制造空 turn。
- 提示文案必须明确“概率软提醒，可在正当分析时忽略”。

## 8. 暂不吸收

- 未经 fixture 证明的 usage 直接相加。
- 任何具体模型名称或模型能力判断。
- 下游项目名、绝对路径、业务术语和事故记录。
- 将 stall warning 改成硬阻断。
- 将推断出的 transcript 字段写成已验证契约。
- 为兼容未知格式无限扩大 parser 或 tail-read 范围。

## 9. 建议实施批次

### 批次 A：低风险事件兼容

- 统一 `_content_text()`。
- 支持 `event_msg.user_message`。
- 支持 `response_item.message` 与 `*_call`。
- 支持三种文本 block。
- 移除具体模型文案。

### 批次 B：Usage 语义

- 收集脱敏真实 fixture。
- 确认 `token_count` 是轮次值还是累计值。
- 实现来源优先级和去重。
- 覆盖混合事件流。

### 批次 C：产品化

- 镜像模板与 BridgeForge 自身 `.codex` hook。
- 运行 downstream fixture 与 dogfood。
- bump 版本并记录 `[product]` CHANGELOG。

## 10. 推荐裁定

将本候选判为“通用增量，其中事件解析可直接吸收，usage 合并需验证后吸收”。

先落批次 A 和 fixture 框架；只有同轮双来源不重复、累计值不误加的断言通过后，
才合入 `token_count` usage。这样能解决 Codex 新日志格式漏检，又不会把当前下游
实现中的潜在误报传播到所有项目。
