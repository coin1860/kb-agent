import re
from typing import List, Dict
import kb_agent.config as config

class Chunk:
    def __init__(self, text: str, metadata: Dict):
        self.text = text
        self.metadata = metadata

def split_by_markdown_headers(text: str) -> List[Chunk]:
    lines = text.split('\n')
    chunks = []
    
    current_title = "Introduction"
    current_text = []
    
    header_pattern = re.compile(r'^(#{1,3})\s+(.*)')
    
    for line in lines:
        match = header_pattern.match(line)
        if match:
            # Save previous chunk if exists
            if current_text:
                joined_text = '\n'.join(current_text).strip()
                if joined_text:
                    chunks.append(Chunk(text=joined_text, metadata={"section_title": current_title}))
            current_title = match.group(2).strip()
            current_text = [line]
        else:
            current_text.append(line)
            
    if current_text:
        joined_text = '\n'.join(current_text).strip()
        if joined_text:
            chunks.append(Chunk(text=joined_text, metadata={"section_title": current_title}))
            
    return chunks

def split_by_paragraphs(text: str, max_chars: int = None, overlap_chars: int = None) -> List[str]:
    if max_chars is None:
        max_chars = config.settings.chunk_max_chars if config.settings and config.settings.chunk_max_chars is not None else 800
    if overlap_chars is None:
        overlap_chars = config.settings.chunk_overlap_chars if config.settings and config.settings.chunk_overlap_chars is not None else 200
        
    paragraphs = text.split('\n\n')
    chunks = []
    
    current_chunk = []
    current_length = 0
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
            
        if current_length + len(para) > max_chars and current_chunk:
            chunks.append('\n\n'.join(current_chunk))
            
            # Start next chunk with overlap
            overlap_length = 0
            overlap_paras = []
            for p in reversed(current_chunk):
                if overlap_length + len(p) <= overlap_chars:
                    overlap_paras.insert(0, p)
                    overlap_length += len(p) + 2
                else:
                    break
            
            if not overlap_paras:
                overlap_paras = [current_chunk[-1]]
                
            current_chunk = overlap_paras + [para]
            current_length = sum(len(p) for p in current_chunk) + (len(current_chunk) - 1) * 2
        else:
            current_chunk.append(para)
            current_length += len(para) + 2
            
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
        
    return chunks

class MarkdownAwareChunker:
    """
    Hierarchical chunker that splits document into semantic chunks primarily using
    Markdown headers, falling back to overlapping paragraph chunks if a section is too long.
    """
    def __init__(self, max_chars: int = None, overlap_chars: int = None):
        if max_chars is None:
            max_chars = config.settings.chunk_max_chars if config.settings and config.settings.chunk_max_chars is not None else 800
        if overlap_chars is None:
            overlap_chars = config.settings.chunk_overlap_chars if config.settings and config.settings.chunk_overlap_chars is not None else 200
            
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars
        
    def chunk(self, text: str, base_metadata: Dict) -> List[Chunk]:
        initial_chunks = split_by_markdown_headers(text)
        
        final_chunks = []
        for chunk in initial_chunks:
            if len(chunk.text) > self.max_chars:
                sub_texts = split_by_paragraphs(chunk.text, self.max_chars, self.overlap_chars)
                for sub_text in sub_texts:
                    meta = base_metadata.copy()
                    meta.update(chunk.metadata)
                    final_chunks.append(Chunk(text=sub_text, metadata=meta))
            else:
                meta = base_metadata.copy()
                meta.update(chunk.metadata)
                final_chunks.append(Chunk(text=chunk.text, metadata=meta))
                
        # Inject standard metadata
        total = len(final_chunks)
        for i, c in enumerate(final_chunks):
            c.metadata["chunk_index"] = i
            c.metadata["total_chunks"] = total
            
        return final_chunks
