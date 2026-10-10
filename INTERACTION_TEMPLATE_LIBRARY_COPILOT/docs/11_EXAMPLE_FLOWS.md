# 11 — Detailed Example Flows

## A. Jensen convexity misconception

### Authoring
1. choose `FUNCTION_GRAPH_EXPLORER_V1`
2. configure `f(x)=x^2`
3. bind existing Jensen canonical node
4. attach `MIS-JENSEN-01`
5. map `CONVEX_DIRECTION_REVERSED`
6. attach diagnostic learning item
7. attach `SCENE-JENSEN-CONVEX-CHORD`
8. attach fixed intervention
9. validate/publish

### Runtime
Learner chooses wrong direction.

```text
event
-> CONVEX_DIRECTION_REVERSED
-> +0.35 evidence
-> neutral feedback
```

Repeated:
```text
focused feedback
-> diagnostic probe
```

Probe failed:
```text
confidence >= threshold
-> fixed convex-chord remediation
-> return to original interaction
-> retry
```

Graph:

```text
CourseState -> USES_INTERACTION -> JensenInteraction
JensenInteraction -> TEACHES -> Jensen
JensenInteraction -> CAN_REVEAL -> MIS-JENSEN-01
JensenInteraction -> USES_SCENE -> ConvexChordScene
ConvexChordScene -> ADDRESSES -> MIS-JENSEN-01
```

---

## B. Vieta partial correctness

Learner computes transformed-root:
- E1 correctly
- E2 incorrectly
- E3 correctly

Return:

```text
PARTIAL
accepted = E1,E3
focus = E2
```

UI:
- retain E1/E3
- highlight E2 only
- show pairwise-symmetric-sum feedback
- do not reset

Graph:

```text
VietaInteraction -> PRACTICES -> VIETA_SYMSUM
VietaInteraction -> CAN_REVEAL -> VIETA-M01
```

---

## C. Markov transition-row misconception

Learner creates:

```text
A -> [0.3, 0.4, 0.5]
```

Evaluation:

```text
row sum = 1.2
ROW_SUM_INVALID
```

UI:
- highlight row A
- pulse graph arrows leaving A
- display row total 1.2
- display required total 1
- show TRY_AGAIN icon + text

Evidence:
`MC-M05 +0.35`.

Second same signature:
additional evidence.

Probe:
> What must mutually exclusive next-state probabilities from one current state total?

If failed:
- confirm MC-M05
- fixed row-sum intervention
- retry

Graph:

```text
InteractionInstance -> CAN_REVEAL -> MC-M05
EvidenceRule -> EVIDENCE_FOR -> MC-M05
MC-M05 -> DIAGNOSED_BY -> LearningItem
MC-M05 -> REMEDIATED_BY -> Intervention
```

---

## D. Markov prerequisite gap, not misconception

Learner understands state graph but cannot compute matrix product.

Diagnosis:

```text
PREREQUISITE_GAP ALG_MATRIX
```

Not:

```text
MC-M02
```

Course:
- launch fixed matrix prerequisite module
- return to Markov matrix state

Graph:

```text
InteractionInstance -> REQUIRES -> ALG_MATRIX
```

---

## E. Video pause to interaction

Approved video segment:
- timestamp 02:11–02:42
- explains transition rows

Graph:

```text
VideoSegment -> EXPLAINS -> PROB_MARKOV_MATRIX
VideoSegment -> CAN_LAUNCH -> MARKOV-MATRIX-01
```

Learner pauses at 02:23 and asks:
> Why do the probabilities add to 1?

Tutor:
- resolves exact approved segment
- loads approved Q&A
- may offer linked interaction

If learner opens it:
- save video state/time
- complete interaction
- return to exact timestamp
- no dynamic interaction generation

---

## F. Same SceneSpec, Web and Manim

`SCENE-VIETA-ROOTS-TO-COEFF`

Web:
- roots can be dragged
- coefficients update

Manim:
- scene plays linearly

Both expose semantic events:

```text
CONCEPT_INTRODUCED ALG_VIETA
EQUATION_DERIVED VIETA_COEFFICIENT_PATTERN
TECHNIQUE_RECOGNITION_CUE_SHOWN VIETA_SYMSUM
```

Motion differs.
Semantics do not.

---

## G. Resolved misconception recurs

1. misconception confirmed
2. learner completes remediation
3. immediate retry correct
4. transfer item correct
5. confidence falls -> RESOLVED

Later:
- same validated error
- failed probe

State -> `RECURRED`.

Canonical misconception remains unchanged.
Only learner evidence changes.
