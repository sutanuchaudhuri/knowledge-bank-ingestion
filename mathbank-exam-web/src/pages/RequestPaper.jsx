import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageHeader, Field, Button, Callout } from "../components/ui.jsx";
import { api } from "../api.js";

const EXAMPLES = [
  "A 5-question MCQ paper on combinatorics, medium difficulty, 30 minute time limit",
  "A 10-question AIME-style paper on number theory, hard, 60 minutes",
  "3 proof-based questions on geometry, no time limit",
];

export default function RequestPaper() {
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { quiz_id: quizId } = await api.startPaper(text, true);
      navigate(`/generating/${quizId}`, { state: { nlRequest: text } });
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="mb-shell">
      <PageHeader
        icon="magic"
        title="Request a mock exam"
        subtitle="Describe what you want in plain language — topic, how many questions, difficulty, time limit."
      />
      <form className="mb-card" onSubmit={onSubmit}>
        <Field label="What kind of paper do you want?">
          <textarea
            className="mb-textarea"
            rows={4}
            required
            placeholder={EXAMPLES[0]}
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        </Field>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem", marginBottom: "1rem" }}>
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              className="mb-btn mb-btn-ghost"
              style={{ fontSize: "0.78rem", padding: "0.3rem 0.6rem" }}
              onClick={() => setText(ex)}
            >
              {ex}
            </button>
          ))}
        </div>
        {error && <Callout tone="danger" icon="exclamation-triangle">{error}</Callout>}
        <Button tone="primary" icon="magic" type="submit" disabled={busy}>
          {busy ? "Starting…" : "Generate paper"}
        </Button>
      </form>
    </div>
  );
}
