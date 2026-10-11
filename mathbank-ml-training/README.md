# mathbank-ml-training

Offline feature/label building and model training for MathBank's IntelliTutor learning-
intelligence platform. See
[documentation/requirements/54_ML_RL_PLATFORM_ARCHITECTURE_AND_SCAFFOLDING.md](../documentation/requirements/54_ML_RL_PLATFORM_ARCHITECTURE_AND_SCAFFOLDING.md)
and
[documentation/requirements/55_ML_TRAINING_PIPELINE_REQUIREMENTS.md](../documentation/requirements/55_ML_TRAINING_PIPELINE_REQUIREMENTS.md)
for the full requirements and status.

**Status: scaffolded, not implemented, not tested.** Every module under `src/` has
real type signatures, docstrings, and `# TODO:` markers citing the exact design-doc
section it implements — but no training, no feature computation, and no dataset has
actually been built yet. See requirements/54 §6 for the authoritative done/partial/
not-started table.

## Why this project exists

This is the "ML environment / SageMaker / Jupyter" half of the platform the request
described: the place mastery/recommendation/tutor-policy models get *trained*, kept
deliberately separate from `mathbank-ml-inference` (which only ever *serves* an
already-trained model) and from `mathbank-ml-frontend` (which only ever *displays*
results).

## Getting started (once real logic exists — not yet)

```bash
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -e ".[dev]"
cp .env.example .env   # fill in read-only Postgres/Neo4j credentials
jupyter notebook notebooks/
```

## Folder guide

| Folder | Purpose |
|---|---|
| `notebooks/` | Thin, numbered, SageMaker-style orchestration notebooks — each one calls into `src/mathbank_ml_training/*`, no real logic lives in the notebook itself (requirements/54 §4) |
| `src/mathbank_ml_training/extract/` | Point-in-time-safe reads from Postgres/Neo4j (requirements/55 §2 EXTRACT stage) |
| `src/mathbank_ml_training/features/` | Feature groups (requirements/55 §4) |
| `src/mathbank_ml_training/labels/` | Label groups, leakage-aware (requirements/55 §5) |
| `src/mathbank_ml_training/datasets/` | Manifests + time/student splits (requirements/55 §7) |
| `src/mathbank_ml_training/models/` | One module per model family (requirements/55 §6) — every `train()` currently raises `NotImplementedError` |
| `src/mathbank_ml_training/evaluation/` | Calibration, offline policy evaluation, leakage checks |
| `src/mathbank_ml_training/registry/` | Writes to `ml.training_run`/`ml.model_registry` |
| `src/mathbank_ml_training/sagemaker/` | Thin wrappers to run the same code as SageMaker Processing/Training jobs (requirements/54 §4, phases 1-3) |
| `src/mathbank_ml_training/jobs/` | Scheduled reindexing/feature-refresh jobs (requirements/57) — reuses this same package's `extract`/`features` code |

## Explicit non-goals (this pass)

- No model is trained.
- No AWS/SageMaker resource is created — `sagemaker/*.py` are local-runnable-shaped stubs.
- No automated test suite — `tests/` has placeholder files only, per the "scaffold, don't
  test yet" instruction.
