"use client";

import { useState } from "react";
import { MathComposer, SpeakButton, WidgetHost } from "mathbank-widgets";
import MathText from "../../../_components/MathText.jsx";

const renderMath = (t) => <MathText>{t}</MathText>;

export default function WidgetGallery({ registry, samples }) {
  const [text, setText] = useState("");
  return (
    <div className="row g-4">
      <div className="col-12 col-xl-8">
        <div className="row g-3" data-testid="widget-gallery">
          {samples.map((s) => (
            <div key={s.intent} className="col-12 col-md-6">
              <div className="small text-secondary mb-1">
                intent “{s.intent}” · {s.valid ? <span className="text-success">valid</span> : <span className="text-danger">invalid: {s.errors.join("; ")}</span>}
              </div>
              <WidgetHost spec={s.spec} renderMath={renderMath} />
            </div>
          ))}
        </div>
      </div>
      <div className="col-12 col-xl-4">
        <div className="card shadow-sm mb-3">
          <div className="card-header bg-white fw-semibold">Input add-ons playground</div>
          <div className="card-body">
            <MathComposer value={text} onChange={setText} renderMath={renderMath} testId="playground-composer"
              ariaLabel="Playground input" placeholder="Try: angle ABC = 90 deg and PA*PB = PT^2" />
            <div className="d-flex align-items-center gap-2 mt-3">
              <SpeakButton text={text || "Power of a point: P A times P B equals P T squared."} label="Read aloud" />
              <span className="small text-secondary">Reads the text above aloud (ElevenLabs, server-side key).</span>
            </div>
          </div>
        </div>
        <div className="card shadow-sm">
          <div className="card-header bg-white fw-semibold">Registry ({registry.length} widget types)</div>
          <ul className="list-group list-group-flush small">
            {registry.map((w) => (
              <li key={w.widget_type} className="list-group-item"><code>{w.widget_type}</code> — {w.label}
                <div className="text-secondary">config: {w.config_keys.join(", ")}</div></li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
