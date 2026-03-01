from kb_agent.agent.nodes import analyze_and_route_node
from kb_agent.agent.state import AgentState
import pytest

# Note: In a real test environment with mocked LLM, these would test the node logic.
# Since analyze_and_route_node makes an LLM call directly, we need to mock _build_llm.

@pytest.fixture
def mock_llm_response(mocker):
    """Mock the LLM response to avoid actual API calls."""
    class MockMessage:
        def __init__(self, content):
            self.content = content
    
    class MockLLM:
        def __init__(self, response_content):
            self.response_content = response_content
            
        def invoke(self, messages):
            return MockMessage(self.response_content)
    
    def _mock(content):
        mocker.patch("kb_agent.agent.nodes._build_llm", return_value=MockLLM(content))
        
    return _mock

def test_analyze_and_route_exact(mock_llm_response):
    mock_llm_response('''{"query_type": "exact", "sub_questions": [], "suggested_tools": ["grep_search"], "grep_keywords": ["PROJ-123"]}''')
    
    state = AgentState(query="What is the status of PROJ-123?")
    result = analyze_and_route_node(state)
    
    assert result["query_type"] == "exact"
    assert result["routing_plan"]["suggested_tools"] == ["grep_search"]
    assert result["routing_plan"]["grep_keywords"] == ["PROJ-123"]

def test_analyze_and_route_conceptual(mock_llm_response):
    mock_llm_response('''{"query_type": "conceptual", "sub_questions": [], "suggested_tools": ["vector_search"], "grep_keywords": []}''')
    
    state = AgentState(query="How does the indexing pipeline work?")
    result = analyze_and_route_node(state)
    
    assert result["query_type"] == "conceptual"
    assert result["routing_plan"]["suggested_tools"] == ["vector_search"]

def test_analyze_and_route_relational(mock_llm_response):
    mock_llm_response('''{"query_type": "relational", "sub_questions": [], "suggested_tools": ["graph_related"], "grep_keywords": []}''')
    
    state = AgentState(query="What tickets are linked to PROJ-100?")
    result = analyze_and_route_node(state)
    
    assert result["query_type"] == "relational"
    assert result["routing_plan"]["suggested_tools"] == ["graph_related"]

def test_analyze_and_route_file_discovery(mock_llm_response):
    mock_llm_response('''{"query_type": "file_discovery", "sub_questions": [], "suggested_tools": ["local_file_qa"], "grep_keywords": []}''')
    
    state = AgentState(query="查找关于认证的文件")
    result = analyze_and_route_node(state)
    
    assert result["query_type"] == "file_discovery"
    assert result["routing_plan"]["suggested_tools"] == ["local_file_qa"]

def test_analyze_and_route_decomposition(mock_llm_response):
    mock_llm_response('''{"query_type": "conceptual", "sub_questions": ["What is indexing pipeline?", "What is query engine?"], "suggested_tools": ["vector_search"], "grep_keywords": []}''')
    
    state = AgentState(query="Compare the indexing pipeline with the query engine")
    result = analyze_and_route_node(state)
    
    assert len(result["sub_questions"]) == 2
    assert "What is indexing pipeline?" in result["sub_questions"]
