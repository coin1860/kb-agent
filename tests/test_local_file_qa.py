import os
from unittest.mock import patch, MagicMock
import pytest

# Dummy env vars for config
os.environ.setdefault("KB_AGENT_LLM_API_KEY", "dummy")
os.environ.setdefault("KB_AGENT_LLM_BASE_URL", "http://dummy")

from kb_agent.engine import Engine

@pytest.mark.asyncio
@patch("kb_agent.engine.compile_graph")
@patch("kb_agent.engine.LLMClient")
async def test_search_for_mexico_payment_files(MockLLM, MockGraph):
    mock_graph = MockGraph.return_value
    # Mock the return value of graph.invoke to simulate the expected LLM output
    mock_graph.invoke.side_effect = [
        {"final_answer": "1, /docs/mexico_payments.md (filename match)"}, # First query result
        {"final_answer": "Summary of Mexico payments: We pay them quickly, securely, and always on time as requested."} # Second query result
    ]
    
    engine = Engine()
    
    # 3.1 Verify query returns the formatted table
    history1 = []
    
    response = engine.answer_query("Find Mexico payment files", history=history1, mode="knowledge_base")
            
    print("RESPONSE 1:", response)
    
    # Simple check for numbers and parenthesis (filename match / context match)
    assert "1, " in response
    assert "(filename match)" in response or "(context match)" in response
    
    history1.append({"role": "user", "content": "Find Mexico payment files"})
    history1.append({"role": "assistant", "content": response})

    # 3.2 Verify follow-up file summarization
    response2 = engine.answer_query("Summarize file 1", history=history1, mode="knowledge_base")
            
    print("RESPONSE 2:", response2)
    assert len(response2) > 50 # Basic check that a summary was generated

