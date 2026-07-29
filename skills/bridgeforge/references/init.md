# Init / 既有项目首次接入操作手册

仅当根 `SKILL.md` 判定为全新 init 或“既有项目首次接入”时读取。执行前必须已完成根入口刷新、工厂自检、agent 分流和公共用户级 skill 维护。

## 目录

- 1-3：cwd 冲突、元信息、Python 硬依赖
- 4-8：复制清单、ignore、版本、裁剪、hook 适配
- 9-12：占位符、memory junction、Git、版本戳
- 13-14：能力速查与停止条件

## 1. 核对 cwd 与冲突

确认 cwd 是目标项目根，检查入口文件、配置目录、`doc/` 和 Git 状态。

若已存在当前 agent 的 `$PROJECT_ENTRY_FILE` 或 `$PROJECT_AGENT_DIR/rules/`，且项目没有 `.bridgeforge_version`，必须停下让用户选：

- A：保留现有内容，只补缺失骨架并 merge 配置。
- B：备份后覆盖入口文件/rules。
- C：退出。

禁止把“已有文件”当成覆盖授权。

若 `$PROJECT_AGENT_DIR/settings.json` 已存在，必须读取并 merge：

- Claude 的 `hooks.*`：追加上游通用 hook 注册，不替换已有数组。
- `permissions.allow` / `ask` / `deny`：分别追加去重；只增不删，deny 优先级最高。
- `permissions.defaultMode`：仅用户原配置未设置时写 `acceptEdits`；已设置则保留。
- 其余字段保持原样。

Codex 的项目级 hook 注册只允许 merge 到 `.codex/hooks.json`；按 `command`
身份增补或替换受管的 `memory_junction_check` `SessionStart` 项，并保留所有
第三方事件与 hook。必须从 `.codex/settings.json` 移除旧的
`memory_junction_check` 注册，其他字段不动。保存前给用户 merge 预览。cwd
不是目标根时，先询问正确路径。

## 2. 一次性收集项目元信息

一次问齐：

1. 项目名。
2. 主语言/技术栈：`python` / `rust` / `node` / `go` / `mixed` 等。
3. 目标系统：`windows` / `macos` / `linux` / `cross-platform`。
4. 是否需要换机 checklist（默认需要）。
5. 交付是否按 Milestone 管理：`milestone`（`1_delivery/M1/<topic>/`）或 `flat`（`1_delivery/<topic>/`）。

`mixed` 保留全部 LANG 段；`cross-platform` 保留全部 PLATFORM 段。

BridgeForge 强制铺设 `doc/` 分层，不接受跳过。用户明确不要文档分层时，停止并建议使用其他脚手架。

## 3. Python 硬依赖检查

复制 hooks 前确认有 Python ≥3.8：

1. 优先项目 `.venv`：Windows `.venv/Scripts/python.exe`；Unix `.venv/bin/python`。
2. 否则使用 PATH 中的 `python`。
3. 两者都没有：停止，要求先安装 Python 后重跑。禁止先跳过 hooks。

BridgeForge 的 `version_check`、ctx 预警、snapshot、memory/rules lint 都依赖 Python，且适用于 Rust/Node/Go 项目。用户不接受 Python 硬依赖时，停止并改用纯文档脚手架。

缺 Python 时给出对应修复入口：Windows 可用 python.org 或 `winget install Python.Python.3`；macOS 可用 `brew install python`；Linux 用发行版包管理器安装 `python3`。安装后建议在项目根执行 `python -m venv .venv`，再重跑 `/bridgeforge`。

## 4. 实际复制清单

模板根固定为 `$BRIDGEFORGE_HOME/templates/$TEMPLATE_AGENT/`，禁止整包复制 `templates/`。

| 模板 | 目标 | 条件 |
|---|---|---|
| `$PROJECT_ENTRY_FILE` | 项目根同名文件 | 总是；冲突按 §1 |
| `rules/*.md` | `$PROJECT_AGENT_DIR/rules/` | 总是 |
| `memory/MEMORY.md` | `$PROJECT_AGENT_DIR/memory/MEMORY.md` | 总是 |
| `hooks/*.py` | `$PROJECT_AGENT_DIR/hooks/` | 总是 |
| `scripts/*.py` | `$PROJECT_AGENT_DIR/scripts/` | 总是 |
| `settings.json` | `$PROJECT_AGENT_DIR/settings.json` | 总是；已存在只 merge |
| `hooks.json` | `.codex/hooks.json` | 仅 Codex；按 command 身份 merge 受管项，保留第三方事件与 hook |
| `config.toml` | `.codex/config.toml` | 仅 Codex；已存在按字段 merge，保留项目覆盖 |
| `agents/*.toml` | `.codex/agents/` | 仅 Codex；同名文件冲突必须展示 diff 后决定；根入口 Step 4.5 刚生成的 `implementation-worker.toml` 保留档位字段并补齐模板其余内容 |
| `subscription-tier.toml` | `.codex/subscription-tier.toml` | 仅 Codex；不直接复制，由根入口 Step 4.5 按用户选择写入 |
| `skill-routing.json` | `.codex/skill-routing.json` | 仅 Codex；与 agents 一起复制并验证引用完整 |
| `.githooks/pre-commit` | 项目根 `.githooks/pre-commit` | 仅模板存在时；已有文件只合并 BridgeForge 检查段 |
| `doc/README.md` | `doc/README.md` | 总是；将 `delivery_layout` 替换为用户选择 |
| `VERSION` | 项目根 `VERSION` | 总是；内容来自 `$BRIDGEFORGE_HOME/VERSION` |
| `CHANGELOG.md` | 项目根 `CHANGELOG.md` | 总是 |
| `.bridgeforge_version` | `$PROJECT_AGENT_DIR/.bridgeforge_version` | Step 9 最后写 |
| doc 目录 | `doc/{0_architecture,1_delivery,2_bugs,3_reference,4_archive}/` | 总是 |
| BridgeForge ignore 块 | 项目根 `.gitignore` | 总是，幂等 merge |

初始化 memory 时只复制 `MEMORY.md`。禁止预建空的 `architecture/`、
`engineering/`、`domain/`、`operations/`、`topics/` 或 `_inbox/`；
分类目录只在首条真实记录写入时创建。

## 5. `.gitignore` 机制块

项目无 `.gitignore` 时新建；已有时只补缺行，禁止删除项目自有忽略项：

```gitignore
# === bridgeforge 协作骨架机制自动生成（勿提交，由 bridgeforge skill 维护）===
__pycache__/
*.pyc
.claude/settings.local.json
.codex/settings.local.json
.runtime/session_state/
.runtime/focus/
.runtime/*.log
```

只维护 BridgeForge 自身机制生成物，不替项目决定 `target/`、`node_modules/` 等语言相关规则。

## 6. 版本号 SoT

无论项目根是否存在 `package.json`、`Cargo.toml`、`pyproject.toml` 或 `setup.py`，都**必须**写入根 `VERSION`，其内容直接复制 `$BRIDGEFORGE_HOME/VERSION`。该文件是唯一受 BridgeForge 管理的骨架版本源。

原生 manifest 的版本字段属于下游业务，**禁止**参与 BridgeForge 的版本检查、展示或版本 bump；初始化不得改写它们。始终复制 `CHANGELOG.md`。

## 7. OPTIONAL 段裁剪

复制后、替换占位符前处理：

```text
<!-- OPTIONAL_BEGIN <TYPE>: <VALUE> -->
...
<!-- OPTIONAL_END -->
```

- `PLATFORM: windows|macos|linux`：只保留用户选择的平台；`cross-platform` 全保留。保留内容但删除标记，其他整段删除。
- `LANG: python|rust|node|go`：只保留用户选择的语言；`mixed` 全保留。保留内容但删除标记，其他整段删除。
- `SCENARIO: rewrite|native-binary|build-product-mismatch`：默认保留内容与标记，供后续手动启用。

裁剪后验证所有 `.md` 中 `OPTIONAL_BEGIN PLATFORM` / `OPTIONAL_BEGIN LANG` 计数为 0。

## 8. Python 路径适配与 hook 验证

复制 hooks/scripts 后：

1. `.venv` 存在时，settings 的 hook 命令使用对应 `.venv` Python。
2. 无 `.venv` 但系统 Python 可用时，改用裸 `python`，并在 hook `comment` 尾部提示“建好 .venv 后可改回项目解释器”。
3. conda 项目使用 conda env 的绝对 Python 路径。
4. 当前模板若仍使用 `context_warning.py` 的静态 `WINDOW` 常量：1M 专用模型设 `1_000_000`；标准 200k 模型设 `200_000`。若模板已改为从 session 日志动态读取窗口，禁止再手改不存在的常量。
5. 在目标项目根运行：

```bash
python "$PROJECT_AGENT_DIR/hooks/session_snapshot.py" manual
```

期望输出 `[session snapshot manual] -> .runtime/session_state/<ts>.md`。失败则检查 Python 路径和 `.runtime/` 权限，不得宣称 hooks 已验证。

Codex 若新增或变更 `.codex/hooks.json`，必须让用户执行 `/hooks`，逐项 review 并
trust；随后开启新会话，以实际 `SessionStart` 行为做 smoke。无法在当前流程完成
新会话 smoke 时，收据只能写“trust 未验证”，禁止把 JSON 可解析或脚本直跑当成
已信任。Claude 若新增或变更 `.claude/settings.json` 的 hook，保持 Claude Code
对应的配置 review / trust 流程，并在新会话 smoke；未完成时同样报告“trust 未验证”。

还需告知用户：ctx-budget、PostCompact/Stop snapshot、skill-sync SessionStart 已启用；`find-doc.map.md` / `sync-docs.map.md` 可等项目目录稳定后再填。

## 9. 替换占位符

只替换：

| 占位符 | 值 |
|---|---|
| `{{PROJECT_NAME}}` | 项目名 |
| `{{PRIMARY_LANGUAGE}}` | 主语言 |
| `{{TODAY}}` | 当天 `YYYY-MM-DD` |

架构红线、快速命令、项目结构等 `<!-- TODO: ... -->` 留给用户，禁止代编。

## 10. 建 memory junction

只处理当前宿主，不读取或修改另一套骨架。路径映射：

| 宿主 | 系统 memory | 项目唯一事实源 | SessionStart 承载 |
|---|---|---|---|
| Codex | `~/.codex/projects/<project-hash>/memory/` | `.codex/memory/` | `.codex/hooks.json` |
| Claude Code | `~/.claude/projects/<project-hash>/memory/` | `.claude/memory/` | `.claude/settings.json` |

先只读盘点 junction 状态：

1. 已是指向当前项目 memory 的正确 junction：验证目标后 no-op。
2. 系统 memory 不存在、项目 memory 存在：直接建 junction，并验证最终目标。
3. 系统 memory 是实目录、错误/断裂 junction 或路径异常：阻断 memory 路径写入，
   记录“待维护”，完成其余 init 后提示无参数运行 `/bridgeforge`。

`init` 和 `SessionStart` 都禁止复制、合并或删除系统 memory。实目录迁移只能由
无参数 `/bridgeforge` 的既有项目维护分支展示逐文件计划并取得用户确认后，调用当前宿主脚本
`--mode migrate --confirmed`；禁止创建 `.bak` 或其他备份，同路径异内容、路径异常、
错误或断裂 junction 必须阻断且零写入。

## 11. 可选 Git 初始化

项目未初始化 Git 时可运行：

```bash
git init
git add .
git status
```

只给用户 review，不自动 commit。

## 12. 写版本戳与交付

所有前置步骤成功后才写；Codex 还必须确认根入口 Step 4.5 已成功写入订阅档位 marker 和对应模型配置：

```bash
cp "$BRIDGEFORGE_HOME/VERSION" "$PROJECT_AGENT_DIR/.bridgeforge_version"
```

然后报告用户需要手填的三处：入口文件的架构红线、快速命令、项目结构；并列出可选的 path-specific rules、doc 索引补充和用户自行 commit。

## 13. 模板能力速查

| 内容 | 作用 |
|---|---|
| 入口文件 | 通用红线、交互和 ctx 信号；架构/命令/结构留空 |
| `rules/` | architecture/modules 骨架与 debugging/workflow/portability/meta rule |
| `hooks/` | ctx、版本、snapshot、memory/rules/skill 检查等自动化 |
| `settings.json` | permissions 三档；Claude 还承载 hook 注册；已有配置只 merge |
| Codex `hooks.json` | Codex 项目级 `SessionStart` hook 注册；已有配置只 merge |
| Codex `subscription-tier.toml` / `config.toml` / `agents/*.toml` / `skill-routing.json` | 项目订阅档位、主对话默认档、named agent 预设和 skill 路由契约；必须配套验证 |
| `.githooks/pre-commit` | 提交前聚合硬闸；已有项目只 merge BridgeForge 检查段 |
| `memory/MEMORY.md` | 初始唯一文件；分类与 topic 目录在首次真实写入时创建 |
| `doc/README.md` | 分层唯一索引 |
| `VERSION` / `CHANGELOG.md` | `VERSION` 是唯一骨架版本源，初始化时来自 BridgeForge 根 `VERSION`；业务 manifest 不参与 |
| `.bridgeforge_version` | 下次路由 update 的同步基线 |

## 14. 停止条件

- 不是目标项目根。
- 当前 agent 文件冲突但用户尚未选保留补缺/备份覆盖/退出。
- settings merge 尚未 review。
- 用户拒绝强制 doc 分层或 Python 硬依赖。
- 缺 Python，或 hook 脚本 smoke test 失败。
- Codex 订阅档位未由用户选择，或订阅路由脚本失败。
- 任何步骤需要静默覆盖用户已有内容。

Codex `.codex/hooks.json` 或 Claude hook 配置的 review / trust 与新会话 smoke 未完成时，
交付收据必须写“trust 未验证”，不得宣称 hook runtime 已验收。
