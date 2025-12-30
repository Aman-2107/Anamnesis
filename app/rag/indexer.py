# app/rag/indexer.py
from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Patient, Encounter, StructuredIntake, Utterance, PatientChunk
from app.intake.schema import StructuredIntakeModel
from app.rag.embeddings import get_embedding_client


def _get_session() -> Session:
    return SessionLocal()


def _load_encounter_with_structured(session: Session, encounter_id: str):
    enc = session.get(Encounter, encounter_id)
    if enc is None:
        raise ValueError(f"Encounter {encounter_id} not found")

    patient = session.get(Patient, enc.patient_id)
    if patient is None:
        raise ValueError(f"Patient {enc.patient_id} not found")

    structured = session.get(StructuredIntake, encounter_id)
    structured_model: StructuredIntakeModel | None = None
    if structured is not None:
        structured_model = StructuredIntakeModel.model_validate(structured.data)

    # Load utterances ordered by time
    utts = (
        session.query(Utterance)
        .filter(Utterance.encounter_id == encounter_id)
        .order_by(Utterance.ts.asc(), Utterance.id.asc())
        .all()
    )

    return patient, enc, structured_model, utts


def _build_chunks_from_structured(
    structured: StructuredIntakeModel | None,
) -> List[tuple[str, str]]:
    """
    Build (source_type, text) chunks from structured intake.
    """
    chunks: List[tuple[str, str]] = []
    if structured is None:
        return chunks

    if structured.chief_complaint:
        chunks.append(
            (
                "structured",
                f"Chief complaint: {structured.chief_complaint}",
            )
        )

    if structured.symptoms:
        symptom_strs = []
        for s in structured.symptoms:
            parts = [f"name: {s.name}"]
            if s.onset:
                parts.append(f"onset: {s.onset}")
            if s.duration:
                parts.append(f"duration: {s.duration}")
            if s.location:
                parts.append(f"location: {s.location}")
            if s.character:
                parts.append(f"character: {s.character}")
            if s.severity:
                parts.append(f"severity: {s.severity}")
            if s.associated_symptoms:
                parts.append(f"associated: {', '.join(s.associated_symptoms)}")
            if s.red_flags:
                parts.append(f"red_flags: {', '.join(s.red_flags)}")
            symptom_strs.append("; ".join(parts))
        chunks.append(
            (
                "structured",
                "Symptoms: " + " | ".join(symptom_strs),
            )
        )

    if structured.medications:
        med_strs = []
        for m in structured.medications:
            parts = [m.name]
            if m.dose:
                parts.append(m.dose)
            if m.frequency:
                parts.append(m.frequency)
            med_strs.append(", ".join(parts))
        chunks.append(
            (
                "structured",
                "Medications: " + "; ".join(med_strs),
            )
        )

    if structured.allergies:
        all_strs = []
        for a in structured.allergies:
            parts = [a.substance]
            if a.reaction:
                parts.append(f"reaction: {a.reaction}")
            all_strs.append(", ".join(parts))
        chunks.append(
            (
                "structured",
                "Allergies: " + "; ".join(all_strs),
            )
        )

    if structured.past_medical_history:
        chunks.append(
            (
                "structured",
                "Past medical history: " + "; ".join(structured.past_medical_history),
            )
        )

    if structured.family_history:
        chunks.append(
            (
                "structured",
                "Family history: " + "; ".join(structured.family_history),
            )
        )

    if structured.social_history:
        chunks.append(
            (
                "structured",
                "Social history: " + "; ".join(structured.social_history),
            )
        )

    if structured.red_flags:
        chunks.append(
            (
                "structured",
                "Red flags: " + "; ".join(structured.red_flags),
            )
        )

    if structured.patient_goals:
        chunks.append(
            (
                "structured",
                f"Patient goals: {structured.patient_goals}",
            )
        )

    if structured.other_notes:
        chunks.append(
            (
                "structured",
                f"Other notes: {structured.other_notes}",
            )
        )

    return chunks


def _build_chunks_from_utterances(utts: list[Utterance]) -> List[tuple[str, str]]:
    qas = []
    current_question = None

    for u in utts:
        if u.speaker == "assistant":
            current_question = u.text
        else:
            # patient
            if current_question:
                qas.append(f"Q: {current_question} A: {u.text}")
            else:
                qas.append(f"A: {u.text}")

    chunks: List[tuple[str, str]] = []
    if qas:
        chunks.append(("utterance", "Conversation QA pairs: " + " | ".join(qas)))
    return chunks


def index_encounter_for_rag(encounter_id: str) -> int:
    """
    Build RAG chunks for a given encounter and insert them into patient_chunks.

    Returns: number of chunks inserted.
    """
    session = _get_session()
    try:
        patient, enc, structured_model, utts = _load_encounter_with_structured(
            session, encounter_id
        )

        chunks: List[tuple[str, str]] = []
        chunks.extend(_build_chunks_from_structured(structured_model))
        chunks.extend(_build_chunks_from_utterances(utts))

        if not chunks:
            print(f"No chunks to index for encounter {encounter_id}")
            return 0

        texts = [c[1] for c in chunks]
        source_types = [c[0] for c in chunks]

        emb_client = get_embedding_client()
        embeddings = emb_client.embed(texts)

        # Insert into patient_chunks
        inserted = 0
        for (source_type, text), emb in zip(chunks, embeddings):
            pc = PatientChunk(
                patient_id=patient.id,
                encounter_id=encounter_id,
                source_type=source_type,
                text=text,
                embedding=emb,
            )
            session.add(pc)
            inserted += 1

        session.commit()
        print(f"Indexed {inserted} chunks for encounter {encounter_id}")
        return inserted
    finally:
        session.close()
