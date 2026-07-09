# 调查报告：Codex 模板 `.githooks/pre-commit` 带 BOM 导致 Git 无法 spawn

日期：2026-07-07
来源项目：`D:\Quant\CausisRiskSuite`
上游项目：`D:\Quant\BridgeForge`

## 结论

`templates/codex/.githooks/pre-commit` 文件头带 UTF-8 BOM。下游硬切到 Codex 骨架后，Git for Windows 执行 pre-commit 时会把 shebang 读坏，表现为：

```text
error: cannot spawn .githooks/pre-commit: No such file or directory
```

这不是 hook 文件缺失；文件存在，但首字节是 `EF BB BF`，导致 `#!/bin/sh` 不在文件真实起点。

## 直接证据

下游 `CausisRiskSuite` 首次提交时失败：

```text
error: cannot spawn .githooks/pre-commit: No such file or directory
```

当时检查文件存在：

```text
D:\Quant\CausisRiskSuite\.githooks\pre-commit
Length: 2385
```

当时文件头：

```text
00000000   EF BB BF 23 21 2F 62 69 6E 2F 73 68 ...
```

手动去掉 BOM 后，文件头变为：

```text
00000000   23 21 2F 62 69 6E 2F 73 68 ...
```

随后提交成功：

```text
[main 745dfbf] chore(bridgeforge): 硬切 Codex 协作骨架 [skip-version]
```

## 上游复查

当前 BridgeForge 仓库里三份 pre-commit 的状态不一致：

```text
D:\Quant\BridgeForge\templates\codex\.githooks\pre-commit
00000000   EF BB BF 23 21 2F 62 69 6E 2F 73 68 ...

D:\Quant\BridgeForge\templates\claude\.githooks\pre-commit
00000000   23 21 2F 62 69 6E 2F 73 68 ...

D:\Quant\BridgeForge\.githooks\pre-commit
00000000   23 21 2F 62 69 6E 2F 73 68 ...
```

因此风险集中在 Codex 产品模板。新下游若从 `templates/codex/.githooks/pre-commit` 复制，会继承这个 BOM。

## 影响

- 下游已经设置 `core.hooksPath=.githooks` 时，`git commit` 会直接失败。
- 报错看起来像文件不存在，容易误导排查方向。
- `git status` / `git add` / 普通 hook 脚本内容检查都可能显示正常，直到提交阶段才暴露。

## 建议修复

1. 立刻去掉 `templates/codex/.githooks/pre-commit` 文件头 BOM，保持首字节为 `#`。
2. 给 BridgeForge 自身增加一个轻量校验：所有 `.githooks/pre-commit`、`templates/*/.githooks/pre-commit` 必须以 `23 21` 开头。
3. 在 `bridgeforge_switch.py` 复制 shell hook 时，可考虑写入后做一次 shebang/BOM 自检，发现 BOM 直接报错或自动剥离。

## 本次下游处置

`CausisRiskSuite` 已在提交前剥离 `.githooks/pre-commit` BOM，并完成提交推送：

```text
745dfbf chore(bridgeforge): 硬切 Codex 协作骨架 [skip-version]
```
