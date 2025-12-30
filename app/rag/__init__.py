# app/rag/__init__.py
from .embeddings import EmbeddingClient, get_embedding_client
from .indexer import index_encounter_for_rag
from .retriever import retrieve_patient_chunks
from .qa import answer_doctor_question

__all__ = [
    "EmbeddingClient",
    "get_embedding_client",
    "index_encounter_for_rag",
    "retrieve_patient_chunks",
    "answer_doctor_question",
]
