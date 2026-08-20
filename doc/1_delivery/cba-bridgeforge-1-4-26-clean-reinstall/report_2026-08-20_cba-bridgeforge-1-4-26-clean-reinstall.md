# ClaudeBridgeAssist BridgeForge 1.4.26 白名单式干净安装报告

## 结论

- 状态：实施完成，等待独立审计。
- 项目：`D:\Quant\ClaudeBridgeAssist`。
- Git：`master@55919c202acca6228e6bbf8bb58ca31c67d26244`；未 commit、未 push、未 reset、未 restore、未 stash、未 clean。
- 骨架：一次性新基线已封为 `1.4.26`；最终 no-op replan 的 safe、risk、gap、blocker、G 均为 0。
- 边界：本次明确放弃 1.4.25 -> 1.4.26 历史谱系证明，因此不宣称普通 release transition 通过；从 1.4.26 以后恢复常规 Planner/Apply 更新检查。

## BridgeForge 产品基线

- 未完成的 1.4.27 release-artifact 源码、测试、合同、manifest 与现行文档口径已撤回；两份 `.runtime` artifact 已删除。
- `VERSION`、Template contract、dogfood contract 均为 `1.4.26`；manifest `--check` current，Template/dogfood 镜像一致。
- 完整产品测试 `311/311 OK`；downstream fixture `status=passed`，覆盖 29 个发布版本、9 个自动迁移与 19 个显式适配场景。

## CBA before

- 工作树 clean，骨架戳 `1.4.25`；项目 `.venv` 为 CPython 3.11.9 且 runtime identity 通过。
- AGENTS 项目区：`sha256:4e226f44a699b81309fde420c81fe8cbb8f6998e16e7da9e6c48c133ba1ddd51`。
- 两个项目 hook 脚本：`vault_junction_check.py=sha256:f1396bac...8b02`，`vault_snapshot.py=sha256:99dbedb7...89e6`。
- 29 个 memory 正文聚合：`sha256:5d63bc01...a3bb`；`_stats.json=sha256:50a50039...d4e`。
- `vault_node_map=sha256:f558d275...ff63`；`vault_path.local=sha256:d1c1c71f...8a76`。
- `vault/` 是指向 `F:\BridgeCloudDrive\Obsidian\Main` 的 junction。
- 原始 update Planner 只有两个 ordinary gap：managed contract 与 version-release 缺可信历史；无其他未知资产类别。
- 可恢复 before：`D:\Quant\BridgeForge\.runtime\cba-clean-reinstall\before-55919c2.tar`。

## 实际处置

### 保留

- 根 `AGENTS.md` 项目区逐字保持同一摘要。
- `vault_junction_check.py`、`vault_snapshot.py` 业务脚本逐字保持。
- `vault`、`vault-chat`、`linkify` 三个 Skill 正文保持；`vault` 与 `linkify` 只增加标准 frontmatter。
- 29 个 memory 正文、`_stats.json`、`vault_node_map`、`vault_path.local` 与 junction 目标保持。
- `.githooks/pre-commit` 项目扩展区保持为空；未触碰 `vault/`、`vault-mirror/` 或业务文件。

### 适配

- `.codex/hooks.json` 中两个项目 hook 的注册从裸 `python` 改为 Git 根下 `.venv/Scripts/python.exe`；未增加 `bridgeforgeCodexId`，仍为项目 external handlers。
- 使用 1.4.26 memory 脚本重建 `MEMORY.md` 与 `MEMORY_COLD.md`；终态未产生 Git diff，正文与 `_stats.json` 摘要不变。

### 替换与删除

- `.codex/managed-skeleton.json`、`.codex/scripts/version_release.py` 替换为 1.4.26 canonical，SHA-256 分别为
  `d23c5121...a08b`、`953002cb...d328`。
- `.codex/rules/obsidian_vault.md` 的有效红线已逐项确认存在于 AGENTS 项目区，随后删除旧 rule。
- validators 全部通过后，最后把 `.codex/.bridgeforge_codex_version` 从 `1.4.25` 写为 `1.4.26`。

## 特殊基线说明

替换两个 canonical 文件后，普通 Planner 已无 ordinary gap，但统一 evaluator 仍因 HEAD 的 1.4.25 合同不在可信历史中输出不可执行 G1。该结果与用户“摒弃本次旧骨架历史”的决定一致。本轮没有伪造历史、补 hash、写 artifact 或把 G1 宣称为已适配；而是对白名单与 canonical after 独立验证后一次性封存 1.4.26 新基线。最终同一 Planner 在 1.4.26 上为完全 no-op。

## 验证收据

- 项目 runtime：CPython 3.11.9，项目 prefix 有效。
- memory organize/lint、config health `--strict`、instruction source、project structure、encoding、rule size/index、mirror drift、Skill metadata 与 `git diff --check` 均 exit 0。
- project structure 只输出既有 `doc/4_archive/.gitkeep` advisory，不阻断。
- `vault` 与 `linkify` 去除新增 frontmatter 后，正文逐行与 HEAD 完全一致；`vault-chat` 未改。
- 最终 no-op fingerprint：`sha256:b99aa6bd8cd6978e530607a60e806ff725759498fa9b7600f7569a02de3806b9`。
- Native Memory 按 installed product authority 只读复核：`enabled=true / hookInstalled=true / pending=false / remoteConfigured=true`；未运行 reconcile。用 dirty 工厂 home 尝试 repair 时因 authority 不同返回 `conflicted` 且零写。

## 当前 Git diff

仅 7 个批准路径：骨架戳、hooks.json、managed contract、version-release、两个 Skill frontmatter、删除旧 obsidian rule。`vault-mirror/`、业务代码、项目文档、memory 正文和映射文件不在 diff 中。

## 未验证边界

- 未 commit，因此没有触发真实 Git hook 的 commit-time shell；本轮已用项目 `.venv` 逐项运行公共区全部 Python 硬闸。
- 未执行 `vault_snapshot.py`，避免写外部活库或 `vault-mirror/`。
- 未执行 Native Memory reconcile 或远端写入。

