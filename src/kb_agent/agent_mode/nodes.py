import json
import traceback
from typing import Any, Dict, Callable
from datetime import datetime
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.types import interrupt

from kb_agent.llm_router import get_llm_router
from kb_agent.agent_mode.state import AgentTaskState
from kb_agent.agent_mode.sandbox import SandboxContext
from kb_agent.agent_mode.skills import SkillLoader
from kb_agent.agent_mode.session import SessionManager

_skill_loader = None
def get_skill_loader():
    global _skill_loader
    if not _skill_loader:
        _skill_loader = SkillLoader()
        _skill_loader.scan()
    return _skill_loader

_session_manager = None
def get_session_manager():
    global _session_manager
    if not _session_manager:
        _session_manager = SessionManager()
    return _session_manager

_STATUS_CALLBACKS: Dict[str, Callable[[Dict[str, Any]], None]] = {}

def register_status_callback(session_id: str, cb):
    _STATUS_CALLBACKS[session_id] = cb

def unregister_status_callback(session_id: str):
    if session_id in _STATUS_CALLBACKS:
        del _STATUS_CALLBACKS[session_id]

def _emit(state: AgentTaskState, emoji: str, msg: str):
    sess_id = state.get("session_id")
    cb = _STATUS_CALLBACKS.get(sess_id)
    if cb:
        cb({"emoji": emoji, "msg": msg})

def _append_log(state: AgentTaskState, emoji: str, event: str, details: Any = None) -> list:
    return [{"timestamp": datetime.now().isoformat(), "emoji": emoji, "event": event, "details": details}]

def goal_intake_node(state: AgentTaskState) -> Dict[str, Any]:
    _emit(state, "🎯", "Analyzing goal...")
    goal = state.get("goal", "")
    router = get_llm_router()
    llm = router.get("strong")
    
    prompt = f"""You are an autonomous AI agent. Analyze the user's goal and break it down into a clear, actionable objective.
User goal: {goal}

Output ONLY a JSON object with a single key "analysis" containing your analysis string.
"""
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)
        analysis = data.get("analysis", goal)
    except Exception as e:
        analysis = f"Fallback analysis due to error: {e}"
        
    return {
        "goal_analysis": analysis,
        "task_status": "running",
        "execution_log": _append_log(state, "🎯", "Goal intake completed")
    }

def plan_node(state: AgentTaskState) -> Dict[str, Any]:
    _emit(state, "📋", "Generating execution plan...")
    router = get_llm_router()
    llm = router.get("strong")
    
    goal = state.get("goal")
    analysis = state.get("goal_analysis")
    skills = get_skill_loader().skills
    skill_manifest = [{"name": n, "desc": s.description, "params": s.parameters} for n, s in skills.items()]
    
    prompt = f"""You are planning steps to achieve a goal.
Goal: {goal}
Analysis: {analysis}

Available skills:
{json.dumps(skill_manifest, indent=2)}

Create an ordered list of steps. Each step MUST use one of the available skills.
Output ONLY a JSON object with a single key "plan" containing an array of step objects.
Each step object must have:
- "step_id": A unique string ID (e.g. "step_1")
- "description": What this step attempts to achieve
- "skill_name": The exact name of the skill to use
- "skill_args": A JSON object of arguments matching the skill parameters
"""
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.replace("```json", "").replace("```", "").strip()
        data = json.loads(content)
        plan = data.get("plan", [])
        for step in plan:
            step["status"] = "pending"
            step["result"] = None
    except Exception as e:
        plan = [{"step_id": "error", "description": f"Failed to generate plan: {e}", "skill_name": "unknown", "skill_args": {}, "status": "error", "result": None}]
        
    return {
        "plan": plan, 
        "plan_version": state.get("plan_version", 0) + 1,
        "current_step_index": 0,
        "consecutive_failures": 0,
        "needs_replan": False,
        "execution_log": _append_log(state, "📋", f"Generated plan with {len(plan)} steps")
    }

def act_node(state: AgentTaskState) -> Dict[str, Any]:
    plan = list(state.get("plan", []))
    idx = state.get("current_step_index", 0)
    
    if idx >= len(plan):
        return {} # nothing to do
        
    step = plan[idx]
    skill_name = step.get("skill_name")
    skill_args = step.get("skill_args", {})
    step_desc = step.get("description", skill_name)
    
    _emit(state, "⚙️", f"Executing step {idx+1}/{len(plan)}: {step_desc}")
    
    tier = 0
    if skill_name in ["write_output", "ensure_venv", "git_commit"]:
        tier = 2
        
    if tier == 2:
        _emit(state, "⚠️", f"Step requires confirmation: {skill_name}")
        response = interrupt(f"Agent wants to run {skill_name} with args {skill_args}. Type 'approve', 'deny', or provide feedback:")
        if str(response).strip().lower() in ["deny", "no", "cancel"]:
            step["status"] = "error"
            step["result"] = "User denied execution."
            return {"plan": plan, "execution_log": _append_log(state, "❌", f"User denied step {idx+1}")}
        elif str(response).strip().lower() not in ["approve", "yes", "y", "ok"]:
            step["status"] = "error"
            step["result"] = f"User feedback: {response}"
            return {"plan": plan, "execution_log": _append_log(state, "💬", f"User feedback for step {idx+1}: {response}")}
    
    loader = get_skill_loader()
    sandbox = SandboxContext(state.get("session_id", "default"))
    
    step["status"] = "in_progress"
    
    try:
        # Check if the skill name is a class instance method (it usually isn't)
        # It's an execute function taking kwargs
        result = loader.invoke(skill_name, skill_args, sandbox)
        # Usually it returns {"status": "success", "result": ...}
        if isinstance(result, dict) and "status" in result:
            step["status"] = result.get("status", "done")
            step["result"] = str(result.get("result", ""))
        else:
            step["status"] = "done"
            step["result"] = str(result)
    except Exception as e:
        step["status"] = "error"
        step["result"] = f"Error: {str(e)}\n{traceback.format_exc()}"
        
    log_detail = {"skill": skill_name, "args": skill_args, "status": step["status"]}
    return {
        "plan": plan,
        "execution_log": _append_log(state, "⚙️", f"Executed {skill_name}", log_detail)
    }

def reflect_node(state: AgentTaskState) -> Dict[str, Any]:
    _emit(state, "🤔", "Reflecting on outcome...")
    plan = list(state.get("plan", []))
    idx = state.get("current_step_index", 0)
    
    if idx >= len(plan):
        return {} # Should not happen
        
    step = plan[idx]
    failures = state.get("consecutive_failures", 0)
    
    next_idx = idx
    needs_human = False
    update = {}
    
    if step.get("status") in ["success", "done"]:
        step["status"] = "done"
        next_idx = idx + 1
        failures = 0
        _emit(state, "✅", f"Step {idx+1} succeeded.")
        log_ev = f"Step {idx+1} succeeded"
    else:
        failures += 1
        err_msg = step.get('result', '')
        _emit(state, "❌", f"Step {idx+1} failed ({failures} consecutive).\n[dim]Error: {err_msg}[/dim]")
        log_ev = f"Step {idx+1} failed"
        
        router = get_llm_router()
        llm = router.get("strong")
        
        prompt = f"""Step execution failed.
Skill: {step.get('skill_name')}
Args: {step.get('skill_args')}
Error: {step.get('result')}

Analyze the error and output ONLY a JSON object with:
"decision": "retry" (if it was a transient error or syntax fix), "replan" (if fundamentally flawed), or "human" (if impossible to proceed).
"reason": short string explaining why.
"""
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            content = response.content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
            decision = data.get("decision", "human")
            
            if decision == "human":
                needs_human = True
            elif decision == "retry":
                pass 
            elif decision == "replan":
                update["needs_replan"] = True
        except Exception:
            if failures >= state.get("max_consecutive_failures", 3):
                needs_human = True
                
        # If the LLM failed to parse or decided human was needed, we don't set replan here
        # But if it decided replan, it is caught above

    update["current_step_index"] = next_idx
    update["consecutive_failures"] = failures
    update["needs_human_input"] = needs_human
    
    # 5.8 Wire up SessionManager checkpoint
    sess_id = state.get("session_id")
    if sess_id:
        chk_state = dict(state)
        chk_state.update(update)
        try:
            get_session_manager().checkpoint(sess_id, chk_state)
        except Exception:
            pass
            
    return update

def human_intervene_node(state: AgentTaskState) -> Dict[str, Any]:
    _emit(state, "✋", "Waiting for human intervention...")
    response = interrupt("Agent specifies it needs your help to proceed. Please provide guidance:")
    
    return {
        "needs_human_input": False,
        "consecutive_failures": 0,
        "human_response": str(response),
        "execution_log": _append_log(state, "👤", "Human intervened", str(response))
    }

def finalize_node(state: AgentTaskState) -> Dict[str, Any]:
    _emit(state, "🏁", "Finalizing task...")
    
    sess_id = state.get("session_id")
    if sess_id:
        sandbox = SandboxContext(sess_id)
        out_path = sandbox.data_folder / "output" / f"summary_{sess_id}.txt"
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(f"Goal: {state.get('goal')}\\nStatus: Completed\\n")
        except Exception:
            pass

    log = _append_log(state, "🏁", "Task finalized")
    return {
        "task_status": "completed",
        "execution_log": log
    }
