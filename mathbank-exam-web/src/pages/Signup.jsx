import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { PageHeader, Field, Button, Callout } from "../components/ui.jsx";
import { api, setSession } from "../api.js";

export default function Signup() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    first_name: "", last_name: "", grade: "", email: "", phone: "", password: "", confirm: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [generatedUsername, setGeneratedUsername] = useState(null);

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function onSubmit(e) {
    e.preventDefault();
    setError(null);
    if (form.password !== form.confirm) {
      setError("Passwords don't match.");
      return;
    }
    if (!form.email && !form.phone) {
      setError("Without an email or phone, you won't be able to reset your password later. You can still continue.");
    }
    setBusy(true);
    try {
      const data = await api.signup({
        first_name: form.first_name, last_name: form.last_name,
        grade: form.grade || null, email: form.email || null, phone: form.phone || null,
        password: form.password,
      });
      setSession(data.access_token, data.student_id);
      if (data.generated_username) {
        setGeneratedUsername(data.username);
      } else {
        navigate("/request");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (generatedUsername) {
    return (
      <div className="mb-shell">
        <PageHeader icon="key" title="Remember this login ID" subtitle="You didn't provide an email or phone, so here's your username — write it down." />
        <div className="mb-card">
          <Callout tone="warning" icon="exclamation-triangle">
            Your login ID is <strong>{generatedUsername}</strong>. You'll need it (with your password) to log in again — there's no way to recover it otherwise.
          </Callout>
          <Button tone="primary" icon="arrow-right" onClick={() => navigate("/request")}>
            Continue
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mb-shell">
      <PageHeader icon="person-badge" title="Create your account" subtitle="Grade helps us calibrate difficulty; email/phone are optional but enable password recovery." />
      <form className="mb-card" onSubmit={onSubmit}>
        <Field label="First name">
          <input className="mb-input" required value={form.first_name} onChange={(e) => update("first_name", e.target.value)} />
        </Field>
        <Field label="Last name">
          <input className="mb-input" required value={form.last_name} onChange={(e) => update("last_name", e.target.value)} />
        </Field>
        <Field label="Grade">
          <input className="mb-input" placeholder="e.g. 9, 10, College" value={form.grade} onChange={(e) => update("grade", e.target.value)} />
        </Field>
        <Field label="Email (optional)">
          <input className="mb-input" type="email" value={form.email} onChange={(e) => update("email", e.target.value)} />
        </Field>
        <Field label="Phone (optional)">
          <input className="mb-input" type="tel" value={form.phone} onChange={(e) => update("phone", e.target.value)} />
        </Field>
        <Field label="Password">
          <input className="mb-input" type="password" required minLength={8} value={form.password} onChange={(e) => update("password", e.target.value)} />
        </Field>
        <Field label="Confirm password">
          <input className="mb-input" type="password" required value={form.confirm} onChange={(e) => update("confirm", e.target.value)} />
        </Field>
        {error && <Callout tone="danger" icon="exclamation-triangle">{error}</Callout>}
        <Button tone="primary" icon="check2" type="submit" disabled={busy}>
          {busy ? "Creating…" : "Create account"}
        </Button>
        <p style={{ marginTop: "0.75rem", fontSize: "0.85rem" }}>
          Already have an account? <Link className="mb-link" to="/login">Log in</Link>
        </p>
      </form>
    </div>
  );
}
