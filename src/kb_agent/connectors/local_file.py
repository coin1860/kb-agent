import pandas as pd
from docx import Document
from pathlib import Path
from typing import List, Dict, Any, Optional
from .base import BaseConnector

class LocalFileConnector(BaseConnector):
    """
    Connector for reading local files (Excel, Word, Markdown) and converting them to a common format.
    """

    def __init__(self, source_dir: Path):
        self.source_dir = Path(source_dir)
        if not self.source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {self.source_dir}")

    def fetch_data(self, query: str) -> List[Dict[str, Any]]:
        # For local files, "query" might be a filename or just list all files that match.
        # This is a simple implementation: find files matching the query in the name.
        results = []
        for file_path in self.source_dir.rglob(f"*{query}*"):
            if file_path.is_file():
                content = self._read_file(file_path)
                if content:
                    results.append({
                        "id": file_path.name,
                        "title": file_path.stem,
                        "content": content,
                        "metadata": {"source": "local_file", "path": str(file_path), "type": file_path.suffix}
                    })
        return results

    def fetch_all(self) -> List[Dict[str, Any]]:
        results = []
        # Support recursive search for common document types
        patterns = ["*.md", "*.txt", "*.docx", "*.xlsx", "*.csv"]
        for pattern in patterns:
            for file_path in self.source_dir.rglob(pattern):
                if file_path.is_file():
                    content = self._read_file(file_path)
                    if content:
                        results.append({
                            "id": file_path.name,
                            "title": file_path.stem,
                            "content": content,
                            "metadata": {"source": "local_file", "path": str(file_path), "type": file_path.suffix}
                        })
        return results

    def _read_file(self, file_path: Path) -> Optional[str]:
        """Reads a file and converts it to Markdown text."""
        try:
            suffix = file_path.suffix.lower()
            if suffix == ".md":
                return file_path.read_text(encoding="utf-8", errors="replace")
            elif suffix == ".txt":
                return file_path.read_text(encoding="utf-8", errors="replace")
            elif suffix == ".docx":
                return self._read_docx(file_path)
            elif suffix in [".xlsx", ".csv"]:
                return self._read_spreadsheet(file_path)
            else:
                return None
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return None

    def _read_docx(self, file_path: Path) -> str:
        doc = Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return "\n\n".join(full_text)

    def _read_spreadsheet(self, file_path: Path) -> str:
        # Convert spreadsheet to Markdown table
        if file_path.suffix == ".csv":
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path)

        # Simple markdown conversion using pandas
        return df.to_markdown(index=False)
