# Codex 既有项目接入

仅在根 skill 判定为 `adopt` 后读取。

1. 只运行 `bridgeforge_codex_project_sync.py --mode adopt` 生成计划。
2. 先分类已有 AGENTS、rules、hooks、memory、doc 和配置的 ownership。
3. project-owned、未知或人工修改内容逐字保留；只增补可证明缺失的受管资产。
4. risk 与 absorption 并入唯一风险卡；fingerprint 漂移时零写入。
5. 验证完成且无 gap 后，最后写 `.codex/.bridgeforge_codex_version`。

发现 `.claude/` 或 `CLAUDE.md` 时仅提示“Claude 骨架已停止支持”，不得读取、迁移、
删除，也不得因此阻止 Codex 接入。
