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
    <div style={{ maxWidth: 460, margin: "48px auto", padding: 16, fontFamily: "system-ui, sans-serif" }}>
      <p style={{ marginTop: 0 }}>
        <Link href="/" style={{ fontSize: 13, color: "#2563eb" }}>&larr; Back to chat</Link>
      </p>
      <h1 style={{ fontSize: 20 }}>{mode === "login" ? "Student login" : "Create your student account"}</h1>

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button style={mode === "login" ? primaryButton : button} onClick={() => setMode("login")}>Log in</button>
        <button style={mode === "register" ? primaryButton : button} onClick={() => setMode("register")}>Register</button>
      </div>

      <form onSubmit={submit} style={{ ...panel, display: "grid", gap: 8 }}>
        {mode === "register" && (
          <>
            <input style={input} placeholder="First name" required
              value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} />
            <input style={input} placeholder="Last name" required
              value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} />
          </>
        )}
        <input style={input} type="email" placeholder="Email" autoComplete="email" required
          value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <input style={input} type="password" placeholder="Password (min 8 characters)"
          autoComplete={mode === "login" ? "current-password" : "new-password"} required
          value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <button type="submit" style={primaryButton} disabled={status === "submitting"}>
          {status === "submitting" ? "Working…" : mode === "login" ? "Log in" : "Create account"}
        </button>
        {status?.startsWith("error") && <p style={{ color: "#b91c1c", fontSize: 13 }}>{status}</p>}
      </form>

      <div style={{ ...panel, marginTop: 16 }}>
        <h3 style={{ marginTop: 0, fontSize: 14 }}>Try a demo account</h3>
        <p style={{ color: "#666", fontSize: 12, marginTop: 0 }}>
          Three seeded profiles with real attempt history (password <code>{DEMO_PASSWORD}</code> for all three) —
          see <code>mathbank-rest/scripts/seed_demo_students.py</code>.
        </p>
        <div style={{ display: "grid", gap: 6 }}>
          {DEMO_ACCOUNTS.map((d) => (
            <button key={d.email} style={button} onClick={() => fillDemo(d.email)}>
              {d.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
