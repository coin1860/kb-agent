import asyncio
import os
import logging
from typing import List, Dict, Any, Optional

from kb_agent.config import settings, get_project_root

logger = logging.getLogger(__name__)

class RerankClient:
    def __init__(self):
        self.llm: Any = None
        self._load_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        
    async def initialize(self):
        """Asynchronously initialize the reranker model if enabled."""
        if not settings.use_reranker or not settings.reranker_model_path:
            logger.info("Reranker is disabled or model path is not set.")
            return

        async with self._lock:
            if self._load_task is None and self.llm is None:
                self._load_task = asyncio.create_task(self._load_model())

    async def _load_model(self):
        try:
            from llama_cpp import Llama
            
            model_path_str = str(settings.reranker_model_path)
            model_path = os.path.expanduser(model_path_str)
            if not os.path.isabs(model_path):
                model_path = os.path.join(str(get_project_root()), model_path)
                
            if not os.path.exists(model_path):
                logger.error(f"Reranker model not found at {model_path}")
                return

            logger.info(f"Loading reranker model from {model_path}...")
            
            loop = asyncio.get_running_loop()
            
            # Use pooling_type=4 (LLAMA_POOLING_TYPE_RANK) and embedding=True to get sequence scores
            def create_llama():
                return Llama(
                    model_path=model_path,
                    embedding=True,
                    pooling_type=4,
                    verbose=False,
                    n_ctx=2048, # Sufficient context for query + chunk
                )

            self.llm = await loop.run_in_executor(None, create_llama)
            logger.info("Reranker model loaded successfully.")
            
        except ImportError:
            logger.error("llama-cpp-python is not installed. Please install it to use the reranker.")
        except Exception as e:
            logger.error(f"Failed to load reranker model: {e}")
        finally:
            self._load_task = None

    async def rerank(self, query: str, chunks: List[Dict[str, Any]], top_n: int = 3) -> List[Dict[str, Any]]:
        """Rerank a list of chunks based on a query."""
        if not settings.use_reranker:
            logger.debug("Reranker is disabled, returning original top_n chunks.")
            return chunks[:top_n]

        if self._load_task:
            logger.debug("Waiting for reranker model to finish loading...")
            await self._load_task

        if self.llm is None:
            logger.warning("Reranker model is not loaded, returning original top_n chunks.")
            return chunks[:top_n]

        logger.info(f"Reranking {len(chunks)} chunks...")
        scored_chunks = []
        
        loop = asyncio.get_running_loop()
        
        for chunk in chunks:
            content = chunk.get("content", "")
            # Assuming BGE-M3 cross-encoder format: <s>query</s></s>text</s>
            prompt = f"<s>{query}</s></s>{content}</s>"
            
            try:
                # Use a wrapper to avoid lambda issues with run_in_executor typing in some environments
                def get_embed():
                    return self.llm.create_embedding(prompt)

                res = await loop.run_in_executor(None, get_embed)
                
                # The score is the first float in the embedding array when using pooling_type=RANK
                score = res["data"][0]["embedding"][0]
                
                chunk_copy = chunk.copy()
                chunk_copy["rerank_score"] = float(score)
                scored_chunks.append(chunk_copy)
            except Exception as e:
                logger.error(f"Error reranking chunk: {e}")
                chunk_copy = chunk.copy()
                chunk_copy["rerank_score"] = -999.0
                scored_chunks.append(chunk_copy)
                
        # Sort chunks by rerank_score descending
        scored_chunks.sort(key=lambda x: x.get("rerank_score", -999.0), reverse=True)
        
        return scored_chunks[:top_n]

    def rerank_sync(self, query: str, chunks: List[Dict[str, Any]], top_n: int = 3) -> List[Dict[str, Any]]:
        """Synchronously rerank a list of chunks based on a query."""
        if not settings.use_reranker:
            logger.debug("Reranker is disabled, returning original top_n chunks.")
            return chunks[:top_n]

        if self.llm is None:
            logger.warning("Reranker model is not loaded, returning original top_n chunks.")
            return chunks[:top_n]

        logger.info(f"[Sync] Reranking {len(chunks)} chunks...")
        scored_chunks = []
        
        for chunk in chunks:
            content = chunk.get("content", "")
            prompt = f"<s>{query}</s></s>{content}</s>"
            
            try:
                res = self.llm.create_embedding(prompt)
                score = res["data"][0]["embedding"][0]
                chunk_copy = chunk.copy()
                chunk_copy["rerank_score"] = float(score)
                scored_chunks.append(chunk_copy)
            except Exception as e:
                logger.error(f"Error reranking chunk: {e}")
                chunk_copy = chunk.copy()
                chunk_copy["rerank_score"] = -999.0
                scored_chunks.append(chunk_copy)
                
        scored_chunks.sort(key=lambda x: x.get("rerank_score", -999.0), reverse=True)
        return scored_chunks[:top_n]

# Global instance
reranker_client = RerankClient()
