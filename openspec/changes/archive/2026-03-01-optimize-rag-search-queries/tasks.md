## 1. 拆分的检索参数更新 (hybrid_search)

- [x] 1.1 在 `src/kb_agent/agent/tools.py` 的 `hybrid_search` 函数签名中，将参数 `query: str` 更新为 `semantic_query: str` 和 `exact_keywords: str = ""` 
- [x] 1.2 在 `hybrid_search` 实现内部：如果 `exact_keywords` 为空，尝试用 `semantic_query` 代替；然后向 `_get_grep().search()` 传递 `exact_keywords`，向 `_get_vector().search` 传递 `semantic_query`
- [x] 1.3 更新 `hybrid_search` 的 docstring 说明，明确告知 LLM 这个工具需要传哪些自然语言字段/关键词实体
- [x] 1.4 在 `src/kb_agent/agent/nodes.py` 这个文件中的 `TOOL_DESCRIPTIONS` 中更新 `hybrid_search` 的说明，告知要求区分传参 `semantic_query` 和 `exact_keywords`

## 2. 路由提示词(Prompt) 与解析改造

- [x] 2.1 在 `src/kb_agent/agent/nodes.py` 中更新 `ANALYZE_SYSTEM` prompt，要求对于 `sub_questions` 返回一个对象列表，每个对象含 `{"semantic_intent": "句子...", "search_keywords": "关键词1 关键词2..."}` (如果问题是复杂的话)
- [x] 2.2 更新 `analyze_and_route_node` 解析逻辑里的 fallback 初始化，确保容错处理（如 `routing_plan["sub_questions"]` 解析时支持对象列表或者纯字符串列表）

## 3. 规划节点逻辑及互斥增强 (`plan_node`)

- [x] 3.1 修改 `nodes.py` 里的 `_build_tool_args(tool_name: str, query: str | dict)`。使其能处理入参是个词典的情况：如 tool 为 `hybrid_search` 时，分别提取 `semantic_intent` 和 `search_keywords`。如 tool 为 `grep` 时取 `search_keywords` (或退化到整体 query)
- [x] 3.2 修改 `plan_node` `existing_context` 为空时直接并发拉取 sub_questions 的那段逻辑，现在因为传来的是 `dict`，要妥善传递给 `_build_tool_args`
- [x] 3.3 在 `plan_node` 构建工具调用的入口 (无论是 json 成功还是 text fallback)，拦截/过滤建议的工具 `suggested_tools`：如果数组里有 "hybrid_search"，则删掉数组里的 "vector_search" 和 "grep_search"，以免由于大模型生成的建议产生双倍甚至三倍执行重复操作的开销 

## 4. 测试与验证 

- [x] 4.1 在 `tests/agent/test_analyzer_and_route.py` 或同等文件加入/更新相应的单元测试，确保解析出的 `sub_questions` 能容纳新的字典数组
- [x] 4.2 在 `tests/agent/test_hybrid_search.py` (如果有) 的调用处加上两组分离的参数，确保测试通过
- [x] 4.3 `pytest` 全局运行一次相关测试。
