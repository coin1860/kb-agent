## Context

当前 Agentic RAG 管线有 5 个节点（`analyze_and_route → plan → tool_exec → grade_evidence → synthesize`），每次查询固定 4 次 LLM 调用。`analyze_and_route` 已经做了查询意图分类（exact/conceptual/relational/file_discovery），但分类结果**仅用于指导工具选择**，不影响管线路径。`grade_evidence` 节点对所有 context items 做 LLM 批量打分，即使证据质量很明显也无法跳过。

### 现有架构要素

| 组件 | 文件 | 关键局限 |
|------|------|----------|
| analyze_and_route | `agent/nodes.py:225` | 只输出 query_type，无复杂度分级 |
| graph 拓扑 | `agent/graph.py` | `tool_exec → grade_evidence` 是硬边，无法跳过 |
| grade_evidence | `agent/nodes.py:633` | 仅 local_file_qa 有 auto-approve，其他场景全走 LLM |
| AgentState | `agent/state.py` | routing_plan 已有 dict 字段，可复用存 complexity |

## Goals / Non-Goals

**Goals:**
- G1: 简单查询（单意图、无 sub-questions）跳过 `grade_evidence`，LLM 调用从 4 次降至 3 次
- G2: 闲聊/问候类查询跳过 `plan + tool_exec + grade_evidence`，LLM 调用从 4 次降至 1 次
- G3: 复杂查询在进入 LLM grading 前，用规则预筛过滤高置信 context items，减少 grading token 消耗
- G4: 保持 `Engine.answer_query()` 对外接口不变

**Non-Goals:**
- NG1: 不做 grade + synthesize 合并节点（P2 优先级，留给后续变更）
- NG2: 不做真并行 speculative synthesis（P3 优先级，复杂度高）
- NG3: 不新增 embedding 预筛（需要额外 embedding 调用，本次只用已有 metadata）
- NG4: 不改变 tool 执行逻辑和工具集

## Decisions

### D1: analyze_and_route 输出扩展 — 新增 complexity 字段

**选择**：在 `analyze_and_route` 的 LLM prompt 中新增 `complexity` 输出字段，无额外 LLM 调用开销。

**输出 schema 变更**：
```json
{
  "query_type": "exact | conceptual | relational | file_discovery | chitchat",
  "complexity": "simple | complex | chitchat",
  "sub_questions": [],
  "suggested_tools": ["vector_search"],
  "grep_keywords": []
}
```

**分类规则**（写入 prompt 指导 LLM）：
| complexity | 条件 | 示例 |
|---|---|---|
| `chitchat` | 问候、闲聊、非知识库查询 | "你好"、"谢谢"、"你是谁" |
| `simple` | 单一意图、无需分解 | "VectorTool 是什么"、"PROJ-123 详情" |
| `complex` | 多意图、需要分解或多轮检索 | "比较索引管线和查询引擎的架构差异" |

**存储**：`complexity` 存入 `routing_plan` dict（`state["routing_plan"]["complexity"]`），无需新增 AgentState 字段。

**替代方案**：用 regex/关键词匹配做本地分类，不走 LLM。
**否决原因**：`analyze_and_route` 已经在做 LLM 调用，多输出一个字段几乎零成本；本地规则难以准确区分简单概念查询和复杂多意图查询。

---

### D2: Graph 拓扑新增条件边 — 三级路由

**选择**：将 `analyze_and_route` 后和 `tool_exec` 后各增加条件边。

**新拓扑**：
```
START → analyze_and_route
              │
         ┌────┴────────────────────┐
         │ chitchat                │ simple/complex
         ▼                        ▼
    synthesize               plan → tool_exec
                                      │
                              ┌───────┴───────┐
                              │ simple        │ complex
                              ▼               ▼
                         synthesize     grade_evidence
                                              │
                                        (existing routing)
                                              ▼
                                         synthesize
```

**条件函数**：

```python
def _route_after_analyze(state):
    complexity = state.get("routing_plan", {}).get("complexity", "complex")
    if complexity == "chitchat":
        return "synthesize"
    return "plan"

def _route_after_tool_exec(state):
    complexity = state.get("routing_plan", {}).get("complexity", "complex")
    if complexity == "simple":
        return "synthesize"
    return "grade_evidence"
```

**替代方案**：只在 `tool_exec` 后加条件边，不处理 chitchat。
**否决原因**：chitchat 短路是最高收益优化（省 3 次 LLM 调用），实现代价极低（1 个条件边），没有理由不做。

---

### D3: grade_evidence 规则预筛 — 零 LLM 过滤

**选择**：在 `grade_evidence_node` 的 LLM 调用前增加规则检查层，命中任一规则则跳过 LLM 打分。

**规则引擎**（按优先级排列）：

| # | 规则 | 条件 | 动作 |
|---|------|------|------|
| 1 | local_file_qa 结果 | `tool_history[-1].tool == "local_file_qa"` | 自动 GENERATE（**已有**） |
| 2 | read_file 结果 | 所有 pending tools 都是 `read_file` | 自动 GENERATE（用户明确要读文件） |
| 3 | 少量 context | `len(context_items) <= 2` | 自动 GENERATE（不值得花 LLM 评估） |
| 4 | vector 高分命中 | context 来自 vector_search 且 metadata 中 score ≥ 0.8 | 自动 GENERATE |
| 5 | 以上均不满足 | — | 走 LLM grading（现有逻辑） |

**实现位置**：在 `grade_evidence_node()` 函数开头，现有 local_file_qa auto-approve 逻辑后面扩展。

```python
def grade_evidence_node(state):
    # ... existing local_file_qa auto-approve (rule 1) ...
    
    # Rule 2: read_file results auto-approve
    if all(t.get("tool") == "read_file" for t in tool_history[-len(pending):]):
        return auto_generate(...)
    
    # Rule 3: few context items
    if len(context_items) <= 2:
        return auto_generate(...)
    
    # Rule 4: high vector scores (parse from context metadata)
    if _all_high_vector_scores(context_items, threshold=0.8):
        return auto_generate(...)
    
    # ... existing LLM grading logic ...
```

**替代方案**：用小模型做 grading 代替规则。
**否决原因**：规则覆盖最常见场景，零延迟；小模型仍需 LLM 调用，且需要额外配置模型端点。规则不够时再考虑小模型。

---

### D4: chitchat synthesize 行为

**选择**：当 `query_type == "chitchat"` 时，`synthesize_node` 跳过 "ONLY from context" 约束，转为普通对话模式应答。

**实现**：在 synthesize_node 中检测：
```python
if state.get("routing_plan", {}).get("complexity") == "chitchat":
    # Use conversation history only, no context needed
    # Respond naturally without the "only from evidence" constraint
```

**替代方案**：chitchat 走 `Engine.answer_query(mode="normal")` 路径。
**否决原因**：engine 层面已经根据 UI 模式分流了；在 graph 内部短路更简单，不需要改 engine 逻辑。

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM 对 complexity 分类不准确，simple 误判为 chitchat | 简单知识库问题被当闲聊回答 | prompt 中明确强调：只有纯社交性质的才是 chitchat，任何涉及知识内容的都不是 |
| 规则 3（≤2 条 context 自动通过）可能放过低质量证据 | synthesize 基于垃圾 context 生成答案 | synthesize 已有 "only from evidence" 约束，低质量 context 会被回答为"未找到信息" |
| simple 路径跳过 grading，无法发现需要重检索的情况 | 答案质量可能受影响 | simple 查询通常单轮即可解决；如果用户反馈不佳可手动重试 |
| 规则 4 依赖 context 文本中包含 vector score metadata | vector_search 结果格式变化会导致规则失效 | tool_node 已有统一的 citation 格式化逻辑，score 可以从 tool_history 中获取更可靠 |

## Resolved Questions

1. **complexity 阈值调优** → **通过 .env 配置**。规则预筛阈值通过环境变量配置，支持动态调优：
   - `KB_AGENT_VECTOR_SCORE_THRESHOLD`：vector 高分自动通过阈值（默认 `0.8`）
   - `KB_AGENT_AUTO_APPROVE_MAX_ITEMS`：少量 context 自动通过阈值（默认 `2`）

2. **指标收集** → **是，记录 fast-path hit 事件**。在每个快路径命中时通过 `log_audit("fast_path_hit", {...})` 记录，包含：
   - `path_type`: `chitchat` / `simple_skip_grading` / `rule_auto_approve`
   - `rule_name`: 命中的具体规则（如 `read_file`、`few_context`、`high_vector_score`）
   - `query`: 原始查询（用于后续分析命中率和准确率）
