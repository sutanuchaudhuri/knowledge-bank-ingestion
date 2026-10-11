---
name: mathbank-neural-geometry
description: 'Working in mathbank-neural-geometry: the neural-symbolic construction-program compiler built on mathbank-geometry-engine. Use when editing src/neural_geometry/ (compiler.py, models.py, planning.py) or the nested mathbank-prasolov-dataset-audit tool.'
argument-hint: 'Optional: compiler, models, planning, or the nested prasolov-dataset-audit tool'
---

# mathbank-neural-geometry conventions

Full detail: [mathbank-neural-geometry/README.md](../../../mathbank-neural-geometry/README.md).
(Renamed from `neural-geometry-engine` for naming consistency; its old `-v1` sibling tool is now
nested here as `mathbank-prasolov-dataset-audit/`, not a separate top-level folder.)

## Non-negotiables

- Reuses `mathbank-geometry-engine`'s math state/solver/renderer/validation wholesale — never
  reimplement that logic here; this project only adds the construction-program IR, provisional
  curves, and planner/critic interfaces on top of it.
- A `ConstructionProgram` must start with exactly one `CREATE_SCENE`; no later step may reset the
  scene.
- `--trusted-facts` is a **trusted host input** — never pass unverified planner output, model
  prose, or a student's own claim as a trusted fact; `PROMOTE_CURVE` relies on this being genuinely
  trustworthy.
- No trained neural model, configured planner/critic, or REST exposure ships here yet — mock
  planner/critic roles verify orchestration only, not neural-model quality. Don't claim more
  capability than this when describing the project.

## Before changing anything

1. `make test` (3 test files: compiler/planning/traces) and `make lint` (Ruff + mypy).
2. `make install` installs the local `mathbank-geometry-engine` dependency editable
   (`-e ../mathbank-geometry-engine`) — this project is genuinely not standalone at install time,
   by design; don't try to "fix" that coupling.
3. The nested `mathbank-prasolov-dataset-audit/` tool is a separate dataset/annotation experiment,
   not part of the compiler — its preview renderer is explicitly a debug aid, not a production
   leakage-safe tutor renderer; don't promote it to one without a separate review.
