"""
Engine — the public API for answering user queries.

In ``knowledge_base`` mode the query is delegated to the LangGraph agentic
RAG workflow.  In ``normal`` mode or when URLs are detected the legacy
direct-LLM path is used.
"""

import logging
import json
import re
from pathlib import Path
from typing import List, Dict, Any

from kb_agent.llm import LLMClient
from kb_agent.security import Security
from kb_agent.audit import log_audit, log_llm_response
from kb_agent.connectors.web_connector import WebConnector
from kb_agent.processor import Processor

# Agentic RAG (LangGraph)
from kb_agent.agent.graph import compile_graph
from kb_agent.agent.tools import reset_tools_cache

# Agent Mode (LangGraph)
from kb_agent.agent_mode.session import SessionManager
from kb_agent.agent_mode.skills import SkillLoader
from kb_agent.agent_mode.graph import build_agent_graph
from kb_agent.agent_mode.nodes import register_status_callback, unregister_status_callback
from langgraph.types import Command
from langgraph.checkpoint.memory import MemorySaver

# Regex to detect URLs, Jira tickets, and Confluence page IDs
_URL_PATTERN = re.compile(r'https?://[^\s<>"\']+')
_JIRA_PATTERN = re.compile(r'^[A-Z][A-Z0-9]+-\d+$', re.IGNORECASE)
_CONFLUENCE_PATTERN = re.compile(r'^\d+$')

logger = logging.getLogger("kb_agent_audit")


class Engine:
    def __init__(self):
        self.llm = LLMClient()
        self.web_connector = WebConnector()
        self._docs_path = Path("docs")

        # Clear cached tool instances so they pick up new config
        reset_tools_cache()

        # Compile the agentic RAG graph once
        self._graph = compile_graph()
        
        # Agent Mode Components
        self.session_manager = SessionManager()
        self.skill_loader = SkillLoader()
        self.skill_loader.scan()
        
        # Use MemorySaver so LangGraph can interrupt and persist
        # Note: We still save our own JSON checkpoints for easy access,
        # but LangGraph needs its native checkpointer for interrupts.
        self._agent_checkpointer = MemorySaver()
        self._agent_graph = build_agent_graph()
        self._agent_graph.checkpointer = self._agent_checkpointer

    def _get_processor(self) -> Processor:
        """Lazy load processor to avoid circular imports or early config checks."""
        import kb_agent.config as config
        if config.settings and config.settings.index_path:
            return Processor(config.settings.index_path)
        return Processor(Path("index"))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def answer_query(
        self,
        user_query: str,
        on_status=None,
        mode: str = "knowledge_base",
        history: List[Dict[str, str]] = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Main entry point for answering a user query.

        Args:
            user_query: The user's natural language question.
            on_status: Optional callback ``(emoji, message)`` for TUI progress.
            mode: ``"knowledge_base"`` or ``"normal"``.
            history: Previous conversation messages ``[{role, content}, ...]``.
            
        Returns:
            A tuple of (answer_text, sources_list) where each source is a dict.
        """
        def _status(emoji, msg):
            if on_status:
                on_status(emoji, msg)

        log_audit("start_query", {"query": user_query, "mode": mode})

        history = history or []

        # 0. URL Detection — fetch, convert, answer
        urls = _URL_PATTERN.findall(user_query)
        if urls:
            return self._handle_urls(user_query, urls, _status, mode=mode, history=history)

        # 1. Normal (non-RAG) mode — direct LLM chat
        if mode == "normal":
            _status("✨", "Generating answer...")
            messages = [{"role": "system", "content": "You are a helpful assistant."}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_query})
            raw_response = self.llm.chat_completion(messages)
            log_llm_response(user_query, raw_response)
            return Security.mask_sensitive_data(raw_response), []

        # 2. Knowledge Base mode — agentic RAG via LangGraph
        return self._run_agentic_rag(user_query, _status, history)

    # ------------------------------------------------------------------
    # Agentic RAG (LangGraph)
    # ------------------------------------------------------------------

    def _run_agentic_rag(
        self,
        user_query: str,
        _status,
        history: List[Dict[str, str]],
    ) -> tuple[str, list[dict[str, Any]]]:
        """Invoke the LangGraph compiled workflow."""
        _status("🚀", "Starting agentic RAG workflow...")

        initial_state = {
            "query": user_query,
            "messages": history,
            "mode": "knowledge_base",
            "search_queries": [],
            "context": [],
            "tool_history": [],
            "files_read": [],
            "iteration": 0,
            "is_sufficient": False,
            "final_answer": "",
            "status_callback": _status,
        }

        try:
            final_state = self._graph.invoke(initial_state)
            answer = final_state.get("final_answer", "")
            sources = final_state.get("sources", [])
            if not answer:
                answer = (
                    "I couldn't find relevant information in the knowledge base "
                    "to answer this question."
                )
            return answer, sources
        except Exception as e:
            return f"An error occurred while processing your query: {e}", []

    # ------------------------------------------------------------------
    # Agent Mode API (LangGraph)
    # ------------------------------------------------------------------

    def start_task(self, goal: str, on_status=None) -> str:
        """Start a new agent mode task."""
        def _status(status_dict):
            if on_status:
                emoji = status_dict.get("emoji", "")
                msg = status_dict.get("msg", "")
                on_status(emoji, msg)

        session = self.session_manager.create(goal)
        _status({"emoji": "🏁", "msg": f"Started new session {session.id}"})
        
        initial_state = {
            "session_id": session.id,
            "goal": goal,
            "task_status": "init",
            "execution_log": [],
            "plan": [],
            "current_step_index": 0,
            "consecutive_failures": 0,
            "max_consecutive_failures": 3,
            "needs_human_input": False,
        }
        
        config = {"configurable": {"thread_id": session.id}}
        try:
            register_status_callback(session.id, _status)
            for event in self._agent_graph.stream(initial_state, config=config):
                for node_name, output in event.items():
                    if isinstance(output, dict) and "plan" in output:
                        if on_status:
                            on_status("INTERNAL_PLAN_UPDATE", output["plan"])
                
                # Check for interrupts
                graph_state = self._agent_graph.get_state(config)
                if graph_state.next:
                    if on_status:
                        # Heuristic for confirmation vs feedback
                        # Check last message or state fields
                        msg = "Agent requires your guidance to proceed."
                        is_conf = False
                        if "act" in graph_state.next:
                            is_conf = True
                            
                        # Extract the actual interrupt message if available
                        if graph_state.tasks:
                            task = graph_state.tasks[0]
                            if getattr(task, "interrupts", None) and len(task.interrupts) > 0:
                                val = task.interrupts[0].value
                                if val:
                                    msg = str(val)
                        
                        on_status("INTERNAL_INTERRUPT", {
                            "session_id": session.id,
                            "message": msg,
                            "is_confirmation": is_conf
                        })

        except Exception as e:
            if on_status:
                on_status("❌", f"Agent execution error: {e}")
            logger.error(f"Agent execution failed: {e}", exc_info=True)
        finally:
            unregister_status_callback(session.id)
            
        return session.id

    def resume_task(self, session_id: str, on_status=None, user_input: str = None) -> bool:
        """Resume an existing agent mode task, optionally providing user input to an interrupt."""
        def _status(status_dict):
            if on_status:
                emoji = status_dict.get("emoji", "")
                msg = status_dict.get("msg", "")
                on_status(emoji, msg)

        try:
            register_status_callback(session_id, _status)
            # We must load the checkpointer state
            config = {"configurable": {"thread_id": session_id}}
            
            # If there's user input to provide to an interrupt:
            stream_input = None
            if user_input is not None:
                stream_input = Command(resume=user_input)
                
            for event in self._agent_graph.stream(stream_input, config=config):
                for node_name, output in event.items():
                    if isinstance(output, dict) and "plan" in output:
                        if on_status:
                            on_status("INTERNAL_PLAN_UPDATE", output["plan"])
            
            # Check for subsequent interrupts
            graph_state = self._agent_graph.get_state(config)
            if graph_state.next:
                if on_status:
                    msg = "Another intervention required."
                    is_conf = "act" in graph_state.next
                    
                    if graph_state.tasks:
                        task = graph_state.tasks[0]
                        if getattr(task, "interrupts", None) and len(task.interrupts) > 0:
                            val = task.interrupts[0].value
                            if val:
                                msg = str(val)
                                
                    on_status("INTERNAL_INTERRUPT", {
                        "session_id": session_id,
                        "message": msg,
                        "is_confirmation": is_conf
                    })
                    
            return True
        except Exception as e:
            if on_status:
                on_status("❌", f"Agent execution error: {e}")
            logger.error(f"Agent execution failed: {e}", exc_info=True)
            return False
        finally:
            unregister_status_callback(session_id)

    # ------------------------------------------------------------------
    # URL handling (unchanged)
    # ------------------------------------------------------------------

    def answer_from_context(
        self,
        context_text: str,
        user_query: str,
        _status=None,
        history: List[Dict[str, str]] = None,
    ) -> str:
        """
        Directly answer a query based on the provided context text, bypassed RAG.
        Used by /jira, /confluence, and /file commands in chat mode.
        """
        def _stat(emoji, msg):
            if _status:
                _status(emoji, msg)

        history = history or []
        _stat("✨", "Generating answer from provided content...")
        
        system_prompt = (
            "You are a helpful assistant. Answer the user's question based on "
            "the provided content context (and previous conversation if "
            "necessary). Be concise, accurate, and well-structured. "
            "If the content doesn't fully answer the question, summarize "
            "the key information available."
        )
        user_prompt = f"Context:\n{context_text[:12000]}\n\nQuestion: {user_query}"

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})

        raw_response = self.llm.chat_completion(messages)
        log_llm_response(user_prompt, raw_response)
        return Security.mask_sensitive_data(raw_response)

    # ------------------------------------------------------------------
    # URL handling
    # ------------------------------------------------------------------

    def _handle_urls(
        self,
        user_query: str,
        urls: List[str],
        _status,
        mode: str = "knowledge_base",
        history: List[Dict[str, str]] = None,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Fetch URLs, convert to markdown, process, and answer."""
        history = history or []
        all_content = []

        for url in urls:
            _status("🌐", f"Fetching {url}...")
            docs = self.web_connector.fetch_data(url)
            for doc in docs:
                if doc.get("metadata", {}).get("error"):
                    all_content.append(f"Error fetching {url}: {doc['content']}")
                    continue

                all_content.append(
                    f"Source: {url}\nTitle: {doc['title']}\n\n{doc['content']}"
                )

        if not all_content:
            return "Failed to fetch any content from the provided URL(s).", []

        full_context = "\n\n---\n\n".join(all_content)

        question = user_query
        for url in urls:
            question = question.replace(url, "").strip()
        if not question:
            question = "Please summarize the content from the provided URL(s)."

        answer = self.answer_from_context(full_context, question, _status=_status, history=history)
        return answer, []

    def index_resource(self, url_or_id: str, on_status=None) -> str:
        """
        Fetch an external resource (URL, Jira, Confluence), convert it to Markdown,
        and ingest it into the vector index.
        """
        def _status(emoji, msg):
            if on_status:
                on_status(emoji, msg)

        target = url_or_id.strip()

        # Route to appropriate connector
        if _URL_PATTERN.match(target):
            _status("🌐", f"Fetching Web URL: {target}...")
            docs = self.web_connector.fetch_data(target)
        elif _JIRA_PATTERN.match(target):
            _status("🎫", f"Fetching Jira Ticket: {target}...")
            from kb_agent.connectors.jira import JiraConnector
            docs = JiraConnector().fetch_data(target)
        elif _CONFLUENCE_PATTERN.match(target):
            _status("📄", f"Fetching Confluence Page: {target}...")
            from kb_agent.connectors.confluence import ConfluenceConnector
            docs = ConfluenceConnector().fetch_data(target)
        else:
            msg = f"Unrecognized resource format: {target}. Please provide a valid URL, Jira ID (e.g., PROJ-123), or Confluence Page ID."
            _status("❌", msg)
            return msg

        if not docs:
            msg = f"Failed to fetch content from {target}."
            _status("❌", msg)
            return msg

        # Ensure index_path exists and write the docs
        import os
        import kb_agent.config as config
        settings = config.settings

        index_dir = settings.index_path if settings else Path("index")
        os.makedirs(index_dir, exist_ok=True)
        
        processor = self._get_processor()
        success_count = 0
        errors = []

        for doc in docs:
            # Handle connector-level errors gracefully
            if doc.get("metadata", {}).get("error"):
                errors.append(doc.get('content', 'Unknown fetch error'))
                continue

            # Save the raw MD file to the index directory
            # For web links or arbitrary content, generate a safe filename
            doc_id = doc.get("id", "doc")
            safe_filename = re.sub(r'[^A-Za-z0-9_\-]', '_', str(doc_id)) + ".md"
            file_path = index_dir / safe_filename
            
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(doc.get("content", ""))
                _status("💾", f"Saved Markdown to {file_path}")
                
                # Update the doc metadata with its new local path so Processor uses it correctly
                doc.setdefault("metadata", {})["path"] = str(file_path)
                
                # Ingest strictly into Chroma
                _status("🧠", f"Ingesting into Data Store...")
                processor.process(doc)
                log_audit("index_resource", {"target": target, "doc_id": doc_id})
                success_count += 1
            except Exception as e:
                logger.warning(f"Processor failed for {target}: {e}")
                errors.append(str(e))

        if errors:
            err_msg = "; ".join(errors)
            msg = f"Error processing {target}: {err_msg}"
            _status("⚠️", msg)
            return msg
        else:
            msg = f"Successfully indexed {target} ({success_count} item{'s' if success_count != 1 else ''} ingested)."
            _status("✅", msg)
            return msg
