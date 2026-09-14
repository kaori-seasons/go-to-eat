# MiniCPM5-2B 多工具编排 Bad Case 加固方案
## —— 基于 Infinite-Genre-Instance-Dungeons（IGID）记忆系统能力的生产落地方案

> 归档日期：2026-09-08
> 适用项目：Where to Eat（where-to-eat-main）
> 借鉴项目：Infinite-Genre-Instance-Dungeons（`/Users/kaori/Documents/gitrepo/Infinite-Genre-Instance-Dungeons/`）
> 目标模型：MiniCPM5-2B-0822（api.modelbest.cn）
> 状态：设计稿（待评审）

---

## 目录

1. [背景与问题定义](#一背景与问题定义)
2. [Bad Case 深度归因](#二bad-case-深度归因)
3. [IGID 能力提炼与映射](#三igid-能力提炼与映射)
4. [自我辩证与反思](#四自我辩证与反思)
5. [目标架构](#五目标架构)
6. [分阶段实施计划](#六分阶段实施计划)
7. [测试与验收](#七测试与验收)
8. [风险与回滚](#八风险与回滚)
9. [附录：模块与文件映射](#九附录模块与文件映射)

---

## 一、背景与问题定义

### 1.1 现状

Where to Eat 当前有两条使用入口：

- **Web 服务**（Cloudflare Pages Functions → 高德 REST API）：编排逻辑**硬编码在确定性代码中**，表现稳定（综合测试 52 例成功率 98.1%）。
- **对话式 Skill / LLM 编排链路**：由模型（MiniCPM5-2B / Kimi 2.5）自主决定调用高德工具的顺序与参数。此链路是 bad case 的重灾区。

MiniCPM5-2B 深度测评（52 用例 / 173 次真实 API 调用）显示：

| 维度 | 得分 | 评级 |
|------|------|------|
| D7 上下文保持 | 98% | ✅ 强项 |
| D6 错误恢复 | 95% | ✅ 强项 |
| D1/D2/D3 工具识别/参数提取/验证 | 85–90% | ✅ 合格 |
| D5 条件分支 | 72% | ⚠️ 薄弱 |
| D4 多工具编排 | 68% | ❌ 短板 |
| D8 结果整合 | 65% | ❌ 短板 |
| 并行调用识别 | 45% | ❌ 严重短板 |
| 端到端流程完成率 | 11% | ❌ 严重短板 |

### 1.2 问题本质

> **结论先行：MiniCPM5-2B 的 bad case 不是"参数提不准"，而是"记不住整体计划、追不完多步依赖"。**
> 2B 模型在单轮/单工具上可靠，但在 7–15 步的编排链上会出现"步骤坍缩"（只执行第一步或随机子集）、"依赖跳步"（用地名直接调路线规划）、"分支误判"（8km 还算骑行）。

这恰好是 IGID 项目的核心命题的同构问题：IGID 解决"剧情无法连续"（选择失效、状态丢失、线索断裂），where-to-eat 的 LLM 链路患的是"**编排无法连续**"。因此可以用 IGID 的记忆底座能力为编排层做 hardening。

---

## 二、Bad Case 深度归因

### BC-1：并行调用识别失败（并行度 45%）

- **现象**：3 人聚餐场景期望 7 次调用（3 geo + 1 search + 3 route），实际只发 3 次 geo，缺少 search 和 route。
- **根因**：模型把"下一步该做什么"当作每次独立决策，没有一个显式的**计划数据结构**告诉他"还剩哪些步骤未完成"。步骤完成的记账完全靠对话上下文里的隐式推理，2B 模型撑不住。

### BC-2：多工具编排顺序错误（D4 = 68%）

- **现象**：直接 `maps_direction_driving(origin="望京", destination="国贸")`，用地名代替坐标。
- **根因**：依赖关系（geo → route）只写在 system prompt 的自然语言里，没有**机器可校验的前置条件检查**——工具入参 schema 声明要坐标，但没有运行时守门员。

### BC-3：端到端流程坍缩（完成率 11%）

- **现象**：4 人 + 日料 + 19 点的复杂请求，只执行 1 次 `maps_text_search`，9 步流程完成 1 步。
- **根因**：任务复杂度超出模型"心算规划"能力。没有外部**任务分解器**把 9 步计划物化成状态，也没有**未完成步骤追踪**（IGID 的"未闭合话题"同构问题）。

### BC-4：条件分支误判（D5 = 72%）

- **现象**：朱辛庄→五道口约 8km，仍调用骑行路线。
- **根因**：业务规则（">3km 不推荐骑行"）是隐性知识，模型无法从坐标心算球面距离。缺一个**规则前置层**在调用前拦截。

### 归因总结

四类 bad case 共同指向一个缺口：**LLM 链路缺少一个外置的、持久化的、可召回的"编排记忆层"**。这正是 IGID 已经验证过的架构（记忆图谱 + 未闭合追踪 + 召回注入 + 作用域隔离）。

---

## 三、IGID 能力提炼与映射

### 3.1 IGID 可复用的五项核心能力

对 IGID 源码结构（`core/`、`intelligence/`、`memory/`）的分析，提炼出与编排加固直接相关的能力：

| IGID 能力 | 关键文件 | 原始用途 | 编排域同构 |
|-----------|---------|---------|-----------|
| **话题记忆图谱** | `core/memory_graph.py` | 把碎片对话沉淀为结构化记忆节点+连接 | 把碎片工具调用沉淀为**编排步骤图（Plan DAG）**：节点=步骤，边=依赖 |
| **未闭合话题追踪** | `core/memory_system.py`、`intelligence/temporal.py` | 记住"还没结束的事"，下轮重新触发 | 记住"**还没完成的步骤**"，下一轮迭代强制回流给模型 |
| **召回与上下文注入** | `memory/memory_recall.py`、`core/recall_system.py` | 下轮对话前召回高强度记忆注入 prompt | 每次模型调用前，注入"**当前计划进度 + 可执行步骤 + 已固化结果摘要**" |
| **人物印象 / 关系** | `memory/extractor.py`、impressions API | 维护人物好感度与印象 | 维护**实体缓存**：地名→坐标、餐厅→POI 详情，避免重复 geo 调用与不一致 |
| **作用域隔离** | `enable_group_isolation` | 不同副本世界线不串线 | 不同**会话/不同聚餐请求**的编排状态互相隔离（session_id 作用域） |

### 3.2 明确不搬运的能力（见第四节辩证）

- 多模态 CLIP / LanceDB 链路（`infrastructure/` 多模态部分）
- LLM 驱动的记忆生成（`intelligence/topic_analyzer.py` 的重分析流水线）
- 遗忘/整理的完整生命周期（`enable_forgetting`/`enable_consolidation` 全套）——只保留轻量 TTL

### 3.3 核心设计转译

IGID 的世界观："用户消息 → 识别话题 → 形成结构化记忆 → 存入图谱 → 下一轮召回注入"。

转译到编排域：

```text
用户聚餐请求
→ 意图分解器物化为 Plan DAG（geo* N → search → route* M → rank）
→ 每步执行结果写入"编排记忆"（步骤状态：pending / ready / done / failed / skipped）
→ 每轮模型调用前，召回器只注入"当前可执行步骤 + 所需的上游结果"
→ 未完成步骤永不丢失（类似未闭合话题），直到计划闭合或用户取消
```

**关键洞察**：不让 2B 模型"记 15 步计划"，只让它在每一轮回答一个被裁剪到能力范围内的小问题："给定这些已固化结果，下一步该调哪个工具、参数填什么"。这把 D4/D8 的开放式编排问题降维成 D1/D2 的封闭式识别问题——恰好是 MiniCPM5-2B 的 85–90% 强项区。

---

## 四、自我辩证与反思

### 辩证 1：为什么不直接用现成工作流引擎（如 LangGraph）？

- **正方**：成熟、社区支持、DAG 编排是标配。
- **反方**：where-to-eat 的 Skill 链路运行在 MCP/对话环境，重框架引入成本高；且 LangGraph 不解决"跨轮次实体缓存"与"会话级编排记忆持久化"，而这两点恰是 IGID 的存量能力。
- **裁决**：**自研轻量编排记忆层（~600 行），设计模式抄袭 IGID，不引入 IGID 的运行时依赖**。理由：编排记忆层的核心抽象（状态图 + 召回注入 + 作用域）简单到不值得付出框架税；IGID 代码作为参考实现而非依赖库。

### 辩证 2：计划由谁生成？模型分解 vs 规则分解？

- MiniCPM5-2B 自己做任务分解已被证明不可靠（BC-3 完成率 11%）。
- 但纯规则分解（正则抽数）对模糊输入鲁棒性差。
- **裁决**：**两级分解**——规则抽取器负责实体（地点/菜系/时间/人数，覆盖 90% 输入），模型只在规则抽取置信度低时做一次"单步结构化抽取"调用（输出 JSON schema 约束的实体槽），不做自由编排。这与 deep-analysis 报告中"TaskDecomposer"建议一致，但明确了模型兜底的窄接口。

### 辩证 3：每次注入召回内容，会不会撑爆 2B 模型的上下文？

- 会。2B 模型长上下文能力弱，全量注入路线 JSON（单次 transit 响应可达数 KB）正是 BC-3 恶化的诱因之一。
- **裁决**：召回必须做**投影（projection）而非原文注入**。工具结果入库时即提取为紧凑槽位（`{name, lng, lat, duration_s, transfer_count}`），单轮注入预算硬上限 ~1200 token。IGID 的 `max_injected_memories` / `memory_injection_threshold` 配置思想直接照搬。

### 辩证 4：条件分支（BC-4）该靠记忆还是靠规则？

- 记忆解决不了"8km 不该骑车"——这是纯业务规则，与历史无关。
- **裁决**：条件分支**不下放给模型**，在编排层的步骤守护（Step Guard）中硬编码：距离由已缓存的坐标 haversine 预计算，>3km 直接把骑行步骤标记为 `skipped`，根本不进入模型的选项空间。记忆层只负责"为什么跳过"的可解释留痕。

### 辩证 5：这是否让模型沦为摆设？

- 不。保留模型的价值区：① 低置信度实体抽取兜底；② 地点歧义消解（"望京"是地铁站还是商圈，结合候选召回让模型选择）；③ 最终自然语言推荐文案生成（D8 的"整合"部分从模型移除，但"表达"保留给模型）。
- **反思记录**：原测评报告建议"混合架构按复杂度路由模型"，本方案进一步收紧为"**编排全确定性，模型只做认知缝隙的填补**"。若未来换 Kimi 2.5 或更大模型，同一编排记忆层无需改动，只放宽 Step Guard 的模型裁量范围——架构向前兼容。

---

## 五、目标架构

### 5.1 架构图

```text
用户聚餐请求（Skill / MCP / Web）
        │
        ▼
┌─────────────────────────────────────────────────┐
│  L1 意图与实体层                                  │
│   RuleExtractor（地名/菜系/时间/人数正则+词典）     │
│   └─ 低置信度 → MiniCPM 单步 JSON 槽位抽取兜底      │
├─────────────────────────────────────────────────┤
│  L2 编排记忆层（Orchestration Memory，新模块）      │   ← IGID 模式移植
│   PlanDag        ≈ memory_graph（步骤节点+依赖边）  │
│   StepState      ≈ 未闭合话题（pending/ready/done/ │
│                    failed/skipped，永不静默丢失）   │
│   EntityCache    ≈ 人物印象（地名→坐标、餐厅→POI，   │
│                    会话级 + TTL 磁盘级）            │
│   RecallProjector≈ memory_recall（每轮注入裁剪投影， │
│                    ≤1200 token）                  │
│   SessionScope   ≈ group_isolation（session_id 隔离）│
├─────────────────────────────────────────────────┤
│  L3 执行与守护层                                   │
│   StepGuard（前置条件校验：坐标格式、距离规则、      │
│             城市白名单；失败步骤重试/降级）          │
│   ParallelExecutor（就绪步骤 asyncio.gather 并行） │
│   Ranker（公平性排序：最慢优先/时间差/均值，纯代码）  │
├─────────────────────────────────────────────────┤
│  L4 高德 API 层（maps_geo / text_search /          │
│     direction_driving / direction_transit / regeo）│
└─────────────────────────────────────────────────┘
```

### 5.2 数据模型（Plan DAG 节点）

```python
@dataclass
class PlanStep:
    step_id: str            # "geo:wangjing", "route:poi3:wangjing"
    kind: str               # geo | search | route | rank
    params: dict            # 已解析参数（可引用 EntityCache 键）
    depends_on: list[str]   # 上游 step_id
    status: str = "pending" # pending|ready|done|failed|skipped
    result_ref: str | None = None   # EntityCache 键，不存大 payload
    failure: dict | None = None     # 错误分类 + 降级动作留痕

@dataclass
class OrchestrationSession:
    session_id: str
    scope: str              # 用户/群组隔离键（≈ IGID group_isolation）
    plan: list[PlanStep]
    turn: int = 0
    created_at: float
```

### 5.3 每轮模型调用的注入模板（裁剪投影）

```text
[计划进度] 7 步中已完成 5，失败 0，跳过 1（骑行：距离 8.2km > 3km 规则）
[本次只需决定] 下一步从以下 2 个就绪步骤中选择并给出参数：
  1. route:poi1:wangjing  需 origin=<缓存:望京坐标> destination=<缓存:poi1坐标>
  2. route:poi1:huoying   需 origin=<缓存:霍营坐标> destination=<缓存:poi1坐标>
[已固化事实] 参与者坐标：望京(116.47,39.99)、霍营(116.37,40.07)；候选餐厅：3 家（名称+坐标+评分）
只输出一个 JSON 工具调用，不要输出其他内容。
```

### 5.4 目录规划（where-to-eat-main 内新增）

```text
where-to-eat-main/
└── orchestrator/                  # 新增顶层模块（纯 Python，可跑在 Pages Functions 之外）
    ├── __init__.py
    ├── plan.py                    # PlanStep / OrchestrationSession / PlanDagBuilder
    ├── extractor.py               # RuleExtractor + 模型兜底窄接口
    ├── memory.py                  # EntityCache（SQLite/内存双后端）+ TTL
    ├── recall.py                  # RecallProjector（token 预算裁剪）
    ├── guard.py                   # StepGuard（前置条件 + 业务规则）
    ├── executor.py                # ParallelExecutor + 失败重试/降级
    ├── ranker.py                  # 公平性排序（移植 web 端现有逻辑，单一事实源）
    ├── llm_client.py              # MiniCPM/Kimi 统一客户端（窄接口）
    └── session_store.py           # 会话持久化 + 作用域隔离
tests/
└── test_orchestrator_*.py         # 见第七节
```

---

## 六、分阶段实施计划

### P0（第 1–2 周）：止血 —— 闭环最小编排器

**目标**：端到端流程完成率 11% → ≥95%，任何请求不再"步骤坍缩"。

| 任务 | 说明 | 验收 |
|------|------|------|
| P0-1 `plan.py` | PlanDagBuilder：按固定模板物化 `N geo → 1 search → M route → 1 rank` | 3 人场景生成 7+ 节点 DAG 单测通过 |
| P0-2 `extractor.py` | 规则抽取（城市白名单 5 城、菜系词典、2–5 人约束） | 20 条标注语句实体抽取 F1 ≥ 0.9 |
| P0-3 `memory.py` | EntityCache 内存后端 + 坐标/POI 槽位 | geo 结果零重复调用 |
| P0-4 `executor.py` | 拓扑序调度 + `asyncio.gather` 同层并行 | 3 人场景 wall-time ≤ 串行 50% |
| P0-5 `ranker.py` | 从 Web 端移植三种公平策略 | 与 Web 端同输入输出一致 |
| P0-6 `llm_client.py` | 仅保留两处模型调用：实体兜底 + 最终文案 | 单测 mock 全通过 |

**P0 结束时模型已退出编排决策回路**——这是保底：即使模型环节全部降级为模板文案，功能仍然正确。

### P1（第 3–4 周）：加固 —— 守护、降级与持久化

**目标**：错误恢复从"模型自觉"变为"系统保证"；支持多轮修改（"换一家烤肉"）。

| 任务 | 说明 | 对应 IGID 能力 |
|------|------|---------------|
| P1-1 `guard.py` | 坐标格式校验、haversine 距离规则（>3km 跳骑行、>25km 建议驾车）、城市一致性 | —（新增，堵 BC-4） |
| P1-2 失败降级 | driving 限流/失败 → 自动改 transit 并标记 `failure.degraded_from`；geo 失败 → 站点后缀重试链（`X → X地铁站 → X公交站`，复用现有 SKILL 语义） | 未闭合追踪思想：failed 步骤进重试队列而非丢弃 |
| P1-3 `session_store.py` | SQLite 持久化 + scope 隔离；支持"换菜系"时仅重置 search/route 子图，geo 结果复用 | group_isolation + 记忆复用 |
| P1-4 `recall.py` | 注入投影器 + 1200 token 硬预算；接回模型增量决策（模型从 2 个就绪步骤中选序） | memory_recall 投影 |
| P1-5 多轮指令 | "换一家""改时间""加一个人"→ 增量改图（DAG diff）而非重建 | 话题延续 |

### P2（第 5–6 周）：增益 —— 可观测、评测闭环、缓存升级

| 任务 | 说明 |
|------|------|
| P2-1 编排留痕 | 每步落 `orchestration_trace`（step_id、耗时、降级原因），供 Web UI 与排障 |
| P2-2 磁盘缓存 TTL | EntityCache 升级 SQLite 落盘，坐标缓存 7 天、POI 1 天（POI 更新频繁） |
| P2-3 评测回归 | 将 `tests/test_cases.py` 的 D1–D10 用例接入 CI，新增编排维度用例（见第七节） |
| P2-4 模型路由开关 | 配置项 `orchestration_mode: deterministic | model_assisted`，可灰度对比 |

### 明确不做（Non-Goals）

- ❌ 多模态记忆（CLIP/LanceDB）——聚餐场景无图像资产，纯成本
- ❌ LLM 驱动的记忆生成流水线——编排状态是确定性的，无需语义沉淀
- ❌ 遗忘/整理全生命周期——只保留 TTL
- ❌ 依赖 IGID 代码库运行——只做模式移植，避免跨仓依赖

---

## 七、测试与验收

### 7.1 针对四类 bad case 的回归用例（新增至 tests/）

| 用例 ID | 复现场景 | 断言 |
|---------|---------|------|
| ORCH-BC1 | 3 人（望京/霍营/朱辛庄）烤肉 | DAG 含 ≥7 节点；geo 层 3 调用并行发出；search 与 route 全部 done |
| ORCH-BC2 | "望京到国贸开车多久" | 路线步骤入参必为坐标；若 EntityCache 未命中则自动先 geo，**不允许**地名入参到达 API 层 |
| ORCH-BC3 | 4 人 + 日料 + 19:00 | 计划完成率 = 100%（rank 节点产出 1 推荐 + ≤2 备选） |
| ORCH-BC4 | 朱辛庄→五道口 | 骑行步骤 status=skipped 且留痕含距离规则；API 无 bicycling 调用 |
| ORCH-DEG | mock driving 限流 | 自动降级 transit，最终推荐仍产出，trace 含 degraded_from |
| ORCH-MULTI | 轮 2 "换烤肉" | geo 节点复用（0 次新 geo 调用），仅 search/route 重执行 |
| ORCH-SCOPE | 两个并发 session | 实体与计划零串线 |
| ORCH-TOK | 最大规模（5 人）注入投影 | 投影 token ≤ 1200 |

### 7.2 验收指标（对照基线）

| 指标 | 基线（MiniCPM 自由编排） | P0 目标 | P1 目标 |
|------|------|------|------|
| 端到端完成率 | 11% | ≥95% | ≥99% |
| 计划步骤召回（无坍缩） | ~45% 并行识别 | 100%（确定性调度） | 100% |
| 依赖顺序错误 | D4=68% | 0（guard 强制） | 0 |
| 无效调用（如 8km 骑行） | 存在 | 0 | 0 |
| 3 人场景 wall-time | 32s（e2e） | ≤12s | ≤8s |
| 高德 API 调用数 | 冗余 | 恰好 = DAG 节点数 | 同左 + 缓存命中进一步下降 |

### 7.3 测试基础设施

- API 层用现有 `tests/mock_amap_server.py`，编排层单测全部离线。
- 真机回归沿用 `minicpm_e2e_test.py` 骨架，改为驱动 `orchestrator` 包，报告落 `tests/results/orchestrator_e2e_report.json`，与历史报告同构可比。

---

## 八、风险与回滚

| 风险 | 等级 | 缓解 |
|------|------|------|
| 规则抽取对长尾表述覆盖不足 | 中 | 模型兜底窄接口 + 用例集持续扩充；抽取置信度打分留痕 |
| SQLite 在 Cloudflare Pages Functions 不可用 | 高 | 编排层不下沉到 Functions：Web 链路维持现有确定性实现不变；orchestrator 面向 Skill/MCP/自托管后端。若未来需下沉，session_store 抽象后端可换 Durable Objects |
| 注入投影仍超预算 | 低 | 投影器单测 token 计数硬断言；超限按 step 优先级截断 |
| 模型增量决策（P1-4）反而劣化 | 低 | `orchestration_mode` 开关，默认 deterministic，灰度开启 model_assisted，按 ORCH 指标对比决定去留 |
| 与 IGID 模式移植"形似神不似" | 中 | 以第七节行为断言为准，而非结构相似度；IGID 仅作设计参考 |

**回滚策略**：orchestrator 为新增独立模块，不改动现有 Web/Functions 代码路径；Skill 链路通过配置切回旧的 free-form 提示词模式即可整体回滚。

---

## 九、附录：模块与文件映射

| 本方案模块 | IGID 参考文件 | 移植要点 |
|-----------|--------------|---------|
| `orchestrator/plan.py` | `core/memory_graph.py` | 节点+边+状态的数据结构；物化时机前置（请求到达即建图） |
| `orchestrator/memory.py` | `core/models.py`、impressions API | 实体槽位化存储；键值命名沿用"实体:标识:属性" |
| `orchestrator/recall.py` | `memory/memory_recall.py`、`core/recall_system.py` | 阈值过滤 + 数量上限 → token 预算投影 |
| `orchestrator/session_store.py` | `core/save_manager.py` + group_isolation 配置 | scope 键隔离会话；只存紧凑状态不存原始响应 |
| `orchestrator/guard.py` | （IGID 无对应，新增） | 业务规则引擎：距离/城市/格式三类前置断言 |
| `orchestrator/executor.py` | `core/scene_manager.py` 的推进思想 | 拓扑分层 + 层内并行 + failed 回流重试队列 |

---

## 结论

1. MiniCPM5-2B 的编排 bad case（并行识别 45%、e2e 完成 11%）本质是**状态外置缺位**，不是参数能力问题——用外部记忆补状态，比换模型性价比高一个数量级（成本比 1:150）。
2. IGID 的五项能力中，**记忆图谱、未闭合追踪、召回注入、作用域隔离**四项可低成本移植为"编排记忆层"；**多模态与 LLM 记忆生成**应明确放弃。
3. 架构原则一句话：**编排确定性、状态持久化、模型窄接口**。模型从"规划者"降级为"认知缝隙填补者与表达者"，bad case 的四类根因被结构性消除，而非提示词层面打补丁。
