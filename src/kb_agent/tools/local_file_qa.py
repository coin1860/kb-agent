import os
from pathlib import Path
from kb_agent.config import settings

class LocalFileQATool:
    """
    Search for local markdown files by filename prefix in the index directory and return their contents.
    """
    def __init__(self):
        pass

    def query(self, search_term: str) -> str:
        """
        Search for files starting with the given filename prefix in the index directory.
        If multiple matching files have different extensions, prioritize .md.
        Returns the content of the file or an error message.
        """
        if not settings or not settings.index_path:
            return "Error: index_path is not configured in settings."

        index_dir = settings.index_path
        if not index_dir.exists() or not index_dir.is_dir():
            return f"Error: Index directory {index_dir} does not exist."

        matching_files = []
        try:
            # Strip trailing .md from search_term to make it more flexible
            clean_search_term = search_term.lower()
            if clean_search_term.endswith('.md'):
                clean_search_term = clean_search_term[:-3]

            for item in index_dir.iterdir():
                if item.is_file() and item.name.lower().startswith(clean_search_term):
                    matching_files.append(item)
        except Exception as e:
            return f"Error reading index directory: {str(e)}"

        if not matching_files:
            return f"No files found starting with '{search_term}' in {index_dir}."

        # Prioritize .md
        target_file = None
        for file in matching_files:
            if file.suffix.lower() == '.md':
                target_file = file
                break
        
        if not target_file:
            target_file = matching_files[0]

        try:
            content = target_file.read_text(encoding='utf-8')
            if len(content) > 8000:
                content = content[:8000] + "\n\n... (truncated to save tokens)"
            
            return f"File Content for '{target_file.name}':\n\n{content}"
        except Exception as e:
            return f"Error reading file {target_file.name}: {str(e)}"

    def run(self, search_term: str) -> str:
        """Alias for query to match tool interface."""
        return self.query(search_term)
