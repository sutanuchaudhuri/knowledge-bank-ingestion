# 06 — Feedback and Misconception Evidence

## Error is evidence, not diagnosis

Pipeline:

```text
action
-> semantic event
-> evaluation
-> error signature
-> evidence rule
-> confidence update
-> optional probe
-> confirmation threshold
-> fixed remediation
-> retry
```

## Suggested learner misconception states

```text
UNOBSERVED
SUSPECTED
PROBED
CONFIRMED
REMEDIATING
RESOLVED
RECURRED
```

Learner state stays in PostgreSQL.

## Default evidence weights

Example defaults:

```text
observed structural error      +0.30
repeat same signature          +0.15
failed diagnostic probe        +0.45
successful remediation probe   -0.40
correct transfer item          -0.35
transfer failure               +0.35
```

Clamp to [0,1].

Suggested defaults:

```text
<0.35       insufficient
0.35-0.64   suspected
0.65-0.79   probe
>=0.80      confirmed
```

Allow misconception-specific overrides.

## Markov example

Learner transition row:

```text
0.3, 0.4, 0.5
```

Error:

```text
ROW_SUM_INVALID
```

Evidence:

```text
MC-M05 +0.35
```

Feedback:

> Check whether the probabilities leaving state A account for all possible next states.

Do not immediately claim a misconception.

If repeated:
- focused feedback
- fixed diagnostic item
- evidence update
- fixed intervention only after threshold

## Vieta example

Learner uses wrong sign pattern:

```text
x³ + e1 x² + e2 x + e3
```

Signature:

```text
VIETA_ALTERNATING_SIGN_ERROR
```

Candidate:

```text
VIETA-M01
```

Probe:

> Expand `(x-r)(x-s)`. What sign appears on `(r+s)x`?

## Jensen example

Learner reverses convex Jensen.

Signature:

```text
JENSEN_CONVEX_DIRECTION_REVERSED
```

Candidate:
`MIS-JENSEN-01`

Remediation:
- approved chord animation
- fixed probe
- retry original task

## Feedback ladder

Default:

1. neutral structural clue
2. focused conceptual clue
3. diagnostic probe
4. confirmed misconception
5. fixed remediation
6. retry original interaction
7. later transfer verification

## Corrective animations are part of feedback

Example `MC-M09`:
student believes `P²` means squaring entries.

Run:
`ANIM_TWO_STEP_PATH_EXPANSION`

Show all intermediate states and derive:

```text
(P²)_AC = Σ_j P_Aj P_jC
```

## Prerequisite gap is separate

If learner understands Markov transitions but fails matrix multiplication:

```text
PREREQUISITE_GAP ALG_MATRIX
```

Do not mislabel as a Markov misconception.

## Agent boundary

LLM may rephrase an approved feedback item only when the template explicitly permits it.
It cannot:
- invent evidence
- change threshold
- invent misconception
- skip a required diagnostic
- choose unapproved intervention
