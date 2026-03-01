## Context

当前 `plan_node` 承担工具选择职责，通过 LLM 调用决定下一步使用哪些工具。`analyze_and_route` 节点正确产出路由计划（`query_type`、`sub_questions`、`suggested_tools`），但 `plan_node` 仅将其作为 prompt 中的参考文本传给 LLM，LLM 的 JSON 响应解析失败后，`_extract_tools_from_text` fallback 扫描 LLM 推理文本中所有被提到的工具名并无条件调用。

**现有代码关键位置**:
- `nodes.py:135-179` — `_extract_tools_from_text`: 纯文本匹配提取工具名，不参考路由计划
- `nodes.py:314-493` — `plan_node`: 路由计划仅作为 SystemMessage guidance，最终 HumanMessage 始终是原始 query
- `nodes.py:148-158` — `tool_arg_map`: 所有工具统一使用原始 query 作为参数

**受影响的数据流**:
```
analyze_and_route → routing_plan (query_type, sub_questions, suggested_tools)
                         ↓
                    plan_node → 应该尊重 routing_plan，实际上忽略了它
                         ↓
                 _extract_tools_from_text → 从 LLM 推理文本中提取所有提到的工具
```

## Goals / Non-Goals

**Goals:**
- G1: `plan_node` 在 fallback 路径中严格遵守 `routing_plan.suggested_tools` 白名单
- G2: 当 `sub_questions` 存在时，为每个子问题独立生成工具调用
- G3: 特殊工具（`jira_fetch`、`confluence_fetch`、`web_fetch`）仅在参数格式有效时被调用
- G4: 保持正常 JSON 解析成功时 LLM 的完全自主权不变（只约束 fallback 路径）

**Non-Goals:**
- NG1: 不修改 `analyze_and_route` 节点逻辑（它已经正确工作）
- NG2: 不修改 `tool_node` 执行逻辑
- NG3: 不引入新的 LLM 调用或改变调用次数
- NG4: 不修改 `grade_evidence` / `synthesize` 节点

## Decisions

### D1: `_extract_tools_from_text` 增加 `allowed_tools` 白名单过滤

**选择**: 给函数新增 `allowed_tools: list[str] | None` 参数。当白名单非空时，只提取白名单中的工具。

**理由**: 这是最小侵入的修复 — 只在 fallback 路径生效，不影响 JSON 解析成功时 LLM 的自主决策。`plan_node` 调用时传入 `routing_plan.get("suggested_tools")`。

**替代方案**: 完全移除 `_extract_tools_from_text`，JSON 解析失败时直接按 routing_plan 生成工具调用。
**否决原因**: 保留文本提取能力有助于 LLM 在 routing_plan 范围内做更细粒度的参数选择（如从推理文本中提取具体关键词）。

---

### D2: 新增 `_is_tool_applicable` 工具适用性校验

**选择**: 新增独立函数，通过正则匹配判断工具是否适用于给定 query:
- `jira_fetch`: query 中包含 `[A-Z]+-\d+` pattern
- `confluence_fetch`: query 中包含 `confluence`/`wiki`/数字 page ID
- `web_fetch`: query 中包含 `https?://` URL

其余工具（`grep_search`、`vector_search`、`hybrid_search`、`local_file_qa`、`read_file`、`graph_related`）视为通用工具，始终适用。

**应用时机**: 在 `_extract_tools_from_text` 循环和 `plan_node` fallback 路径中调用。

**替代方案**: 在 LLM prompt 中更强调工具适用条件。
**否决原因**: prompt 工程不可靠——LLM 仍然可能在 `<think>` 块中提到这些工具导致被提取。硬编码校验更确定。

---

### D3: 子问题驱动工具调用

**选择**: 在 `plan_node` 中，当 `routing_plan.sub_questions` 非空且当前为首轮（无 existing_context）时，跳过 LLM 调用，直接为每个子问题 × 每个 suggested_tool 生成工具调用。

**参数逻辑**: 使用 `_build_tool_args(tool_name, sub_question)` 为每个组合生成适配的参数。

**替代方案**: 仍然让 LLM 决定，但将子问题作为独立的 HumanMessage 发送。
**否决原因**: 增加 LLM 调用次数（每个子问题一次 plan 调用），且 LLM 仍可能忽略子问题。直接构建更确定。

---

### D4: `_build_tool_args` 参数适配函数

**选择**: 新增函数，根据工具类型提取合适的参数:
- 搜索工具: `{"query": sub_question}`
- `jira_fetch`: 从 query 中正则提取 issue key，提取不到则返回 None（不调用）
- `web_fetch`: 从 query 中正则提取 URL，提取不到则返回 None
- `confluence_fetch`: 从 query 中提取 page ID 或搜索关键词

**返回 None 表示不应调用该工具**，调用方跳过。

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| 白名单过于严格，阻止 LLM 做有用的工具选择 | 某些边界 case 可能漏掉有用工具 | 白名单仅在 fallback 路径生效；JSON 解析成功时 LLM 仍有完全自主权 |
| 子问题直接构建跳过 LLM → 参数质量可能不如 LLM 优化的 | 搜索召回率略降 | sub_questions 已经是 LLM 在 analyze_and_route 中精心拆解的，质量足够 |
| `_is_tool_applicable` 正则可能漏掉合法的 Jira/Confluence 引用 | false negative | 正则覆盖常见 pattern，后续可按需扩展；这比 false positive 好得多 |
| 直接跳过 plan LLM 调用减少了一次 LLM 参与 | 灵活性降低 | 仅在有 sub_questions 时跳过；简单查询仍走 LLM plan |
