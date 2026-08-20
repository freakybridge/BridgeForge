# Codex 新项目初始化

仅在根 skill 判定为 `init` 后读取。

1. 只运行 `bridgeforge_codex_project_sync.py --mode init` 生成计划。
2. 空项目的 current baseline 安装可零确认应用。
3. apply 必须带紧邻 plan 的 aggregate fingerprint。
4. 所有资产验证通过后，最后写 `.codex/.bridgeforge_codex_version`。

禁止先创建半套 `.codex/`，禁止从 Claude 模板、旧用户目录或其他项目复制资产，禁止
人工写版本戳。项目专属架构、目录地图和快速命令由项目填写。
