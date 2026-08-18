---
status: implemented-awaiting-independent-audit
next: independent_audit
scale: M
source_bug: doc/2_bugs/BUG-native-memory-maintain-misclassified-safe-data-egress.md
---

# Native Memory 长期授权与自动同步职责解耦需求

## 原始需求摘要

修复 `codex_memory_sync.py maintain` 被误分类为 safe 的问题。用户只需在首次启用 native Memory 时明确授权一次；授权范围未变化时，双向自动同步和同步 hook 的日常维护必须无感运行。内部必须拆开“修复 hook”和“同步数据”，避免项目骨架更新顺手触发一次完整远端同步。

## 调用来源与后续交接

- 调用来源：`$develop`，由本轮 `$confirm` 已确认结论进入实施。
- 后续交接：主对话完成 discovery、实现、最多两轮验证和用户试用收据；不自动 commit/push。

## 规模与预算

- 规模：M。原因是修改跨越 native Memory 命令、长期授权 ledger、用户级迁移和根 Skill 编排。
- 时间预算：45 分钟。
- token 预算：20k 新增 token（估算；平台不提供可靠实测）。
- agent 预算：0 个子 agent。
- 验证预算：原定最多两轮；两轮用尽后，用户明确批准增加一轮完整复测。
- 超预算停止点：范围扩大、需要第三轮验证、或发现必须改变已确认授权语义时停止并请求用户调整预算或范围。

## 已核实事实

1. `scripts/codex_memory_sync.py maintain` 当前依次迁移状态目录、检查/创建 GitHub 仓库、修复用户 hook、写 `remote.txt` 并立即调用 `reconcile`。
2. `skills/bridgeforge-codex/SKILL.md` 当前把 `approved + enabled` 下的 drift maintenance 归为 safe。
3. 当前 ledger 只以 `approved/declined` 字符串记录 native Memory consent，没有记录授权策略版本、同步范围和远端身份。
4. 当前 `reconcile` 是双向同步：本地较新上传，远端较新恢复本地。
5. 自动 hook 在 SessionStart/Stop/SessionEnd 生命周期触发同步或调度。

## 已确认业务规则

1. 保留双向自动同步：本地较新自动上传，远端较新自动恢复。
2. 用户首次明确授权一次；范围和目标未变化时，不因 hook 漂移或日常同步重复询问。
3. 同步范围固定为用户级 `~/.codex/memories/**`，不得包含项目 `.codex/memory/`。
4. 目标固定为 BridgeForgeCodex 管理的 GitHub 私有 Memory 仓库。
5. 首次授权必须明确披露同步范围、双向同步、未来生命周期自动同步和自动 hook 维护。
6. 内部拆开本地 hook 修复和远端 reconcile；项目骨架更新不得顺手执行完整同步。
7. 每次自动同步前必须验证长期授权仍为 approved 且策略范围、目标和可见性未发生实质变化；不满足时 fail closed。
8. 旧 `approved` 在能够证明仍为原目录和原私有仓库时自动继承；证据不一致时才重新确认。
9. `declined`、损坏授权或无法证明授权范围时禁止同步。

## 数据映射

长期授权必须能表达：

- 决策：approved / declined；
- 授权策略版本；
- 数据范围：用户级 Codex native Memory；
- 同步模式：bidirectional；
- 自动 hook 维护：允许；
- 远端仓库身份与 private 要求。

旧字符串 consent 只允许按上述可信迁移规则转为结构化授权，禁止无条件扩大旧授权。

## 拟修改

1. `scripts/codex_memory_sync.py`：新增本地-only hook repair；让旧 maintain 成为无远端副作用兼容入口；reconcile 强制验证长期授权。
2. `skills/bridgeforge-codex/SKILL.md`：首次单卡授权、日常自动维护和分离 readiness/receipt。
3. `scripts/bridgeforge_codex_shared_update.ps1`、`scripts/bridgeforge_codex_user_migrate.py`：兼容并保留结构化 consent，迁移可信旧授权。
4. `scripts/tests/**`：补本地修复零网络、长期授权、旧授权迁移、双向同步、拒绝与远端变化场景。
5. `VERSION`、`CHANGELOG.md`、manifest 与相关文档：传播发布事实。

## 非目标

- 不取消 native Memory。
- 不改成仅上传。
- 不读取或展示真实用户 Memory 内容。
- 不访问真实用户 Memory 远端，除非后续单独授权真实验收。
- 不把项目 Memory 与用户级 native Memory 合并。
- 不自动 commit/push。

## 验收

1. 首次授权写入完整长期授权，拒绝状态同样可审计。
2. 已授权且 hook 缺失时自动修复；GitHub、Git、Memory 扫描和 `reconcile` 必须零调用。
3. hook 健康时完全 no-op。
4. 自动 reconcile 每次验证长期授权；declined、损坏或范围/目标变化时 fail closed。
5. 旧 approved 在可信原范围内无感迁移；证据不足时不自动同步。
6. 原双向 push/restore 行为不变。
7. 项目文件与项目 `.codex/memory/` 不变。
8. 根 Skill 保持整体零次或一次 A/B/C 确认，不新增零散确认。
9. 通过相关 unittest、完整 factory unittest、fixture、manifest check、dogfood gate、git diff check 和独立审计。

## 合理假设、风险与自动化边界

- GitHub 仓库身份和 private 状态属于授权边界；外部状态无法证明时宁可停止同步。
- 本地 hook 修复虽然不立即读写 Memory，但会恢复未来自动同步；其权限来自已记录的长期授权。
- 本轮测试使用临时目录/临时 Git remote，不访问真实 `~/.codex/memories/` 或真实 GitHub Memory 仓库。
- 真实新会话 hook 加载与真实远端 smoke 必须单独标记验证状态，未运行不得宣称通过。

## 实施记录

- `scripts/codex_memory_sync.py` 已将用户 hook 修复与远端 reconcile 拆开：`repair-hook` 和兼容 `maintain` 只做本地事务修复；自动 reconcile 仍保持双向同步，但执行前必须验证长期授权、目标仓库身份和 private 可见性。
- native Memory consent 已升级为结构化策略，记录 decision、policy version、用户级 Memory 范围、bidirectional 模式、自动 hook 维护、受管仓库名、private 要求和精确 remote；可信旧字符串授权可迁移，范围或目标漂移则 fail closed。
- `skills/bridgeforge-codex/SKILL.md` 已改为首次完整披露并确认一次，后续在授权边界不变时静默维护；项目骨架更新不得顺手执行远端 reconcile，收据分别报告项目和用户级 native Memory 状态。
- 用户级 updater 与 legacy migrator 已支持结构化 consent 的校验、保留和兼容迁移；本地 hook 修复失败会回滚 hooks、ledger 与迁移状态。
- 发布传播已更新到 `1.4.12`，并重建 Template/dogfood contract 与 active/compat manifest。

## 验证记录

- 完整自动测试：`.venv\\Scripts\\python.exe -B -m unittest discover -s scripts/tests -p "test_*.py" -v`，`252/252` 通过。覆盖本地-only repair 零远端调用、结构化授权、旧授权迁移、private 校验、双向 reconcile、事务回滚和 updater 刷新保留 consent。
- 完整下游 fixture：`.venv\\Scripts\\python.exe -B scripts/tests/run_downstream_fixture.py`，状态 `passed`；已发布 lineage `26/26` 可执行迁移通过。
- 派生数据：`.venv\\Scripts\\python.exe -B scripts/rebuild_shared_skill_manifest.py --check`，exit 0，manifest already current。
- 工厂硬闸：skill metadata、project structure、mirror drift、instruction source 与 `git diff --check` 均 exit 0；project structure 仅输出既有归档 advisory。
- 未验证：独立 agent 审计、真实 `~/.codex/memories/`、真实 private GitHub Memory 仓库、新 Codex 会话 hook runtime smoke。按需求卡边界不得据此宣称真实运行环境已通过。
