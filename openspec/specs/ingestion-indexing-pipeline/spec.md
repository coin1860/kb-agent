---
title: Indexing Pipeline
domain: ingestion
---

# indexing-pipeline Specification

## Purpose
TBD - created by archiving change system-baseline-docs. Update Purpose after archive.
## Requirements
### Requirement: Process raw markdown files into indexable formats
The system SHALL ingest markdown files from a local source directory, save a standardized copy, and generate a concise LLM summary for each file.

#### Scenario: User runs kb-agent index on valid local directory
- **WHEN** the user runs the `kb-agent index` command
- **THEN** the system iterates through all files in the configured `source_docs_path`
- **AND** the system generates an LLM summary for each file
- **AND** the system saves both the full content and the summary to the `index_path`

### Requirement: Vectorize document content
The system SHALL chunk and embed both the full content (truncated) and the summary of a document into ChromaDB to enable semantic search.

#### Scenario: Document is processed by VectorTool
- **WHEN** a document and its generated summary are ready for indexing
- **THEN** the system adds the summary to ChromaDB with type `summary`
- **AND** the system adds the truncated full content to ChromaDB with type `full`

### Requirement: Archive processed documents
The system SHALL move successfully processed source documents out of the input directory to prevent duplicate processing on subsequent runs.

#### Scenario: File completes indexing successfully
- **WHEN** a document has been successfully summary-generated and vectorized
- **THEN** the system moves the physical file from `source_docs_path` to `archive_path`

### Requirement: Build Semantic Knowledge Graph
The system SHALL parse explicit relationships (like Jira IDs and local markdown links) from the documents and construct a directed Knowledge Graph.

#### Scenario: GraphBuilder scans the index
- **WHEN** the indexing pipeline finishes processing documents
- **THEN** the `GraphBuilder` parses the files in the `index_path` for `[JIRA-123]` tags and `[Link](file)` patterns
- **AND** the system outputs a `knowledge_graph.json` file representing the graph nodes and edges
 
 ### Requirement: Local File Scan Includes PDF
 The `LocalFileConnector` must treat `.pdf` as a natively supported document type alongside markdown, text, word, and spreadsheets during local directory scanning.
 
 #### Scenario: User queries for files in local directory
 - **WHEN** the `fetch_all` or `fetch_data` method is invoked
 - **THEN** files ending with `.pdf` (case-insensitive) should be discovered and processed.
 
 ### Requirement: Large PDF Text Extraction with Pagination Structure
 The system must be capable of extracting the raw text content from PDF documents, specifically handling large files natively without memory corruption, outputting a structure compatible with downstream Markdown Chunkers.
 
 #### Scenario: A Large PDF file is processed
 - **WHEN** a `.pdf` file is passed to `_read_file`
 - **THEN** it must utilize PyMuPDF (fitz) to extract text safely.
 - **AND** it must inject explicit Structural Metadata (e.g. `## Page N`) between text segments so that the `MarkdownAwareChunker` correctly separates large PDF files into bite-sized indexable chunks using standard Header boundaries.
 
 ### Requirement: Robust PDF Processing Tests
 The new functionality must be backed by explicit testing bounds.
 
 #### Scenario: Running test suite
 - **WHEN** `pytest tests/` is invoked
 - **THEN** it must execute a test isolating `LocalFileConnector` PDF reading behavior, verifying that generated markdown accurately represents the injected pagination.
 
 ### Requirement: Full Recursive DOCX Extraction
 Connector 组件 SHALL 提供针对 Word 文档深度全量抽取的能力：即摒弃目前只能提取顶层段落的缺陷，需要逐级检索其全部可见的文本范围，将结构化内容降维为纯文本或者 Markdown 字符串。
 
 #### Scenario: DOCX parser detects tables and recursively extracts texts
 - **WHEN** 解析文件流，遇到 `Table` 类型时
 - **THEN** Python-docx 不应忽略对象，而必须进入 `iter_inner_content()` 把表格的结构或正文追加抓取出来
 - **AND** 其他各种嵌套 `Paragraph` 对象也必须在生成的长文中体现
 - **AND** 对超过安全长度的长表头不引起段内严重死循环或者抛出严重崩溃
 
 ### Requirement: Full Volume Semantic Embedding
 在建立知识索引的插入环节 (Vector Indexing)，VectorTool SHALL 接收分段处理后的整个文本内容向量阵列插入。
 
 #### Scenario: No text gets truncated explicitly by length anymore
 - **WHEN** `Processor` 执行将全文投入 ChromaDB 的操作
 - **THEN** 不可硬编码类似 `[:2000]` 的丢包限制
 - **AND** 系统根据上一层级分发的每个 Chunk 单独建立向量条目和标签插入数据库中
 - **AND** Chunk条目在保留 `type="full"` 或者其他自定义类型时需要追加明确的 `parent_id` 相关识别项。
 
 ### Requirement: Limited Deep Rows Expansion inside Sheet parsing
 若用户给系统投喂几万行的超长表，系统 SHALL 避免由于转换生成巨型的 Markdown Text 造成后续处理溢出。
 
 #### Scenario: Spreadsheet cuts large row counts gracefully
 - **WHEN** 对于一个 `Sheet` 执行转 Markdown 时，内部读取发现其超过 1000 行
 - **THEN** Pandas Engine 应加上受限约束 (e.g. `nrows=1000`) 从而截去超出部分
 - **AND** 末尾加上诸如 `[TRUNCATED: (Actual) more rows]` 或类似警示语，用以让检索该源时的 LLM 或终端知道后续没有显示

