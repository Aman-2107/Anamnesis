# app/rag/qa.py
from __future__ import annotations

from typing import List

from app.llm import LLMClient
from app.rag.retriever import retrieve_patient_chunks, RetrievedChunk


def _build_context(chunks: List[RetrievedChunk]) -> str:
    """
    Build a readable context string for the LLM, with simple citations.
    """
    lines = []
    for i, c in enumerate(chunks, start=1):
        ref = f"[chunk {i}, encounter={c.encounter_id}, source={c.source_type}]"
        lines.append(f"{ref} {c.text}")
    return "\n".join(lines)


def answer_doctor_question(
    patient_id: str,
    question: str,
    llm_client: LLMClient,
    k: int = 5,
) -> tuple[str, List[RetrievedChunk]]:
    """
    Use RAG over patient_chunks to answer a doctor's question about a patient.

    Returns:
      - answer string
      - list of retrieved chunks (for debugging / UI display)
    """
    chunks = retrieve_patient_chunks(patient_id=patient_id, query=question, k=k)

    if not chunks:
        return (
            "I couldn't find any information about that in this patient's records.",
            [],
        )

    context = _build_context(chunks)

    messages = [
        {
        "role": "system",
        "content": (
            "You are an AI assistant helping a doctor review a single patient's history. "
            "You are given context snippets from this patient's intake conversations and structured notes.\n\n"
            "RULES:\n"
            "- Answer ONLY using the provided context.\n"
            "- If the answer is not clearly supported by the context, say you don't know.\n"
            "- Keep answers short and direct (1–2 sentences).\n"
            "- When possible, mention which chunks support your answer using [chunk N]. "
            "Do not quote messy or confusing raw text verbatim; just summarise it."
        ),
    },
        {
            "role": "user",
            "content": (
                f"Doctor's question: {question}\n\n"
                "Here are context snippets from this patient's records:\n"
                f"{context}\n\n"
                "Based only on this context, answer the doctor's question. "
                "If you cannot answer from these snippets, say so clearly."
            ),
        },
    ]

    answer = llm_client.chat(messages, temperature=0.1)
    return answer, chunks
