"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Callout, EmptyState, PageHeader, Pill } from "../../_components/ui.jsx";

export default function PublishedMicroCoursesPage() {
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/rest/micro-courses", { cache: "no-store", signal: controller.signal })
      .then(async response => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.error || `Course catalog failed (${response.status})`);
        return body;
      })
      .then(setCourses)
      .catch(err => { if (err.name !== "AbortError") setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  return (
    <>
      <PageHeader icon="diagram-3" title="Micro-courses" subtitle="Study short, instructor-reviewed lessons connected to MathBank concepts." />
      {error && <Callout tone="danger" role="alert">{error}</Callout>}
      {loading && <p role="status" className="text-secondary">Loading published courses…</p>}
      {!loading && !error && courses.length === 0 && (
        <EmptyState icon="diagram-3">No published micro-courses are available yet.</EmptyState>
      )}
      {courses.length > 0 && (
        <>
          <Callout tone="insight" title="Reviewed learning paths">
            Every course is published as a fixed, reviewed release mapped to existing concepts and techniques.
          </Callout>
          <div className="row g-3 mt-1">
            {courses.map(course => (
              <div className="col-md-6 col-xxl-4" key={course.canonical_code}>
                <Link href={`/learn/courses/${encodeURIComponent(course.canonical_code)}`}
                  className="card h-100 border-0 shadow-sm p-4 text-decoration-none">
                  <div className="d-flex justify-content-between align-items-start gap-3">
                    <h2 className="h5 text-body mb-0">{course.title}</h2>
                    <Pill tone="success">v{course.version}</Pill>
                  </div>
                  <p className="text-secondary mt-3 mb-3">{course.description || "A focused, instructor-reviewed lesson."}</p>
                  <div className="d-flex flex-wrap gap-2 mb-3">
                    {course.primary_targets.map(target => (
                      <Pill key={`${target.target_type}-${target.slug}`} tone="primary" icon="diagram-3">
                        {target.name}
                      </Pill>
                    ))}
                  </div>
                  <div className="d-flex flex-wrap gap-2 mt-auto">
                    <Pill tone="neutral" icon="clock">{course.estimated_minutes ? `${course.estimated_minutes} min` : "Self-paced"}</Pill>
                    <Pill tone="neutral" icon="list-check">{course.state_count} steps</Pill>
                  </div>
                </Link>
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}
