import operator
from typing import Annotated, Any, Callable, Dict, List, Literal, Optional, TypedDict

class PlanStep(TypedDict, total=False):
    step_id: str
    description: str
    skill_name: str
    skill_args: Dict[str, Any]
    status: Literal["pending", "in_progress", "done", "error"]
    result: Optional[str]

class AgentTaskState(TypedDict, total=False):
    session_id: str
    goal: str
    goal_analysis: str
    plan: List[PlanStep]
    current_step_index: int
    plan_version: int
    
    execution_log: Annotated[List[Dict[str, Any]], operator.add]
    
    workspace: str # path to agent_tmp/session_{id}
    available_skills: List[str]
    
    consecutive_failures: int
    max_consecutive_failures: int
    
    reflection_history: Annotated[List[Dict[str, Any]], operator.add]
    
    needs_replan: bool
    needs_human_input: bool
    human_prompt: str
    human_response: str
    
    task_status: Literal["init", "running", "paused", "completed", "failed", "aborted"]
