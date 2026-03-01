from kb_agent.agent.nodes import grade_evidence_node
from kb_agent.agent.state import AgentState
import pytest

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
        
        # Override settings to disable few_context auto-approve rule for tests
        from kb_agent.config import settings
        mocker.patch.object(settings, "auto_approve_max_items", 0)
        
    return _mock

def test_grade_evidence_generate(mock_llm_response):
    mock_llm_response('''[0.8, 1.0]''')
    
    state = AgentState(
        query="What is the process?",
        context=["Step 1 is X", "Step 2 is Y"]
    )
    result = grade_evidence_node(state)
    
    assert result["grader_action"] == "GENERATE"
    assert len(result["evidence_scores"]) == 2
    assert len(result["context"]) == 2 # all > 0.3

def test_grade_evidence_refine(mock_llm_response):
    mock_llm_response('''[0.9, 0.1]''')
    
    state = AgentState(
        query="What is the process?",
        context=["Step 1 is X", "Random irrelevant text"]
    )
    result = grade_evidence_node(state)
    
    assert result["grader_action"] == "REFINE" # avg is 0.5
    assert len(result["context"]) == 1 # 0.1 filtered out
    assert result["context"][0] == "Step 1 is X"

def test_grade_evidence_re_retrieve(mock_llm_response):
    mock_llm_response('''[0.1, 0.2]''')
    
    state = AgentState(
        query="What is the process?",
        context=["Random text A", "Random text B"]
    )
    result = grade_evidence_node(state)
    
    assert result["grader_action"] == "RE_RETRIEVE" # avg is 0.15
    assert len(result["context"]) == 0 # both filtered out

def test_grade_evidence_parse_failure(mock_llm_response):
    mock_llm_response('''Sorry, I cannot help.''')
    
    state = AgentState(
        query="What is the process?",
        context=["Context item 1", "Context item 2"]
    )
    result = grade_evidence_node(state)
    
    # Fallback to 0.5 default
    assert result["grader_action"] == "REFINE" # avg is 0.5
    assert len(result["context"]) == 2 # both kept
    assert result["evidence_scores"] == [0.5, 0.5]

def test_grade_evidence_no_context():
    state = AgentState(
        query="What is the process?",
        context=[]
    )
    result = grade_evidence_node(state)
    
    assert result["grader_action"] == "RE_RETRIEVE"
