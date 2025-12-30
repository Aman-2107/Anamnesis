# app/rag/embeddings.py
from __future__ import annotations

from functools import lru_cache
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import get_settings


class EmbeddingClient:
    """
    Thin wrapper around a sentence-transformers model.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        settings = get_settings()
        self.dim = settings.embedding_dim

    def embed(self, texts: List[str]) -> np.ndarray:
        """
        Returns a numpy array of shape (len(texts), dim).
        """
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)

        embeddings = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        if embeddings.shape[1] != self.dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.dim}, got {embeddings.shape[1]}"
            )
        return embeddings.astype(np.float32)


@lru_cache(maxsize=1)
def get_embedding_client() -> EmbeddingClient:
    return EmbeddingClient()
