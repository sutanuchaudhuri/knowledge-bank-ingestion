---
name: mathbank-geometry-engine
description: 'Working in mathbank-geometry-engine: the deterministic geometry scene engine (Frame/MathState/SceneState/VisualState, bounded solver, SVG renderer). Use when editing src/geometry_scene/ or asked about scene/relation/frame semantics.'
argument-hint: 'Optional: module (api, service, repository, schemas, orchestration) to focus on'
---

# mathbank-geometry-engine conventions

Full detail: [mathbank-geometry-engine/README.md](../../../mathbank-geometry-engine/README.md).
(Renamed from `geometry-scene-engine` for naming consistency with the rest of this repo.)

## Non-negotiables

- **Not** a general-purpose theorem prover, and does not interpret arbitrary prose — the typed
  schema (`SceneInput`/`StateDelta`/`Frame`) is the only accepted input shape.
- `PROVEN`/`DISPROVEN` relation status can only be authorized through the theorem registry plus
  trusted evidence gates — never from model prose, numeric agreement alone, or a raw learner
  mutation. Don't weaken this to make a feature "just work."
- The bounded solver has hard limits (400 evaluations, `1e-6` residual tolerance, 64 objects / 128
  relations / 256 entities / 32 overlays) — these are deliberate safety bounds, not arbitrary
  tuning knobs to raise without understanding why they're there.
- SVG is served privately (`no-store`, restrictive CSP) — don't relax this when adding a new
  consumer without re-reading why in the README.
- Existing points stay fixed across deltas; a seed/mode/minimum-angle change requires an explicit
  `relayout=True` — it never happens implicitly.

## Before changing anything

1. `make test` (8 test files) and `make lint` (Ruff + mypy) must stay green.
2. `make gallery` regenerates the fixture SVG/state gallery — regenerate and visually spot-check it
   after any renderer/layout change.
3. `mathbank-neural-geometry` depends on this project (`mathbank-geometry-engine>=0.1.0,<0.2` in its
   `pyproject.toml`) — a breaking API change here needs a coordinated update there, not just a
   version bump.
