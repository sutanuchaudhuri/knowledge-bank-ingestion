import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { PageHeader, Field, Button, Callout } from "../components/ui.jsx";
import { api } from "../api.js";

export default function ForgotPassword() {
  const navigate = useNavigate();
  const [step, setStep] = useState("request"); // request -> confirm
  const [username, setUsername] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [destination, setDestination] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function requestCode(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const data = await api.forgotPassword({ username });
      setDestination(data.destination);
      setStep("confirm");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function confirmReset(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.confirmForgotPassword({ username, confirmation_code: code, new_password: newPassword });
      navigate("/login");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mb-shell">
      <PageHeader icon="key" title="Reset your password" />
      {step === "request" ? (
        <form className="mb-card" onSubmit={requestCode}>
          <Field label="Username (email or phone on file)">
            <input className="mb-input" required value={username} onChange={(e) => setUsername(e.target.value)} />
          </Field>
          {error && <Callout tone="danger" icon="exclamation-triangle">{error}</Callout>}
          <Button tone="primary" icon="send" type="submit" disabled={busy}>
            {busy ? "Sending…" : "Send reset code"}
          </Button>
          <p style={{ marginTop: "0.75rem", fontSize: "0.85rem" }}>
            <Link className="mb-link" to="/login">Back to login</Link>
          </p>
        </form>
      ) : (
        <form className="mb-card" onSubmit={confirmReset}>
          <Callout tone="info" icon="envelope">
            A reset code was sent to {destination || "your account's contact method"}.
          </Callout>
          <Field label="Reset code">
            <input className="mb-input" required value={code} onChange={(e) => setCode(e.target.value)} />
          </Field>
          <Field label="New password">
            <input className="mb-input" type="password" required minLength={8} value={newPassword} onChange={(e) => setNewPassword(e.target.value)} />
          </Field>
          {error && <Callout tone="danger" icon="exclamation-triangle">{error}</Callout>}
          <Button tone="primary" icon="check2" type="submit" disabled={busy}>
            {busy ? "Resetting…" : "Reset password"}
          </Button>
        </form>
      )}
    </div>
  );
}
