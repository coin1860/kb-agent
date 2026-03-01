## Context

目前的 indexing pipeline 非常薄弱且存在大量数据丢失，原因包括：
1. **Word 文档数据丢失**：`_read_docx` 的实现只提取直接 `paragraphs` 子节点，丢失了嵌套结构（如表格中的文字）的内容。对于包含大量需求和原型的技术文档来说，这会导致超过 40% 的关键内容丢失。
2. **文本暴力截断**：长文档在建立全文索引时硬编码被截断至前 2000 个字符；摘要也被截断到了 4000 个字符。文档后续的内容被完全忽略，导致长尾召回率为零。
3. **缺乏 Chunking 和语义关联**：检索过程缺乏精准的文本块级别（chunk）的分页和上下文（滑窗机制）处理。目前在 ChromaDB 里只有粗粒度的 `full` 和 `summary` 标签，两者孤立。

## Goals / Non-Goals

**Goals:**
1. 完整地提取包括段落和表格内的所有 Word（DOCX）数据。
2. 将大型数据源切割为合理的语义段落（Chunks），支持层级的 Markdown 标题感知切割。
3. 建立 Map-Reduce 分析模式来生成超大文档的高质量摘要。
4. 增强 Excel (`xlsx`, `csv`) 加载机制，使其支持行内分页和多个 sheets。

**Non-Goals:**
1. 添加直接对 PDF 类型文档的提取能力（预留接口或考虑以后支持）。
2. 从头重构整体 RAG 工作流的架构（本变更主要改进数据摄取和索引逻辑）。
3. 设计 Parent-Child 融合召回器（本次先建立相关的 Metadata 基础，真正的检索层增强视日后情况迭代）。

## Decisions

### 1. `LocalFileConnector._read_docx` 全级递归解析
利用 `python-docx` 的 `iter_inner_content()` 方法，按顺序捕获 `Paragraph` 对象和 `Table` 对象。
对于 `Table`，需递归遍历每个 cell 中的 `iter_inner_content()` 或者直接提其文字内容，尽量将其渲染为 Markdown 上的简单 `| table |` 或者结构化段落，以此避免漏数据。

### 2. 引入 Markdown-aware Hierarchical Chunker
与其依赖简单的基于字符长度的文本切分器，我们为本知识引擎编写一个能够感知 Markdown 结构的 Chunker：
- **Level 1**：基于 Header (`#`, `##`, `###`) 做文档的一级切断，把每一个 Section 视作独立单元。
- **Level 2**：对字数超过限制大小（如 4000 个字符）的巨型 Section，进一步通过 `\n\n` 进行段落切割。
- **Level 3**：仅当单段也无法满足时（极少出现），做按句号划分带重叠率的滑窗切割（如大小 1000 字符，重叠 200）。

所有 Chunks 都将自动带上属于其上的 Metadata（如 `section_title`, `doc_id`, `chunk_index`）。

### 3. 基于块分布式的 Map-Reduce Summary 生成
大文档摘要逻辑不再只取前 4000 字，取而代之的是：
- 将全文档按前文的 Markdown Chunks 序列化输入。
- 长文分块分别交由小 Map Call（生成 Chunk 的局部理解）。
- 最后聚合各局部的总结并发给 Reduce Call 生成整篇文章的大总结（Global Summary）。

### 4. Excel 多 Sheet 转 Markdown 和截断限制
- `pd.read_excel` 需迭代处理文件中所有具有内容的 Sheets。
- 一个表过长会爆显存且污染最终检索质量，我们在读取时引入 `nrows=1000`（或相似安全范围）限制，并抛出 `[TRUNCATED: N more rows]` 的明确告知。

## Risks / Trade-offs

1. **时间和 Token 成本激增**：将文件逐个分段发请求做局部 Summary 再做整体汇总的耗时和调用频次远大于之前的一次性截断请求，存在可能的 API Rate Limit 风险。
2. **ChromaDB 结构升级导致的清理风险**：原先的记录没有 Chunk 分段体系，本次升级之后，为了检索效果最佳，用户需要去清理之前的旧 Index 重新建索。
3. **表格转 Markdown 会极其臃肿**：将具有高复杂度的多维 Word 表格塞进拉平后的纯文本，这部分仍会有部分阅读难度。
