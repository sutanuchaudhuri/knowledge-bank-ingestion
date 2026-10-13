import { useNavigate } from "react-router-dom";
import { PageHeader, Button } from "../components/ui.jsx";
import { api, setSession } from "../api.js";
import { useState } from "react";

export default function Landing() {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function continueAsGuest() {
    setBusy(true);
    setError(null);
    try {
      const data = await api.anonymous();
      setSession(data.access_token, data.student_id);
      navigate("/request");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mb-shell">
      <PageHeader
        icon="journal-check"
        title="MathBank Mock Exam"
        subtitle="Tell us what kind of paper you want, take it like a real exam, and get a full breakdown afterward."
      />
      <div className="mb-card" style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <Button tone="primary" icon="person-badge" onClick={() => navigate("/signup")}>
          Create an account
        </Button>
        <Button tone="ghost" icon="box-arrow-in-right" onClick={() => navigate("/login")}>
          Log in
        </Button>
        <Button tone="ghost" icon="incognito" disabled={busy} onClick={continueAsGuest}>
          {busy ? "Starting…" : "Continue as guest"}
        </Button>
        {error && <p style={{ color: "var(--mb-danger)", fontSize: "0.85rem" }}>{error}</p>}
      </div>
    </div>
  );
}
