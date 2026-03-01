## 1. AgentState 扩展

- [x] 1.1 在 `agent/state.py` 的 `AgentState` 中新增字段：`query_type: str`、`sub_questions: list[str]`、`routing_plan: dict`、`evidence_scores: list[float]`、`grader_action: str`
- [x] 1.2 为新字段添加 docstring 注释

## 2. 查询分析与自适应路由 (adaptive-query-routing)

- [x] 2.1 在 `agent/nodes.py` 中新增 `analyze_and_route_node` 函数，实现查询意图分类（exact/conceptual/relational/file_discovery）
- [x] 2.2 编写 `ANALYZE_SYSTEM` prompt，输出结构化 JSON：`{query_type, sub_questions, suggested_tools, grep_keywords}`
- [x] 2.3 实现 sub-question 分解逻辑：复杂问题拆分为原子子问题，简单问题跳过分解
- [x] 2.4 修改 `plan_node`，读取 `AgentState.routing_plan` 作为工具选择的首选依据，而非默认 fallback 全部工具
- [x] 2.5 为 `analyze_and_route_node` 编写单元测试，覆盖 4 种 query_type 分类场景

## 3. 混合检索 (hybrid-retrieval)

- [x] 3.1 在 `tools/grep_tool.py` 的 `_ripgrep_search` 中添加 `-C 10` 参数，返回上下文窗口（前后 10 行）
- [x] 3.2 实现同文件相邻匹配（20 行内）的 passage 合并去重
- [x] 3.3 添加 `rank-bm25` 依赖至 `pyproject.toml`
- [x] 3.4 在 `tools/grep_tool.py` 中新增 `_bm25_rerank` 方法，对 grep passages 做 BM25 评分排序，过滤低分结果
- [x] 3.5 在 `agent/tools.py` 中新增 `hybrid_search` LangChain tool，封装 grep(BM25) + vector_search 并行调用 + RRF 融合逻辑
- [x] 3.6 将 `hybrid_search` 添加到 `ALL_TOOLS` 列表和 `TOOL_DESCRIPTIONS` 中
- [x] 3.7 为 `hybrid_search` 编写单元测试：正常融合、单源为空 fallback、BM25 评分排序

## 4. CRAG 闭环验证 (corrective-rag)

- [x] 4.1 在 `agent/nodes.py` 中新增 `grade_evidence_node` 函数，替换原 `evaluate_node`
- [x] 4.2 编写 `GRADER_SYSTEM` prompt，对所有 context items 批量打分（0.0-1.0 JSON 数组）
- [x] 4.3 实现证据过滤：移除 score < 0.3 的 context items
- [x] 4.4 实现聚合决策：avg ≥ 0.7 → GENERATE，0.3-0.7 → REFINE，< 0.3 → RE_RETRIEVE
- [x] 4.5 实现 grader JSON 解析失败的 fallback（默认 0.5 分）
- [x] 4.6 为 `grade_evidence_node` 编写单元测试：覆盖 GENERATE/REFINE/RE_RETRIEVE 三种路径和 parse failure

## 5. 带引用的生成 (citations)

- [x] 5.1 统一 context item 格式为 `[SOURCE:{path}:L{line}] content`，在 `tool_node` 结果拼接时添加来源前缀
- [x] 5.2 修改 `synthesize_node` 的 `SYNTHESIZE_SYSTEM` prompt，要求 LLM 输出脚注引用格式 `[N]`
- [x] 5.3 在 `synthesize_node` 中实现 citation footer 自动追加逻辑
- [x] 5.4 处理无行号 metadata 的情况（vector_search 结果仅引用文件路径）

## 6. Graph 拓扑重构

- [x] 6.1 修改 `agent/graph.py`，新增 `analyze_and_route` 和 `grade_evidence` 节点
- [x] 6.2 实现新拓扑：`START → analyze_and_route → plan → tool_exec → grade_evidence`，从 `grade_evidence` 三路条件边（GENERATE → synthesize, REFINE → plan, RE_RETRIEVE → analyze_and_route）
- [x] 6.3 修改 `_route_after_evaluate` 为 `_route_after_grade`，支持三路决策 + max_iter 保底
- [x] 6.4 将 `KB_AGENT_MAX_ITERATIONS` 默认值调整为 3
- [x] 6.5 移除旧 `evaluate_node` 引用，保持向后兼容

## 7. 集成测试与验证

- [x] 7.1 跑通所有 existing 单元测试（`pytest`）确保无退化
- [x] 7.2 验证 TUI 正常工作，运行知识库相关的查询，检查来源片段是否正常拼接。走 grep → BM25 → 命中，概念查询走 hybrid → RRF → 命中
- [x] 7.3 编写端到端测试：CRAG REFINE 路径触发二次检索后成功合成
- [x] 7.4 验证 citation footer 在最终输出中正确附带源文件引用
- [x] 7.5 TUI 端到端验证：在 TUI 中用 knowledge_base 模式提问并确认新拓扑运行和引用展示
