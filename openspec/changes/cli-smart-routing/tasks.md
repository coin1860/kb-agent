## 1. Session History Infrastructure

- [ ] 1.1 In `SkillShell.__init__`, add `self.session_messages: list[dict[str, str]] = []` alongside (or replacing) `session_history`
- [ ] 1.2 In `SkillShell._run_command()`, after result is obtained from either skill path or RAG path, append `{"role": "user", "content": command}` and `{"role": "assistant", "content": result}` to `session_messages`
- [ ] 1.3 Add history truncation: pass only the most recent 20 entries (`session_messages[-20:]`) to RAG graph calls

## 2. RAG Graph Bridge

- [ ] 2.1 In `SkillShell.__init__`, import `compile_graph` from `kb_agent.agent.graph` and store as `self._rag_graph = compile_graph()`
- [ ] 2.2 Add `SkillShell._run_rag_query(command: str, session_messages: list) -> str` method that builds `AgentState` with `query`, `messages`, `status_callback`, and invokes `self._rag_graph.invoke()`
- [ ] 2.3 In `_run_rag_query`, wire `status_callback = lambda emoji, msg: self.renderer.print_info(f"{emoji} {msg}")` into the initial state
- [ ] 2.4 Extract `state["final_answer"]` from the RAG graph result and return it as a string

## 3. Routing Fork in shell.py

- [ ] 3.1 In `SkillShell._run_command()`, after `route_intent()` returns `free_agent`, call `self._run_rag_query(resolved, self.session_messages[-20:])` instead of `generate_plan → execute_plan`
- [ ] 3.2 Ensure the skill path (when `route.route == "skill"`) continues unchanged: `generate_plan → approval_gate → execute_plan`
- [ ] 3.3 Remove the "🤖 Free-agent mode — generating plan..." info message for free_agent path (replaced by RAG status callbacks)
- [ ] 3.4 Ensure result from `_run_rag_query` is passed to `renderer.print_result()` and appended to `session_messages`

## 4. Testing

- [ ] 4.1 Write unit test: `test_free_agent_routes_to_rag_graph` — mock `_rag_graph.invoke()`, verify it's called when `route_intent` returns `free_agent`
- [ ] 4.2 Write unit test: `test_skill_path_unchanged` — mock `generate_plan`, verify it's still called when skill is matched
- [ ] 4.3 Write unit test: `test_session_messages_appended` — verify `session_messages` grows correctly after each command
- [ ] 4.4 Write unit test: `test_session_history_truncation` — verify only last 20 entries are passed when history exceeds 20
- [ ] 4.5 Manual smoke test: start kb-cli, type "hi" → should get direct LLM response without plan table
- [ ] 4.6 Manual smoke test: ask a knowledge question → should see RAG status callbacks (🧠, 🔍, ✨) and synthesized answer
- [ ] 4.7 Manual smoke test: ask about a Jira ticket → verify jira_fetch is called via RAG plan node
- [ ] 4.8 Manual smoke test: use a skill (if any loaded) → verify plan table + approval gate still appear
