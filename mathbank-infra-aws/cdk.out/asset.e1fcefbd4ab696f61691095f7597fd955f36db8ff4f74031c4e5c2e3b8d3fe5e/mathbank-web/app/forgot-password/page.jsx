"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { input, primaryButton } from "../db/dbStyles.js";
import { Callout, PageHeader } from "../_components/ui.jsx";

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [step, setStep] = useState("request"); // request | confirm
  const [username, setUsername] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [destination, setDestination] = useState(null);
  const [status, setStatus] = useState(null);

  async function requestCode(e) {
    e.preventDefault();
    setStatus("submitting");
    try {
      const res = await fetch("/api/auth/forgot-password", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || `status ${res.status}`);
      setDestination(body.destination);
      setStep("confirm");
      setStatus(null);
    } catch (err) {
      setStatus(`error: ${err.message}`);
    }
  }

  async function confirmReset(e) {
    e.preventDefault();
    setStatus("submitting");
    try {
      const res = await fetch("/api/auth/confirm-forgot-password", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, confirmation_code: code, new_password: newPassword }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || `status ${res.status}`);
      router.push("/login");
    } catch (err) {
      setStatus(`error: ${err.message}`);
    }
  }

  return (
    <div className="app-auth">
      <div className="mb-4">
        <PageHeader icon="key" title="Reset your password" centered />
      </div>
      {step === "request" ? (
        <form onSubmit={requestCode} className="card p-4 d-grid gap-3">
          <label className="form-label mb-0">Username (email or phone on file)
          <input className={input} required value={username} onChange={(e) => setUsername(e.target.value)} /></label>
          <button type="submit" className={primaryButton} disabled={status === "submitting"}>
            {status === "submitting" ? "Sending…" : "Send reset code"}
          </button>
          {status?.startsWith("error") && <Callout tone="danger" role="alert">{status}</Callout>}
        </form>
      ) : (
        <form onSubmit={confirmReset} className="card p-4 d-grid gap-3">
          <Callout tone="info">A reset code was sent to {destination || "your account's contact method"}.</Callout>
          <label className="form-label mb-0">Reset code
          <input className={input} required value={code} onChange={(e) => setCode(e.target.value)} /></label>
          <label className="form-label mb-0">New password
          <input className={input} type="password" minLength={8} required value={newPassword} onChange={(e) => setNewPassword(e.target.value)} /></label>
          <button type="submit" className={primaryButton} disabled={status === "submitting"}>
            {status === "submitting" ? "Resetting…" : "Reset password"}
          </button>
          {status?.startsWith("error") && <Callout tone="danger" role="alert">{status}</Callout>}
        </form>
      )}
    </div>
  );
}
