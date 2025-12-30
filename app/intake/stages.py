# app/intake/stages.py
from enum import Enum


class IntakeStage(str, Enum):
    CHIEF_COMPLAINT = "chief_complaint"
    SYMPTOM_DETAILS = "symptom_details"
    SAFETY_CHECKS = "safety_checks"
    HISTORY = "history"
    WRAP_UP = "wrap_up"
    DONE = "done"
