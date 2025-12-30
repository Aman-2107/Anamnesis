# app/services/intake_session.py
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import text

from app.db import SessionLocal, engine, Base
from app.models import Patient, Encounter, Utterance
from app.intake.agent import IntakeAgent
from app.intake.state import IntakeState


@contextmanager
def db_session():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """
    Ensure pgvector extension and create all tables.
    Call this once at startup (e.g. from scripts).
    """
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()

    Base.metadata.create_all(bind=engine)


class IntakeSessionService:
    """
    Service that coordinates:
      - creating Patient and Encounter rows
      - driving the IntakeAgent
      - persisting Utterances to the database
    """

    def __init__(self):
        self.agent = IntakeAgent()

    def start_session(
        self,
        patient_display_name: Optional[str] = None,
    ) -> Tuple[IntakeState, str, str, str]:
        """
        Start a new intake session.

        Returns:
          - intake state
          - first assistant question
          - patient_id
          - encounter_id
        """
        with db_session() as session:
            patient = Patient(display_name=patient_display_name)
            session.add(patient)
            session.flush()  # to get patient.id

            encounter = Encounter(
                patient_id=patient.id,
                started_at=datetime.now(timezone.utc),
                chief_complaint=None,
            )
            session.add(encounter)
            session.flush()  # to get encounter.id

            # Kick off the intake conversation
            state, first_question = self.agent.start()

            # Persist the first assistant utterance
            utterance = Utterance(
                encounter_id=encounter.id,
                speaker="assistant",
                text=first_question,
                ts=datetime.now(timezone.utc),
            )
            session.add(utterance)

            return state, first_question, patient.id, encounter.id

    def handle_turn(
        self,
        state: IntakeState,
        encounter_id: str,
        patient_message: str,
    ) -> Tuple[IntakeState, Optional[str]]:
        """
        Handle a single patient message:
          - persist patient's message to Utterances
          - step the IntakeAgent
          - persist assistant's next question (if any)

        Returns:
          - updated state
          - next assistant question (or None if done)
        """
        with db_session() as session:
            # Persist patient utterance
            patient_utt = Utterance(
                encounter_id=encounter_id,
                speaker="patient",
                text=patient_message,
                ts=datetime.now(timezone.utc),
            )
            session.add(patient_utt)

            # Step the agent
            state, next_q = self.agent.step(state, patient_message)

            # Persist assistant utterance (if any)
            if next_q is not None:
                assistant_utt = Utterance(
                    encounter_id=encounter_id,
                    speaker="assistant",
                    text=next_q,
                    ts=datetime.now(timezone.utc),
                )
                session.add(assistant_utt)

            return state, next_q
