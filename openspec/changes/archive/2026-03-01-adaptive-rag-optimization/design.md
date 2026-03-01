## Context

当前 Agentic RAG 是 4 节点线性拓扑：`plan → tool_exec → evaluate → synthesize`。所有查询不分类型，统一走 `grep_search + vector_search` 组合。GrepTool（ripgrep 封装）返回单行结果无上下文窗口，evaluate_node 只做 sufficient/not-sufficient 二分判断。这导致：

- 简单精确查询（票号、配置名）浪费向量检索
- 概念性问题被强制 grep，关键字匹配失败率高
- 评估器无法区分"部分相关"和"完全无关"，频繁触发无效重试（常见 3 轮仍不命中）

参考：Google Search AI Mode 的核心是 **先理解查询意图 → 自适应选择数据源 → 闭环质量验证 → 带引用输出**。

### 现有架构要素

| 组件 | 文件 | 关键局限 |
|------|------|----------|
| AgentState | `agent/state.py` | 无查询分类字段、无证据评分字段 |
| plan_node | `agent/nodes.py:227` | 无查询分析，fallback 齐发所有工具 |
| evaluate_node | `agent/nodes.py:495` | bool 判断，无细粒度 grading |
| synthesize_node | `agent/nodes.py:611` | 无引用/citation 能力 |
| GrepTool | `tools/grep_tool.py` | ripgrep 单行匹配，无 BM25、无上下文窗口 |
| Graph 拓扑 | `agent/graph.py` | 线性 4 节点，max_iter=1-5 |

## Goals / Non-Goals

**Goals:**
- G1: 引入查询分析节点，按意图类型自适应路由到最优工具组合
- G2: GrepTool 升级为混合检索（BM25 评分 + 上下文窗口 + 与向量结果 RRF 融合）
- G3: 引入 CRAG 评分替代二分判断，按证据质量驱动重检索/生成/澄清决策
- G4: synthesize_node 输出带文件路径和行号引用
- G5: 保持 `Engine.answer_query()` 对外接口不变

**Non-Goals:**
- NG1: 不做 Web Search 集成（已有 `web_fetch` 工具，本次不改）
- NG2: 不改索引构建流水线（indexing pipeline 不在此变更范围内）
- NG3: 不引入多模态检索（图片、PDF 等）
- NG4: 不做 streaming 改造（当前已有 status_callback 机制足够）

## Decisions

### D1: 新增 `analyze_and_route` 节点 — 查询前置分析

**选择**: 在 `plan_node` 之前新增独立节点，用结构化 LLM 调用对查询做分类和分解。

**输出schema**:
```json
{
  "query_type": "exact | conceptual | relational | file_discovery",
  "sub_questions": ["子问题1", "子问题2"],
  "suggested_tools": ["vector_search", "graph_related"],
  "grep_keywords": ["精确关键字1"]
}
```

**路由规则**:
| query_type | 首选工具 | 备选 |
|---|---|---|
| `exact` | grep_search (精确匹配) | vector_search |
| `conceptual` | vector_search (语义检索) | hybrid_search |
| `relational` | graph_related → read_file | vector_search |
| `file_discovery` | local_file_qa | — |

**替代方案**: 不新增节点，直接在 plan_node 中增加分析 prompt。
**否决原因**: plan_node 已承担工具选择职责，混入分析逻辑会让 prompt 过长、JSON 解析更脆弱。分离关注点更可维护。

**对 AgentState 的影响**: 新增 `query_type: str`、`sub_questions: list[str]`、`routing_plan: dict` 字段。

---

### D2: GrepTool 升级为带上下文窗口的 BM25 混合检索

**选择**: 分两步增强 GrepTool：

1. **上下文窗口**: ripgrep 添加 `-C 10` 参数（前后 10 行），结果格式从单行扩展为 passage
2. **BM25 评分**: 用 `rank-bm25` 库对 grep 结果做 BM25 重评分排序，过滤低分噪声

**新增 `hybrid_search` LangChain tool**: 封装 "grep (BM25) + vector_search → RRF 融合" 逻辑：
```
hybrid_search(query) → grep结果(BM25排序) + vector结果 → RRF合并 → top-K
```

**RRF (Reciprocal Rank Fusion) 公式**:
```
RRF_score(d) = Σ 1 / (k + rank_i(d))   (k=60 为标准常数)
```

**替代方案 A**: 完全替换 ripgrep 为纯 BM25 索引（如 Whoosh）。
**否决原因**: ripgrep 对已有 MD 文件的零索引搜索很适合 POC，重建全文索引增加复杂度。

**替代方案 B**: 只加上下文窗口，不做 BM25。
**否决原因**: 上下文窗口解决碎片化但不解决排序问题，LLM 仍然会被大量低相关结果淹没。

---

### D3: CRAG 闭环验证 — 替换 evaluate_node

**选择**: 将 evaluate_node 升级为 CRAG (Corrective RAG) 模式：

1. **Relevance Grader**: 对每条 context item 独立打分 (0.0 - 1.0)
2. **聚合决策**:
   - `avg_score ≥ 0.7` → **GENERATE** (直接进 synthesize)
   - `avg_score < 0.3` → **RE-RETRIEVE** (回到 plan，携带 "需要什么" 的 hint)
   - `0.3 ≤ avg_score < 0.7` → **REFINE** (保留高分证据，用新关键词补充低分部分)
3. **过滤**: 打分 < 0.3 的 context item 直接丢弃，避免污染 synthesize

**对 AgentState 的影响**: 新增 `evidence_scores: list[float]`、`grader_action: str` 字段。

**替代方案**: 保持二分判断 + 调整 prompt。
**否决原因**: prompt 工程无法解决结构性问题——LLM 在 JSON 输出中频繁解析失败导致 fallback 到 "有内容就通过"。

---

### D4: 带引用的生成 (Citations)

**选择**: 在 synthesize_node 的 system prompt 中要求以脚注格式生成引用：
```
答案内容 [1]

---
[1] /path/to/file.md:L42
[2] /path/to/another.md:L15-L25
```

**实现**: synthesize_node 向 LLM 传递 context 时，每条 context 前缀标注来源路径和行号（已存在于 grep/vector 结果的 metadata 中），prompt 要求 LLM 在回答中引用这些标号。

**对 AgentState 的影响**: context items 格式统一为 `[SOURCE:{path}:L{line}] content`，synthesize 解析后附加 citation footer。

---

### D5: 新 Graph 拓扑

**选择**: 从线性 4 节点升级为 6 节点自适应拓扑：

```
START → analyze_and_route → plan → tool_exec → grade_evidence
                                                    ├─ GENERATE ──→ synthesize → END
                                                    ├─ REFINE ────→ plan (保留高分 context)
                                                    └─ RE-RETRIEVE → analyze_and_route (新策略)
```

**关键变化**:
- `evaluate` 重命名为 `grade_evidence`（更准确反映 CRAG 语义）
- 新增 `analyze_and_route` 作为入口
- 从 `grade_evidence` 有 3 条出路（原来只有 2 条）
- `RE-RETRIEVE` 回到 `analyze_and_route` 而非 `plan`，允许切换工具策略

**max_iter**: 保持环境变量 `KB_AGENT_MAX_ITERATIONS` 控制，默认提升到 3（原来默认 1）。

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| 新增 `analyze_and_route` 增加 1 次 LLM 调用 latency | 每次查询多 ~1s | 用轻量 prompt + 低 temperature，简单查询 fast-path 跳过分解 |
| CRAG grader 逐条打分在 context 多时成本高 | context 20条 → 20次 LLM 调用 | 批量打分：一次 LLM 调用评估所有 context items（JSON 数组） |
| `rank-bm25` 新依赖 | 增加包管理复杂度 | rank-bm25 是纯 Python、无 C 扩展、维护良好（PyPI 周下载 >100k） |
| 上下文窗口 (±10行) 使单条 context 变长 | Token 消耗增加 | 截断单条 context 上限 2000 chars；synthesize 只取 top-10 items |
| graph 拓扑变复杂，调试难度增加 | 开发效率 | 每个节点保持 audit log（已有 `log_audit` 基础设施） |
| 现有测试需全部更新 | 回归风险 | 渐进式：先加新节点不删旧的，feature flag 切换 |

## Open Questions

1. **BM25 中文分词**: `rank-bm25` 默认按空格分词，中文需要 jieba 分词吗？还是先用字符级 n-gram 做 POC？
2. **Grader 批量评分 prompt 模板**: 一次性评估所有 context items 的 prompt 需要多大 context window？是否需要分批？
3. **Feature Flag**: 是否需要环境变量（如 `KB_AGENT_USE_ADAPTIVE_RAG=true`）在新旧模式间切换？
