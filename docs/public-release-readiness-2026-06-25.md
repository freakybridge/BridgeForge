# setup_agent 公开发布风险评审（2026-06-25）

> 评审对象：GitHub 仓库 `freakybridge/setup_agent`（拟设为 public）
> 评审范围：当前工作树全文 + 全 git 历史（40 commits）+ `.claude/memory/` 实际内容 + `settings.json`
> 结论：**可以公开 —— 无凭证级风险，但有几个"隐私 / 商业画像"项建议先权衡**

---

## 结论速览

骨架本体（hooks / skills / templates）是干净的通用工具，公开无碍。**唯一真正需要你拍板的是下游私有项目被公开点名**这一项；其余为 GitHub 通病级的轻微信息暴露。

---

## ✅ 阻断性风险：无（已逐项核查）

| 检查项 | 结果 |
|--------|------|
| 硬编码密钥 / token / 密码 / 私钥 / API key | **无**。命中项全是变量名（`CONTINUATION_TOKENS`）、token 用量统计、脱敏指南占位 |
| 公司内网域名:端口 | **无**。`causis.com.cn` 等真实内网地址未出现；只有脱敏指南里的 `causis.internal/...` 占位示例 |
| 真实 IP | **无**。只有脚本里的 `192.168.1.1` 示例值 |
| git 历史删除过的敏感数据文件 | **无**。删过的文件都是骨架自身 hook/skill（`memory_guard.py` / `prune-memory` / `session-tag`） |
| `.claude/memory/` 实际内容 | **干净**。全是 setup_agent 自身的版本开发状态，无下游业务机密 |

---

## ⚠️ 低风险项（非泄密，是"暴露商业活动画像"，是否在意由你决定）

### 1. 下游私有项目被公开点名 + 链接（**唯一需要拍板的项**）

- **在哪**：`README.md` / `CHANGELOG.md` / `docs/*.md` 大量出现真实项目名：
  - `StratusAgent`（量化交易终端，Rust + Python）
  - `causis_risk_suite`（金融风控）
  - `causis_api`、`ClaudeBridgeAssist`
  - 并附 `github.com/freakybridge/StratusAgent` 等仓库链接
- **影响**：代码没泄，但等于公开承认你在做这些量化 / 风控项目及其技术栈（多 Gateway / CTP / vnpy_ctp）。`causis` 可关联到真实公司。
- **若介意**：公开前把 README / CHANGELOG / docs 里的真实项目名 + 链接批量替换成通用占位（`<下游项目>` / `<量化项目>` / `<风控项目>`）。工作量中等——约 10 来个文件里的几十处。

### 2. 个人邮箱

- **在哪**：所有 commit 的 author = `bridgexue2021@gmail.com`
- **影响**：公开后可被爬虫收集
- **若介意**：改用 GitHub `noreply` 邮箱并重写历史（`git filter-repo` / `git rebase`）

### 3. Windows 用户名 + 本机目录结构

- **在哪**：示例路径 `C:\Users\bridg`、`D:\Quant\` 下并列多个量化项目
- **影响**：轻微信息暴露；用户名 `bridg` 本就随 commit author 暴露
- **若介意**：把文档示例路径泛化为占位（多数已是说明性示例，优先级最低）

---

## 建议处置

1. **若不介意点名下游项目** → 直接公开，无需改动。
2. **若介意（推荐先做第 1 项）** → 跑一次"脱敏 PASS"，把真实项目名 / 链接换成通用占位后再公开；第 2、3 项视个人偏好可选。

> 备注：本评审基于 2026-06-25 的工作树与历史快照。后续若有新 commit 引入凭证 / 内网地址，需在 push public 前用 `docs/reverse-sync-playbook.md §3` 的脱敏 checklist 复查。
