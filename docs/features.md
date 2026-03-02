# KB Agent 项目业务逻辑梳理

本文档梳理了基于最新 `kb_agent` 源码的业务骨架，分为两个核心领域：**索引构建流水线 (Indexing Pipeline)** 和 **问答引擎流水线 (Query & RAG Engine)**。

## 1. 核心业务领域一：索引构建（Indexing Pipeline）

索引构建的目的是将未经处理的原始文件转化为机器和 LLM 都可快速检索的结构化信息（向量 + 知识图谱）。

### 核心类名
*   `cli.py (run_indexing)`:  整个本地全量索引和构建任务的主入口点。
*   `LocalFileConnector (kb_agent.connectors.local_file)`:  数据采集连接器。负责从指定的 `source_docs_path` 目录中递归获取所有的原始降价文件。
*   `Processor (kb_agent.processor)`:  文档核心处理引擎。
    *   将包含元数据的原始数据写入纯净的 Markdown 文件。
    *   调用大模型生成文件的摘要 (`LLMClient.generate_summary`)。
    *   调用向量工具写入数据库。
*   `VectorTool (kb_agent.tools.vector_tool)`:  封装了对 ChromaDB 的操作，负责持久化文本内容的 Embeddings。
*   `GraphBuilder (kb_agent.graph.graph_builder)`:  知识图谱构建引擎。负责通过正则扫描 MD 标记和特定的关系指令（如 `[JIRA-123]`, `Parent:`, `Clones:`），构建局部知识图谱，并输出为 `knowledge_graph.json`。

### 索引数据流向
1.  **数据采集**: `run_indexing` 调用 `LocalFileConnector.fetch_all()` 从 `source_docs` 本地目录获取所有原始文件。
2.  **内容加工与向量化**: 遍历每个文件将其传入 `Processor.process(doc)`：
    *   **步骤A**: 存储完整文件到 `index_path (<id>.md)`。
    *   **步骤B**: 让 LLM 根据完整内容生成摘要，并另存为 `<id>-summary.md`。
    *   **步骤C**: 使用 `VectorTool` 将摘要块和被截断的完整文本内容，附上元数据后，作为 Document 存入 Chroma 数据库（实现密集向量检索）。
    *   **步骤D**: 文件如果处理成功，原有的源文件将被迁移到 `archive_path` 以防二次处理。
3.  **图谱构建**: 随后，调用 `GraphBuilder.build_graph()` 解析索引库中的文本关系和依赖状态，更新节点状态，并在本地落地持久化拓扑关系。

---

## 2. 核心业务领域二：问答引擎（Agentic RAG）

为 TUI 等终端前端提供强大的，兼具图谱推理与知识库召回能力的交互会话接口。

### 核心类名
*   `KBAgentApp (kb_agent.tui)`:  基于 Textual 构建的终端用户界面应用，捕获用户文本输入。
*   `Engine (kb_agent.engine)`:  整个搜索、推理与作答系统的入口门面。
*   `LLMClient (kb_agent.llm)`:  大模型基座通信客户端，统一代理 OpenAI 或 Azure 等后台 API。
*   `kb_agent.agent.graph / nodes`:  基于 LangGraph 的 Agent 工作流控制器，用于解决复杂问题所需的多次搜索、调用等步骤流转。

### 问答数据流向
1.  **交互捕获**: 用户通过 `TUI` 界面输入自然语言 Query。
2.  **预解析拦截**:
    *   提交给 `Engine.answer_query()`。
    *   引擎会预先通过正则寻找 Query 中的网页 URL（若是 URL 内容抓取意图，直接委托 `WebConnector` 解析并进行本地直读摘要）。
3.  **模式分流**:
    *   **Normal 模式**: 仅开启聊天模式，不挂载任何检索上下文，直接委托 `LLMClient` 生成对话。随即将返回文本做 `Security.mask_sensitive_data` （脱敏拦截，比如消解信用卡号等）。
    *   **Knowledge Base 模式 (Agentic RAG)**:  将 Query、历史对话包装为 `initial_state` 掷出给 LangGraph `_graph.invoke()` 图机器。
4.  **智能推理与获取 (LangGraph)**:
    *   Agent 自己决策目前已知内容是否“足够(Is Sufficient)”。
    *   如不够，Agent 会生成查询短语，去调用 `VectorTool`（向量检索）和 `GraphTool`（图谱上下游关联检索）或者 `GrepTool`（文件精确检索），甚至进行文件通读以补充背景 (Context)。
    *   多轮自迭代，直到搜集到的数据足够支撑用户的请求。
5.  **归纳与反馈**: Agent 生成最终的 `final_answer`。经过安全拦截处理后，经回调流式输出或打印到控制台/TUI 页面中。
