# 共享 Skill 双骨架分发与 `.agents` 退役需求卡

> 状态：`confirmed`
> 确认日期：2026-07-25
> 来源：StratusAgent 中的 `$develop` + `$confirm` 多轮确认
> 后续交接目标：在 BridgeForge 上游实现 GitHub `main` 驱动的 Codex / Claude 共享 skill 安装与更新，并退役 `.agents` / `~/.bridgeforge` runtime 依赖。

## 原始需求摘要

1. 把共享 skill 从 `~/.agents/skills/` 收敛到 `~/.codex/skills/`。
2. `~/.agents/` 原则上退役。
3. 项目私有 rule / memory / hook 留在 `<项目>/.codex/`；项目内 `.agents/` 应移除。
4. `~/.bridgeforge` junction 应移除，改用 GitHub 上游分支作为唯一事实源。
5. 不能只覆盖 Codex，Claude 骨架必须同步纳入设计。

## 已核实事实

- BridgeForge 上游远端为 `https://github.com/freakybridge/BridgeForge`，当前主分支为 `main`，不是 `master`。
- `~/.bridgeforge` 是 junction，指向 `D:\Quant\BridgeForge`；移除 junction 不等于删除实体仓库。
- `~/.agents/skills/` 当前有 20 个共享 skill；`~/.codex/skills/` 当前只有系统目录。
- Claude 已使用 `~/.claude/skills/`，当前有 18 个 skill；其模板明确规定项目私有 rule、memory、hook 在 `<项目>/.claude/`，并使用 `CLAUDE.md`。
- Codex 项目私有资产在 `<项目>/.codex/`；当前 StratusAgent 项目 `.agents/` 为空，`.bridgeforge/` 仅含 archive。
- 现有 BridgeForge/下游 hook 和 skill 中仍存在对 `~/.agents`、`~/.bridgeforge` 的旧布局假设，必须转译。

## 已确认规则

1. GitHub `origin/main` 是共享 skill 的唯一上游事实源；`D:\Quant\BridgeForge` 本地工作副本不得作为下游安装或更新内容源。
2. 首次安装由 BridgeForge 提供显式 PowerShell 安装脚本。脚本必须从 GitHub `main` 创建干净临时副本、校验来源与分支、安装后删除临时副本。
3. 后续更新由下游项目中用户显式调用无参数 `/bridgeforge` 触发；日常启动或日常会话不得自动联网更新。保持公开命令面仅为 `/bridgeforge` 与 `/bridgeforge switch <claude|codex>`，不新增 `/bridgeforge update` 或其他迁移命令。
4. 共享 skill 使用同一上游、按平台 manifest 分发：
   - Codex 兼容 skill 安装到 `~/.codex/skills/`。
   - Claude 兼容 skill 安装到 `~/.claude/skills/`。
   - 不强制两端 skill 名称或数量完全相同。
5. `/bridgeforge` 的共享 skill 更新阶段必须强制覆盖 manifest 管理的全部 BridgeForge skill；本地改动不保留、不备份、不跳过。安装器必须在 `~/.codex/bridgeforge-managed.json` 与 `~/.claude/bridgeforge-managed.json` 维护每个平台的托管账本，记录 skill 名、来源 commit、内容哈希与安装时间；只有账本登记的 skill 可被覆盖或在上游移除后删除。未登记但同名的目标目录视为非托管冲突，必须停止并报告。
6. 强制更新只影响 manifest 管理的 BridgeForge skill，必须保留两个用户级 `skills/` 目录内其他来源的 skill。
7. `/bridgeforge` 的共享 skill 更新阶段默认只更新用户级共享 skill；不得自动修改当前项目或任何其他项目的 `.codex`、`.claude`、rule、memory、hook 或项目私有 skill。仅当用户在当前项目显式调用 `/bridgeforge`、且它发现遗留 `.agents/` 时，才可进入当前项目迁移模式：必须先输出 dry-run 迁移计划并取得确认；不得扫描或修改其他项目。
8. 首次安装校验成功后，不处理 `~/.agents/`，由用户自行决定是否清理；只在确认 `~/.bridgeforge` 为 junction 且其 target 为保留的实体上游仓库后删除该 junction。
9. 项目内 `.agents/` 没有独立职责，应在用户显式调用当前项目的 `/bridgeforge` 并确认迁移计划后删除；空目录可删除，已知公共 skill 副本可删除，项目私有内容必须迁入目标骨架，未知文件、链接或无法归类内容必须阻断。项目私有 Codex 资产只留在 `<项目>/.codex/`，项目私有 Claude 资产只留在 `<项目>/.claude/` 与 `CLAUDE.md`。
10. 本次共享 skill 分发仅支持 Windows。首次安装脚本必须在任何下载或写入前检测操作系统；macOS、Linux 及其他非 Windows 平台必须直接报错退出、零写入，不提供 symlink 或其他兼容迁移逻辑。

## 已确认的实现约束

1. 安装器只从硬编码 canonical URL `https://github.com/freakybridge/BridgeForge.git` 创建干净临时副本；不读取本机已有 clone、`origin`、`~/.bridgeforge` 或 `~/.agents/` 作为安装源。临时副本必须检出 `main`、记录完整 `HEAD` commit SHA，并拒绝 submodule。
2. 根目录分发 manifest 是唯一允许写入用户级 skill 目录的清单。manifest 必须包含 schema version、平台、skill 名、相对源路径和逐文件 SHA-256；安装器必须拒绝重复名称、绝对路径、`..` 路径逃逸、缺失文件及哈希不符。
3. 安装前校验所有目标目录可写，并写入单一更新操作日志，记录目标 commit、manifest 哈希、两个平台的待办和完成进度。每个平台的 skill 先在同卷临时目录组装并校验，再以可恢复替换写入目标；两个平台都完成后才原子更新托管账本并删除操作日志。中断后，下一次显式 `/bridgeforge` 必须先按操作日志恢复或补完，最终把两个平台收敛到同一 commit。
4. `bridgeforge` 自身作为每个平台最后一个被替换的 skill，避免更新过程中提前破坏当前入口。操作成功后删除所有临时替换目录；临时目录仅用于中断恢复，不作为用户改动备份。
5. GitHub 不可达、认证或分支校验失败，或任一 manifest / 文件 / 可写性校验失败时，安装或更新必须失败退出，不得写入用户级目标，更不得回退到本地工作副本。

## 非目标

- 不删除用户级 `~/.codex/`、`~/.claude/` 或实体上游仓库 `D:\Quant\BridgeForge`。
- 不把项目 rule 或 memory 提升到用户级目录。
- 不在运行时直接加载 GitHub、junction 或本地 BridgeForge 工作副本。
- 不自动覆盖任何项目私有资产。
- 不处理项目 `.bridgeforge/archive/` 的历史内容。

## 拟修改范围

- BridgeForge 的共享 skill 分发 manifest、PowerShell 首次安装脚本及 `/bridgeforge update` 工作流。
- 共享 skill 和相关脚本中对 `~/.agents`、`~/.bridgeforge` 的引用。
- Codex 与 Claude 模板中涉及共享 skill 发现、安装、升级的说明与入口。
- 相关 hook / 文档，包括目录关系报告。
- 下游项目中的空 `.agents/` 清理逻辑或显式迁移步骤。

## 验收标准

1. 在干净机器上，首次安装脚本仅从 canonical GitHub `main` 获取内容，记录实际 commit，并正确安装 Codex 与 Claude 的平台 manifest skill；远端 URL 不符、没有 `main`、manifest 哈希不符或 manifest 试图写到目标目录外时，必须失败且零写入。
2. 安装完成后，`~/.agents/` 保持不变；已核验的 `~/.bridgeforge` junction 不存在；`D:\Quant\BridgeForge` 仍存在且不被安装器作为读取源。
3. 无参数 `/bridgeforge` 能从 GitHub `main` 强制同步全部受管 skill，并删除上游已移除且托管账本登记的 skill；未登记的同名目录必须阻断而不是覆盖或删除。
4. 非 BridgeForge skill 在 `~/.codex/skills/`、`~/.claude/skills/` 中保持不变。
5. 只执行共享 skill 更新时，任何项目的 `.codex`、`.claude`、rule、memory、hook 与项目私有 skill 都不发生修改；当前项目仅在用户确认 `/bridgeforge` 的 dry-run 迁移计划后才允许修改。
6. 新初始化项目不创建 `.agents/`；存量项目仅在显式确认并成功完成当前项目迁移后，不再有 `.agents/`。相关运行时配置、hook、skill 中不存在把 `~/.agents` 或 `~/.bridgeforge` 作为加载源的引用；历史 archive 与 changelog 不在本项扫描范围。
7. 注入 Codex 已替换后 Claude 写入失败、进程中断和目标目录不可写三种故障；重跑无参数 `/bridgeforge` 后，两个平台必须最终收敛到同一 commit。
8. 在非 Windows 平台运行首次安装脚本时，必须在下载、临时目录创建或用户级目录写入前失败退出。

## 风险与约束

- 强制覆盖意味着用户不得在用户级受管 BridgeForge skill 中保留手工改动；必须把通用改动提交到上游 GitHub `main`。
- 删除 `~/.agents/` 和 junction 属于破坏性操作，必须在安装校验成功后执行，并明确区分“删除 junction”与“删除其 target”。
- GitHub 可达性、认证或分支校验失败时，安装/更新必须失败退出，不得回退到本地 BridgeForge 工作副本。
- 首次安装入口在 shared skill 尚未存在前不能依赖 `/bridgeforge`；必须由独立 PowerShell 脚本提供。

## 自动化边界

- 只允许用户显式运行首次安装脚本或显式调用 `/bridgeforge update`。
- 更新在临时副本和校验完成前不得写入用户级 `skills/` 目标。
- 不执行 push、commit、stash、merge、reset 或任何项目级自动同步。

## 实施计划

1. 新增根目录 `shared-skill-manifest.json`、Windows 首次安装脚本和可恢复的共享 skill updater。manifest 将 `bridgeforge` 作为平台托管 command bundle：除入口 `SKILL.md` 外，分发它所需的 `doc/0_architecture/`、`templates/`、项目迁移脚本和 updater；其他通用 skill 按各自目录分发。
2. 将 `/bridgeforge` 改为直接从已安装的 command bundle 运行：无参数时先显式执行共享 skill 更新，再维护当前项目；不再读取、pull 或 fallback 到 `~/.bridgeforge`、`~/.agents` 或本地工作副本。遗留项目 `.agents/` 只在当前项目的 dry-run 与用户确认后迁移。
3. 同步 Codex / Claude 模板及 bridgeforge 自身 dogfood 镜像，清除运行时旧路径假设；补充 manifest、首次安装、托管冲突、第三方保留、故障恢复、非 Windows 零写入与当前项目迁移的自动化测试。
4. 产品层实现完成后，bump 根版本与双端模板版本，追加 `[product]` CHANGELOG，并记录实际验证收据与独立审查结论。

## 实施与验证记录

- 2026-07-25：用户确认按本卡开始开发；只读发现已完成，确认当前仓库尚无生产 manifest / bootstrap / updater，现有分发仍依赖 `~/.bridgeforge` 与旧 Codex `~/.agents/skills` 路径。
- 2026-07-25：已新增 `shared-skill-manifest.json`、Windows 首次安装器和可恢复 updater；manifest 覆盖 Codex / Claude 各 20 个 skill，并将 `bridgeforge` 作为包含入口、references、templates 与运行脚本的 command bundle。根版本升至 `0.64.0`，Codex / Claude 模板分别升至 `0.35.0` / `0.25.0`。
- 2026-07-25：已完成旧运行时退役：无参数 `/bridgeforge` 从已安装 bundle 执行；运行时不再以 `~/.bridgeforge`、`~/.agents` 或本地工作副本为来源。`harvest` 改为要求用户明确提供 canonical 上游 clone；当前项目 `.agents/` 使用独立迁移脚本的 `--dry-run` / 确认 / `--apply` 事务流程。
- 验证：实现 agent 运行 `python tests/harness/test_shared_skill_distribution.py -v`，13/13 通过，覆盖 canonical fetch/HEAD 身份、未托管冲突、第三方保留、强制覆盖、manifest 路径与哈希、真实 crash recovery，以及 Codex 全部 swap 后 Claude 首项真实 swap 失败、回滚和重跑收敛；迁移与双端账本 harness 14 项通过。主线程运行 PowerShell AST 解析（installer / updater）和 `git diff --check`，均通过；最终 manifest SHA-256 为 `19f1eb09de1f1c8bbc0f67c1f9208e2ffbd39caa80fe3f9c606ca6422d11bbc9`。
- 独立复核：review-auditor 三轮读取真实 diff。前两轮提出 canonical 来源、同名私有 skill、遗留 runtime、跨平台故障覆盖与 Claude dogfood 问题，均已修复；第三轮结论“无阻断、可交付”。
- 未验证边界：未访问真实 GitHub/TLS，测试通过 Git URL rewrite 指向本地 bare remote 模拟；未在真实 macOS/Linux PowerShell 执行，非 Windows 零写入由测试开关覆盖。仓库未配置 `.venv` 或项目 Conda 环境，主线程未在本地重跑 Python harness。
