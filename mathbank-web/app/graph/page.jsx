"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { RELATIONSHIPS } from "../../lib/graphConfig.js";
import { colorFor } from "./_components/graphColors.js";
import styles from "./graph.module.css";

const VIEWS_BY_TYPE = Object.entries(RELATIONSHIPS).reduce((views, [slug, config]) => {
  (views[config.type] ||= []).push({ slug, title: config.title });
  return views;
}, {});

const sum = (rows) => rows.reduce((total, row) => total + row.count, 0);

export default function GraphOverviewPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback((signal) => {
    setData(null);
    setError(null);
    fetch("/api/graph/overview", { signal })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`status ${res.status}`))))
      .then(setData)
      .catch((err) => { if (err.name !== "AbortError") setError(err.message); });
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  if (error) {
    return (
      <div className="alert alert-danger d-flex align-items-center justify-content-between gap-2" role="alert">
        <span>Could not load graph overview: {error}</span>
        <button type="button" className="btn btn-sm btn-outline-danger" onClick={() => load()}>Retry</button>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="d-flex align-items-center gap-2 text-body-secondary" role="status">
        <span className="spinner-border spinner-border-sm" aria-hidden="true" />
        Loading overview…
      </div>
    );
  }

  const { nodeCounts = [], relationshipCounts = [] } = data;

  return (
    <>
      <div className="alert alert-light border d-flex flex-wrap align-items-center justify-content-between gap-3">
        <div>
          <strong>Teaching graph readiness</strong>
          <p className="small mb-0">
            {data.teaching ? `${data.teaching.reviewedSkills} reviewed skills of ${data.teaching.skills} collected.` : "Teaching metadata totals are unavailable."}
            {data.teaching?.reviewedSkills === 0 && " No reviewed skill metadata has been projected yet."}
            {" "}Corpus tags alone are not a prerequisite curriculum.
          </p>
        </div>
        <Link href="/learn" className="btn btn-sm btn-outline-primary">Start guided practice</Link>
      </div>
      <div className={styles.metrics}>
        <div className={styles.metric}>
          <div className={styles.metricLabel}>Total nodes</div>
          <div className={styles.metricValue}>{sum(nodeCounts).toLocaleString()}</div>
        </div>
        <div className={styles.metric}>
          <div className={styles.metricLabel}>Total relationships</div>
          <div className={styles.metricValue}>{sum(relationshipCounts).toLocaleString()}</div>
        </div>
        <div className={styles.metric}>
          <div className={styles.metricLabel}>Node labels</div>
          <div className={styles.metricValue}>{nodeCounts.length}</div>
        </div>
        <div className={styles.metric}>
          <div className={styles.metricLabel}>Relationship types</div>
          <div className={styles.metricValue}>{relationshipCounts.length}</div>
        </div>
      </div>
      <div className={styles.overviewGrid}>
        <section className={`card ${styles.tableCard}`}>
          <div className="card-header fw-semibold" style={{ padding: "0.5rem 0.75rem" }}>Nodes</div>
          {nodeCounts.length === 0 ? (
            <p className="text-body-secondary m-3">No nodes found.</p>
          ) : (
            <table className={`table table-sm table-hover mb-0 ${styles.simpleTable}`}>
              <tbody>
                {nodeCounts.map((row) => (
                  <tr key={row.label}>
                    <td>
                      <span className={styles.swatch} style={{ background: colorFor(row.label), marginRight: 8 }} />
                      {row.label}
                    </td>
                    <td className="text-end" style={{ textAlign: "right" }}>{row.count.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
        <section className={`card ${styles.tableCard}`}>
          <div className="card-header fw-semibold" style={{ padding: "0.5rem 0.75rem" }}>Relationships</div>
          {relationshipCounts.length === 0 ? (
            <p className="text-body-secondary m-3">No relationships found.</p>
          ) : (
            <table className={`table table-sm table-hover mb-0 ${styles.simpleTable}`}>
              <tbody>
                {relationshipCounts.map((row) => {
                  const views = VIEWS_BY_TYPE[row.type] || [];
                  return (
                    <tr key={row.type}>
                      <td>
                        {views.length === 1 ? <Link href={`/graph/${views[0].slug}`}>{row.type}</Link> : row.type}
                        {views.length > 1 && (
                          <div className="d-flex flex-wrap gap-2 small">
                            {views.map((view) => <Link key={view.slug} href={`/graph/${view.slug}`}>{view.title}</Link>)}
                          </div>
                        )}
                      </td>
                      <td className="text-end" style={{ textAlign: "right" }}>{row.count.toLocaleString()}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>
      </div>
    </>
  );
}
