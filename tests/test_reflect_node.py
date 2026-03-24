import pytest
from kb_agent.agent.state import AgentState
from kb_agent.agent.nodes import reflect_node
from kb_agent.config import settings

def test_reflect_node_jira_extraction():
    state: AgentState = {
        "query": "test",
        "context": ["We are tracking this under FSR-123 and also TTP-9990"],
        "attempted_task_ids": [],
        "discovered_entities": [],
        "task_queue": [],
        "knowledge_gaps": [],
        "iteration": 1,
        "grader_action": "REFINE",
    }
    
    result = reflect_node(state)
    
    # Needs precision since it found tasks but wasn't GENERATE
    assert result["reflection_verdict"] == "needs_precision"
    assert len(result["task_queue"]) == 2
    
    tasks = {t["id"]: t for t in result["task_queue"]}
    assert "jira:FSR-123" in tasks
    assert "jira:TTP-9990" in tasks
    assert tasks["jira:FSR-123"]["args"]["issue_key"] == "FSR-123"


def test_reflect_node_confluence_logic():
    # Bare number without hints
    state1: AgentState = {
        "query": "test",
        "context": ["The cost is 123456789 dollars."],
        "attempted_task_ids": [],
        "discovered_entities": [],
        "task_queue": [],
        "knowledge_gaps": [],
        "iteration": 1,
        "grader_action": "REFINE",
    }
    result1 = reflect_node(state1)
    assert len(result1["task_queue"]) == 0
    
    # Number with hint
    state2: AgentState = {
        "query": "test",
        "context": ["See confluence page 123456789 for details."],
        "attempted_task_ids": [],
        "discovered_entities": [],
        "task_queue": [],
        "knowledge_gaps": [],
        "iteration": 1,
        "grader_action": "REFINE",
    }
    result2 = reflect_node(state2)
    assert len(result2["task_queue"]) == 1
    assert result2["task_queue"][0]["id"] == "confluence:123456789"


def test_reflect_node_already_attempted():
    state: AgentState = {
        "query": "test",
        "context": ["FSR-123 is the ticket."],
        "attempted_task_ids": ["jira:FSR-123"],
        "discovered_entities": [{"type": "jira", "value": "FSR-123"}],
        "task_queue": [],
        "knowledge_gaps": [],
        "iteration": 1,
        "grader_action": "REFINE",
    }
    result = reflect_node(state)
    assert len(result["task_queue"]) == 0
    assert result["reflection_verdict"] == "needs_precision" # Still needs more but no exact task


def test_reflect_node_exhaustion():
    state: AgentState = {
        "query": "test",
        "context": ["FSR-123 is missing."],
        "attempted_task_ids": ["jira:FSR-123"],  # already tried
        "discovered_entities": [{"type": "jira", "value": "FSR-123"}],
        "task_queue": [],
        "knowledge_gaps": [],
        "iteration": 5, # max iterations
        "grader_action": "REFINE", # not generate
    }
    
    result = reflect_node(state)
    assert result["reflection_verdict"] == "exhausted"
    assert len(result["knowledge_gaps"]) == 1
    assert "FSR-123" in result["knowledge_gaps"][0]


def test_reflect_node_extraction_markers():
    # Content with markers
    context = [
        "Please look at FSR-444 (active).",
        "<!-- NO_ENTITY_EXTRACT -->\nSub-tasks:\n- FSR-555 (hidden)\n- 123456789 (hidden confluence)\n<!-- /NO_ENTITY_EXTRACT -->",
        "Also see TTP-101 (active)."
    ]
    state: AgentState = {
        "query": "test",
        "context": context,
        "attempted_task_ids": [],
        "discovered_entities": [],
        "task_queue": [],
        "knowledge_gaps": [],
        "iteration": 1,
        "grader_action": "REFINE",
    }
    
    result = reflect_node(state)
    
    task_ids = [t["id"] for t in result["task_queue"]]
    
    # Should find outside markers
    assert "jira:FSR-444" in task_ids
    assert "jira:TTP-101" in task_ids
    
    # Should NOT find inside markers
    assert "jira:FSR-555" not in task_ids
    assert "confluence:123456789" not in task_ids
    
    assert len(result["task_queue"]) == 2
