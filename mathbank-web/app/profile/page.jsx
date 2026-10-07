"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Avatar, Callout, EmptyState, IconButton, PageHeader, Pager, Pill, SectionTitle, StatCard } from "../_components/ui.jsx";
import { assessedAccuracy, attemptResult } from "../../lib/attemptHistory.mjs";
import PracticeThemes from "./PracticeThemes.jsx";

const TIER = {
  critical: { tone: "danger", icon: "exclamation-octagon" },
  developing: { tone: "warning", icon: "arrow-up-right-circle" },
  solid: { tone: "success", icon: "check-circle" },
};
const PAGE = 10;

function tierFor(score) {
  if (score < 0.4) return "critical";
  if (score < 0.7) return "developing";
  return "solid";
}

function TierPill({ score }) {
  const numScore = Number(score);
  const tier = tierFor(numScore);
  return <Pill tone={TIER[tier].tone} icon={TIER[tier].icon} title={`Mastery ${numScore.toFixed(2)}`}>{tier} · {Math.round(numScore * 100)}%</Pill>;
}

function AttemptsTable({ attempts }) {
  const [offset, setOffset] = useState(0);
  if (!attempts.length) return <EmptyState icon="pencil-square">No attempts recorded yet.</EmptyState>;
  const rows = attempts.slice(offset, offset + PAGE);
  return (
    <>
      <div className="table-responsive"><table className="table table-hover align-middle mb-0">
        <thead><tr><th>Problem</th><th>Competition</th><th>Result</th><th className="text-end">Hints</th><th className="text-end">Time</th><th>When</th></tr></thead>
        <tbody>
          {rows.map((a) => (
            <tr key={a.attempt_id}>
              <td><code>{a.canonical_code}</code></td>
              <td>{a.competition} {a.year}</td>
              <td><Pill tone={attemptResult(a.is_correct).tone} icon={attemptResult(a.is_correct).icon}>{attemptResult(a.is_correct).label}</Pill></td>
              <td className="text-end mb-num">{a.hint_count}</td>
              <td className="text-end mb-num">{a.time_spent_seconds ? `${a.time_spent_seconds}s` : "—"}</td>
              <td className="text-secondary small">{new Date(a.attempted_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table></div>
      {attempts.length > PAGE && (
        <Pager offset={offset} limit={PAGE} count={rows.length} hasMore={offset + PAGE < attempts.length}
          onPrev={() => setOffset(Math.max(0, offset - PAGE))} onNext={() => setOffset(offset + PAGE)} />
      )}
    </>
  );
}

function MasteryBreakdown({ mastery }) {
  const rows = [
    ...mastery.concepts.map((c) => ({ ...c, kind: "concept" })),
    ...mastery.techniques.map((t) => ({ ...t, kind: "technique" })),
  ].sort((a, b) => a.mastery_score - b.mastery_score);
  if (!rows.length) return <EmptyState icon="bar-chart">No mastery data yet. Solve a few problems first.</EmptyState>;
  return (
    <div className="table-responsive"><table className="table table-hover align-middle mb-0">
      <thead><tr><th>Concept / technique</th><th>Kind</th><th>Tier</th><th className="text-end">Attempts</th><th className="text-end">Correct</th></tr></thead>
      <tbody>
        {rows.map((r) => (
          <tr key={`${r.kind}-${r.slug}`}>
            <td className="fw-semibold">{r.name}</td>
            <td><Pill tone="neutral" icon={r.kind === "concept" ? "lightbulb" : "tools"}>{r.kind}</Pill></td>
            <td><TierPill score={r.mastery_score} /></td>
            <td className="text-end mb-num">{r.attempts_count}</td>
            <td className="text-end mb-num">{r.correct_count}</td>
          </tr>
        ))}
      </tbody>
    </table></div>
  );
}

function ImprovementPlan({ plan }) {
  if (!plan.focus_areas.length) {
    return <Callout tone="success" title="All solid">Nothing below the solid tier right now. Nice work.</Callout>;
  }
  return (
    <div className="app-focus-areas">
      {plan.focus_areas.map((area) => (
        <div key={`${area.kind}-${area.slug}`} className="card p-3">
          <div className="d-flex flex-wrap justify-content-between gap-2 mb-1">
            <strong>{area.name}</strong>
            <TierPill score={area.mastery_score} />
          </div>
          <div className="small text-secondary mb-2">{area.kind} · {area.attempts_count} attempt{area.attempts_count === 1 ? "" : "s"}</div>
          {area.recommended_problems.length > 0 && (
            <div className="d-flex flex-wrap gap-1">
              {area.recommended_problems.map((p) => (
                <a key={p.canonical_code} href={`/learn?problem=${encodeURIComponent(p.canonical_code)}`} className="mb-pill mb-pill-primary text-decoration-none">
                  <i className="bi bi-play-fill" aria-hidden="true" />{p.canonical_code}
                </a>
              ))}
            </div>
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
  const [tab, setTab] = useState("practice");
  const [practice, setPractice] = useState(null);
  const [practiceError, setPracticeError] = useState("");
  const [practiceRetry, setPracticeRetry] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setPracticeError("");
    fetch("/api/rest/learner/practice-progress", { signal: controller.signal })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || `Practice progress unavailable (${response.status}).`);
        if (!Array.isArray(data.items)) throw new Error("Practice progress returned invalid data.");
        if (!controller.signal.aborted) setPractice(data);
      }).catch((err) => { if (!controller.signal.aborted) setPracticeError(err.message); });
    return () => controller.abort();
  }, [practiceRetry]);

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
        for (const response of [profileRes, attemptsRes, masteryRes, planRes]) {
          if (!response.ok) throw new Error(`Progress data could not be loaded (${response.status}).`);
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

  if (error) return <Callout tone="danger" role="alert">{error}</Callout>;
  if (!profile || !attempts || !mastery || !plan) {
    return <p className="text-secondary" role="status"><span className="spinner-border spinner-border-sm me-2" />Loading your progress…</p>;
  }

  const name = `${profile.first_name || ""} ${profile.last_name || ""}`.trim() || profile.email;
  const accuracy = assessedAccuracy(attempts);
  const awaiting = attempts.filter((a) => a.is_correct == null).length;
  const avgHints = attempts.length ? (attempts.reduce((n, a) => n + (a.hint_count || 0), 0) / attempts.length).toFixed(1) : "—";
  const skills = [...mastery.concepts, ...mastery.techniques];
  const solid = skills.filter((r) => tierFor(Number(r.mastery_score)) === "solid").length;

  return (
    <>
      <div className="d-flex align-items-center gap-3 mb-1">
        <Avatar name={name} size={56} />
        <div className="flex-grow-1 min-w-0">
          <PageHeader title={name} subtitle={profile.email}
            pills={<>
              <Pill tone="neutral" icon="person-badge" title={`Student ID ${profile.student_id}`}>{String(profile.student_id).slice(0, 8)}</Pill>
              {awaiting > 0 && <Pill tone="warning" icon="hourglass-split">{awaiting} awaiting assessment</Pill>}
              {profile.last_login_at && <Pill tone="neutral" icon="clock-history">{new Date(profile.last_login_at).toLocaleDateString()}</Pill>}
            </>}
            actions={<IconButton icon="box-arrow-right" label="Log out" variant="outline-secondary" onClick={logout} />} />
        </div>
      </div>

      <div className="row g-3 mb-4">
        <div className="col-6 col-xl-3"><StatCard icon="pencil-square" label="Attempts" value={attempts.length} hint="last 50" /></div>
        <div className="col-6 col-xl-3"><StatCard icon="bullseye" tone="success" label="Accuracy" value={accuracy === null ? "—" : `${accuracy}%`} hint="Assessed attempts only" progress={accuracy} /></div>
        <div className="col-6 col-xl-3"><StatCard icon="lightbulb" tone="warning" label="Hints per attempt" value={avgHints} /></div>
        <div className="col-6 col-xl-3"><StatCard icon="award" tone="info" label="Solid skills" value={`${solid}/${skills.length}`} progress={skills.length ? (solid / skills.length) * 100 : null} /></div>
      </div>

      <div className="nav nav-pills gap-2 mb-4" role="tablist" aria-label="Progress views">
        {[["practice", "Practice by theme"], ["mastery", "Strength & weakness"], ["attempts", "Past attempts"]].map(([value, label]) =>
          <button key={value} role="tab" id={`progress-${value}`} aria-selected={tab === value} aria-controls="progress-panel"
            className={`nav-link${tab === value ? " active" : ""}`} onClick={() => setTab(value)}>{label}</button>)}
      </div>
      <div id="progress-panel" role="tabpanel" aria-labelledby={`progress-${tab}`}>
      {tab === "practice" && (practiceError ? <Callout tone="danger" role="alert">{practiceError}
        <button className="btn btn-sm btn-outline-secondary ms-2" onClick={() => setPracticeRetry((value) => value + 1)}>Retry practice progress</button>
      </Callout> : practice ? <PracticeThemes items={practice.items} /> : <p role="status">Loading practice coverage…</p>)}
      {tab === "mastery" && <>
      <section className="mb-4">
        <SectionTitle icon="signpost-2">What to improve next</SectionTitle>
        <ImprovementPlan plan={plan} />
      </section>

        <section>
          <div className="card p-3 h-100">
            <SectionTitle icon="bar-chart-line">Strength &amp; weakness</SectionTitle>
            <MasteryBreakdown mastery={mastery} />
          </div>
        </section>
        </>}
        {tab === "attempts" && <section>
          <div className="card p-3 h-100">
            <SectionTitle icon="clock-history">Past attempts</SectionTitle>
            <AttemptsTable attempts={attempts} />
          </div>
        </section>}
      </div>
    </>
  );
}
