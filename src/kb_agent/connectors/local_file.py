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
        query_lower = query.lower()
        for file_path in self.source_dir.rglob("*"):
            if file_path.is_file() and query_lower in file_path.name.lower():
                content = self._read_file(file_path)
                if content is not None:
                    if not content.strip():
                        print(f"Warning: Extracted empty text from {file_path.name}")
                    results.append({
                        "id": file_path.name,
                        "title": file_path.stem,
                        "content": content,
                        "metadata": {"source": "local_file", "path": str(file_path), "type": file_path.suffix}
                    })
        return results

    def fetch_all(self) -> List[Dict[str, Any]]:
        results = []
        # Support recursive search for common document types, case-insensitive
        supported_extensions = {".md", ".txt", ".docx", ".xlsx", ".csv", ".pdf"}
        for file_path in self.source_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
                content = self._read_file(file_path)
                if content is not None:
                    if not content.strip():
                        print(f"Warning: Extracted empty text from {file_path.name}")
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
            elif suffix == ".pdf":
                return self._read_pdf(file_path)
            else:
                return None
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return None

    def _read_pdf(self, file_path: Path) -> str:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            # Fallback if fitz missing
            return f"[PDF parsing requires pymupdf. File: {file_path.name}]"
            
        doc = fitz.open(file_path)
        full_text = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text").strip()
            
            if text:
                # Inject Structural Metadata Headers enabling downstream Semantic Chunking
                full_text.append(f"## Page {page_num + 1}\n\n{text}")
                
        return "\n\n".join(full_text)

    def _read_docx(self, file_path: Path) -> str:
        doc = Document(file_path)
        full_text = []
        
        def extract_blocks(container):
            for block in container.iter_inner_content():
                from docx.text.paragraph import Paragraph
                from docx.table import Table
                
                if isinstance(block, Paragraph):
                    text = block.text.strip()
                    if text:
                        # You can also try to preserve header levels if style represents it (e.g. block.style.name.startswith('Heading'))
                        # For simplicity preserving the text is enough here.
                        full_text.append(text)
                elif isinstance(block, Table):
                    table_md = []
                    for i, row in enumerate(block.rows):
                        row_data = []
                        for cell in row.cells:
                            cell_text = cell.text.replace('\n', ' ').strip()
                            row_data.append(cell_text)
                        
                        row_md = "| " + " | ".join(row_data) + " |"
                        table_md.append(row_md)
                        
                        # Markdown table separator
                        if i == 0:
                            sep = "| " + " | ".join(["---"] * len(row.cells)) + " |"
                            table_md.append(sep)
                            
                    if table_md:
                        full_text.append("\n".join(table_md))

        extract_blocks(doc)
        return "\n\n".join(full_text)

    def _read_spreadsheet(self, file_path: Path) -> str:
        # Convert spreadsheet to Markdown table with row limits
        max_rows = 1000
        
        if file_path.suffix == ".csv":
            df = pd.read_csv(file_path, nrows=max_rows + 1)
            is_truncated = False
            if len(df) > max_rows:
                df = df.head(max_rows)
                is_truncated = True
                
            md_text = df.to_markdown(index=False)
            if is_truncated:
                md_text += f"\n\n[TRUNCATED: {len(df)} limit reached, more rows omitted]"
            return md_text
        else:
            # Excel might have multiple sheets
            dfs = pd.read_excel(file_path, sheet_name=None, nrows=max_rows + 1)
            md_parts = []
            for sheet_name, df in dfs.items():
                is_truncated = False
                if len(df) > max_rows:
                    df = df.head(max_rows)
                    is_truncated = True
                    
                md_text = f"## Sheet: {sheet_name}\n\n" + df.to_markdown(index=False)
                if is_truncated:
                    md_text += f"\n\n[TRUNCATED: {len(df)} limit reached, more rows in this sheet omitted]"
                md_parts.append(md_text)
                
            return "\n\n".join(md_parts)
