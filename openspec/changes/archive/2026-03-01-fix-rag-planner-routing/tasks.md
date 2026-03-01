## 1. 工具适用性校验函数

- [x] 1.1 在 `nodes.py` 中新增 `_is_tool_applicable(tool_name: str, query: str) -> bool` 函数，对 `jira_fetch`（需 `[A-Z]+-\d+` pattern）、`confluence_fetch`（需 `confluence`/`wiki`/数字 page ID）、`web_fetch`（需 `https?://` URL）增加正则校验，其余工具返回 True
- [x] 1.2 在 `nodes.py` 中新增 `_build_tool_args(tool_name: str, query: str) -> dict | None` 函数，根据工具类型提取合适参数：搜索工具用 `{"query": ...}`，`jira_fetch` 提取 issue key，`web_fetch` 提取 URL，返回 None 表示不应调用

## 2. `_extract_tools_from_text` 白名单过滤

- [x] 2.1 修改 `_extract_tools_from_text` 签名，新增 `allowed_tools: list[str] | None = None` 参数
- [x] 2.2 在工具提取循环中，当 `allowed_tools` 非空时跳过不在白名单中的工具
- [x] 2.3 在工具提取循环中调用 `_is_tool_applicable` 跳过不适用的工具
- [x] 2.4 将 `tool_arg_map` 中的静态 `"value": query` 替换为 `_build_tool_args` 动态构建，返回 None 时跳过该工具

## 3. `plan_node` 子问题驱动

- [x] 3.1 在 `plan_node` 中，当 `routing_plan.sub_questions` 非空且为首轮（无 existing_context）时，跳过 LLM 调用，为每个子问题 × suggested_tool 组合调用 `_build_tool_args` 生成工具调用列表
- [x] 3.2 修改 `plan_node` 中 `_extract_tools_from_text` 的调用处，传入 `allowed_tools=routing_plan.get("suggested_tools")`

## 4. 测试验证

- [x] 4.1 端到端测试：概念型中文问题（如 "Introduction里面没写什么？"）应只调用 `vector_search`，不调用 `jira_fetch`/`confluence_fetch`/`web_fetch`
- [x] 4.2 端到端测试：包含 Jira ticket 的问题（如 "PROJ-123 的状态"）应调用 `jira_fetch(issue_key="PROJ-123")`
- [x] 4.3 端到端测试：包含 URL 的问题应调用 `web_fetch(url="https://...")` 
- [x] 4.4 端到端测试：复杂多部分问题应拆分为子问题，每个子问题独立检索
