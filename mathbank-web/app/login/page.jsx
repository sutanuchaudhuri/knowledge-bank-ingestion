"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { panel, input, primaryButton, button } from "../db/dbStyles.js";

const DEMO_ACCOUNTS = [
  { email: "maya.chen@example.com", label: "Maya Chen — strong" },
  { email: "daniel.osei@example.com", label: "Daniel Osei — struggling" },
  { email: "priya.patel@example.com", label: "Priya Patel — mixed" },
];
const DEMO_PASSWORD = "Demo1234!";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState("login"); // login | register
  const [form, setForm] = useState({ email: "", password: "", first_name: "", last_name: "" });
  const [status, setStatus] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setStatus("submitting");
    const endpoint = mode === "login" ? "/api/auth/student-login" : "/api/auth/student-register";
    const body = mode === "login"
      ? { email: form.email, password: form.password }
      : { email: form.email, password: form.password, first_name: form.first_name, last_name: form.last_name };
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const resBody = await res.json();
      if (!res.ok) throw new Error(resBody.error || `status ${res.status}`);
      router.push("/profile");
      router.refresh();
    } catch (err) {
      setStatus(`error: ${err.message}`);
    }
  }

  function fillDemo(email) {
    setMode("login");
    setForm({ ...form, email, password: DEMO_PASSWORD });
  }

  return (
    <div className="app-auth">
      <p style={{ marginTop: 0 }}>
        <Link href="/" style={{ fontSize: 13, color: "#2563eb" }}>&larr; Back to chat</Link>
      </p>
      <h1 className="h3 fw-bold mb-4">{mode === "login" ? "Student login" : "Create your student account"}</h1>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button className={mode === "login" ? primaryButton : button} aria-pressed={mode === "login"} onClick={() => setMode("login")}>Log in</button>
        <button className={mode === "register" ? primaryButton : button} aria-pressed={mode === "register"} onClick={() => setMode("register")}>Register</button>
      </div>

      <form onSubmit={submit} className={`${panel} gap-3`}>
        {mode === "register" && (
          <>
            <label className="form-label mb-0">First name
            <input className={input} placeholder="First name" autoComplete="given-name" required
              value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} /></label>
            <label className="form-label mb-0">Last name
            <input className={input} placeholder="Last name" autoComplete="family-name" required
              value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} /></label>
          </>
        )}
        <label className="form-label mb-0">Email
        <input className={input} type="email" placeholder="Email" autoComplete="email" required
          value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
        <label className="form-label mb-0">Password
        <input className={input} type="password" placeholder="Password (min 8 characters)"
          autoComplete={mode === "login" ? "current-password" : "new-password"} required
          value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
        <button type="submit" className={primaryButton} disabled={status === "submitting"}>
          {status === "submitting" ? "Working…" : mode === "login" ? "Log in" : "Create account"}
        </button>
        {status?.startsWith("error") && <p className="alert alert-danger mb-0" role="alert">{status}</p>}
      </form>

      <div className={`${panel} mt-4`}>
        <h3 style={{ marginTop: 0, fontSize: 14 }}>Try a demo account</h3>
        <p style={{ color: "#666", fontSize: 12, marginTop: 0 }}>
          Three seeded profiles with real attempt history (password <code>{DEMO_PASSWORD}</code> for all three) —
          see <code>mathbank-rest/scripts/seed_demo_students.py</code>.
        </p>
        <div style={{ display: "grid", gap: 6 }}>
          {DEMO_ACCOUNTS.map((d) => (
            <button key={d.email} className={button} onClick={() => fillDemo(d.email)}>
              {d.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
