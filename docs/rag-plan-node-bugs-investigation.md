# RAG Plan Node 问题调查与修复方案

> **日期**: 2026-03-01
> **状态**: 待修复
> **影响范围**: `src/kb_agent/agent/nodes.py` — `plan_node`, `_extract_tools_from_text`

---

## 问题复现

用户查询: `"Introduction里面没写什么？"`

```
🛤️ Route: conceptual | Tools: vector_search          ← analyze_and_route ✓ 正确
🧠 Planning: deciding which tools to use (round 1)... ← plan_node 开始
🔄 Extracted intent from AI reasoning: grep_search, vector_search, jira_fetch, confluence_fetch, web_fetch
                                                       ↑ BUG: 路由建议被完全忽略
📋 Plan: grep_search, vector_search, jira_fetch, confluence_fetch, web_fetch
🔍 Executing: grep_search(query='Introduction里面没写什么？')
🔍 Executing: vector_search(query='Introduction里面没写什么？')
🔍 Executing: jira_fetch(issue_key='Introduction里面没写什么？')      ← 荒谬: 中文问题作为 Jira key
🔍 Executing: confluence_fetch(page_id='Introduction里面没写什么？')  ← 荒谬: 中文问题作为 page ID
🔍 Executing: web_fetch(url='Introduction里面没写什么？')             ← 报错: 无效 URL
```

---

## 4 个核心问题

### Bug 1: 复杂查询未拆分为子问题

**现象**: `analyze_and_route` 正确输出了 `sub_questions`，但 `plan_node` 从未使用它们来生成独立的工具调用。

**根因** (`nodes.py:363-382`):

```python
# 路由计划只作为"建议"附加到 prompt 中 (line 363-380)
if routing_plan and not existing_context:
    guidance = f"Query Type: {routing_plan.get('query_type')}\n"
    if routing_plan.get("sub_questions"):
        guidance += f"Sub-questions to retrieve for: {', '.join(...)}\n"  # ← 只是文本提示
    messages.append(SystemMessage(content=f"Initial Routing Analysis:\n{guidance}\n..."))

# 但 HumanMessage 始终是原始问题 (line 382)
messages.append(HumanMessage(content=state["query"]))  # ← 永远是原始 query
```

**问题**: sub_questions 仅作为 system message 的参考文本传给 LLM，LLM 可能忽略它。即使 LLM 采纳了，最终 fallback 路径也只用 `state["query"]` 构建工具调用。

---

### Bug 2: 路由计划被 `_extract_tools_from_text` 覆盖

**现象**: `analyze_and_route` 建议只用 `vector_search`，但 `plan_node` 最终调用了 5 个工具。

**根因** (`nodes.py:400-432`):

LLM 返回的响应 JSON 解析失败时，进入 `_extract_tools_from_text` fallback:

```python
# 这个函数扫描 LLM 响应文本中所有提到的工具名 (line 163-164)
for tool_name, arg_info in tool_arg_map.items():
    if tool_name in text and tool_name not in seen:  # ← 只要文本中提到就算
        found.append(...)
```

LLM 的 `<think>` 推理块中可能写了: *"我可以用 grep_search 或 vector_search，也许 jira_fetch..."*  
这些**推理过程中的提及**被错误地解释为**实际的工具选择决策**。

**关键**: 这个 fallback 完全不参考 `routing_plan.suggested_tools`，也不对工具做任何相关性过滤。

---

### Bug 3: 不相关工具被无条件调用

**现象**: 问一个关于文档内容的问题，却调用了 `jira_fetch`、`confluence_fetch`、`web_fetch`。

**根因** (`nodes.py:148-158`):

```python
tool_arg_map = {
    "grep_search":      {"key": "query",      "value": query},
    "vector_search":    {"key": "query",      "value": query},
    "jira_fetch":       {"key": "issue_key",  "value": query},   # ← 原始问题作为 issue_key
    "confluence_fetch": {"key": "page_id",    "value": query},   # ← 原始问题作为 page_id
    "web_fetch":        {"key": "url",        "value": query},   # ← 原始问题作为 URL
    ...
}
```

没有任何逻辑判断工具是否与问题相关:
- `jira_fetch` 应该只在问题包含 Jira ticket pattern (如 `PROJ-123`) 时调用
- `confluence_fetch` 应该只在问题包含 page ID 或明确提到 Confluence 时调用
- `web_fetch` 应该只在问题包含有效 URL 时调用

---

### Bug 4: 所有工具使用原始问题而非子问题/适配参数

**现象**: 所有工具调用都用 `"Introduction里面没写什么？"` 作为参数，无论工具类型。

**根因**: 两条路径都硬编码使用 `state["query"]`:

1. `_extract_tools_from_text` (line 150-157): `"value": query` 对所有工具
2. `plan_node` fallback (line 441-461): `query = state["query"]` 然后直接传入

---

## 问题流转图

```
┌─────────────────────────────────────────────────────────────────────┐
│                      当前的错误流程                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  analyze_and_route_node                                             │
│  ┌──────────────────────────┐                                       │
│  │ query_type: conceptual   │                                       │
│  │ sub_questions: [...]     │── ✓ 正确产出                           │
│  │ suggested: vector_search │                                       │
│  └──────────────────────────┘                                       │
│           │                                                         │
│           ▼                                                         │
│  plan_node                                                          │
│  ┌───────────────────────────────────────────────────┐              │
│  │ 1. routing_plan 作为"建议" 发给 LLM               │              │
│  │ 2. LLM 回复 (常在 <think> 推理块中)                │              │
│  │ 3. JSON 解析失败                                   │              │
│  │ 4. _extract_tools_from_text 扫描文本中的工具名     │ ← ❌ Bug 2   │
│  │    → 找到 grep, vector, jira, confluence, web      │              │
│  │ 5. 所有工具参数 = 原始问题                         │ ← ❌ Bug 4   │
│  │ 6. sub_questions 完全被忽略                        │ ← ❌ Bug 1   │
│  │ 7. 不判断工具是否与问题相关                        │ ← ❌ Bug 3   │
│  └───────────────────────────────────────────────────┘              │
│           │                                                         │
│           ▼                                                         │
│  tool_node → 执行 5 个工具，其中 3 个完全无意义                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 修复方案

### 方案总览

| # | 问题 | 修改位置 | 修复策略 |
|---|------|----------|----------|
| 1 | 子问题未被使用 | `plan_node` | 若存在 sub_questions，为每个子问题独立生成工具调用 |
| 2 | 路由计划被覆盖 | `_extract_tools_from_text` | 接受 `allowed_tools` 参数，只提取被路由允许的工具 |
| 3 | 不相关工具被调用 | `_extract_tools_from_text` | 增加工具适用性校验 (Jira pattern, URL 格式等) |
| 4 | 工具参数不适配 | `_extract_tools_from_text` + `plan_node` | 使用子问题作为参数；对特殊工具做参数格式校验 |

---

### Fix 1: plan_node 使用子问题驱动工具调用

**思路**: 如果 `routing_plan.sub_questions` 非空，为每个子问题分别生成工具调用，而非只针对原始 query。

```python
# plan_node 中 (替换 line 382 附近)

sub_questions = state.get("sub_questions") or []
if sub_questions and not existing_context:
    # 复杂查询: 每个子问题独立检索
    all_tool_calls = []
    suggested_tools = (routing_plan or {}).get("suggested_tools", ["vector_search"])
    
    for sq in sub_questions:
        for tool_name in suggested_tools:
            if tool_name in ("grep_search", "vector_search", "hybrid_search", "local_file_qa"):
                all_tool_calls.append({"name": tool_name, "args": {"query": sq}})
            elif tool_name == "graph_related":
                all_tool_calls.append({"name": tool_name, "args": {"entity_id": sq}})
    
    if all_tool_calls:
        return {"pending_tool_calls": all_tool_calls}

# 简单查询: 保持现有逻辑
messages.append(HumanMessage(content=state["query"]))
```

---

### Fix 2: `_extract_tools_from_text` 支持工具白名单

**思路**: 传入 `routing_plan.suggested_tools` 作为白名单，只提取被路由允许的工具。

```python
def _extract_tools_from_text(
    raw_response: str,
    query: str,
    allowed_tools: list[str] | None = None,  # 新参数
) -> list[dict[str, Any]]:
    ...
    for tool_name, arg_info in tool_arg_map.items():
        # 如果有白名单，只允许白名单中的工具
        if allowed_tools and tool_name not in allowed_tools:
            continue
        if tool_name in text and tool_name not in seen:
            ...
```

**调用处修改** (`plan_node` line 426):

```python
suggested = (routing_plan or {}).get("suggested_tools")
tool_calls = _extract_tools_from_text(raw_response, state["query"], allowed_tools=suggested)
```

---

### Fix 3: 工具适用性校验 (Tool Relevance Guard)

**思路**: 在 `_extract_tools_from_text` 中，对特殊工具增加格式校验。不满足条件的工具不应该被调用。

```python
import re

def _is_tool_applicable(tool_name: str, query: str) -> bool:
    """判断工具是否适用于给定查询"""
    if tool_name == "jira_fetch":
        # 只在问题中包含 Jira ticket pattern 时调用
        return bool(re.search(r'[A-Z]+-\d+', query))
    
    if tool_name == "confluence_fetch":
        # 只在问题提到 confluence 或包含数字 page ID 时调用
        return bool(re.search(r'confluence|wiki|page.?\d+', query, re.IGNORECASE))
    
    if tool_name == "web_fetch":
        # 只在问题中包含有效 URL 时调用
        return bool(re.search(r'https?://', query))
    
    # grep_search, vector_search, hybrid_search, local_file_qa, read_file, graph_related
    # 这些是通用搜索工具，总是适用
    return True
```

在 `_extract_tools_from_text` 循环中增加:

```python
for tool_name, arg_info in tool_arg_map.items():
    if allowed_tools and tool_name not in allowed_tools:
        continue
    if not _is_tool_applicable(tool_name, query):  # ← 新增
        continue
    if tool_name in text and tool_name not in seen:
        ...
```

---

### Fix 4: 工具参数适配

**思路**: 不同工具应该使用不同的参数提取逻辑，而非统一使用原始 query。

```python
def _build_tool_args(tool_name: str, query: str) -> dict[str, str] | None:
    """为工具构建合适的参数，返回 None 表示不应调用该工具"""
    
    if tool_name in ("grep_search", "vector_search", "hybrid_search", "local_file_qa"):
        return {"query": query}
    
    if tool_name == "read_file":
        return {"file_path": query}
    
    if tool_name == "graph_related":
        return {"entity_id": query}
    
    if tool_name == "jira_fetch":
        match = re.search(r'([A-Z]+-\d+)', query)
        if match:
            return {"issue_key": match.group(1)}
        return None  # 无法提取有效 issue_key
    
    if tool_name == "confluence_fetch":
        match = re.search(r'(\d{5,})', query)  # Confluence page IDs 通常是长数字
        if match:
            return {"page_id": match.group(1)}
        return None
    
    if tool_name == "web_fetch":
        match = re.search(r'(https?://[^\s]+)', query)
        if match:
            return {"url": match.group(1)}
        return None
    
    return {"query": query}  # fallback
```

---

## 修改影响评估

| 文件 | 改动量 | 风险 |
|------|--------|------|
| `agent/nodes.py` — `_extract_tools_from_text` | ~30 行 | 低: 只增加过滤逻辑 |
| `agent/nodes.py` — `plan_node` | ~20 行 | 中: 子问题驱动逻辑是新路径 |
| `agent/nodes.py` — 新增 `_is_tool_applicable` | ~20 行 | 低: 纯判断函数 |
| `agent/nodes.py` — 新增 `_build_tool_args` | ~30 行 | 低: 纯参数构建函数 |

**总改动**: ~100 行，集中在 `nodes.py` 一个文件。

**向后兼容**: 完全兼容。对外接口 `Engine.answer_query()` 不变，只是内部工具选择更精准。

**测试建议**:
1. 简单概念型查询 → 应只调用 `vector_search`
2. 包含 Jira ticket 的查询 → 应调用 `jira_fetch` + `grep_search`
3. 复杂多部分查询 → 应拆分为子问题，每个子问题独立检索
4. 包含 URL 的查询 → 应调用 `web_fetch` + 其他搜索工具
5. 纯中文概念型问题 → 绝不应调用 `jira_fetch`/`confluence_fetch`/`web_fetch`
