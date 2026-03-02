# Agent RAG 深度探索 — 续篇

基于你的反馈，继续深入研究以下几个新问题。

---

## 1. `analyze_and_route` 的困境

### 你描述的问题

> LLM 经常将复杂问题分类为 chitchat 或 simple，导致性能更差。

这是一个典型的 **分类器精度 vs. 架构收益** 的权衡。分类器（用 LLM 做 intent classification）本身就不太靠谱，特别是当：
- 模型较小或者使用本地模型时
- 中文/混合语言输入时分类边界模糊
- "简单"和"复杂"本身是主观判断

### 更好的替代方案

与其用 LLM 做一个不靠谱的预分类，不如用**规则引导 + 统一 pipeline**：

```
┌──────────────────────────────────────────────────┐
│              UNIVERSAL PIPELINE                   │
│                                                   │
│  Any Query                                        │
│      │                                            │
│  ┌───▼───────────────────┐                        │
│  │  Rule-based Pre-check │  ← 不走 LLM            │
│  │  1. 有 URL? → web_fetch                        │
│  │  2. 有 PROJ-xxx? → jira_fetch                  │
│  │  3. 纯打招呼? → regex 检测 → chitchat          │
│  │  4. 其他 → vector_search (DEFAULT)             │
│  └───┬───────────────────┘                        │
│      ▼                                            │
│  plan_node (只在第2轮+由LLM决定retry策略)          │
│      ▼                                            │
│  tool_exec → grade → synthesize 或 retry          │
└──────────────────────────────────────────────────┘
```

**关键改变**：
- **第一次搜索不走 LLM planner** — 直接用规则 + [vector_search](file:///Users/shaneshou/Dev/kb-agent/src/kb_agent/agent/tools.py#121-136)
- **LLM planner 只在 retry 轮使用** — 当第一轮证据不足时，才让 LLM 决定换什么策略
- **chitchat 用简单 regex 判断** — `^(hi|hello|你好|谢谢|thanks)$` 之类，不用 LLM

这样避免了分类错误导致的性能下降，同时保留了智能 retry 的能力。

---

## 2. ChromaDB 文件路径问题 + `doc_id` 命名 Bug

### 完整的文件流转路径

追踪代码后，完整链路是：

```
source/report.docx                    ← 原始文件
      │
      ▼  (LocalFileConnector.fetch_all)
doc = {"id": "report.docx", ...}      ← doc_id = file_path.name
      │
      ▼  (Processor.process)
index/report.docx.md                  ← full_path = docs_path / f"{doc_id}.md"
index/report.docx-summary.md          ← summary_path
      │
      ▼  (ChromaDB metadata)
{
  "file_path": "index/report.docx.md",      ← ✅ 指向 index，不指向 source
  "related_file": "index/report.docx.md",   ← ✅ 同上
  "type": "chunk" | "summary"
}
      │
      ▼  (cli.py archive)
source/report.docx → archive/report.docx    ← 原文件被归档
```

### 问题确认

#### Bug 1: `.doc.md` 命名问题

在 [local_file.py:47](file:///Users/shaneshou/Dev/kb-agent/src/kb_agent/connectors/local_file.py#L47):
```python
"id": file_path.name,   # → "report.docx"
```

在 [processor.py:32](file:///Users/shaneshou/Dev/kb-agent/src/kb_agent/processor.py#L32):
```python
full_path = self.docs_path / f"{doc_id}.md"  # → "index/report.docx.md"  ❌
```

**应该是** `index/report.md`。

**修复方案**：在 `Processor.process` 或 [LocalFileConnector](file:///Users/shaneshou/Dev/kb-agent/src/kb_agent/connectors/local_file.py#7-161) 中，将 `doc_id` 改为 stem（无扩展名）：

```python
# 方案 A: 在 Processor.process 中
doc_id = Path(data.get("id")).stem   # "report.docx" → "report"

# 方案 B: 在 LocalFileConnector 中
"id": file_path.stem,               # "report.docx" → "report"
```

> [!WARNING]
> **注意**：如果已有索引是用旧命名（`report.docx.md`）建的，改了之后需要重新 index，否则 ChromaDB 里的旧 ID 和新 ID 不匹配。

#### 关于文件路径指向

好消息是 ChromaDB 里的 `related_file` 和 [file_path](file:///Users/shaneshou/Dev/kb-agent/src/kb_agent/agent/nodes.py#488-509) 已经指向 **index 目录**（不是 source），因为 [Processor](file:///Users/shaneshou/Dev/kb-agent/src/kb_agent/processor.py#7-99) 初始化时 `docs_path = settings.index_path`。所以：
- [read_file](file:///Users/shaneshou/Dev/kb-agent/src/kb_agent/tools/file_tool.py#17-44) 应该能找到 index 下的文件 ✅  
- [FileTool](file:///Users/shaneshou/Dev/kb-agent/src/kb_agent/tools/file_tool.py#6-44) 已经在 `allowed_paths` 里包含了 `index_path` ✅

**但**：如果 LLM 从 chunk 里提取的 path 不正确（如旧数据里还有 source 路径），就会读取失败。

---

## 3. AI 总结内容过少 — 根因分析

### 症状

> 即使命中返回了几千个 char，最后 AI 总结的内容还是很少。

### 根因分析

在 [synthesize_node](file:///Users/shaneshou/Dev/kb-agent/src/kb_agent/agent/nodes.py#842-966) 中找到了 **4 个互相叠加的原因**：

#### 原因 1: Prompt 措辞鼓励简短

```python
# SYNTHESIZE_SYSTEM 中的关键措辞:
"5. Be precise, professional, and well-structured.\n"
```

"Be precise" 对 LLM 来说意味着 **简洁、不啰嗦**。特别是小模型或中文场景，这会导致它把几千字的证据浓缩成 2-3 句话。

#### 原因 2: Evidence 内容被截断

在 [grade_evidence_node](file:///Users/shaneshou/Dev/kb-agent/src/kb_agent/agent/nodes.py#672-813) (line 748-749):
```python
# 每个 context item 限制 2000 chars 给 grader
truncated_item = item[:2000] + "... [truncated]" if len(item) > 2000 else item
```

**但在 [synthesize_node](file:///Users/shaneshou/Dev/kb-agent/src/kb_agent/agent/nodes.py#842-966) 里没有这个限制** — context items 是完整传入的。

那问题可能在哪呢？在 [tool_node](file:///Users/shaneshou/Dev/kb-agent/src/kb_agent/agent/nodes.py#515-650) (line 596-627)，[read_file](file:///Users/shaneshou/Dev/kb-agent/src/kb_agent/tools/file_tool.py#17-44) 结果被限制在 8000 chars：
```python
# tools.py read_file
if len(content) > 8000:
    return content[:8000] + "\n... (truncated)"
```

8000 chars 理论上足够了。但是 **vector_search 的 chunk 本身只有 ~800 chars**（`chunk_max_chars = 800`），所以 5 个 chunk 加起来只有 ~4000 chars。这已经是全部证据了。

#### 原因 3: 模型行为 — temperature 太低

```python
# nodes.py _build_llm()
return ChatOpenAI(
    ...
    temperature=0.2,   # ← 非常保守，倾向于最"安全"的回答
)
```

`temperature=0.2` + "Be precise" prompt = **极度保守的输出**。模型会倾向于写最少量的文字来确保正确性。

#### 原因 4: 没有明确要求详细回答

对比其他 RAG 系统的 synthesize prompt，通常会包含这类指令：

```
"Provide a thorough, detailed answer that covers all aspects of the evidence."
"Include specific details, data points, and quotes from the evidence."
"Structure your response with headers and bullet points for readability."
```

当前 prompt 缺少这种"鼓励详尽"的指令。

### 建议修改

```python
SYNTHESIZE_SYSTEM = (
    "You are a helpful knowledge base assistant. Answer the user's question "
    "based on the provided context and conversation history.\n\n"
    "RULES:\n"
    "1. **Be thorough**: Extract ALL relevant details, data points, and specific "
    "   information from the evidence. Do NOT summarize away important details.\n"
    "2. If the evidence contains structured data (tables, lists, technical specs), "
    "   reproduce them in your answer, not just paraphrase.\n"
    "3. Structure your response using headers (##), bullet points, and formatting "
    "   for readability. Long, well-structured answers are PREFERRED over short ones.\n"
    "4. If the retrieved context is completely empty, respond with: "
    "   'I couldn't find relevant information in the knowledge base.'\n"
    "5. **CITATIONS**: Cite sources using [1], [2] etc.\n"
    "6. You MAY supplement with your own knowledge, but clearly mark assumptions.\n"
)
```

关键变化：
- ~~"Be precise"~~ → **"Be thorough"**
- 新增 "Do NOT summarize away important details"
- 新增 "Long, well-structured answers are PREFERRED over short ones"
- 新增 reproduce structured data 的要求

---

## 改进优先级矩阵（更新）

| 优先级 | 改进项 | 影响面 | 复杂度 |
|--------|--------|--------|--------|
| 🔴 P0 | 修改 synthesize prompt — "Be thorough" | 直接改善输出质量 | **极低** |
| 🔴 P0 | 错误结果不进 context | 消除错误答案 | 低 |
| 🟠 P1 | 修复 `doc_id` 命名 bug（.doc.md → .md） | 修复文件路径 | 低（需重新 index） |
| 🟠 P1 | 第一轮默认 [vector_search](file:///Users/shaneshou/Dev/kb-agent/src/kb_agent/agent/tools.py#121-136) + 规则路由（不走 LLM planner） | 提升首次命中率 | 中 |
| 🟡 P2 | [read_file](file:///Users/shaneshou/Dev/kb-agent/src/kb_agent/tools/file_tool.py#17-44) 支持行范围 + REFINE 轮自动 follow-up | 获取更多上下文 | 中 |
| 🟢 P3 | 合并/降级 [local_file_qa](file:///Users/shaneshou/Dev/kb-agent/src/kb_agent/agent/tools.py#229-244) | 减少工具混乱 | 低 |
