## Context

当前 RAG 的 `analyze_and_route` 会将复杂问题拆分为自然语言字符串（如 `"kb-agent 依赖哪些工具"`）。这个字符串随后被喂给 `hybrid_search(query: str)`。在 `hybrid_search` 内部，这一句长话又被分别喂给了 `vector_search`（效果尚可）和 `grep_search`（因包含句法和标点，导致 Ripgrep 完全匹配不到，效果为 0）。结果：混合检索退化为代价昂贵的、重复的单边向量检索。

另外，如果路由系统同时吐出 `["vector_search", "hybrid_search"]`，由于 `plan_node` 缺乏拦截逻辑，还会发起相同参数的查询两次，对向量库极度冗余。

## Goals / Non-Goals

**Goals:**
- 将基于句子的单一维度 `sub_questions` (list[str]) 转换为双维度的复合对象 (list[dict])：语义域 (semantic_intent) + 关键字域 (search_keywords)。
- 把 `hybrid_search` 升序改造为 `hybrid_search(semantic_query, exact_keywords)`，内部解耦两套检索引擎的传参。
- 在 `plan_node` 中引入互斥检查，避免建议列表中各种 search 的同维度同质调用（即：混合搜索开启时，压制单独的向量或关键字搜索）。

**Non-Goals:**
- 不涉及大语言模型底层模型 (LLM) 提供商变更。
- 不影响正常/简单的搜索工作流 (如 `grep_search` 或 `vector_search` 被单独调用时)。

## Decisions

### D1: `analyze_and_route` 输出 Schema 改造

**选择**: 修改 `ANALYZE_SYSTEM` prompt 和 `AgentState.routing_plan["sub_questions"]` 以及对应的解析逻辑，让它不再是简单的 `list[str]`，而是包含 `{"semantic_intent": str, "search_keywords": str}` 的字典列表。
**理由**: 这是治本之法。LLM 自己能非常好地同时做两件事：翻译句义和抠图式提词。

### D2: `hybrid_search` 函数签名更新

**选择**: 重命名 `query` 参数为 `semantic_query`，新增 `exact_keywords` 参数。 `_get_grep().search()` 只用 `exact_keywords`，`_get_vector().search()` 只用 `semantic_query`。
**理由**: 各取所需，两套引擎不再相互制约，极大提升了 Ripgrep 在多源检索情况下的作用。

### D3: `plan_node` 增加工具互斥机制与参数适配更新

**选择**: 当准备开始调用提议的工具时，在快速模式或组装模式下，增加以下拦截：
`if "hybrid_search" in suggested_tools: suggested_tools = [t for t in suggested_tools if t not in ("vector_search", "grep_search")]`
并在 `_build_tool_args` 中增加专门解析字典元素的逻辑，以适配新的 `sub_questions` 字典（若遇到字典，分别抽取并传入对应的 search args）。

**理由**: 把内耗切除，让 `hybrid_search` 真正一肩挑起大梁，无需旁边再跟一个小跟班浪费 token 消耗。

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| JSON 解析对 `sub_questions` 中复杂对象的脆弱性 | 方案结构复杂化导致 LLM 输出可能失效 | 提供清晰的 Prompt Example；依靠现有的容错 fallback 或者继续在 fallback 时退化为 plain string |
| 打破向后兼容：现存的旧字典解析可能出错 | 只有 `plan_node` 这一段逻辑使用了 `sub_questions` | `_build_tool_args` 函数需做好类型兼容判断 (若拿到了新版 dict 就直接用，若拿到 string 则退化为 `semantic_intent=query, exact_keywords=query`) |
