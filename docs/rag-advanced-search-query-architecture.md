# RAG 检索意图架构演进与优化

在 RAG（Retrieval-Augmented Generation）Agent 的演进过程中，如何将用户的复杂自然语言提问转化为高效的底层搜索引擎参数，是一个核心痛点。本文档梳理了业界（以 2026 年大厂架构为标准）在解决“检索意图拆解”和“混合检索冲突”时的架构演进路径。

## 1. 痛点：自然语言与精确检索的冲突

当我们让 LLM 分解用户的复杂问题时，通常会得到自然语言形式的“子问题”（例如 `kb-agent 和 llmnote 的工具依赖项有什么不同？`）。这种形态的查询：

*   **对于 Vector Search（向量检索）**：表现良好，Embedding 模型能够捕捉句子的综合语义。
*   **对于 Grep Search（关键词/正则检索）**：表现灾难。由于长句中包含了主谓宾和标点符号，传统的关键词精确匹配引擎（如 Ripgrep）几乎无法在目标文档中找到完全匹配的长文本片段。

**混合检索（Hybrid Search）的退化**：
如果系统的 `hybrid_search` 仅仅接受一个单一的 `query(str)` 参数，并在内部同时派发给 Vector 和 Grep 引擎。那么由于 Grep 引擎召回率为 0，导致 RRF (Reciprocal Rank Fusion) 融合排序时只有向量引擎的数据。这使得昂贵的混合检索退化成了毫无意义的单边向量检索（甚至是二次重复检索）。

## 2. 业界标准架构：分离检索域（Retrieval Dispatch Layer）

现在的标准 RAG 高阶架构（如 Multi-Query/Multi-Vector 模式及闭源模型的内部实现），抛弃了让大模型单纯输出“自然语言查询词”的做法，而是采用了**参数结构化（Parameterized Tooling）**理念。

### 核心思想：把一把刀变成一套手术刀

```text
┌─────────────────────────────────────────────────────────────┐
│ 2026 年标准 RAG 检索分发层 (Retrieval Dispatch Layer)       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   USER: "kb-agent 和 llmnote 的工具依赖项有什么不同？"      │
│                            │                                │
│                            ▼                                │
│    ┌──────────────────────────────────────────┐             │
│    │        Query Analyzer (LLM Router)       │             │
│    │  (同时生成 semantic 和 keyword 两个维度) │             │
│    └──────────────────────────────────────────┘             │
│          /                               \                  │
│  "kb-agent 和 llmnote      ["kb-agent", "llmnote",          │
│   工具依赖的区别"                 "工具", "依赖"]           │
│         /                                 \                 │
│        ▼                                   ▼                │
│ ┌───────────────┐                  ┌───────────────┐        │
│ │ Vector Search │                  │  Grep Search  │        │
│ │  (用自然语言) │                  │ (用关键词数组) │       │
│ └───────────────┘                  └───────────────┘        │
│          \                                /                 │
│           ▼                              ▼                  │
│       ┌──────────────────────────────────────┐              │
│       │ RRF 混合融合排序 (Reciprocal Rank)   │              │
│       └──────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### 架构优势与实现方式

1. **分离检索域**：
   抛弃单一输入，为不同的检索技术提供定制化输入。
2. **工具 Schema 升级**：
   暴露给 LLM 的 Hybrid Search 工具签名从单参数升维双参数：
   ```python
   def hybrid_search(semantic_intent: str, exact_keywords: list[str] | str) -> str:
   ```
   *   `semantic_intent`: 供 Vector Search 使用，保留自然语言的语义和语境。
   *   `exact_keywords`: 供 Grep/BM25 使用，由 LLM 从用户请求中精准提取的实体名和专业术语（去除干扰词）。
3. **复合 Schema 解析**：
   在 `analyze_and_route` 节点，指导 LLM 不再只吐出一个字符串数组，而是输出结构化 JSON 对象。例如：
   ```json
   {
     "sub_questions": [
       {
          "semantic_intent": "kb-agent 依赖项差异",
          "search_keywords": "kb-agent llmnote dependency"
       }
     ]
   }
   ```

## 3. 防内卷：工具规划互斥策略 (Mutual Exclusion)

导致搜索效率低下的另一个元凶是**引擎工具重复调度**。

假设某次查询 LLM 倾向于彻底搜索，使得其路由分析得出建议使用：`["vector_search", "hybrid_search"]`。

如果在编排节点（Plan Node）缺乏约束，系统会：
1. 先跑一遍 `vector_search("query")`
2. 再跑一遍 `hybrid_search("query")`（其内部又包含了一遍完全相同参数的 `vector_search`）

**解决方案：计划级强压制**
在实际分派工具调用前增加硬性防重逻辑：
```python
suggested_tools = routing_plan.get("suggested_tools", [])

# 互斥清洗：如果决定使用能覆盖底层的混合搜索，那就剔除掉专门只跑一层的搜索
if "hybrid_search" in suggested_tools:
    suggested_tools = [t for t in suggested_tools if t not in ("vector_search", "grep_search")]
```

## 4. 总结与优化路线

针对 RAG Agent 的搜索优化可以简单划分为两个阶段：

*   **快修版（防御性编程）**：专注于去除自身内部消耗（解决相同引擎重复查询问题）。依靠 Python 侧过滤（如上述方案3），立即见效，无需改动复杂 Prompt。
*   **结构改造版（大厂架构）**：重塑查询意图分解。对 `hybrid_search` 方法进行双维度入参升级，改变 `analyze_and_route` 的解析数据结构，实现检索维度的最佳耦合，全面彻底地解决关键字召回降级的问题。
