---
description: 手动存档当前 session 的工作状态到 .runtime/session_state/ — 与自动 hook 互补，能写入 Claude 主观的"本轮做了啥 / 下一步打算"。
model: sonnet
---

# /snapshot — 主动存档当前工作状态

**定位**：在 Hook D（PostCompact + Stop 节流）的自动快照基础上，提供**手动触发 + 主观内容补全**。

## 与相关机制的区别

| 机制 | 触发 | 内容 | 何时用 |
|------|------|------|--------|
| **Hook D（post-compact）** | compact 自动 | 客观状态 | 自动跑 |
| **Hook D（stop 节流 5min）** | 每轮 Stop ≥5min | 客观状态 | 自动跑（Word-style 自动保存）|
| **`/snapshot`（本 skill）** | 用户显式 call | 客观 + **主观** | 觉得"这轮有重要进展"要保 |
| **`/summary`** | 用户显式 call | 决策沉淀到 memory（长期） | 决策值得**永久**记 |

`/snapshot` = 短期工作状态（session state）；`/summary` = 长期知识（memory）。

## 执行步骤

1. **跑 hook 脚本抓客观状态 + 落盘**：
   ```bash
   .venv/Scripts/python.exe .claude/hooks/session_snapshot.py manual
   ```
   会在 `.runtime/session_state/<ts>.md` 写客观快照。

2. **读取刚写的 snapshot 文件**（拿到完整路径 + 当前客观状态）。

3. **追加主观内容**到同一文件末尾：

   ```markdown
   ## 本轮做了什么（Claude 填）
   - ...（本轮关键动作，简练 3-5 条）

   ## 当前假设 / 未验证
   - ...（正在假设但还没验的事）

   ## 下一步打算
   - ...（user 或 claude 推进的方向）
   ```

4. **回复用户**一行摘要：
   ```
   ✓ snapshot → <相对路径>
   含本轮 X 件事 + Y 个未验假设 + Z 条下一步
   ```

## 何时主动建议

- 用户说"先停一下" / "暂告一段落" / "明天再继续"
- 完成一个完整子任务（修完一个 bug、写完一个 skill、走完一个 milestone）
- 即将切 session / 切 role
- 对话已经长且有重要决策（防丢）

## 禁止

- 不要调 `/summary`（那是长期 memory）
- 不要把主观内容放磁盘以外的地方
- 不要删旧 snapshot（脚本自己 cap 20 份会清理）