# 09 — Data Readiness and Metadata-Gap Detection

## 1. This is a first-class pipeline output

The system must not silently train on incomplete data.

Every training/inference workflow emits a readiness report.

Example:

```json
{
  "student_id": "...",
  "use_case": "TIME_OF_DAY_RECOMMENDATION",
  "status": "NOT_READY",
  "confidence": 0.18,
  "blocking_signals": [
    "ONLY_ONE_FULL_MOCK",
    "NO_AFTERNOON_SESSION"
  ],
  "recommended_data": [
    "take 2 full mocks between 1pm and 5pm",
    "record active per-question time"
  ]
}
```

## 2. Data-quality dimensions

```text
COVERAGE
RECENCY
VOLUME
BALANCE
CONSISTENCY
LABEL_QUALITY
TIMESTAMP_QUALITY
GRAPH_MAPPING
DIFFICULTY_CALIBRATION
DUPLICATION
LEAKAGE_RISK
```

## 3. Per-student readiness

Check:
- enough attempts per node
- enough transfer items
- enough timed data
- hint logging present
- exam sessions comparable
- misconception probes present
- course outcome data
- recent data

## 4. Per-content readiness

Problem:
- taxonomy resolved
- difficulty calibrated
- expected time available
- solution/review available
- source lineage
- duplicate family known
- technique mapping confidence

Course:
- target/prerequisite graph
- completion data
- post-course transfer data
- estimated duration
- interaction telemetry coverage

## 5. Metadata enrichment suggestions

The pipeline may emit:

```text
MISSING_PRIMARY_TECHNIQUE
MISSING_EXPECTED_TIME
DIFFICULTY_UNCALIBRATED
NO_TRANSFER_LABEL
NO_SOURCE_LINEAGE
NEAR_DUPLICATE_UNKNOWN
COURSE_TARGET_TOO_BROAD
ROUTE_STEP_TECHNIQUE_UNRESOLVED
VIDEO_SEGMENT_UNTAGGED
```

These become admin tasks.

## 6. Do not auto-mutate canonical metadata

ML can propose:

```json
{
  "problem_id": "...",
  "proposed_technique": "VIETA_SYMSUM",
  "confidence": 0.91,
  "evidence": [...]
}
```

But it stays a review candidate.

## 7. Feature availability matrix

Generate automatically:

| Use case | Required signals | Optional | Status |
|---|---|---|---|
| mastery | attempts/correctness/tags | hints/time | READY |
| pacing | per-question active time | confidence | READY |
| time-of-day | multiple dayparts | energy | NOT READY |
| course lift | pre/post transfer | matched control | PARTIAL |
| tutor RL | action/reward/allowed-set logs | explicit feedback | READY |

## 8. Admin "what data should improve?" page

Rank missing data by expected value:

```text
1. Add expected-time calibration to 312 AMC problems.
   Unlocks: pacing model, dynamic mock quality.

2. Add transfer labels to 5 micro-courses.
   Unlocks: course-effectiveness ranking.

3. Collect 3 more full mocks for this student.
   Unlocks: stable exam pacing/time-of-day recommendation.
```

This page is as important as the recommendations themselves.
