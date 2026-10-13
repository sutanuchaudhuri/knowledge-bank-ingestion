"use client";

import { useEffect, useRef, useState } from "react";
import { ActiveResponseClock } from "../../lib/tutorResponseWindow.mjs";
import { Icon, Pill } from "./ui.jsx";

export default function TutorResponseWindow({ window: checkpoint, blocked, paused, onPause, onElapsed }) {
  const [remaining, setRemaining] = useState(checkpoint.seconds);
  const [hidden, setHidden] = useState(false);
  const clockRef = useRef(null);
  const callbackRef = useRef(onElapsed);
  callbackRef.current = onElapsed;
  const blockedRef = useRef(blocked || paused);
  blockedRef.current = blocked || paused;

  useEffect(() => {
    const clock = new ActiveResponseClock(checkpoint.seconds, performance.now());
    clockRef.current = clock;
    setRemaining(checkpoint.seconds);
    const tick = () => {
      const result = clock.update(performance.now(), blockedRef.current || document.hidden);
      setRemaining(result.seconds);
      if (result.expired) callbackRef.current(checkpoint);
    };
    const visibility = () => {
      setHidden(document.hidden);
      tick();
    };
    visibility();
    const timer = setInterval(tick, 250);
    document.addEventListener("visibilitychange", visibility);
    return () => { clearInterval(timer); document.removeEventListener("visibilitychange", visibility); };
  }, [checkpoint.id, checkpoint.action, checkpoint.seconds]);

  useEffect(() => {
    const result = clockRef.current?.update(performance.now(), blocked || paused || document.hidden);
    if (result) {
      setRemaining(result.seconds);
      if (result.expired) callbackRef.current(checkpoint);
    }
  }, [blocked, paused]);

  return (
    <div className="d-flex flex-wrap align-items-center gap-2 mt-2" aria-label="Tutor response window">
      <Pill tone="neutral" icon="hourglass-split" title="The tutor offers a hint, then explains this step if you need more help. This is not a test deadline.">
        {blocked || paused || hidden ? "Thinking time paused" : "Time to think"} · {remaining}s
      </Pill>
      <button type="button" className="btn btn-sm btn-ghost" onClick={onPause}
        aria-label={paused ? "Resume paced tutoring" : "Pause paced tutoring"}>
        <Icon name={paused ? "play-fill" : "pause-fill"} className="me-1" />
        {paused ? "Resume" : "Pause"}
      </button>
    </div>
  );
}
