# shared-skill manifest 换行符哈希不一致

**状态**：fixed  
**日期**：2026-07-26  
**影响范围**：从 GitHub 安装用户级 `/bridgeforge` 的 Windows 下游项目

## 现象

安装器在下载 GitHub `main` 后，`bridgeforge_shared_update.ps1` 对
`CHANGELOG.md`、`shared-skill-manifest.json` 等文件执行 SHA-256 自校验失败，
因此在写入用户目录前停止。

## 根因

旧 manifest 由 Windows 工作区的原始文件字节生成。该工作区可因
`core.autocrlf` 取得 CRLF；GitHub 中同一文本 Git blob 是 LF。文本视觉相同，
字节不同，SHA-256 必然不同。安装器 clone 也继承用户的全局
`core.autocrlf`，使问题随安装机器的 Git 配置复现。

## 修复

1. `.gitattributes` 统一 Git 管理的文本为 LF。
2. 发布源依赖 `.gitattributes` 固定 LF；安装回归在用户全局 `core.autocrlf=true` 下验证 GitHub 等价字节，不再把某个 clone 参数写成唯一保证。
3. 新增 `scripts/rebuild_shared_skill_manifest.py`，将文本 CRLF 规范化为 LF 后
   计算 manifest 哈希；repo 的 `codex_git_sync.py` 在暂存前自动运行该脚本。

## 验收

回归测试创建 CRLF 源文件，并模拟用户全局 `core.autocrlf=true`。GitHub 等价
LF manifest 经安装器 clone 后完成两端（Codex / Claude）安装，验证不再出现
SHA-256 mismatch。

## 2026-08-15 系统重构复核

- `rebuild_shared_skill_manifest.py` 继续按 Git blob 等价 LF 字节计算 hash。
- 重建器 `--check` 已收紧为只读；发现 stale 时只返回非零，不再顺手改 manifest/contract。
- CRLF、LF 与 `core.autocrlf=true` 回归仍属于发布硬闸，本 Bug 保持 `fixed`。
