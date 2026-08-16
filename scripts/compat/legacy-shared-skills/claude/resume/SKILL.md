---
name: resume
description: 从 .runtime/session_state/ 读取一份 snapshot，在核对当前 Git 状态后接续工作；新会话要继续上次任务时使用，支持 latest 直取最新快照或无参数选择候选。
user_invocable: true
argument: 可选——latest 或指定 snapshot 文件名
model: sonnet
---

# 从 snapshot 接续

## 定位与边界

只读取一张短交接卡，不继承旧 transcript，也不把 snapshot 写入长期 memory。Git 状态一致时直接接续；只有不一致或用户未指定候选时才停下来询问。

## 输入

| 输入 | 选择方式 |
|------|----------|
| `latest` | 直接选择最新一份 snapshot |
| 指定文件名 | 选择该文件 |
| 无参数 | 列出最近 10 份候选，让用户选一份 |

## 核心流程

1. 选择 snapshot：
   - `latest`：按修改时间取 `.runtime/session_state/*.md` 最新一份，不展示候选列表。
   - 指定文件名：只接受 `.runtime/session_state/` 内存在的文件。
   - 无参数：列出最近 10 份的时间和主题摘要，使用结构化提问让用户选择，然后结束本轮。
2. 完整读取选定的一份 snapshot；禁止同时读取其他候选。
3. 运行 `git status`，对比 snapshot 记录的 branch 与未提交文件集合：
   - 一致：不要再问“是否继续”，直接进入下一步。
   - 不一致：列出差异并停下，询问用户要以当前状态继续、另存现场，还是放弃接续；不得自动 stash、覆盖或还原。
4. 从 branch、任务主题和 P0 TODO 提取 2–4 个关键词：
   - 先查当前 agent 的 `memory/MEMORY.md`。
   - 热区无匹配且历史决策会影响当前任务时，再调用 `find-memory`，只读最相关的 1–2 个文件。
5. 汇总上次状态、已完成、关键决定、未验证项、改动文件和下一步，并从第一条可执行动作继续工作。
6. 从“已完成 / 下一步”提取 3–12 字的“动词 + 对象”主题，建议用户把当前任务改成该名称；用户拒绝后不再追问。

## 输出与验证

输出必须包含：snapshot 文件名、当前 branch、Git 对齐结果、未验证项和即将执行的下一步。只有实际对比过 `git status` 才能写“状态一致”。

## 停止条件

- 没有 snapshot 或指定文件不存在：报告事实并停止。
- 无参数尚未选定候选：列出候选后停止。
- Git 状态不一致：展示差异并等待用户决定。
- snapshot 损坏或缺少足以对齐的状态：标记缺口，不猜测接续。

## 禁止事项

- 禁止在 Git 状态一致时额外询问一次“准备继续吗”。
- 禁止盲信 snapshot、一次读取多份 snapshot，或读取旧 transcript。
- 禁止自动 stash、覆盖、还原用户当前改动。
- 禁止把短期 snapshot 内容写入长期 memory。
- 禁止使用“继续工作”“新任务”等无动作语义的建议名称。
