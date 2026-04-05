import pytest
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from kb_agent.skill.planner import _build_message_history, _truncate_messages

def test_build_message_history_merges_iteration_prompt():
    """Verify that _build_message_history merges iteration info into the last HumanMessage."""
    command = "calculate 2+2"
    tool_history = [] # Iteration 1
    
    messages = _build_message_history(
        command=command,
        tool_history=tool_history,
        iteration=1,
        max_iterations=3
    )
    
    # Should have [SystemMessage, HumanMessage] (NOT 3 messages)
    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert "Iteration: 1 / 3" in messages[1].content
    assert "User command: calculate 2+2" in messages[1].content

def test_build_message_history_with_tools_maintains_alternation():
    """Verify that with tools, it still merges the iteration prompt into the last HumanMessage."""
    command = "task"
    tool_history = [
        {"tool": "ls", "args": {"path": "."}, "result": "file.txt", "step": 1, "tool_call_id": "c1"}
    ]
    
    messages = _build_message_history(
        command=command,
        tool_history=tool_history,
        iteration=2,
        max_iterations=3
    )
    
    # [System, Human(Command+Iter), AI(Call), Tool(Result)]
    # Wait, in my current implementation, it looks for the LAST HumanMessage.
    # In _build_message_history construction:
    # messages = [system, human_command]
    # for tool in history: messages.extend([ai, tool])
    # then merge iter into last human.
    
    # So it should be [System, Human(Command+Iter), AI, Tool]
    # This keeps the human role from being consecutive with another human if the next turn started.
    
    # Let's check the order
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], HumanMessage)
    assert "Iteration: 2 / 3" in messages[1].content
    assert isinstance(messages[2], AIMessage)
    assert isinstance(messages[3], ToolMessage)
    
    # No two consecutive HumanMessages
    for i in range(len(messages) - 1):
        if isinstance(messages[i], HumanMessage):
             assert not isinstance(messages[i+1], HumanMessage)

def test_truncate_messages_preserves_pairs():
    """Verify that truncation doesn't leave an orphaned ToolMessage at the start."""
    system = SystemMessage(content="sys")
    h1 = HumanMessage(content="h1")
    ai1 = AIMessage(content="", tool_calls=[{"name":"t1", "args":{}, "id":"1"}])
    t1 = ToolMessage(content="r1", tool_call_id="1")
    h2 = HumanMessage(content="h2")
    ai2 = AIMessage(content="", tool_calls=[{"name":"t2", "args":{}, "id":"2"}])
    t2 = ToolMessage(content="r2", tool_call_id="2")
    
    messages = [system, h1, ai1, t1, h2, ai2, t2]
    
    # Truncate to 4 messages (System + 3 latest)
    # 3 latest are [h2, ai2, t2]. This is valid.
    truncated = _truncate_messages(messages, max_messages=4)
    assert len(truncated) == 4
    assert truncated[0] == system
    assert truncated[1] == h2
    
    # Truncate to 3 messages (System + 2 latest)
    # 2 latest are [ai2, t2]. This is valid.
    truncated = _truncate_messages(messages, max_messages=3)
    assert len(truncated) == 3
    assert truncated[0] == system
    assert truncated[1] == ai2
    
    # Truncate to 2 messages (System + 1 latest)
    # 1 latest is [t2]. This IS NOT VALID (orphaned tool message).
    # Logic should drop it and return just [system].
    truncated = _truncate_messages(messages, max_messages=2)
    assert len(truncated) == 1
    assert truncated[0] == system
