"use client";

import MathText from "./MathText.jsx";

const when = (ts) => (ts ? new Date(ts.endsWith("Z") || ts.includes("+") ? ts : `${ts}Z`).toLocaleString() : "");
const KIND_LABEL = { thinking: "Thinking", tool_call: "Tool call", tool_result: "Tool result", error: "Error" };

// Renders a rebuilt agent conversation (requirements/22). Students get text only; the admin view
// also receives thinking/tool messages, rendered collapsed and monospace.
export default function Transcript({ transcript }) {
  if (!transcript) return null;
  const messages = transcript.messages || [];
  if (!messages.length) return <p className="text-secondary" data-testid="transcript-empty">No messages in this conversation yet.</p>;
  return (
    <ol className="list-unstyled mb-0" data-testid="transcript">
      {messages.map((m, i) => {
        const student = m.role === "student";
        if (m.kind !== "text") {
          return (
            <li key={i} className="mb-2 ms-4">
              <details className="border rounded-3 px-3 py-2 bg-light small">
                <summary className="text-secondary">
                  <span className={`badge me-2 ${m.kind === "error" ? "text-bg-danger" : "text-bg-secondary"}`}>{KIND_LABEL[m.kind] || m.kind}</span>
                  {m.tool && <code>{m.tool}</code>} <span className="ms-2">{when(m.timestamp)}</span>
                </summary>
                <pre className="mb-0 mt-2" style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{m.text}</pre>
              </details>
            </li>
          );
        }
        return (
          <li key={i} className={`d-flex mb-3 ${student ? "justify-content-end" : ""}`}>
            <div className={`rounded-4 p-3 ${student ? "bg-primary text-white" : "bg-body-tertiary"}`} style={{ maxWidth: "90%", minWidth: 0 }}>
              <div className="small fw-bold mb-1">{student ? "Student" : "MathBank Tutor"} <span className="fw-normal opacity-75 ms-2">{when(m.timestamp)}</span></div>
              {student ? <div style={{ whiteSpace: "pre-wrap" }}>{m.text}</div> : <MathText>{m.text}</MathText>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
