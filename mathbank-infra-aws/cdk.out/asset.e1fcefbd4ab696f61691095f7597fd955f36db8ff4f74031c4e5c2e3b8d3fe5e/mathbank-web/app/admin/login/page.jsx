"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { input, primaryButton } from "../../db/dbStyles.js";
import { Callout, Icon, PageHeader } from "../../_components/ui.jsx";

export default function AdminLoginPage() {
  const router = useRouter();
  const [form, setForm] = useState({ username: "", password: "" });
  const [status, setStatus] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setStatus("checking");
    try {
      const res = await fetch("/api/auth/admin-login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || `status ${res.status}`);
      router.push("/admin");
      router.refresh();
    } catch (err) {
      setStatus(`error: ${err.message}`);
    }
  }

  return (
    <div className="app-auth">
      <div className="mb-4">
        <PageHeader icon="shield-lock" title="Admin login" subtitle="Sign in with your Cognito admin account." tone="warning" centered />
      </div>
      <form onSubmit={submit} className="card p-4 d-grid gap-3">
        <label className="form-label mb-0">Username
        <input
          className={input}
          placeholder="Username"
          autoComplete="username"
          required
          value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })}
        /></label>
        <label className="form-label mb-0">Password
        <input
          className={input}
          type="password"
          placeholder="Password"
          autoComplete="current-password"
          required
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        /></label>
        <button type="submit" className={primaryButton} disabled={status === "checking"}>
          {status === "checking" ? "Checking…" : "Log in"}
        </button>
        {status?.startsWith("error") && <Callout tone="danger" role="alert">{status}</Callout>}
        <p className="small text-center mb-0">
          <Link href="/forgot-password">Forgot password?</Link>
        </p>
      </form>
      <p className="small text-secondary text-center mt-3" title="Admin accounts are provisioned via AWS Cognito, in the Admins group — not self-service sign-up.">
        <Icon name="info-circle" className="me-1" />Admin access requires membership in the Cognito <code>Admins</code> group.
      </p>
    </div>
  );
}
