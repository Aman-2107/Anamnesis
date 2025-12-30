# app/rag/retriever.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.rag.embeddings import get_embedding_client


@dataclass
class RetrievedChunk:
    id: int
    encounter_id: str | None
    source_type: str
    text: str
    score: float  # approximate distance (lower is better)


def _get_session() -> Session:
    return SessionLocal()


def retrieve_patient_chunks(
    patient_id: str,
    query: str,
    k: int = 5,
) -> List[RetrievedChunk]:
    """
    Retrieve top-k chunks for a given patient and query using pgvector similarity.
    """
    emb_client = get_embedding_client()
    query_emb = emb_client.embed([query])[0]  # shape (dim,)

    session = _get_session()
    try:
        sql = text(
            """
            SELECT id, encounter_id, source_type, text,
                   (embedding <-> CAST(:query_embedding AS vector)) AS distance
            FROM patient_chunks
            WHERE patient_id = :patient_id
            ORDER BY embedding <-> CAST(:query_embedding AS vector)
            LIMIT :k;
            """
        )

        rows = session.execute(
            sql,
            {
                "patient_id": patient_id,
                "query_embedding": query_emb.tolist(),
                "k": k,
            },
        ).fetchall()

        chunks: List[RetrievedChunk] = []
        for row in rows:
            chunks.append(
                RetrievedChunk(
                    id=row.id,
                    encounter_id=row.encounter_id,
                    source_type=row.source_type,
                    text=row.text,
                    score=float(row.distance) if row.distance is not None else 0.0,
                )
            )
        return chunks
    finally:
        session.close()
