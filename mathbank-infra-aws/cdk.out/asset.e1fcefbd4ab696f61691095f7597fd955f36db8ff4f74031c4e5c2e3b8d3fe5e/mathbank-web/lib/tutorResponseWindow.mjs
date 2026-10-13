export function publicResponseWindow(value) {
  if (value === null) return null;
  if (!value || typeof value !== "object"
      || !/^[0-9a-f-]{36}$/.test(value.id)
      || !["hint", "explain"].includes(value.action)
      || !Number.isInteger(value.seconds) || value.seconds < 15 || value.seconds > 300
      || typeof value.question !== "string" || !value.question.trim() || value.question.length > 2000) {
    throw new Error("The tutor returned an invalid response window. Please retry.");
  }
  return { id: value.id, action: value.action, seconds: value.seconds, question: value.question };
}

export function idleQuestionMessage(window) {
  const value = publicResponseWindow(window);
  if (!value) throw new Error("No active tutor question.");
  return `[Tutor idle:${value.id}:${value.action}]`;
}

export class ActiveResponseClock {
  constructor(seconds, now) {
    this.remaining = seconds * 1000;
    this.last = now;
    this.paused = true;
    this.fired = false;
  }

  update(now, paused) {
    if (!this.paused) this.remaining = Math.max(0, this.remaining - Math.max(0, now - this.last));
    this.last = now;
    this.paused = paused;
    const expired = !paused && this.remaining === 0 && !this.fired;
    if (expired) this.fired = true;
    return { seconds: Math.ceil(this.remaining / 1000), expired };
  }
}
