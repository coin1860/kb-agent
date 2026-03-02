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

        # Compile the agentic RAG graph once
        self._graph = compile_graph()

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
