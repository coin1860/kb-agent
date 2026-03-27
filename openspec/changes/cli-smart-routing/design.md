## Context

CLI mode (`kb-cli`) 当前通过 `SkillShell._run_command()` 处理所有非 builtin 命令，固定流程为：`route_intent()` → `generate_plan()` → `approval_gate()` → `execute_plan()`。这条链路为 skill playbook 设计，不适合无结构的自然语言问答。

RAG 模式（TUI）已实现了一套成熟的 LangGraph agentic pipeline：`analyze_and_route → plan → tool_exec → rerank → grade_evidence → reflect → synthesize`，具备 chitchat 快捷路由、CRAG 相关性过滤、实体精准追踪等能力，但 CLI 完全没有复用这套逻辑。

**当前数据流（问题）：**
```
用户: "hi"
  → route_intent()        # LLM call 1: 路由分类
  → generate_plan()       # LLM call 2: 生成 [vector_search(query="hi")]
  → approval_gate()       # 展示 plan（哪怕只读也展示）
  → execute_plan()
      → vector_search("hi")   # 返回完全不相关的 chunks
      → reflect()         # LLM call 3: 判断 continue/retry
  → 输出: 一堆无关 chunks 的拼接
```

**目标数据流（fix 后）：**
```
用户: "hi"
  → route_intent()        # 无 skill 匹配 → free_agent
  → _run_rag_query()      # Bridge to RAG graph
      → analyze_and_route # LLM: route_decision="direct"
      → synthesize        # LLM: chitchat 模式，直接回答
  → 输出: "你好！有什么我可以帮助你的？"
```

## Goals / Non-Goals

**Goals:**
- CLI `free_agent` 模式调用 RAG graph，复用其全套智能路由和 CRAG 过滤
- 实现 chitchat 快捷路径（"hi" 等直接回答，不走工具）
- CLI session 存储双向对话历史，使 `analyze_and_route` 能解析代词引用
- RAG graph 的 `status_callback` 接入 CLI renderer，展示实时进度
- 保留 skill 路径（有 playbook 匹配时）的完整 plan+approval UX 不变

**Non-Goals:**
- 不修改 RAG graph 内部节点（`nodes.py`, `graph.py`）
- 不修改 skill 路径的 `planner.py`、`executor.py`
- 不为 CLI 实现独立的 CRAG 或 rerank（直接复用 RAG graph 即可）
- 不改变 TUI 模式行为

## Decisions

### Decision 1：以 `route_intent` 的结果作为分叉点，而不是新增前置路由

**方案 A（选择）**：保留 `route_intent()`，当其返回 `free_agent` 时，改为走 RAG graph 而非 `generate_plan`。

**方案 B（否决）**：用扩展的 `analyze_and_route` 替换 `route_intent`，让其额外输出 `route_decision="skill"`。

**理由**：方案 A 改动最小，`route_intent` 已经有完整的 skill 匹配逻辑（基于 playbook 描述），不需要重写。方案 B 会让 RAG graph 的 `analyze_and_route` 需要感知 CLI 的 skill 配置，产生不必要的耦合。

### Decision 2：实现 `_run_rag_query()` bridge 方法，隔离 RAG 调用

新增 `SkillShell._run_rag_query(command, session_messages)` 方法，负责：
1. 构建 `AgentState` 初始化字典（`query`, `messages`, `status_callback`）
2. 调用 `compiled_rag_graph.invoke(state)`
3. 提取 `state["final_answer"]` 并调用 `renderer.print_result()`

好处：RAG graph 无感知 CLI 存在，两者通过 `AgentState` 接口解耦。

### Decision 3：`status_callback` 使用 lambda 接入 `SkillRenderer`

RAG graph 通过 `state["status_callback"](emoji, msg)` 发送进度。CLI 中：
```python
status_callback = lambda emoji, msg: self.renderer.print_info(f"{emoji} {msg}")
```
无需修改 renderer，也无需修改 RAG graph。

### Decision 4：会话历史存储为 `list[dict[str, str]]`（RAG messages 格式）

`SkillShell.session_messages: list[dict[str, str]]` 替换现有的 `session_history: list[str]`（或同时保留两者以兼容 `_show_history` 等功能）。

每轮结束后追加：
```python
self.session_messages.append({"role": "user", "content": command})
self.session_messages.append({"role": "assistant", "content": result})
```

### Decision 5：RAG graph 实例在 shell 初始化时编译一次，复用

```python
# __init__ 中
from kb_agent.agent.graph import compile_graph
self._rag_graph = compile_graph()
```

避免每次请求重新编译 LangGraph（编译有成本）。

## Risks / Trade-offs

- **[Risk] `AgentState` 字段与 CLI 的 `Session` 字段不完全对应** → Mitigation：只传 RAG graph 需要的字段（`query`, `messages`, `status_callback`），其余字段使用默认值。AgentState 是 TypedDict，缺少的 key 默认 None。
- **[Risk] RAG graph 的 LLM 实例与 CLI 的 LLM 实例分开构建** → Mitigation：`nodes.py` 的 `_build_llm()` 使用全局 `config.settings`，与 `skill_cli.py` 里构建的 LLM 使用相同配置，结果等价。可以先不传入 llm 参数。
- **[Risk] 对话历史过长时 token 超限** → Mitigation：传入 `messages` 时截断至最近 N 轮（如 10 轮），与 RAG TUI 模式的处理方式一致。
- **[Risk] free_agent 路径原本展示 plan table，改为 RAG graph 后用户看到的是 emoji 进度流** → Trade-off：这是预期的体验升级，free_agent 路径本来的 plan 展示价值有限（plan 是 LLM 预测的，不代表最终工具选择）。

## Migration Plan

1. 无 breaking change。现有 skill 路径行为完全保留。
2. 在 `SkillShell.__init__` 中懒加载 `compile_graph()`（可选，减少启动时间）。
3. 新增 `_run_rag_query()` 方法，在 `_run_command()` 中替换 free_agent 分支。
4. 不需要数据迁移，无持久化状态变更。

## Open Questions

- RAG graph 在 CLI 中是否也需要 `rerank_node`（依赖外部 reranker 服务）？当前 `rerank_node` 在无配置时会直接透传 context，应该是安全的。
- `session_messages` 的最大长度限制是否与 TUI 一致（还是需要更短）？待确认 LLM 的 context window 限制。
