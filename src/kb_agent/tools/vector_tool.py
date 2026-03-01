import chromadb
from chromadb.config import Settings
import chromadb.utils.embedding_functions as embedding_functions
import kb_agent.config as config
from typing import List, Dict, Optional, Any
import os

class VectorTool:
    def __init__(self, collection_name: str = "kb_docs"):
        settings = config.settings
        # Initialize ChromaDB client (local persistent)
        if settings and settings.docs_path:
            persist_dir = str(settings.docs_path / ".chroma")
        else:
            persist_dir = "./.chroma"

        os.makedirs(persist_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(path=persist_dir)

        # Get or create collection
        ef = None
        if settings and getattr(settings, "embedding_url", None):
            ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key="dummy",
                api_base=settings.embedding_url,
                model_name=settings.embedding_model if hasattr(settings, "embedding_model") and settings.embedding_model else "text-embedding-ada-002"
            )

        if ef:
            try:
                self.collection = self.client.get_collection(name=collection_name, embedding_function=ef)
            except Exception:
                try:
                    self.collection = self.client.create_collection(name=collection_name, embedding_function=ef)
                except Exception:
                    # Fallback if there's a race condition or mismatch
                    self.collection = self.client.get_or_create_collection(name=collection_name)
        else:
            self.collection = self.client.get_or_create_collection(name=collection_name)

    def add_documents(self, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]):
        """
        Adds documents to the vector store.
        """
        if not documents:
            return

        try:
            self.collection.upsert(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
        except Exception as e:
            print(f"Error adding documents to ChromaDB: {e}")

    def query(self, query_text: str, n_results: int = 5, where: Optional[Dict[str, Any]] = None):
        """
        Semantic search (raw).
        """
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where
            )
            return results
        except Exception as e:
            print(f"Error querying ChromaDB: {e}")
            return None

    def search(self, query_text: str, n_results: int = 5, threshold: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Convenience wrapper around query.
        Returns a list of dicts with 'id', 'content', 'metadata', 'score'.
        Filters out results where distance >= threshold (if threshold is provided).
        """
        # Fallback to configured default if not provided
        if threshold is None:
            settings = config.settings
            threshold = settings.vector_score_threshold if settings and settings.vector_score_threshold is not None else 0.5
            
        raw_results = self.query(query_text, n_results=n_results)
        if not raw_results or not raw_results['ids']:
            return []

        processed_results = []
        ids = raw_results['ids'][0]
        distances = raw_results['distances'][0] if raw_results.get('distances') else []
        metadatas = raw_results['metadatas'][0] if raw_results.get('metadatas') else []
        documents = raw_results['documents'][0] if raw_results.get('documents') else []

        for i, doc_id in enumerate(ids):
            distance = distances[i] if i < len(distances) else 0.0
            
            # Filter by threshold (L2 distance: shorter is better, so discard if distance >= threshold)
            # Default ChromaDB embedding space metric is l2
            if threshold is not None and distance >= threshold:
                continue
                
            processed_results.append({
                "id": doc_id,
                "content": documents[i] if i < len(documents) else "",
                "metadata": metadatas[i] if i < len(metadatas) else {},
                "score": distance
            })

        return processed_results
