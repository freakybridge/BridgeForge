# 需求：永久 Git Worktree 创建 Skill

> 日期：2026-08-15
> 状态：已验收
> 入口：新增 Codex 用户级 `/create-worktree` / `$create-worktree`，在当前 Git 仓库外创建无槽位永久 worktree，并同步创建独立开发分支。

## 背景与目标

Codex Desktop 自动创建的 worktree 可能使用短槽位目录，并可能以 detached HEAD 启动；手动创建永久 worktree 又容易遗漏分支隔离或项目注册。本需求在 BridgeForge 产品层新增 Windows 专用 `$create-worktree`，把路径、分支和失败边界固化为确定性流程。

目标调用形式：

```text
/create-worktree causis_risk_suite_2 risk-suite-2
/create-worktree causis_risk_suite_2 risk-suite-2 develop
```

预期结果：

```text
工作树：D:\Quant\CodexWorktree\causis_risk_suite_2
分支：codex/risk-suite-2
基准：本地 main 当前指向的提交
```

## 非目标

- 不向发起调用的下游项目写入 skill 或需求文件。
- 不支持 macOS 或 Linux。
- 不迁移、删除、修复或复用已有 worktree。
- 不生成 Codex Desktop 的短槽位目录。
- 不自动执行 `fetch`、`pull`、commit、merge 或 push。
- 不发布到 Claude skill 目录。
- 不自动提交或推送 BridgeForge 本次实现。

## 规模与预算

- 规模：L。
- 已确认预算：90 分钟、约 40k 新 token、最多 3 个子 agent、2 轮验证。
- 本确认卡只完成需求交接；实现由用户进入 BridgeForge 后另行启动。

## 已核实事实

- BridgeForge 的 `skills/**` 是下游可分发的产品层，适合作为本 skill 的单一事实源。
- BridgeForge 使用 `doc/1_delivery/<topic>/` 扁平交付布局。
- Codex 用户配置可通过 `~/.codex/config.toml` 的 `desktop.git-worktree-root` 提供永久 worktree 根目录。
- Codex Desktop 注册的 `codex://threads/new?path=<encoded-path>` 协议可用于打开本地工作区，并避免执行器直接启动 WindowsApps 可执行文件。

## 用户可见行为

### 位置参数

调用按顺序接收两个必填位置参数和一个可选位置参数：

- 第一个：目标工作树的单层目录名。
- 第二个：用户输入不带前缀的分支名。
- 第三个（可选）：创建新分支所基于的本地分支。

缺少前两个参数时必须暂停创建，并一次只询问一个缺失参数。用户禁止被要求输入 `worktree_name=`、`branch_name=` 或 `base_branch=` 这类变量名。第三个参数缺省时优先使用本地 `main`；`main` 不存在时使用本地 `master`；两者均不存在时零写入停止并请用户补充第三个参数。

### 路径规则

- skill 只允许在目标 Git 仓库内调用，并通过 Git 自动识别仓库根目录。
- 当前目录不属于 Git 仓库时必须零写入失败。
- 必须从 `~/.codex/config.toml` 读取 `desktop.git-worktree-root`；缺失、为空或无效时必须零写入失败。
- 目标路径必须严格为 `<desktop.git-worktree-root>\<worktree_name>`。
- 禁止在根目录和工作树名称之间插入槽位、哈希或随机目录。
- `worktree_name` 只能是单个目录名；禁止绝对路径、路径分隔符、`.`、`..` 或任何可逃逸根目录的表达。

### 分支规则

- skill 必须为新 worktree 创建新分支，禁止 detached HEAD。
- `branch_name=risk-suite-2` 必须转换为 `codex/risk-suite-2`。
- 用户已输入 `codex/` 时不得重复添加前缀。
- 完整分支名必须通过 `git check-ref-format --branch` 验证。
- `base_branch` 必须是已存在的本地分支，并只使用其当前指向的提交。
- 未传入基准分支时必须按 `main` 后 `master` 的固定优先级选择，禁止使用当前分支或其他推断值。
- 禁止自动访问远端或更新本地基准分支。

### 创建前硬闸

所有检查必须在创建目录或 Git 引用之前完成：

- 源仓库存在已修改、已暂存或未跟踪文件时暂停创建，要求用户处理后重新调用。
- 目标路径已存在时停止。
- 完整目标分支已存在时停止。
- 任一输入、配置或 Git 状态检查失败时保持零写入。
- 禁止自动覆盖、删除、复用、改名或添加数字后缀。

### 创建与 Codex 注册

- 通过 Git 原生命令一次性创建目标 worktree 和 `codex/` 新分支。
- 创建成功后验证目标路径、当前分支、HEAD 和 `git worktree list --porcelain` 登记结果。
- Git 验证通过后通过 Windows Shell 启动 `codex://threads/new?path=<encoded-path>`，注册并打开 Codex 项目。
- 如果 Codex Desktop 协议激活失败，必须保留已创建的工作树与分支，报告“部分成功”，并输出可复制的重试命令。
- 禁止因为 Codex 打开失败而自动删除有效的 Git 成果。

## 自动化边界

允许的外部变更只有：

- 在已配置根目录下创建一个明确命名的 worktree。
- 在源仓库创建一个明确命名的 `codex/` 分支。
- 请求 Codex Desktop 注册并打开该路径。

禁止修改源工作树的当前分支、HEAD、文件内容、暂存区或远端状态；禁止任何自动清理或破坏性回滚。

## BridgeForge 产品传播

1. 单一事实源：`skills/create-worktree/`。
2. 传播目标：BridgeForge 现有 shared-skill 分发清单中的 Codex 用户级 skill 目录；不传播到 Claude。
3. 版本治理：实现时同步 BridgeForge 产品版本与 `CHANGELOG.md`，不得静默增加受管产品。
4. 验证责任：验证 skill 元数据、分发清单、用户级安装结果及 Windows 端到端行为。

该 skill 是用户级显式入口，不加入下游项目的项目级 skill routing。

## 预计实现范围

- 新增 `skills/create-worktree/SKILL.md`。
- 新增低自由度、确定性的 Windows PowerShell 创建脚本。
- 新增 `skills/create-worktree/agents/openai.yaml`。
- 接入现有 Codex shared-skill 分发清单。
- 同步必要的版本、`CHANGELOG.md` 与文档。
- 用 BridgeForge metadata 门卫校验用户可调用的兼容 metadata；单独记录 OpenAI 当前 `quick_validate.py` 不接受该扩展字段。

## 验收清单

- [x] 在干净的临时 Git 仓库中，以两个必填位置参数成功创建直接路径 worktree。
- [x] 省略第三个参数时优先使用本地 `main`，没有 `main` 时回退到本地 `master`，两者均无时零写入失败。
- [x] 新 worktree 当前分支为自动补前缀后的 `codex/<branch_name>`，且不是 detached HEAD。
- [x] 原工作树的当前分支、HEAD、文件与暂存区不变。
- [x] `git worktree list --porcelain` 登记路径中不存在槽位层。
- [x] 已修改、已暂存、未跟踪三类脏状态均在任何写入前停止。
- [x] 前两个参数缺失时一次只询问一个，且不要求用户输入变量名。
- [x] 非 Git 目录、缺失根目录配置、非法目录名、非法分支名、本地基准分支缺失均零写入失败。
- [x] 目标路径冲突和目标分支冲突均零写入失败，不自动修复。
- [x] 测试证明创建过程没有执行 `fetch`、`pull`、commit、merge 或 push。
- [x] Codex Desktop 协议激活成功时调用注册打开命令；失败时保留 Git 成果并给出重试命令。
- [x] BridgeForge skill 元数据检查、PowerShell 脚本测试和临时仓库端到端测试通过；OpenAI 当前 `quick_validate.py` 对 `user_invocable` / `argument` 报不支持，不伪报为通过。
- [x] shared-skill 分发验证证明该 skill 只安装到 Codex 用户级目录。
- [x] `git diff --check` 通过，并形成包含命令、断言和覆盖场景的验证收据。

## 假设与风险

- 假设运行环境安装了 Git，并能定位 `codex` CLI；CLI 缺失只影响 Codex 注册阶段，不撤销 Git 成果。
- Codex 配置键或 CLI 行为未来可能变化；实现必须把解析与命令失败转成明确错误，不得猜测替代路径。
- Windows 路径可能包含空格或非 ASCII 字符；脚本必须使用结构化参数传递，禁止字符串拼接执行命令。
- Git 创建命令若自身留下异常中间状态，首版只报告诊断信息，不进行破坏性自动清理。

## 确认记录

- 2026-08-15：用户逐项确认目标路径、必填参数、`codex/` 前缀、脏仓库硬闸、冲突策略、Codex 注册、失败保留、Windows/Codex-only 范围及本地基准分支规则。
- 2026-08-15：用户确认需求卡准确，并要求将需求交接到 BridgeForge，后续在 BridgeForge 内开发。
- 2026-08-15：实现前 discovery 发现 BridgeForge 旧 metadata 门卫强制 `user_invocable` / `argument`，与 OpenAI 当前 `quick_validate.py` 的标准 frontmatter 冲突；用户确认更新门卫，采用向后兼容方案继续开发。
- 2026-08-15：独立审计发现 reparse point 路径逃逸与 Unicode 上标设备名缺口；用户批准修复，并将验证预算从 2 轮增加至 3 轮。
- 2026-08-15：用户要求与 `summary` 一样进入斜杠命令清单，改为两个必填位置参数和一个可选基准分支，并明确缺省顺序为 `main` 后 `master`。
- 2026-08-15：用户要求 Skill 选择后的 UI 展示文本为精确的 `create-worktree`，不使用中文展示名。
- 2026-08-15：用户显式调用 `$summary 同意验收`，本交付关闭。
- 2026-08-15：用户验收协议启动补丁；确认清理试用产生的 `D:\Quant\CodexWorktree\aaa` 与 `codex/bbb` 后，再次执行 `$summary 同意验收`。
- 2026-08-15：用户验收协议启动补丁；确认清理试用产生的 `D:\Quant\CodexWorktree\aaa` 与 `codex/bbb` 后，再次执行 `$summary 同意验收`。

## 实施计划

1. 使用 `$skill-creator` 初始化 `skills/create-worktree/`，实现低自由度 PowerShell 创建脚本与显式入口元数据。
2. 让 Codex/Claude metadata hook 同时接受既有 BridgeForge 格式与 OpenAI 当前标准格式，并同步模板、dogfood 镜像及测试。
3. 将 skill 仅接入 Codex shared-skill 清单，更新产品版本与 CHANGELOG，并执行临时仓库、分发和静态验证。

## 实施记录

- 2026-08-15：完成 L 级规模与预算硬闸；预算维持 90 分钟、约 40k 新 token（平台无可靠计量，未实测）、最多 3 个子 agent；独立审计后验证预算由 2 轮增至 3 轮。
- 2026-08-15：只读 discovery、实现、三轮验证和首次独立审计已完成；审计发现的 reparse point 路径逃逸与 Unicode 上标设备名缺口已修复并回归。
- 2026-08-15：根据用户试用反馈补齐斜杠调用 metadata，将 Skill 与 PowerShell 脚本改为两必填、一可选的位置接口，并增加基准分支缺省回归。
- 2026-08-15：将 `agents/openai.yaml` 的 `interface.display_name` 改为 `create-worktree`，并增加静态契约测试。

## 验证记录

- 第一轮（implementation）：`test_create_worktree_skill.py` 10/10、`test_skill_metadata_budget.py` 7/7、shared-skill inventory/Codex-only 安装与 downstream 隔离检查通过；`quick_validate.py`、PowerShell 解析、manifest、镜像与 `git diff --check` 通过。
- 第二轮（主 agent）：
  - `.venv\Scripts\python.exe tests\harness\test_create_worktree_skill.py`：10/10，通过成功创建、分支前缀、三类脏状态、配置/输入/冲突零写入、Codex 成败分支与禁止命令契约。
  - `.venv\Scripts\python.exe tests\harness\test_skill_metadata_budget.py`：7/7，通过官方两字段格式与完整 legacy 格式兼容门禁。
  - `.venv\Scripts\python.exe tests\harness\test_shared_skill_distribution.py`：19/19，通过 Codex-only manifest 与安装、Claude 排除及 shared updater 回归。
  - `quick_validate.py skills\create-worktree`：`Skill is valid!`；`rebuild_shared_skill_manifest.py --check`：清单为当前状态。
  - `.codex\hooks\skill_metadata_check.py --pre-commit`、`.codex\hooks\mirror_drift_check.py --pre-commit`、`.codex\scripts\factory_version_check.py`：退出码 0。
  - PowerShell AST 解析与 `git diff --check`：退出码 0。
- 第三轮（审计修复回归）：真实创建 junction 后验证配置根目录在任何 Git/路径写入前被拒绝；`LPT².txt` 验证 Unicode 上标设备名零写入拒绝；2/2 定向测试通过，0 skip，manifest 重建后 `--check` 通过。
- 用户试用修订：`test_create_worktree_skill.py` 13/13，覆盖斜杠调用契约、省略基准时优先 `main`、回退 `master` 及两者缺失时零写入；metadata 门卫 7/7，PowerShell AST 解析通过。
- 独立审计：首次审计确认主体流程、metadata 镜像、Codex-only 分发和版本治理正确，并发现两项运行时边界缺口；两项均已修复，修复后只读复核通过，无仍存阻塞问题。

## 剩余风险与试用边界

- 自动化测试使用真实 Windows Git 与可控的 `Start-Process` 替身，已验证 deep link 的路径编码、成功/异常分支及失败保留；未在测试中实际打开 Codex Desktop GUI，真实注册显示留给用户试用确认。
- 2026-08-15 补充修复：用户实测提升权限后的 `codex app` 仍因执行器直接访问 WindowsApps `codex.exe` 而报 `Access is denied`；实现改为通过 Windows 注册协议 `codex://threads/new?path=...` 激活 Desktop，`test_create_worktree_skill.py` 13/13 通过。
- Codex Desktop 斜杠菜单发现依赖用户级 Skill 刷新；安装后若当前对话未刷新，需重启 Codex 再试。
- reparse point 采用 fail-closed：源仓库或配置根目录的任一现存祖先带 junction/symlink 属性时拒绝创建，不尝试解析或接受该路径。
