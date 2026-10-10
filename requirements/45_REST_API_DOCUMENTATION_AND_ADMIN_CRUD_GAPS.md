# 45. REST API documentation and admin CRUD/lookup gap analysis (planning only)

> **Explicit scope note.** This document is **analysis and a requirements/design plan only**.
> No code, schema, router, or documentation file described below has been changed as part of
> producing this document. Every finding below was verified against the live running service
> (`mathbank-rest`, `http://localhost:8000/openapi.json`, 268 operations across 256 paths at the
> time of writing) and the real router/db source, not guessed. Implementation is tracked as
> future work (see §12) and must be picked up explicitly, task by task.

## 0. Status and scope

| | |
|---|---|
| Status | **Planning only.** Not implemented. |
| Trigger | Admin-facing complaint: Swagger documentation is thin, several taxonomy admin operations (strategy/technique lookup, updating a skill's description, adding an alias) don't exist as REST endpoints, APIs aren't grouped sensibly, and fields that have a bounded set of valid values are documented as free text instead of pointing at an enum or a lookup endpoint. |
| Grounding | Live `GET /openapi.json` (268 ops), every router file under [mathbank-rest/src/mathbank_rest/routers/](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-rest/src/mathbank_rest/routers), the taxonomy schema in [001_schema.sql](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-db/sql/001_schema.sql) and [006_pedagogy.sql](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-db/sql/006_pedagogy.sql), and the governance workflow in [pedagogy_admin.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py). |
| Terminology note | The admin ask used the word **"strategies."** There is no `strategy` table or concept anywhere in the schema or code. The closest, and almost certainly intended, entity is `knowledge.technique` — competition problem-solving techniques (e.g. "Pigeonhole", "AM-GM") are colloquially called "strategies" in math-olympiad teaching. This document treats **strategy = technique** throughout and flags the assumption here for correction if wrong. |

## 1. Why this document exists — the concrete evidence

Four independent, separately-verified gap categories. Each one is cited with the exact file,
line, or live response that proves it — not inferred from a README.

### 1.1 Taxonomy entities have almost no admin CRUD surface

| Entity | Table | List (GET) | Create | Update (e.g. description) | Alias / synonym | Activate / deactivate |
|---|---|---|---|---|---|---|
| Concept | `knowledge.concept` | ✅ `GET /v1/concepts` (read-only, public) | ❌ none | ❌ none | ❌ no column/table exists | ❌ `status` column exists (`DEFAULT 'ACTIVE'`, **no CHECK constraint**, unused by any query) |
| Technique ("strategy") | `knowledge.technique` | ✅ `GET /v1/techniques` (read-only, public) | ❌ none | ❌ none | ❌ no column/table exists | ❌ same unused `status` column |
| Skill | `knowledge.skill` | ❌ **no listing endpoint at all** — only `GET /v1/admin/pedagogy/queue?kind=skill`, which is the PENDING-review governance queue, not a browse/search surface | ⚠️ indirectly, only via automatic enrichment pipelines | ⚠️ only via the generic revision-gated `POST /v1/admin/pedagogy/edit` governance workflow (see §1.2) — no plain "update description" call | ❌ no column/table exists | ❌ `review_status` is `PENDING/REVIEWED/REJECTED` only — there is no `ACTIVE/INACTIVE` lifecycle concept for skills at all |
| Misconception | `knowledge.misconception` | ❌ no admin listing endpoint. The only read path is `search_canonical_targets(target_type="MISCONCEPTION", ...)` inside `micro_course_service.py`, which is scoped to micro-course authoring and hard-filters `review_status='APPROVED'` | ❌ none | ❌ none | ❌ no column/table exists | ❌ `review_status` only (`PENDING_REVIEW/APPROVED/REJECTED`), no post-approval deactivate |

Evidence: `grep -rln "misconception" mathbank-rest/src/mathbank_rest/routers/*.py` returns
**zero files** — confirmed live, not from memory.

### 1.2 The one governance workflow that *does* exist doesn't cover the base entities

[pedagogy_admin.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-rest/src/mathbank_rest/routers/pedagogy_admin.py)
implements a real, well-designed revision-gated review/edit/publish workflow (`/v1/admin/pedagogy/{queue,review,edit,publish,bulk-review}`)
with an explicit `Kind` enum:

```python
Kind = Literal[
    "skill", "skill_concept", "skill_relation", "concept_relation",
    "problem_skill", "problem_pedagogy", "problem_concept", "problem_technique",
]
```

`"skill"` is covered (so a skill's `review_status` can be changed and its fields edited through
`POST /edit`, in theory) — but **`"concept"`, `"technique"`, and `"misconception"` are absent**
from `Kind`. There is no code path, anywhere, that lets an admin change a concept's or
technique's `name`/`description`/`status` through this workflow or any other REST call. The only
way today is a raw SQL `UPDATE` run outside the application.

### 1.3 Swagger/OpenAPI documentation is thin and inconsistent

Pulled live from `GET /openapi.json` (268 operations, 256 paths):

- **No app-level description.** `FastAPI(title="mathbank-rest", version="0.1.0")` in
  [main.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-rest/src/mathbank_rest/main.py)
  sets no `description`, no `summary`, and registers no `openapi_tags` metadata — so every tag
  section header in Swagger UI (`/docs`) has a bare name and no explanation of what it covers,
  who can call it, or what auth it needs.
- **205 of 268 operations (76%) have no `description`.** FastAPI derives `description` from the
  handler's docstring; most handlers have none, so the expanded view in Swagger UI shows only an
  auto-titled operation with a parameter list and nothing else.
- **15 operations carry no `tags` at all** and fall into Swagger UI's unlabeled "default" bucket,
  including the single most important public read surface in the whole API:
  `GET /v1/concepts`, `GET /v1/techniques`, `GET /v1/problems`, `GET /v1/competitions`,
  `POST /v1/search/concepts`, `POST /v1/search/problems`, `GET /v1/corpus/coverage`,
  `GET /v1/analytics/weak-concepts`, plus the three `/health*` endpoints. ([v1.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-rest/src/mathbank_rest/routers/v1.py)
  declares `APIRouter(prefix="/v1")` with no `tags=`.)
- **Tag naming has three incompatible conventions in the same spec**, so alphabetical sorting in
  Swagger UI doesn't even group every admin-only router together:
  - hyphenated: `admin-corpus`, `admin-imports`, `admin-textbooks`
  - space-separated: `admin pedagogy`, `admin micro-courses`
  - bare feature name with no "admin" marker even though the whole router is admin-gated:
    `admin` (itself inconsistent — the tag is literally `"admin"`, not `"admin-competitions"`)
  - public/student routers mixed in alphabetically next to admin ones: `agent-sessions`,
    `artifacts`, `fluid-widgets`, `learner`, `live-sessions`, `micro-courses`, `pedagogy`, `tutor`

### 1.4 The admin auth scheme is invisible to Swagger UI and misdocumented as optional

`require_admin_api_key` in
[security.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-rest/src/mathbank_rest/security.py)
reads the key with a plain FastAPI `Header(default=None)` parameter, not
`fastapi.security.APIKeyHeader`. Confirmed live from `/openapi.json` for
`GET /v1/admin/micro-courses`:

```json
{
  "name": "x-admin-api-key",
  "in": "header",
  "required": false,
  "schema": {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "X-Admin-Api-Key"}
}
```

Two concrete problems:

1. **It says `"required": false`.** In reality the dependency raises 401 if the header is
   missing or wrong. The published contract is actively wrong, not just incomplete.
2. **It is not a registered OpenAPI `securityScheme`.** `components.securitySchemes` only
   contains `HTTPBearer` (the student JWT). Swagger UI therefore has **no padlock icon on any of
   the ~90 admin-gated operations**, and no "Authorize" button that would let someone paste the
   key once and have it applied to every `Try it out` call — they must type the header into every
   single operation by hand.

### 1.5 Enumerated-value fields are documented as free text instead of real enums

Two confirmed patterns, cited by file and line:

- [admin.py:49](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-rest/src/mathbank_rest/routers/admin.py):
  `source_kind: str = Field(default="PDF", description="PDF | HTML")` — a human-readable
  pipe-separated string instead of `Literal["PDF", "HTML"]`. The *code* already enforces this set
  at runtime (`SOURCE_KINDS = {"PDF", "HTML"}`, checked manually and raising 422) — the type
  system and the OpenAPI schema simply don't say so, so Swagger UI renders a free-text box
  instead of a dropdown, and no client library can generate a proper enum type from the spec.
- [admin.py:101](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-rest/src/mathbank_rest/routers/admin.py):
  `status: str | None = Query(default=None, description="PENDING | DOWNLOADED | PARSED | INGESTED | FAILED")`
  — same anti-pattern on a query parameter.
- `RecordInteractionEvent.event_type` (added this session, in
  [micro_courses.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-rest/src/mathbank_rest/routers/micro_courses.py))
  and `StateBinding.role` are plain length-bounded strings with **no enum and no description
  pointing anywhere** — a new admin author has no way to discover the valid set except reading
  the Python source.
- `knowledge.concept.status` and `knowledge.technique.status` are `text NOT NULL DEFAULT 'ACTIVE'`
  with **no CHECK constraint at all** — the "valid values" are an unenforced convention, not even
  a database-level enum, so there is nothing for an API layer to introspect even if it wanted to.

### 1.6 A good pattern already exists in this codebase — it just isn't generalized

This session's own micro-course work ([doc 40](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/40_MICRO_COURSE_PLATFORM.md),
[doc 43](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/43_ADMIN_MICRO_COURSE_AUTHORING_UI.md))
already solved exactly this class of problem, twice, and both are the right template to copy
elsewhere instead of re-inventing:

- **Lookup-over-free-text**: `GET /v1/admin/micro-courses/targets?target_type=CONCEPT|TECHNIQUE|SKILL|MISCONCEPTION&q=`
  lets an author search the real canonical entities instead of typing a slug from memory, and
  `target_type` itself is a real `Literal`, not a described string.
  `GET /v1/admin/micro-courses/templates` enumerates the real widget/control/icon/animation
  catalog the same way.
- **Activate/deactivate with audit**: migration 035 added `is_active` /
  `deactivated_at` / `deactivated_by` to `pedagogy.micro_course`, plus
  `POST /{code}/deactivate` and `POST /{code}/reactivate`, each writing one
  `audit.action_log` row (`record_audit_event`). This is a complete, tested, reusable template for
  "give an existing ACTIVE-by-default entity a real deactivate/reactivate lifecycle with an
  audit trail" — concept, technique, skill, and misconception all currently lack this.

## 2. Full router/tag inventory (ground truth, not illustrative)

| Router file | URL prefix | Tag(s) | Ops | Gaps noted |
|---|---|---|---|---|
| `v1.py` | `/v1` | *(none)* | 13 | No tags at all (§1.3); the only read surface for concepts/techniques, no CRUD (§1.1) |
| `admin.py` | `/v1/admin` | `admin` | 7 | Free-text enum anti-pattern (§1.5); tag name not distinguishable from other "admin*" tags |
| `admin_corpus.py` | `/v1/admin/corpus` | `admin-corpus` | 9 | — |
| `admin_imports.py` | `/v1/admin/imports` | `admin-imports` | 15 | — |
| `admin_textbooks.py` | `/v1/admin/textbooks` | `admin-textbooks` | 7 | — |
| `agent_sessions.py` | `/v1` | `agent-sessions` | 5 | — |
| `artifacts.py` | `/v1/artifacts` | `artifacts` | 20 | — |
| `attempt_media.py` | `/v1/attempt-media` | `multimodal-attempts` | 20 | — |
| `fluid.py` | `/v1` | `fluid-widgets` | 22 | — |
| `geometry_interpretation.py` | `/v1/geometry-scenes` | `geometry-agent` | 1 | — |
| `geometry_scenes.py` | *(none)* | *(none)* | 10 | No prefix/tags declared at the router level |
| `interaction_templates.py` | `/v1/admin/interaction-templates` | `interaction-templates` | 8 | Admin-gated but tag doesn't say "admin" |
| `learner.py` | `/v1/learner` | `learner` | 8 | — |
| `live.py` | `/v1` | `live-sessions` | 28 | — |
| `micro_courses.py` (admin) | `/v1/admin/micro-courses` | `admin micro-courses` | 22 | Space in tag name (inconsistent with hyphenated siblings) |
| `micro_courses.py` (student) | `/v1/micro-courses` | `micro-courses` | 9 | — |
| `pedagogy.py` | `/v1/tutor` | `pedagogy` | 10 | — |
| `pedagogy_admin.py` | `/v1/admin/pedagogy` | `admin pedagogy` | 11 | Space in tag name; `Kind` enum missing base entities (§1.2) |
| `step_runtime.py` | `/v1` | `step-runtime` | 30 | — |
| `tutor.py` | `/v1/tutor` | `tutor` | 2 | Shares `/v1/tutor` prefix with `pedagogy.py` but a different tag — same URL family, two tag names |
| `tutoring_routes.py` | `/v1` | `tutoring-routes` | 9 | — |

Totals verified live: 268 operations, 256 paths, 21 routers (including the two halves of
`micro_courses.py`).

## 3. Proposed fix — API grouping and OpenAPI metadata

Not implemented. Proposed shape, for a follow-up task:

1. **One tag-naming convention.** All tags hyphenated, lower-case, and every admin-only router's
   tag prefixed `admin-` (so `admin`, `admin pedagogy`, `admin micro-courses`,
   `interaction-templates` become `admin-competitions`/`admin-papers` (or split further, see §9),
   `admin-pedagogy`, `admin-micro-courses`, `admin-interaction-templates`).
2. **Register `openapi_tags` on the `FastAPI(...)` app** with a one-line description per tag,
   stating in the description itself which auth scheme applies (admin key vs. learner JWT vs.
   anonymous) — this is visible directly in Swagger UI's section header, no separate doc needed.
3. **Set `app = FastAPI(title=..., description=..., version=..., summary=...)`** with a short
   paragraph: what this API is, the two auth schemes and where to get each, and a link to
   `requirements/reference/REST_API.md` for the prose reference.
4. **Register the admin key as a real OpenAPI security scheme** (`APIKeyHeader(name="X-Admin-Api-Key")`
   wired through `Security(...)` instead of a bare `Header(...)` parameter) so: (a) every admin
   operation gets a padlock icon, (b) Swagger UI's global "Authorize" button lets a user paste the
   key once, (c) the spec correctly reports the parameter as required, not optional.
5. **Add a one-line docstring to every handler that doesn't have one**, focused on *why*/*when*,
   not restating the path — FastAPI already surfaces docstrings as `description` for free; this is
   pure backfill, not new machinery.
6. Give `v1.py` and `geometry_scenes.py` explicit tags (today they have none) and split
   `v1.py`'s mixed concerns (competitions/problems/concepts/techniques/search/analytics) across
   tags that match their actual audience, rather than one undifferentiated tag for all 13 ops.

## 4. Proposed fix — enumerated-value documentation standard

Two complementary mechanisms, to be applied consistently everywhere a field has a bounded value
set, not just in new code:

1. **If the set is small, fixed, and known at code-authoring time** (e.g. `source_kind`,
   `review_status`, `relation_type`, `role`): the field **must** be a `Literal[...]` (or a reused
   named Python/Pydantic enum), never a `str` with the valid values only spelled out in English in
   `description=`. This makes Swagger UI render a dropdown and makes every generated client type
   the field correctly. The `Kind`/`Status` literals in `pedagogy_admin.py` and the
   `target_type`/`state_type`/`transition_type` literals in `micro_courses.py` (this session) are
   the two good examples already in the codebase to copy verbatim as the pattern.
2. **If the set is large, data-dependent, or grows over time** (e.g. "which concept slugs exist,"
   "which techniques exist," "which widget templates exist"): the field's OpenAPI `description`
   **must** name the exact lookup endpoint to call first (e.g. `"One of the slugs returned by GET
   /v1/concepts"`), and ideally that lookup endpoint should support a `q=` search param so an admin
   UI can offer a type-ahead instead of requiring the operator to already know the value. The
   micro-course `/targets` and `/templates` endpoints (§1.6) are the existing, already-shipped
   example of this exact pattern — this document proposes generalizing it, not inventing it.
3. Concretely fix the two confirmed violations from §1.5 (`source_kind`, papers `status=`) as part
   of the same pass that adds the new taxonomy lookup endpoints (§5), since they're small,
   contained changes with no schema impact.

## 5. Proposed fix — taxonomy admin CRUD endpoints (concept / technique / skill / misconception)

All of the following are **new, additive REST endpoints** under a consistent
`/v1/admin/taxonomy/{concepts|techniques|skills|misconceptions}` prefix (proposed; see §9 for the
full table), reusing the already-proven patterns from doc 43/micro-courses (audit logging,
revision-gated optimistic concurrency, activate/deactivate) rather than inventing new ones. No
endpoint here removes or replaces anything that exists today.

### 5.1 List / search (closes the "no `GET /v1/skills`, no misconception listing" gap)

```
GET /v1/admin/taxonomy/concepts?q=&status=ACTIVE|INACTIVE|ALL&limit=&offset=
GET /v1/admin/taxonomy/techniques?q=&status=ACTIVE|INACTIVE|ALL&limit=&offset=
GET /v1/admin/taxonomy/skills?q=&review_status=PENDING|REVIEWED|REJECTED|ALL&limit=&offset=
GET /v1/admin/taxonomy/misconceptions?q=&review_status=PENDING_REVIEW|APPROVED|REJECTED|ALL&limit=&offset=
```

Each returns `slug`/`canonical_code`, `name`, `description` (or `objective` for skills),
`status`/`review_status`, `aliases` (§5.3), and problem/usage counts — admin-only, a superset of
what the existing public `GET /v1/concepts`/`GET /v1/techniques` expose, and the first-ever
listing surface for skills and misconceptions.

### 5.2 Update description/name (closes "update description" / generic edit gap)

Two options, to be decided in implementation (not this document):

- **(a) Extend `pedagogy_admin.py`'s existing `Kind` literal** to include `"concept"`,
  `"technique"`, and `"misconception"`, and extend its `db.edit`/`db.decide` implementations to
  know how to look up/mutate those tables by slug/canonical_code. Reuses the existing
  revision-gated (`expected_revision` sha256) optimistic-concurrency + review-note pattern as-is.
- **(b) A dedicated, simpler `PATCH /v1/admin/taxonomy/{kind}/{slug}` endpoint** (name,
  description/objective, level) with a plain `expected_updated_at`/row-version check, for entities
  that don't need the full PENDING/REVIEWED/REJECTED governance ceremony (concept/technique are
  already `status='ACTIVE'` by default with no review queue today — forcing them through the
  PENDING-review workflow would be a behavior change beyond "add an update endpoint").

This document recommends **(b)** for concept/technique (lighter weight, matches their current
unreviewed nature) and **(a)** for skill/misconception (they already have a review-status
lifecycle; reuse it rather than adding a second).

### 5.3 Alias / synonym support (closes "add an alias for a skill" — currently impossible)

No alias table or column exists anywhere in the schema today. Proposed new table, additive only:

```sql
CREATE TABLE knowledge.entity_alias (
    alias_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_kind text NOT NULL CHECK (entity_kind IN ('CONCEPT','TECHNIQUE','SKILL','MISCONCEPTION')),
    entity_id   uuid NOT NULL,       -- concept_id / technique_id / skill_id / misconception_id
    alias       text NOT NULL CHECK (btrim(alias) <> ''),
    created_at  timestamptz NOT NULL DEFAULT now(),
    created_by  text,
    UNIQUE (entity_kind, entity_id, alias)
);
```

One shared table (not four per-entity alias tables) keeps the add/remove/list endpoints and the
search-by-alias query identical across all four kinds:

```
GET    /v1/admin/taxonomy/{kind}/{slug}/aliases
POST   /v1/admin/taxonomy/{kind}/{slug}/aliases          {"alias": "AM-GM"}
DELETE /v1/admin/taxonomy/{kind}/{slug}/aliases/{alias_id}
```

And the existing public/admin search endpoints (`GET /v1/concepts`, `GET /v1/techniques`, the new
`GET /v1/admin/taxonomy/*`, and the micro-course `/targets` search) would all extend their `q=`
matching to also check `knowledge.entity_alias.alias ILIKE`, so a search for "AM-GM" finds the
technique canonically named "Arithmetic Mean–Geometric Mean Inequality" without the admin needing
to already know the canonical name.

### 5.4 Activate / deactivate (generalizing the migration-035 pattern)

For concept/technique, this is mostly wiring an *already-present* column, since
`knowledge.concept.status`/`knowledge.technique.status` already default to `'ACTIVE'` — the gap
is (a) no CHECK constraint pinning the valid set, (b) no endpoint to flip it, (c) nothing filters
on it today so even a manually-set `'INACTIVE'` row would still appear in every list/search. For
skill/misconception, there is no `ACTIVE/INACTIVE` axis at all today (only the pre-publication
review-status) — adding deactivate to those means adding new columns, mirroring migration 035:

```sql
ALTER TABLE knowledge.concept       ADD COLUMN IF NOT EXISTS deactivated_at timestamptz;
ALTER TABLE knowledge.concept       ADD COLUMN IF NOT EXISTS deactivated_by text;
ALTER TABLE knowledge.concept       DROP CONSTRAINT IF EXISTS concept_status_check,
                                     ADD CONSTRAINT concept_status_check CHECK (status IN ('ACTIVE','INACTIVE'));
-- identical ALTERs for knowledge.technique

ALTER TABLE knowledge.skill         ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
ALTER TABLE knowledge.skill         ADD COLUMN IF NOT EXISTS deactivated_at timestamptz;
ALTER TABLE knowledge.skill         ADD COLUMN IF NOT EXISTS deactivated_by text;
-- identical ALTERs for knowledge.misconception
```

```
POST /v1/admin/taxonomy/{kind}/{slug}/deactivate   {"reason": "..."}
POST /v1/admin/taxonomy/{kind}/{slug}/reactivate
```

Each writes one `audit.action_log` row via the existing `record_audit_event()` helper (already
built and tested this session for micro-courses) — no new audit mechanism, same table, same
helper, different `entity_kind`. Deactivating a concept/technique/skill/misconception should also
be blocked (409, matching the micro-course publish-immutability pattern) while it is still the
*primary* canonical target of a PUBLISHED micro-course release, so authoring content can never
silently point at a hidden canonical entity — this needs one new guard query, analogous to the
existing micro-course identity-immutability trigger.

## 6. What this document is explicitly *not* proposing

- **Not** proposing a generic "admin CRUD framework" or ORM-style auto-generated endpoints for
  every table in the schema — only the four concretely-named entities (concept, technique, skill,
  misconception) that the admin ask named or that share their exact shape.
- **Not** proposing to change the existing `pedagogy_admin.py` governance workflow's semantics for
  `problem_concept`/`problem_technique`/`problem_skill`/relations — those already work and are out
  of scope.
- **Not** proposing to remove or rename any existing endpoint, tag, or field — every change here
  is additive (new endpoints, new optional columns, new tag metadata) to avoid breaking the
  existing Next.js admin UI, CLI, or any other current consumer.
- **Not** proposing new authentication mechanisms beyond correctly *declaring* the one that
  already exists (`X-Admin-Api-Key`) as a real OpenAPI security scheme.
- **Not** auditing every one of the 268 operations line-by-line for documentation quality in this
  pass — §1.3's 205-undocumented-operations count is the starting backlog; which specific
  operations get a docstring first is an implementation-time prioritization call, not something
  to pre-decide in a planning document.

## 7. Dependencies and sequencing

1. §3 (OpenAPI/tag/security-scheme fixes) has no schema dependency and can be done first, in
   isolation, with no risk to any existing consumer.
2. §4's `Literal`-ification of `source_kind` and the papers `status=` filter can be done alongside
   §3, same reasoning.
3. §5.1 (list/search) can be built against the *existing* schema with zero migration — it only
   needs new read-only queries over `knowledge.concept`/`technique`/`skill`/`misconception`.
4. §5.2 (update) likewise needs no new migration if option (b) (lightweight PATCH) is chosen for
   concept/technique; option (a) (extend `Kind`) needs no new migration either since the
   governance tables already exist.
5. §5.3 (alias) requires the new `knowledge.entity_alias` table — a migration, additive only.
6. §5.4 (activate/deactivate) requires new columns/constraints on four tables — a migration,
   additive only, modeled directly on migration 035.

Recommended implementation order if/when this is picked up: 3 → 4 → 5.1 → 5.2 → 5.3 → 5.4,
each independently shippable and testable (mirrors how this session's AMC-* work was sequenced
and verified one slice at a time).

## 8. Requirement inventory (APID-*)

| ID | Requirement | Acceptance evidence |
|---|---|---|
| APID-1 | One consistent, hyphenated, admin-prefixed tag-naming convention across every router | Every admin-gated router's tag starts with `admin-`; no router declares zero tags; `GET /openapi.json` shows no operation in the unlabeled default bucket |
| APID-2 | App-level OpenAPI `description`/`summary` and registered `openapi_tags` with a one-line purpose + auth note per tag | `GET /openapi.json`'s `info.description` is non-empty; `tags` array is non-null and covers every tag used by any operation |
| APID-3 | Admin API key registered as a real OpenAPI security scheme | `components.securitySchemes` includes an `APIKeyHeader` entry; the `x-admin-api-key` parameter on any admin operation reports `"required": true` |
| APID-4 | Every operation handler has a non-empty docstring | `GET /openapi.json` reports 0 operations with an empty `description` field |
| APID-5 | `source_kind` and papers `status=` (and any other confirmed free-text-enum field found during implementation) converted to real `Literal`/enum types | Both fields render as an OpenAPI `enum`, not a `description`-only string |
| APID-6 | `GET /v1/admin/taxonomy/{concepts,techniques,skills,misconceptions}` listing/search endpoints exist | Each returns real rows for the live database (20 templates/etc. style live verification, not a mock) with `q=`/`status=` filtering |
| APID-7 | An admin can update a concept/technique's name/description/level through a REST call | A live PATCH changes `knowledge.concept.description` and the next `GET` reflects it |
| APID-8 | An admin can update a skill's `objective`/fields through a REST call without going through raw SQL | Live edit via the (extended) governance workflow changes `knowledge.skill` and is visible on the next queue/list call |
| APID-9 | An admin can add/remove an alias for any of the four taxonomy kinds, and alias text participates in the existing search endpoints | Adding alias "AM-GM" to a technique makes it discoverable via `q=AM-GM` on the existing public/technique search and the new admin listing |
| APID-10 | An admin can deactivate/reactivate a concept, technique, skill, or misconception, with an audit trail, and a deactivated entity is blocked from being newly referenced while still visible to admins | Deactivated entity disappears from default public listing, reappears on reactivate, one `audit.action_log` row per transition, and new authoring calls that try to reference it return 409/422 |
| APID-11 | Deactivating a canonical entity that's the primary target of a **published** micro-course release is blocked | Attempting to deactivate such an entity returns 409 with a message naming the blocking release, matching the existing publish-immutability error style |

## 9. Proposed consolidated new-endpoint table (for implementation-time reference)

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/admin/taxonomy/concepts` | List/search concepts (admin, includes inactive) |
| PATCH | `/v1/admin/taxonomy/concepts/{slug}` | Update name/description/level |
| POST | `/v1/admin/taxonomy/concepts/{slug}/deactivate` | Deactivate, with audit + immutability guard |
| POST | `/v1/admin/taxonomy/concepts/{slug}/reactivate` | Reactivate, with audit |
| GET/POST/DELETE | `/v1/admin/taxonomy/concepts/{slug}/aliases[/{alias_id}]` | Alias CRUD |
| *(identical 5 rows for `techniques`)* | | |
| GET | `/v1/admin/taxonomy/skills` | List/search skills (new — no listing exists today) |
| *(update via extended `pedagogy_admin.py` `Kind`, not a new path)* | | |
| POST/POST | `/v1/admin/taxonomy/skills/{slug}/{de,re}activate` | New lifecycle axis (skills have none today) |
| GET/POST/DELETE | `/v1/admin/taxonomy/skills/{slug}/aliases[/{alias_id}]` | Alias CRUD |
| GET | `/v1/admin/taxonomy/misconceptions` | List/search misconceptions (new — no listing exists today) |
| POST/POST | `/v1/admin/taxonomy/misconceptions/{code}/{de,re}activate` | New lifecycle axis |
| GET/POST/DELETE | `/v1/admin/taxonomy/misconceptions/{code}/aliases[/{alias_id}]` | Alias CRUD |

21 new operations total (5 × 2 entities with existing status column + 7 × 2 entities needing a
new lifecycle axis − shared counting of the alias triad), all additive, none replacing an
existing path.

## Cross-document relationship

- Builds on and explicitly reuses patterns from [doc 40](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/40_MICRO_COURSE_PLATFORM.md)
  and [doc 43](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/43_ADMIN_MICRO_COURSE_AUTHORING_UI.md)
  (audit logging, activate/deactivate, canonical-target lookup search) rather than introducing new
  mechanisms.
- Independent of [doc 44](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/44_MICRO_COURSE_MOBILE_AI_ANALYTICS_PLATFORM.md)'s
  mobile/analytics scope; no overlap, no ordering dependency either direction.
- If/when implemented, `requirements/reference/REST_API.md`, `REST_ENDPOINTS.md`, and
  `openapi.json` under [requirements/reference/](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/reference)
  should be regenerated/updated in the same change, since they are already stale against the live
  API (229 operations recorded there vs. 268 live today) independent of this document's proposals.
