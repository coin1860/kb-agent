"""
Graph node functions for the agentic RAG workflow.

Nodes:
    plan_node      – LLM decides which tools to call next.
    tool_node      – Executes the tool calls selected by the planner.
    evaluate_node  – LLM judges whether gathered context is sufficient.
    synthesize_node – LLM generates the final answer from context only.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

import kb_agent.config as config
from kb_agent.security import Security
from kb_agent.audit import log_audit, log_llm_response

from .state import AgentState
from .tools import ALL_TOOLS

logger = logging.getLogger("kb_agent_audit")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Regex to strip <think>...</think> tags (Qwen3, DeepSeek R1, etc.)
_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> reasoning blocks from model output."""
    return _THINK_TAG_RE.sub("", text).strip()


def _emit(state: AgentState, emoji: str, msg: str):
    """Call the TUI status callback if present."""
    cb = state.get("status_callback")
    if cb:
        cb(emoji, msg)


def _build_llm() -> ChatOpenAI:
    """Construct a ChatOpenAI that points at the user-configured provider."""
    settings = config.settings
    if not settings:
        raise ValueError("Settings not initialized.")

    model_name = settings.llm_model
    if model_name.startswith("groq-com/"):
        model_name = model_name.removeprefix("groq-com/")
    elif model_name.startswith("groq/"):
        model_name = model_name.removeprefix("groq/")

    return ChatOpenAI(
        api_key=settings.llm_api_key.get_secret_value(),
        base_url=str(settings.llm_base_url),
        model=model_name,
        temperature=0.0,
    )


def _history_to_messages(history: list[dict[str, str]]) -> list:
    """Convert plain dicts ``{role, content}`` to LangChain message objects."""
    out: list = []
    for m in history:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            out.append(SystemMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        else:
            out.append(HumanMessage(content=content))
    return out


def _extract_json(text: str) -> Any:
    """Best-effort extraction of JSON from LLM output.

    Handles: raw JSON, ```json fences, leading/trailing prose,
    and <think> tags from reasoning models.
    """
    # 1. Strip think tags
    cleaned = _strip_think_tags(text)

    # 2. Try direct parse
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        pass

    # 3. Strip markdown code fences
    if "```" in cleaned:
        # Extract content between first pair of ```
        parts = cleaned.split("```")
        if len(parts) >= 3:
            fenced = parts[1]
            # Remove language identifier (e.g., "json\n")
            if fenced.startswith(("json", "JSON")):
                fenced = fenced[4:]
            try:
                return json.loads(fenced.strip())
            except (json.JSONDecodeError, ValueError):
                pass

    # 4. Find first [ or { and try to parse from there
    for start_char, end_char in [("[", "]"), ("{", "}")]:
        start = cleaned.find(start_char)
        if start == -1:
            continue
        # Find matching close
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == start_char:
                depth += 1
            elif cleaned[i] == end_char:
                depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start: i + 1])
                except (json.JSONDecodeError, ValueError):
                    break

    return None


def _extract_tools_from_text(raw_response: str, query: str) -> list[dict[str, Any]]:
    """Extract tool calls from the AI's natural language response.

    When JSON parsing fails, the LLM has still decided which tools to use
    in its reasoning text (e.g. inside <think> blocks or in prose).
    This function scans for mentioned tool names and builds calls from them.

    The AI drives tool selection — we just parse what it already decided.
    """
    # Use the FULL response including <think> tags — the AI's reasoning
    # reveals its intent even if the final output is malformed.
    text = raw_response.lower()

    # Valid tool names → argument key mapping
    tool_arg_map = {
        "grep_search": {"key": "query", "value": query},
        "vector_search": {"key": "query", "value": query},
        "read_file": {"key": "file_path", "value": query},
        "graph_related": {"key": "entity_id", "value": query},
        "jira_fetch": {"key": "issue_key", "value": query},
        "confluence_fetch": {"key": "page_id", "value": query},
        "web_fetch": {"key": "url", "value": query},
    }

    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    for tool_name, arg_info in tool_arg_map.items():
        if tool_name in text and tool_name not in seen:
            # Try to extract a quoted argument near the tool name mention
            arg_value = arg_info["value"]
            # Look for patterns like: tool_name("some arg") or tool_name(query="some arg")
            pattern = rf'{tool_name}\s*\(\s*(?:\w+\s*=\s*)?["\']([^"\']+)["\']'
            match = re.search(pattern, raw_response, re.IGNORECASE)
            if match:
                arg_value = match.group(1)

            found.append({
                "name": tool_name,
                "args": {arg_info["key"]: arg_value},
            })
            seen.add(tool_name)

    return found


# ---------------------------------------------------------------------------
# Tool descriptions for the planner prompt
# ---------------------------------------------------------------------------

TOOL_DESCRIPTIONS = """Available tools:
1. grep_search(query: str) — Keyword search on indexed Markdown files using ripgrep. Best for exact terms, ticket IDs, config names. Returns JSON array of {file_path, line, content}.
2. vector_search(query: str) — Semantic similarity search using ChromaDB embeddings. Best for conceptual/fuzzy queries. Returns JSON array of {id, content, metadata, score}.
3. read_file(file_path: str) — Read the full content of a document by its file path. Use after search tools find relevant files.
4. graph_related(entity_id: str) — Find related entities in the Knowledge Graph (e.g. parent Jira ticket, linked pages). Input is an entity ID like 'PROJ-123' or 'document.md'.
5. jira_fetch(issue_key: str) — Fetch a Jira issue by key (e.g. 'PROJ-123') or search text. Returns issue details.
6. confluence_fetch(page_id: str) — Fetch a Confluence page by ID or search text.
7. web_fetch(url: str) — Fetch a specific web page by URL and convert to Markdown. The 'url' parameter MUST be a valid HTTP/HTTPS URL (e.g., 'https://domain.com'). Do NOT use this tool for natural language web searches."""


# ---------------------------------------------------------------------------
# Node: PLAN
# ---------------------------------------------------------------------------

PLAN_SYSTEM = (
    "You are a retrieval planner for a Knowledge Base Agent. "
    "Your job is to decide which tools to call next to find evidence.\n\n"
    + TOOL_DESCRIPTIONS + "\n\n"
    "RULES:\n"
    "1. You must NEVER answer the question yourself — only choose tools.\n"
    "2. Output ONLY a JSON array of tool calls. Example:\n"
    '   [{"name": "grep_search", "args": {"query": "login flow"}}, '
    '{"name": "vector_search", "args": {"query": "authentication process"}}]\n'
    "3. Start with grep_search for exact keywords. If that's not enough, add vector_search.\n"
    "4. If the question mentions a Jira ticket (e.g. PROJ-123), use jira_fetch or graph_related.\n"
    "5. After search returns file paths, use read_file to get full content.\n"
    "6. Avoid repeating tool calls with the same arguments.\n"
    "7. On subsequent rounds, try DIFFERENT search keywords, or use "
    "read_file on files discovered in previous rounds.\n"
    "8. Output ONLY the JSON array, no other text, no explanation.\n"
)


def plan_node(state: AgentState) -> dict[str, Any]:
    """LLM-backed planner that selects which tools to invoke next."""
    iteration = state.get("iteration", 0)
    _emit(state, "🧠", f"Planning: deciding which tools to use (round {iteration + 1})...")
    log_audit("agent_plan_start", {
        "query": state["query"],
        "iteration": iteration,
        "context_count": len(state.get("context") or []),
    })

    llm = _build_llm()

    messages: list = [SystemMessage(content=PLAN_SYSTEM)]

    # Inject conversation history
    history = state.get("messages") or []
    messages.extend(_history_to_messages(history))

    # Show what we already have
    existing_context = state.get("context") or []
    tool_history = state.get("tool_history") or []

    if existing_context:
        # Summarize previous tool calls so planner can try something different
        prev_calls = ", ".join(
            f"{t['tool']}({t['input']})" for t in tool_history[-5:]
        )
        # Show short snippet of what was found
        ctx_snippets = []
        for c in existing_context[-3:]:
            snippet = c[:200] + "..." if len(c) > 200 else c
            ctx_snippets.append(snippet)
        ctx_summary = "\n".join(ctx_snippets)

        messages.append(
            SystemMessage(
                content=(
                    f"Previous tool calls: {prev_calls}\n\n"
                    f"Evidence found so far:\n{ctx_summary}\n\n"
                    "The evidence was deemed insufficient. "
                    "You MUST try DIFFERENT tools or DIFFERENT search terms. "
                    "If previous searches found file paths, use read_file. "
                    "If grep didn't work, try vector_search with different wording. "
                    "Do NOT repeat the same calls."
                )
            )
        )

    messages.append(HumanMessage(content=state["query"]))

    response: AIMessage = llm.invoke(messages)
    raw_response = response.content.strip()

    log_audit("agent_plan_raw_response", {"raw": raw_response[:500]})

    # --- Extract tool calls ---
    tool_calls = []

    # Try native tool_calls first (OpenAI, etc.)
    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            tool_calls.append({"name": tc["name"], "args": tc["args"]})
        log_audit("agent_plan_parsed", {
            "method": "native_tool_calls",
            "tool_calls": [t["name"] for t in tool_calls],
        })
    else:
        # Parse from text — handles <think> tags, markdown fences, etc.
        parsed = _extract_json(raw_response)

        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict) and "name" in item:
                    tool_calls.append({
                        "name": item["name"],
                        "args": item.get("args", {}),
                    })
        elif isinstance(parsed, dict) and "name" in parsed:
            tool_calls.append({
                "name": parsed["name"],
                "args": parsed.get("args", {}),
            })

        if tool_calls:
            log_audit("agent_plan_parsed", {
                "method": "json_extract",
                "tool_calls": [t["name"] for t in tool_calls],
            })
        else:
            # JSON failed — extract tool intent from the LLM's own text
            # The AI already decided which tools to use in its reasoning;
            # we just need to pick up tool names from its natural language response.
            tool_calls = _extract_tools_from_text(raw_response, state["query"])
            if tool_calls:
                log_audit("agent_plan_parsed", {
                    "method": "text_intent_extraction",
                    "tool_calls": [t["name"] for t in tool_calls],
                })
                _emit(state, "🔄", f"Extracted intent from AI reasoning: {', '.join(t['name'] for t in tool_calls)}")
            else:
                log_audit("agent_plan_parse_failed", {
                    "raw_after_strip": _strip_think_tags(raw_response)[:500],
                })

    # Final fallback: if still no tool calls, default to grep + vector
    if not tool_calls and not existing_context:
        query = state["query"]
        tool_calls = [
            {"name": "grep_search", "args": {"query": query}},
            {"name": "vector_search", "args": {"query": query}},
        ]
        log_audit("agent_plan_fallback", {
            "reason": "first_iteration_no_tools",
            "tool_calls": [t["name"] for t in tool_calls],
        })

    # Fallback for retry rounds: try to read files from previous search results
    if not tool_calls and existing_context:
        read_files = _extract_file_paths_from_context(existing_context)
        already_read = set(state.get("files_read") or [])
        new_files = [f for f in read_files if f not in already_read]

        if new_files:
            tool_calls = [
                {"name": "read_file", "args": {"file_path": f}}
                for f in new_files[:3]
            ]
            log_audit("agent_plan_fallback", {
                "reason": "retry_round_read_discovered_files",
                "files": new_files[:3],
            })
        else:
            tool_calls = [
                {"name": "vector_search", "args": {"query": state["query"]}},
            ]
            log_audit("agent_plan_fallback", {
                "reason": "retry_round_vector_search",
            })

    _emit(state, "📋", f"Plan: {', '.join(t['name'] for t in tool_calls) if tool_calls else 'no tools selected'}")

    return {"pending_tool_calls": tool_calls}


def _extract_file_paths_from_context(context: list[str]) -> list[str]:
    """Extract file paths from tool results for read_file follow-up."""
    paths = []
    for item in context:
        # Look for file_path fields in JSON results
        for match in re.finditer(r'"file_path"\s*:\s*"([^"]+)"', item):
            paths.append(match.group(1))
        # Look for .md file references
        for match in re.finditer(r'[\w/.-]+\.md', item):
            paths.append(match.group(0))
    # De-duplicate while preserving order
    seen = set()
    unique = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


# ---------------------------------------------------------------------------
# Node: TOOL EXECUTOR
# ---------------------------------------------------------------------------

def tool_node(state: AgentState) -> dict[str, Any]:
    """Execute tool calls from the planner."""
    pending = state.get("pending_tool_calls") or []

    log_audit("tool_node_start", {
        "pending_count": len(pending),
        "tools": [t["name"] for t in pending],
    })

    if not pending:
        _emit(state, "⚠️", "No tools to execute")
        log_audit("tool_node_skip", {"reason": "no_pending_tool_calls"})
        return {
            "context": state.get("context", []),
            "tool_history": state.get("tool_history", []),
            "pending_tool_calls": [],
        }

    tool_map = {t.name: t for t in ALL_TOOLS}
    new_context = list(state.get("context") or [])
    new_tool_history = list(state.get("tool_history") or [])
    files_read = list(state.get("files_read") or [])

    for tc in pending:
        tool_name = tc["name"]
        tool_args = tc.get("args", {})

        args_str = ", ".join(f"{k}={v!r}" for k, v in tool_args.items())
        _emit(state, "🔍", f"Executing: {tool_name}({args_str})")

        tool_fn = tool_map.get(tool_name)
        if tool_fn is None:
            result = f"Unknown tool: {tool_name}"
            _emit(state, "❌", f"Unknown tool: {tool_name}")
        else:
            try:
                result = tool_fn.invoke(tool_args)
            except Exception as e:
                result = f"Tool error ({tool_name}): {e}"
                _emit(state, "❌", f"Tool error: {tool_name} — {e}")

        result_str = str(result)
        result_preview = result_str[:200] + "..." if len(result_str) > 200 else result_str

        log_audit("tool_call_result", {
            "tool": tool_name,
            "args": tool_args,
            "result_length": len(result_str),
            "result_preview": result_preview,
        })

        _emit(state, "📄", f"Got {len(result_str)} chars from {tool_name}")

        if tool_name == "read_file" and "file_path" in tool_args:
            files_read.append(tool_args["file_path"])

        new_context.append(f"[{tool_name}] {result_str}")
        new_tool_history.append({
            "tool": tool_name,
            "input": tool_args,
            "output": result_str[:500],
        })

    log_audit("tool_node_complete", {
        "tools_executed": len(pending),
        "total_context_items": len(new_context),
    })

    return {
        "context": new_context,
        "tool_history": new_tool_history,
        "files_read": files_read,
        "pending_tool_calls": [],
    }


# ---------------------------------------------------------------------------
# Node: EVALUATE
# ---------------------------------------------------------------------------

EVALUATE_SYSTEM = (
    "You are an evidence evaluator. Given the user's question and the "
    "evidence gathered so far, decide if the evidence is SUFFICIENT to "
    "answer the question accurately.\n\n"
    "RULES:\n"
    "1. The answer must come ONLY from the evidence — never from your own knowledge.\n"
    "2. If the evidence contains relevant information that addresses the "
    "user's question, respond with: {\"sufficient\": true}\n"
    "3. If the evidence is missing, irrelevant, or incomplete, respond "
    "with: {\"sufficient\": false, \"reason\": \"<brief explanation>\"}\n"
    "4. Output ONLY valid JSON, nothing else. No thinking, no explanation.\n"
)


def evaluate_node(state: AgentState) -> dict[str, Any]:
    """LLM judges whether the accumulated context can answer the query."""
    iteration = state.get("iteration", 0) + 1
    _emit(state, "🤔", f"Evaluating: checking if evidence is sufficient (round {iteration})...")

    context_items = state.get("context") or []

    log_audit("evaluate_start", {
        "iteration": iteration,
        "context_count": len(context_items),
        "total_chars": sum(len(c) for c in context_items),
    })

    # If no context at all → clearly insufficient
    if not context_items:
        log_audit("evaluate_result", {
            "iteration": iteration,
            "sufficient": False,
            "reason": "no context gathered",
        })
        _emit(state, "⚠️", "No evidence found yet")
        return {"iteration": iteration, "is_sufficient": False}

    llm = _build_llm()

    messages: list = [SystemMessage(content=EVALUATE_SYSTEM)]
    history = state.get("messages") or []
    messages.extend(_history_to_messages(history))

    ctx_text = "\n---\n".join(context_items[-10:])
    messages.append(
        HumanMessage(
            content=(
                f"User question: {state['query']}\n\n"
                f"Evidence gathered:\n{ctx_text}"
            )
        )
    )

    response = llm.invoke(messages)
    raw = response.content.strip()

    log_audit("evaluate_raw_response", {"raw": raw[:500]})

    # Strip think tags and parse
    cleaned = _strip_think_tags(raw)
    parsed = _extract_json(cleaned)

    if isinstance(parsed, dict):
        sufficient = parsed.get("sufficient", False)
        reason = parsed.get("reason", "")
    else:
        # JSON parse failed — fallback heuristic:
        # If we have meaningful context (>100 chars of actual content),
        # assume sufficient rather than wasting retries
        total_content_chars = sum(len(c) for c in context_items)
        if total_content_chars > 100:
            sufficient = True
            reason = f"Evaluator parse failed but {total_content_chars} chars of context exists — treating as sufficient"
            log_audit("evaluate_parse_fallback", {
                "reason": reason,
                "raw_cleaned": cleaned[:300],
            })
        else:
            sufficient = False
            reason = f"Evaluator parse failed and only {total_content_chars} chars of context"

    log_audit("evaluate_result", {
        "iteration": iteration,
        "sufficient": sufficient,
        "reason": reason,
    })

    if sufficient:
        _emit(state, "✅", "Evidence is sufficient!")
    else:
        _emit(state, "🔄", f"Need more evidence: {reason[:80]}")

    return {"iteration": iteration, "is_sufficient": sufficient}


# ---------------------------------------------------------------------------
# Node: SYNTHESIZE
# ---------------------------------------------------------------------------

SYNTHESIZE_SYSTEM = (
    "You are a helpful knowledge base assistant. Answer the user's question "
    "based ONLY on the provided context and conversation history.\n\n"
    "STRICT RULES:\n"
    "1. You must ONLY use information from the 'Context' section and the "
    "conversation history. Do NOT use your own knowledge.\n"
    "2. If the context does not contain relevant information to answer the "
    "question, you MUST respond with:\n"
    "   'I couldn't find relevant information in the knowledge base to "
    "answer this question.'\n"
    "3. Be precise, professional, and well-structured.\n"
    "4. Cite the source document when possible.\n"
)


def synthesize_node(state: AgentState) -> dict[str, Any]:
    """Generate the final answer grounded strictly in context."""
    _emit(state, "✨", "Synthesizing answer from evidence...")

    context_items = state.get("context") or []

    log_audit("synthesize_start", {
        "context_count": len(context_items),
        "total_chars": sum(len(c) for c in context_items),
    })

    llm = _build_llm()

    messages: list = [SystemMessage(content=SYNTHESIZE_SYSTEM)]

    history = state.get("messages") or []
    messages.extend(_history_to_messages(history))

    ctx_text = "\n---\n".join(context_items) if context_items else "(No evidence was found.)"

    messages.append(
        HumanMessage(
            content=f"Context:\n{ctx_text}\n\nQuestion: {state['query']}"
        )
    )

    response = llm.invoke(messages)
    raw_answer = _strip_think_tags(response.content)

    log_audit("synthesize_result", {
        "answer_length": len(raw_answer),
        "answer_preview": raw_answer[:300],
    })
    log_llm_response(state["query"], raw_answer)

    final_answer = Security.mask_sensitive_data(raw_answer)

    return {"final_answer": final_answer}
