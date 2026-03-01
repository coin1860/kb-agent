## Why

当前 indexing pipeline 存在 **多层级、多环节的知识丢失** 问题，导致 RAG 系统的检索召回率和摘要质量远低于可用水平。问题覆盖了从文件读取、内容处理到向量存储的整个链路。

### 问题 1: Word 文档提取严重不完整

`LocalFileConnector._read_docx` 使用 `doc.paragraphs` 遍历文档，这是 `python-docx` 的一个已知局限 — **`paragraphs` 属性只返回文档 body 中的顶级段落元素，完全跳过表格（Tables）、文本框（Text Boxes）和页眉页脚（Headers/Footers）中的内容**。

对于企业级的 Word 文档（通常大量使用表格来组织数据、需求矩阵、会议记录等），这意味着 **40-70% 的文档内容在源头就被丢弃**。用户实测 5MB 的 Word 文档，转换出的 markdown 只有原文档的一小部分，且 summary 也只是基于这部分残缺内容生成的。

`python-docx` 的 `Document` 类提供了 `iter_inner_content()` 方法可以按文档顺序遍历段落和表格，而表格的每个 cell 也是一个 `BlockItemContainer`，支持递归遍历。当前代码完全没有利用这些能力。

### 问题 2: 多重硬编码截断导致知识断带

即使 Connector 成功读取了文件全文，后续处理环节也会暴力丢弃绝大部分内容：

- **摘要生成截断** (`llm.py:42`): `content[:4000]` — 只看了文档的前 ~1000 个中文字（约 1-2 页），后面所有内容被直接忽略。对于一个 50 页的文档，Summary 本质上只是"前言摘要"。
- **全文索引截断** (`processor.py:70`): `full_content[:2000]` — 更激进，只有前 ~500 个中文字被存入 ChromaDB 做向量检索。一个 10 万字的文档，98% 的内容完全不可搜索。

### 问题 3: 完全没有文本分割（Chunking）机制

当前系统对每个文档只在 ChromaDB 中生成 **2 条记录**（1 个 summary + 1 个截断全文），而不是将文档切分成多个语义段落（chunks）分别 embed。这导致：

- **检索粗糙**: embedding 代表的是整个截断文档的"平均语义"，无法精确匹配具体段落。
- **无法返回精准上下文**: 用户查询时得到的是一大块模糊内容，而非精确命中的段落。
- **无法利用 overlap**: 段落边界处的语义会丢失。

### 问题 4: Summary ↔ Chunk 关系断裂

ChromaDB 中 summary 和全文条目的 metadata 都包含 `related_file` 字段，但 `VectorTool.search()` 和 `query()` 从未利用该字段进行关联查询。搜索到 summary 无法获取相关原文 chunks，搜索到某个 chunk 也无法获取该文档的全局摘要。两者形成了"两张皮"。

### 问题 5: Excel 处理不完善

`_read_spreadsheet` 只读取 Excel 文件的默认第一个 sheet、不限制行数。大型 Excel（数万行）转成 markdown table 后会产生巨大的字符串，随后又被截断处理环节丢弃。

### 问题 6: PDF 完全不支持

当前支持的文件格式仅有 `md, txt, docx, xlsx, csv`，不包含 PDF。PDF 是企业知识库中最常见的文档格式之一。（注：PDF 支持作为 P1 优先级，不在本次变更的核心范围内，但本次重构应为其预留扩展点。

## What Changes

本次变更聚焦 **P0 级别** 的两个核心修复，同时为后续 P1/P2 改进打好架构基础：

### 变更 A: 修复 Word 文档完整提取

重写 `LocalFileConnector._read_docx`，使用 `doc.iter_inner_content()` 按文档顺序遍历所有块级元素（段落和表格），并递归处理表格中每个 cell 的内容。输出的 markdown 应保留文档结构：
- 段落 → markdown 文本段落
- 表格 → markdown table 格式
- 保留标题层级（利用 paragraph style 中的 Heading 信息）

### 变更 B: 引入 Markdown-Aware 层级分段（Semantic Chunking）

在 `Processor` 层引入 **Markdown 感知的层级文本分割**，替代现有的暴力截断。由于所有内容进入 Processor 前已被 Connector 转为 markdown，文档的逻辑结构天然由 `#`/`##`/`###` 标题标记，应优先利用这种结构进行语义完整的切分：

**分割优先级（从高到低）：**
1. **主分割 — Markdown Header 切分**: 按 `#`, `##`, `###` 标题切分，每个 section 成为独立 chunk，保留标题作为 chunk 的语义标签
2. **Fallback — 段落切分**: 如果某个 section 超过 4000 字符，按 `\n\n`（段落边界）继续切分
3. **最终兜底 — 句子滑窗切分**: 如果某个段落仍超过 4000 字符（极端情况），按句号/换行做滑窗切分 + overlap

**存储策略：**
- 每个 chunk 独立写入 ChromaDB，携带结构化 metadata（`doc_id`, `chunk_index`, `total_chunks`, `section_title`, `header_level`）
- 废弃 `processor.py` 中的 `full_content[:2000]` 和 `llm.py` 中的 `content[:4000]` 截断逻辑
- 无需引入外部 text-splitting 库，自研 Markdown 感知分割器即可（正则 `^#{1,6}\s` 识别切分点）

### 变更 C: 改进摘要生成策略

对大文件采用 Map-Reduce 摘要策略：
- 小文件（< 4000 字符）：直接生成摘要（现有逻辑）
- 大文件（≥ 4000 字符）：分段生成子摘要 → 汇总生成全局摘要
- 确保文档的"全貌"被 summary 覆盖，而不仅仅是"前言"

### 变更 D: 增强 Excel 读取

- 支持多 Sheet 读取
- 对行数设置上限（默认 1000 行/sheet），超出部分标注 `[TRUNCATED: N more rows]`
- 每个 sheet 作为独立章节输出

## Capabilities

### New Capabilities
- `semantic-chunking`: 文本分割与分段向量化能力，包括 chunk 大小控制、overlap 滑窗、结构化 metadata、以及 Map-Reduce 摘要策略。

### Modified Capabilities
- `indexing-pipeline`: 更新文档处理和向量化的规范要求 — 从"截断全文单条存储"改为"全量分段多条存储"；从"仅段落提取"改为"全结构提取（含表格）"；摘要生成从"截断单次"改为"Map-Reduce 全覆盖"。

## Impact

### 代码影响

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/kb_agent/connectors/local_file.py` | **重写** | `_read_docx` 全结构提取；`_read_spreadsheet` 多 sheet + 行数限制 |
| `src/kb_agent/processor.py` | **重构** | 移除截断逻辑，引入 Chunker，批量写入 chunks 到 ChromaDB |
| `src/kb_agent/llm.py` | **增强** | `generate_summary` 支持 Map-Reduce 策略处理大文件 |
| `src/kb_agent/tools/vector_tool.py` | **增强** | `add_documents` 支持批量 chunk 写入 |

### 依赖影响
- 可能新增 `langchain-text-splitters` 或自研轻量级 splitter（避免引入重依赖）

### 用户影响
- 已有的 ChromaDB 索引数据需要**重新生成**（用户需重新运行 `kb-agent index`）
- 索引数据量将显著增加（每个文档从 2 条变为 N+1 条）
- 索引速度可能变慢（需更多 LLM 调用来生成分段摘要），但检索质量将大幅提升

### 预留扩展点
- PDF 支持：`_read_file` 的 `suffix` 分支已预留 `.pdf` 扩展位
- Parent Document Retriever：chunk metadata 中的 `doc_id` + `chunk_index` 为后续实现层级检索打好基础
