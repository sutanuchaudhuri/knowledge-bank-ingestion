"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { panel, input, primaryButton } from "../../db/dbStyles.js";

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
      <p style={{ marginTop: 0 }}>
        <Link href="/" style={{ fontSize: 13, color: "#2563eb" }}>&larr; Back to chat</Link>
      </p>
      <h1 className="h3 fw-bold mb-4">Admin login</h1>
      <p style={{ color: "#666", fontSize: 13 }}>
        Predefined single admin account — a bridge until real OAuth login is built
        (see requirements/12_STUDENT_PROFILE_AND_ADMIN_LOGIN_UI_REQUIREMENTS.md).
        Default dev credentials: <code>admin</code> / <code>ChangeMe123!</code>
        (set <code>ADMIN_LOGIN_USERNAME</code>/<code>ADMIN_LOGIN_PASSWORD</code> in
        mathbank-web/.env to change).
      </p>
      <form onSubmit={submit} className={`${panel} gap-3`}>
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
        {status?.startsWith("error") && <p className="alert alert-danger mb-0" role="alert">{status}</p>}
      </form>
    </div>
  );
}
