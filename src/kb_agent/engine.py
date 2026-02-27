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

# Regex to detect URLs in user input
_URL_PATTERN = re.compile(r'https?://[^\s<>"\']+')

logger = logging.getLogger("kb_agent_audit")


class Engine:
    def __init__(self):
        self.llm = LLMClient()
        self.web_connector = WebConnector()
        self._docs_path = Path("docs")

        # Compile the agentic RAG graph once
        self._graph = compile_graph()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def answer_query(
        self,
        user_query: str,
        on_status=None,
        mode: str = "knowledge_base",
        history: List[Dict[str, str]] = None,
    ) -> str:
        """
        Main entry point for answering a user query.

        Args:
            user_query: The user's natural language question.
            on_status: Optional callback ``(emoji, message)`` for TUI progress.
            mode: ``"knowledge_base"`` or ``"normal"``.
            history: Previous conversation messages ``[{role, content}, ...]``.
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
            return Security.mask_sensitive_data(raw_response)

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
    ) -> str:
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
            if not answer:
                answer = (
                    "I couldn't find relevant information in the knowledge base "
                    "to answer this question."
                )
            return answer
        except Exception as e:
            logger.error(f"Agentic RAG failed: {e}")
            return f"An error occurred while processing your query: {e}"

    # ------------------------------------------------------------------
    # URL handling (unchanged)
    # ------------------------------------------------------------------

    def _handle_urls(
        self,
        user_query: str,
        urls: List[str],
        _status,
        mode: str = "knowledge_base",
        history: List[Dict[str, str]] = None,
    ) -> str:
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

                if mode == "knowledge_base":
                    _status("📝", f"Processing content from {doc['title']}...")
                    try:
                        processor = Processor(self._docs_path)
                        processor.process(doc)
                        log_audit("web_fetch", {"url": url, "doc_id": doc["id"]})
                    except Exception as e:
                        logger.warning(f"Processor failed for {url}: {e}")

                all_content.append(
                    f"Source: {url}\nTitle: {doc['title']}\n\n{doc['content']}"
                )

        if not all_content:
            return "Failed to fetch any content from the provided URL(s)."

        full_context = "\n\n---\n\n".join(all_content)

        question = user_query
        for url in urls:
            question = question.replace(url, "").strip()
        if not question:
            question = "Please summarize the content from the provided URL(s)."

        _status("✨", "Generating answer from web content...")
        system_prompt = (
            "You are a helpful assistant. Answer the user's question based on "
            "the web page content provided (and previous conversation if "
            "necessary). If the content doesn't answer the question, summarize "
            "the key points of the page. Be concise and well-structured."
        )
        user_prompt = f"Web Content:\n{full_context[:8000]}\n\nQuestion: {question}"

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})

        raw_response = self.llm.chat_completion(messages)
        log_llm_response(user_prompt, raw_response)
        return Security.mask_sensitive_data(raw_response)
