# Step 3 聚合输出格式

把各 Path 命中聚合成下述结构化 markdown 呈给用户。空段不显示。

```markdown
# 关于 "<topic>" 的检索结果

## 📍 直达位置（文件名 + 共现交集）
- `<paths from Path A + E, 去重后>`

## 📚 README 入口（agent 推荐先读）
- `<paths from Path B>`

## 🟢 活跃 / 进行中（如 "找东西" 意图）
- 从 Path A 命中里挑 `1_plan/<topic>/` 下的活跃文件

## 🔴 待解决问题（仅 "看 TODO" 意图，或主动列出）
- TODO #N（P0/P1/P2）— <description>（来自 Path C）
- 未决 debates: <files from Path C>

## ⚠️ 关联 rules（字典查表，无 grep）
- `<rules from Step 2 字典>`

## 🧠 相关 memory
- `<entries from Path D>`

## 🗂 已归档（仅作历史参考）
- 从 Path A 命中里挑 `4_archive/` 下的文件

---

**建议下一步**：
- 改代码 → 先读 [README + 关联 rules]
- 看进展 → 读 [活跃] 段
- 修问题 → 读 [待解决问题] 段
```
