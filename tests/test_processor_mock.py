import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock
import pandas as pd

# Set environment variables BEFORE importing config/modules
os.environ["KB_AGENT_LLM_API_KEY"] = "dummy_key"
os.environ["KB_AGENT_LLM_BASE_URL"] = "http://dummy.url"

# Import settings after env vars are set
from kb_agent.config import settings

# Since docs_path is a property dependent on index_path, we set index_path
settings.index_path = Path("./test_docs")
if os.path.exists("./test_docs"):
    shutil.rmtree("./test_docs")
os.makedirs("./test_docs")

# Mock LLM
from kb_agent.llm import LLMClient
LLMClient.generate_summary = MagicMock(return_value="This is a summary.")

# Mock VectorTool
from kb_agent.tools.vector_tool import VectorTool
VectorTool.add_documents = MagicMock()

from kb_agent.processor import Processor

def test_processor():
    p = Processor(docs_path=Path("./test_docs"))

    data = {
        "id": "TEST-123",
        "title": "Test Document",
        "content": "This is the content of the test document.",
        "metadata": {"source": "test"}
    }

    p.process(data)

    # Check files created
    assert (p.docs_path / "TEST-123.md").exists()
    assert (p.docs_path / "TEST-123-summary.md").exists()

    # Check LLM called
    p.llm.generate_summary.assert_called_once()

    # Check VectorTool called twice (summary + full)
    assert p.vector_tool.add_documents.call_count == 2

if __name__ == "__main__":
    try:
        test_processor()
        print("Processor test passed!")
    except Exception as e:
        print(f"Processor test failed: {e}")
