# InterviewForge 架构设计文档

> **一句话定位**：一个能根据岗位 JD 和用户简历，自主出题、多轮追问、最后给出结构化评分报告的 AI 模拟面试官。底层对标 Claude Code 七层架构。卖点不在功能，在**模型外的全部工程（harness）**。
>
> **底层模型**：OpenAI 兼容接口（`base_url` + `api_key`，OpenAI / DeepSeek / Qwen / 本地 vLLM 通用）。
> **技术栈**：Vue 3 + Vite（前端）｜ FastAPI（后端）｜ MySQL（业务数据）｜ Chroma（RAG 向量库）｜ Agent 核心纯 Python 手搓，LangChain 仅用于 RAG 检索。
> **语言**：Python。
> **核心原则**：`Agent = Model + Harness`，本项目做的几乎全是 Harness。

---

## 目录

0. [产品描述](#零产品描述)
1. [整体分层](#一整体分层agent--model--harness)
2. [Agent Loop / PEV 状态机](#二pev-loop-主循环状态机)
3. [上下文 Assembler（组装顺序与缓存）](#三context-assembler-组装顺序与缓存策略)
4. [五层压缩管道](#四五层压缩管道)
5. [四类记忆系统](#五四类记忆系统)
6. [Skills 模块](#六skills-模块能力即插件)
7. [工具池与子 Agent](#七工具池--子-agent-隔离与摘要返回)
8. [RAG 检索模块](#八rag-检索模块题库语义检索)
9. [会话持久化](#九会话持久化)
10. [面试黑话速查](#十面试黑话速查)
11. [目录结构](#十一建议目录结构)
12. [全局接缝图](#十二全局接缝图)

---

## 零、产品描述

### 一句话定位

一个能根据岗位 JD 和用户简历，自主出题、多轮追问、最后给出结构化评分报告的 AI 模拟面试官。底层对标 Claude Code 的 agent harness 架构。

### 目标用户与场景

秋招 / 校招 / 社招的求职者，在投递某个岗位前用它做高仿真模拟面试。和"刷题库"的根本区别：它会读你的简历、对着 JD 出题、顺着你的回答深挖追问，像真面试官一样。

### 核心使用流程（用户视角）

**阶段 0 — 投递准备**
用户上传目标岗位 JD（或选预设岗位）+ 简历。Agent 解析两者，提取 JD 的技能要求和简历的项目/技术栈，找出交叉点（该考什么）和缺口（简历未覆盖但 JD 要求的）。

**阶段 1 — 面试规划**
Agent 加载对应岗位的 interview skill，结合 JD + 简历画像，规划面试结构：考几道、每道考什么维度、难度梯度。例如简历写"精通 Redis"，就规划一道深挖题验证"精通"是否属实。

**阶段 2 — 多轮面试（核心）**
逐题出题 → 用户回答 → Agent 判断回答质量决定追问还是放过。答得好加难度，答得卡给提示或换角度。每题表现实时记入记忆。这是与题库刷题最大的区别。

**阶段 3 — 评分报告**
面试结束，汇总整场表现，产出结构化报告：每维度得分、具体强弱点、与 JD 的匹配度、改进建议。

### 内部运作流程（技术视角）

```
上传 JD + 简历
   ↓
[Assembler] 解析,构建初始候选人画像 → 写入 semantic memory
   ↓
┌─────────── 每一轮进入 PEV 状态机 ───────────┐
│ PLAN    加载岗位 skill,规划本轮考什么、追问方向    │
│ EXECUTE 委派 Examiner 子agent 出题(隔离上下文)   │
│         → Examiner 经 MCP 查题库/JD,只回一道题   │
│ (用户回答)                                     │
│ EXECUTE 委派 Grader 子agent 评分(隔离上下文)     │
│         → Grader 只回 {分数, 弱点标签, 反馈}     │
│ VERIFY  校验:难度匹配岗位?没重复?分数合法?         │
│ RESPOND 决定追问 or 进入下一题,输出给用户          │
│ COMPACT 历史过长 → 五层压缩 + L4 蒸馏画像         │
└────────────────────────────────────────────┘
   ↓ (循环到题目耗尽 / 达到 max_turns)
[Grader 汇总] 生成结构化评分报告
   ↓
全程落 trace(JSONL),可重放整场面试
```

### 各模块在面试场景里的角色

| 架构模块 | 在面试 agent 里做什么 |
|---|---|
| PEV 状态机 | 保证每轮"先规划再出题、出完必校验"，不乱问不跳步 |
| Skills | 封装各岗位面试方法论，加岗位类型不改核心代码 |
| 四类记忆 | 画像记强弱项；事件记每题表现；规则存评分标准 |
| 子 Agent 隔离 | 出题官与评分官分开，避免"自出自评"互相污染 |
| 五层压缩 | 长面试不爆上下文，折叠旧题时顺手更新画像 |
| MCP | 题库、JD 查询做成外部 server，可换可扩 |
| 可观测 trace | 整场面试可重放，能 debug"为什么问了这道题" |

### 经得起面试官追问的设计点

- 为什么出题和评分分两个子 agent？→ 隔离避免评分被出题意图带偏，且权限最小化
- 面试很长会不会爆上下文？→ 五层压缩，岗位规则 pinned 永不丢
- 怎么保证不重复出题、不跑题？→ VERIFY 相位门规则校验
- 加一个新岗位要改多少代码？→ 一个 skill 文件，核心零改动
- 怎么 debug 它的决策？→ 全程 trace 可重放

---

## 一、整体分层：Agent = Model + Harness

设计第一原则：`harness` 指代 AI 智能体中除模型本身之外的一切，即 **Agent = Model + Harness**。我们做的几乎全是 harness。

```
┌─────────────────────────────────────────────┐
│  接口层 (CLI / 后续可扩 Web)                    │
├─────────────────────────────────────────────┤
│  Harness 控制平面: Plan-Execute-Verify Loop    │
│  ┌──────────┬──────────┬──────────────────┐  │
│  │ 上下文组装 │ 工具调度  │ 权限/守卫         │  │
│  └──────────┴──────────┴──────────────────┘  │
├─────────────────────────────────────────────┤
│  五层压缩管道 (Context Management)             │
├─────────────────────────────────────────────┤
│  记忆系统 (working/episodic/semantic/procedural)│
├─────────────────────────────────────────────┤
│  工具池 + 子 Agent 委派                        │
├─────────────────────────────────────────────┤
│  会话持久化 (append-only JSONL)                │
└─────────────────────────────────────────────┘
            ↕ OpenAI-compatible Model Client
```

对应 Claude Code 逆向出的七组件结构：汇聚到共享 agent loop 的用户接口、带模式和 ML 分类的权限系统、内置工具池加 MCP 扩展、五层压缩管道、带隔离边界的子智能体委派、append-only JSONL 会话持久化。

---

## 二、PEV Loop 主循环状态机

### 2.1 为什么是状态机

朴素 loop = 组装上下文 → 调模型 → 接收工具请求 → 执行 → 重复。要可靠，升级成**有界的相位门状态机（Plan-Execute-Verify）**：每个阶段有明确入口/出口条件，不满足出口条件不许进下一阶段。把"agent 乱跑"变成"agent 在轨道上跑"。

关键架构赌注：单线程 + append-only 历史，在生产中比更强但不透明的多线程方案更有价值。

### 2.2 状态定义

```
IDLE      # 等待用户输入
PLAN      # 产出本轮计划,不行动
EXECUTE   # 执行计划中的工具调用 / 子agent委派
VERIFY    # 规则门校验本轮产出
COMPACT   # (条件触发)调压缩管道
RESPOND   # 产出面向用户的输出
HALT      # 终止(完成 / 超界 / 错误)
```

### 2.3 状态转移图

```
IDLE ──user input──> PLAN
PLAN ──plan ok──────> EXECUTE
PLAN ──plan invalid─> PLAN (重规划,计数+1)
EXECUTE ──tool结果──> VERIFY
VERIFY ──pass───────> RESPOND
VERIFY ──fail───────> PLAN (带失败原因重规划)
RESPOND ────────────> COMPACT?
COMPACT ────────────> IDLE
任意状态 ──超turn上界/致命错误──> HALT
```

### 2.4 各相位门规格

| 相位 | 动作 | 出口门 | 失败处理 |
|---|---|---|---|
| **PLAN** | 调模型产出结构化计划 `Plan{intent, tool_calls[], expected_outcome}` | 引用合法工具 + 符合岗位 procedural 规则 + 不超剩余题数 | 回 PLAN，`replan_count+=1`，超 `max_replans`→HALT |
| **EXECUTE** | 只执行 PLAN 声明过的调用，不许临时起意 | 所有声明调用都有返回 | 显式失败也算返回 |
| **VERIFY** | 规则校验产出（难度匹配？分数合法？无重复题？） | 全部规则 pass | 失败原因写入上下文 → 回 PLAN，可写进 episodic |
| **COMPACT** | 调用五层压缩管道 | 入口条件 `current_tokens > token_budget` | 与压缩模块接缝 |

VERIFY 是 harness 的"反馈门"：若产出被拒，捕获修正字符串、与失败轨迹配对，提交到记忆库作为后续迭代的规则约束。

### 2.5 有界性保障（可靠性来源）

- `max_turns`：整场对话硬上限
- `max_replans`：单轮重规划上限，防 PLAN↔VERIFY 死循环
- `max_tool_calls_per_turn`：防单轮工具风暴
- 触线即 HALT，给用户体面收尾

### 2.6 落 trace

`TransitionEvent{from, to, gate_result, tokens, ts}` 追加到转录，可重放，同时是 episodic memory 的数据源。

---

## 三、Context Assembler 组装顺序与缓存策略

### 3.1 职责

每次调模型前把多来源拼成上下文窗口，估算 token、决定是否触发 COMPACT。

### 3.2 组装顺序（稳定 → 易变，缓存命根子）

```
段位  内容                      来源              易变性  可压缩
────────────────────────────────────────────────────────────
[0]  系统提示(面试官人设)        config            稳定    ✗ pinned
[1]  岗位规则/rubric            procedural mem    稳定    ✗ pinned
[2]  工具定义                   tool registry     稳定    ✗
[3]  候选人画像                 semantic mem      半稳    △
[4]  压缩摘要(往期题概览)        compact_summary   半稳    (压缩产物)
[5]  最近N轮对话                working mem       易变    ✓
[6]  本轮工具结果/子agent摘要     execute阶段产出    最易变  ✓ (L1先压)
```

### 3.3 缓存策略（prefix caching）

**核心原理**：OpenAI 兼容接口的 prompt 缓存按**前缀**命中——前缀变一个 token，后面全部 miss。所以越稳定的内容越靠前。压缩管道、记忆检索、assembler 三模块共享同一条"稳定在前"纪律。

- 段位 `[0]–[2]` 永不变 → 跨整个 session 命中
- 段位 `[3]–[4]` 半稳 → 仅在 consolidate/collapse 后变一次
- 变动只发生在尾部 `[5]–[6]` → miss 限制在最小范围
- L3 Microcompact 的真正目的就是稳住中段前缀

### 3.4 Token 估算与延迟加载

- `estimate_tokens()` 每段算一次，汇总后比 `token_budget`，决定是否进 COMPACT
- 工具定义延迟加载（ToolSearch 思路）：接口预留 `lazy=True`，体现对 **Orientation Tax** 的认知

### 3.5 接口

```python
class ContextAssembler:
    def assemble(self, session, memory: "MemoryService") -> "AssembledContext": ...
    def estimate_tokens(self, ctx) -> int: ...
    def needs_compaction(self, ctx) -> bool: ...   # 给状态机的 COMPACT 入口判断

class AssembledContext:
    segments: list["Segment"]      # 有序,带 pinned 标记
    total_tokens: int
    cache_prefix_len: int          # 预估稳定前缀长度(可观测)
```

`cache_prefix_len` 暴露出来，demo 可展示"缓存前缀有多长"。

---

## 四、五层压缩管道

### 4.1 设计哲学

没有单一压缩策略能应对所有上下文压力。管道是**有序级联触发**：便宜的先跑，跑完不够再上更贵的。

```
estimate_tokens()
   → L1 budget?  → 跑 → 重新估算
   → L2 snip?    → 跑 → 重新估算
   → L3 micro?   → 跑 → 重新估算
   → L4 collapse?→ 跑 → 重新估算
   → L5 auto?    → 跑(兜底,最贵,要调模型)
```

### 4.2 统一接口（策略模式）

```python
class CompactionLayer:           # 抽象
    name: str
    cost: int                    # 相对成本,用于排序与日志
    def should_trigger(self, ctx: "ContextState") -> bool: ...
    def apply(self, ctx: "ContextState") -> "CompactionResult": ...

class ContextState:
    messages: list["Message"]    # 当前历史(append-only 视图)
    pinned: set                  # 不可压缩集合(岗位规则等)
    token_budget: int            # 上限,如 模型上下文的 70%
    current_tokens: int

class CompactionResult:
    layer_name: str
    tokens_before: int
    tokens_after: int
    messages_affected: int
    summary_text: str | None
```

**关键设计 `pinned`（钉住集合）**：对治"CLAUDE.md 指令在上下文变大时被忽略"的失败模式。岗位规则、评分标准、系统人设全进 `pinned`，任何层不许动。

### 4.3 逐层规格

| 层 | 对治对象 | 触发 | 操作/算法 | 成本 |
|---|---|---|---|---|
| **L1 Budget Reduction** | 溢出大小限制的单个工具输出 | 任一 tool_result > `single_output_cap`(如2000) | 截断保头尾，中间替 `[... elided ...]`；结构化只留前 K 条 | 最低，不调模型 |
| **L2 Snip** | 时间深度 | 历史轮数 > `snip_after_turns`(如20) | 早期工具往返删成占位符 `[tool X called, result discarded]` | 低，不调模型 |
| **L3 Microcompact** | 缓存开销 | 大量连续琐碎小消息 / 缓存前缀频繁变动 | 滑窗合并相邻同角色短消息，稳定缓存前缀 | 低 |
| **L4 Context Collapse** | 超长历史 | `current_tokens > budget*0.85` | 抽取式：从折叠区间提取(题,分,弱点)生成紧凑摘要；**触发记忆 consolidation 的钩子** | 中 |
| **L5 Auto-compact** | 兜底 | 前四层跑完仍超 budget | fork 子上下文调模型做语义摘要，只留画像+进行中的题 | 最高，调模型 |

### 4.4 为什么必须压缩而非截断（面试金句）

- **Lost in the Middle (2023)**：模型无法关注长提示中间的信息，埋深处的指令/事实功能性不可见。
- **二次成本**：标准 transformer 注意力随序列长度二次增长，超长上下文不切实际。
- **真实失败模式**：CLAUDE.md 指令在上下文变大时被忽略，因压缩丢掉了早期加载的项目级配置 → 用 `pinned` 对治。

### 4.5 可观测性

每次 `apply` 产出 `CompactionResult` 写 trace，demo 可画"每层压缩了多少 token"。

---

## 五、四类记忆系统

### 5.1 顶层接口：记忆即服务

把记忆当作有明确 API 的专用微服务，而非 agent 代码里的模块。好处：可升级基础设施而不重写提示、可观测（追踪记住了什么/何时/为何）。

```python
class MemoryService:             # 门面
    def recall(self, query: "RecallQuery") -> list["MemoryItem"]: ...     # 读
    def remember(self, item: "MemoryItem") -> None: ...                   # 写
    def consolidate(self, trigger: "ConsolidateTrigger") -> None: ...     # 蒸馏/提升

class RecallQuery:
    kinds: list["MemoryKind"]    # WORKING/EPISODIC/SEMANTIC/PROCEDURAL
    role: str
    topic: str | None
    limit: int

class MemoryItem:
    id: str
    kind: "MemoryKind"
    content: dict
    created_at: float
    salience: float              # 重要度,用于排序与遗忘
```

### 5.2 四类记忆映射

| 类型 | 内容 | 本项目实现 | 存储 |
|---|---|---|---|
| **Working** | 当前活跃上下文窗口（token受限/会话作用域/易失） | 本轮对话窗口，loop 持有的 message list | 内存，session 内 |
| **Episodic** | 事件（"第3题答错卡在base case"） | 从过往交互学习 | append-only JSONL（与转录共用） |
| **Semantic** | 蒸馏的事实/画像（擅长SQL、弱系统设计） | 候选人画像 | SQLite（起步） |
| **Procedural** | 规则（出题策略、评分rubric、追问决策树） | "知道怎么做" | `roles.yaml` + rubric 文件，进 pinned |

**Semantic 为什么起步用 SQLite 而非向量库**（刻意的工程判断，写进 README）：纯文件系统在记忆任务上得分 74%，击败专门的向量存储库。接口预留 `backend` 抽象，演进路线为混合检索（向量检索语义相似 + 图检索实体关系，两者都需要）。

### 5.3 记忆生命周期（consolidate 编排）

```
working ──(每轮结束/答完一题)──> episodic       [提升]
episodic ──(L4 Context Collapse 触发)──> semantic [蒸馏]
semantic ──(会话结束生成报告)──> 持久画像          [固化]
```

**关键耦合**：`consolidate(EPISODIC→SEMANTIC)` 由压缩管道 **L4 Context Collapse** 触发——压缩和记忆共用同一个触发点。系统最优雅处，面试单独讲。

### 5.4 遗忘与优先级（避免"完美记忆"陷阱）

更多记忆并不帮助，如果 agent 无法优先排序（淹没在细节里，相关与不相关争夺注意力）。

- 每个 `MemoryItem` 带 `salience`
- `recall` 按 `salience × 时间衰减` 排序，只取 `limit` 条
- 低 salience 的 episodic 在 consolidate 时丢弃（蒸馏即遗忘）

### 5.5 检索流程

```
RecallQuery(kinds=[SEMANTIC, EPISODIC], role="后端", topic=当前主题, limit=5)
   → 画像 1 条 + 最相关历史事件 4 条
   → 拼进上下文(画像放前=稳定, 事件放后=易变)
```

---

## 六、Skills 模块：能力即插件

### 6.1 设计目标

把每一类岗位的面试方法论封装成一个**可按需加载的能力包**。主 agent 平时不加载任何岗位方法论，进入 PLAN 阶段识别出岗位类型后，才把对应的 `SKILL.md` 读进上下文。对标 Claude Code 的 skill 机制：能力按任务懒加载，平时不占上下文预算。

核心收益：**加一个新岗位类型 = 加一个 skill 文件夹，核心代码零改动。** 这在简历上是"能力即插件"架构的强信号。

### 6.2 目录结构

```
skills/
├── backend-interview/      # 后端面试方法论
│   └── SKILL.md
├── frontend-interview/
├── algorithm-interview/    # 算法题:怎么给提示、怎么判断思路质量
├── system-design/          # 系统设计:分层追问、scale 演进
└── behavioral-interview/   # 行为面:STAR 框架、追问真实性
```

### 6.3 单个 SKILL.md 的结构

```markdown
---
name: backend-interview
description: 后端工程师面试方法论。当岗位 JD 涉及服务端、
  数据库、并发、分布式、API 设计时加载。registry 据此匹配触发。
---

## 考察维度
该岗位要验证哪些能力（如:数据库索引、并发控制、缓存、系统可靠性）

## 追问树
- 答得好 → 加深一层（"那高并发下这个方案的瓶颈在哪?"）
- 答得卡 → 给提示或换角度（"先想想读写比例?"）
- 答得含糊 → 要求举具体例子验证真实性

## 评分 rubric
每个维度的分级标准（1-5 分）与红旗信号（如:把"精通"写进简历
但答不出基础原理 → 标记 overclaim 风险）
```

`description` 字段是 registry 匹配的依据，写法直接影响"什么岗位触发哪个 skill"。

### 6.4 加载时机与机制

```
PLAN 阶段:
  识别岗位类型(从 JD 解析得出)
    → Skill registry 扫描所有 SKILL.md 的 description,匹配最合适的
    → 懒加载:只读匹配中的那一份 SKILL.md
    → 注入上下文 [1] 段位区域(随岗位选定后,会话内稳定)
```

加载进来的 SKILL.md 进入 assembler 的 `[1]` 段位（岗位规则区），一旦本场岗位选定就稳定不变，因此享受缓存前缀命中，也被标记 `pinned` 不参与压缩。

### 6.5 Skills 与 Procedural Memory 的分工

二者都属"agent 知道怎么做"，但定位不同，必须分清（面试常被追问）：

| 维度 | Skills（方法论·按需加载） | Procedural memory（规则·常驻） |
|---|---|---|
| 内容 | 岗位特定：怎么考、怎么追问 | 全局通用：出题节奏、合法性约束 |
| 体量 | 大而专 | 小而通用 |
| 加载 | 懒加载，平时不占上下文 | 常驻，pinned 不压缩 |
| 扩展 | 热插拔，加文件夹即可 | 改全局配置 |
| 谁用 | PLAN 阶段规划出题 | VERIFY 门据此校验合法性 |

类比 Claude Code：skill 是大而专的能力包，按任务懒加载；procedural 是小而通用的常驻规则。一个回答"这个岗位该怎么考"，一个回答"任何面试都不许违反的规矩"。

---

## 七、工具池 + 子 Agent 隔离与摘要返回

### 7.1 工具池（起步 4 个）

| 工具 | 作用 |
|---|---|
| `search_questions(role, topic)` | 查题库 |
| `lookup_jd(company, role)` | 查岗位要求 |
| `record_answer(question_id, score, notes)` | 写 episodic memory |
| `generate_report()` | 汇总反馈 |

### 7.2 子 Agent 两条铁律

1. **横向扩展而非塞满单窗口**：委派、摘要、返回。
2. **只返回摘要**：主 loop 拿结果不被细节污染（带隔离执行边界 + 重建权限上下文）。

### 7.3 接口

```python
class SubAgent:                  # 抽象
    name: str
    allowed_tools: list[str]     # 权限子集
    def run(self, task: "SubTask") -> "SubResult": ...

class SubTask:
    goal: str                    # 单一明确目标
    inputs: dict                 # 主agent显式传入(非共享内存!)

class SubResult:
    summary: str                 # 只回这个进主上下文
    structured: dict             # 结构化结果(题目/分数)
    tokens_used: int
    # 子agent完整对话历史不返回,留在隔离上下文
```

**隔离本质**：子 agent 有独立 message 历史、独立 token 预算、独立权限子集，跑完即焚。

### 7.4 两个子 Agent

| 子 Agent | goal | allowed_tools | 返回 |
|---|---|---|---|
| **Examiner（出题官）** | 为 {岗位,主题,难度} 设计一道题 | `search_questions`, `lookup_jd`（只读） | `summary` + `structured={question, rubric, expected_points}` |
| **Grader（评分官）** | 评估候选人对某题的回答 | 无 / `record_answer` | `summary` + `structured={score, weakness_tags, feedback}` |

### 7.5 委派调用点（状态机内）

```
EXECUTE 阶段:
  主loop 决定"该出新题了"
    → delegate(Examiner, SubTask(goal=出题, inputs={role, topic, 画像}))
    → Examiner 在隔离上下文跑(主上下文此刻不增长)
    → 返回 SubResult.summary 进主历史 + structured 进 working memory
```

### 7.6 权衡（面试深度）

子智能体隔离限制跨智能体一致性，好的局部决策可能产生差的全局结果。**缓解**：委派时把 semantic memory（画像）作为 `inputs` 显式注入子 task，用"显式传参"补"无共享内存"的一致性缺口。

---

## 八、RAG 检索模块（题库语义检索）

### 8.1 定位

RAG 用于 Examiner 子 agent 出题环节：根据 JD 技能要求 + 简历项目 + 本轮考察维度，从题库里**语义检索**最相关的题。光靠关键词匹配不够——简历写"分布式锁"，题库里写"如何保证多节点互斥"，关键词对不上但语义相关，需要向量检索捞出来。

### 8.2 两层数据库分工（面试考点：别混淆）

RAG 不是"一个数据库"，是两层。把这两层混为一谈是常见扣分点：

```
查询 → Embedding 模型 → 向量库(语义找相关) → 关系库(取原文) → 过滤 → LLM
```

| 层 | 用什么 | 存什么 | 职责 |
|---|---|---|---|
| 向量库 | Chroma（嵌入式） | 题目 embedding | 相似度检索，返回候选题 id |
| 关系库 | MySQL | 题库原文、参考答案、难度、元数据 | 按 id 取业务数据 |

为什么是 Chroma 而非 Qdrant/Milvus（选型理由，自带面试讲点）：题库规模撑死几千到几万道题，**远低于任何性能拐点**，专用向量库的分布式能力用不上。Chroma 嵌入式运行（和 SQLite 同理，跑在 Python 进程内，存本地文件），`pip install chromadb` 一行装好，零额外基础设施。选型原则：按需选型，避免过度工程——这句话本身就是面试加分点。

演进路线（预留）：题库若涨到百万级或需要复杂元数据过滤，再迁移到 pgvector（若已用 Postgres）或 Qdrant。接口对向量库做抽象，换库不动检索逻辑。

### 8.3 检索流程

```
① 查询构造（Examiner 内）
   JD 技能 + 简历项目 + 本轮维度 → query
② Embedding → 向量
③ Chroma 相似度检索 → 候选题 id 列表
④ MySQL 按 id 取原文 + 参考答案 + 难度
⑤ 过滤 + 排序:
   - 去掉 episodic memory 里"本场已问过"的 id（关键!）
   - 按难度匹配岗位/画像排序
⑥ 选出最终一道题 → 返回主 loop
```

第 ⑤ 步与 episodic memory 联动是关键设计：episodic 记录了本场已问过的题 id，检索时据此去重，避免重复出题。这把 RAG 和记忆系统接起来了。

### 8.4 真功夫在检索质量，不在选库

工程共识：向量库选哪个其实没那么重要，**chunking 策略和检索管道远比选库重要**。面试官真正会追问的是：

- **chunk 怎么切**：题干和参考答案分开切（检索匹题干，评分取答案），还是合并？建议分开——检索时只对题干 embedding，避免参考答案的词干扰相似度。
- **怎么去重**：靠 episodic memory 的已问 id 列表过滤（见 8.3 第 ⑤ 步）。
- **怎么排序**：候选题按"难度匹配画像"重排，答得好的维度出难题，弱的维度出基础题。

### 8.5 LangChain 的取舍

LangChain 仅用在 RAG 这一小块（题库检索），核心 harness 仍全部手搓。简历可写"核心自研 harness + LangChain 做 RAG 检索"，既有框架关键词，又守住"手搓 harness"的卖点。要能讲清"为什么 RAG 用框架、核心不用"——这正好呼应那道经典面试题：知道何时用框架、何时该拆掉它。

---

## 九、会话持久化

**append-only JSONL** 转录。每个事件（user / assistant / tool_call / tool_result / compact / transition）追加一行。好处：可重放、可审计、可 resume。同时是 episodic memory 的物理载体。

---

## 十、面试黑话速查

| 术语 | 含义 | 本项目如何对治 |
|---|---|---|
| **Context Rot** | 多步工作流中工具输出/中间推理/错误信息堆积，导致 LLM 注意力退化 | 五层压缩管道 |
| **Orientation Tax** | agent 因缺乏环境结构图盲目试探 API/目录的 token 成本 | 工具描述 + 题库索引 + 延迟加载 |
| **Inner vs Outer Harness** | Inner=模型内嵌的安全层/原生工具调用/上下文窗口；Outer=真正的工程护城河 | 本项目全做 Outer Harness |
| **Environment Engineering** | harness 的逆操作：改造真实系统让工作区对 agent 天然可读 | 题库扁平化/标准化 |
| **Plan-Execute-Verify (PEV)** | 严格相位门架构 | 主循环状态机 |
| **CoALA** | 形式化"记忆类型 vs 记忆架构"的框架 (arXiv:2309.02427) | 四类记忆设计依据 |

---

## 十一、建议目录结构

```
interviewforge/
├── README.md              # 含黑话速查 + 架构图
├── model_client.py        # OpenAI 兼容封装
├── loop.py                # PEV agent loop 状态机
├── context/
│   ├── assembler.py       # 上下文组装(固定顺序 + 缓存)
│   └── compaction.py      # 五层压缩管道
├── memory/
│   ├── base.py            # MemoryService + recall/remember/consolidate
│   ├── working.py
│   ├── episodic.py        # JSONL
│   ├── semantic.py        # SQLite 画像
│   └── procedural.py      # 出题/评分规则
├── tools/
│   ├── registry.py
│   └── interview_tools.py
├── rag/                   # 题库语义检索 (RAG 一小块用 LangChain)
│   ├── retriever.py       # 检索流程: query→Chroma→MySQL→去重排序
│   ├── chunking.py        # 题干/答案分开切
│   └── vector_store.py    # Chroma 接入 (嵌入式,本地文件)
├── subagents/
│   ├── examiner.py        # 出题官
│   └── grader.py          # 评分官
├── skills/                # 能力即插件:每个岗位一份方法论
│   ├── registry.py        # 扫描 description 匹配并懒加载
│   ├── backend-interview/
│   │   └── SKILL.md
│   ├── algorithm-interview/
│   │   └── SKILL.md
│   └── system-design/
│       └── SKILL.md
├── persistence/
│   └── transcript.py      # append-only JSONL
└── config/
    └── roles.yaml         # 全局规则(procedural · 标记为 pinned)
```

---

## 十二、全局接缝图

```
   ┌─────────────── PEV State Machine (loop) ───────────────┐
   │  PLAN → EXECUTE → VERIFY → RESPOND → [COMPACT?] → IDLE │
   └───┬──────────┬────────────────────┬──────────┬─────────┘
       │          │                    │          │
   assemble()  delegate()          consolidate()  compaction
       │          │                    │          │
   Assembler   SubAgents            Memory      Pipeline(L1-5)
   (稳定在前)   (隔离+回摘要)        (4类+遗忘)    (L4↔consolidate)
       └──────────┴──── 共享缓存纪律:稳定在前 ────┴──────────┘
                         全程落 trace → 可观测
```

**收尾金句**：整套架构系统性地**用有界换可靠**。`Agent = Model + Harness`——本项目做的五块全是 Harness，模型只是被它包裹的那个核。这正是 harness engineering 的定义：设计包裹 AI agent 的系统、约束和反馈循环，使其在生产中可靠。
