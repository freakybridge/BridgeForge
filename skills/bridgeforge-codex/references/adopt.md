# Codex 既有项目接入

仅在根 skill 判定为 `adopt` 后读取。

1. 只运行 `bridgeforge_codex_project_sync.py --mode adopt` 生成计划。
2. 既有项目缺少 current 版本戳时必须零写阻断；禁止猜测其来源或自动补戳。
3. 用户需要先安装当前骨架，或提供可识别的 `<1.4.28` current 版本戳进入重建流程。

发现 `.claude/` 或 `CLAUDE.md` 时仅提示“Claude 骨架已停止支持”，不得读取、迁移、
删除。
