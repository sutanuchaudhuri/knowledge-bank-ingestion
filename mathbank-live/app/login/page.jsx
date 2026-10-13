"use client";

import { useState } from "react";
import Link from "next/link";

async function post(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Sign-in failed (${res.status})`);
  return data;
}

export default function LoginPage() {
  const [values, setValues] = useState({ email: "", password: "" });
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await post("/api/auth/student-login", values);
      window.location.href = "/";
    } catch (ex) {
      setErr(ex.message);
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="text-center mb-4">
        <h1 className="h3 mb-1">Sign in</h1>
        <p className="text-secondary small mb-0">Join live classroom sessions on MathBank Live.</p>
      </div>
      <form className="card auth-card p-4" onSubmit={submit} data-testid="student-login">
        <div className="mb-3">
          <label className="form-label small" htmlFor="student-login-email">Email</label>
          <input id="student-login-email" type="email" className="form-control" autoComplete="username" required
            value={values.email} onChange={(e) => setValues((v) => ({ ...v, email: e.target.value }))} />
        </div>
        <div className="mb-3">
          <label className="form-label small" htmlFor="student-login-password">Password</label>
          <input id="student-login-password" type="password" className="form-control" autoComplete="current-password" required
            value={values.password} onChange={(e) => setValues((v) => ({ ...v, password: e.target.value }))} />
        </div>
        <button className="btn btn-primary w-100" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        {err && <div className="text-danger small mt-2" role="alert">{err}</div>}
      </form>
      <p className="text-center small mt-3 mb-0">
        <Link href="/admin/login">Login as admin &rarr;</Link>
      </p>
      <p className="text-center text-secondary small mt-2 mb-0">
        Already signed in on MathBank Web? You&rsquo;re signed in here too.
      </p>
    </div>
  );
}
