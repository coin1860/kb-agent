## Why

`plan_node` 的工具选择逻辑存在 4 个关联 Bug，导致 `analyze_and_route` 节点的路由计划被完全忽略：LLM 响应 JSON 解析失败时，`_extract_tools_from_text` fallback 会从推理文本中提取所有被提及的工具名并无条件调用，不考虑路由白名单、工具适用性、也不使用子问题作为参数。结果是简单概念型问题（如 "Introduction里面没写什么？"）会触发 `jira_fetch`（中文问题作为 issue_key）、`web_fetch`（中文问题作为 URL 导致报错）等完全不相关的工具调用，浪费时间和资源。

## What Changes

- **修复 `_extract_tools_from_text` 函数**: 新增 `allowed_tools` 白名单参数，只提取 `routing_plan.suggested_tools` 允许的工具；新增工具适用性校验（`jira_fetch` 需要 PROJ-123 pattern，`web_fetch` 需要有效 URL，`confluence_fetch` 需要 page ID 或关键词）
- **修复 `plan_node` 子问题驱动**: 当 `routing_plan.sub_questions` 非空时，为每个子问题独立生成工具调用，而非只用原始 query
- **新增 `_is_tool_applicable` 校验函数**: 判断工具是否适用于给定查询（pattern 匹配）
- **新增 `_build_tool_args` 参数构建函数**: 不同工具使用不同参数提取逻辑，避免中文问题直接作为 Jira key / URL / page ID

## Capabilities

### New Capabilities
- `planner-tool-guard`: 工具选择约束与适用性校验 — 确保 plan_node 的工具选择受路由计划约束，不相关工具不被调用，工具参数格式合理

### Modified Capabilities
- `adaptive-query-routing`: plan_node 增强为真正使用 routing_plan 的 suggested_tools 和 sub_questions，而非仅作为提示文本
- `query-engine`: plan_node 内部逻辑修改，fallback 路径增加工具过滤和参数适配

## Impact

- **核心文件**: `src/kb_agent/agent/nodes.py` — 修改 `_extract_tools_from_text`、`plan_node`；新增 `_is_tool_applicable`、`_build_tool_args`
- **改动量**: ~100 行，集中在单个文件
- **API 兼容**: `Engine.answer_query()` 对外接口不变，内部工具选择更精准
- **性能**: 减少不必要的工具调用（3-4 个无效调用 → 0），每次查询节省 1-3 秒
- **依赖**: 无新依赖
