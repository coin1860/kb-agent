## Why

CLI mode (`kb-cli`) 的 `free_agent` 路径对所有用户输入一视同仁，无论是"hi"还是复杂的知识查询，都强制走 generate_plan → execute_plan 的重量级流程。这导致三个核心问题：RAG 模式成熟的 CRAG 过滤、chitchat 快捷路由、实体追踪等智能能力没有复用；`vector_search` 作为默认 fallback 会对无关问题返回无关 chunks；CLI 没有对话历史传递，跨轮没有上下文。这些问题已经积累到影响日常使用体验的程度，需要在 skill 路径保持不变的前提下系统性修复。

## What Changes

- **CLI `free_agent` 路由重定向至 RAG graph**：当 `route_intent` 未匹配 skill 时，由 `shell.py` 直接调用 `rag_graph.invoke()`，替代现有的 `generate_plan → execute_plan` 链。
- **新增 CLI chitchat 快捷路径**：RAG graph 的 `analyze_and_route` 节点输出 `route_decision="direct"` 时，跳过所有工具调用，直接由 LLM 回答（"hi"、"谢谢"等对话类输入）。
- **新增会话双向历史记录**：`shell.py` 在每轮结束后保存 `{"role": "user", ...}` 和 `{"role": "assistant", ...}` 的完整对话历史，并在每次 RAG graph 调用时传入 `messages` 字段，使 `analyze_and_route` 能够解析代词引用和上下文延续。
- **vector_search 结果经 CRAG 过滤后再展示**：free_agent 路径的 `vector_search` 结果经过 `grade_evidence_node` 评分过滤后，再由 `synthesize_node` 生成自然语言回答，不再返回原始 chunks。
- **CLI RAG 调用的状态回调**：RAG graph `status_callback` 接入 `SkillRenderer`，在 CLI 里实时输出 emoji 进度提示（🧠 Planning / 🔍 Searching / ⚖️ Grading / ✨ Synthesizing）。
- **skill 路径不变**：当 `route_intent` 匹配 skill 时，完整保留现有的 generate_plan → approval_gate → execute_plan 流程（包含 plan 展示 UX）。

## Capabilities

### New Capabilities

- `cli-rag-bridge`: CLI free_agent 模式调用 RAG graph 的 bridge 层，负责构建 AgentState、传递 session 历史、接收 `final_answer` 并格式化输出。
- `cli-session-history`: CLI session 双向对话历史记录机制，存储 user/assistant 消息对，供 RAG graph 的 `analyze_and_route` 消费。

### Modified Capabilities

- `routing-engine`: CLI 的 free_agent 路径现在也经过 `analyze_and_route` 节点，需要在规格中明确 CLI/TUI 两套入口均使用同一 RAG graph。
- `routing-adaptive`: `analyze_and_route` 承担的 chitchat 快捷路由现在也覆盖 CLI 模式，不只是 TUI。

## Impact

- **修改文件**：`src/kb_agent/skill/shell.py`（主要改动）、`src/kb_agent/skill/session.py`（历史存储）
- **不修改**：`src/kb_agent/skill/planner.py`、`skill/executor.py`（skill 路径保留原样）
- **不修改**：`src/kb_agent/agent/nodes.py`、`agent/graph.py`（RAG graph 原样复用）
- **依赖**：`rag_graph.invoke()` 需要 `AgentState` schema，需确认 CLI 使用的 LLM 实例与 RAG 兼容（当前两者都是 `skill_cli.py` 里的同一个 `llm` 对象）
- **无 breaking change**：skill 路径 UX 不变，只有 free_agent 路径行为升级
