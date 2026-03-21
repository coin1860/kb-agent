"""
name: search_kb
description: Searches the knowledge base using vector search.
parameters: {"query": "string"}
"""
from typing import Any
from kb_agent.tools.vector_tool import VectorTool

def execute(query: str, sandbox: Any = None) -> dict:
    try:
        tool = VectorTool()
        results = tool.search(query)
        res_str = ""
        for i, r in enumerate(results):
            res_str += f"Result {i+1} [{r['metadata'].get('source', 'unknown')}]:\n{r['document']}\n---\n"
        if not res_str:
            res_str = "No results found."
        return {"status": "success", "result": res_str}
    except Exception as e:
        return {"status": "error", "result": str(e)}
