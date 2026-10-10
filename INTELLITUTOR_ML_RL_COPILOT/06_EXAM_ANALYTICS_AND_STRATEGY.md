# 06 — Exam Analytics and Strategy

## 1. Required outputs

For a given exam family:
- predicted score distribution
- topic-by-topic expected points
- time-loss sources
- pacing curve
- skip/revisit strategy
- recommended full-mock frequency
- recommended mock time-of-day only if data supports it
- error taxonomy
- high-value practice targets

## 2. Pacing analytics

Per full mock:

```text
question ordinal
difficulty estimate
active time
correctness
skip/revisit
answer changes
confidence
topic/technique
```

Derived:

```text
seconds per expected point
seconds per difficulty band
time lost on incorrect questions
late-section accuracy drop
questions abandoned after long investment
successful skips
productive revisits
```

## 3. Strategy examples

Possible evidence-based recommendations:

```text
"Your Q18–22 accuracy is 54% when first-pass time exceeds 6 minutes.
Cap first-pass investment at ~4 minutes and revisit."

"You gain 1.8 expected points per mock from revisiting skipped geometry questions,
but lose 0.6 expected points from changing previously-correct algebra answers."
```

Never issue such numerical claims unless sample/data sufficiency passes thresholds.

## 4. Time-of-day model

Only recommend "take mocks at 9 AM" if there is:
- multiple comparable timed sessions in different dayparts
- controlled enough difficulty
- sufficient active-time data

Features:
- local hour bucket
- day type
- sleep/energy self-report only if intentionally collected
- duration
- exam difficulty
- result

Prefer within-student comparison.

If insufficient:

```text
NO_RECOMMENDATION
reason = INSUFFICIENT_DAYPART_COVERAGE
required_data = "2–3 more full mocks in afternoon/evening"
```

## 5. Exam readiness

Separate:
- knowledge readiness
- speed readiness
- endurance readiness
- strategy readiness
- variance / reliability

A student can be mathematically strong but pacing-weak.
