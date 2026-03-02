import os
import kb_agent.config as config
from kb_agent.config import load_settings, save_settings, Settings
from kb_agent.engine import Engine
from kb_agent.agent.nodes import _build_llm

load_settings()
print("Initial model:", config.settings.llm_model)
llm1 = _build_llm()
print("LLM1 model:", llm1.model_name)

# Simulate TUI update
new_data = config.settings.model_dump(mode='json')
new_data["llm_model"] = "gpt-4o-mini-test"
new_settings = Settings(**new_data)
save_settings(new_settings)
load_settings()

print("After update, config model:", config.settings.llm_model)
llm2 = _build_llm()
print("LLM2 model:", llm2.model_name)
