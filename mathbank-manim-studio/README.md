# mathbank-manim-studio

Two long-running agents over the SceneSpec contract (doc 41 ITL-4), built as a standalone
FastAPI service with a Postgres-backed job queue:

1. **Research agent** — topic (+ optional context) → a real, grounded SceneSpec JSON plus
   a short explanation. Uses an OpenAI tool-calling loop against
   [mathbank-mcp-competitions](../mathbank-mcp-competitions) (doc 49) over a real MCP
   stdio connection, so a generated scene is grounded in real corpus data, not invented.
2. **Video creator agent** — a validated SceneSpec JSON → a real, rendered `.mp4`, via a
   deterministic SceneSpec → Manim Python compiler and a genuine `manim` subprocess
   render (not a mock/stub).

Both job types are explicitly **ephemeral**: Postgres rows (schema `studio`, migration
`mathbank-db/sql/044_manim_studio_jobs.sql`) expire 1 day after creation; a cleanup script
deletes expired rows and their stored videos. See
[documentation/requirements/60_MANIM_VIDEO_STUDIO_RESEARCH_AND_RENDER_AGENTS.md](../documentation/requirements/60_MANIM_VIDEO_STUDIO_RESEARCH_AND_RENDER_AGENTS.md)
for the full design and scope rationale.

A deliberate exception to "ephemeral": a `DONE` render job can be **promoted** into the
permanent `visual.scene_spec` catalog (doc 41 ITL-1/ITL-4) by `mathbank-rest`'s admin
review workflow (doc 60 §7) — this service exposes `GET /v1/render-jobs` (list/filter,
e.g. `?status=DONE&unpromoted_only=true`) and `POST /v1/render-jobs/{id}/mark-promoted`
(admin-key-gated) so that workflow can discover candidates and record the outcome,
without ever reading `studio.*` tables from another service directly.

**Status: fully implemented and live-tested.** 26/26 tests passing, including a genuine
end-to-end round trip (research job → render job → downloadable `.mp4`) against the live
Neon Postgres instance, a real OpenAI call, a real MCP subprocess, and a real `manim`
render — not scaffolded, not mocked. The catalog-promotion workflow this README
previously listed as a deliberate non-goal is now also implemented and live-verified —
see doc 60 §7 and [mathbank-rest](../mathbank-rest)'s
`src/mathbank_rest/scene_spec_promotion.py`.

## Architecture

```text
POST /v1/research-jobs {topic, context}
        │
        ▼
studio.scene_research_job (PENDING) ──▶ worker polls, claims (FOR UPDATE SKIP LOCKED)
        │                                        │
        │                                        ▼
        │                          research_agent.py: OpenAI tool-calling loop
        │                          against mathbank-mcp-competitions (MCP/stdio)
        │                                        │
        ▼                                        ▼
GET /v1/research-jobs/{id}  ◀── DONE: result_scene_spec + result_explanation

POST /v1/render-jobs {research_job_id} or {scene_spec_json}
        │
        ▼
studio.video_render_job (PENDING) ──▶ worker polls, claims
        │                                        │
        │                                        ▼
        │                          manim_compiler.py: SceneSpec → Manim Python source
        │                          → real `manim` subprocess render → object_store
        ▼                                        │
GET /v1/render-jobs/{id}    ◀── DONE: video_object_key + video_duration_ms
GET /v1/render-jobs/{id}/video ◀── streams the real .mp4
```

## Getting started

```bash
make install   # installs fastapi/manim/fastmcp/openai into .venv (manim needs system
               # ffmpeg + cairo + pango + a LaTeX distribution — already present here;
               # see https://docs.manim.community/en/stable/installation.html otherwise)
cp .env.example .env   # fill in postgres_* from ../mathbank-rest/.env, openai_api_key
                       # from the repository root .env
make test      # 26 pass (~45s; makes one real OpenAI call + two real manim renders)
make start     # http://localhost:8020
```

Apply migration 044 once against your Postgres instance before running:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f ../mathbank-db/sql/044_manim_studio_jobs.sql
```

### Try it live

```bash
curl -s -X POST localhost:8020/v1/research-jobs \
  -H 'content-type: application/json' \
  -d '{"topic": "Jensen'"'"'s inequality for a convex function"}' | jq

# poll .../research-jobs/{id} until status is DONE, then:
curl -s -X POST localhost:8020/v1/render-jobs \
  -H 'content-type: application/json' -d '{"research_job_id": "<id>"}' | jq

# poll .../render-jobs/{id} until DONE, then:
curl -s localhost:8020/v1/render-jobs/<id>/video -o explainer.mp4
```

## SceneSpec v1 vocabulary (a real, documented subset of ITL-4)

7 object types (`TITLE_TEXT`, `TEXT`, `EQUATION`, `STATE_NODE`, `FUNCTION_GRAPH`,
`GRAPH_POINT`, `MATRIX`) and 7 actions (`SHOW`, `HIDE`, `WRITE`, `HIGHLIGHT`,
`DRAW_TRANSITION`, `EQUATION_MORPH`, `WAIT`) — see
`src/mathbank_manim_studio/scene_spec_validation.py` for the exact required fields per
type/action, and requirements/60 §3 for the full table. Extending the compiler
(`manim_compiler.py`) with more of ITL-4's full 18-object/23-action vocabulary is
additive future work.

## Design notes / gotchas found while building this

- **The research agent's first attempt used `"text"` instead of `"label"`** for
  `TEXT`/`TITLE_TEXT` objects, and separately produced a `TEXT` object whose `"label"`
  contained raw `\(...\)` LaTeX delimiters (since `TEXT` renders as plain `Text(...)`, not
  `MathTex(...)`, this would silently render garbled text, not an error). Neither the
  JSON Schema (deliberately loose — `additionalProperties` unconstrained, for ITL-4's
  future vocabulary growth) nor the original semantic checks caught this. Fixed two ways:
  (1) `scene_spec_validation.py` now checks `REQUIRED_OBJECT_FIELDS`/`REQUIRED_TIMELINE_FIELDS`
  per type/action, and rejects LaTeX-looking content (`\(`, `\[`, or a bare `\word` command)
  inside `TITLE_TEXT`/`TEXT`/`STATE_NODE` labels; (2) the research agent's system prompt
  now spells out the exact field name and the TEXT-vs-EQUATION distinction explicitly,
  and a validation failure triggers an automatic one-shot repair turn instead of silently
  shipping a broken scene.
- **`FUNCTION_GRAPH.expr` must never be passed through `eval`/`exec`** even though it
  ultimately becomes a Python lambda body in generated Manim source — `manim_compiler.py`
  walks the expression's AST first and rejects anything outside a small whitelist
  (numeric literals, the name `x`, `+-*/**`, unary minus, and calls to a fixed set of
  named math functions) before the now-provably-safe text is embedded in the generated
  script. This matters because the expression ultimately comes from an LLM, which is not
  a trusted code source even when the rest of the pipeline is working correctly.
- **`subprocess.run(["manim", ...])` fails with `FileNotFoundError` unless you spawn the
  calling interpreter's own `-m manim`** (`[sys.executable, "-m", "manim", ...]`) — a bare
  `"manim"` resolves against the invoking shell's `PATH`, not the project's `.venv`,
  which silently breaks the render the moment this code is invoked from a different
  shell/process than the one `.venv` happens to be active in (e.g. from within `uvicorn`
  started by `make start`, or from a test runner using a different interpreter).
- **A `FastMCPApp`'s own README gotchas (`mathbank-mcp-competitions`'s §"Design notes")
  apply unchanged here** since this project's `mcp_corpus_client.py` just reuses that
  server's `PythonStdioTransport` spawn pattern — no new MCP-specific gotchas were found
  in this pass.
