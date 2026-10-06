"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { input, primaryButton } from "../../db/dbStyles.js";
import { Callout, Icon } from "../../_components/ui.jsx";

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
      <div className="text-center mb-4">
        <span className="mb-page-icon mb-tone-warning mx-auto mb-3"><Icon name="shield-lock" /></span>
        <h1 className="mb-page-title">Admin login</h1>
        <p className="mb-page-sub">Single predefined admin account until OAuth lands.</p>
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
      </form>
      <p className="small text-secondary text-center mt-3" title="Set ADMIN_LOGIN_USERNAME / ADMIN_LOGIN_PASSWORD in mathbank-web/.env to change (requirements/12).">
        <Icon name="info-circle" className="me-1" />Dev default: <code>admin</code> / <code>ChangeMe123!</code>
      </p>
    </div>
  );
}
