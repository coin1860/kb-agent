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
        temperature=0.2,
    )


def _history_to_messages(history: list[dict[str, str]]) -> list:
    """Convert plain dicts ``{role, content}`` to LangChain message objects."""
    out: list = []
    
    # Regex to aggressively strip out LLM Usage stats blocks to prevent hallucination
    stats_pattern = re.compile(
        r'''(?:^|\n)(?:\-\-\-\n)?(?:📊\s*)?\*\*(?:LLM\s*)?Usage\s*Stats:?\*\*.*?(?=\n\n|\Z)''', 
        re.DOTALL | re.IGNORECASE
    )
    
    for m in history:
        role = m.get("role", "user")
        content = m.get("content", "")
        
        if role == "assistant":
            # Strip out stats so the model doesn't mimic them
            content = stats_pattern.sub("", content).strip()
            
            # Simple fallback line-by-line removal in case the regex misses some edge cases
            lines = content.split('\n')
            filtered_lines = []
            in_stats_block = False
            for line in lines:
                if 'LLM Usage Stats:' in line or '📊' in line and 'Usage Stats' in line:
                    in_stats_block = True
                    # Also remove the preceding '---' if it's the last line we added
                    if filtered_lines and filtered_lines[-1].strip() == '---':
                        filtered_lines.pop()
                    continue
                if in_stats_block:
                    if not line.strip() or line.strip().startswith('-'):
                        continue
                    else:
                        in_stats_block = False
                        
                if not in_stats_block:
                    filtered_lines.append(line)
            content = '\n'.join(filtered_lines).strip()
            
            # Also clean up trailing semantic separators that may have been left alone
            if content.endswith('---'):
                content = content[:-3].strip()
                
            out.append(AIMessage(content=content))
        elif role == "system":
            out.append(SystemMessage(content=content))
        else:
            out.append(HumanMessage(content=content))
            
    return out


def _invoke_and_track(llm: ChatOpenAI, messages: list, state: AgentState) -> AIMessage:
    """Wrapper around `llm.invoke` that tracks LLM usage in the AgentState."""
    response: AIMessage = llm.invoke(messages)

    # Increment call count
    state["llm_call_count"] = state.get("llm_call_count", 0) + 1

    # Extract tokens safely
    metadata = getattr(response, "usage_metadata", {}) or {}
    if not metadata and hasattr(response, "response_metadata"):
        metadata = response.response_metadata.get("token_usage", {})

    prompt_tokens = metadata.get("input_tokens", metadata.get("prompt_tokens", 0))
    completion_tokens = metadata.get("output_tokens", metadata.get("completion_tokens", 0))
    total_tokens = metadata.get("total_tokens", prompt_tokens + completion_tokens)

    state["llm_prompt_tokens"] = state.get("llm_prompt_tokens", 0) + prompt_tokens
    state["llm_completion_tokens"] = state.get("llm_completion_tokens", 0) + completion_tokens
    state["llm_total_tokens"] = state.get("llm_total_tokens", 0) + total_tokens

    return response


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


def _is_tool_applicable(tool_name: str, query: str) -> bool:
    """Validate if a tool is applicable to the given query."""
    if tool_name == "jira_fetch":
        return bool(re.search(r'[A-Z]+-\d+', query))
    if tool_name == "jira_jql":
        return True
    if tool_name == "confluence_fetch":
        return bool(re.search(r'confluence|wiki|page.?\d+', query, re.IGNORECASE))
    if tool_name == "web_fetch":
        return bool(re.search(r'https?://', query))
    return True


def _build_tool_args(tool_name: str, query: str) -> dict[str, str] | None:
    """Build tool arguments based on the tool type and query.
    Returns None if the tool should not be called."""
    query_str = query
    if tool_name in ("grep_search", "vector_search", "local_file_qa"):
        return {"query": query_str}
        
    if tool_name == "read_file":
        return {"file_path": query_str}
    if tool_name == "graph_related":
        return {"entity_id": query_str}
    if tool_name == "jira_fetch":
        match = re.search(r'([A-Z]+-\d+)', query_str)
        if match:
            return {"issue_key": match.group(1)}
        return None
    if tool_name == "jira_jql":
        return {"query": query_str}
    if tool_name == "confluence_fetch":
        match = re.search(r'(\d{5,})', query)
        if match:
            return {"page_id": match.group(1)}
        return None
    if tool_name == "web_fetch":
        match = re.search(r'(https?://[^\s]+)', query_str)
        if match:
            return {"url": match.group(1)}
        return None
    return {"query": query_str}


def _extract_tools_from_text(
    raw_response: str, query: str, allowed_tools: list[str] | None = None
) -> list[dict[str, Any]]:
    """Extract tool calls from the AI's natural language response.

    When JSON parsing fails, the LLM has still decided which tools to use
    in its reasoning text (e.g. inside <think> blocks or in prose).
    This function scans for mentioned tool names and builds calls from them.

    The AI drives tool selection — we just parse what it already decided.
    """
    # Use the FULL response including <think> tags — the AI's reasoning
    # reveals its intent even if the final output is malformed.
    text = raw_response.lower()

    # Valid tool names mapping limit
    valid_tools = [
        # "grep_search", # TEMPORARILY DISABLED
        "vector_search", "read_file",
        "graph_related", "jira_fetch", "jira_jql", "confluence_fetch",
        "web_fetch", "local_file_qa"
    ]

    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    for tool_name in valid_tools:
        if allowed_tools is not None and tool_name not in allowed_tools:
            continue
            
        if not _is_tool_applicable(tool_name, query):
            continue
            
        if tool_name in text and tool_name not in seen:
            tool_args = _build_tool_args(tool_name, query)
            if tool_args is None:
                continue
                
            # Try to extract a quoted argument near the tool name mention
            # Look for patterns like: tool_name("some arg") or tool_name(query="some arg")
            pattern = rf'{tool_name}\s*\(\s*(?:\w+\s*=\s*)?["\']([^"\']+)["\']'
            match = re.search(pattern, raw_response, re.IGNORECASE)
            
            # If we extracted an argument value AND it wasn't specially parsed by _build_tool_args
            # (e.g. for simple query search tools), update it.
            if match and tool_name in ("grep_search", "vector_search", "read_file", "graph_related"):
                tool_args_key = list(tool_args.keys())[0] # The key (e.g. 'query' or 'file_path')
                tool_args = {tool_args_key: match.group(1)}

            found.append({
                "name": tool_name,
                "args": tool_args,
            })
            seen.add(tool_name)

    return found


# ---------------------------------------------------------------------------
# Tool descriptions for the planner prompt
# ---------------------------------------------------------------------------

TOOL_DESCRIPTIONS = """Available tools:
1. vector_search(query: str) — Semantic similarity search using ChromaDB embeddings. Best for conceptual/fuzzy queries. Returns JSON array of {id, content, metadata, score}.
3. read_file(file_path: str, start_line: int=None, end_line: int=None) — Read the full content of a document, or a specific line range. Use after search tools find relevant files.
4. graph_related(entity_id: str) — Find related entities in the Knowledge Graph (e.g. parent Jira ticket, linked pages). Input is an entity ID like 'PROJ-123' or 'document.md'.
5. jira_fetch(issue_key: str) — Fetch a Jira issue by key (e.g. 'PROJ-123'). Returns issue details.
6. jira_jql(query: str) — Convert natural language to Jira JQL and search. Use for semantic queries like "my unresolved tasks".
7. confluence_fetch(page_id: str) — Fetch a Confluence page by ID or search text.
8. web_fetch(url: str) — Fetch a specific web page by URL and convert to Markdown. The 'url' parameter MUST be a valid HTTP/HTTPS URL (e.g., 'https://domain.com'). Do NOT use this tool for natural language web searches."""


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
    '   [{"name": "vector_search", "args": {"query": "login flow"}}, '
    '{"name": "read_file", "args": {"file_path": "docs/auth.md"}}]\n'
    "3. Start with vector_search for Q&A. If the question is complex or conceptual, YOU MUST issue multiple vector_search queries in parallel.\n"
    "   **CRITICAL EXCEPTION**: If the user's INTENT is to find/list files (e.g. '查找文件', 'find documents about X'), you MUST use local_file_qa INSTEAD of vector_search to avoid duplicate chunks.\n"
    "4. If the question mentions a Jira ticket (e.g. PROJ-123), use jira_fetch or graph_related.\n"
    "5. After search returns file paths, use read_file to get full content.\n"
    "6. **INDEX RESOLUTION**: When a user refers to a file by index (e.g. 'Summarize 1', 'Tell me about file 2'), you MUST:\n"
    "   a) Look at the PREVIOUS ASSISTANT MESSAGE in the conversation history.\n"
    "   b) Find the line starting with that number (e.g., '1, /path/to/file.md').\n"
    "   c) Extract the EXACT file path as printed (e.g., '/path/to/file.md').\n"
    "   d) Call read_file(file_path=resolved_path).\n"
    "7. Do NOT call local_file_qa again if the user is asking to summarize a file from a list you just provided.\n"
    "8. Avoid repeating tool calls with the same arguments.\n"
    "9. On subsequent rounds, you will be given 'Context File Hints' (like file paths or Jira IDs) found in previous searches. You MUST prioritize using read_file, jira_fetch, or confluence_fetch on these hints BEFORE trying new vector_search keywords.\n"
    "   - Only rephrase vector searches if no hints exist or hints proved useless.\n"
)

DECOMPOSE_SYSTEM = (
    "You are a query analysis expert. Your job is to analyze the user's question and decide how to search the knowledge base.\n\n"
    "RULES:\n"
    "1. If the user asks about a specific Jira ticket (e.g., FSR-123, WCL-456, PROJ-789), output a 'direct' action for jira_fetch.\n"
    "2. If the user asks to SEARCH/QUERY/LIST Jira issues by criteria (e.g. 'my tasks', 'unresolved bugs', '本周更新的任务'), output a 'direct' action for jira_jql.\n"
    "3. If the user asks about a specific Confluence page ID (e.g., 12345678), output a 'direct' action for confluence_fetch.\n"
    "4. For all other questions, output a 'decompose' action that splits the question into exactly 3 diverse, atomic sub-queries for parallel vector search.\n"
    "   - Sub-queries should capture different aspects, synonyms, or keywords of the original question.\n"
    "   - If the question is very simple, use slightly different phrasing for the 3 sub-queries to maximize recall.\n"
    "   - MUST KEEP THE ORIGINAL LANGUAGE. DO NOT TRANSLATE TO ENGLISH IF THE QUERY IS IN CHINESE.\n"
    "4. Output ONLY valid JSON matching this schema:\n"
    '   - For direct: {"action": "direct", "tool": "jira_fetch", "args": {"issue_key": "FSR-123"}}\n'
    '   - For direct: {"action": "direct", "tool": "jira_jql", "args": {"query": "my unresolved tasks"}}\n'
    '   - For decompose: {"action": "decompose", "sub_queries": ["query 1", "query 2", "query 3"]}\n'
    "5. Do NOT output any other text or explanation."
)

def _decompose_query(query: str, state: AgentState) -> list[dict[str, Any]]:
    """Use LLM to decompose a query into sub-queries or route to a specific tool."""
    _emit(state, "🧠", "Analyzing query for decomposition or direct routing...")
    
    llm = _build_llm()
    messages = [
        SystemMessage(content=DECOMPOSE_SYSTEM),
        HumanMessage(content=query)
    ]
    
    response = _invoke_and_track(llm, messages, state)
    raw = _strip_think_tags(response.content.strip())
    
    log_audit("agent_decompose_response", {"raw": raw[:200]})
    
    parsed = _extract_json(raw)
    
    if isinstance(parsed, dict):
        action = parsed.get("action")
        if action == "direct" and "tool" in parsed and "args" in parsed:
            _emit(state, "🧭", f"LLM Routing: detected exact intent, routing to {parsed['tool']}.")
            return [{"name": parsed["tool"], "args": parsed["args"]}]
        elif action == "decompose" and isinstance(parsed.get("sub_queries"), list):
            sub_queries = parsed["sub_queries"][:3] # cap at 3
            if sub_queries:
                _emit(state, "🔀", f"Decomposed into {len(sub_queries)} sub-queries for parallel search.")
                return [{"name": "vector_search", "args": {"query": sq}} for sq in sub_queries]
                
    # Fallback if parsing fails or unexpected format
    _emit(state, "⚠️", "Decomposition parse failed, falling back to original query.")
    return [{"name": "vector_search", "args": {"query": query}}]


def plan_node(state: AgentState) -> dict[str, Any]:
    """LLM-backed planner that selects which tools to invoke next."""
    iteration = state.get("iteration", 0)
    _emit(state, "🧠", f"Planning: deciding which tools to use (round {iteration + 1})...")
    log_audit("agent_plan_start", {
        "query": state["query"],
        "iteration": iteration,
        "context_count": len(state.get("context") or []),
    })

    existing_context = state.get("context") or []

    # --- NEW RULE/LLM ROUTING FOR FIRST ITERATION ---
    if iteration == 0 and not existing_context:
        import re
        query = state["query"]
        
        # 1. Very strict URL fast-path (bypasses LLM decompose)
        url_match = re.search(r'https?://[^\s]+', query)
        if url_match:
            tool_calls = [{"name": "web_fetch", "args": {"url": url_match.group(0)}}]
            _emit(state, "🧭", "Rule routing: detected URL, routing to web_fetch.")
        else:
            # 2. LLM decompose for Jira detection and vector search splitting
            tool_calls = _decompose_query(query, state)
            
        return {
            "pending_tool_calls": tool_calls,
            "llm_call_count": state.get("llm_call_count", 0),
            "llm_prompt_tokens": state.get("llm_prompt_tokens", 0),
            "llm_completion_tokens": state.get("llm_completion_tokens", 0),
            "llm_total_tokens": state.get("llm_total_tokens", 0),
        }

    grader_action = state.get("grader_action")
    
    # Let the LLM planner handle retry actions (REFINE/RE_RETRIEVE)
    # The PLAN_SYSTEM prompt will guide it to follow context_file_hints
    
    # ── LLM Planner (iteration > 0 or normal planning) ──
    llm = _build_llm()
    messages = [SystemMessage(content=PLAN_SYSTEM)]

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
        
        hints_text = ""
        context_file_hints = state.get("context_file_hints") or []
        if context_file_hints:
            hints_text = "Context File Hints (clues found in previous rounds):\n" + "\n".join(f"- {h}" for h in context_file_hints) + "\n\n"

        messages.append(
            SystemMessage(
                content=(
                    f"Previous tool calls: {prev_calls}\n\n"
                    f"{hints_text}"
                    "The evidence found so far was deemed insufficient to answer the user's question. "
                    "You MUST try DIFFERENT tools or DIFFERENT search terms.\n"
                    "If 'Context File Hints' are provided above (file paths, Jira IDs), you MUST prioritize following those clues using read_file, jira_fetch, etc., rather than blindly rephrasing vector searches.\n"
                    "Do NOT repeat the exact same tool calls."
                )
            )
        )

    messages.append(HumanMessage(content=state["query"]))

    response: AIMessage = _invoke_and_track(llm, messages, state)
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

    # Final fallback: if still no tool calls and no existing context, use default
    if not tool_calls and not existing_context:
        query = state["query"]
        tool_calls = [
            # {"name": "grep_search", "args": {"query": query}},
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

    return {
        "pending_tool_calls": tool_calls,
        "llm_call_count": state.get("llm_call_count", 0),
        "llm_prompt_tokens": state.get("llm_prompt_tokens", 0),
        "llm_completion_tokens": state.get("llm_completion_tokens", 0),
        "llm_total_tokens": state.get("llm_total_tokens", 0),
    }


def _extract_file_paths_from_context(context: list[str]) -> list[str]:
    """Extract file paths from tool results for read_file follow-up."""
    paths = []
    for item in context:
        # Look for file_path fields in JSON results
        for match in re.finditer(r'"file_path"\s*:\s*"([^"]+)"', item):
            paths.append(match.group(1))
        # Look for numbered list outputs from local_file_qa (e.g., "1, /path/to/file.md (filename match)")
        for match in re.finditer(r'^\d+,\s*([^ ]+\.md)', item, re.MULTILINE):
            paths.append(match.group(1))
        # Look for .md file references
        for match in re.finditer(r'[\w/.-]+\.md', item):
            paths.append(match.group(0))

    # Normalize source paths → index paths (source/X.txt → index/X.md)
    settings = config.settings
    normalized = []
    for p in paths:
        pp = __import__('pathlib').Path(p)
        if settings and settings.index_path:
            # Check if this looks like a source file that should be read from index
            stem = pp.stem
            ext = pp.suffix.lower()
            if ext in ('.txt', '.pdf', '.docx', '.xlsx', '.csv') or 'source' in str(pp):
                index_candidate = settings.index_path / f"{stem}.md"
                if index_candidate.exists():
                    normalized.append(str(index_candidate))
                    continue
        normalized.append(p)

    # De-duplicate while preserving order
    seen = set()
    unique = []
    for p in normalized:
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

        is_error = False
        try:
            parsed = json.loads(result_str)
            if isinstance(parsed, dict) and parsed.get("status") == "error":
                is_error = True
            elif isinstance(parsed, list) and len(parsed) > 0:
                is_error = all(item.get("metadata", {}).get("error") for item in parsed if isinstance(item, dict))
        except (json.JSONDecodeError, TypeError):
            pass

        if is_error or result_str.startswith("Tool error"):
            _emit(state, "⚠️", f"{tool_name} returned error: {result_preview}")
            new_tool_history.append({
                "tool": tool_name,
                "input": tool_args,
                "output": result_str[:500],
                "error": True
            })
            continue

        extra_info = ""
        try:
            parsed_json = json.loads(result_str)
            if isinstance(parsed_json, list):
                count = len(parsed_json)
                if tool_name == "grep_search":
                    unique_files = len(set(item.get("file_path") for item in parsed_json if "file_path" in item))
                    extra_info = f" ({unique_files} files matched)"
                elif tool_name in ["vector_search", "hybrid_search"]:
                    extra_info = f" ({count} chunks found)"
                elif count > 0:
                    extra_info = f" ({count} results)"
        except (json.JSONDecodeError, TypeError):
            pass

        _emit(state, "📄", f"Got {len(result_str)} chars from {tool_name}{extra_info}")

        from ..config import settings
        if settings and getattr(settings, "debug_mode", False) and tool_name in ["vector_search", "hybrid_search"]:
            try:
                preview_items = json.loads(result_str)
                for i, chunk in enumerate(preview_items):
                    content = chunk.get("content", "")
                    preview = content[:100].replace("\n", " ") + "..." if len(content) > 100 else content.replace("\n", " ")
                    _emit(state, "🐛", f"Chunk {i+1} [{chunk.get('id', 'unknown')}]: {preview}")
            except Exception:
                pass

        if tool_name == "read_file" and "file_path" in tool_args:
            files_read.append(tool_args["file_path"])

        # Attempt to add citation formatting if the result is JSON
        formatted_result = result_str
        multi_items = None
        try:
            parsed_res = json.loads(result_str)
            if isinstance(parsed_res, list) and len(parsed_res) > 0 and isinstance(parsed_res[0], dict):
                formatted_items = []
                for item in parsed_res:
                    path = item.get("file_path") or item.get("metadata", {}).get("path") or item.get("metadata", {}).get("source") or item.get("id")
                    line = item.get("line") or item.get("metadata", {}).get("line") or "1"
                    score = item.get("score")
                    content = item.get("content", str(item))

                    # Normalize source paths → index paths for LLM context
                    if path and settings and settings.index_path:
                        from pathlib import Path as _Path
                        _pp = _Path(path)
                        _ext = _pp.suffix.lower()
                        if _ext in ('.txt', '.pdf', '.docx', '.xlsx', '.csv') or 'source' in str(_pp):
                            _idx = settings.index_path / f"{_pp.stem}.md"
                            if _idx.exists():
                                path = str(_idx)

                    if path:
                        if score is not None:
                            formatted_items.append(f"[SOURCE:{path}:L{line}:S{score:.4f}] {content}")
                        else:
                            formatted_items.append(f"[SOURCE:{path}:L{line}] {content}")
                    else:
                        formatted_items.append(str(item))
                
                # For `vector_search` and `grep_search`, return them as a list of independent items
                # so CRAG logic treats them as N distinct evidences instead of 1 giant evidence string
                if tool_name in ["vector_search", "grep_search", "hybrid_search"]:
                    multi_items = formatted_items
                else:
                    formatted_result = "\n".join(formatted_items)
            elif isinstance(parsed_res, dict) and "id" in parsed_res:
                 # Single item case (like Jira/Confluence/Web)
                 path = parsed_res.get("id", "unknown_source")
                 content = parsed_res.get("content", str(parsed_res))
                 formatted_result = f"[SOURCE:{path}:L1] {content}"
        except (json.JSONDecodeError, TypeError):
            # Not JSON, fallback to generic formatting
            formatted_result = f"[{tool_name}] {result_str}"

        if multi_items:
            new_context.extend(multi_items)
        else:
            new_context.append(formatted_result)
        new_tool_history.append({
            "tool": tool_name,
            "input": tool_args,
            "output": result_str[:500],
        })

    if len(pending) > 1 and "vector_search" in [t["name"] for t in pending]:
        _emit(state, "🧹", "Deduplicating chunks from parallel searches...")
        unique_chunks: dict[str, str] = {}
        for item in new_context:
            import re
            # Extract basic id ([SOURCE:file_path:Lline) and score if present
            # Format: [SOURCE:path:Lline:Sscore] content
            match = re.search(r'^\[SOURCE:(.+?:L\d+)(?::S([0-9.]+))?\]', item)
            if match:
                chunk_id = match.group(1)
                score = float(match.group(2)) if match.group(2) else 0.0
                
                if chunk_id in unique_chunks:
                    # Keep the one with higher score
                    existing_match = re.search(r'^\[SOURCE:.+?:L\d+(?::S([0-9.]+))?\]', unique_chunks[chunk_id])
                    existing_score = float(existing_match.group(1)) if existing_match and existing_match.group(1) else 0.0
                    if score > existing_score:
                        unique_chunks[chunk_id] = item
                else:
                    unique_chunks[chunk_id] = item
            else:
                # If it doesn't match the format, it's not a chunk, just keep it (e.g., from web_fetch)
                unique_chunks[item] = item
                
        deduped_context = list(unique_chunks.values())
        if len(deduped_context) < len(new_context):
            _emit(state, "🧹", f"Deduplicated context from {len(new_context)} to {len(deduped_context)} items.")
        new_context = deduped_context

    # Ensure context count isn't too extreme for the LLM
    if len(new_context) > 50:
        _emit(state, "⚠️", f"Truncating context from {len(new_context)} to 50 items to fit context window.")
        new_context = new_context[:50]

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
# Node: GRADE EVIDENCE (CRAG)
# ---------------------------------------------------------------------------

GRADER_SYSTEM = (
    "You are an evidence grader. Your job is to assess the relevance of retrieved "
    "context items to the user's question.\n\n"
    "RULES:\n"
    "1. Grade each context item strictly on its relevance to the query: does it contain "
    "   information needed to answer the question? (1.0 = highly relevant, "
    "   0.5 = partially relevant, 0.0 = completely irrelevant/useless).\n"
    "2. If the user's intent is to 'Find/Search' for files, and the context contains "
    "   a numbered list of files, grade it 1.0.\n"
    "3. You MUST output ONLY a JSON array of floats (0.0 to 1.0) exact matching the "
    "   number of context items provided, in the same order.\n"
    "4. Example output for 3 items: [1.0, 0.0, 0.5]\n"
    "5. Output NOTHING ELSE. No explanation, no markdown blocks, just the array.\n"
)


def grade_evidence_node(state: AgentState) -> dict[str, Any]:
    """Grade retrieved evidence, filter irrelevant items, and decide next action (CRAG)."""
    iteration = state.get("iteration", 0) + 1
    _emit(state, "⚖️", f"Grading evidence relevance (round {iteration})...")

    context_items = state.get("context") or []

    if not context_items:
        _emit(state, "⚠️", "No evidence to grade, forcing retrieval")
        return {"iteration": iteration, "grader_action": "RE_RETRIEVE"}

    # Load thresholds
    from ..config import settings
    max_items = settings.auto_approve_max_items if settings and settings.auto_approve_max_items is not None else 2
    score_threshold = settings.vector_score_threshold if settings and settings.vector_score_threshold is not None else 0.8
    
    # --- AUTO-APPROVE RULES (FAST-PATH) ---
    tool_history = state.get("tool_history") or []
    
    # 1. LOCAL FILE QA
    if tool_history and tool_history[-1].get("tool") == "local_file_qa":
        _emit(state, "✅", "File search results auto-approved (local_file_qa)")
        log_audit("fast_path_hit", {"path_type": "rule_auto_approve", "rule_name": "local_file_qa", "query": state["query"]})
        return {"iteration": iteration, "grader_action": "GENERATE", "evidence_scores": [1.0] * len(context_items)}
        
    # 2. READ FILE
    # If all tools executed in the last round (or all tools total if just one round) are read_file
    if tool_history and all(t.get("tool") == "read_file" for t in tool_history):
        _emit(state, "✅", "File content auto-approved (read_file)")
        log_audit("fast_path_hit", {"path_type": "rule_auto_approve", "rule_name": "read_file", "query": state["query"]})
        return {"iteration": iteration, "grader_action": "GENERATE", "evidence_scores": [1.0] * len(context_items)}
        
    # 3. FEW CONTEXT ITEMS
    if len(context_items) <= max_items:
        _emit(state, "✅", f"Few context items ({len(context_items)}), auto-approved")
        log_audit("fast_path_hit", {"path_type": "rule_auto_approve", "rule_name": "few_context", "query": state["query"], "items": len(context_items)})
        return {"iteration": iteration, "grader_action": "GENERATE", "evidence_scores": [1.0] * len(context_items)}
        
    # 4. HIGH VECTOR SCORES
    # Check if all tools were vector_search and all scores are >= threshold
    # Note: Currently vector_search doesn't explicitly expose scores in a structured way to tool_history easily
    # without parsing the string output. Let's do a robust check: if any vector_search was used and it returned
    # results that we can parse scores from, we check them.
    # To be safe and simple: if we are here, we just check if it's purely a vector_search result and score > threshold.
    # The spec allows us to parse metadata. We can look at the raw string for "[Score: X.XXX]".
    import re
    all_high_scores = True
    has_vector_scores = False
    
    for item in context_items:
        score_match = re.search(r'\[Score:\s*([0-9.]+)\]', item)
        if score_match:
            has_vector_scores = True
            score = float(score_match.group(1))
            if score < score_threshold:
                all_high_scores = False
                break
        else:
            # If any item doesn't have a score, we can't auto-approve based on vector score
            all_high_scores = False
            break
            
    if has_vector_scores and all_high_scores:
        _emit(state, "✅", f"High vector scores (>= {score_threshold}), auto-approved")
        log_audit("fast_path_hit", {"path_type": "rule_auto_approve", "rule_name": "high_vector_score", "query": state["query"]})
        return {"iteration": iteration, "grader_action": "GENERATE", "evidence_scores": [1.0] * len(context_items)}

    # --- LLM GRADING (FALLBACK) ---

    llm = _build_llm()

    messages: list = [SystemMessage(content=GRADER_SYSTEM)]
    
    # Format context items for prompt
    ctx_text = ""
    # Limit to 20 items and 2000 chars per item to avoid token limits
    for i, item in enumerate(context_items[:20]):
        truncated_item = item[:2000] + "... [truncated]" if len(item) > 2000 else item
        ctx_text += f"--- Item {i} ---\n{truncated_item}\n\n"
        
    messages.append(
        HumanMessage(
            content=(
                f"User question: {state['query']}\n\n"
                f"Context Items:\n{ctx_text}"
            )
        )
    )

    response = _invoke_and_track(llm, messages, state)
    raw = response.content.strip()

    # Parse JSON array of scores
    cleaned = _strip_think_tags(raw)
    scores = _extract_json(cleaned)

    # Fallback/validation for JSON parsing
    if not isinstance(scores, list) or len(scores) != len(context_items):
        log_audit("grade_evidence_parse_failure", {"raw_cleaned": cleaned[:300]})
        scores = [0.5] * len(context_items) # default fallback
    else:
        # Ensure all items are floats
        scores = [float(s) if isinstance(s, (int, float)) else 0.5 for s in scores]

    # Filter context (keep score > 0.0)
    filtered_context = []
    for item, score in zip(context_items, scores):
        if score > 0.0:
            filtered_context.append(item)

    avg_score = sum(scores) / len(scores) if scores else 0.0
    
    context_file_hints = state.get("context_file_hints", [])
    
    # Adaptive decision
    if avg_score >= 0.7:
        action = "GENERATE"
        _emit(state, "✅", "Evidence highly relevant, proceeding to generation.")
    elif avg_score >= 0.3:
        action = "REFINE"
        _emit(state, "🔄", "Evidence partially relevant, refining plan.")
        context_file_hints = _extract_hints_from_context(context_items, context_file_hints)
    else:
        action = "RE_RETRIEVE"
        _emit(state, "🗑️", "Evidence irrelevant, restarting retrieval.")
        context_file_hints = _extract_hints_from_context(context_items, context_file_hints)

    log_audit("grade_evidence_result", {
        "iteration": iteration,
        "avg_score": avg_score,
        "action": action,
        "filtered_count": len(filtered_context)
    })

    return {
        "iteration": iteration,
        "context": filtered_context,  # Update state with filtered context
        "context_file_hints": context_file_hints,
        "evidence_scores": scores,
        "grader_action": action,
        "llm_call_count": state.get("llm_call_count", 0),
        "llm_prompt_tokens": state.get("llm_prompt_tokens", 0),
        "llm_completion_tokens": state.get("llm_completion_tokens", 0),
        "llm_total_tokens": state.get("llm_total_tokens", 0),
    }

def _extract_hints_from_context(context_items: list[str], existing_hints: list[str]) -> list[str]:
    """Extract actionable hints (file paths, Jira keys, Confluence logic) from context items."""
    import re
    hints = set(existing_hints)
    
    for item in context_items:
        # 1. File paths from tags [SOURCE:file_path...]
        path_matches = re.finditer(r'\[SOURCE:([^:]+)', item)
        for match in path_matches:
            hint = match.group(1).strip()
            if hint and not hint.startswith("http") and not re.match(r'^[A-Z]+-\d+$', hint):
                hints.add(hint)
                
        # 2. Jira ticket IDs
        jira_matches = re.finditer(r'\b([A-Z]+-\d+)\b', item)
        for match in jira_matches:
            hints.add(match.group(1))
            
        # 3. Confluence Page IDs (crude proxy: 5+ digit numbers that might be IDs)
        # Often they appear near words like 'page', 'confluence', 'wiki'
        # For safety we just grab exact matches of page indicators
        page_matches = re.finditer(r'(?:page|confluence\s+id)[:\s]+(\d{5,})', item, re.IGNORECASE)
        for match in page_matches:
            hints.add(f"Confluence Page ID: {match.group(1)}")
            
    return list(hints)


# ---------------------------------------------------------------------------
# Node: SYNTHESIZE
# ---------------------------------------------------------------------------

SYNTHESIZE_SYSTEM = (
    "You are a helpful knowledge base assistant. Answer the user's question "
    "primarily based on the provided context and conversation history.\n\n"
    "RULES:\n"
    "1. **Be thorough**: Extract ALL relevant details, data points, and specific "
    "   information from the evidence. Do NOT summarize away important details.\n"
    "2. If the evidence contains structured data (tables, lists, technical specs), "
    "   reproduce them in your answer, not just paraphrase.\n"
    "3. Structure your response using headers (##), bullet points, and formatting "
    "   for readability. Long, well-structured answers are PREFERRED over short ones.\n"
    "4. If the retrieved context is completely empty or devoid of any related signal at all, you MUST respond with:\n"
    "   'I couldn't find relevant information in the knowledge base to answer this question.'\n"
    "5. You MAY use your general knowledge to interpret or glue these facts together. If you provide "
    "   assumptions or explanations beyond the provided text, clearly state that you are doing so.\n"
    "6. **CITATIONS**: You MUST cite your sources using bracketed numbers, e.g., [1], [2].\n"
    "   The context items provided will contain markers like [SOURCE:path/to/file.md:L123] or [SOURCE:path:L123:S0.95].\n"
    "   When you use information from an item, append its corresponding number to the sentence.\n"
)


def synthesize_node(state: AgentState) -> dict[str, Any]:
    """Generate the final answer grounded strictly in context, with citations."""
    _emit(state, "✨", "Synthesizing answer from evidence...")

    context_items = state.get("context") or []

    log_audit("synthesize_start", {
        "context_count": len(context_items),
        "total_chars": sum(len(c) for c in context_items),
    })

    llm = _build_llm()
    
    routing_plan = state.get("routing_plan", {})
    complexity = routing_plan.get("complexity", "complex")

    # Handle chitchat mode
    if complexity == "chitchat":
        chitchat_system = (
            "You are a helpful and friendly knowledge base assistant. "
            "The user is making conversation or asking a social/greeting question. "
            "Respond naturally, politely, and concisely."
        )
        messages: list = [SystemMessage(content=chitchat_system)]
        history = state.get("messages") or []
        messages.extend(_history_to_messages(history))
        messages.append(HumanMessage(content=state['query']))
        
        response = _invoke_and_track(llm, messages, state)
        raw_answer = _strip_think_tags(response.content)
        
        log_audit("synthesize_result", {
            "mode": "chitchat",
            "answer_length": len(raw_answer),
            "answer_preview": raw_answer[:300],
        })
        log_llm_response(state["query"], raw_answer)
        final_answer = Security.mask_sensitive_data(raw_answer)
        
        # Append LLM Stats to final answer (even for chitchat)
        stats_block = (
            f"\n\n---\n"
            f"📊 **LLM Usage Stats:**\n"
            f"- **API Calls:** {state.get('llm_call_count', 0)}\n"
            f"- **Tokens:** {state.get('llm_prompt_tokens', 0)} prompt + "
            f"{state.get('llm_completion_tokens', 0)} completion "
            f"= **{state.get('llm_total_tokens', 0)} total**"
        )
        final_answer += stats_block
        
        return {
            "final_answer": final_answer,
            "llm_call_count": state.get("llm_call_count", 0),
            "llm_prompt_tokens": state.get("llm_prompt_tokens", 0),
            "llm_completion_tokens": state.get("llm_completion_tokens", 0),
            "llm_total_tokens": state.get("llm_total_tokens", 0),
        }

    # Standard evidence-based synthesis
    messages: list = [SystemMessage(content=SYNTHESIZE_SYSTEM)]

    history = state.get("messages") or []
    messages.extend(_history_to_messages(history))

    # Format context with explicit numbers for citation mapping
    sources_list = []
    ctx_blocks = []
    seen_sources = set()
    
    import re
    
    for item in context_items:
        # Extract the source reference if it exists
        source_match = re.search(r'\[SOURCE:(.+?):L(\d+)(?::S([0-9.]+))?\]\s*(.*)', item, re.DOTALL)
        if source_match:
            path, line, score_str, content = source_match.groups()
            score = float(score_str) if score_str else None
            key = (path, line)
            if key not in seen_sources:
                seen_sources.add(key)
                sources_list.append({
                    "path": path,
                    "line": line,
                    "score": score,
                    "content": content.strip()  # Pass full content for the TUI Modal
                })
                # Re-index citations consecutively for the LLM prompt
                ctx_blocks.append(f"--- Evidence [{len(sources_list)}] ---\n{item}")
        else:
            # Fallback for unformatted items
            key = ("Knowledge Base Item", str(len(seen_sources) + 1))
            if key not in seen_sources:
                seen_sources.add(key)
                sources_list.append({
                    "path": "Knowledge Base Item",
                    "line": "1",
                    "score": None,
                    "content": item.strip()
                })
                ctx_blocks.append(f"--- Evidence [{len(sources_list)}] ---\n{item}")
            
    ctx_text = "\n\n".join(ctx_blocks) if ctx_blocks else "(No evidence was found.)"

    messages.append(
        HumanMessage(
            content=f"Context:\n{ctx_text}\n\nQuestion: {state['query']}"
        )
    )

    response = _invoke_and_track(llm, messages, state)
    raw_answer = _strip_think_tags(response.content)

    log_audit("synthesize_result", {
        "answer_length": len(raw_answer),
        "answer_preview": raw_answer[:300],
    })
    log_llm_response(state["query"], raw_answer)

    final_answer = Security.mask_sensitive_data(raw_answer)

    # Format and Append LLM Usage Stats block
    stats_block = (
        f"\n\n---\n"
        f"📊 **LLM Usage Stats:**\n"
        f"- **API Calls:** {state.get('llm_call_count', 0)}\n"
        f"- **Tokens:** {state.get('llm_prompt_tokens', 0)} prompt + "
        f"{state.get('llm_completion_tokens', 0)} completion "
        f"= **{state.get('llm_total_tokens', 0)} total**"
    )
    final_answer += stats_block

    return {
        "final_answer": final_answer,
        "sources": sources_list,
        "llm_call_count": state.get("llm_call_count", 0),
        "llm_prompt_tokens": state.get("llm_prompt_tokens", 0),
        "llm_completion_tokens": state.get("llm_completion_tokens", 0),
        "llm_total_tokens": state.get("llm_total_tokens", 0),
    }
