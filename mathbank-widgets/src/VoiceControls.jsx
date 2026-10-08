"use client";
// Voice add-ons (requirements 29). The browser never sees the ElevenLabs key: it calls the host app's
// own /api/voice/* routes, which attach ELEVEN_API_KEY server-side.
import { useEffect, useRef, useState } from "react";
import { speakableText } from "./speech.mjs";
import { WIcon, WidgetStyles } from "./icons.jsx";

let currentAudio = null;

/** 🔊 Read tutor text aloud via POST {endpoint} {text} -> audio/mpeg. Click again to stop. */
export function SpeakButton({ text, endpoint = "/api/voice/tts", className = "", label = "Listen" }) {
  const [state, setState] = useState("idle");
  const audioRef = useRef(null);
  useEffect(() => () => { audioRef.current?.pause(); }, []);

  async function toggle() {
    if (state === "playing" || state === "loading") {
      audioRef.current?.pause();
      setState("idle");
      return;
    }
    const speech = speakableText(text);
    if (!speech) return;
    setState("loading");
    try {
      const res = await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: speech }) });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || `voice ${res.status}`);
      const url = URL.createObjectURL(await res.blob());
      currentAudio?.pause();
      const audio = new Audio(url);
      currentAudio = audio;
      audioRef.current = audio;
      audio.onended = () => { setState("idle"); URL.revokeObjectURL(url); };
      await audio.play();
      setState("playing");
    } catch (err) {
      setState("error");
      console.warn("tts failed", err);
      setTimeout(() => setState("idle"), 2500);
    }
  }

  const icon = state === "loading" ? "spinner" : state === "playing" ? "stop" : state === "error" ? "alert" : "speaker";
  return (
    <button type="button" className={`mbw-speak${state === "playing" ? " is-live" : ""} ${className}`} onClick={toggle}
      title={state === "error" ? "Voice unavailable" : state === "playing" ? "Stop" : label} aria-label={label} data-testid="speak-button">
      <WidgetStyles /><WIcon name={icon} size={16} />
    </button>
  );
}

/** 🎤 Record up to `maxSeconds`, POST multipart audio to {endpoint}, call onTranscript(text). */
export function MicButton({ onTranscript, endpoint = "/api/voice/stt", maxSeconds = 60, className = "", disabled = false, onBusyChange }) {
  const [state, setState] = useState("idle");
  const recRef = useRef(null);
  const timerRef = useRef(null);
  const [supported, setSupported] = useState(false);
  useEffect(() => {
    onBusyChange?.(["requesting", "recording", "transcribing"].includes(state));
    return () => onBusyChange?.(false);
  }, [state, onBusyChange]);
  // Detected after mount so server and client render the same markup (no hydration mismatch).
  useEffect(() => { setSupported(typeof window.MediaRecorder !== "undefined" && !!navigator.mediaDevices?.getUserMedia); }, []);

  useEffect(() => () => { clearTimeout(timerRef.current); recRef.current?.stream?.getTracks().forEach((t) => t.stop()); }, []);

  async function start() {
    setState("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const chunks = [];
      rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        clearTimeout(timerRef.current);
        setState("transcribing");
        try {
          const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
          const form = new FormData();
          form.append("file", blob, `speech.${(rec.mimeType || "audio/webm").includes("mp4") ? "mp4" : "webm"}`);
          const res = await fetch(endpoint, { method: "POST", body: form });
          const body = await res.json().catch(() => ({}));
          if (!res.ok) throw new Error(body.error || `stt ${res.status}`);
          if (body.text) onTranscript?.(body.text);
          setState("idle");
        } catch (err) {
          console.warn("stt failed", err);
          setState("error");
          setTimeout(() => setState("idle"), 2500);
        }
      };
      recRef.current = rec;
      rec.start();
      setState("recording");
      timerRef.current = setTimeout(() => rec.state === "recording" && rec.stop(), maxSeconds * 1000);
    } catch (err) {
      console.warn("microphone unavailable", err);
      setState("error");
      setTimeout(() => setState("idle"), 2500);
    }
  }

  function toggle() {
    if (state === "recording") recRef.current?.stop();
    else if (state === "idle" || state === "error") start();
  }

  if (!supported) return null;
  const icon = state === "recording" ? "stop" : state === "transcribing" ? "spinner" : state === "error" ? "alert" : "mic";
  return (
    <button type="button" className={`mbw-ghost${state === "recording" ? " is-live" : ""} ${className}`}
      onClick={toggle} disabled={disabled || state === "transcribing" || state === "requesting"} data-testid="mic-button"
      title={state === "recording" ? "Stop and transcribe" : "Dictate (speech to text)"} aria-label="Dictate">
      <WIcon name={icon} />
    </button>
  );
}
