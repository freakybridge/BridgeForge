---
paths:
  - ".claude/**"
  - "config/**"
---

# 换机可移植性约束

> 涉及配置文件、memory、settings、hooks 时自动加载。

核心原则：**clone 即恢复，不依赖用户目录下的任何状态。**

---

## 1. 红线

- 所有影响开发体验的配置 **必须** 存放在项目 `.claude/` 内，纳入 git 管理
- **禁止** 在用户目录 (`~/.claude/`) 下创建仅特定机器才有的关键配置
- 新增配置/技能/规则时，默认放项目内，除非明确只对当前机器有意义
- `effortLevel` 是上条的反向例外：**不放项目内、由用户级全局统一管**（项目级会盖全局、顶掉顺手的 slider/`/effort`）。此约束**不靠 rule，由 `SessionStart` hook `enforce_no_effortlevel.py` 机检强制剔除项目级值**（本骨架特征：能机检的红线一律 hook 化）。覆盖关系与决策见 memory `effort-config-layering`。

---

## 2. 必须跟随项目的内容

| 内容 | 项目内路径 | 机制 |
|------|-----------|------|
| Memory | `.claude/memory/` | Junction/symlink，CLAUDE.md §5 自动恢复 |
| Rules | `.claude/rules/` | 直接 git 管理 |
| 项目专属 Skill | `.claude/skills/` | 直接 git 管理。**仅项目独有、bridgeforge 不出品的 skill**（如某项目的 restart-ui） |
| 通用 skill 的项目数据 | `.claude/find-doc.map.md` / `.claude/sync-docs.map.md` 等 | 通用 skill 本体在 bridgeforge，但其**项目专属映射表**留项目内，直接 git 管理 |
| 项目设置 | `.claude/settings.json` | hooks、defaultMode、项目级权限 |

> **通用协作 skill 不进项目 git（单一源拆分）**：plan / escalate / snapshot / find-doc 本体等通用 skill 的**单一源是 bridgeforge**，装到用户级 `~/.claude/skills/`，**不在项目 `.claude/skills/` 留副本**（留副本会 shadow 单一源、各项目漂移；`/bridgeforge` Step 0.5 会清掉）。换机恢复靠在该机跑 `/bridgeforge`（装用户级），不靠 `git clone`。这是 DRY 对 clone-完整性的**有意取舍**；项目专属**数据**（上表 `.map.md`）仍在项目 git，可移植性不受影响。

### 2.1 Memory junction 自愈（SessionStart hook，机制化）

memory 纳入项目 git（`.claude/memory/`），但 Claude Code 读写走系统路径 `~/.claude/projects/<project-hash>/memory/`。**换机 clone 后系统路径不会自动指向项目内 memory** —— 这步恢复由 `SessionStart` hook `.claude/hooks/memory_junction_check.py` 自动兜底，无需人工：

- **project-hash 推导**：从 repo root 绝对路径，**每个非字母数字字符替换为 `-`，大小写原样保留**（如 `D:\Quant\BridgeForge` → `D--Quant-BridgeForge`）。Windows 上 `Path.resolve()` 把盘符规范成大写，与 Claude Code 启动 cwd 的原始大小写可能不一致，但文件系统大小写不敏感，命中同一目录。
- **三情形**：已链接→noop / 系统路径缺失+项目内有→建 junction（新机 clone）/ 系统是实目录→复制进项目 + 原目录改名 `.premigrate.bak`（**绝不硬删**）+ 建 junction。系统与项目同时有内容→拒绝自动合并，提示人工。
- **可移植**：hook 项目无关，靠自身路径推导，无硬编码。

> 这是 §2 表格里「Memory … Junction，CLAUDE.md §5 自动恢复」的实现支点。早期靠人工建 junction（易漏），现由 hook 机制化。

---

## 3. 不提交但需按需重建的内容

| 文件 | 说明 | 处理方式 |
|------|------|---------|
| `.claude/settings.local.json` | 本机路径、本机权限覆盖 | `.gitignore` 已排除，换机后按需创建 |
| 用户级 `~/.claude/settings.json` | 全局默认（effortLevel 等）| 换机后手动设置；**effortLevel 一律在此（全局）管；项目级由 `enforce_no_effortlevel` SessionStart hook 自动剔除，本机配 `reset_effort` SessionEnd hook 还原 medium baseline** |

### 3.1 项目专属授权禁放用户级（红线）

**项目专属 `additionalDirectories` / `permissions.allow` 条目禁放 `~/.claude/settings.json`；被权限弹窗时，优先落本项目 `settings.local.json`（已 `.gitignore`），不扩散用户级。**

用户级只放**共性条目**：通用协作 skill 本体（合法 DRY）、共性安全红线（`deny` 拦截敏感路径）、沟通风格等全项目通用规则。

| 进用户级 = 合法 | 进用户级 = 污染 |
|---|---|
| bridgeforge 出品的通用 skill 本体（plan/escalate/snapshot…） | 项目绝对路径的 allow（`d:\\Quant\\<proj>\\…`） |
| 共性 deny 红线（`~/.ssh`/`.env`/`rm -rf`） | 本机 PID / IP 写死的 allow |
| 沟通风格 / 防空转行为指令 | 一次性 clone / 编译命令的 allow |

> **Why**: 项目专属 allow「随机器走」会在新机污染全局、干扰其他项目；正确落点是已 `.gitignore` 的 `settings.local.json`（换机缺 allow 就按需重建它，别写进用户级）。

---

## 4. 包安装约束

<!-- TODO: 按本项目主语言定制 -->

**红线：所有包必须装到项目隔离环境，禁止全局安装。** 各语言最小命令：

- **Python**：`.venv/Scripts/pip.exe install <pkg>`（Windows）/ `.venv/bin/pip install <pkg>`（Unix）。**禁止**裸 `pip install` / `python -m pip install`（落系统环境）。
- **Node.js**：`npm install <pkg>` / `pnpm add <pkg>`（写入 `package.json`）。**禁止** `npm install -g`（全局）。
- **Rust**：依赖走 `Cargo.toml` 不存在全局污染（cargo/rustup 全局正常），但须 `rust-toolchain.toml` 锁 `channel`。

### 4.1 依赖清单禁止绝对路径 URL（红线）

依赖清单（`requirements.txt` / `package.json` / `Cargo.toml` 等）里**禁止**出现 `pkg @ file:///C:/...` 或 `pkg @ file:///D:/...` 这类硬编码绝对路径的依赖。换机、换盘符、换用户名、换操作系统都会立即 fail。

**正确写法**：本地包放 `libs/` 目录，用相对路径 / `--find-links` 引用：

```
# requirements.txt 顶部
--find-links libs/
mypackage==1.0.0
```

```jsonc
// package.json
"dependencies": {
  "mypackage": "file:./libs/mypackage-1.0.0.tgz"  // 相对路径
}
```

### 4.2 依赖清单注释编码限制（红线）

部分工具（如 Windows 上的 pip）默认用本地编码（GBK / cp936）解析依赖清单。**保险做法**：注释只用 ASCII，中文说明放 `README.md` 或 `doc/setup/`。

<!-- OPTIONAL_BEGIN LANG: python -->
### 4.3 venv 不可移植，目录改名 / 移位后必须重建（红线）

Python `venv` 在 `pyvenv.cfg` + `activate.bat` + `activate` 三处硬编码创建时的项目绝对路径。**项目目录改名 / 整体移动 / clone 到新机后复用旧 venv** 都会让 activate **静默失败**（errorlevel = 0 不报错），后续命令回落到系统 Python，装包阶段才以"requires Python >=X.Y"等版本不符报错。

**正确做法**：改名 / 移位后直接 `rm -rf .venv`，让启动脚本重建。**禁止**用 sed 改路径（容易漏文件，且未来 venv 内部可能藏其他路径引用）。

**诊断信号**：装包日志里 `Requirement already satisfied: pip in <系统 python 路径>` ≠ `.venv/...` → activate 失效。
<!-- OPTIONAL_END -->

<!-- OPTIONAL_BEGIN PLATFORM: windows -->
### 4.4 Windows 批处理 / PowerShell 脚本必须 CRLF（红线）

`.bat` / `.cmd` / `.ps1` 文件**必须**用 CRLF (`\r\n`) 行尾。LF 行尾在 `cmd.exe` 下会让 `goto label` 静默失败，症状是"闪退"或 `The system cannot find the batch label specified`。

**正确做法**：

- 项目根 `.gitattributes` 锁定：
  ```
  *.bat text eol=crlf
  *.cmd text eol=crlf
  *.ps1 text eol=crlf
  ```
- AI / Linux 工具链生成这些文件后**必须** verify：`od -c file.bat | head -3` 应见 `\r\n`
- 不要依赖 Git autocrlf — `.gitattributes` 才是单一权威

**调试 trick**：用户报"双击 .bat 闪退" → **先查行尾**，不要从 batch 逻辑找 bug。

### 4.4.1 入口启动脚本 `.vbs` / `.bat` 必须 ASCII-only（红线）

**双击运行的入口脚本（`start.vbs` / `start.bat` / `*.cmd` / `*.ps1`）的注释、字符串、MsgBox / echo 文案一律只用 ASCII，中文放 `README.md` / `doc/`。**

**Why**：WSH / cmd.exe 按系统 codepage（GBK / cp936）解析，"含中文 + 编码非当前 codepage"必爆；规定"GBK 无 BOM"也不可靠（编辑器易改回 UTF-8 而不察觉）。典型症状：GBK 环境下中文 echo 启动闪退；UTF-8 无 BOM 的 `.vbs` 报 `800A0409 未结束的字符串常量`。

- 改这类脚本禁止写中文；已有中文的整文件 rewrite（不要 Edit 替换，避免残留中文字节）
- Verify：`Select-String -Pattern '[一-鿿]'` 应无匹配
- **调试 trick**：双击报 `800A04xx` / 闪退 / 字符串未结束 → **先查非 ASCII 字符**，别从脚本逻辑找 bug
- **例外**：纯内部、非双击、不上同事机器的脚本可保留中文（仍建议 ASCII 化）
<!-- OPTIONAL_END -->

<!-- OPTIONAL_BEGIN LANG: python -->
### 4.5 项目内源码包必须由启动脚本显式 editable 安装（红线）

项目内源码包（`libs/<pkg>/setup.py`）**不能**只靠 `requirements.txt` 拉起（pip 不扫 `libs/`），必须在启动脚本里显式跑 `pip install -e libs/<pkg> --no-deps`，且**做幂等判断**（已装则跳过，避免每次重装）。

- **为什么必须装进 venv**：仅靠 `sys.path` import 时，包内 `pkg_resources.get_distribution(...).version` 反射查询找不到 distribution 会返回 None，下游版本比较/鉴权静默崩（典型 `TypeError: '<' not supported between NoneType and str`）。
- **为什么 `--no-deps`**：依赖已在 `requirements.txt` 锁版本，再解析会被源码包 `install_requires` 拉到不兼容新版覆盖。
<!-- OPTIONAL_END -->

<!-- OPTIONAL_BEGIN SCENARIO: native-binary -->
### 4.6 关键 binary / DLL / 模型文件由项目自带

**禁止**依赖第三方 pip 包 / npm 包 / cargo crate 提供"运行时关键 binary"（因为：包版本号 ≠ 包内 binary 真实版本、拉取失败时 binary 缺失难 debug、跨平台 ship 可能不一致）。

**正确做法**：关键 binary 直接 ship 到项目内（如 `<project>/native/<platform>/lib.dll`），git 或 git-lfs 管理。

**升级时**用工具核实真实版本（如 native binary 自带的 `GetVersion` API），不要信文件名或包版本号。
<!-- OPTIONAL_END -->

---

## 5. hooks 脚本约束

项目 `.claude/settings.json` 中引用的 hook 脚本 **必须** 存放在项目内（如 `.claude/hooks/`），**禁止** 硬编码用户目录路径（如 `C:/Users/<name>/.claude/hooks/`）。

原因：硬编码路径换机即失效，且不同机器用户名可能不同。

### 5.1 dogfood 镜像红线（骨架仓库：templates/hooks ↔ .claude/hooks 文件齐全）

> 仅对**同时含 `templates/hooks/` 与 `.claude/hooks/` 的骨架仓库（如 bridgeforge 自身）**生效。纯下游项目无 `templates/`，`mirror_drift_check.py` 自门控 no-op，本节对你无感。

- **文件齐全（红线，机检硬拦）**：`templates/hooks/*.py` 的每个 hook **必须**在 `.claude/hooks/` 有对应文件（发给下游的 hook 自己也得装 = dogfood）。缺文件由 `mirror_drift_check.py` 在 `.githooks/pre-commit` **exit 2 硬拦**。
- **正文差异（软提示）**：两侧 `.py` 正文（归一化 `.venv`↔系统 python 前缀后）应逐字一致；不一致只 stderr 软提示、**不阻断**（合法差异不止 python 前缀，逐字一致当硬闸会误伤 → 只降软）。前缀差异只该出现在 `settings.json` / `pre-commit` 命令行，不在 `.py` 里。
- **硬拦豁免**：纯下游业务、本 repo 永远跑不到的 hook 可豁免——在 `CHANGELOG.md` 顶部当条加 `[dogfood-exempt: <hook> <因>]` + 一行 Why 指针（memory `feedback-dogfood-hook-gap`）。

---

## 6. 换机恢复流程（预期）

```
git clone <repo>
→ <按主语言初始化项目环境>
→ claude login
→ 开始工作
```

> Memory junction 首次对话自动恢复（§5 / §2.1），无需手动。
