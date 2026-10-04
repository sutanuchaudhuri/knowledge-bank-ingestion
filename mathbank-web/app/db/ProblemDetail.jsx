"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { normalizeMathDelimiters } from "../../lib/markdown.js";
import { panel } from "./dbStyles.js";

/** Fetches and renders the full HAS_SOLUTION/TESTS/USES_TECHNIQUE detail for one problem. */
export default function ProblemDetail({ code }) {
  const [problem, setProblem] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!code) return;
    setProblem(null);
    setError(null);
    fetch(`/api/rest/problems/${encodeURIComponent(code)}`)
      .then((res) =>
        res.ok ? res.json() : res.json().then((body) => Promise.reject(new Error(body.error || `status ${res.status}`)))
      )
      .then(setProblem)
      .catch((err) => setError(err.message));
  }, [code]);

  if (!code) return <div className={panel}><p className="text-secondary mb-0">Select a row to see details.</p></div>;
  if (error) return <div className="alert alert-danger" role="alert">Could not load {code}: {error}</div>;
  if (!problem) return <div className={panel}><p className="mb-0" role="status">Loading…</p></div>;

  return (
    <div className={panel}>
      <h3 className="h5 fw-bold">{problem.canonical_code}</h3>
      <p style={{ color: "#666", fontSize: 13 }}>
        {problem.competition} {problem.year} · {problem.paper_code} · Problem {problem.problem_number}
        {problem.source_url && (
          <>
            {" · "}
            <a href={problem.source_url} target="_blank" rel="noreferrer">source</a>
          </>
        )}
      </p>

      {problem.statement_text && (
        <div className="markdown-body" style={{ fontSize: 14, marginBottom: 12 }}>
          <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
            {normalizeMathDelimiters(problem.statement_text)}
          </ReactMarkdown>
        </div>
      )}

      {problem.official_answer && (
        <p style={{ fontSize: 13 }}>
          <strong>Answer:</strong> {problem.official_answer}
        </p>
      )}

      {problem.concepts?.length > 0 && (
        <p style={{ fontSize: 13 }}>
          <strong>Concepts (TESTS):</strong>{" "}
          {problem.concepts.map((c) => c.name).join(", ")}
        </p>
      )}

      {problem.techniques?.length > 0 && (
        <p style={{ fontSize: 13 }}>
          <strong>Techniques (USES_TECHNIQUE):</strong>{" "}
          {problem.techniques.map((t) => t.name).join(", ")}
        </p>
      )}

      {problem.solutions?.length > 0 && (
        <div>
          <strong style={{ fontSize: 13 }}>Solutions (HAS_SOLUTION):</strong>
          {problem.solutions.map((sol, i) => (
            <details key={i} open={i === 0} className="border rounded-3 p-3 my-3">
              <summary className="fw-semibold">
                {sol.solution_kind} rev {sol.revision} · {sol.verification_status}
              </summary>
              <div className="markdown-body" style={{ fontSize: 13, marginTop: 6 }}>
                <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]}>
                  {normalizeMathDelimiters(sol.body_markdown || "")}
                </ReactMarkdown>
              </div>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}
