---
name: archive-scan
description: 扫描 doc/2_pending/ 中疑似已完成的文档，给出归档候选，经用户逐项确认后使用 git mv 移至 doc/4_archive/ 并同步 doc/README.md；清理已完成 pending 文档时使用。
user_invocable: true
argument: 无
model: haiku
---

# 扫描并归档完成文档

## 定位与边界

脚本只负责候选打分；用户决定是否移动。扫描范围是 `doc/2_pending/`，`doc/0_architecture/TODO-INDEX.md` 不是候选。

## 输入

无需参数。任何移动都必须以本轮用户明确选择的候选为准。

## 核心流程

1. 运行当前 agent 的扫描脚本：

   ```bash
   # Claude
   .venv/Scripts/python.exe .claude/scripts/archive_scan.py --json
   # Codex
   .venv/Scripts/python.exe .codex/scripts/archive_scan.py --json
   ```

2. 解析 JSON 中的 `file / score / reasons / refs_in_todo / last_modified_days`，输出候选表。
3. 复核候选信号：
   - 仅子任务完成、仍属活跃验收/里程碑、仍被其他文档引用：说明依据并建议保留。
   - 用户已明确完成，或 TODO 删除后来源文档成为孤立项：可补充为归档候选。
4. 使用当前平台的结构化多选提问，提供“全部归档”“选择归档”“都不移”“再看某个”的操作；列出候选后立即停止本轮。
5. 用户要求“再看”时只读指定文件，说明判断后再次结构化询问；仍不得移动。
6. 用户明确批准后先运行 `git status`：
   - 工作区不干净：列出已有改动并停止，等待用户决定。
   - 工作区干净：对批准文件逐个执行：

     ```bash
     git mv doc/2_pending/<file> doc/4_archive/<file>
     ```

7. 同步 `doc/README.md`：从 current 表格删除对应行，按时间倒序加入 archive 表格；“最近归档批次”注释可选。
8. 再次检查 Git 状态，确认移动文件与索引修改和用户选择一致。

## 输出与验证

回报实际移动数量、每个源/目标路径和 `doc/README.md` 更新结果。只有 `git mv` 与索引均成功才写“归档完成”。

## 停止条件

- 扫描脚本失败或 JSON 无法解析：报告错误并停止。
- 没有候选：报告“无可归档候选”并停止。
- 用户尚未选择或选择“都不移”：停止，不修改文件。
- 批量操作前工作区不干净：停止并展示现状。

## 禁止事项

- 禁止未经用户确认执行 `git mv`，或在列完候选的同一回合移动。
- 禁止移动后漏改 `doc/README.md`。
- 禁止把 TODO 新增、长期 memory 总结或普通文档新建混入归档流程。
- 禁止把脚本分数当最终判断，忽略活跃引用和用户意见。
