# 08 — Generative UI Policy

## 1. FastMCP capability

FastMCP's `GenerativeUI` lets the LLM write Prefab Python at runtime.

The provider registers:
- `generate_prefab_ui`;
- `search_prefab_components`;
- a streaming renderer.

The generated code is executed in browser-side Pyodide while streaming and then validated
server-side in a Pyodide sandbox.

The documented sandbox includes the Python standard library and Prefab but not arbitrary
third-party Python packages such as NumPy, pandas or requests.

## 2. IntelliTutor default policy

Generative UI is **not** the canonical learner runtime.

Do not use it to generate at runtime:
- graded quiz UI;
- canonical course state UI;
- correctness logic;
- hint ladders;
- misconception detectors;
- required remediation;
- route topology;
- published diagrams that affect correctness.

Why:
- canonical instruction must be versioned/testable;
- LLM-written UI is dynamic;
- learner safety and assessment security require fixed contracts;
- the sandbox is intentionally limited.

## 3. Approved uses

### Internal authoring exploration

Admin:
> "Show me three possible layouts for this course dashboard."

Use Generative UI with non-sensitive draft metadata.

The generated result is a preview only.

Promotion path:

```text
Generative preview
-> human selects
-> implementation converted to fixed Prefab/SceneSpec/template
-> validation/review
-> publish
```

### Analytics visualization

Admin:
> "Visualize aggregate completion by module and difficulty."

Use de-identified/thresholded aggregate data.

### Temporary comparison visualization

Learner:
> "Can you visualize how these three public formulas compare?"

Only if:
- no grading;
- no canonical state mutation;
- no private learner evidence is exposed to generated code;
- result is clearly supplemental.

## 4. Disallowed data

Do not pass to Generative UI:
- raw learner event histories unless explicitly authorized and necessary;
- hidden answer keys;
- private misconception thresholds;
- unpublished source solution bodies;
- secrets/tokens;
- unrestricted internal URLs.

## 5. Component discovery

If Generative UI is enabled, allow the model to call `search_prefab_components` before
writing code rather than hallucinating component APIs.

For normal Copilot implementation, also inspect the installed Prefab version directly.

## 6. Promotion rule

Generated code never becomes production curriculum by copying it automatically into a
published release.

Required:

```text
generate
-> inspect
-> convert to fixed implementation
-> tests
-> accessibility
-> graph bindings if relevant
-> review
-> publish
```

## 7. Example internal generative request

Data:

```json
{
  "module_stats": [
    {"module":"State Models","completion":0.92},
    {"module":"Matrices","completion":0.71},
    {"module":"Absorption","completion":0.58}
  ]
}
```

Prompt to agent:

```text
Create a compact Prefab dashboard showing completion by module and a clear note that this
is aggregate internal analytics.
```

This is appropriate because the UI presentation may vary without changing learner
curriculum.

## 8. Production feature flag

Recommended:

```text
ENABLE_GENERATIVE_UI_ADMIN=true
ENABLE_GENERATIVE_UI_LEARNER=false
```

Treat learner enablement as a separately reviewed feature.
