## Why

当前 Agentic RAG 管线对所有查询一视同仁——即使是 "你好" 或 "VectorTool 是什么" 这样的简单问题，也要走完 `analyze_and_route → plan → tool_exec → grade_evidence → synthesize` 全部 5 个节点（4 次 LLM 调用）。`grade_evidence` 节点将所有 context items 整体发送给 LLM 做批量打分，当 context 较多时 token 消耗大、延迟高。同时，很多场景下（如 read_file 结果、vector_search 高分结果）根本不需要 LLM 介入就能判定证据充分。

核心问题：**缺乏按查询复杂度分流的机制，以及缺乏零 LLM 开销的证据预筛能力**。

## What Changes

- **快路径分类器 (Fast-Path Classifier)**：在 `analyze_and_route` 节点的输出中新增 `complexity` 字段（`simple` / `complex`），简单查询跳过 `grade_evidence` 直接进入 `synthesize`，省 1 次 LLM 调用
- **闲聊短路 (Chitchat Short-circuit)**：新增 `chitchat` 查询类型，闲聊/问候类查询跳过整个 RAG 管线（plan + tool_exec + grade_evidence），直接由 `synthesize` 回复，省 3 次 LLM 调用
- **规则预筛 (Rule-based Pre-filter)**：在 `grade_evidence` 节点的 LLM 调用前增加规则引擎，对常见高置信场景自动通过（如 read_file 结果、vector_search 高分命中、少量 context），仅将不确定的 items 送 LLM 打分
- **Graph 拓扑条件边**：在 `tool_exec → grade_evidence` 之间插入条件路由，根据 complexity 和 query_type 决定是否跳过 grading

## Capabilities

### New Capabilities
- `fast-path-classifier`: 查询复杂度分级（simple/complex/chitchat）与管线短路机制，根据复杂度自适应跳过不必要的 LLM 节点

### Modified Capabilities
- `adaptive-query-routing`: 路由输出新增 `complexity` 字段；新增 `chitchat` 查询类型
- `corrective-rag`: grade_evidence 节点新增规则预筛层，在 LLM 打分前用规则过滤高置信场景
- `query-engine`: Graph 拓扑新增 `tool_exec` 后的条件边，支持跳过 `grade_evidence` 直接到 `synthesize`

## Impact

- **核心文件**：`agent/graph.py`（新增条件边）、`agent/nodes.py`（analyze_and_route 输出扩展 + grade_evidence 预筛逻辑）、`agent/state.py`（可能无变更，复用 routing_plan）
- **API 兼容**：`Engine.answer_query()` 对外接口不变，内部管线变化对调用方透明
- **性能预期**：简单查询 LLM 调用从 4 次降至 2 次（analyze + synthesize），闲聊降至 1 次；复杂查询通过规则预筛减少 grading token 消耗
- **无新依赖**：规则预筛使用已有的 tool_history 和 vector score metadata，无需引入新包
