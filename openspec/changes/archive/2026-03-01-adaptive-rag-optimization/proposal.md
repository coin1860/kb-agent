## Why

当前 Agentic RAG 采用线性 4 节点拓扑（plan → tool_exec → evaluate → synthesize），`plan_node` 缺乏查询分析能力，默认 fallback 到 `grep_search + vector_search` 齐头并进。GrepTool 效果不佳的根因有三：

1. **无查询分析/路由**：所有类型问题都走同样的工具组合，LLM 生成的 grep 关键字经常太宽泛或太狭窄
2. **单行返回无上下文**：ripgrep 命中一行后不拉取前后上下文，导致碎片化信息无法被 evaluate 正确判断
3. **缺乏闭环验证**：evaluate_node 只做 sufficient/not-sufficient 二分判断，无法区分"部分相关"和"完全无关"，导致低质量证据被采纳或高质量证据被丢弃

仿照 Google Search AI Mode，需要引入自适应路由、混合检索、和 CRAG 闭环验证，让 Agent 像搜索引擎一样"先理解问题复杂度，再选择最佳检索策略"。

## What Changes

- **新增查询分析与自适应路由节点** (`analyze_and_route`)：在 `plan_node` 之前增加查询分解层，将问题分类为"精确型/概念型/关系型/文件发现型"，自适应选择工具组合
- **升级 GrepTool 为混合检索**：引入 BM25 全文评分 + 上下文窗口（前后 10 行）增强，与向量检索结果做 RRF (Reciprocal Rank Fusion) 重排序
- **引入 CRAG (Corrective RAG) 评分机制**：替换 evaluate_node 的简单二分判断，新增 relevance grader 对每条证据打分（0-1），根据分数自适应决策：直接生成 / 扩大检索 / 要求用户澄清
- **带引用的生成 (Citations)**：synthesize_node 输出时强制附带源文件路径和行号引用
- **查询分解 (Sub-question Decomposition)**：复杂问题自动拆分为原子子问题，每个子问题独立检索后汇总

## Capabilities

### New Capabilities
- `adaptive-query-routing`: 查询复杂度分析与自适应工具路由，包含查询分解（sub-question decomposition）和意图分类（精确/概念/关系/文件发现）
- `hybrid-retrieval`: BM25 + 向量混合检索，包含上下文窗口增强和 RRF 重排序融合
- `corrective-rag`: CRAG 闭环验证评分，对检索证据做细粒度 relevance 打分，驱动自适应决策（生成/重检索/澄清）

### Modified Capabilities
- `query-engine`: 升级 LangGraph 拓扑从 4 节点线性架构到自适应多阶段架构；synthesize 节点新增强制引用（citation）能力

## Impact

- **核心文件**：`agent/graph.py`（拓扑重构）、`agent/nodes.py`（新增/修改节点）、`agent/state.py`（状态扩展）
- **工具层**：`tools/grep_tool.py`（BM25 + 上下文窗口）、`agent/tools.py`（新增 `hybrid_search` wrapper）
- **依赖**：可能新增 `rank-bm25` Python 包用于 BM25 评分
- **API 兼容**：`Engine.answer_query()` 对外接口不变，内部 graph 拓扑变化对调用方透明
- **性能**：混合检索和 CRAG 评分会增加 1-2 次额外 LLM 调用，但通过减少无效迭代（当前常见 3 轮循环仍不命中）总体 latency 预期持平或降低
