---
name: feedback-glob-search-gotchas
description: 用户机器上用 Glob/Grep 查文件的首选方式与三个坑（范围、文件非目录、跳过点目录）
metadata:
  node_type: memory
  type: feedback
  originSessionId: 6b1677dc-7273-41e9-acc0-c1cb80337936
---

查文件/找目录优先用 `Glob`/`Grep`（受控只读工具，**零权限弹窗**），不要用 PowerShell/bash 的 `find`/`Get-ChildItem`——后者是自由文本命令，会触发确认弹窗（尤其访问工作目录外路径时）。

**Why:** 用户明确要"无感"，反感重复的 shell 权限确认。`Read(//c/**)` 只放行文件读，管不住任意 PowerShell 命令，所以 shell 全盘扫描永远会弹。

**How to apply:** 用 `Glob`，但避开它的三个坑（一次演示连踩两个）：
1. **范围别贪大** — 全盘 `C:\` + `**/x` 会 20s 超时；path 给得越具体越好。
2. **`Glob` 匹配的是文件不是目录** — 找文件夹 `foo` 要写 `**/foo/**`（匹配里面的文件），写 `**/foo` 会落空。
3. **默认跳过 `.` 开头的隐藏目录**（ripgrep 规矩）— 目标在 `.claude` 这类点目录里时，从上层扫进不去；要把 `path` 直接扎进点目录内部（如 `C:\Users\bridg\.claude\skills\bridgeforge`）。

环境配置默认 `Shell: PowerShell`，所以我会下意识首选 PowerShell 查文件——这是要主动纠正的反射。相关：[[feedback-dogfood-hook-gap]]