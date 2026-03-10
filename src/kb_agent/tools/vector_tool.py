import chromadb
from chromadb.config import Settings
import chromadb.utils.embedding_functions as embedding_functions
import kb_agent.config as config
from typing import List, Dict, Optional, Any
import os

class ONNXEmbeddingFunction(embedding_functions.EmbeddingFunction):
    """
    Custom embedding function that loads a local ONNX model and tokenizer.
    Designed for BGE-like models (mean pooling + normalization).
    """
    def __init__(self, model_dir: str):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        
        self.model_dir = model_dir
        model_path = os.path.join(model_dir, "model.onnx")
        if not os.path.exists(model_path):
            model_path = os.path.join(model_dir, "onnx", "model.onnx")
            
        tokenizer_path = os.path.join(model_dir, "tokenizer.json")
        
        if not os.path.exists(model_path) or not os.path.exists(tokenizer_path):
            raise FileNotFoundError(f"Model ({model_path}) or Tokenizer ({tokenizer_path}) not found in {model_dir}")
        
        # Load the ONNX model
        self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        
        # Load the tokenizer
        self.tokenizer = Tokenizer.from_file(tokenizer_path)

    def mean_pooling(self, token_embeddings, attention_mask):
        import numpy as np
        # token_embeddings: [batch_size, seq_length, hidden_size]
        # attention_mask: [batch_size, seq_length]
        input_mask_expanded = np.expand_dims(attention_mask, -1)
        input_mask_expanded = np.broadcast_to(input_mask_expanded, token_embeddings.shape).astype(float)
        
        sum_embeddings = np.sum(token_embeddings * input_mask_expanded, axis=1)
        sum_mask = np.clip(np.sum(input_mask_expanded, axis=1), a_min=1e-9, a_max=None)
        return sum_embeddings / sum_mask
        
    def __call__(self, input: List[str]) -> List[List[float]]:
        import numpy as np
        
        if not input:
            return []
            
        # Tokenize
        encoded = self.tokenizer.encode_batch(input)
        
        # Prepare inputs for ONNX
        batch_input_ids = []
        batch_attention_mask = []
        batch_token_type_ids = []
        
        for enc in encoded:
            batch_input_ids.append(enc.ids)
            batch_attention_mask.append(enc.attention_mask)
            if hasattr(enc, 'type_ids'):
                batch_token_type_ids.append(enc.type_ids)
            else:
                batch_token_type_ids.append([0] * len(enc.ids))
                
        # Pad to max length in batch
        max_len = max(len(ids) for ids in batch_input_ids)
        
        for i in range(len(batch_input_ids)):
            pad_len = max_len - len(batch_input_ids[i])
            if pad_len > 0:
                batch_input_ids[i].extend([0] * pad_len)
                batch_attention_mask[i].extend([0] * pad_len)
                batch_token_type_ids[i].extend([0] * pad_len)
        
        ort_inputs = {
            "input_ids": np.array(batch_input_ids, dtype=np.int64),
            "attention_mask": np.array(batch_attention_mask, dtype=np.int64),
            "token_type_ids": np.array(batch_token_type_ids, dtype=np.int64)
        }
        
        # Run inference
        outputs = self.session.run(None, ort_inputs)
        
        # outputs[0] is typically the sequence output
        token_embeddings = outputs[0]
        
        # Perform mean pooling
        sentence_embeddings = self.mean_pooling(token_embeddings, ort_inputs["attention_mask"])
        
        # Normalize
        norms = np.linalg.norm(sentence_embeddings, axis=1, keepdims=True)
        sentence_embeddings = sentence_embeddings / np.clip(norms, a_min=1e-12, a_max=None)
        
        return sentence_embeddings.tolist()

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

        # Embedding logic fallback: URL > Configured Local ONNX > Built-in Default Local ONNX > Chroma Default
        if settings and getattr(settings, "embedding_url", None):
            ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key="dummy",
                api_base=settings.embedding_url,
                model_name=settings.embedding_model if hasattr(settings, "embedding_model") and settings.embedding_model else "text-embedding-ada-002"
            )
        else:
            # Determine Local Model Base Path and Model Name
            emb_model_name = getattr(settings, "embedding_model", None)
            if not emb_model_name:
                emb_model_name = "bge-small-zh-v1.5" # Fallback if not specified

            # Check configured base path, otherwise use default bundled model path
            base_path = str(settings.embedding_model_path) if settings and getattr(settings, "embedding_model_path", None) else os.path.join(os.getcwd(), "models")
            
            # Combine base path and model name
            model_path_str = os.path.join(base_path, emb_model_name)
            
            if os.path.exists(model_path_str):
                try:
                    ef = ONNXEmbeddingFunction(model_path_str)
                except Exception as e:
                    print(f"Warning: Failed to load local ONNX model from {model_path_str}: {e}")
                    print("Falling back to ChromaDB default embedding function.")
                    ef = None
            else:
                print(f"Warning: Expected local model path {model_path_str} does not exist.")
                print("Falling back to ChromaDB default embedding function.")
                ef = None

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
