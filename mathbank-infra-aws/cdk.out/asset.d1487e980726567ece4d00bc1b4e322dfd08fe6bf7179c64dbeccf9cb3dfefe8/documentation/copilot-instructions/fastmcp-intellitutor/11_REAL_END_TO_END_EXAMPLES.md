# 11 — Real End-to-End Agentic Examples

## Example A — "Teach me Markov chains"

### User
> Teach me Markov chains. Start by checking prerequisites.

### Agent action
Calls model-visible:
`open_course(canonical_code="MC-MARKOV-COMP-01")`

### App
Course opens on PRE diagnostic.

Student answers:
> Total probability formula question → correct.

UI calls:
`submit_quiz(...)`

Server:
- validates pinned release/state;
- grades;
- returns approved explanation;
- persists attempt;
- no misconception evidence if correct.

Student completes PRE.

`advance_course` returns State Modeling.

### Later
Matrix editor row A = `(0.3,0.4,0.5)`.

App emits:
`SET_TRANSITION_ROW`.

Server:
- computes sum 1.2;
- signature `ROW_SUM_INVALID`;
- adds evidence +0.35 to MC-M05;
- returns focused object IDs.

UI:
- highlights exact row;
- pulses outgoing A arrows;
- says "Row A totals 1.2."

No LLM needed.

Repeated error:
- server selects diagnostic probe.

If probe fails:
- fixed remediation launches.

## Example B — "Give me a hint, not the solution"

User is solving AMC/AIME problem in route tutor.

Agent opens:
`open_problem_tutor(problem_id=...)`

Route step:
> Express the transformed roots using symmetric sums.

Student asks:
> Hint please.

UI calls:
`request_hint(attempt_id, current_step_id)`.

Server returns H1 only:
> Start with the sum of the transformed roots.

The UI does not preload H2–H5.

Student may ask a textual question:
> Why is solving the roots directly a bad idea?

UI calls scoped tutor backend.

Tutor answer is grounded only in:
- route step;
- Vieta theory;
- current approved explanation.

## Example C — Vieta partial correctness

Task:
Given roots `a,b,c`, form polynomial whose roots are `a+b,b+c,c+a`.

Learner supplies:
- new `E1`: correct;
- new `E2`: wrong;
- new `E3`: correct.

Backend returns:

```json
{
  "outcome": "PARTIAL",
  "accepted_components": ["E1","E3"],
  "focus_components": ["E2"],
  "feedback": "Keep your sum and product. Recompute the pairwise-product sum."
}
```

UI retains correct fields and focuses E2.

## Example D — Pause YouTube and ask

Course uses an approved video with timestamped transcript.

Learner pauses at 02:23:
> Why does each row total 1?

UI calls:
`ask_current_context(video_time_ms=143000, ...)`.

Server:
- resolves transcript segment 02:11–02:42;
- resolves Markov matrix concept;
- resolves allowed interaction;
- sends scoped grounding to tutor.

Tutor may answer and offer:
`OPEN_INTERACTION MARKOV-MATRIX-01`.

If opened:
- save 02:23;
- complete interaction;
- return to 02:23.

## Example E — Student progress

User:
> How is my competition math prep going?

Agent calls:
`open_progress()`.

User sees:
- course completion chart;
- recent practice table;
- focus areas.

Model sees summary:
> 3 active courses, 84 problems completed, Markov matrix normalization and transformed-root Vieta are current focus areas.

Assistant can then say:
> Your most productive next block is Markov matrix practice followed by one transformed-root Vieta problem.

That recommendation is based on learner-owned progress and published content.

## Example F — Admin creates micro-course quiz

Admin:
> Add a four-question checkpoint after the Weighted AM-GM video.

Agent opens authoring app.

Admin form captures:
- question;
- choices;
- correct answer;
- explanation;
- target technique;
- purpose.

AI may draft candidates, but admin must approve.

Publication preflight ensures:
- answers are present server-side;
- student payload excludes them;
- canonical mappings resolve;
- state transitions remain valid.

## Example G — Admin asks for a visualization

Admin:
> Show aggregate completion by Markov module.

Internal Generative UI can build a temporary Prefab chart from aggregate data.

That generated display is not stored as canonical course UI.

## Example H — Custom geometry app

User:
> Let me drag the point and see how the ratio changes.

Agent opens a Custom HTML geometry app.

The custom renderer:
- draws the triangle;
- lets point D move;
- updates safe local values instantly.

On commit/check:
- calls server tool;
- server validates semantic construction;
- returns deterministic feedback.

The HTML does not contain grading answers or misconception thresholds.
