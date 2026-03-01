## Why

在之前完成 `fix-indexing-integrity-and-chunking` 的修复后，系统的文本切分逻辑（Chunking）和数据结构抓取能力（Word/Excel）已经大幅完善。然而，用户在实际操作中抛入了大量包含重要商业或原型的文档，这些文档的格式是 `.pdf`。

由于系统中 `LocalFileConnector` 目前仅支持 `["*.md", "*.txt", "*.docx", "*.xlsx", "*.csv"]`，导致 RAG 系统的索引管道会直接**静默跳过（Skip）所有的 PDF 文件**。
PDF 是企业知识库中最主流、最刚需的文件格式。如果不支持 PDF 提取，系统在实际生产环境中将缺失海量上下文，因此亟需实现基于 PDF 的全文抓取，并将其接入到已经完善的 Markdown-aware 分块索引管线中。

## What Changes

本变更将在 `LocalFileConnector` 中引入 PDF 解析能力：
1. **追加受支持后缀**: 将 `*.pdf` 正式加入 `fetch_all` 的扫描匹配列表中。
2. **集成外部 PDF 处理库**: 引入 `PyMuPDF`（即 `fitz`）作为提取引擎，因其在抽取纯文本、处理排版乃至简单表格保留上拥有目前 Python 生态里最佳的性能和靠谱度。
3. **实现 `_read_pdf` 方法**: 提取 PDF 内含的纯文本，通过简单的换行符整理，使其能够尽最大可能兼容后续的 Markdown-aware hierarchical chunker（将其视作多段落的普通长文本处理）。

## Capabilities

### New Capabilities
- `pdf-extraction`: 引入使系统能够识别、读取和全量抽取 PDF 文件内纯文本的本地文件连接器 (Connector) 能力。

### Modified Capabilities
- `indexing-pipeline`: 修订索引流水线规范，将 `.pdf` 声明为一等支持（First-class citizen）的知识库输入源格式。

## Impact

**Affected Code/Files:**
- `src/kb_agent/connectors/local_file.py`: 需要增加 `_read_pdf` 函数并修改扫描 extension 列表。
- `pytest` 或其他测试依赖：需要加入相应的 PDF 格式的容错测试。

**Dependencies (package additions):**
- 需在项目依赖包管理（如 `requirements.txt` / `pyproject.toml`）中显式增加 `PyMuPDF`。
