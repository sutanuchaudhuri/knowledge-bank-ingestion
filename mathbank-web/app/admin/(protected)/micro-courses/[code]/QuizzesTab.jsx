"use client";

import { Callout, EmptyState, Icon, Pill, SectionTitle } from "../../../../_components/ui.jsx";

/** Per-state quiz question list. Creating a new activity.definition row has no REST
 * endpoint yet — like visual.interaction_instance, these are statically authored content
 * (today via the seed scripts, e.g. scripts/seed_reference_course_extras.py), not a
 * generic admin-authoring surface. "Draft with AI" is flagged, not faked. */
export default function QuizzesTab({ release }) {
  if (!release) return <EmptyState icon="patch-question">Create a draft release first (see the Versions tab).</EmptyState>;

  const quizStates = release.states.filter(state => (state.activities || []).length > 0
    || ["QUIZ", "CHECKPOINT", "DIAGNOSTIC"].includes(state.state_type));

  return (
    <div>
      <Callout tone="hint" className="mb-3">
        <Icon name="robot" /> <strong>Authoring new quiz questions from this tab, and "Draft
        with AI," are not yet available.</strong> Quiz questions (<code>activity.definition</code>)
        are currently authored through content scripts, the same way approved interaction
        instances are — see requirements/43 §3.2.4 and §7.1 for the planned flow and the
        open answer-exposure issue it depends on.
      </Callout>

      {!quizStates.length ? (
        <EmptyState icon="patch-question">No quiz states in this release yet.</EmptyState>
      ) : (
        quizStates.map(state => (
          <div key={state.state_id} className="card border-0 shadow-sm p-3 mb-3">
            <SectionTitle icon="patch-question">{state.title} <Pill tone="neutral" className="ms-2">{state.state_type}</Pill></SectionTitle>
            {!state.activities?.length ? (
              <p className="text-secondary small mb-0">No questions attached to this state.</p>
            ) : (
              <ul className="list-group list-group-flush">
                {state.activities.map(activity => (
                  <li key={activity.activity_id} className="list-group-item">
                    <div className="d-flex justify-content-between gap-2">
                      <strong>{activity.prompt}</strong>
                      <Pill tone="info">{activity.activity_type}</Pill>
                    </div>
                    {Array.isArray(activity.options) && activity.options.length > 0 && (
                      <ul className="small text-secondary mt-1 mb-0">
                        {activity.options.map((option, index) => <li key={index}>{option}</li>)}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))
      )}
    </div>
  );
}
