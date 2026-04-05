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

        content = data.get("content", "")
        title = data.get("title", "")
        metadata = data.get("metadata", {})

        # Combine title and content for the file
        # Check if content already has a header to avoid duplication
        if content.lstrip().startswith("#"):
            full_content = content
        else:
            full_content = f"# {title}\n\n{content}"

        full_path_str = metadata.get("path")
        if not full_path_str:
            full_path_str = str(self.docs_path / f"{doc_id}.md")

        # 2. Skip Summary Generation
        summary = ""

        # 3. Index Chunks
        base_meta = metadata.copy()
        base_meta.update({
            "type": "chunk",
            "file_path": full_path_str,
            "doc_id": doc_id,
            "related_file": full_path_str,
            "document_title": title,
        })
        
        if summary:
            base_meta["document_summary"] = summary
        
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
