# BridgeForge switch 双骨架直接同步辩论

> 状态：`concluded`
> 确认卡：[requirements_2026-07-25_bridgeforge-switch-direct-sync.md](../1_plan/bridgeforge-switch-direct-sync/requirements_2026-07-25_bridgeforge-switch-direct-sync.md)
> 目标：审查以目标骨架内映射表替代项目根 `.bridgeforge/` archive / receipt / lineage 的双骨架直接同步方案。

## 边界与约束

- `.codex` 与 `.claude` 长期共存，切换为“同步 + 在当前宿主继续工作”。
- 映射表分别位于 `.codex/.bridgeforge-map.json`、`.claude/.bridgeforge-map.json`，纳入 Git，不保存资产原文。
- 未转译项允许完成 switch，但须显式标识；人工修改或映射表异常时不得静默覆盖或删除目标文件。
- 不实现代码，直至用户确认辩论收敛方案。

## 角色

- 事实研读：`/root/direct_sync_facts`（`light-explorer`）
- A（实现立场）：`/root/direct_sync_implementer`（`implementation-worker`）
- B（审计立场）：`/root/direct_sync_auditor`（`review-auditor`）

## 轮次记录

### 第一轮：方案与挑战

**A（实现立场）**

- 不能将 archive / receipt 的路径机械替换成 map；应以“目标映射拥有的文件集合”为同步和删除边界，重写 `Plan → proposal → validate → apply` 状态机。
- 保留现有哈希、路径安全、stage、输入漂移复核和受控异常回滚；移除 archive / receipt / lineage 读写与 source skeleton 移动。
- map 用稳定 `asset_id`、`sources[]`、`targets[]`、adapter id/version、状态和生成哈希表示语义组；目标端生成文件未经修改才允许更新或删除。
- 对来自源 map 且哈希未变的生成投影作回声抑制；投影被人工修改时不得自动反向回灌。
- 证据：`scripts/bridgeforge_switch.py` 的 `build_plan()`（约 463）、`build_proposal()`（约 708）、`validate_manifest()`（约 941）、`apply_manifest()`（约 1560）；hash/path/recheck 辅助函数约 143、239、256、1435。

**B（审计立场）**

- 卡片未定义未修改生成投影、已修改生成投影与双边 map 的关系；只读源 map 会造成双向回声或将 lossy projection 反向覆盖源语义。
- 多文件同步在没有明确事务协议时不能声称原子：map 先写与后写都会留下不一致窗口。
- 可解析 map 仍可能 stale 或被错误合并；自动删除至少要绑定 target 当前字节等于 `last_generated_sha256`，冲突时不能把观察到的人工哈希晋升为新生成基线。
- 一对多 / 多对一和共享配置必须按语义组处理；动态从 map 执行 adapter 会引入 repo 输入执行风险。
- 当前 CLI 无宿主识别能力，必须由宿主入口传入受限的 host attestation；根入口是否属于同步表面也需澄清。
- 证据：`scripts/bridgeforge_switch.py` 约 31-32、97-107、466-1060、1558-1810、1826-1873；harness 约 461/1019、1961-2157。

**待第二轮收敛**

1. 双向回声与人工修改后的投影是否一律禁止自动回灌。
2. 映射表能否作为受信项目输入；自动更新 / 删除的字节级前置条件。
3. 多文件组与目标 map 的更新 / 回滚协议；是否接受硬崩溃语义降级。
4. 宿主匹配的调用证据、adapter allowlist 与根入口范围。

### 第二轮：最小安全模型

**共同接受的护栏**

- 每次读取 source 与 target 两张 map：source 的未修改生成投影必须抑制回声；已修改投影标为 `forked_projection`，默认不自动回灌。
- target map 的 `last_generated_sha256` 是自动更新 / 删除的必要基线。仅 map 声称“受管”不足够；实际文件或 selector 子树必须匹配该哈希。冲突时不得用观察到的人工哈希覆盖生成基线。
- map 是需严格校验的受信项目输入，不是自证 provenance：校验 schema、相对路径、Windows 冲突、host surface、唯一 asset/group/selector、hash 格式和内置 adapter id/version；异常时所有破坏性操作降级为保留 + 冲突。
- 稳定 `asset_id` 不包含内容哈希，按语义组记录 `source_members[]`、`target_members[]` 和内置 adapter id/version。未知 adapter 不执行 repo 提供代码，只能成为 `untranslated` / `stale`。
- 同一语义组整体更新或冲突；共享 JSON 配置使用内置 adapter 声明的非重叠 JSON Pointer selector，hash 绑定到 canonical 子树。首版不支持的 TOML / 自由文本共享配置标 `untranslated`。
- commit 前重读双 map、所有源项与待写 / 待删目标项，复用 link / junction / Windows 路径安全校验；map 最后以原子替换写入。源端始终不动。
- 包含未转译、stale、forked 或 conflict 项时，switch 的成功输出必须为 `completed_with_gaps` / `readiness=degraded`。

**唯一分歧：硬崩溃语义**

- A 主张目标骨架内短命 `.bridgeforge-txn/` 与 before-image，以完成 kill / 断电后的自动恢复。
- B 主张本期不引入 journal：它会重新引入恢复协议与运行状态，增加系统复杂度；只保证普通 Python 异常精确回滚，硬崩溃后由 map/live 哈希不一致触发保守冲突，绝不自动猜测恢复。

**第三轮问题**

在用户已明确“项目不保留 `.bridgeforge/` 状态、偏好低系统复杂度”的前提下，是否将硬崩溃恢复排出本期，并把 fail-safe preserve + conflict 作为唯一恢复策略。

### 第三轮：硬崩溃语义裁决

**共同结论：不引入 target-local transaction journal。**

- 普通、可被 Python rollback handler 捕获的异常：临时备份和 `try/except` 必须精确恢复全部写入、新建、删除与旧 map，并逐项验证提交前 hash。
- 单文件以同目录临时文件加原子替换提交；目标写入 / 更新后再执行已证明为 clean generated projection 的删除；map 最后原子替换。
- commit 前重验双 map、源项与全部目标 write/delete pre-state；map 写入后再核对 map 与 live 输出的完整关系，只有通过才报告成功。
- kill、强制终止、系统崩溃或断电不承诺跨文件原子性，也不自动恢复。下次运行发现 map/live 不一致时，对受影响 semantic group 一律 `preserve + conflict: interrupted-or-modified`：不覆盖、不删除、不认领 ownership、不自动重建缺失输出，也不推进 `last_generated_sha256`。
- 独立且无路径碰撞的无歧义组仍可同步；源骨架始终保持不变。

**原因**：journal 会新增恢复协议、残留清理、版本兼容和新的项目运行状态，违背已确认的低系统复杂度目标。硬崩溃后的 map/live 不一致无法可靠区分人工修改，保守冲突是唯一不猜测所有权的策略。

## 收敛结论

推荐以 **双 map + 语义组 + 受控异常回滚 + 硬崩溃后保守冲突** 实施直接同步：

1. 重写 `Plan → proposal → validate → apply`，移除项目根 archive / receipt / lineage 和 source skeleton 移动；保留 hash、路径安全、stage、输入漂移复核与故障回滚。
2. 每轮同时读取 source / target map。source 的 clean generated projection 必须 suppress；drift projection 标 `forked_projection`，不得自动回灌。target 的 map 只在 live member / selector hash 等于 `last_generated_sha256` 时授予更新 / 删除权。
3. map 使用稳定的语义 `asset_id` 与 `source_members[]` / `target_members[]`；只引用内置 allowlist adapter 的 id/version。组内任一成员漂移即整组 conflict。
4. 共享 JSON 配置本期仅支持内置 adapter 声明的、无重叠 JSON Pointer selector；其他共享格式标 `untranslated`。map 不保存正文、命令或模块路径。
5. map 的 schema / path / host surface / adapter / selector / hash 任何校验异常，都使破坏性操作降级为保留 + 冲突。未转译、stale、forked、conflict 存在时成功状态必须是 `completed_with_gaps` / `readiness=degraded`。
6. 宿主入口必须向脚本传入受限 `current-host` 证据；参数不匹配在任何项目写入前失败。该 guard 约束工作流，不声称防御用户手工伪造。
7. 根入口文件是否纳入同步表面须在实现设计中显式限定；默认不把根入口作为自动写入目标，避免“完整盘点”扩大为对项目根通用文件的无权覆盖。

## 必测项

- 双向三跳 roundtrip 无回声；clean projection 抑制、forked projection 冲突。
- target map 的 clean update/delete、人工修改、map 缺失/非法/schema/path/hash/adapter 异常均 fail-safe。
- 一对多、多对一、JSON Pointer selector 重叠与字段级保留。
- 可捕获故障在首写后、删除后、map 替换前、map 替换后最终核验前全部精确回滚；源骨架不变。
- 人工构造四类硬崩溃残态后，受影响组只报告 `interrupted-or-modified`，不自动修改；独立无歧义资产仍可同步。
- host 证据缺失 / 不匹配零写入；旧项目根 `.bridgeforge/` 仅提示、不读写删。
- 保留路径 / link / junction / Windows canonical collision / source-target-map TOCTOU 安全测试意图，并清除 harness 中被后定义静默覆盖的旧 archive 测试函数。

## 收敛结论

待形成。
