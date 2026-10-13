"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { input, primaryButton } from "../db/dbStyles.js";
import { Avatar, Callout, Icon, PageHeader } from "../_components/ui.jsx";

const DEMO_ACCOUNTS = [
  { email: "maya.chen@example.com", label: "Maya Chen — strong" },
  { email: "daniel.osei@example.com", label: "Daniel Osei — struggling" },
  { email: "priya.patel@example.com", label: "Priya Patel — mixed" },
];
const DEMO_PASSWORD = "Demo1234!";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState("login"); // login | register
  const [form, setForm] = useState({ email: "", password: "", first_name: "", last_name: "", grade: "", phone: "" });
  const [status, setStatus] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setStatus("submitting");
    const endpoint = mode === "login" ? "/api/auth/student-login" : "/api/auth/student-register";
    const body = mode === "login"
      ? { email: form.email, password: form.password }
      : {
        email: form.email, password: form.password, first_name: form.first_name,
        last_name: form.last_name, grade: form.grade || null, phone: form.phone || null,
      };
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const resBody = await res.json();
      if (!res.ok) throw new Error(resBody.error || `status ${res.status}`);
      const next = new URLSearchParams(window.location.search).get("next");
      router.push(next && next.startsWith("/") && !next.startsWith("//") ? next : "/profile");
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
      <div className="mb-4">
        <PageHeader icon="mortarboard" title={mode === "login" ? "Student login" : "Create your student account"}
          subtitle="Save your conversations and track your progress." centered />
      </div>
      <div className="mb-segment mb-3" role="group" aria-label="Account mode">
        <button type="button" className={mode === "login" ? "active" : ""} aria-pressed={mode === "login"} onClick={() => setMode("login")}>Log in</button>
        <button type="button" className={mode === "register" ? "active" : ""} aria-pressed={mode === "register"} onClick={() => setMode("register")}>Register</button>
      </div>

      <form onSubmit={submit} className="card p-4 d-grid gap-3">
        {mode === "register" && (
          <>
            <label className="form-label mb-0">First name
            <input className={input} placeholder="First name" autoComplete="given-name" required
              value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} /></label>
            <label className="form-label mb-0">Last name
            <input className={input} placeholder="Last name" autoComplete="family-name" required
              value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} /></label>
            <label className="form-label mb-0">Grade (optional)
            <input className={input} placeholder="e.g. 9, 10, College" autoComplete="off"
              value={form.grade} onChange={(e) => setForm({ ...form, grade: e.target.value })} /></label>
            <label className="form-label mb-0">Phone (optional)
            <input className={input} type="tel" placeholder="Phone" autoComplete="tel"
              value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></label>
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
        {status?.startsWith("error") && <Callout tone="danger" role="alert">{status}</Callout>}
        {mode === "login" && (
          <p className="small text-center mb-0">
            <Link href="/forgot-password">Forgot password?</Link>
          </p>
        )}
      </form>

      <div className="mt-4">
        <div className="small text-secondary text-center mb-2">
          <Icon name="people" className="me-1" />Demo accounts · password <code>{DEMO_PASSWORD}</code>
        </div>
        <div className="d-flex flex-wrap justify-content-center gap-2">
          {DEMO_ACCOUNTS.map((d) => (
            <button key={d.email} type="button" className="mb-tab" onClick={() => fillDemo(d.email)} title={d.email}>
              <Avatar name={d.label} size={22} />{d.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
