from typing import Any, Literal
from langgraph.graph import StateGraph, END
from kb_agent.agent_mode.state import AgentTaskState
from kb_agent.agent_mode.nodes import (
    goal_intake_node, plan_node, act_node, reflect_node, 
    human_intervene_node, finalize_node
)

def route_after_plan(state: AgentTaskState) -> Literal["act"]:
    """Route from plan node to the next step.
    Will map out parallel steps or conditional routing later, currently hardcoded to act.
    """
    return "act"

def route_after_reflect(state: AgentTaskState) -> Literal["act", "plan", "human_intervene", "finalize"]:
    """Route from reflect node based on current step status and overall plan execution."""
    if state.get("needs_human_input", False):
        return "human_intervene"
        
    if state.get("needs_replan", False):
        return "plan"
    
    failures = state.get("consecutive_failures", 0)
    max_failures = state.get("max_consecutive_failures", 3)
    if failures >= max_failures:
        return "human_intervene"
        
    plan = state.get("plan", [])
    
    all_done = True
    for step in plan:
        if step.get("status") != "done":
            all_done = False
            break
            
    if all_done and plan:
        return "finalize"
        
    # Check if we need to replan due to errors or new constraints
    # (a real reflect node might set a flag 'requires_replan' in the state)
    # For skeleton, just go to act if not completed
    return "act"

def build_agent_graph():
    workflow = StateGraph(AgentTaskState)
    
    # Add nodes
    workflow.add_node("goal_intake", goal_intake_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("act", act_node)
    workflow.add_node("reflect", reflect_node)
    workflow.add_node("human_intervene", human_intervene_node)
    workflow.add_node("finalize", finalize_node)
    
    # Set entry point
    workflow.set_entry_point("goal_intake")
    
    # Add edges
    workflow.add_edge("goal_intake", "plan")
    
    workflow.add_conditional_edges(
        "plan",
        route_after_plan,
        {
            "act": "act"
        }
    )
    
    workflow.add_edge("act", "reflect")
    
    workflow.add_conditional_edges(
        "reflect",
        route_after_reflect,
        {
            "act": "act",
            "plan": "plan",
            "human_intervene": "human_intervene",
            "finalize": "finalize"
        }
    )
    
    # Human intervene routes back to plan to resume execution or refine strategy
    workflow.add_edge("human_intervene", "plan")
    
    # Finalize node cleanly finishes the task
    workflow.add_edge("finalize", END)
    
    return workflow.compile()
