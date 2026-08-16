# Codex hook 信号参考

`[clarify]` 和 `[focus]` 只是轻量信号，响应契约以项目根 `AGENTS.md` §4.4-§4.5 为准。

- `[clarify]` 在新的、大而模糊的需求中提醒先收敛目标；续接或细节已全时忽略。
- `[focus]` 只检查无意漂移；用户明确转任务或正当深入时忽略。
- hook 不得自动替用户选择范围，也不得把信号宣称为 Markdown rule 加载证据。

调试时记录当次 hook event、matcher、输入 payload 和返回码，然后分别验证“信号是否产生”与“agent 是否正确响应”。
