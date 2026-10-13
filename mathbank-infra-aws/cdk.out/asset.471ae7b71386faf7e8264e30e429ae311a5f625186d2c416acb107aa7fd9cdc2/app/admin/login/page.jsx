"use client";

import { useState } from "react";
import Link from "next/link";

async function post(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Sign-in failed (${res.status})`);
  return data;
}

export default function AdminLoginPage() {
  const [values, setValues] = useState({ username: "", password: "" });
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await post("/api/auth/admin-login", values);
      window.location.href = "/";
    } catch (ex) {
      setErr(ex.message);
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="text-center mb-4">
        <h1 className="h3 mb-1">Instructor sign in</h1>
        <p className="text-secondary small mb-0">Host and manage live classroom sessions.</p>
      </div>
      <form className="card auth-card p-4" onSubmit={submit} data-testid="instructor-login">
        <div className="mb-3">
          <label className="form-label small" htmlFor="instructor-login-username">Username</label>
          <input id="instructor-login-username" type="text" className="form-control" autoComplete="username" required
            value={values.username} onChange={(e) => setValues((v) => ({ ...v, username: e.target.value }))} />
        </div>
        <div className="mb-3">
          <label className="form-label small" htmlFor="instructor-login-password">Password</label>
          <input id="instructor-login-password" type="password" className="form-control" autoComplete="current-password" required
            value={values.password} onChange={(e) => setValues((v) => ({ ...v, password: e.target.value }))} />
        </div>
        <button className="btn btn-primary w-100" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        {err && <div className="text-danger small mt-2" role="alert">{err}</div>}
      </form>
      <p className="text-center small mt-3 mb-0">
        <Link href="/login">&larr; Back to student sign in</Link>
      </p>
    </div>
  );
}
