---
name: sync-docs
description: 根据本次代码变更，同步更新对应的设计文档。
user-invocable: true
argument: 可选的额外上下文提示（如本次改动的重点）
model: sonnet
---

# 同步设计文档

根据本次代码变更，同步更新对应的设计文档。

## 步骤

1. 运行 `git diff --stat HEAD` 和 `git status`，找出本次修改的文件
2. 按以下映射规则找到对应设计文档（**项目接入时维护本项目的源码 → 文档映射表**）：

   <!-- TODO: 按本项目实际目录结构填写源码 → 文档映射表。例：
   - `src/<feature>/<file>.py` → `doc/3_design/<feature>/设计.md`
   - `src/api/` → `doc/0_architecture/api-contract.md`
   - `src/db/migrations/` → `doc/0_architecture/数据结构与常量.md`
   - 其他文件根据路径和内容判断最相关的文档
   -->

3. 读取对应设计文档的现有内容
4. 根据实际代码变更，在文档中更新或补充：
   - 新增的类/方法/字段
   - 修改的行为或逻辑
   - 删除的功能
   - 重要的设计决策（如果能从代码推断）

5. **只更新有实质变化的部分**，不改动无关内容
6. 输出一份简短的同步摘要：更新了哪些文档、改了什么

## 规则
- 文档描述保持与代码一致，不添加代码中没有的内容
- 如果找不到对应文档，列出来告诉用户，不要自己新建
- `$ARGUMENTS` 如果有值，作为额外的上下文提示（比如本次改动的重点）

## Step 7：placeholder 检测与提醒（任务收尾）

同步摘要已呈现后，**额外**做一件事：

1. 检查 Step 2 的源码 → 文档映射表是否仍含 `<!-- TODO:` 占位
2. 如仍是占位 **且** 本次 git diff 涉及到了**有规律的源码路径**（同一目录 / 同一模块多文件改动，能看出 pattern） → 在回复末尾追加：

   ```
   💡 映射表提醒：本次改了 <path_pattern>，sync-docs Step 2 映射表还是 placeholder。
   要不要顺手加这行？候选：
     - <src_pattern> → <guessed_doc_path>
   ```

3. **禁止**：
   - 凭空提醒（仅改了零散无规律文件时不提醒）
   - 强制要求用户填
   - 同一会话内对同一路径重复提醒

**Why this exists**：映射表是项目目录结构稳定后才填得准的（StratusAgent 演化出 10+ 行 `stratus/ui/risk_panel.py → doc/3_design/engine/risk/面板.md` 这种细粒度映射）。早期项目映射空着 sync-docs 走 catchall（"其他文件根据路径和内容判断"），效果打折。本段保证用户在目录稳定后顺手补表。

$ARGUMENTS
