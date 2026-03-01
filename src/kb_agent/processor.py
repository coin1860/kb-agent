from typing import List, Dict, Any
from pathlib import Path
from kb_agent.llm import LLMClient
from kb_agent.tools.vector_tool import VectorTool
import os

class Processor:
    """
    Processes fetched data into markdown files and indexes them in ChromaDB.
    """
    def __init__(self, docs_path: Path):
        self.docs_path = docs_path
        os.makedirs(self.docs_path, exist_ok=True)

        # Dependencies
        self.llm = LLMClient()
        self.vector_tool = VectorTool()
        
        from kb_agent.chunking import MarkdownAwareChunker
        self.chunker = MarkdownAwareChunker()

    def process(self, data: Dict[str, Any]):
        """
        Process a single data item.
        data: {"id": "ISSUE-123", "title": "...", "content": "...", "metadata": {...}}
        """
        doc_id = data.get("id")
        if not doc_id:
            return # Skip invalid data

        # 1. Save Full Markdown File
        full_path = self.docs_path / f"{doc_id}.md"
        content = data.get("content", "")
        title = data.get("title", "")
        metadata = data.get("metadata", {})

        # Combine title and content for the file
        # Check if content already has a header to avoid duplication
        if content.lstrip().startswith("#"):
            full_content = content
        else:
            full_content = f"# {title}\n\n{content}"

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(full_content)

        # 2. Generate Summary
        summary = self.llm.generate_summary(full_content)
        summary_path = self.docs_path / f"{doc_id}-summary.md"
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary)

        # 3. Index Both

        # Index Summary
        # Note: We apply **metadata first so that our specific keys override it if necessary
        # But actually we want our keys to be authoritative.
        # So we unpack metadata, then overwrite type/paths.
        summary_meta = metadata.copy()
        summary_meta.update({
            "type": "summary",
            "file_path": str(summary_path),
            "related_file": str(full_path)
        })

        self.vector_tool.add_documents(
            documents=[summary],
            metadatas=[summary_meta],
            ids=[f"{doc_id}-summary"]
        )

        # Index Chunks instead of truncated full content
        base_meta = metadata.copy()
        base_meta.update({
            "type": "chunk",
            "file_path": str(full_path),
            "doc_id": doc_id,
            "related_file": str(full_path)
        })
        
        chunks = self.chunker.chunk(full_content, base_meta)
        
        chunk_docs = []
        chunk_metas = []
        chunk_ids = []
        
        for c in chunks:
            chunk_docs.append(c.text)
            chunk_metas.append(c.metadata)
            idx = c.metadata.get("chunk_index", 0)
            chunk_ids.append(f"{doc_id}-chunk-{idx}")
            
        if chunk_docs:
            self.vector_tool.add_documents(
                documents=chunk_docs,
                metadatas=chunk_metas,
                ids=chunk_ids
            )
