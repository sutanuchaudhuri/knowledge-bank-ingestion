"use client";

import { useState } from "react";

async function post(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Sign-in failed (${res.status})`);
  return data;
}

function LoginForm({ title, endpoint, fields, testId }) {
  const [values, setValues] = useState({});
  const [err, setErr] = useState(null);
  async function submit(e) {
    e.preventDefault();
    setErr(null);
    try { await post(endpoint, values); window.location.href = "/"; } catch (ex) { setErr(ex.message); }
  }
  return (
    <form className="card shadow-sm h-100" onSubmit={submit} data-testid={testId}>
      <div className="card-body">
        <h2 className="h5">{title}</h2>
        {fields.map(([name, label, type]) => (
          <div key={name} className="mb-2">
            <label className="form-label small" htmlFor={`${testId}-${name}`}>{label}</label>
            <input id={`${testId}-${name}`} type={type} className="form-control" autoComplete={type === "password" ? "current-password" : "username"}
              onChange={(e) => setValues((v) => ({ ...v, [name]: e.target.value }))} />
          </div>
        ))}
        <button className="btn btn-primary mt-2">Sign in</button>
        {err && <div className="text-danger small mt-2">{err}</div>}
      </div>
    </form>
  );
}

export default function LoginPage() {
  return (
    <div className="mx-auto" style={{ maxWidth: 900 }}>
      <h1 className="h3 mb-3">Sign in</h1>
      <div className="row g-4">
        <div className="col-12 col-md-6">
          <LoginForm title="Student" endpoint="/api/auth/student-login" testId="student-login"
            fields={[["email", "Email", "email"], ["password", "Password", "password"]]} />
        </div>
        <div className="col-12 col-md-6">
          <LoginForm title="Instructor" endpoint="/api/auth/admin-login" testId="instructor-login"
            fields={[["username", "Username", "text"], ["password", "Password", "password"]]} />
        </div>
      </div>
      <p className="small text-secondary mt-3">Signed in on MathBank Web (same host)? You are already signed in here.</p>
    </div>
  );
}
