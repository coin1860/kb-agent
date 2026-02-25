import logging
import json
import re
from typing import List, Dict, Any, Set
from kb_agent.llm import LLMClient
from kb_agent.tools.vector_tool import VectorTool
from kb_agent.tools.grep_tool import GrepTool
from kb_agent.tools.file_tool import FileTool
from kb_agent.security import Security
from kb_agent.audit import log_audit, log_search, log_llm_response

# Use the same logger name as configured in audit.py
logger = logging.getLogger("kb_agent_audit")

class Engine:
    def __init__(self):
        self.llm = LLMClient()
        self.vector_tool = VectorTool()
        self.grep_tool = GrepTool()
        self.file_tool = FileTool()

    def answer_query(self, user_query: str) -> str:
        """
        Main entry point for the agent to answer a user query.
        """
        log_audit("start_query", {"query": user_query})

        # 1. Initial Search
        candidates = self._hybrid_search(user_query)
        logger.info(f"Initial candidates count: {len(candidates)}")

        # 2. Autonomous Retry Logic
        if not candidates:
            log_audit("retry_logic", {"reason": "no_candidates", "original_query": user_query})
            new_queries = self._generate_alternative_queries(user_query)

            for q in new_queries:
                log_audit("retry_search", {"query": q})
                extra_candidates = self._hybrid_search(q)
                candidates.extend(extra_candidates)

            # De-duplicate
            candidates = self._deduplicate_candidates_list(candidates)
            logger.info(f"Candidates after retry: {len(candidates)}")

        if not candidates:
            return "I couldn't find any relevant documents in the knowledge base, even after trying alternative keywords."

        # 3. Decision (Heuristic + LLM)
        top_candidates = candidates[:5]

        files_to_read = self._decide_files_to_read(user_query, top_candidates)
        logger.info(f"LLM Decided files: {files_to_read}")

        # Fallback if LLM decision logic fails but we have strong candidates
        if not files_to_read and candidates:
            # Read at least the top candidate's full content or summary
            top = candidates[0]
            if top.get("full_path"):
                files_to_read.append(top["full_path"])
            elif top.get("summary_path"):
                files_to_read.append(top["summary_path"])
            logger.info(f"Fallback added files: {files_to_read}")

        # Deduplicate files_to_read
        files_to_read = list(set(files_to_read))

        if not files_to_read:
             logger.warning("No files to read after decision and fallback.")
             return "I identified potential documents but decided none were relevant enough to read."

        # 4. Read Content and Trace Links (Jira)
        context = []
        read_files = set() # Track what we read to avoid loops
        file_queue = list(files_to_read)

        # Regex for Jira-like IDs: [PROJ-123]
        JIRA_LINK_PATTERN = re.compile(r'\[([A-Z]+-\d+)\]')

        processed_count = 0
        MAX_FILES = 5 # Safety limit to avoid context overflow

        while file_queue and processed_count < MAX_FILES:
            file_path = file_queue.pop(0)
            if file_path in read_files:
                continue

            content = self.file_tool.read_file(file_path)
            if content:
                read_files.add(file_path)
                context.append(f"Source: {file_path}\nContent:\n{content}")
                processed_count += 1

                # Check for Jira Links in the content
                links = JIRA_LINK_PATTERN.findall(content)
                for link_id in links:
                    # Assumption: Linked docs are stored as [ID].md
                    linked_doc_path = f"{link_id}.md"

                    # Avoid re-queueing if already read or in queue
                    if linked_doc_path not in read_files and linked_doc_path not in file_queue:
                        # Add to queue. BFS.
                        file_queue.append(linked_doc_path)
                        log_audit("link_trace", {"from": file_path, "to": linked_doc_path})

        full_context = "\n\n".join(context)

        # 5. Synthesize Answer
        system_prompt = (
            "You are a helpful banking assistant. Answer the user's question based ONLY on the provided context. "
            "If the context doesn't contain the answer, say so. "
            "Be precise and professional."
        )
        user_prompt = f"Context:\n{full_context}\n\nQuestion: {user_query}"

        logger.info(f"Synthesizing answer with context length: {len(full_context)}")

        raw_response = self.llm.chat_completion([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ])

        log_llm_response(user_prompt, raw_response)

        # 6. Mask Sensitive Data
        final_response = Security.mask_sensitive_data(raw_response)

        return final_response

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
            filename = path.split("/")[-1]
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
