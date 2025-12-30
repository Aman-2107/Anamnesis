# app/intake/schema.py
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Symptom(BaseModel):
    name: str = Field(..., description="Symptom name, e.g. 'cough'")
    onset: Optional[str] = Field(
        None,
        description="Free-text onset, e.g. '3 weeks ago'",
    )
    duration: Optional[str] = None
    location: Optional[str] = None
    character: Optional[str] = None
    severity: Optional[str] = None
    aggravating_factors: Optional[str] = None
    relieving_factors: Optional[str] = None
    associated_symptoms: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)


class Medication(BaseModel):
    name: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    indication: Optional[str] = None


class Allergy(BaseModel):
    substance: str
    reaction: Optional[str] = None
    severity: Optional[str] = None


class StructuredIntakeModel(BaseModel):
    """
    Our target schema for one intake encounter.

    This is what the LLM will output as JSON and what we'll store
    in the structured_intake.data JSONB column.
    """

    chief_complaint: Optional[str] = None
    symptoms: List[Symptom] = Field(default_factory=list)
    medications: List[Medication] = Field(default_factory=list)
    allergies: List[Allergy] = Field(default_factory=list)

    past_medical_history: List[str] = Field(default_factory=list)
    family_history: List[str] = Field(default_factory=list)
    social_history: List[str] = Field(default_factory=list)

    red_flags: List[str] = Field(default_factory=list)
    patient_goals: Optional[str] = None
    other_notes: Optional[str] = None

    # Allow extra fields from the LLM without crashing
    model_config = {
        "extra": "ignore",
    }
