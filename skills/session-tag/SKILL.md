---
description: 给当前 session 起一个标签名，后续 /snapshot 和 /resume 在该标签子目录隔离命名空间。多 session 并发时必用，单 session 可不用。
---

# /session-tag — 为本 session 起标签名

**定位**：解决多 session 并发时 snapshot 互相覆盖 / `/resume` 不知道接续哪个的问题。

## 用法

```
/session-tag <name>
```

`<name>` 必须匹配 `[a-zA-Z0-9_-]+`，建议描述本 session 主题（如 `bug-44`、`refactor-cache`、`ladder-perf`）。

## 执行步骤

1. **校验 name 格式**：
   - 必须 `[a-zA-Z0-9_-]+`
   - 不能等于保留名 `.archive`、`.tags`
   - 不能以 `.` 开头
   - 长度 ≤ 50

2. **创建 tag 目录**：
   ```bash
   mkdir -p .runtime/session_state/<name>
   ```

3. **写活跃标记**（让 SessionStart hint 能看到）：
   ```bash
   date +%s > .runtime/session_state/<name>/.last_active
   ```

4. **Claude 在心里记住** `本 session tag = <name>`：后续同 session 内的 `/snapshot` 和 `/resume` 默认带上这个 tag。

5. **回复用户**：
   ```
   ✓ 本 session 标记为 `<name>`
   后续 /snapshot 写到 .runtime/session_state/<name>/
   /resume 默认接续 <name>（也可显式 /resume <other-tag>）
   ```

## 跨 compact 行为

如果 context 被 compact，Claude 可能丢失 tag 记忆。处理方式：

- `/snapshot` 时如找不到 tag 记忆 → 检查 `.runtime/session_state/` 下是否有过去 1 小时内 `.last_active` 更新过的 tag 子目录：
  - 只有 1 个候选 → 提示用户："是不是 `<tag>`？" 等用户确认再写
  - 多个候选或没有 → 默认写根目录 + 提醒用户"如果有 tag 请重打 /session-tag"

## 何时用 / 何时不用

| 场景 | 要 tag 吗 |
|------|----------|
| 当前只开了 1 个 session | ❌ 不需要（默认根目录就够）|
| 同时开 ≥ 2 个 session 解决不同问题 | ✅ **必需**（每个 session 起不同名）|
| 长期项目分阶段，但每次只开 1 个 session | ❌ 不需要 |
| SessionStart 提示有"其他活跃 tag" | ⚠️ 建议（避免冲突）|

## 禁止

- ❌ 同时两个 session 用同一个 tag（会写到同一目录互相干扰）
- ❌ tag 名含路径分隔符 `/` 或 `\`
- ❌ 用 tag 替代 commit / memory（tag 是短期工作状态隔离，不是持久知识）