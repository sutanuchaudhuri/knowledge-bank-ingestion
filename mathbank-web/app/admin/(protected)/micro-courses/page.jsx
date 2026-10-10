"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Callout, EmptyState, Icon, Pager, PageHeader, Pill } from "../../../_components/ui.jsx";

const endpoint = "/api/rest/admin/micro-courses";
const PAGE_SIZE = 25;

async function request(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || body.detail || `Request failed (${response.status})`);
  return body;
}

const STATUS_TONE = {
  PUBLISHED: "success",
  DRAFT: "warning",
  REVIEWED: "info",
  APPROVED: "info",
  SUPERSEDED: "neutral",
  RETIRED: "neutral",
};

/** Client-only relative date — never server-rendered, to avoid hydration drift (UI-15). */
function RelativeDate({ value }) {
  const [text, setText] = useState("");
  useEffect(() => {
    if (!value) return;
    const date = new Date(value);
    const days = Math.floor((Date.now() - date.getTime()) / 86400000);
    setText(days <= 0 ? "Today" : days === 1 ? "Yesterday" : `${days} days ago`);
  }, [value]);
  return <span className="small text-secondary">{text}</span>;
}

export default function MicroCourseCatalogPage() {
  const [rows, setRows] = useState([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    request(endpoint, { signal: controller.signal })
      .then(setRows)
      .catch(err => { if (err.name !== "AbortError") setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  const filtered = rows.filter(row => {
    const matchesStatus = statusFilter === "ALL"
      || (statusFilter === "DEACTIVATED" ? row.is_active === false : row.status === statusFilter);
    const needle = search.trim().toLowerCase();
    const matchesSearch = !needle || row.title.toLowerCase().includes(needle)
      || row.canonical_code.toLowerCase().includes(needle);
    return matchesStatus && matchesSearch;
  });
  const page = filtered.slice(offset, offset + PAGE_SIZE);

  return (
    <>
      <PageHeader
        icon="diagram-3"
        title="Micro-courses"
        subtitle="Author deterministic lessons mapped to existing concepts, techniques and skills."
        pills={[<Pill key="immutable" tone="info">Published releases are immutable</Pill>]}
        actions={[
          <Link key="new" href="/admin/micro-courses/new" className="btn btn-primary">
            <Icon name="plus-lg" /> New course
          </Link>,
        ]}
      />
      {error && <Callout tone="danger" role="alert">{error}</Callout>}

      <div className="d-flex flex-wrap gap-2 align-items-center mb-3">
        <div className="mb-search" style={{ maxWidth: 360 }}>
          <Icon name="search" className="mb-search-icon" />
          <input className="form-control" placeholder="Search title or code" value={search}
            onChange={event => { setSearch(event.target.value); setOffset(0); }} aria-label="Search courses" />
        </div>
        <div className="d-flex flex-wrap gap-1" role="group" aria-label="Filter by status">
          {["ALL", "DRAFT", "PUBLISHED", "SUPERSEDED", "RETIRED", "DEACTIVATED"].map(status => (
            <button key={status} type="button"
              className={`btn btn-sm ${statusFilter === status ? "btn-primary" : "btn-outline-secondary"}`}
              onClick={() => { setStatusFilter(status); setOffset(0); }}>
              {status === "ALL" ? "All" : status.charAt(0) + status.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <p role="status" className="text-secondary">Loading courses…</p>
      ) : !filtered.length ? (
        <EmptyState icon="diagram-3">
          {rows.length ? "No courses match these filters." : "No courses yet."}
        </EmptyState>
      ) : (
        <div className="table-responsive">
          <table className="table table-hover align-middle">
            <thead>
              <tr>
                <th scope="col">Title</th>
                <th scope="col">Target</th>
                <th scope="col">Status</th>
                <th scope="col">Version</th>
                <th scope="col">Steps</th>
                <th scope="col">Updated</th>
              </tr>
            </thead>
            <tbody>
              {page.map(row => (
                <tr key={row.canonical_code}>
                  <td>
                    <Link href={`/admin/micro-courses/${encodeURIComponent(row.canonical_code)}`} className="fw-semibold text-decoration-none stretched-link">
                      {row.title}
                    </Link>
                    <div className="small text-secondary">{row.canonical_code}</div>
                  </td>
                  <td>
                    {row.primary_targets?.map(item => <Pill key={item.slug || item.name} tone="neutral" className="me-1">{item.name}</Pill>)}
                  </td>
                  <td>
                    <div className="d-flex flex-wrap gap-1">
                      <Pill tone={STATUS_TONE[row.status] || "neutral"}>{row.status || "NO RELEASE"}</Pill>
                      {row.is_active === false && <Pill tone="danger">Deactivated</Pill>}
                    </div>
                  </td>
                  <td><Pill tone="neutral">v{row.version ?? "—"}</Pill></td>
                  <td><Pill tone="neutral" icon="list-check">{row.state_count ?? 0}</Pill></td>
                  <td><RelativeDate value={row.updated_at} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {filtered.length > PAGE_SIZE && (
        <Pager offset={offset} limit={PAGE_SIZE} hasMore={offset + PAGE_SIZE < filtered.length}
          loading={loading} onPrev={() => setOffset(value => Math.max(0, value - PAGE_SIZE))}
          onNext={() => setOffset(value => value + PAGE_SIZE)} count={page.length} />
      )}
    </>
  );
}
