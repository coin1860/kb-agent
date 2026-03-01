## Why

当前 Agent 的 `hybrid_search` 设计存在缺陷，导致重复调用和检索降级。当 `analyze_and_route` 节点将问题分解为自然语言子问题（如 "kb-agent 依赖哪些工具？"）并同时建议使用 `vector_search` 和 `hybrid_search` 时，会发生两个问题：
1. **重复检索**：`plan_node` 会在同一次迭代中为这两种工具都生成调用，由于当前 `hybrid_search` 内部包含了 `vector_search`，这导致了完全相同的请求去 ChromaDB 跑了两次。
2. **Grep 降级**：`hybrid_search` 仅接收单一的 `query(str)` 参数（如一个完整的自然语言中文疑问句）。因为 Ripgrep 无法匹配置复杂的中文长句，这就导致其依赖的关键字检索（grep_search）部分召回率为0，使得 `hybrid_search` 退化成了一次纯纯的（二手的）向量检索。

我们需要采用大厂的标准解法：分离检索域（自然语义 vs 实体关键字），并修改工具签名接收双维度输入。

## What Changes

- **修改 `hybrid_search` 工具签名 (BREAKING)**：从 `hybrid_search(query: str)` 更改为 `hybrid_search(semantic_query: str, exact_keywords: str)`，内部再将它们分别传递给 vector 和 grep 引擎。
- **修改 `analyze_and_route` 节点输出 Schema**：在分析查询意图时，不仅吐出完整的自然语言 `sub_questions`，还要并行提取供关键词引掣使用的 `search_keywords`。我们将引入一个新的对象结构来代替原有的字符串列表。
- **优化 `plan_node` 的工具互斥路由**：在生成工具调用时，增加互斥拦截逻辑——如果建议工具里已经包含了 `hybrid_search`，则自动剔除独立的 `vector_search` 和 `grep_search` 以避免冗余拉取。

## Capabilities

### New Capabilities
*(None. This refines existing capabilities.)*

### Modified Capabilities
- `adaptive-query-routing`: 修改子问题拆解的输出结构，不再仅是字符串数组，而是包含 `semantic_intent` 和 `exact_keywords` 的结构体；增加工具路由互斥策略。
- `hybrid-retrieval`: 修改工具的入参签名和内部参数分发逻辑，分离语义查询和关键字查询。

## Impact

- **代码影响**: 
  - `src/kb_agent/agent/tools.py` (`hybrid_search`: 签名和实现)
  - `src/kb_agent/agent/nodes.py` (`ANALYZE_SYSTEM`, `analyze_and_route_node`, `plan_node`, `_build_tool_args`)
- **API 兼容性**: 破坏性变更 (Breaking Change) - 纯 LLM prompt 及 JSON output 结构会发生变化，导致之前仅仅提取 `sub_questions` (list of strings) 的逻辑需要重构成提取 dict 列表。
- **性能影响**: 去除因为 `plan_node` 没有做互斥而导致的 100% 重复查询（从 O(2) 降至 O(1)），检索速度翻倍。大幅度提升 grep 的召回命中率，改善 RRF 融合效果。
