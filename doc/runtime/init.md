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

- `hooks.*`：追加上游通用 hook 注册，不替换已有数组。
- `permissions.allow` / `ask` / `deny`：分别追加去重；只增不删，deny 优先级最高。
- `permissions.defaultMode`：仅用户原配置未设置时写 `acceptEdits`；已设置则保留。
- 其余字段保持原样。

保存前给用户 merge 预览。cwd 不是目标根时，先询问正确路径。

## 2. 一次性收集项目元信息

一次问齐：

1. 项目名。
2. 主语言/技术栈：`python` / `rust` / `node` / `go` / `mixed` 等。
3. 目标系统：`windows` / `macos` / `linux` / `cross-platform`。
4. 是否需要换机 checklist（默认需要）。

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
| `config.toml` | `.codex/config.toml` | 仅 Codex；已存在按字段 merge，保留项目覆盖 |
| `agents/*.toml` | `.codex/agents/` | 仅 Codex；同名文件冲突必须展示 diff 后决定；根入口 Step 4.5 刚生成的 `implementation-worker.toml` 保留档位字段并补齐模板其余内容 |
| `subscription-tier.toml` | `.codex/subscription-tier.toml` | 仅 Codex；不直接复制，由根入口 Step 4.5 按用户选择写入 |
| `skill-routing.json` | `.codex/skill-routing.json` | 仅 Codex；与 agents 一起复制并验证引用完整 |
| `.githooks/pre-commit` | 项目根 `.githooks/pre-commit` | 仅模板存在时；已有文件只合并 BridgeForge 检查段 |
| `doc/README.md` | `doc/README.md` | 总是 |
| `VERSION` | 项目根 `VERSION` | 仅无原生版本源时 |
| `CHANGELOG.md` | 项目根 `CHANGELOG.md` | 总是 |
| `.bridgeforge_version` | `$PROJECT_AGENT_DIR/.bridgeforge_version` | Step 9 最后写 |
| doc 目录 | `doc/{0_architecture,1_plan,1_plan/sprints,2_pending,3_design,4_archive,9_reference}/` | 总是 |
| BridgeForge ignore 块 | 项目根 `.gitignore` | 总是，幂等 merge |

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

检测项目根：

- `package.json`
- `Cargo.toml`
- `pyproject.toml` / `setup.py`，且含 version 字段

任一原生版本源存在：跳过模板 `VERSION`，仍复制 `CHANGELOG.md`，并说明以后只 bump 原生版本源。全部不存在：复制模板 `VERSION`（初始 `0.1.0`）和 `CHANGELOG.md`。

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

Claude Code：按平台运行 BridgeForge 脚本；先让用户 review，不静默 sudo。

```powershell
& <BRIDGEFORGE_HOME>\scripts\setup-junction.ps1 -ProjectPath <project-abs-path>
```

```bash
bash "$BRIDGEFORGE_HOME/scripts/setup-junction.sh" <project-abs-path>
```

脚本把 `~/.claude/projects/<project-hash>/memory/` 链到 `<project>/.claude/memory/`。已有正确链接则跳过；已有非空实目录则先提示备份，禁止硬删。

Codex 不运行 Claude 脚本，改为：

```bash
python .codex/hooks/memory_junction_check.py
```

Codex 系统路径是 `~/.codex/projects/<project-hash>/memory/`，项目路径是 `.codex/memory/`。系统路径是有内容实目录时，先复制进项目 memory，再把系统目录改名 `.bak`，最后建链接；禁止硬删。

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
| `settings.json` | permissions 三档与 hook 注册；已有配置只 merge |
| Codex `subscription-tier.toml` / `config.toml` / `agents/*.toml` / `skill-routing.json` | 项目订阅档位、主对话默认档、named agent 预设和 skill 路由契约；必须配套验证 |
| `.githooks/pre-commit` | 提交前聚合硬闸；已有项目只 merge BridgeForge 检查段 |
| `memory/MEMORY.md` | 空索引与命名说明 |
| `doc/README.md` | 分层唯一索引 |
| `VERSION` / `CHANGELOG.md` | 项目版本与变更记录；原生版本源优先 |
| `.bridgeforge_version` | 下次路由 update 的同步基线 |

## 14. 停止条件

- 不是目标项目根。
- 当前 agent 文件冲突但用户尚未选保留补缺/备份覆盖/退出。
- settings merge 尚未 review。
- 用户拒绝强制 doc 分层或 Python 硬依赖。
- 缺 Python、memory junction 冲突、hook smoke test 失败。
- Codex 订阅档位未由用户选择，或订阅路由脚本失败。
- 任何步骤需要静默覆盖用户已有内容。
