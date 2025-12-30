# app/api/routes.py
from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, HTTPException

from app.services import IntakeSessionService
from app.intake.state import IntakeState
from app.intake.summarizer import build_structured_intake_with_llm
from app.llm import OpenAILLMClient
from app.rag import index_encounter_for_rag, answer_doctor_question
from app.db import SessionLocal
from app.models import StructuredIntake
from app.intake.schema import StructuredIntakeModel
from .schemas import (
    StartIntakeRequest,
    StartIntakeResponse,
    IntakeMessageRequest,
    IntakeMessageResponse,
    QARequest,
    QAResponse,
    RetrievedChunkSchema,
    StructuredIntakeResponse,
)

router = APIRouter()

_session_states: Dict[str, IntakeState] = {}

_service = IntakeSessionService()
_llm_client = OpenAILLMClient()


@router.post("/intake/start", response_model=StartIntakeResponse)
def start_intake(payload: StartIntakeRequest) -> StartIntakeResponse:
    """
    Start a new intake session.
    Creates Patient + Encounter + first assistant question.
    """
    display_name = payload.patient_display_name or "Web Demo Patient"

    state, first_question, patient_id, encounter_id = _service.start_session(
        patient_display_name=display_name
    )

    _session_states[encounter_id] = state

    return StartIntakeResponse(
        patient_id=patient_id,
        encounter_id=encounter_id,
        first_question=first_question,
        stage=state.stage.value,
    )


@router.post("/intake/message", response_model=IntakeMessageResponse)
def intake_message(payload: IntakeMessageRequest) -> IntakeMessageResponse:
    encounter_id = payload.encounter_id
    state = _session_states.get(encounter_id)

    if state is None:
        raise HTTPException(
            status_code=404,
            detail="Encounter state not found. Start a new intake session.",
        )

    state, next_q = _service.handle_turn(
        state=state,
        encounter_id=encounter_id,
        patient_message=payload.message,
    )
    _session_states[encounter_id] = state

    is_complete = next_q is None

    if is_complete:
        build_structured_intake_with_llm(encounter_id, llm_client=_llm_client)
        index_encounter_for_rag(encounter_id)

    return IntakeMessageResponse(
        next_question=next_q,
        is_complete=is_complete,
        stage=state.stage.value,
    )


@router.get(
    "/encounters/{encounter_id}/structured",
    response_model=StructuredIntakeResponse,
)
def get_structured_intake(encounter_id: str) -> StructuredIntakeResponse:
    session = SessionLocal()
    try:
        db_obj = session.get(StructuredIntake, encounter_id)
        if db_obj is None:
            raise HTTPException(
                status_code=404,
                detail="Structured intake not found for this encounter.",
            )

        model = StructuredIntakeModel.model_validate(db_obj.data)
        return StructuredIntakeResponse(**model.model_dump())
    finally:
        session.close()


@router.post("/patient/qa", response_model=QAResponse)
def patient_qa(payload: QARequest) -> QAResponse:
    answer, chunks = answer_doctor_question(
        patient_id=payload.patient_id,
        question=payload.question,
        llm_client=_llm_client,
        k=5,
    )

    chunk_schemas = [
        RetrievedChunkSchema(
            id=c.id,
            encounter_id=c.encounter_id,
            source_type=c.source_type,
            text=c.text,
            score=c.score,
        )
        for c in chunks
    ]

    return QAResponse(answer=answer, chunks=chunk_schemas)
