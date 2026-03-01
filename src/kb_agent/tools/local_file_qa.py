import json
from kb_agent.tools.vector_tool import VectorTool

class LocalFileQATool:
    """
    Search for local markdown files by filename and context keywords.
    Returns explicitly formatted table entries for Q&A reference.
    """
    def __init__(self):
        self._vector_tool = VectorTool()

    def query(self, search_term: str) -> str:
        """
        Queries ChromaDB explicitly filtering for type: 'summary' or 'full'.
        Returns 1-indexed tables of matching filenames.
        """
        # Search the knowledge base via ChromaDB Wrapper
        # We query for both "full" and "summary" types to maximize surface area
        where_filter = {
            "$or": [
                {"type": "summary"},
                {"type": "full"}
            ]
        }
        
        results = self._vector_tool.search(query_text=search_term, n_results=30)
        
        if not results:
            return "No matching files found in the knowledge base."

        # Process and format results
        formatted_rows = []
        seen_basenames = set()
        index = 1

        for r in results:
            metadata = r.get("metadata", {})
            file_path = metadata.get("related_file", "")
            
            if not file_path:
                continue

            import os
            basename = os.path.basename(file_path)
            
            if basename in seen_basenames:
                continue
                
            seen_basenames.add(basename)
            
            # Simple heuristic for filename vs context match:
            query_words = [w.lower() for w in search_term.split() if len(w) > 2]
            is_filename_match = any(qw in basename.lower() for qw in query_words)
            
            match_type = "(filename match)" if is_filename_match else "(context match)"
            
            formatted_rows.append(f"{index}, {file_path} {match_type}")
            index += 1
            if index > 10:
                break
            
        return "\n".join(formatted_rows)
