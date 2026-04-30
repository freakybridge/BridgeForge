# 模块组织范式

> **始终加载** — 新增/移动文件、创建模块时自动生效。

---

## 1. 项目结构

<!-- TODO: 列出本项目的顶层结构和各目录职责
示例（按主语言/技术栈替换）：

```
{{PROJECT_NAME}}/
├── src/                  ← 主代码
│   ├── core/             ← 协调中枢 + 基类 + 横切服务
│   ├── feature_a/        ← 独立 feature
│   ├── feature_b/        ← 独立 feature
│   └── utils/            ← 通用工具
├── tests/                ← 测试
├── doc/                  ← 文档
├── config/               ← 配置
└── .claude/              ← Claude Code 协作配置
```
-->

---

## 2. 新增模块流程

### Step 1：创建目录骨架

<!-- TODO: 按本项目的 feature 目录范式填写
示例（Python）：
```
src/<feature>/
  __init__.py
  service.py          # 主逻辑
  models.py           # 数据模型（如需要）
  tests/              # 模块自包含测试
```

示例（Rust workspace）：
```
crates/<feature>/
  Cargo.toml
  src/lib.rs
```
-->

### Step 2：注册到中枢

<!-- TODO: 描述新模块如何接入协调中枢
示例：
- 在 `src/core/registry.py` 添加注册项
- 在 workspace 的 Cargo.toml `members` 列表追加
-->

### Step 3：验证

<!-- TODO: 给出验证命令
示例：
```bash
<test-command-for-this-module>
<lint-command>
```
-->

---

## 3. 禁止事项

| 层 | 职责 | 禁止 |
|----|------|------|
| 协调中枢（如 `core/` / `app/`） | 协调 + 基类 + 横切服务 | 放具体功能逻辑 |
| Feature 模块 | 独立功能 | import 其他 feature 的内部实现 |

**判断标准**：被 2 个以上 feature 模块使用的代码 → 抽到协调中枢的 `utils/` 或 `base/`；只被单个模块使用的 → 留在该模块目录下。

---

## 4. 跨模块通信

<!-- TODO: 描述模块间如何通信（事件总线 / 接口契约 / DI）
示例：

- 模块间**只通过事件总线 / 接口契约**通信，不直接 import 对方内部
- 共享类型放 `src/types/`，所有模块从这里 import
- 跨模块依赖通过依赖注入而非全局单例

这一节是为了让"模块独立可测、可替换"成为可行。
-->
