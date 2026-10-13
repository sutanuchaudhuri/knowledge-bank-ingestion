"use client";

import { Suspense, useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Callout, EmptyState, Icon, IconButton, PageHeader, Pill, TabBar } from "../../../../_components/ui.jsx";
import { endpoint, request } from "./shared.js";
import OverviewTab from "./OverviewTab.jsx";
import ContentTab from "./ContentTab.jsx";
import MediaTab from "./MediaTab.jsx";
import QuizzesTab from "./QuizzesTab.jsx";
import WidgetsTab from "./WidgetsTab.jsx";
import VersionsTab from "./VersionsTab.jsx";
import ActivityTab from "./ActivityTab.jsx";
import JsonTab from "./JsonTab.jsx";

const TABS = [
  ["overview", "Overview", "info-circle"],
  ["content", "Content", "list-check"],
  ["media", "Media", "camera-video"],
  ["quizzes", "Quizzes", "patch-question"],
  ["widgets", "Widgets", "puzzle"],
  ["versions", "Versions", "clock-history"],
  ["activity", "Activity", "graph-up-arrow"],
  ["json", "JSON", "braces"],
];

function MicroCourseWorkspaceInner() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const code = Array.isArray(params.code) ? params.code[0] : params.code;
  const tab = TABS.some(([key]) => key === searchParams.get("tab")) ? searchParams.get("tab") : "overview";

  const [course, setCourse] = useState(null);
  const [release, setRelease] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [refreshToken, setRefreshToken] = useState(0);

  function refresh() {
    setRefreshToken(value => value + 1);
  }

  useEffect(() => {
    if (!code) return undefined;
    const controller = new AbortController();
    setLoading(true);
    request(`${endpoint}/${encodeURIComponent(code)}`, { signal: controller.signal })
      .then(data => {
        setCourse(data);
        const newest = data.releases?.[0];
        if (!newest) return setRelease(null);
        return request(`${endpoint}/releases/${newest.release_id}`, { signal: controller.signal }).then(setRelease);
      })
      .catch(err => { if (err.name !== "AbortError") setError(err.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [code, refreshToken]);

  function setTab(next) {
    const query = new URLSearchParams(Array.from(searchParams.entries()));
    query.set("tab", next);
    router.push(`/admin/micro-courses/${encodeURIComponent(code)}?${query.toString()}`);
  }

  async function deactivate() {
    setBusy(true);
    setError("");
    try {
      const actor = window.prompt("Your name (for the audit trail)");
      if (!actor) { setBusy(false); return; }
      await request(`${endpoint}/${encodeURIComponent(code)}/deactivate`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ actor }),
      });
      setNotice("Course deactivated — hidden from the student catalog.");
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function reactivate() {
    setBusy(true);
    setError("");
    try {
      const actor = window.prompt("Your name (for the audit trail)");
      if (!actor) { setBusy(false); return; }
      await request(`${endpoint}/${encodeURIComponent(code)}/reactivate`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ actor }),
      });
      setNotice("Course reactivated — visible in the student catalog again.");
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function newDraftVersion() {
    if (!course) return;
    const actor = window.prompt("Your name (for the audit trail)");
    if (!actor) return;
    setBusy(true);
    setError("");
    try {
      const parent = course.releases?.[0]?.release_id;
      await request(`${endpoint}/${encodeURIComponent(code)}/releases`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ created_by: actor, parent_release_id: parent || null }),
      });
      setNotice("New draft version created.");
      setTab("content");
      refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <>
      <PageHeader icon="diagram-3" title="Loading…" subtitle="Opening the course workspace." />
    </>;
  }
  if (error && !course) {
    return <>
      <PageHeader icon="diagram-3" title="Course unavailable" />
      <Callout tone="danger" role="alert">{error}</Callout>
    </>;
  }
  if (!course) return <EmptyState icon="diagram-3">Course not found.</EmptyState>;

  const latestRelease = course.releases?.[0];
  const publishedRelease = course.releases?.find(r => r.status === "PUBLISHED");
  const hasDraft = course.releases?.some(r => r.status === "DRAFT");

  return (
    <>
      <PageHeader
        icon="diagram-3"
        title={course.title}
        subtitle={course.canonical_code}
        pills={[
          publishedRelease && <Pill key="pub" tone="success">Published v{publishedRelease.version}</Pill>,
          hasDraft && latestRelease?.status === "DRAFT" && <Pill key="draft" tone="warning">Draft v{latestRelease.version} in progress</Pill>,
          course.is_active === false && <Pill key="deact" tone="danger">Deactivated</Pill>,
        ].filter(Boolean)}
        actions={[
          <Link key="preview" href={`/learn/courses/${encodeURIComponent(code)}?preview=1${latestRelease ? `&release_id=${latestRelease.release_id}` : ""}`}
            target="_blank" className="btn btn-outline-secondary btn-sm">
            <Icon name="eye" /> View as student
          </Link>,
          <IconButton key="json" icon="braces" label="View JSON" variant="outline-secondary" size="sm" onClick={() => setTab("json")} />,
          !hasDraft && publishedRelease && (
            <IconButton key="newdraft" icon="file-earmark-plus" label="New draft version" variant="outline-primary" size="sm"
              disabled={busy} onClick={newDraftVersion} />
          ),
          course.is_active !== false
            ? <IconButton key="deactivate" icon="slash-circle" label="Deactivate" variant="outline-danger" size="sm" disabled={busy || !publishedRelease} onClick={deactivate} />
            : <IconButton key="reactivate" icon="arrow-counterclockwise" label="Reactivate" variant="outline-success" size="sm" disabled={busy} onClick={reactivate} />,
        ].filter(Boolean)}
      />
      {error && <Callout tone="danger" role="alert">{error}</Callout>}
      {notice && <Callout tone="success" role="status">{notice}</Callout>}

      <TabBar tabs={TABS} value={tab} onChange={setTab} label="Course workspace sections" />

      <div className="mt-3">
        {tab === "overview" && <OverviewTab course={course} refresh={refresh} />}
        {tab === "content" && <ContentTab course={course} release={release} refresh={refresh} />}
        {tab === "media" && <MediaTab course={course} release={release} refresh={refresh} />}
        {tab === "quizzes" && <QuizzesTab course={course} release={release} refresh={refresh} />}
        {tab === "widgets" && <WidgetsTab course={course} release={release} refresh={refresh} />}
        {tab === "versions" && <VersionsTab course={course} refresh={refresh} />}
        {tab === "activity" && <ActivityTab course={course} />}
        {tab === "json" && <JsonTab course={course} release={release} />}
      </div>
    </>
  );
}

export default function MicroCourseWorkspace() {
  return (
    <Suspense fallback={<p role="status" className="text-secondary">Loading…</p>}>
      <MicroCourseWorkspaceInner />
    </Suspense>
  );
}
