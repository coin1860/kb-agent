# semantic-chunking Specification

## Purpose
文本分割与分段向量化能力，能够基于 Markdown 层级对长文本提取高质量的 Semantic Chunks。它极大提高了 RAG 检索阶段定位具体信息段落的能力并增强了 LLM 的 Map-Reduce 理解上下文。

## Requirements

### Requirement: Markdown-Aware Hierarchical Chunking
系统 SHALL 优先依赖 Markdown 的 `H1` 到 `H3` (`#`, `##`, `###`) 标签进行分段切割，这构成了 Level-1 的 Semantic Unit。如果某段文字本身超过限定大小而没有 Header，则继续依赖 Level-2 (按 `\n\n` 切割) 和 Level-3 (按标点滑窗切割)。 

#### Scenario: Document is properly split by Headings
- **WHEN** 给入一份拥有标题的 Markdown 并启用 Chunker 时
- **THEN** 提取出的所有的 Chunks 分界线都应该按照给定的最高权重 Header 进行分割
- **AND** Chunk 原文需要自带该 Header
- **AND** Chunk 设置大小需要控制在阈值（如约 4000 个字符的硬界限以下）

#### Scenario: Long paragraphs split with overlap
- **WHEN** 分析到超过 4000 个字符长度的连续大段正文（无 Header 分割）
- **THEN** 系统将其通过换行符切为不同 Chunks，每个最大不超过 1000 Tokens
- **AND** 系统在临近块的交界处需带上适量的 Overlap (100-200 Tokens)

### Requirement: Granular Chunk Metadata
为每个分割出来的 Chunk 都 SHALL 提供富文本语义和分发跟踪信息的 Metadata。

#### Scenario: Injecting Metadata to Chroma Vectors
- **WHEN** Chunker 输出 `Document` 或存入 ChromaDB 时
- **THEN** 返回的 `metadata` 内必须显式包含 `doc_id` 表示母文件路径或主键
- **AND** 必须包含 `chunk_index` 来标记所在序列
- **AND** 应该尝试抓取最近的一个 `section_title` 传递其中（以备后续 Parent-Document Retrieval 召回扩展）

### Requirement: Map-Reduce Summary Generation
若文本篇幅过长，不能够以一轮单路传入给 LLM 生成 Summary，应当 SHALL 发起分块处理再规约。

#### Scenario: Executing global summary over massive document
- **WHEN** 输入生成摘要的文档长度 > 4000 字符
- **THEN** 将文档应用 Chunk 拆分，每个不超过限制
- **AND**  逐个发向 LLM 生成该分段的独立 Sub-Summary
- **AND**  系统使用最后一个 Reduce Calling 讲所有的 Sub-Summary 总结聚合起来，并且生成全局摘要
