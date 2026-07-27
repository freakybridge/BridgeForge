---
status: superseded
topic: memory-rule-organization
created: 2026-07-28
confirmation_card: ../requirements_2026-07-28_user-level-memory-junction-hooks.md
superseded_by: ../requirements_2026-07-28_project-level-memory-junction-hooks.md
research_agent: /root/junction_research
pro_agent: /root/junction_pro
con_agent: /root/junction_con
---

# Debate：用户级双宿主 memory junction hook

## 已确认目标与边界

- 首次安装经一次明确确认后，同时注册 Codex 与 Claude Code 的用户级 junction hook。
- 对已安装当前宿主 BridgeForge 骨架的下游项目，自动把系统 memory junction 到项目内、受 Git 跟踪的 memory。
- 存量项目经无参 `/bridgeforge` 展示并确认迁移；legacy hook 存在时用户级 hook 必须 no-op。
- 非 BridgeForge 仓库、另一宿主未安装骨架的项目完全 no-op；不扫描项目、不补建骨架、不硬删数据。

## 待辩论问题

1. 用户级 runtime 与 hook 配置如何受管，才能不破坏现有 shared updater 的 skill-only 边界和第三方 hook？
2. 如何建立 cutover 兼容闸门，保证任意存量下游不会双跑？
3. 如何以最少活动部件支持 Codex/Claude 的路径、hash、信任和迁移差异？

## 研究阶段

- `/root/junction_research`：当前两侧项目级注册分别位于 `templates/codex/settings.json`、`templates/claude/settings.json`；脚本同构，均由自身路径推导 repo root 与 hash，尚未读取 hook payload。
- `scripts/bridgeforge_shared_update.ps1` 仅允许写用户级 `skills/` 与托管账本，现有 manifest 没有 runtime 资产类型；若采纳，必须显式扩展其受管边界和事务协议。
- 尚无 memory junction 专项测试；可复用 shared updater 与 downstream fixture harness，但需要新增定向覆盖。

## Round 1

- 正方 `/root/junction_pro`：保留 shared updater 的 skill-only 边界；由其分发 runtime/reconciler 代码，但用户级 runtime、两份配置 merge 与独立账本由新的事务脚本管理。用户级 runtime 需 host-specific cutover marker、legacy 注册/脚本双检、正确 junction target 校验及可回滚首迁。
- 反方 `/root/junction_con`：反对按原提案直接实施。指出项目内版本戳不是用户级写入授权，要求本机 enrollment；现有首迁不是事务、任意 junction 会被误认为成功、hash 规则存在碰撞风险，并要求配置 compare-and-swap、版本化信任和真实 payload 收据。
- 争点：是否必须增加本机 enrollment ledger；非空系统 memory 的首迁是否允许在 SessionStart 自动执行；以及稳定 wrapper 是否会削弱宿主对 runtime 更新的信任语义。

## Round 2

- 正方接受所有安全质疑：项目 marker 不再作为授权；提出 Git-private token + 本机 enrollment ledger，SessionStart 只在系统路径不存在时建链，非空迁移改为 `/bridgeforge` 的带锁、journal、确认式事务；runtime 改为 content-addressed immutable 路径，配置命令随版本变更。
- 反方接受“独立 reconciler + skill-only updater + marker-last cutover + 精确 junction target 校验”的方向；同意 SessionStart 不得迁移已存在目录。反方认为，若安装确认已授权且 SessionStart 仅恢复缺失链接，可不强制每 clone enrollment，但必须记录 hash ownership。
- 剩余分歧：新 clone 的缺失 junction 是否允许零交互恢复，还是必须对当前 worktree enrollment 后才允许写宿主 memory。

## Round 3

- 正反双方一致推荐：采用“一次全局明确授权 + canonical-root ownership ledger”，不使用每 clone Git-private enrollment。这样保留新 clone 首次启动的自动恢复。
- 项目内版本戳与 cutover marker 仅作路由/迁移状态，不作真实性授权。自动路径只允许当前宿主、系统 memory 路径完全不存在、系统 project 父目录已由宿主创建、ledger 无冲突时新建 junction。
- 任何已存在的系统路径（包括空目录、错误/断裂 junction、普通文件和非空目录）均不得由 SessionStart 处理；必须进入无参 `/bridgeforge` 的锁、journal、plan/确认、可回滚迁移。
- ownership ledger 对 `(host, canonical root)` 和 `(host, system memory path)` 都要求唯一；junction 最终 target 必须精确等于当前项目的对应 memory。legacy 注册/脚本、异常 journal、非法 JSON 或任何路径漂移均 fail-closed。
- runtime 采用 content-addressed immutable 文件路径；每次更新都改变两侧 handler command，分别进入 trust-pending。不得由稳定 wrapper 静默加载被替换代码。

## 收敛结论

### 根因

当前 memory junction 是两份同构的项目级实现；Codex 的注册承载面又不是其有效 hook 发现面。将其收敛到用户级可消除副本漂移，但不能把用户级配置/运行时写入塞进现有 skill-only updater。

### 推荐方案

1. shared updater 继续只管理 BridgeForge skill 与现有账本；它仅分发独立 reconciler/runtime 的代码。
2. 新增独立用户 runtime reconciler，事务化管理 content-addressed runtime、Codex `~/.codex/hooks.json`、Claude `~/.claude/settings.json` 和独立 ownership ledger，并精确保留第三方 hook。
3. 一次安装确认须明确授权：在宿主已创建 system project 父目录、项目通过当前宿主 marker/cutover/legacy 检查、且系统 memory 路径不存在时，自动创建正确的 junction。
4. 新 init 直接写 host-specific cutover marker；存量项目只在无参 `/bridgeforge` 经用户确认后，以“移除 legacy 注册与已知脚本 → 验证 → 最后写 marker”的顺序切换。
5. SessionStart 仅做缺失路径的幂等建链/恢复；所有已有系统路径的迁移、冲突、错误 junction 和 crash journal 都交给交互式 `/bridgeforge`。

### 未验证前提与发布硬闸

- 必须在真实 Codex 与 Claude Code 中留取收据，证明用户级 SessionStart 在 repo 信任之后、memory 被读取之前运行；否则自动恢复不能保证生效，需退回逐项目 enrollment 或项目级实现。
- 必须实测两宿主的 payload `cwd`、project hash 规则与 hook trust 行为；不得沿用现有同构脚本的推测。
- 必须新增配置并发/回滚、hash 碰撞、错误 junction、子目录/路径别名、新 clone、legacy 回流与双宿主 trust-pending 的测试矩阵。

### 取舍

- 接受：用户一次全局授权后，已信任且带严格 marker 的项目可在空系统路径上自动建链；伪造项目最多占用自身原本不存在的 memory 路径，ownership ledger 会阻断碰撞后的覆盖。
- 不接受：SessionStart 搬迁已有数据、稳定 launcher 静默替换 runtime、覆盖第三方 hook、把用户 runtime 混入 skill updater、或绕过宿主 trust。

## 状态

- superseded：用户基于辩论结论选择项目级双宿主方案，详见新的确认卡。

## 收敛结论

- 待定。
