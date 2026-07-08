# Harness Regression Fixture

这个目录放 BridgeForge 自身的最小回归检查。脚本不会提交生成项目，只会在 `.runtime/harness/` 下临时生成 Codex 形态的下游 fixture。

运行全部检查：

```bash
python tests/harness/run_downstream_fixture.py
```

当前覆盖：

- D6：`.codex/rules/` 下游形态里的 `rule_index_check.py` / `rule_size_check.py` 是否真的 `exit 2`。
- D8：factory 形态里的 `mirror_drift_check.py` 缺文件硬拦，以及纯下游无 `templates/` 时 no-op。
- settings：关键 PostToolUse hook matcher 必须覆盖 `Edit|Write|MultiEdit`。
- root pre-commit：根 `.githooks/pre-commit` 必须同时覆盖 `.claude` / `.codex` 两侧镜像闸、规则闸和 memory 索引重建。
- skills：`skills/**/SKILL.md` 的可调用 frontmatter 和高置信本地引用是否健康。

白话：这是一个可重建的“模拟下游项目”，用来确认模板装进真实布局后开关真的会响，而不是只在源码仓库里看起来没报错。
