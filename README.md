# Anamnesis – AI Patient Intake & Clinical Memory

Anamnesis is an AI-powered **patient intake assistant** and **clinical memory** system.

- Patients first chat with an intake bot that asks clinically inspired questions.
- A large language model converts the transcript into a **structured intake note** (chief complaint, symptoms, medications, allergies, history, red flags, etc.).
- Key information is stored and indexed in **PostgreSQL + pgvector**.
- Doctors can then ask **free-text questions** about a patient and get grounded answers with citations, using RAG (Retrieval-Augmented Generation).

> ⚠️ **Disclaimer**  
> This is a **research / portfolio project**. It is **not a medical device** and must **not** be used for real patient care or clinical decision making.

---

## ✨ Features

### 🗣 Multi-stage patient intake

The intake assistant walks through a structured, clinically inspired flow:

1. **Chief complaint** – what brings the patient in.
2. **Symptom details** – onset, course, location, severity, etc.
3. **Safety checks** – potential red-flag symptoms.
4. **History** – past medical history, medications, allergies, family & social history.
5. **Wrap-up** – anything else the patient wants the doctor to know.

Under the hood this is implemented as:

- `IntakeAgent` – a rule-based, stage-based agent.
- `IntakeState` – keeps track of stage, turns, and completion.
- `Utterance` rows in Postgres – each message (patient / assistant) is persisted.

---

### 🧠 LLM-based structured intake note

After the intake conversation completes:

1. The full transcript is assembled from `Utterance`s.
2. A large language model (LLaMA 3.3 70B via **Groq**, OpenAI-compatible API) is prompted to output **strict JSON**.
3. The JSON is validated against a Pydantic v2 schema: `StructuredIntakeModel`.
4. The validated record is stored as **JSONB** in the `structured_intake` table.

The structured note includes:

- `chief_complaint`
- `symptoms` (with onset, duration, location, character, severity, associated symptoms, red flags)
- `medications`
- `allergies`
- `past_medical_history`, `family_history`, `social_history`
- `red_flags`
- `patient_goals`, `other_notes`

---

### 📚 RAG over patient history (Postgres + pgvector)

To support doctor questions:

1. **Chunking**
   - Text chunks are built from:
     - structured intake fields (symptoms, meds, allergies, histories, red flags, goals)
     - merged patient utterances
     - merged assistant questions.
2. **Embeddings**
   - Chunks are embedded with `sentence-transformers/all-MiniLM-L6-v2` (384-dim).
3. **Vector store**
   - Embeddings are stored in the `patient_chunks` table using **pgvector**.
4. **Retrieval + QA**
   - For each doctor question:
     - embed the question,
     - run a pgvector similarity search over that patient’s chunks,
     - build a context prompt with the top-k chunks,
     - call the LLM with strict “only answer from context” instructions,
     - return an answer plus the chunks used (citations like `[chunk 1]`).

---

### 🧩 End-to-end app (backend + frontend)

**Backend**

- Python + FastAPI API
- PostgreSQL + pgvector (Docker Compose)
- SQLAlchemy 2.x ORM
- Pydantic v2 (`BaseModel`, `BaseSettings`)
- LLM client abstraction (`LLMClient` / `OpenAILLMClient`) configured for Groq

**Frontend**

- React + TypeScript (Vite)
- Tailwind CSS for styling
- Single-page layout:
  - **Left:** “Step 1 – Patient Intake” (chat UI + stage progress).
  - **Right:** “Step 2 – Doctor View” (structured summary + QA with supporting snippets).

---

## 🏗 Architecture Overview

**Backend modules**

- `app/config.py` – settings (DB URL, embedding dimension, LLM key, base URL, model name).
- `app/db.py` – SQLAlchemy engine, session factory, Base, pgvector type.
- `app/models.py` – ORM models:
  - `Patient`
  - `Encounter`
  - `Utterance`
  - `StructuredIntake`
  - `PatientChunk`
- `app/intake/`
  - `schema.py` – `StructuredIntakeModel` + nested types (`Symptom`, `Medication`, `Allergy`).
  - `stages.py` – `IntakeStage` enum.
  - `state.py` – `IntakeState`, `IntakeTurn`.
  - `agent.py` – rule-based intake agent.
  - `summarizer.py` – heuristic + LLM-based builders for `StructuredIntakeModel`.
- `app/llm/`
  - `client.py` – `LLMClient` interface and `OpenAILLMClient` that talks to Groq via OpenAI-compatible API (using `OPENAI_BASE_URL`).
- `app/services/`
  - `intake_session.py` – `IntakeSessionService`: orchestrates patient/encounter creation, intake agent, and utterance persistence; `init_db()` to create tables and pgvector extension.
- `app/rag/`
  - `embeddings.py` – SentenceTransformer wrapper (`all-MiniLM-L6-v2`).
  - `indexer.py` – builds chunks and inserts into `patient_chunks`.
  - `retriever.py` – pgvector similarity search for a given patient + query.
  - `qa.py` – RAG-style QA over retrieved chunks using the LLM.
- `app/api/`
  - `schemas.py` – FastAPI request/response models.
  - `routes.py` – API endpoints (intake + structured note + QA).
- `app/main.py` – FastAPI app, startup hook (`init_db`), router mounting.

**Frontend**

- `frontend/src/App.tsx`
  - Left pane: patient intake chat (with stage progress and status chips).
  - Right pane: structured summary card + doctor QA area.
- `frontend/src/main.tsx`
  - React entry point.
- `frontend/src/index.css`
  - Tailwind base/components/utilities + dark theme base styles.
- `tailwind.config.cjs`, `postcss.config.cjs` – Tailwind configuration.

---