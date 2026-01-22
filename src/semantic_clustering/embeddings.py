"""
Semantic embeddings module for issue clustering.

Provides embeddings generation using Sentence-BERT or Cohere API.
"""

from typing import Union, List
import numpy as np


class EmbeddingsModel:
    """Wrapper for generating semantic embeddings.
    
    Uses Sentence-Transformers (local, no API key) by default.
    Can be switched to Cohere API (cloud-based) for better quality.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", 
                 provider: str = "sentence_transformers"):
        """Initialize embeddings model.
        
        Args:
            model_name: Model identifier
                - "sentence-transformers/all-MiniLM-L6-v2" (384-dim, fast, local)
                - "sentence-transformers/all-mpnet-base-v2" (768-dim, better quality)
                - "cohere" (uses Cohere API, requires API key)
            provider: "sentence_transformers" or "cohere"
        """
        self.model_name = model_name
        self.provider = provider
        self.model = None
        self._initialize_model()

    def _initialize_model(self):
        """Initialize the actual embeddings model."""
        if self.provider == "sentence_transformers":
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(self.model_name)
            except ImportError:
                raise ImportError(
                    "sentence-transformers not installed. "
                    "Install with: pip install sentence-transformers"
                )
        elif self.provider == "cohere":
            try:
                import cohere
                self.model = cohere.Client()
            except ImportError:
                raise ImportError(
                    "cohere not installed. "
                    "Install with: pip install cohere"
                )
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for a single text.
        
        Args:
            text: Input text to embed
            
        Returns:
            numpy array of embeddings (float32)
        """
        if self.provider == "sentence_transformers":
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.astype(np.float32)
        elif self.provider == "cohere":
            response = self.model.embed(
                texts=[text],
                model="embed-english-v3.0",
                input_type="search_document"
            )
            return np.array(response.embeddings[0], dtype=np.float32)

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Generate embeddings for multiple texts at once.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            2D numpy array (N x embedding_dim)
        """
        if self.provider == "sentence_transformers":
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return embeddings.astype(np.float32)
        elif self.provider == "cohere":
            response = self.model.embed(
                texts=texts,
                model="embed-english-v3.0",
                input_type="search_document"
            )
            return np.array(response.embeddings, dtype=np.float32)

    def get_embedding_dim(self) -> int:
        """Get the dimension of embeddings produced by this model.
        
        Returns:
            Embedding dimension (e.g., 384 for MiniLM, 768 for MPNet)
        """
        if self.provider == "sentence_transformers":
            return self.model.get_sentence_embedding_dimension()
        elif self.provider == "cohere":
            # Cohere embed-english-v3.0 produces 1024-dim embeddings
            return 1024


def normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    """Normalize embedding to unit length (L2 normalization).
    
    This allows using cosine similarity as dot product: cos(a, b) = a·b
    when both are unit length.
    
    Args:
        embedding: numpy array of floats
        
    Returns:
        L2-normalized embedding (unit length)
    """
    norm = np.linalg.norm(embedding)
    if norm == 0:
        return embedding
    return (embedding / norm).astype(np.float32)


def cosine_similarity(emb1: np.ndarray, emb2: np.ndarray) -> float:
    """Compute cosine similarity between two embeddings.
    
    Args:
        emb1: First embedding (should be normalized)
        emb2: Second embedding (should be normalized)
        
    Returns:
        Cosine similarity in range [-1, 1], typically [0, 1] for normalized embeddings
    """
    similarity = float(np.dot(emb1, emb2))
    # Clamp to [-1, 1] to handle numerical errors
    return max(-1.0, min(1.0, similarity))


__all__ = [
    'EmbeddingsModel',
    'normalize_embedding',
    'cosine_similarity',
]
