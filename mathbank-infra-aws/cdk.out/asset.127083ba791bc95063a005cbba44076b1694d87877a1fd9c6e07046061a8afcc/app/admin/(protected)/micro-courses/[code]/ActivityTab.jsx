"use client";

import { useEffect, useState } from "react";
import { Bar, Callout, EmptyState, Pill, SectionTitle, StatCard } from "../../../../_components/ui.jsx";
import { endpoint, request } from "./shared.js";

/** Live aggregate dashboard for one course (requirements/43 §3.2.7, AMC-7); backed by
 * GET /{code}/activity, which queries enrollment/quiz-attempt tables directly against the
 * currently PUBLISHED release rather than a rollup table (requirements/44 §4.3 explicitly
 * allows this for low-volume courses). Courses with no published release yet have no
 * activity to show. */
export default function ActivityTab({ course }) {
  const [activity, setActivity] = useState(null);
  const [notPublished, setNotPublished] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    request(`${endpoint}/${encodeURIComponent(course.canonical_code)}/activity`, { signal: controller.signal })
      .then(setActivity)
      .catch(err => {
        if (err.name === "AbortError") return;
        if (err.status === 404) setNotPublished(true);
        else setError(err.message);
      });
    return () => controller.abort();
  }, [course.canonical_code]);

  if (error) return <Callout tone="danger" role="alert">{error}</Callout>;
  if (notPublished) return <EmptyState icon="activity">Publish a release to start collecting activity data.</EmptyState>;
  if (!activity) return <p role="status" className="text-secondary">Loading activity…</p>;

  const maxStepCount = Math.max(1, ...activity.step_funnel.map(step => step.reached_count));

  return (
    <div>
      <div className="row g-3 mb-4">
        <div className="col-6 col-lg-3"><StatCard icon="people" value={activity.total_enrollments} label="Enrollments" /></div>
        <div className="col-6 col-lg-3"><StatCard icon="play-circle" value={activity.in_progress} label="In progress" /></div>
        <div className="col-6 col-lg-3">
          <StatCard icon="check-circle" value={activity.completion_rate == null ? "—" : `${Math.round(activity.completion_rate * 100)}%`} label="Completion rate" />
        </div>
        <div className="col-6 col-lg-3"><StatCard icon="patch-question" value={activity.quiz_accuracy.length} label="Quiz questions tracked" /></div>
      </div>

      <div className="card border-0 shadow-sm p-3 mb-4">
        <SectionTitle icon="bar-chart-steps">Step funnel — v{activity.version}</SectionTitle>
        {!activity.step_funnel.length ? <EmptyState icon="bar-chart-steps">No step activity yet.</EmptyState> : (
          <div className="d-flex flex-column gap-2">
            {activity.step_funnel.map(step => (
              <Bar key={step.state_key} label={`${step.title} (${step.state_key})`} value={step.reached_count} max={maxStepCount} />
            ))}
          </div>
        )}
      </div>

      <div className="card border-0 shadow-sm p-3 mb-4">
        <SectionTitle icon="patch-question">Quiz accuracy</SectionTitle>
        {!activity.quiz_accuracy.length ? <EmptyState icon="patch-question">No quiz submissions yet.</EmptyState> : (
          <ul className="list-group list-group-flush">
            {activity.quiz_accuracy.map(quiz => {
              const accuracy = quiz.attempts ? quiz.correct / quiz.attempts : null;
              return (
                <li key={quiz.activity_id} className="list-group-item d-flex justify-content-between align-items-center gap-3">
                  <span>{quiz.prompt} <span className="text-secondary small">({quiz.state_key})</span></span>
                  <Pill tone={accuracy == null ? "neutral" : accuracy >= 0.7 ? "success" : accuracy >= 0.4 ? "warning" : "danger"}>
                    {accuracy == null ? "No attempts" : `${Math.round(accuracy * 100)}% (${quiz.attempts})`}
                  </Pill>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="card border-0 shadow-sm p-3">
        <SectionTitle icon="activity">Recent activity</SectionTitle>
        {!activity.recent_activity.length ? <EmptyState icon="activity">No recent activity.</EmptyState> : (
          <ul className="list-group list-group-flush">
            {activity.recent_activity.map(event => (
              <li key={event.event_id} className="list-group-item d-flex justify-content-between align-items-center gap-3 small">
                <span>{event.student_initials} · {event.event_type} · {event.state_title || "—"}</span>
                <span className="text-secondary">{event.created_at?.replace("T", " ").slice(0, 19)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
