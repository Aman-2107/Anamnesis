# app/intake/agent.py
from __future__ import annotations

from typing import Optional, Dict, List

from app.intake.state import IntakeState, IntakeTurn
from app.intake.stages import IntakeStage


class IntakeAgent:
    """
    IntakeAgent manages a multi-stage intake conversation.

    Stages:
      - chief complaint
      - symptom details
      - safety checks
      - history
      - wrap-up

    For now, questions are rule-based and taken from fixed templates.
    Later we can:
      - let an LLM paraphrase / adapt questions
      - adapt which questions to ask based on earlier answers.
    """

    # Maximum number of questions to ask in each stage (upper bounds).
    MAX_QUESTIONS_PER_STAGE: Dict[IntakeStage, int] = {
        IntakeStage.CHIEF_COMPLAINT: 1,
        IntakeStage.SYMPTOM_DETAILS: 3,  # out of 5 candidates
        IntakeStage.SAFETY_CHECKS: 2,    # out of 2 candidates
        IntakeStage.HISTORY: 3,          # out of 5 candidates
        IntakeStage.WRAP_UP: 1,
    }

    # Question templates per stage.
    QUESTIONS: Dict[IntakeStage, List[str]] = {
        IntakeStage.CHIEF_COMPLAINT: [
            "To start, can you tell me in your own words what brings you in today?",
        ],
        IntakeStage.SYMPTOM_DETAILS: [
            "When did this problem first start?",
            "Has it been getting better, worse, or staying the same?",
            "Can you describe where in your body you notice it most?",
            "On a scale from 0 to 10, how bad is it at its worst?",
            "Is there anything that makes it better or worse?",
        ],
        IntakeStage.SAFETY_CHECKS: [
            "Have you noticed any alarming or sudden changes, like chest pain, trouble breathing, or feeling faint?",
            "Is there anything about your symptoms that particularly worries you?",
        ],
        IntakeStage.HISTORY: [
            "Do you have any ongoing medical conditions that a doctor has diagnosed in the past?",
            "What medications are you currently taking, including over-the-counter or herbal remedies?",
            "Do you have any allergies to medications, foods, or anything else?",
            "Is there any important family medical history you think your doctor should know about?",
            "Could you briefly describe your lifestyle, such as smoking, alcohol, or exercise habits?",
        ],
        IntakeStage.WRAP_UP: [
            "Is there anything else you would like your doctor to know before they review this information?",
        ],
        IntakeStage.DONE: [],
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> tuple[IntakeState, str]:
        """
        Initialise a new intake session and return:
          - initial state
          - the first assistant question to show to the patient
        """
        state = IntakeState(stage=IntakeStage.CHIEF_COMPLAINT)
        first_question = self._next_question(state)
        if first_question is None:
            # Very unlikely, but be defensive
            state.is_complete = True
            return state, "I have no questions to ask at this time."

        self._record_assistant_turn(state, first_question)
        state.stage_question_count = 1
        return state, first_question

    def step(self, state: IntakeState, patient_message: str) -> tuple[IntakeState, Optional[str]]:
        """
        Take a patient message, update the state, and return:
          - updated state
          - next assistant question (or None if we’re done)
        """
        if state.is_complete or state.stage == IntakeStage.DONE:
            # Conversation already finished
            return state, None

        # Record patient reply
        self._record_patient_turn(state, patient_message)

        # Decide whether to stay in this stage or move on
        if self._should_advance_stage(state):
            self._advance_stage(state)

        if state.stage == IntakeStage.DONE:
            state.is_complete = True
            return state, None

        # Ask the next question within the current stage
        next_q = self._next_question(state)
        if next_q is None:
            # No more questions left in this stage → move to DONE
            self._advance_stage_to_done(state)
            state.is_complete = True
            return state, None

        self._record_assistant_turn(state, next_q)
        state.stage_question_count += 1
        return state, next_q

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_patient_turn(self, state: IntakeState, content: str) -> None:
        state.turns.append(IntakeTurn(role="patient", content=content))

    def _record_assistant_turn(self, state: IntakeState, content: str) -> None:
        state.turns.append(IntakeTurn(role="assistant", content=content))

    def _should_advance_stage(self, state: IntakeState) -> bool:
        """
        Decide whether we’ve asked enough questions in the current stage.
        """
        max_q = self.MAX_QUESTIONS_PER_STAGE.get(state.stage, 0)
        return state.stage_question_count >= max_q

    def _advance_stage(self, state: IntakeState) -> None:
        """
        Move from the current stage to the next logical one.
        """
        state.stage = self._next_stage(state.stage)
        state.stage_question_count = 0

    def _advance_stage_to_done(self, state: IntakeState) -> None:
        state.stage = IntakeStage.DONE
        state.stage_question_count = 0

    def _next_stage(self, current: IntakeStage) -> IntakeStage:
        if current == IntakeStage.CHIEF_COMPLAINT:
            return IntakeStage.SYMPTOM_DETAILS
        if current == IntakeStage.SYMPTOM_DETAILS:
            return IntakeStage.SAFETY_CHECKS
        if current == IntakeStage.SAFETY_CHECKS:
            return IntakeStage.HISTORY
        if current == IntakeStage.HISTORY:
            return IntakeStage.WRAP_UP
        if current == IntakeStage.WRAP_UP:
            return IntakeStage.DONE
        return IntakeStage.DONE

    def _next_question(self, state: IntakeState) -> Optional[str]:
        """
        Pick the next question for the current stage, based on how many
        questions we've already asked in that stage.

        - Uses state.stage to look up the candidate list.
        - Uses state.stage_question_count as a 0-based index.
        - If we've exhausted the list, returns None.
        """
        candidates = self.QUESTIONS.get(state.stage, [])
        if not candidates:
            return None

        index = state.stage_question_count  # 0-based
        if index >= len(candidates):
            return None

        return candidates[index]
