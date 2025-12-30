# app/intake/state.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from app.intake.stages import IntakeStage
from app.intake.schema import StructuredIntakeModel


@dataclass
class IntakeTurn:
    role: str  # "patient" or "assistant"
    content: str


@dataclass
class IntakeState:
    """
    In-memory representation of an intake session.

    Later we’ll connect this to the DB (Encounter + Utterances),
    but for now this is enough to drive a CLI demo and tests.
    """

    stage: IntakeStage = IntakeStage.CHIEF_COMPLAINT
    turns: List[IntakeTurn] = field(default_factory=list)

    # How many questions the assistant has asked in the *current* stage
    stage_question_count: int = 0

    # We’ll fill this later from the full transcript using an LLM
    structured: StructuredIntakeModel = field(default_factory=StructuredIntakeModel)

    is_complete: bool = False
