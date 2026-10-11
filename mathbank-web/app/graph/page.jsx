"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Callout, Pill } from "../_components/ui.jsx";
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
  const [mounted, setMounted] = useState(false);

  const load = useCallback((signal) => {
    setData(null);
    setError(null);
    fetch("/api/graph/overview", { signal })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`status ${res.status}`))))
      .then(setData)
      .catch((err) => { if (err.name !== "AbortError") setError(err.message); });
  }, []);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const nodeCounts = data?.nodeCounts ?? [];
  const relationshipCounts = data?.relationshipCounts ?? [];
  const totalNodes = sum(nodeCounts);
  const totalRelationships = sum(relationshipCounts);

  const formatNumber = useCallback((value) => {
    const num = Number(value);
    if (!Number.isFinite(num)) return "—";
    return mounted ? num.toLocaleString() : String(num);
  }, [mounted]);

  return (
    <>
      <div className="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-3">
        <p className="text-secondary mb-0">Scan projected nodes, relationships and curriculum readiness before drilling into a specific view.</p>
        <Link href="/learn" className="btn btn-sm btn-outline-secondary">
          Start guided practice
        </Link>
      </div>

      {error && (
        <Callout tone="danger" role="alert" title="Could not load graph overview" className="mb-3">
          <div className="d-flex flex-wrap align-items-center justify-content-between gap-2">
            <span>Could not load graph overview: {error}</span>
            <button type="button" className="btn btn-sm btn-primary" onClick={() => load()}>
              Retry
            </button>
          </div>
        </Callout>
      )}

      {!data && !error && (
        <Callout tone="insight" role="status" title="Loading overview" className="mb-3">
          <div className="d-flex align-items-center gap-2">
            <span className="spinner-border spinner-border-sm text-primary" aria-hidden="true" />
            <span>Fetching graph totals and relationship coverage.</span>
          </div>
        </Callout>
      )}

      {data && (
        <>
          <Callout tone={data.teaching?.reviewedSkills === 0 ? "warning" : "hint"} title="Teaching graph readiness" className="mb-3">
            <p className="small mb-2">
              {data.teaching
                ? `${formatNumber(data.teaching.reviewedSkills)} reviewed skills of ${formatNumber(data.teaching.skills)} collected.`
                : "Teaching metadata totals are unavailable."}
              {data.teaching?.reviewedSkills === 0 && " No reviewed skill metadata has been projected yet."} Corpus tags alone are not a prerequisite curriculum.
            </p>
            {data.teaching && (
              <div className="d-flex flex-wrap gap-2">
                <Pill tone="info" icon="bullseye">{formatNumber(data.teaching.reviewedSkills)} reviewed skills</Pill>
                <Pill tone="neutral" icon="diagram-3">{formatNumber(data.teaching.skills)} collected skills</Pill>
              </div>
            )}
          </Callout>

          <div className={styles.metrics}>
            <div className={styles.metric}>
              <div className={styles.metricLabel}>Total nodes</div>
              <div className={`${styles.metricValue} mb-num`}>{formatNumber(totalNodes)}</div>
            </div>
            <div className={styles.metric}>
              <div className={styles.metricLabel}>Total relationships</div>
              <div className={`${styles.metricValue} mb-num`}>{formatNumber(totalRelationships)}</div>
            </div>
            <div className={styles.metric}>
              <div className={styles.metricLabel}>Node labels</div>
              <div className={`${styles.metricValue} mb-num`}>{formatNumber(nodeCounts.length)}</div>
            </div>
            <div className={styles.metric}>
              <div className={styles.metricLabel}>Relationship types</div>
              <div className={`${styles.metricValue} mb-num`}>{formatNumber(relationshipCounts.length)}</div>
            </div>
          </div>

          <div className={styles.overviewGrid}>
            <section className={`card ${styles.tableCard}`}>
              <div className="card-header fw-semibold px-3 py-2">Nodes</div>
              {nodeCounts.length === 0 ? (
                <p className="text-body-secondary m-3">No nodes found.</p>
              ) : (
                <table className={`table table-sm table-hover mb-0 ${styles.simpleTable}`}>
                  <tbody>
                    {nodeCounts.map((row) => (
                      <tr key={row.label}>
                        <td>
                          <span className={`${styles.swatch} me-2`} style={{ background: colorFor(row.label) }} />
                          {row.label}
                        </td>
                        <td className="text-end mb-num">{formatNumber(row.count)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </section>
            <section className={`card ${styles.tableCard}`}>
              <div className="card-header fw-semibold px-3 py-2">Relationships</div>
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
                          <td className="text-end mb-num">{formatNumber(row.count)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </section>
          </div>
        </>
      )}
    </>
  );
}
