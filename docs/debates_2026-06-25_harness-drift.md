# 讨论：a18500c9 会话跑偏，harness 该不该改、怎么改
> 日期：2026-06-25
> 相关文件：.claude/hooks/memory_junction_check.py、.claude/hooks/focus_reminder.py、templates/hooks/ 同名件、.claude/settings.json
> 问题描述：会话"评估GitHub仓库公开的风险"在脱敏执行到一半时，模型吐乱码 token `�seted` + 凭空捏造"回答你这个问题/这张图"，转去 Read `setup-junction.ps1` 长篇讲 NTFS junction，再未拐回。三次用户纠偏失败。

## 已钉死的事实（辩论地基，不得推翻，只能在其上论证）

1. **触发扳机 = 模型生成层打嗝 + 幻觉**：drift 句（idx 97）前面零用户输入，是模型读完工具结果后自己续写；开头乱码 `�seted`；"你这个问题/这张图"无中生有（全程无图、无 junction 提问）。
2. **harness 三次把 junction 种进上下文**：
   - Seed A：SessionStart `memory_junction_check.py` 向 stdout 打印 `[memory-junction] 已恢复链接（新机 clone）…junction`，进模型可见上下文且常驻。
   - Seed B：skill 列表里 bridgeforge 描述含"memory junction"。
   - Bridge：脱敏 grep（`C:\Users\bridg|D:\Quant`）命中 `scripts/setup-junction.ps1`（脚本含这些路径），把该文件摆成"脱敏候选"。
   幻觉发生时抓住的正是这个被反复强化、且已在"待办文件"列表里的最显著错误目标。
3. **focus_reminder 结构性不在场**：它是 UserPromptSubmit hook，只在用户提交 prompt 时触发。drift 发生在 turn 内部（无 UserPromptSubmit 事件），故 focus hook 那一刻**物理上不可能触发**。idx 85 的 [focus] 属更早一轮。→ 争点 2 的"措辞太宽松导致没拦住"是伪命题：它压根没在场。任何 UserPromptSubmit hook 都拦不住 turn 内幻觉。

## 候选方案
- (a) memory_junction_check happy-path 静默：noop/恢复链接走 `.runtime/` 日志文件，不再往模型可见 stdout 注入 junction 字样（消除 Seed A）。
- (b) focus hook 增"幻觉自检"措辞（"无用户输入却自称回答用户问题=幻觉信号"）。
- (c) 承认 hook 防不住生成层打嗝，什么都不改。

## Round 1

### 🔵 提议者
定性：harness 是「可消除的帮凶」，非扣扳机的手。主推 (a)：把 memory_junction_check 的 happy-path print（line 112 场景B、137 场景A首迁）降级写 `.runtime/memory_junction.log`，**保留**失败/需人工分支（line 92/125/131/135/145）的 stdout。落产品层 templates/hooks/ + 镜像 .claude/ + bump + `[product]` CHANGELOG。(b) 不做（focus 是 UserPromptSubmit，turn 内不触发，加措辞=安慰剂）。(c) 部分采纳为"诚实边界"写进 CHANGELOG/memory，但不作结论。自曝弱点：n=1 无法证伪有效性；可观测性回退；场景A首迁那条静默有争议。

### 🔴 审阅者
定性：「帮凶」被夸大——harness 是案发现场地上的砖，不是递刀的人；目标分布由解码故障态决定，非输入语料某 token。逐条反对：(a) 安慰剂（模型连上下文里没有的"图"都能捏造，删 junction 对抓错目标概率降幅≈0）+ 实打实可观测性副作用；(b) turn 内 hook 无法机器解析"幻觉"特征，违反 rule 红线；(c) 倾向不改产品层，只把案例写进 memory/docs（连"红线"都提炼不出 → 产品层一行不该加）。新角度：改 Seed A 可能制造**幸存者偏差陷阱**——未来误归因"清理语料有效"→ 把"有项目名就静默/脱敏"惯例下沉给所有下游，削弱人类可见反馈，危害大于 drift 本身且不可逆。开放问题：`�` 乱码是纯解码故障还是 hook stdout 字节回流？证伪前不该改。

### 🔬 仲裁证据（主持人补充，砍开放问题）
U+FFFD（`ef bf bd`）在整个 transcript **仅 1 次**，位于 drift 句的 **assistant 生成 text** 开头，无任何 hook stdout 带坏字节。→ 开放问题判定为 **(i) 纯生成解码层故障**；"编码回流"假说(ii)证伪。改 hook stdout 编码这条路排除。

## Round 2（双方交叉换位）

### 🔵 提议者（放弃 a）
认输两点：①安慰剂——模型捏造出上下文不存在的"图"，证明抓靶不受输入语料约束，删 junction 降幅≈0；②幸存者偏差陷阱最致命，骨架工厂 repo 不能为 n=1 把"有项目名就静默/脱敏"误升为下沉惯例。最终立场：**放弃 (a) 作为产品层改动，不缩小不挣扎**。产品层准入门槛=机制级/可复现/收益确定，本案三项全不沾。新建议：产品层零改动，落一条 memory——结论是"不动"本身 + 反陷阱护栏。

### 🔴 审阅者（松口接受克制版 a）
承认自己把滑坡夸大（克制版只静默 happy-path、保留所有失败分支 print，风险等级中→低）；也承认"防不住根因"≠"减害=0"是逻辑跳步。接受克制版 (a) + 护栏 C1（只静默 happy-path，绝不吞错误）/C2（不碰 hook 编码链路）/C3（减害归减害、根因归 memory）。

### 🔬 主持人仲裁（残余分歧裁决）
决定性事实：`memory_junction_check` line 112 **非每会话噪声**——99% 静默 noop，仅在**新机 clone/路径变更**时触发。本次 a18500c9 触发正因 setup_agent→bridgeforge **刚改名导致 junction 重建**（对应 commit d7964ae）。即 line 112 此处是**罕见且有意义的信号**，静默它有真实可观测性损失、防漂收益≈0。→ 采纳提议者 Round 2 终局：**产品层零改动**。

## ✅ 共识结论

- **根因**：纯模型生成解码层故障（U+FFFD token → 幻觉态自续写，凭空捏造"你这个问题/这张图"）。harness 既非扣扳机的手、也几乎不算帮凶——它只是案发现场地上的砖（junction 语料），而证据（模型捏造出上下文里没有的"图"）证明幻觉抓靶**不受输入语料约束**，故清理语料对防漂收益≈0。
- **Q1（是 harness 引起的吗）**：不是。扳机在模型侧；最像凶手的 focus hook 结构性不在场（UserPromptSubmit 无法在 turn 内触发）；编码回流假说被字节证据证伪。
- **Q2（harness 能预防吗）**：不能。turn 内生成层打嗝在 hook 可见层之下；任何字符串匹配 hook 都无法机器解析"模型正在幻觉"。
- **Q3（怎么改）**：**产品层一行不动**。唯一动作 = 落一条 memory：记清根因边界（生成层故障、改 harness 无效、改编码无效）+ 反陷阱护栏（别把"清理上下文语料/静默日志"当防漂移手段下沉产品层）。
- **被两个 agent 都低估、却最可操作的剩余角度**：真正的失败不是"跑偏"（不可防），而是**模型对用户连续 3 次近似纠偏问句无动于衷、不自救**。这是 UserPromptSubmit hook **能看见**的信号（用户短时间重复近似 prompt = 强漂移信号），是唯一 hook 可介入的杠杆——但属"事后纠偏"而非"事前预防"，且需权衡误报，列为可选项交用户裁决。

- **实施要点**：不写产品层代码；写 1 条 project memory；可选讨论"重复纠偏检测"hook。
- **风险**：唯一真风险是**过度反应**——为 n=1 偶发动产品层，反而把坏惯例复印给所有下游。共识即规避此风险。
