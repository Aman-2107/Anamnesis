import React, { useEffect, useRef, useState } from "react";

const API_BASE = "http://localhost:8000/api";

type ChatMessage = { from: "assistant" | "patient"; text: string };

type StartIntakeResponse = {
  patient_id: string;
  encounter_id: string;
  first_question: string;
  stage: string;
};

type IntakeMessageResponse = {
  next_question: string | null;
  is_complete: boolean;
  stage: string;
};

type Symptom = {
  name: string;
  onset?: string | null;
  duration?: string | null;
  location?: string | null;
  character?: string | null;
  severity?: string | null;
  associated_symptoms?: string[];
  red_flags?: string[];
};

type Medication = {
  name: string;
  dose?: string | null;
  frequency?: string | null;
  route?: string | null;
  indication?: string | null;
};

type Allergy = {
  substance: string;
  reaction?: string | null;
  severity?: string | null;
};

type StructuredIntake = {
  chief_complaint?: string | null;
  symptoms: Symptom[];
  medications: Medication[];
  allergies: Allergy[];
  past_medical_history: string[];
  family_history: string[];
  social_history: string[];
  red_flags: string[];
  patient_goals?: string | null;
  other_notes?: string | null;
};

type QAChunk = {
  id: number;
  encounter_id: string | null;
  source_type: string;
  text: string;
  score: number;
};

type QAResponse = {
  answer: string;
  chunks: QAChunk[];
};

const INTAKE_STAGES = [
  { id: "chief_complaint", label: "Chief complaint" },
  { id: "symptom_details", label: "Symptoms" },
  { id: "safety_checks", label: "Safety" },
  { id: "history", label: "History" },
  { id: "wrap_up", label: "Wrap-up" },
];

const stageIndex = (stage: string | null): number => {
  if (!stage) return 0;
  const idx = INTAKE_STAGES.findIndex((s) => s.id === stage);
  return idx === -1 ? INTAKE_STAGES.length - 1 : idx;
};

const App: React.FC = () => {
  const [patientName, setPatientName] = useState("");
  const [patientId, setPatientId] = useState<string | null>(null);
  const [encounterId, setEncounterId] = useState<string | null>(null);

  const [conversation, setConversation] = useState<ChatMessage[]>([]);
  const [patientInput, setPatientInput] = useState("");
  const [loadingIntake, setLoadingIntake] = useState(false);
  const [intakeComplete, setIntakeComplete] = useState(false);
  const [intakeStage, setIntakeStage] = useState<string | null>(null);

  const [structuredIntake, setStructuredIntake] =
    useState<StructuredIntake | null>(null);
  const [structuredLoading, setStructuredLoading] = useState(false);

  const [qaQuestion, setQaQuestion] = useState("");
  const [qaAnswer, setQaAnswer] = useState<string | null>(null);
  const [qaChunks, setQaChunks] = useState<QAChunk[]>([]);
  const [qaLoading, setQaLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll chat to bottom when conversation changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation]);

  // Helpers
  const resetAll = () => {
    setPatientId(null);
    setEncounterId(null);
    setConversation([]);
    setPatientInput("");
    setLoadingIntake(false);
    setIntakeComplete(false);
    setIntakeStage(null);
    setStructuredIntake(null);
    setStructuredLoading(false);
    setQaQuestion("");
    setQaAnswer(null);
    setQaChunks([]);
    setQaLoading(false);
  };

  const fetchStructuredIntake = async (encId: string) => {
    setStructuredLoading(true);
    try {
      const res = await fetch(`${API_BASE}/encounters/${encId}/structured`);
      if (!res.ok) {
        console.warn("No structured intake available yet.");
        return;
      }
      const data: StructuredIntake = await res.json();
      setStructuredIntake(data);
    } catch (err) {
      console.error(err);
    } finally {
      setStructuredLoading(false);
    }
  };

  // --- PATIENT INTAKE FLOW ---

  const startIntake = async () => {
    resetAll();
    setLoadingIntake(true);

    const displayName =
      patientName.trim() ||
      `Demo patient #${Math.floor(Math.random() * 9000) + 1000}`;

    try {
      const res = await fetch(`${API_BASE}/intake/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_display_name: displayName,
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        console.error("Start intake failed:", res.status, text);
        alert(
          `Error starting intake session (${res.status}). Check backend logs.`
        );
        return;
      }

      const data: StartIntakeResponse = await res.json();
      setPatientName(displayName); // reflect auto-name in header
      setPatientId(data.patient_id);
      setEncounterId(data.encounter_id);
      setIntakeStage(data.stage);
      setConversation([{ from: "assistant", text: data.first_question }]);
    } catch (err) {
      console.error("Network/JS error starting intake:", err);
      alert("Error starting intake session (network error).");
    } finally {
      setLoadingIntake(false);
    }
  };

  const sendPatientMessage = async () => {
    if (!patientInput.trim() || !encounterId) return;
    const message = patientInput.trim();
    setPatientInput("");
    setConversation((prev) => [...prev, { from: "patient", text: message }]);
    setLoadingIntake(true);
    try {
      const res = await fetch(`${API_BASE}/intake/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          encounter_id: encounterId,
          message,
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        console.error("Intake message failed:", res.status, text);
        alert(`Error during intake (${res.status}). Check backend logs.`);
        return;
      }

      const data: IntakeMessageResponse = await res.json();
      setIntakeStage(data.stage);

      if (data.next_question) {
        setConversation((prev) => [
          ...prev,
          { from: "assistant", text: data.next_question! },
        ]);
      }
      if (data.is_complete) {
        setIntakeComplete(true);
        // small delay so structured builder/indexing can finish
        setTimeout(() => {
          if (encounterId) fetchStructuredIntake(encounterId);
        }, 500);
      }
    } catch (err) {
      console.error("Error during intake:", err);
      alert("Error during intake (network error).");
    } finally {
      setLoadingIntake(false);
    }
  };

  // --- DOCTOR QA FLOW ---

  const askDoctorQuestion = async () => {
    if (!qaQuestion.trim() || !patientId) return;
    setQaLoading(true);
    setQaAnswer(null);
    setQaChunks([]);
    try {
      const res = await fetch(`${API_BASE}/patient/qa`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_id: patientId,
          question: qaQuestion.trim(),
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        console.error("QA failed:", res.status, text);
        alert(`Error asking question (${res.status}). Check backend logs.`);
        return;
      }

      const data: QAResponse = await res.json();
      setQaAnswer(data.answer);
      setQaChunks(data.chunks);
    } catch (err) {
      console.error("Error asking question:", err);
      alert("Error asking question (network error).");
    } finally {
      setQaLoading(false);
    }
  };

  const currentStageIndex = stageIndex(intakeStage);
  const intakeProgress =
    intakeStage === "wrap_up" || intakeStage === "done"
      ? 100
      : ((currentStageIndex + 1) / INTAKE_STAGES.length) * 100;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 flex flex-col">
      {/* Top bar */}
      <header className="border-b border-slate-800 bg-slate-950/90 backdrop-blur px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-300 text-xs font-semibold">
            AI
          </div>
          <div>
            <h1 className="text-lg font-semibold">Anamnesis</h1>
            <p className="text-[11px] text-slate-400">
              AI patient intake & clinical memory (demo only, not for clinical use).
            </p>
          </div>
        </div>

        {patientId && encounterId && (
          <div className="flex items-center gap-3 text-[11px] text-slate-400">
            <span className="px-2 py-1 rounded-full bg-slate-900/80 border border-slate-700 text-emerald-300">
              Active patient:{" "}
              <span className="font-medium">
                {patientName || "Anonymous"}
              </span>
            </span>
            <span className="hidden sm:inline">
              Encounter:{" "}
              <span className="font-mono">{encounterId.slice(0, 8)}...</span>
            </span>
          </div>
        )}
      </header>

      {/* Main layout */}
      <main className="flex-1 flex flex-col items-center px-4 py-6">
        <div className="w-full max-w-6xl grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left: Patient intake */}
          <section className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h2 className="text-base font-semibold mb-1">Step 1: Patient Intake</h2>
                <p className="text-xs text-slate-400">
                  The assistant interviews the patient and prepares a structured note.
                </p>
              </div>
              <div className="flex items-center gap-2">
                {intakeComplete ? (
                  <span className="px-2 py-1 rounded-full bg-emerald-500/10 text-emerald-300 text-[11px] border border-emerald-500/40">
                    Intake complete
                  </span>
                ) : encounterId ? (
                  <span className="px-2 py-1 rounded-full bg-sky-500/10 text-sky-300 text-[11px] border border-sky-500/40">
                    In progress
                  </span>
                ) : (
                  <span className="px-2 py-1 rounded-full bg-slate-800 text-slate-300 text-[11px] border border-slate-700">
                    Not started
                  </span>
                )}

                {encounterId && (
                  <button
                    onClick={resetAll}
                    className="px-3 py-1 rounded-lg border border-slate-700 text-slate-300 text-[11px] hover:bg-slate-800"
                  >
                    New patient
                  </button>
                )}
              </div>
            </div>

            {/* Stage progress */}
            <div className="mb-3">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[11px] text-slate-400">Intake stages</span>
                <span className="text-[11px] text-slate-400">
                  {intakeStage
                    ? INTAKE_STAGES[stageIndex(intakeStage)]?.label || "Done"
                    : "Not started"}
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-emerald-500 transition-all"
                  style={{ width: `${intakeProgress}%` }}
                />
              </div>
              <div className="flex justify-between mt-1">
                {INTAKE_STAGES.map((s, idx) => {
                  const done = currentStageIndex > idx || intakeStage === "done";
                  const active = currentStageIndex === idx && !intakeComplete;
                  return (
                    <div
                      key={s.id}
                      className={`h-1 w-1 rounded-full ${
                        done
                          ? "bg-emerald-400"
                          : active
                          ? "bg-sky-400"
                          : "bg-slate-600"
                      }`}
                    />
                  );
                })}
              </div>
            </div>

            {/* Patient name + start */}
            <div className="flex gap-2 mb-3">
              <input
                type="text"
                placeholder="Patient name (optional)"
                value={patientName}
                onChange={(e) => setPatientName(e.target.value)}
                className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs outline-none focus:border-emerald-500/60"
              />
              <button
                onClick={startIntake}
                disabled={loadingIntake}
                className="px-4 py-2 rounded-lg bg-emerald-500 text-slate-950 text-xs font-medium disabled:opacity-50"
              >
                {loadingIntake ? "Starting..." : "Start intake"}
              </button>
            </div>

            {/* Conversation */}
            <div className="flex-1 min-h-[220px] max-h-[300px] overflow-y-auto rounded-xl bg-slate-950/60 border border-slate-800 px-3 py-3 mb-3 space-y-2 text-sm">
              {conversation.length === 0 && (
                <div className="text-slate-500 text-center mt-6 text-xs">
                  Start an intake to begin the conversation.
                </div>
              )}
              {conversation.map((m, idx) => (
                <div
                  key={idx}
                  className={`flex ${
                    m.from === "patient" ? "justify-end" : "justify-start"
                  }`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-3 py-2 text-xs ${
                      m.from === "assistant"
                        ? "bg-slate-800 text-slate-50 rounded-bl-sm"
                        : "bg-emerald-500 text-slate-950 rounded-br-sm"
                    }`}
                  >
                    <div className="text-[10px] opacity-70 mb-0.5">
                      {m.from === "assistant" ? "Anamnesis" : "Patient"}
                    </div>
                    <div>{m.text}</div>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <div className="flex gap-2">
              <input
                type="text"
                placeholder={
                  encounterId
                    ? "Type the patient's reply..."
                    : "Start an intake to begin"
                }
                value={patientInput}
                onChange={(e) => setPatientInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") sendPatientMessage();
                }}
                disabled={!encounterId || loadingIntake}
                className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs outline-none disabled:opacity-50"
              />
              <button
                onClick={sendPatientMessage}
                disabled={!encounterId || loadingIntake || !patientInput.trim()}
                className="px-4 py-2 rounded-lg bg-sky-500 text-slate-950 text-xs font-medium disabled:opacity-50"
              >
                Send
              </button>
            </div>

            {intakeComplete && (
              <p className="mt-3 text-[11px] text-emerald-300">
                Intake finished. A structured note has been generated and indexed for
                the doctor.
              </p>
            )}
          </section>

          {/* Right: Doctor view */}
          <section className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h2 className="text-base font-semibold mb-1">Step 2: Doctor View</h2>
                <p className="text-xs text-slate-400">
                  Review the structured summary and ask free-text questions about this
                  patient.
                </p>
              </div>
            </div>

            {/* Structured summary */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[11px] text-slate-400">Structured summary</span>
                {structuredLoading && (
                  <span className="text-[11px] text-slate-500">Building…</span>
                )}
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-3 text-xs max-h-44 overflow-y-auto">
                {!intakeComplete && (
                  <div className="text-slate-500 text-[11px]">
                    Complete an intake on the left to generate a structured note for
                    the doctor.
                  </div>
                )}

                {intakeComplete && !structuredIntake && !structuredLoading && (
                  <div className="text-slate-500 text-[11px]">
                    Structured note not available yet. Try asking a question or
                    refresh.
                  </div>
                )}

                {structuredIntake && (
                  <div className="space-y-2">
                    {structuredIntake.chief_complaint && (
                      <div>
                        <div className="font-semibold text-slate-200 text-[11px]">
                          Chief complaint
                        </div>
                        <div className="text-slate-100">
                          {structuredIntake.chief_complaint}
                        </div>
                      </div>
                    )}

                    {structuredIntake.symptoms?.length > 0 && (
                      <div>
                        <div className="font-semibold text-slate-200 text-[11px]">
                          Symptoms
                        </div>
                        <ul className="list-disc list-inside">
                          {structuredIntake.symptoms.map((s, idx) => (
                            <li key={idx}>
                              <span className="font-medium">{s.name}</span>
                              {s.onset && ` · onset: ${s.onset}`}
                              {s.location && ` · location: ${s.location}`}
                              {s.severity && ` · severity: ${s.severity}`}
                              {s.associated_symptoms &&
                                s.associated_symptoms.length > 0 &&
                                ` · assoc: ${s.associated_symptoms.join(", ")}`}
                              {s.red_flags && s.red_flags.length > 0 && (
                                <span className="text-red-300">
                                  {" "}
                                  · red flags: {s.red_flags.join(", ")}
                                </span>
                              )}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {structuredIntake.medications?.length > 0 && (
                      <div>
                        <div className="font-semibold text-slate-200 text-[11px]">
                          Medications
                        </div>
                        <ul className="list-disc list-inside">
                          {structuredIntake.medications.map((m, idx) => (
                            <li key={idx}>
                              <span className="font-medium">{m.name}</span>
                              {m.dose && ` · ${m.dose}`}
                              {m.frequency && ` · ${m.frequency}`}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {structuredIntake.allergies?.length > 0 && (
                      <div>
                        <div className="font-semibold text-slate-200 text-[11px]">
                          Allergies
                        </div>
                        <ul className="list-disc list-inside">
                          {structuredIntake.allergies.map((a, idx) => (
                            <li key={idx}>
                              <span className="font-medium">{a.substance}</span>
                              {a.reaction && ` · reaction: ${a.reaction}`}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {structuredIntake.red_flags?.length > 0 && (
                      <div>
                        <div className="font-semibold text-slate-200 text-[11px]">
                          Red flags
                        </div>
                        <div className="text-red-300">
                          {structuredIntake.red_flags.join(", ")}
                        </div>
                      </div>
                    )}

                    {structuredIntake.past_medical_history?.length > 0 && (
                      <div>
                        <div className="font-semibold text-slate-200 text-[11px]">
                          Past medical history
                        </div>
                        <div>
                          {structuredIntake.past_medical_history.join("; ")}
                        </div>
                      </div>
                    )}

                    {structuredIntake.social_history?.length > 0 && (
                      <div>
                        <div className="font-semibold text-slate-200 text-[11px]">
                          Social history
                        </div>
                        <div>{structuredIntake.social_history.join("; ")}</div>
                      </div>
                    )}

                    {structuredIntake.patient_goals && (
                      <div>
                        <div className="font-semibold text-slate-200 text-[11px]">
                          Patient goals
                        </div>
                        <div>{structuredIntake.patient_goals}</div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Doctor QA */}
            <div className="mb-2">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[11px] text-slate-400">
                  Ask questions about this patient
                </span>
                {!patientId && (
                  <span className="text-[11px] text-slate-500">
                    Run an intake first
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-500 mb-1">
                Examples: “What is this patient's chief complaint?”, “Does the
                patient have any allergies?”, “What medications is this patient
                taking?”
              </p>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  placeholder={
                    patientId
                      ? "Ask a doctor-style question about this patient..."
                      : "Run an intake first"
                  }
                  value={qaQuestion}
                  onChange={(e) => setQaQuestion(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") askDoctorQuestion();
                  }}
                  disabled={!patientId || qaLoading}
                  className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs outline-none disabled:opacity-50"
                />
                <button
                  onClick={askDoctorQuestion}
                  disabled={!patientId || qaLoading || !qaQuestion.trim()}
                  className="px-4 py-2 rounded-lg bg-indigo-500 text-slate-50 text-xs font-medium disabled:opacity-50"
                >
                  {qaLoading ? "Asking..." : "Ask"}
                </button>
              </div>
            </div>

            <div className="flex-1 min-h-[140px] max-h-[220px] overflow-y-auto rounded-xl bg-slate-950/80 border border-slate-800 px-3 py-3 text-xs">
              {!qaAnswer && (
                <div className="text-slate-500 text-center mt-4 text-[11px]">
                  No answer yet. Complete an intake and ask a doctor-style question
                  here.
                </div>
              )}
              {qaAnswer && (
                <>
                  <div className="mb-3">
                    <div className="text-[11px] font-semibold text-slate-400 mb-1">
                      Answer
                    </div>
                    <div className="text-slate-100">{qaAnswer}</div>
                  </div>
                  {qaChunks.length > 0 && (
                    <div>
                      <div className="text-[11px] font-semibold text-slate-400 mb-1">
                        Supporting snippets
                      </div>
                      <div className="space-y-1 max-h-24 overflow-y-auto">
                        {qaChunks.map((c, idx) => (
                          <div
                            key={c.id}
                            className="text-[11px] text-slate-400 border border-slate-800 rounded px-2 py-1"
                          >
                            <div className="mb-0.5">
                              [chunk {idx + 1}] ({c.source_type}, score{" "}
                              {c.score.toFixed(3)})
                            </div>
                            <div>
                              {c.text.length > 220
                                ? c.text.slice(0, 220) + "..."
                                : c.text}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>

            <p className="mt-3 text-[11px] text-slate-500">
              Demo only – does not provide diagnoses or treatment recommendations.
            </p>
          </section>
        </div>
      </main>
    </div>
  );
};

export default App;
