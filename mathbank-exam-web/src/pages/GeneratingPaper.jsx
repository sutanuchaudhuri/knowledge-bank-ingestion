import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { PageHeader, Callout } from "../components/ui.jsx";
import { api } from "../api.js";

// requirements/64 (continued): live, step-by-step generation progress — what the agent
// or subagent is doing right now, not one static spinner message. Phase codes match
// quiz.generation_event's own CHECK constraint (mathbank-db/sql/050, 052).
const PHASE_LABELS = {
  INTAKE: "Parsing your request",
  TOPIC_RESOLVE: "Resolving the topic against the corpus",
  DIFFICULTY_SIGNAL: "Checking the corpus difficulty signal",
  POOL_LOOKUP: "Reusing questions from the question pool",
  DRAFT_QUESTION: "Drafting",
  CRITIC_REVIEW: "Critic reviewing",
  AGGREGATE_DIVERSITY_CHECK: "Checking diversity across the whole paper",
  AGGREGATE_FIX: "Revising for diversity",
  PERSIST: "Saving your paper",
  DONE: "Ready",
  FAILED: "Failed",
};

function stepLabel(event) {
  const base = PHASE_LABELS[event.phase] || event.phase;
  const prefix = event.question_ordinal ? `Question ${event.question_ordinal}: ` : "";
  const suffix = event.detail ? ` — ${event.detail}` : "";
  return `${prefix}${base}${event.status === "STARTED" ? "…" : ""}${event.status === "DONE" ? suffix : ""}`;
}

function stepIcon(event) {
  if (event.phase === "FAILED") return "exclamation-triangle-fill text-danger";
  if (event.status === "STARTED") return "arrow-repeat";
  return "check-circle-fill text-success";
}

export default function GeneratingPaper() {
  const { quizId } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const nlRequest = location.state?.nlRequest;
  const [events, setEvents] = useState([]);
  const [error, setError] = useState(null);
  const sinceOrdinal = useRef(0);
  const runStarted = useRef(false);
  const logEndRef = useRef(null);

  useEffect(() => {
    if (!nlRequest) {
      navigate("/request", { replace: true });
      return;
    }
    if (!runStarted.current) {
      runStarted.current = true;
      // Fire-and-forget: the frontend does not wait on this response to navigate —
      // it polls generation-progress + paper status below instead. A real, complete
      // HTTP request either way (not abandoned mid-flight), just not awaited here.
      api.runPaperGeneration(quizId, nlRequest).catch((err) => setError(err.message));
    }

    let cancelled = false;
    let timer;
    const poll = async () => {
      try {
        const [newEvents, paper] = await Promise.all([
          api.generationProgress(quizId, sinceOrdinal.current),
          api.getPaper(quizId).catch(() => null),
        ]);
        if (cancelled) return;
        if (newEvents.length) {
          sinceOrdinal.current = newEvents[newEvents.length - 1].ordinal;
          setEvents((prev) => [...prev, ...newEvents]);
        }
        if (paper && paper.status === "READY") {
          navigate(`/exam/${quizId}`, { replace: true });
          return;
        }
        if (paper && paper.status === "FAILED") {
          setError("Generation failed. Please go back and try again.");
          return;
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
        return;
      }
      if (!cancelled) timer = setTimeout(poll, 1200);
    };
    timer = setTimeout(poll, 400);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quizId]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [events]);

  return (
    <div className="mb-shell">
      <PageHeader
        icon="magic"
        title="Generating your mock exam"
        subtitle="Drafting each question, retrieving real corpus inspiration, critiquing, and checking the whole paper for diversity — this can take a minute or two."
      />
      <div className="mb-card" style={{ maxHeight: "60vh", overflowY: "auto" }}>
        {events.length === 0 && !error && (
          <Callout tone="primary" icon="hourglass-split">Starting up…</Callout>
        )}
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {events.map((e) => (
            <li
              key={e.ordinal}
              style={{ display: "flex", gap: "0.5rem", alignItems: "flex-start", padding: "0.3rem 0" }}
            >
              <i className={`bi bi-${stepIcon(e)}`} aria-hidden="true" style={{ marginTop: "0.15rem" }} />
              <span>{stepLabel(e)}</span>
            </li>
          ))}
        </ul>
        <div ref={logEndRef} />
      </div>
      {error && <Callout tone="danger" icon="exclamation-triangle">{error}</Callout>}
    </div>
  );
}
