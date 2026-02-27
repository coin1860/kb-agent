import logging
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Set
from kb_agent.llm import LLMClient
from kb_agent.tools.vector_tool import VectorTool
from kb_agent.tools.grep_tool import GrepTool
from kb_agent.tools.file_tool import FileTool
from kb_agent.tools.graph_tool import GraphTool
from kb_agent.security import Security
from kb_agent.audit import log_audit, log_search, log_llm_response
from kb_agent.connectors.web_connector import WebConnector
from kb_agent.processor import Processor

# Regex to detect URLs in user input
_URL_PATTERN = re.compile(r'https?://[^\s<>"\']+')

# Use the same logger name as configured in audit.py
logger = logging.getLogger("kb_agent_audit")

class Engine:
    def __init__(self):
        self.llm = LLMClient()
        self.vector_tool = VectorTool()
        self.grep_tool = GrepTool()
        self.file_tool = FileTool()
        self.graph_tool = GraphTool()
        self.web_connector = WebConnector()
        self._docs_path = Path("docs")

    def answer_query(self, user_query: str, on_status=None, mode: str = "knowledge_base", history: List[Dict[str, str]] = None) -> str:
        """
        Main entry point for the agent to answer a user query.

        Args:
            user_query: The user's natural language question.
            on_status: Optional callback(emoji, message) for real-time progress updates.
            mode: Chat mode to use. Values: "knowledge_base" or "normal".
            history: Optional list of previous messages in the conversation.
        """
        def _status(emoji, msg):
            if on_status:
                on_status(emoji, msg)

        log_audit("start_query", {"query": user_query})
        
        history = history or []

        # 0. URL Detection — fetch, convert to markdown, process & answer
        urls = _URL_PATTERN.findall(user_query)
        if urls:
            return self._handle_urls(user_query, urls, _status, mode=mode, history=history)

        if mode == "normal":
            _status("✨", "Generating answer...")
            messages = [{"role": "system", "content": "You are a helpful assistant."}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_query})
            raw_response = self.llm.chat_completion(messages)
            log_llm_response(user_query, raw_response)
            return Security.mask_sensitive_data(raw_response)

        # 1. Smart Router: Decide whether to search the index or answer directly
        _status("🧠", "Analyzing question...")
        router_prompt = (
            "You are an intelligent router for a Knowledge Base AI Agent. "
            "Analyze the user's question and the conversation history. "
            "If the question can be answered entirely using the provided conversation history without looking up new knowledge base documents, OR if the user is just saying a casual greeting (like 'hi', 'hello') or making a general conversational statement, you should answer directly. "
            "Otherwise, you should search the knowledge base. If the question involves multiple distinct concepts, generate multiple queries. Keep queries to a few keywords each.\n"
            "You MUST output raw JSON (no formatting blocks). Format exactly as one of the following:\n"
            "Option A (Direct Answer): {\"action\": \"answer\"}\n"
            "Option B (Search KB): {\"action\": \"search\", \"queries\": [\"keyword1 keyword2\", \"keyword3 keyword4\"]}"
        )
        
        router_messages = [{"role": "system", "content": router_prompt}]
        router_messages.extend(history)
        router_messages.append({"role": "user", "content": user_query})
        
        import json
        try:
            router_response = self.llm.chat_completion(router_messages)
            router_decision = json.loads(router_response.strip().strip('`').replace('json\n', ''))
            action = router_decision.get("action", "search")
            queries_to_run = router_decision.get("queries", [user_query])
        except Exception as e:
            logger.warning(f"Router failed to parse JSON: {e}. Defaulting to search.")
            action = "search"
            queries_to_run = [user_query]
            
        if action == "answer":
            _status("✨", "Generating direct answer...")
            system_prompt = (
                "You are a helpful banking assistant. Answer the user's question based on the conversation history. "
                "Be precise and professional."
            )
            ans_messages = [{"role": "system", "content": system_prompt}]
            ans_messages.extend(history)
            ans_messages.append({"role": "user", "content": user_query})
            raw_response = self.llm.chat_completion(ans_messages)
            log_llm_response(user_query, raw_response)
            return Security.mask_sensitive_data(raw_response)

        # 2. Multi-Query Hybrid Search
        _status("🔍", f"Hybrid search with queries: {', '.join(queries_to_run)}")
        candidates = []
        for q in queries_to_run:
            candidates.extend(self._hybrid_search(q))
            
        candidates = self._deduplicate_candidates_list(candidates)
        logger.info(f"Initial pooled candidates count: {len(candidates)}")
        _status("🔍", f"Found {len(candidates)} candidate(s) total")

        # 3. Autonomous Retry Logic & Graph Navigation
        if not candidates:
            log_audit("retry_logic", {"reason": "no_candidates", "original_query": user_query})

            # 3a. Graph Navigation Strategy
            entities = re.findall(r'\[?([A-Z]+-\d+)\]?', user_query)

            if entities:
                _status("🕸️", f"Navigating Knowledge Graph for {', '.join(entities)}...")
                logger.info("Grepping failed. Navigating Knowledge Graph...")
                for entity in entities:
                    related = self.graph_tool.get_related_nodes(entity)
                    for r in related:
                        node_id = r["node"]
                        if node_id.endswith(".md"):
                             candidates.append({
                                 "id": node_id,
                                 "score": 5.0,
                                 "full_path": node_id,
                                 "summary_path": None,
                                 "matches": [f"Graph Relation: {r['relation']} to {entity}"]
                             })
                             log_audit("graph_nav", {"from": entity, "to": node_id, "relation": r["relation"]})

            # 3b. Query Expansion (Standard Retry)
            if not candidates:
                _status("🔄", "Expanding query with alternative keywords...")
                new_queries = self._generate_alternative_queries(user_query)
                for q in new_queries:
                    log_audit("retry_search", {"query": q})
                    extra_candidates = self._hybrid_search(q)
                    candidates.extend(extra_candidates)

            candidates = self._deduplicate_candidates_list(candidates)
            logger.info(f"Candidates after retry/graph: {len(candidates)}")

        if not candidates:
            return "I couldn't find any relevant documents in the knowledge base, even after trying alternative keywords and graph navigation."

        # 4. Decision (Heuristic + LLM)
        top_candidates = candidates[:5]

        _status("🤔", "Deciding which documents to read...")
        files_to_read = self._decide_files_to_read(user_query, top_candidates)
        logger.info(f"LLM Decided files: {files_to_read}")

        if not files_to_read and candidates:
            top = candidates[0]
            if top.get("full_path"):
                files_to_read.append(top["full_path"])
            elif top.get("summary_path"):
                files_to_read.append(top["summary_path"])
            logger.info(f"Fallback added files: {files_to_read}")

        files_to_read = list(set(files_to_read))

        if not files_to_read:
             logger.warning("No files to read after decision and fallback.")
             return "I identified potential documents but decided none were relevant enough to read."

        # 5. Read Content and Trace Links (Jira)
        context = []
        read_files = set()
        file_queue = list(files_to_read)
        JIRA_LINK_PATTERN = re.compile(r'\[([A-Z]+-\d+)\]')
        processed_count = 0
        MAX_FILES = 5

        while file_queue and processed_count < MAX_FILES:
            file_path = file_queue.pop(0)
            if file_path in read_files:
                continue

            _status("📄", f"Reading {file_path}...")
            content = self.file_tool.read_file(file_path)
            if content:
                read_files.add(file_path)
                context.append(f"Source: {file_path}\nContent:\n{content}")
                processed_count += 1

                links = JIRA_LINK_PATTERN.findall(content)
                for link_id in links:
                    linked_doc_path = f"{link_id}.md"
                    if linked_doc_path not in read_files and linked_doc_path not in file_queue:
                        file_queue.append(linked_doc_path)
                        log_audit("link_trace", {"from": file_path, "to": linked_doc_path})

        full_context = "\n\n".join(context)

        # 5. Synthesize Answer
        _status("✨", "Generating answer...")
        system_prompt = (
            "You are a helpful banking assistant. Answer the user's question based ONLY on the provided context (and previous conversation if necessary to understand the context). "
            "If the context doesn't contain the answer, say so. "
            "Be precise and professional."
        )
        user_prompt = f"Context:\n{full_context}\n\nQuestion: {user_query}"

        logger.info(f"Synthesizing answer with context length: {len(full_context)}")

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})

        raw_response = self.llm.chat_completion(messages)

        log_llm_response(user_prompt, raw_response)

        # 6. Mask Sensitive Data
        final_response = Security.mask_sensitive_data(raw_response)

        return final_response

    def _handle_urls(self, user_query: str, urls: List[str], _status, mode: str = "knowledge_base") -> str:
        """Fetch URLs, convert to markdown, process, and answer."""
        all_content = []

        for url in urls:
            _status("🌐", f"Fetching {url}...")
            docs = self.web_connector.fetch_data(url)
            for doc in docs:
                if doc.get("metadata", {}).get("error"):
                    all_content.append(f"Error fetching {url}: {doc['content']}")
                    continue

                if mode == "knowledge_base":
                    # Process through the same pipeline as local/confluence/jira
                    _status("📝", f"Processing content from {doc['title']}...")
                    try:
                        processor = Processor(self._docs_path)
                        processor.process(doc)
                        log_audit("web_fetch", {"url": url, "doc_id": doc["id"]})
                    except Exception as e:
                        logger.warning(f"Processor failed for {url}: {e}")
                        # Even if processing fails, we still have the content

                all_content.append(
                    f"Source: {url}\nTitle: {doc['title']}\n\n{doc['content']}"
                )

        if not all_content:
            return "Failed to fetch any content from the provided URL(s)."

        full_context = "\n\n---\n\n".join(all_content)

        # Strip the URL from user_query to get the actual question
        question = user_query
        for url in urls:
            question = question.replace(url, "").strip()
        if not question:
            question = "Please summarize the content from the provided URL(s)."

        _status("✨", "Generating answer from web content...")
        system_prompt = (
            "You are a helpful assistant. Answer the user's question based on the web page content provided (and previous conversation if necessary). "
            "If the content doesn't answer the question, summarize the key points of the page. "
            "Be concise and well-structured."
        )
        user_prompt = f"Web Content:\n{full_context[:8000]}\n\nQuestion: {question}"

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_prompt})

        raw_response = self.llm.chat_completion(messages)

        log_llm_response(user_prompt, raw_response)
        return Security.mask_sensitive_data(raw_response)

    def _hybrid_search(self, query: str) -> List[Dict[str, Any]]:
        grep_results = self.grep_tool.search(query)
        vector_results = self.vector_tool.search(query, n_results=5)
        return self._process_candidates(grep_results, vector_results)

    def _generate_alternative_queries(self, query: str) -> List[str]:
        prompt = (
            f"User Query: {query}\n\n"
            "The user is searching for internal documents, but a direct search failed. "
            "Suggest 3 alternative short keyword queries (synonyms, acronyms, or related concepts) to try. "
            "Return ONLY a JSON list of strings."
        )
        try:
            response = self.llm.chat_completion([
                {"role": "system", "content": "You are a search query optimizer. Output JSON only."},
                {"role": "user", "content": prompt}
            ], temperature=0.3)
            clean_json = response.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_json)
        except Exception as e:
            logger.error(f"Error generating queries: {e}")
            return []

    def _deduplicate_candidates_list(self, candidates_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        unique = []
        for c in candidates_list:
            if c["id"] not in seen:
                seen.add(c["id"])
                unique.append(c)
        return sorted(unique, key=lambda x: x["score"], reverse=True)

    def _process_candidates(self, grep_results, vector_results) -> List[Dict[str, Any]]:
        candidates_map = {}

        for res in vector_results:
            meta = res.get("metadata", {})
            res_id = res["id"]

            type_ = meta.get("type", "unknown")
            if type_ == "summary":
                base_id = res_id.replace("-summary", "")
                summary_path = meta.get("file_path")
                full_path = meta.get("related_file")
            elif type_ == "full":
                base_id = res_id.replace("-full", "")
                full_path = meta.get("file_path")
                summary_path = full_path.replace(".md", "-summary.md") if full_path else None
            else:
                base_id = res_id
                summary_path = None
                full_path = None

            distance = res.get("score", 1.0)
            similarity = 1.0 / (1.0 + distance)

            if base_id not in candidates_map:
                candidates_map[base_id] = {
                    "id": base_id,
                    "score": 0.0,
                    "summary_path": summary_path,
                    "full_path": full_path,
                    "matches": []
                }
            candidates_map[base_id]["score"] += similarity

        for res in grep_results:
            path = res["file_path"]
            # Fix cross-platform filename extraction
            filename = Path(path).name

            if filename.endswith("-summary.md"):
                base_id = filename.replace("-summary.md", "")
            elif filename.endswith(".md"):
                base_id = filename.replace(".md", "")
            else:
                base_id = filename

            if base_id not in candidates_map:
                candidates_map[base_id] = {
                    "id": base_id,
                    "score": 0.0,
                    "summary_path": path if "summary" in path else path.replace(".md", "-summary.md"),
                    "full_path": path if "summary" not in path else path.replace("-summary.md", ".md"),
                    "matches": []
                }

            candidates_map[base_id]["matches"].append(res["content"])
            candidates_map[base_id]["score"] += 10.0

        return sorted(candidates_map.values(), key=lambda x: x["score"], reverse=True)

    def _decide_files_to_read(self, query: str, candidates: List[Dict[str, Any]]) -> List[str]:
        candidate_descriptions = ""
        for i, c in enumerate(candidates):
            snippets = " | ".join(c["matches"][:2]) if c["matches"] else "Semantic Match"
            candidate_descriptions += f"{i+1}. ID: {c['id']}, Snippets: {snippets}\n"

        prompt = (
            f"User Query: {query}\n\n"
            f"Available Documents:\n{candidate_descriptions}\n\n"
            "Select the most relevant documents to answer the query. "
            "For each, decide whether to read the 'summary' (for overview) or 'full' (for details). "
            "Return a JSON list of objects with 'id' and 'type' ('summary' or 'full'). "
            "Limit to 3 documents max."
        )

        try:
            response = self.llm.chat_completion([
                {"role": "system", "content": "You are a retrieval optimizer. Output JSON only."},
                {"role": "user", "content": prompt}
            ], temperature=0.0)

            clean_json = response.replace("```json", "").replace("```", "").strip()
            decisions = json.loads(clean_json)

            files = []
            for d in decisions:
                doc_id = d.get("id")
                read_type = d.get("type")

                cand = next((c for c in candidates if c["id"] == doc_id), None)
                if cand:
                    if read_type == "full" and cand.get("full_path"):
                        files.append(cand["full_path"])
                    elif cand.get("summary_path"):
                        files.append(cand["summary_path"])
                    elif cand.get("full_path"):
                        files.append(cand["full_path"])

            return files
        except Exception as e:
            logger.error(f"Error deciding files: {e}")
            return []
