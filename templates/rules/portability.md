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

---

## 2. 必须跟随项目的内容

| 内容 | 项目内路径 | 机制 |
|------|-----------|------|
| Memory | `.claude/memory/` | Junction/symlink，CLAUDE.md §5 自动恢复 |
| Rules | `.claude/rules/` | 直接 git 管理 |
| 项目 Skills | `.claude/skills/` | 直接 git 管理（用户级 skill 不算） |
| 项目设置 | `.claude/settings.json` | hooks、defaultMode、项目级权限 |

---

## 3. 不提交但需按需重建的内容

| 文件 | 说明 | 处理方式 |
|------|------|---------|
| `.claude/settings.local.json` | 本机路径、本机权限覆盖 | `.gitignore` 已排除，换机后按需创建 |
| 用户级 `~/.claude/settings.json` | 全局 effortLevel 等 | 内容简单，换机后手动设置 |

---

## 4. 包安装约束

<!-- TODO: 按本项目主语言定制 -->

**所有包必须安装到项目隔离环境，禁止全局安装。**

### Python

```bash
# 正确 ✅
.venv/Scripts/pip.exe install <package>           # Windows
.venv/bin/pip install <package>                   # Unix

# 错误 ❌
pip install <package>
python -m pip install <package>
```

### Node.js

```bash
# 正确 ✅（项目级，写入 package.json）
npm install <package>
pnpm add <package>

# 错误 ❌（全局安装）
npm install -g <package>
```

### Rust

Rust 工具链（cargo/rustup）是全局的，这是正常的——Rust 依赖通过 `Cargo.toml` 管理，不存在全局污染问题。但 toolchain 版本要锁：

```bash
# 项目根放 rust-toolchain.toml
echo '[toolchain]\nchannel = "1.XX.0"' > rust-toolchain.toml
```

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

### 4.3 关键 binary / DLL / 模型文件由项目自带

> 仅当本项目依赖 native binary（.dll / .so / .dylib）/ 模型文件 / 数据文件时启用本节。

**禁止**依赖第三方 pip 包 / npm 包 / cargo crate 提供"运行时关键 binary"，因为：

- 包版本号可能 ≠ 包内 ship 的 binary 真实版本
- 包升级 / 拉取失败导致 binary 缺失时 debug 困难
- 不同平台 ship 的 binary 可能不一致

**正确做法**：关键 binary 直接 ship 到项目内（如 `<project>/native/<platform>/lib.dll`），git 管理或 git-lfs 管理。

**升级时**用工具核实真实版本（如 native binary 自带的 `GetVersion` API），不要信文件名或包版本号。

---

## 5. hooks 脚本约束

项目 `.claude/settings.json` 中引用的 hook 脚本 **必须** 存放在项目内（如 `.claude/hooks/`），**禁止** 硬编码用户目录路径（如 `C:/Users/<name>/.claude/hooks/`）。

原因：硬编码路径换机即失效，且不同机器用户名可能不同。

---

## 6. 换机恢复流程（预期）

```
git clone <repo>
→ <按主语言初始化项目环境>
→ claude login
→ 开始工作
```

Memory junction 由 CLAUDE.md §5 在首次对话时自动恢复（场景 B），无需手动操作。

**验收标准**：新机器上首次对话时，Claude 能读到全部 memory 和 rules，无信息丢失。
