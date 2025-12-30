# app/api/schemas.py
from __future__ import annotations

from typing import Optional, List

from pydantic import BaseModel

from app.intake.schema import StructuredIntakeModel


class StartIntakeRequest(BaseModel):
    patient_display_name: Optional[str] = None


class StartIntakeResponse(BaseModel):
    patient_id: str
    encounter_id: str
    first_question: str
    stage: str


class IntakeMessageRequest(BaseModel):
    encounter_id: str
    message: str


class IntakeMessageResponse(BaseModel):
    next_question: Optional[str]
    is_complete: bool
    stage: str


class QARequest(BaseModel):
    patient_id: str
    question: str


class RetrievedChunkSchema(BaseModel):
    id: int
    encounter_id: Optional[str]
    source_type: str
    text: str
    score: float


class QAResponse(BaseModel):
    answer: str
    chunks: List[RetrievedChunkSchema]


class StructuredIntakeResponse(StructuredIntakeModel):
    pass
