# git-sync 沙箱 Git 元数据权限验证报告

**状态**：pending  
**日期**：2026-07-17  
**来源**：下游 `D:\Quant\StratusAgent` 实机验证

## 结论

`git-sync` 在受限 Codex 沙箱中失败的根因，是 `git fetch` 无法写入仓库的 `.git/FETCH_HEAD`；不是下游仓库状态、`codex_git_sync.py` 逻辑、分支分叉或 Git TLS 后端问题。

同一条同步命令以沙箱外权限重试后成功返回 `[git-sync] synced; working tree clean`。因此，骨架的 `git-sync` skill 应定义一个窄的恢复规则：首次在 `git fetch` / `.git/FETCH_HEAD` 权限阶段失败时，使用完全相同的 repo-local 同步脚本申请沙箱外执行后重试。

## 验证环境与证据

- 下游仓库：`D:\Quant\StratusAgent`，分支 `master...origin/master`，验证前工作区干净。
- Codex 进程身份：`risk-nb01\codexsandboxoffline`。
- `.git` 与 `.git\FETCH_HEAD` 的 ACL 含显式 `DENY` 写入条目；这类拒绝规则优先于允许项。
- Git 已配置 `http.sslBackend=schannel`，排除已知 OpenSSL/TLS 后端差异作为本次原因。

### 首次执行：受限沙箱

```text
.venv\Scripts\python.exe .codex\scripts\codex_git_sync.py --message "chore: 验证 git-sync 沙箱权限"

[git-sync] git fetch origin failed: error: cannot open '.git/FETCH_HEAD': Permission denied
```

### 原命令重试：沙箱外授权

```text
.venv\Scripts\python.exe .codex\scripts\codex_git_sync.py --message "chore: 验证 git-sync 沙箱权限"

[git-sync] synced; working tree clean
```

该验证覆盖了失败路径与权限恢复路径；没有创建提交、没有 push，也没有修改仓库 ACL。

## 建议的骨架改动

目标文件：`skills/git-sync/SKILL.md` 的“Codex 确定性脚本路径”。

在现有“需要审批时只为该项目脚本申请合理前缀”之后，补充以下行为契约：

1. 首次运行 `python .codex/scripts/codex_git_sync.py --message "<类型>: <描述>"`。
2. 若失败输出明确属于 `git fetch`、`.git/FETCH_HEAD`、`Permission denied` 或 `Access is denied`，必须立即用**同一条命令**重试，并以 `require_escalated` 申请沙箱外执行权限。
3. 审批说明必须说明：该操作需要更新当前项目的 `.git/FETCH_HEAD` 等 Git 元数据，以完成用户已授权的同步。
4. 不得为了绕过该限制改用手工 `fetch/add/commit/push`，不得修改 `.git` ACL，也不得扩大到无关目录或命令。
5. 重试仍失败时，保留原始错误与现场并交回主对话；不得把网络、分叉或凭据错误伪报为权限恢复成功。

建议文本：

```md
若首次运行 repo-local 同步脚本在 `git fetch`、`.git/FETCH_HEAD`、
`Permission denied` 或 `Access is denied` 阶段失败，必须立即用同一条脚本命令重试，
并以 `require_escalated` 申请沙箱外执行权限。审批说明必须限定为：允许 Git 更新当前
项目的 `.git/FETCH_HEAD` 等元数据。不得改走手工 Git 命令或修改 `.git` ACL。
```

## 范围与后续

本报告是元文档，不改变产品层。若上游采纳该规则，后续产品层改动应同时：

1. 修改 `skills/git-sync/SKILL.md`；
2. 按现有分发流程刷新本机运行副本；
3. 因产品层行为发生变化，更新版本与 `CHANGELOG.md` 的 `[product]` 条目；
4. 在至少一个受限沙箱和一个正常环境各验证一次，确认前者可授权恢复、后者不额外阻塞。
