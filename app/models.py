# app/models.py
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
import uuid

from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    JSON,
    CheckConstraint,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.db import Base, VectorType
from app.config import get_settings

settings = get_settings()


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=generate_uuid
    )
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    encounters: Mapped[list["Encounter"]] = relationship(
        "Encounter", back_populates="patient", cascade="all, delete-orphan"
    )


class Encounter(Base):
    __tablename__ = "encounters"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=generate_uuid
    )
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    chief_complaint: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped[Patient] = relationship(
        "Patient", back_populates="encounters"
    )
    utterances: Mapped[list["Utterance"]] = relationship(
        "Utterance", back_populates="encounter", cascade="all, delete-orphan"
    )
    structured_intake: Mapped["StructuredIntake"] = relationship(
        "StructuredIntake",
        back_populates="encounter",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Utterance(Base):
    __tablename__ = "utterances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    encounter_id: Mapped[str] = mapped_column(
        String, ForeignKey("encounters.id", ondelete="CASCADE"), nullable=False
    )
    speaker: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            "speaker IN ('patient', 'assistant')",
            name="ck_utterances_speaker_valid",
        ),
    )

    encounter: Mapped[Encounter] = relationship(
        "Encounter", back_populates="utterances"
    )


class StructuredIntake(Base):
    __tablename__ = "structured_intake"

    encounter_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("encounters.id", ondelete="CASCADE"),
        primary_key=True,
    )
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    encounter: Mapped[Encounter] = relationship(
        "Encounter", back_populates="structured_intake"
    )


class PatientChunk(Base):
    """
    Text chunks used for RAG over a patient's history.
    Backed by pgvector for embeddings.
    """
    __tablename__ = "patient_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    patient_id: Mapped[str] = mapped_column(
        String, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    encounter_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("encounters.id", ondelete="SET NULL"), nullable=True
    )

    source_type: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    embedding = mapped_column(
        VectorType(settings.embedding_dim), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('utterance', 'summary', 'structured')",
            name="ck_patient_chunks_source_type_valid",
        ),
    )
