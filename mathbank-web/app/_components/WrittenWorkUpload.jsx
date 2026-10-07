"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Callout, Icon, IconButton } from "./ui.jsx";
import { MAX_MEDIA_BYTES } from "../../lib/privateRuntimeProxy.mjs";
import { runtimeJson, runtimeErrorMessage } from "../../lib/attemptMedia.mjs";

export default function WrittenWorkUpload({ code }) {
  const input = useRef(null);
  const pasteTarget = useRef(null);
  const controllerRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [resume, setResume] = useState("");
  useEffect(() => () => controllerRef.current?.abort(), []);
  async function upload(file) {
    if (!file || controllerRef.current) return;
    setError(""); setResume("");
    if (!["image/jpeg", "image/png", "application/pdf"].includes(file.type)) {
      setError("Choose a JPEG, PNG or PDF of your work."); return;
    }
    if (file.size > MAX_MEDIA_BYTES) { setError("Choose a file under 20 MB."); return; }
    setBusy(true);
    const controller = new AbortController();
    controllerRef.current = controller;
    let destination = "";
    try {
      const submission = await runtimeJson("/api/rest/attempt-media/submissions", "POST", { problem_ref: code }, controller.signal);
      destination = `/learn/attempt-media?problem_ref=${encodeURIComponent(code)}&submission_id=${encodeURIComponent(submission.submission_id)}`;
      const response = await fetch(`/api/rest/attempt-media/submissions/${encodeURIComponent(submission.submission_id)}/assets?filename=${encodeURIComponent(file.name)}&expected_version=${submission.transcription_version}`, {
        method: "POST", headers: { "Content-Type": file.type }, body: file, signal: controller.signal,
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(runtimeErrorMessage(body.detail?.code) || body.error || body.detail || `Upload failed (${response.status}).`);
      }
      if (!controller.signal.aborted) window.location.assign(destination);
    } catch (err) {
      if (!controller.signal.aborted) { setError(err.message); setResume(destination); }
    } finally { controllerRef.current = null; if (!controller.signal.aborted) setBusy(false); }
  }
  return <div className="min-w-0" onPaste={(event) => {
    const file = [...event.clipboardData.files].find((item) => item.type.startsWith("image/"));
    if (file) { event.preventDefault(); void upload(file); }
  }}>
    <input ref={input} type="file" className="visually-hidden" aria-label="Upload work for this problem"
      accept=".jpg,.jpeg,.png,.pdf" disabled={busy}
      onChange={(event) => { const file = event.target.files?.[0]; event.target.value = ""; void upload(file); }} />
    <div className="d-flex flex-wrap gap-2">
      <button type="button" className="btn btn-outline-secondary btn-sm" disabled={busy} onClick={() => input.current?.click()}>
        <Icon name="camera" />{busy ? "Uploading…" : "Upload handwritten work"}
      </button>
      <IconButton icon="clipboard" label="Paste an image" disabled={busy} onClick={() => pasteTarget.current?.focus()} />
    </div>
    <div ref={pasteTarget} tabIndex={0} role="textbox" aria-label="Paste an image of your work" className="small text-secondary border rounded p-2 mt-2"
      title="Private upload · sign-in required · review transcription before analysis.">
      Paste an image here
    </div>
    {error && <Callout tone="danger" role="alert" className="mt-2">{error}{resume && <> <Link href={resume}>Resume this upload</Link></>}</Callout>}
  </div>;
}
