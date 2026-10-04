"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { panel, table, th, td, button } from "../db/dbStyles.js";

const TIER_COLOUR = { critical: "#b91c1c", developing: "#92400e", solid: "#15803d" };

function tierFor(score) {
  if (score < 0.4) return "critical";
  if (score < 0.7) return "developing";
  return "solid";
}

function TierBadge({ score }) {
  const numScore = Number(score);
  const tier = tierFor(numScore);
  return (
    <span className="badge rounded-pill bg-light border" style={{ color: TIER_COLOUR[tier] }}>
      {tier} ({numScore.toFixed(2)})
    </span>
  );
}

function ProfileHeader({ profile, onLogout }) {
  return (
    <div className={`${panel} flex-row flex-wrap justify-content-between align-items-center gap-3`}>
      <div>
        <h1 className="h3 fw-bold mb-2">{profile.first_name} {profile.last_name}</h1>
        <p style={{ margin: "4px 0 0", color: "#666", fontSize: 13 }}>{profile.email}</p>
        <p style={{ margin: "4px 0 0", color: "#999", fontSize: 11 }}>
          Student ID: <code>{profile.student_id}</code>
          {profile.last_login_at && <> · last login {new Date(profile.last_login_at).toLocaleString()}</>}
        </p>
      </div>
      <button className={button} onClick={onLogout}>Log out</button>
    </div>
  );
}

function AttemptsTable({ attempts }) {
  if (!attempts.length) return <p style={{ color: "#666", fontSize: 13 }}>No attempts recorded yet.</p>;
  return (
    <div className="table-responsive"><table className={table}>
      <thead>
        <tr>
          <th style={th}>Problem</th>
          <th style={th}>Competition</th>
          <th style={th}>Correct?</th>
          <th style={th}>Hints</th>
          <th style={th}>Time</th>
          <th style={th}>When</th>
        </tr>
      </thead>
      <tbody>
        {attempts.map((a) => (
          <tr key={a.attempt_id}>
            <td style={td}><code>{a.canonical_code}</code></td>
            <td style={td}>{a.competition} {a.year}</td>
            <td style={td}>{a.is_correct ? <span style={{ color: "#15803d" }}>yes</span> : <span style={{ color: "#b91c1c" }}>no</span>}</td>
            <td style={td}>{a.hint_count}</td>
            <td style={td}>{a.time_spent_seconds ? `${a.time_spent_seconds}s` : "—"}</td>
            <td style={td}>{new Date(a.attempted_at).toLocaleString()}</td>
          </tr>
        ))}
      </tbody>
    </table></div>
  );
}

function MasteryBreakdown({ mastery }) {
  const rows = [
    ...mastery.concepts.map((c) => ({ ...c, kind: "concept" })),
    ...mastery.techniques.map((t) => ({ ...t, kind: "technique" })),
  ].sort((a, b) => a.mastery_score - b.mastery_score);
  if (!rows.length) return <p style={{ color: "#666", fontSize: 13 }}>No mastery data yet — submit some attempts first.</p>;
  return (
    <div className="table-responsive"><table className={table}>
      <thead>
        <tr>
          <th style={th}>Concept / technique</th>
          <th style={th}>Kind</th>
          <th style={th}>Tier</th>
          <th style={th}>Attempts</th>
          <th style={th}>Correct</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={`${r.kind}-${r.slug}`}>
            <td style={td}>{r.name}</td>
            <td style={td}>{r.kind}</td>
            <td style={td}><TierBadge score={r.mastery_score} /></td>
            <td style={td}>{r.attempts_count}</td>
            <td style={td}>{r.correct_count}</td>
          </tr>
        ))}
      </tbody>
    </table></div>
  );
}

function ImprovementPlan({ plan }) {
  if (!plan.focus_areas.length) {
    return <p style={{ color: "#15803d", fontSize: 13 }}>Nothing below the "solid" tier right now — nice work.</p>;
  }
  return (
    <div className="app-focus-areas">
      {plan.focus_areas.map((area) => (
        <div key={`${area.kind}-${area.slug}`} className={panel}>
          <div className="d-flex flex-wrap justify-content-between gap-2">
            <strong>{area.name}</strong>
            <TierBadge score={area.mastery_score} />
          </div>
          <p style={{ color: "#666", fontSize: 12, margin: "4px 0" }}>
            {area.kind} · {area.attempts_count} attempt{area.attempts_count === 1 ? "" : "s"} so far
          </p>
          {area.recommended_problems.length > 0 && (
            <p style={{ fontSize: 12, margin: 0 }}>
              Try next: {area.recommended_problems.map((p) => (
                <code key={p.canonical_code} style={{ marginRight: 6 }}>{p.canonical_code}</code>
              ))}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

export default function ProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState(null);
  const [attempts, setAttempts] = useState(null);
  const [mastery, setMastery] = useState(null);
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const [profileRes, attemptsRes, masteryRes, planRes] = await Promise.all([
          fetch("/api/rest/learner/me"),
          fetch("/api/rest/learner/attempts?limit=50"),
          fetch("/api/rest/learner/mastery"),
          fetch("/api/rest/learner/mastery/improvement-plan"),
        ]);
        if (profileRes.status === 401) {
          router.push("/login");
          return;
        }
        setProfile(await profileRes.json());
        setAttempts(await attemptsRes.json());
        setMastery(await masteryRes.json());
        setPlan(await planRes.json());
      } catch (err) {
        setError(err.message);
      }
    }
    load();
  }, [router]);

  async function logout() {
    await fetch("/api/auth/student-logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  if (error) return <div className="alert alert-danger" role="alert">Error: {error}</div>;
  if (!profile || !attempts || !mastery || !plan) {
    return <div className="card p-4" role="status">Loading…</div>;
  }

  return (
    <div className="d-grid gap-4">
      <p style={{ margin: 0 }}>
        <Link href="/" style={{ fontSize: 13, color: "#2563eb" }}>&larr; Back to chat</Link>
      </p>
      <ProfileHeader profile={profile} onLogout={logout} />

      <section>
        <h2 className="h5 fw-bold mb-3">What to improve next</h2>
        <ImprovementPlan plan={plan} />
      </section>

      <section className={panel}>
        <h2 className="h5 fw-bold mb-3">Strength &amp; weakness by concept</h2>
        <MasteryBreakdown mastery={mastery} />
      </section>

      <section className={panel}>
        <h2 className="h5 fw-bold mb-3">Past attempts</h2>
        <AttemptsTable attempts={attempts} />
      </section>
    </div>
  );
}
