# Codex 项目操作指南

## AGENTS 项目专区

项目级约束只写入根 `AGENTS.md` 的 `BRIDGEFORGE:PROJECT` 区域，或写入对应目录的嵌套 `AGENTS.md`。禁止修改 `BRIDGEFORGE:PUBLIC` 区域；编辑后 hook 会提示，pre-commit 会同时检查工作树与 staged blob，因而“先暂存公共区修改、再恢复工作树”不能绕过硬闸。

项目专区固定包含项目架构红线、业务与安全红线、目录地图、快速命令和目录级 AGENTS 索引。嵌套 `AGENTS.md`、项目自有 hook、项目 handler 与 pre-commit extension 均是项目资产，bridgeforge-codex 不覆盖、不删除、不重新格式化。

## 文档治理

`doc/README.md` 是文档唯一索引。`0_architecture` 放长期架构，`1_delivery` 放未验收交付，`2_bugs` 放未解决 Bug，`3_reference` 放操作参考，`4_archive` 放已验收或过时记录。新增、删除、移动文档时同步索引，完成交付通过 `$archive-scan` 归档。

## 换机与依赖

clone 后先建立项目虚拟环境，再从受版本控制的依赖清单安装。Python 使用 `.venv/Scripts/pip.exe` 或 `.venv/bin/pip`；Node 依赖写入 `package.json`；Rust 依赖写入 `Cargo.toml` 并用 `rust-toolchain.toml` 锁定 toolchain。目录改名或移动后重建 venv，不复用内含旧绝对路径的环境。

禁止在用户目录保存项目才能运行的关键配置，禁止在依赖清单中写本机绝对路径。机器特定凭据只提供受版本控制的示例与重建步骤，不提交真实凭据。

## 版本域隔离

项目根 `VERSION` 是下游业务版本的唯一事实源；语言原生 manifest 可以镜像业务版本，但必须由项目发布流程同步。`.codex/.bridgeforge_codex_version` 只表示 bridgeforge-codex 骨架版本，只能由统一项目同步器在资产和验证全部通过后最后写入。业务发布、普通提交和本地骨架定制不得修改骨架版本戳。

统一项目同步器准备报告 ready 且实际修改受管资产时还必须通过只读 release preflight；即使
骨架戳已经是当前版本也不得跳过。该预检与 `$git-sync` 使用同一
ownership classifier，且不得修改业务 `VERSION`、CHANGELOG、Git index 或历史。失败时本轮骨架
写入回滚并输出逐文件 `G*` 清单，禁止先写新戳或以“无需改戳”为由把提交问题留给用户处理。

## 大版本依赖升级 Spike

因性能、UI 行为、字体等可感知体验而跨大版本升级依赖前，必须先在主项目外建立最小复现，限定 2–4 小时验证核心诉求。使用新版依赖与最小代码，同现状做截图、benchmark 或可复核的主观对比；只有用户确认体验确实改善后才启动全项目升级。若没有改善，停止升级并保留 spike 结论。

禁止先修改主项目或 lockfile 再验证；禁止只依据 CHANGELOG 宣称体验改善；禁止把“升级完成”当作“诉求已验证”。
