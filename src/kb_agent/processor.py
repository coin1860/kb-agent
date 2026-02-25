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

        # Index Full Content (truncated)
        truncated_content = full_content[:2000]

        full_meta = metadata.copy()
        full_meta.update({
            "type": "full",
            "file_path": str(full_path),
            "related_file": str(full_path) # Self-reference or same as above
        })

        self.vector_tool.add_documents(
            documents=[truncated_content],
            metadatas=[full_meta],
            ids=[f"{doc_id}-full"]
        )
