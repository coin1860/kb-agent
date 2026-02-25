from unittest.mock import patch, MagicMock
import os
import json

# Set dummy env vars for config before importing anything that uses settings
os.environ["KB_AGENT_LLM_API_KEY"] = "dummy"
os.environ["KB_AGENT_LLM_BASE_URL"] = "http://dummy"

def test_engine_flow():
    with patch("kb_agent.engine.LLMClient") as MockLLM, \
         patch("kb_agent.engine.VectorTool") as MockVector, \
         patch("kb_agent.engine.GrepTool") as MockGrep, \
         patch("kb_agent.engine.FileTool") as MockFile:

        # Setup mock instances
        mock_llm = MockLLM.return_value
        mock_vector = MockVector.return_value
        mock_grep = MockGrep.return_value
        mock_file = MockFile.return_value

        # Configure tool outputs
        mock_grep.search.return_value = [
            {"file_path": "DOC-1.md", "content": "Project X status", "line": 10}
        ]

        mock_vector.search.return_value = [
            {"id": "DOC-1-summary", "score": 0.5, "metadata": {"file_path": "DOC-1-summary.md", "related_file": "DOC-1.md", "type": "summary"}}
        ]

        # Configure LLM responses
        # 1. Decision (which file to read)
        # 2. Final Answer
        mock_llm.chat_completion.side_effect = [
            '[{"id": "DOC-1", "type": "summary"}]',
            "The project is on track."
        ]

        mock_file.read_file.return_value = "Summary content..."

        from kb_agent.engine import Engine
        engine = Engine()

        # Run
        answer = engine.answer_query("What is the status of Project X?")

        # Verify
        assert "The project is on track" in answer
        mock_grep.search.assert_called_once()
        mock_vector.search.assert_called_once()
        mock_file.read_file.assert_called()

def test_engine_retry_flow():
    with patch("kb_agent.engine.LLMClient") as MockLLM, \
         patch("kb_agent.engine.VectorTool") as MockVector, \
         patch("kb_agent.engine.GrepTool") as MockGrep, \
         patch("kb_agent.engine.FileTool") as MockFile:

        mock_llm = MockLLM.return_value
        mock_vector = MockVector.return_value
        mock_grep = MockGrep.return_value
        mock_file = MockFile.return_value

        # First attempt: No results
        mock_grep.search.side_effect = [[], [{"file_path": "DOC-2.md", "content": "Found it", "line": 1}]]
        mock_vector.search.side_effect = [[], []] # Second time also empty vector

        # LLM sequence:
        # 1. Generate alternative queries
        # 2. Decision
        # 3. Final Answer
        mock_llm.chat_completion.side_effect = [
            '["new query"]',
            '[{"id": "DOC-2", "type": "full"}]',
            "Found the answer."
        ]

        mock_file.read_file.return_value = "Content..."

        from kb_agent.engine import Engine
        engine = Engine()

        answer = engine.answer_query("Tricky query")

        assert "Found the answer" in answer
        assert mock_grep.search.call_count == 2 # Initial + Retry

def test_engine_link_tracking():
    with patch("kb_agent.engine.LLMClient") as MockLLM, \
         patch("kb_agent.engine.VectorTool") as MockVector, \
         patch("kb_agent.engine.GrepTool") as MockGrep, \
         patch("kb_agent.engine.FileTool") as MockFile:

        mock_llm = MockLLM.return_value
        mock_vector = MockVector.return_value
        mock_grep = MockGrep.return_value
        mock_file = MockFile.return_value

        # Search returns "DOC-1"
        mock_grep.search.return_value = []
        mock_vector.search.return_value = [
            {"id": "DOC-1", "score": 0.5, "metadata": {"file_path": "DOC-1.md", "type": "full"}}
        ]

        # Decision: Read DOC-1
        mock_llm.chat_completion.side_effect = [
            '[{"id": "DOC-1", "type": "full"}]', # Decision
            "Final Answer"
        ]

        # File content logic
        def read_file_side_effect(path):
            if "DOC-1" in path: # Matches "DOC-1.md"
                return "This relates to [LINK-999]."
            if "LINK-999" in path: # Matches "LINK-999.md"
                return "Content of linked document."
            return None

        mock_file.read_file.side_effect = read_file_side_effect

        from kb_agent.engine import Engine
        engine = Engine()

        answer = engine.answer_query("Query")

        # Verify read_file was called for LINK-999.md
        # Inspect all calls to read_file
        calls = [str(args[0]) for args, _ in mock_file.read_file.call_args_list]
        print(f"Read files: {calls}")
        assert any("LINK-999" in c for c in calls)
        assert any("DOC-1" in c for c in calls)

if __name__ == "__main__":
    try:
        test_engine_flow()
        print("Flow test passed!")
        test_engine_retry_flow()
        print("Retry test passed!")
        test_engine_link_tracking()
        print("Link tracking test passed!")
    except Exception as e:
        print(f"Engine test failed: {e}")
        import traceback
        traceback.print_exc()
