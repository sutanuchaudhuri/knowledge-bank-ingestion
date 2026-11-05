// Browser side of the live tutor: microphone -> PCM16 WebSocket frames; model audio/transcripts/sources -> page.
const $ = (id) => document.getElementById(id);
const ui = {
  start: $("start"), stop: $("stop"), state: $("state"), timer: $("timer"), level: $("level"),
  transcript: $("transcript"), text: $("text"), send: $("send"), form: $("text-form"),
  sources: $("sources"), sourcesEmpty: $("sources-empty"),
};
// Exposed for the automated smoke test; contains no audio payloads.
window.__tutor = { events: [], audioChunks: 0, ended: null };

let ws = null, capture = null, playback = null, playHead = 0, playing = new Set(), deadline = 0, ticker = null;
const turns = new Map();

function setState(text, state = text) { ui.state.textContent = text; ui.state.dataset.state = state; }

function line(role, text = "") {
  const li = document.createElement("li");
  li.className = role;
  const who = document.createElement("span");
  who.className = "who";
  who.textContent = role === "user" ? "You" : role === "assistant" ? "Tutor" : "";
  const body = document.createElement("span");
  body.textContent = text;
  li.append(who, body);
  ui.transcript.append(li);
  ui.transcript.scrollTop = ui.transcript.scrollHeight;
  return body;
}

function transcript(msg) {
  let body = turns.get(msg.id);
  if (!body) { body = line(msg.role); turns.set(msg.id, body); }
  if (msg.delta) body.textContent += msg.delta;
  if (msg.text) body.textContent = msg.text;
  ui.transcript.scrollTop = ui.transcript.scrollHeight;
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function sources(msg) {
  ui.sourcesEmpty.hidden = true;
  const block = element("section", undefined, "source");
  block.append(element("h3", `Searched: “${msg.topic}”`));
  if (msg.error || !msg.grounded) {
    block.append(element("p", msg.error || "No close MathBank material — the tutor was told not to invent sources."));
  }
  for (const concept of msg.concepts || []) {
    const p = element("p");
    p.append(element("span", concept.type || "CONCEPT", "tag"), element("strong", concept.name));
    if (concept.summary) p.append(document.createTextNode(` — ${concept.summary}`));
    block.append(p);
  }
  for (const problem of msg.practice_problems || []) {
    const p = element("p");
    p.append(element("span", "PRACTICE", "tag"), element("strong", problem.code), document.createTextNode(` ${problem.statement}`));
    block.append(p);
  }
  if (msg.teaching_moves) block.append(element("p", `${msg.teaching_moves} private teaching notes used by the tutor (not shown).`, "muted"));
  ui.sources.prepend(block);
}

function play(b64, rate) {
  const raw = atob(b64);
  const samples = new Int16Array(raw.length / 2);
  for (let i = 0; i < samples.length; i++) samples[i] = raw.charCodeAt(2 * i) | (raw.charCodeAt(2 * i + 1) << 8);
  const buffer = playback.createBuffer(1, samples.length, rate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < samples.length; i++) data[i] = samples[i] / 32768;
  const source = playback.createBufferSource();
  source.buffer = buffer;
  source.connect(playback.destination);
  playHead = Math.max(playHead, playback.currentTime + 0.03);
  source.start(playHead);
  playHead += buffer.duration;
  playing.add(source);
  source.onended = () => playing.delete(source);
}

function bargeIn() {
  for (const source of playing) { try { source.stop(); } catch { /* already stopped */ } }
  playing.clear();
  playHead = playback ? playback.currentTime : 0;
}

function tick() {
  const left = Math.max(0, Math.round((deadline - Date.now()) / 1000));
  ui.timer.textContent = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")} left`;
}

async function startCapture(rate) {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  const context = new AudioContext();
  await context.audioWorklet.addModule("/static/pcm-worklet.js");
  const node = new AudioWorkletNode(context, "pcm-capture", { processorOptions: { targetRate: rate } });
  node.port.onmessage = ({ data }) => {
    ui.level.value = Math.min(1, data.peak * 3);
    if (ws?.readyState === WebSocket.OPEN) ws.send(data.pcm);
  };
  context.createMediaStreamSource(stream).connect(node);
  return { stream, context, node };
}

function cleanup(message) {
  clearInterval(ticker);
  capture?.stream.getTracks().forEach((t) => t.stop());
  capture?.context.close();
  capture = null;
  if (playback) setTimeout(() => playback?.close(), 1500);
  ui.start.disabled = false; ui.stop.disabled = true; ui.text.disabled = true; ui.send.disabled = true;
  ui.level.value = 0; ui.timer.textContent = "—";
  if (message) line("system", message);
}

async function start() {
  ui.start.disabled = true;
  window.__tutor.ended = null;
  setState("Connecting…", "connecting");
  playback = new AudioContext({ sampleRate: 24000 });
  playHead = 0;
  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onmessage = async ({ data }) => {
    const msg = JSON.parse(data);
    if (msg.type !== "audio") window.__tutor.events.push(msg);
    switch (msg.type) {
      case "ready":
        deadline = Date.now() + msg.seconds * 1000; tick(); ticker = setInterval(tick, 1000);
        try { capture = await startCapture(msg.rate_in); } catch {
          setState("Microphone blocked", "error"); ws.send(JSON.stringify({ type: "stop" })); return;
        }
        setState("Listening", "listening");
        ui.stop.disabled = false; ui.text.disabled = false; ui.send.disabled = false;
        line("system", "Connected. Say hello and name a topic you want to learn.");
        break;
      case "audio": window.__tutor.audioChunks++; play(msg.audio, msg.rate); break;
      case "transcript": transcript(msg); break;
      case "barge_in": bargeIn(); break;
      case "tool": setState("Searching MathBank…", "searching"); break;
      case "sources": sources(msg); break;
      case "status": setState(msg.state === "speaking" ? "Tutor speaking" : msg.state === "listening" ? "Listening" : msg.state, msg.state); break;
      case "error": setState("Error", "error"); line("system", msg.message); break;
      case "ended":
        window.__tutor.ended = msg;
        setState("Session ended", "ended");
        cleanup(`Session ended (${msg.reason}, ${msg.seconds}s). ${Math.round(msg.budget_remaining_s)}s of POC audio budget left.`);
        break;
    }
  };
  ws.onclose = () => { if (!window.__tutor.ended) { setState("Disconnected", "error"); cleanup(); } };
}

ui.start.addEventListener("click", start);
ui.stop.addEventListener("click", () => ws?.send(JSON.stringify({ type: "stop" })));
ui.form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = ui.text.value.trim();
  if (!text || ws?.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: "text", text }));
  line("user", text);
  ui.text.value = "";
});
for (const chip of document.querySelectorAll(".chip")) {
  chip.addEventListener("click", () => {
    if (ws?.readyState === WebSocket.OPEN) { ws.send(JSON.stringify({ type: "text", text: chip.dataset.topic })); line("user", chip.dataset.topic); }
    else ui.text.value = chip.dataset.topic;
  });
}
