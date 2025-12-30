# app/intake/summarizer.py
from __future__ import annotations

import json
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Encounter, Utterance, StructuredIntake
from app.intake.schema import StructuredIntakeModel, Symptom, Medication, Allergy
from app.llm import LLMClient



def _get_session() -> Session:
    return SessionLocal()


def _load_utterances_for_encounter(session: Session, encounter_id: str) -> List[Utterance]:
    stmt = (
        select(Utterance)
        .where(Utterance.encounter_id == encounter_id)
        .order_by(Utterance.ts.asc(), Utterance.id.asc())
    )
    return list(session.scalars(stmt))


def _extract_chief_complaint(utterances: List[Utterance]) -> str | None:
    """
    Very simple heuristic:
      - take the first patient utterance text as the chief complaint.
    """
    for utt in utterances:
        if utt.speaker == "patient":
            return utt.text.strip()
    return None


def _extract_patient_goals(utterances: List[Utterance]) -> str | None:
    """
    Heuristic:
      - last patient utterance is treated as 'anything else' / goals.
    """
    last_patient_text = None
    for utt in utterances:
        if utt.speaker == "patient":
            last_patient_text = utt.text.strip()
    return last_patient_text


def _extract_symptoms(utterances: List[Utterance]) -> List[Symptom]:
    """
    For now, we just create a single generic symptom if a chief complaint exists.
    Later this will be replaced by an LLM-based extractor.
    """
    cc = _extract_chief_complaint(utterances)
    if not cc:
        return []

    return [
        Symptom(
            name="reported symptom",
            onset=None,
            duration=None,
            character=None,
            severity=None,
            associated_symptoms=[],
            red_flags=[],
        )
    ]


def _extract_medications(utterances: List[Utterance]) -> List[Medication]:
    """
    Placeholder: we don't parse medications yet.
    We return an empty list and will let the LLM fill this in later.
    """
    return []


def _extract_allergies(utterances: List[Utterance]) -> List[Allergy]:
    """
    Placeholder: no allergy parsing yet.
    """
    return []


def build_structured_intake_for_encounter(encounter_id: str) -> StructuredIntakeModel:
    """
    Heuristic baseline: builds a StructuredIntakeModel from an encounter
    without using an LLM.
    """
    session = _get_session()
    try:
        encounter = session.get(Encounter, encounter_id)
        if encounter is None:
            raise ValueError(f"Encounter {encounter_id} not found")

        utterances = _load_utterances_for_encounter(session, encounter_id)

        chief_complaint = _extract_chief_complaint(utterances)
        patient_goals = _extract_patient_goals(utterances)
        symptoms = _extract_symptoms(utterances)
        medications = _extract_medications(utterances)
        allergies = _extract_allergies(utterances)

        intake_model = StructuredIntakeModel(
            chief_complaint=chief_complaint,
            symptoms=symptoms,
            medications=medications,
            allergies=allergies,
            past_medical_history=[],
            family_history=[],
            social_history=[],
            red_flags=[],
            patient_goals=patient_goals,
            other_notes=None,
        )

        existing = session.get(StructuredIntake, encounter_id)
        if existing is None:
            db_obj = StructuredIntake(
                encounter_id=encounter_id,
                data=intake_model.model_dump(),
            )
            session.add(db_obj)
        else:
            existing.data = intake_model.model_dump()

        session.commit()
        return intake_model
    finally:
        session.close()

def _build_transcript_text(utterances: List[Utterance]) -> str:
    """
    Build a plain text transcript like:

      assistant: ...
      patient: ...

    for use in the LLM prompt.
    """
    lines: List[str] = []
    for utt in utterances:
        role = "assistant" if utt.speaker == "assistant" else "patient"
        lines.append(f"{role}: {utt.text}")
    return "\n".join(lines)


def _clean_json_from_llm(raw: str) -> dict:
    """
    Try to robustly parse JSON from the LLM response.
    Handles cases where the model wraps it in ```json ... ``` fences.
    """
    text = raw.strip()

    if text.startswith("```"):
        # Strip markdown fences if present
        # e.g. ```json ... ```
        text = text.lstrip("`")
        # After stripping leading backticks, remove possible "json"
        if text.lower().startswith("json"):
            text = text[4:]
        # Remove trailing backticks
        text = text.rstrip("`").strip()

    return json.loads(text)


def build_structured_intake_with_llm(
    encounter_id: str,
    llm_client: LLMClient,
) -> StructuredIntakeModel:
    """
    Use an LLM to build a StructuredIntakeModel from the full transcript,
    then upsert it into structured_intake.

    Falls back to the heuristic version if anything goes wrong.
    """
    session = _get_session()
    try:
        encounter = session.get(Encounter, encounter_id)
        if encounter is None:
            raise ValueError(f"Encounter {encounter_id} not found")

        utterances = _load_utterances_for_encounter(session, encounter_id)
        transcript = _build_transcript_text(utterances)

        schema_description = """
You must return a single JSON object with the following structure:

{
  "chief_complaint": string or null,
  "symptoms": [
    {
      "name": string,
      "onset": string or null,
      "duration": string or null,
      "location": string or null,
      "character": string or null,
      "severity": string or null,
      "aggravating_factors": string or null,
      "relieving_factors": string or null,
      "associated_symptoms": [string, ...],
      "red_flags": [string, ...]
    },
    ...
  ],
  "medications": [
    {
      "name": string,
      "dose": string or null,
      "frequency": string or null,
      "route": string or null,
      "indication": string or null
    },
    ...
  ],
  "allergies": [
    {
      "substance": string,
      "reaction": string or null,
      "severity": string or null
    },
    ...
  ],
  "past_medical_history": [string, ...],
  "family_history": [string, ...],
  "social_history": [string, ...],
  "red_flags": [string, ...],
  "patient_goals": string or null,
  "other_notes": string or null
}
"""

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an AI clinical intake assistant. "
                    "Given a patient–assistant intake conversation, "
                    "you extract key clinical information and output strictly formatted JSON.\n\n"
                    "Do NOT invent details that are not clearly implied. "
                    "Leave fields null or empty lists if information is missing.\n"
                ),
            },
            {
                "role": "user",
                "content": (
                    "Here is the transcript of an intake conversation between a patient "
                    "and an AI assistant. Read it carefully and extract the structured information.\n\n"
                    f"{schema_description}\n\n"
                    "Transcript:\n"
                    f"{transcript}\n\n"
                    "Return ONLY the JSON object, with no additional commentary."
                ),
            },
        ]

        raw = llm_client.chat(messages, temperature=0.1)
        data_dict = _clean_json_from_llm(raw)

        # Validate against our Pydantic schema
        intake_model = StructuredIntakeModel.model_validate(data_dict)

        # Upsert into structured_intake
        existing = session.get(StructuredIntake, encounter_id)
        if existing is None:
            db_obj = StructuredIntake(
                encounter_id=encounter_id,
                data=intake_model.model_dump(),
            )
            session.add(db_obj)
        else:
            existing.data = intake_model.model_dump()

        session.commit()
        return intake_model

    except Exception as e:
        # On any error, log (if you add logging) and fall back
        print(f"[LLM summarizer] Error: {e}. Falling back to heuristic builder.")
        session.rollback()
        return build_structured_intake_for_encounter(encounter_id)
    finally:
        session.close()

