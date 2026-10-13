import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { PageHeader, Field, Button, Callout } from "../components/ui.jsx";
import { api, setSession } from "../api.js";

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const data = await api.login({ username, password });
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
      <PageHeader icon="box-arrow-in-right" title="Log in" />
      <form className="mb-card" onSubmit={onSubmit}>
        <Field label="Username (email, phone, or your login ID)">
          <input className="mb-input" required value={username} onChange={(e) => setUsername(e.target.value)} />
        </Field>
        <Field label="Password">
          <input className="mb-input" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </Field>
        {error && <Callout tone="danger" icon="exclamation-triangle">{error}</Callout>}
        <Button tone="primary" icon="box-arrow-in-right" type="submit" disabled={busy}>
          {busy ? "Logging in…" : "Log in"}
        </Button>
        <p style={{ marginTop: "0.75rem", fontSize: "0.85rem", display: "flex", justifyContent: "space-between" }}>
          <Link className="mb-link" to="/signup">Create an account</Link>
          <Link className="mb-link" to="/forgot-password">Forgot password?</Link>
        </p>
      </form>
    </div>
  );
}
