from pathlib import Path
from kb_agent.config import load_settings, settings
from kb_agent.skill.session import Session
from kb_agent.skill.planner import generate_unified_plan, decide_next_step
from langchain_openai import ChatOpenAI

load_settings()
api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else "local"
model_name = settings.llm_model or "gpt-4o"
if model_name.startswith("groq-com/") or model_name.startswith("groq/"):
    model_name = model_name.split("/", 1)[-1]
llm = ChatOpenAI(api_key=api_key, base_url=str(settings.llm_base_url) if settings.llm_base_url else None, model=model_name, temperature=0.2)

session = Session()
session.setup_dirs(Path("out"), Path("pycode"), Path("tmp"))

cmd = "用python 计算2x2的结果， 输出到result.txt中"
plan = generate_unified_plan(cmd, session, {}, llm)
print("\n--- Unified Plan ---")
print("Route:", plan.route)
print("Summary:", plan.summary)
for i, ms in enumerate(plan.milestones):
    print(f"MS {i+1}: {ms.goal}")
    print(f"  Expected: {ms.expected_output}")
    print("  Deciding step 1:")
    ans = decide_next_step(cmd, session, llm, milestone_goal=ms.goal)
    print("  => Action:", ans.get("action"))
    if ans.get("action") == "call_tool":
        print("  => Tool:", ans.get("tool"))
    else:
        print("  => Answer:", ans.get("answer"))

