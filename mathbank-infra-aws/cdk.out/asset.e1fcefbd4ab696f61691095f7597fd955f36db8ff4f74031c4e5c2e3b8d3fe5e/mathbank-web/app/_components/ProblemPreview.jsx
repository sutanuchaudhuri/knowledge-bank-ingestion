"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import MathText from "./MathText.jsx";
import ProblemDiagrams from "./ProblemDiagrams.jsx";
import { Callout, EmptyState, Icon, Pager, Pill } from "./ui.jsx";
import { corpusJson, hasQuestionText, relatedCandidates, relatedProblemRequest, tutorProblemHref, uniqueProblemTags } from "../../lib/corpusProblems.mjs";
import { hasStepSolution } from "../../lib/solveFlow.mjs";

export function ProblemPreview({ problem, discuss = true }) {
  const code = problem.canonical_code;
  return <div className="mb-corpus-problem min-w-0" data-testid={`problem-preview-${code}`}>
    <div className="d-flex flex-wrap gap-2 mb-3">
      {problem.competition && <Pill tone="primary" icon="trophy">{problem.competition}</Pill>}
      {problem.year != null && <Pill icon="calendar3">{problem.year}</Pill>}
      {problem.problem_number != null && <Pill icon="file-earmark-text">Problem {problem.problem_number}</Pill>}
      {problem.paper_code && <Pill title="Paper">{problem.paper_code}</Pill>}
      {problem.diagrams?.length > 0 && <Pill tone="info" icon="image">{problem.diagrams.length} source figures</Pill>}
      {!hasQuestionText(problem) && <Pill tone="warning" icon="exclamation-diamond">Text incomplete</Pill>}
      {uniqueProblemTags(problem.concepts).map((tag) => <Pill key={`concept:${tag.slug || tag.name}`} tone="info" icon="diagram-3" title="Published concept tag">{tag.name}</Pill>)}
      {uniqueProblemTags(problem.techniques).map((tag) => <Pill key={`technique:${tag.slug || tag.name}`} tone="success" icon="tools" title="Published technique tag">{tag.name}</Pill>)}
    </div>
    {hasQuestionText(problem)
      ? <div className="mb-tutor-problem"><MathText>{problem.statement_text}</MathText></div>
      : <Callout tone="warning">The question text has not been ingested yet. Use the original source when available.</Callout>}
    <ProblemDiagrams code={code} images={problem.diagrams} />
    {discuss && <div className="d-flex flex-wrap gap-2 mt-3">
      <Link className="btn btn-primary btn-sm" href={tutorProblemHref(code)}><Icon name="chat-dots" />Discuss with tutor</Link>
      <Link className="btn btn-outline-secondary btn-sm" href={`/learn?problem=${encodeURIComponent(code)}`}>
        <Icon name="signpost-split" />Learn with diagnosis and hints
      </Link>
      {hasStepSolution(code) && <Link className="btn btn-outline-secondary btn-sm" href={`/learn/solve/${encodeURIComponent(code)}`}>
        <Icon name="list-check" />Solve step by step
      </Link>}
    </div>}
  </div>;
}

export function ProblemPreviewCard({ item, related = false, onChoose, revealSolutions = true }) {
  const [open, setOpen] = useState(false);
  const [problem, setProblem] = useState(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setProblem(null); setError("");
    corpusJson(`/api/rest/problems/${encodeURIComponent(item.canonical_code)}`, { signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) setProblem(data); })
      .catch((err) => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [open, item.canonical_code, retry]);
  return <details className="mb-corpus-preview" onToggle={(event) => {
    if (event.target === event.currentTarget) setOpen(event.currentTarget.open);
  }}>
    <summary className="mb-section-title mb-0">
      <Icon name="file-earmark-text" />
      <span className="min-w-0 text-break">{item.canonical_code}</span>
      <span className="d-flex flex-wrap gap-1 ms-auto">
        {item.competition && <Pill tone="primary">{item.competition}</Pill>}
        {item.year != null && <Pill>{item.year}</Pill>}
      </span>
    </summary>
    {open && <div className="pt-3">
      {error ? <Callout tone="danger" role="alert">{error} <button className="btn btn-sm btn-outline-secondary" onClick={() => setRetry((value) => value + 1)}>Retry preview</button></Callout>
        : !problem ? <p role="status">Loading question…</p>
          : <><ProblemPreview problem={problem} discuss={!onChoose} />
            {onChoose && <button className="btn btn-primary btn-sm mt-2" onClick={() => onChoose(item)}><Icon name="signpost-split" />Practise this problem</button>}
            {related && <RelatedProblems problem={problem} />}
            {revealSolutions && <ProblemSolutions problem={problem} />}</>}
    </div>}
  </details>;
}

export function ProblemSolutions({ problem }) {
  const [open, setOpen] = useState(false);
  if (!problem.official_answer && !problem.solutions?.length) return null;
  return <details className="mb-corpus-related mt-3" onToggle={(event) => {
    if (event.target === event.currentTarget) setOpen(event.currentTarget.open);
  }}>
    <summary className="mb-section-title mb-0"><Icon name="journal-check" />Reveal answer and solutions</summary>
    {open && <div className="pt-3">
      {problem.official_answer && <div><strong>Answer:</strong> <MathText>{String(problem.official_answer)}</MathText></div>}
      {problem.solutions?.map((solution, index) => <details key={index} className="border rounded-3 p-3 mt-3">
        <summary className="fw-semibold">{solution.solution_kind} rev {solution.revision} · {solution.verification_status}</summary>
        <div className="markdown-body mt-2"><MathText>{solution.body_markdown || ""}</MathText></div>
      </details>)}
    </div>}
  </details>;
}

export function RelatedProblems({ problem }) {
  const [open, setOpen] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const request = relatedProblemRequest(problem);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setResult(null); setError("");
    const body = relatedProblemRequest(problem);
    if (!body) return;
    corpusJson("/api/rest/search", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body), signal: controller.signal,
    }).then((data) => {
      if (!controller.signal.aborted) setResult({ ...data, results: relatedCandidates(data.results, problem.canonical_code) });
    }).catch((err) => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [open, problem, retry]);
  return <details className="mb-corpus-related mt-3" onToggle={(event) => {
    if (event.target === event.currentTarget) setOpen(event.currentTarget.open);
  }}>
    <summary className="mb-section-title mb-0"><Icon name="stars" />Explore related problems</summary>
    {open && <div className="pt-3">
      <p className="small text-secondary">Candidates from published tags and question text, across competitions. Topic fit is not guaranteed.</p>
      {!request ? <EmptyState>No question text or tags are available to find related problems.</EmptyState>
        : error ? <Callout tone="danger" role="alert">{error} <button className="btn btn-sm btn-outline-secondary" onClick={() => setRetry((value) => value + 1)}>Retry related search</button></Callout>
          : !result ? <p role="status">Finding related questions…</p>
            : <>
              {result.warnings?.map((warning, index) => <Callout key={index} tone="warning">{warning}</Callout>)}
              {result.results.length ? <div className="d-grid gap-2">{result.results.map((item) => <ProblemPreviewCard key={item.canonical_code} item={item} />)}</div>
                : <EmptyState icon="search">No related candidates found.</EmptyState>}
            </>}
    </div>}
  </details>;
}

export function CompetitionProblemPreviews({ competition }) {
  const [open, setOpen] = useState(false);
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const limit = 6;
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setPage(null); setError("");
    const query = new URLSearchParams({ competition, offset: String(offset), limit: String(limit) });
    corpusJson(`/api/rest/problems?${query}`, { signal: controller.signal })
      .then((data) => { if (!controller.signal.aborted) setPage(data); })
      .catch((err) => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [open, competition, offset, retry]);
  return <details className="mb-corpus-related" onToggle={(event) => {
    if (event.target === event.currentTarget) setOpen(event.currentTarget.open);
  }}>
    <summary className="mb-section-title mb-0"><Icon name="collection" />Preview questions</summary>
    {open && <div className="pt-3">
      {error ? <Callout tone="danger" role="alert">{error} <button className="btn btn-sm btn-outline-secondary" onClick={() => setRetry((value) => value + 1)}>Retry questions</button></Callout>
        : !page ? <p role="status">Loading questions…</p>
          : page.items.length ? <div className="d-grid gap-2">{page.items.map((item) => <ProblemPreviewCard key={item.canonical_code} item={item} related />)}</div>
            : <EmptyState icon="file-earmark-text">No problems available in this competition.</EmptyState>}
      <Pager offset={offset} limit={limit} hasMore={page?.hasMore} count={page?.items.length || 0} loading={!page}
        onPrev={() => setOffset((value) => Math.max(0, value - limit))} onNext={() => setOffset((value) => value + limit)} />
    </div>}
  </details>;
}
