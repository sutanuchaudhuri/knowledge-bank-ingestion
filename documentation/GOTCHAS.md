# GOTCHAS — things that will bite you on a fresh machine

## Pipeline completion and hybrid retrieval

- Admin `/admin` observes registered sources plus canonical papers. A historical
  batch snapshot is only one scope; its totals are not the whole competition.
- Batch `graph_verified` does not imply vectors, generated teaching metadata or
  taxonomy relationships are complete. The console measures these separately.
- Unknown historical timestamps stay unrecorded. Stale heartbeats are evidence
  of stalled reporting, not proof that a process has exited.
- Graph failures show UNKNOWN and warnings, not zero edges. Graph write counts
  in projection logs are operations; live edge counts are separate inventory.
- Search defaults to graph + pgvector + lexical RRF. Graph outages are disclosed
  as degraded retrieval. Similarity is not proof of skills or learner mastery.
- Paper stages now retain start/end times in work-item metrics for future runs;
  existing running workers keep their loaded code until a safe restart.

Every item here was hit for real while building this repo. `make bootstrap`
(root Makefile) automates around all of them where possible; this file
explains *why* each workaround exists, for when it inevitably breaks again on
a different macOS version / Xcode CLT version / Homebrew state.

## Textbook packages (Prasolov) and the solution-step graph

The categorized, exhaustive catalog is [requirements/19](requirements/19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md);
progress and verification SQL are in [requirements/18](requirements/18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md).
Package CSVs carry a BOM (`utf-8-sig`). Source quirks (duplicate 13.39, orphan
solutions, repeated part/step IDs) become `ingest.import_conflict` rows and
`#k` occurrences, never aborts. Any writer of `knowledge.*` must take the shared
`LOCK TABLE … SHARE ROW EXCLUSIVE` list in the same order, or it deadlocks with
the enrichment watcher. The step graph uses `projection_kind='solution_steps'`
so the batch `--pedagogy` replacement never deletes it. It needs the base
Problem/Solution/Skill nodes first (`make -C mathbank-db textbook-graph-remote`)
and fails if a MERGE endpoint is missing. Cypher aliases need `AS` on Aura.
Bridging textbook taxonomy into `knowledge.*` pushed the contest enrichment
schema past OpenAI's 1,000 enum-value limit. Enrichment now leaves out
textbook-only nodes, and `generation_schema` refuses an oversized catalog
before making a paid call (GOT-ENR-10). A deadlock can kill the enrichment
watcher silently, so check it after imports (GOT-RUN-12).

## Automatic enrichment: generation and graph publication are separate

For automatic enrichment recovery, see the
[implementation plan and acceptance criteria](requirements/14_AUTOMATIC_ENRICHMENT_RECOVERY.md).
Cross-corpus prerequisite cycles require corrected proposals, not deleting
existing edges. `COMPLETED` jobs with null `published_at` are durable graph
publication work, not failed generation: retry publication without model calls.
Model HTTP 200 does not mean validated metadata. Watch mode reselects due
five-minute retries between problems and replays failed publication after
60 seconds; a running model/import call is not preempted. Job attempts and
model-response attempts are separate paid budgets. Never run overlapping workers
to bypass an IN_PROGRESS claim; abandoned claims expire after ten minutes.
Structured-output concept enums are shared using `$ref`: duplicating the full
catalog for problem and skill tags can exceed the model API's enum budget.
Keep independent import validation even with constrained generation.
Teaching publication replaces the whole owned pedagogical edge layer even when
corpus tag synchronization is scoped. Include `approval_method` in that atomic
replacement; stamping only the scoped problems afterward falsely labels other
automatic mappings as human-reviewed.
Use one watcher with `--workers 4`, not four watchers. Model requests overlap;
global cycle-safe imports and graph publication remain serialized. SIGTERM
drains the threaded watcher, so wait for its PID to exit before replacement.
Provider throttling and database locks can limit speedup.

## Catalog relationships need separate semantic checks

Question prerequisite enrichment does not populate skill hierarchy, optional
supporting skills, or concept prerequisites. Enable `--relationships` on the
same watcher after migration 009; never relabel edges or fabricate relationships
to fill an empty view. PART_OF is component action -> composite action;
BUILDS_ON is useful prior skill -> dependent skill; concept PREREQUISITE_OF is
necessary foundation -> dependent knowledge.

The first paid pilots passed schema/cycle checks yet produced synonyms,
reversed edges and false prerequisites. Independent semantic verification is
mandatory before automatic approval. Earlier bad pilot edges were REJECTED with
audit history and cannot be resurrected by the worker. Model agreement still
is not expert certification. Both relationship calls default to `gpt-4.1`;
override through `RELATIONSHIP_MODEL` / `RELATIONSHIP_VERIFIER_MODEL`. Question
enrichment is unchanged. Changing models enters the job input fingerprint and
can generate more paid work. Candidate retrieval is bounded and safe empty
proposals are allowed. Mixed-stage throughput is not the question-only ETA.
Details: [relationship enrichment](requirements/15_RELATIONSHIP_ENRICHMENT.md).

## Purple Comet PDF and image completeness

Discover actual contest links and embedded English PDF URLs from the official
archive. Determine each year's question count from its official numbered answer
table; older high-school contests do not all have 30 questions. Some historical
`/files/...pdf` endpoints can return HTML with HTTP 200. Check `%PDF-` bytes and retain
an explicit failed source rather than classifying the homepage.
Some valid old Purple Comet PDFs begin with whitespace before the PDF header.
The first signature check incorrectly rejected these as non-PDF; the shared
header validator now accepts only a whitespace-prefixed header within the
first 1024 bytes. It still rejects HTML with a PDF-looking string inside it.
Validate both official hosts before declaring a source unavailable.

CPU Docling exports headings such as `## Problem 1`. A regex matching only
bare `Problem 1` lines incorrectly falls back to a whole-paper block. Treat
Markdown heading prefixes as question headings, then enforce exact counts.
Docling defaults to CPU, with formula enrichment enabled. Archive workers set
`HF_HOME`, `TORCH_HOME` and `TMPDIR` under the external-drive project; do not
download model caches onto the space-constrained system disk or switch to GPU.

Problem/solution page images must follow numbered page spans. Proportional page
assignment can omit a diagram or continuation page. Keep full page renders for
vector diagrams too; embedded-raster-image extraction alone is insufficient.
Purple Comet sends these real PNG bytes to its visual classifier (`gpt-4.1`),
not merely filenames in a prompt. Preserve original PDFs and extracted text;
native-text fallback still needs formula-quality review, even with all images.

An official answer key is not an explanatory solution. Keep answers in
`core.problem.official_answer`; do not create fake solution records when the
worked-solution PDF is unavailable. Store both problem and solution page
references in `core.problem_image` with distinct sources. Queue publication on
the existing paper advisory lock instead of competing with the SMT/HMMT runner.

## 1. Python venvs: use `uv venv`, not `python3.11 -m venv`

On this class of machine, a bare `python3.11 -m venv .venv` can produce a
**broken interpreter** when `python3.11` resolves to a uv-installed standalone
CPython build invoked directly outside of uv's management:

```
Fatal Python error: init_fs_encoding: failed to get the Python codec of the filesystem encoding
ModuleNotFoundError: No module named 'encodings'
```

**Fix**: every Makefile in this repo creates venvs with `uv venv .venv --python 3.11`
instead. If you add a new project, do the same — don't call `python -m venv`
directly.

## 2. Postgres runs on port 5433, not 5432

`mathbank-db` initializes its own cluster on the external drive and starts it
on port **5433** deliberately, to avoid colliding with any other local
Postgres (e.g. an Anaconda-bundled `psql`/`pg_config` was detected earlier on
this machine's `PATH`). All Makefiles, `.env.example` files, and REST configs
default to 5433 — don't "fix" this back to 5432.

## 3. `CREATE EXTENSION pg_trgm` works for the app owner; `vector` doesn't by default

PostgreSQL extensions are either "trusted" (any role with `CREATE` on the
database can install them, e.g. `pg_trgm`) or not (superuser required,
`pgvector`'s default). `mathbank-db/Makefile`'s `install-pgvector` target
appends `trusted = true` to `vector.control` after building, so
`mathbank_app` (the non-superuser app owner) can self-service
`CREATE EXTENSION vector` exactly like `pg_trgm`, keeping `make migrate-vector`
consistent with the rest of the pipeline (no superuser step needed at
migration time). This matches what newer upstream pgvector releases ship by
default — we're just doing it manually for a source build.

## 4. Homebrew's bottled `pgvector` only targets Postgres 17/18, not our 16

`brew install pgvector` installs compiled `.dylib`/`.sql` files only for
`postgresql@17` and `postgresql@18` (whatever the CI bottle builder had).
Since `mathbank-db` runs `postgresql@16`, **you must build pgvector from
source** against it — `make -C mathbank-db install-pgvector` does this:

```bash
git clone --branch v0.8.0 --depth 1 https://github.com/pgvector/pgvector
make PG_CONFIG=/opt/homebrew/opt/postgresql@16/bin/pg_config ...
```

then copies the resulting `vector.dylib` + `.sql`/`.control` files straight
into `postgresql@16`'s own (Homebrew-owned, **user-writable, no sudo needed**)
`lib`/`share` directories.

## 5. `pg_config --cppflags`/`--ldflags` can bake in a nonexistent macOS SDK path

Building pgvector (or any native Postgres extension) from source can fail
with cryptic errors like:

```
fatal error: 'stdio.h' file not found
```

because `pg_config --cppflags` includes `-isysroot /Library/Developer/CommandLineTools/SDKs/MacOSX26.sdk`
— a path baked in at the time the Homebrew `postgresql@16` bottle was built,
which may not exist on *this* machine (check
`ls /Library/Developer/CommandLineTools/SDKs/`). **Do not** try to fix this
by creating that SDK symlink with `sudo` — it's a system directory and the
fix doesn't need root. Instead, rewrite that one path segment to the SDK
that actually exists (`xcrun --show-sdk-path`) before invoking `make`:

```bash
FIXED_CPPFLAGS=$(pg_config --cppflags | sed "s#MacOSX26.sdk#$(basename $(xcrun --show-sdk-path))#")
```

`install-pgvector` does this automatically.

## 6. `OPENAI_API_KEY`: file-only project credentials

Both `mathbank-db/etl/embed_corpus.py` and `mathbank-rest`'s
`vector_search.py` (and `mathbank-agent`'s LiteLLM model) read `OPENAI_API_KEY`
via the OpenAI/LiteLLM SDK defaults (`os.environ`). Set it in the gitignored
root `.env`, then run `make sync-openai-key`. This writes owner-only service
environment files without displaying the key, including REST, agent and
ingestion. `make up` / `make up-app` also perform this sync.
Shell keys are ignored, including ones inherited from `.zshrc`. The shared
credential loader reads root `.env` without variable interpolation, overrides
the runtime key, and clears inherited OpenAI routing/organization/project
settings unless configured in project files. This also applies to direct
REST, agent, classification/review and embedding commands. A service key is
used only if root `.env` does not exist; a root file with a missing/empty key
fails explicitly. Other worker database overrides are unchanged.

Run `make check-openai` to check authentication; `make check-openai CHAT=1`
also performs a small paid LiteLLM call with the agent's file-configured model.
401 is different from quota/rate-limit 429 or model access 403/404. A shared
file can be valid here but missing/stale on another machine; check there.
Never modify another project's shell profile to fix MathBank.
Restart running services after changing the key. Never commit the key, pass
it as a command-line argument, expose it through `NEXT_PUBLIC_*`, or share
environment files/logs through unsecured channels.

## 7. OCR/PDF-parsed text can contain NUL (`\x00`) bytes

Postgres `text` columns reject embedded NUL bytes outright
(`psycopg.errors.DataError: PostgreSQL text fields cannot contain NUL (0x00) bytes`).
A handful of Docling/PyMuPDF-extracted PDF pages produce them. Every ETL path
that reads `problem.md`/`solution.md` from `data/crawl_pdf/` strips
`"\x00"` before inserting (`mathbank-db/etl/load_corpus.py` and
`pdf_pipeline.py`) — do the same in any new ingestion path.

## 8. MPG PDFs have a "Directions" cover page that corrupts Problem 1–9

`mathbank-data-ingestion`'s shared PDF splitter keeps the **first** occurrence
of each number it finds (`"1. Do not open this test..."`, `"2. Fill out..."`
on the Directions page) rather than the real `Problem 1`/`Problem 2`. Any new
PDF-sourced competition should have its first few parsed questions spot-checked
manually — see `mathbank-db/etl/parse_mpg_pdfs.py`'s `_drop_cover_page()` for
the fix pattern (detect "directions"/"do not open" on page 1 via PyMuPDF and
drop that page before splitting).

## 9. SQLAlchemy `text()` silently fails on `:bindparam::type` (adjacent cast)

`ORDER BY embedding <=> :query_vector::vector(1536)` compiles to a raw,
un-substituted `:query_vector` sent straight to the DBAPI — a confusing
`psycopg.errors.SyntaxError` at the driver level, not a Python-level error.
**Fix**: use `CAST(:query_vector AS vector(1536))` instead of the `::`
shorthand whenever a bind parameter needs an explicit Postgres type cast
inside `sqlalchemy.text()`.

## 10. Google ADK agent discovery convention

`adk api_server <dir>` / `adk web <dir>` expect `<dir>` to contain one
subfolder per agent, each with an `agent.py` exposing a module-level
`root_agent` variable (and an `__init__.py` with `from . import agent`).
`mathbank-agent/agents/mathbank_tutor/` follows this exactly — if you add a
second agent, give it its own sibling folder under `agents/`, not a file.

## 11. Don't name a Makefile variable `NEO4J_CONF` — it collides with Neo4j's own env var

`mathbank-graph/Makefile` has a bare `export` directive that exports *every*
Makefile variable into the environment of recipe commands (this is a GNU
Make feature — the Apple-bundled `make` is GNU Make 3.81, not BSD make).
The Makefile used to define `NEO4J_CONF := .../libexec/conf/neo4j.conf` (a
**file** path) for its own `sed`-based config patching — but `NEO4J_CONF` is
also a reserved environment variable the `neo4j` CLI itself reads, where it's
expected to be a **directory**. Exporting the file path as `NEO4J_CONF`
made the `neo4j start`/`status` subprocess compute
`$NEO4J_CONF/neo4j.conf` → `.../neo4j.conf/neo4j.conf`, which doesn't exist:

```
Error: Unable to load config file [.../libexec/conf/neo4j.conf/neo4j.conf]:
.../libexec/conf/neo4j.conf/neo4j.conf: Not a directory
```

**Fix**: renamed the Makefile variable to `NEO4J_CONF_FILE` everywhere. If you
add new Makefile variables in `mathbank-graph` (or any Makefile with a bare
`export`), avoid reusing names Neo4j itself recognizes (`NEO4J_HOME`,
`NEO4J_CONF`, `NEO4J_DATA`, etc.) even if the *intent* differs.

## 12. Service lifecycle: individual + aggregate Make commands, with auto-kill-on-port-conflict

Every service can be started/stopped/restarted/checked individually from the
root Makefile — `rest`/`agent`/`web` run as background daemons (pidfile in
`.server.pid`, logs in `.server.log`) and their `start` target always runs
`lsof -ti:$(PORT) | xargs kill -9` first, so a stale/stuck process on that
port is killed automatically before the fresh one launches. `db`/`graph`
`start` targets are intentionally **not** port-kill-based (forcefully killing
a database process is a data-corruption risk) — they check `pg_ctl status` /
`neo4j status` first and no-op if already running instead.

```bash
make rest-start / rest-stop / rest-restart / rest-status      # :8000
make agent-start / agent-stop / agent-restart / agent-status  # :8001
make web-start / web-stop / web-restart / web-status          # :5173
make db-start / db-stop / db-status                           # :5433 (idempotent)
make graph-start / graph-stop / graph-status                  # :7687/:7474 (idempotent)

make up      # starts all 5, in dependency order
make down    # stops all 5
make status  # status of all 5
```

## 13. `adk api_server` rejects cross-origin browser requests by default (CORS)

`adk api_server`'s endpoints return `403 Forbidden: origin not allowed` for
any request whose `Origin` header isn't explicitly allow-listed — a plain
React/Vite SPA calling it directly from the browser (`fetch("http://127.0.0.1:8001/...")`)
fails outright, even though `curl` without an `Origin` header works fine
(this is exactly why a passing `curl` smoke test gave false confidence).
Two fixes exist:

1. Pass `adk api_server ... --allow_origins=http://localhost:5173` (the CLI
   option is a Click `multiple=True` flag — repeat it per origin, don't
   comma-separate: `--allow_origins=A --allow_origins=B`).
2. **Preferred (what `mathbank-web` does since its Next.js rewrite)**: don't
   call the agent from the browser at all. Put a same-origin server-side
   proxy in front of it (`app/api/agent/*` Next.js route handlers) — the
   browser only ever talks to its own origin, and the server-to-server call
   to `mathbank-agent` has no CORS restriction at all (CORS is a
   browser-enforced policy, not a server-to-server one). This also means
   `mathbank-agent` needs zero CORS configuration, which matters once it's
   no longer "run on a trusted network only" per its own `--help` text.

## 14. `set -a; source .env; set +a` in a terminal leaks vars into every later command

Real exported environment variables always win over `.env` file values in
pydantic-settings / python-dotenv (the `.env` file is only a fallback). If
you `set -a; source some.env; set +a` in a persistent terminal to test one
command, those vars stay exported in that shell for every command you run
afterward — including a `nohup ... &` background server you launch later,
which silently inherits the stale values instead of reading its own `.env`.
Hit this migrating `mathbank-rest` from local Postgres/Neo4j to remote
Neon/AuraDB: after updating `.env` to the new Aura password, the running
service kept authenticating with the old local Neo4j password because an
earlier `source mathbank-graph/.env` in the same terminal had exported it.
**Fix**: `unset VAR1 VAR2 ...` before relying on `.env` again, open a fresh
terminal, or prefer `VAR=val command` (scoped to one line) over `set -a`.

## 15. Neon's `neondb_owner` role has an EMPTY `search_path` — unqualified pgvector operators/types fail

After migrating `mathbank-db` to Neon, `/v1/search/problems` started 500ing:

```
psycopg.errors.UndefinedObject: type "vector" does not exist
```

and after schema-qualifying the type:

```
psycopg.errors.UndefinedFunction: operator does not exist: public.vector <=> public.vector
```

`SHOW search_path;` on this Neon role returns **blank** — not even the
default `"$user", public`. Any unqualified reference to something pgvector
installs into the `public` schema (the `vector` type itself, and operators
like `<=>`) fails to resolve, even though `CREATE EXTENSION vector` succeeded
and `pg_available_extensions`/`pg_extension` show it present. This only
breaks raw SQL that doesn't schema-qualify — table references like
`core.problem` were unaffected since they're already schema-qualified.

Tried **`ALTER ROLE neondb_owner IN DATABASE neondb SET search_path = public;`**
first — it reports success but `SHOW search_path;` on a fresh connection
through Neon's pooler endpoint still comes back empty, so it does not
reliably fix this for pooled connections.

**Fix**: schema-qualify explicitly in the SQL itself (`mathbank-rest/src/
mathbank_rest/db/vector_search.py`), don't rely on `search_path`:
- Type casts: `public.vector(1536)` instead of `vector(1536)`.
- The distance operator: `OPERATOR(public.<=>)` instead of bare `<=>`
  (Postgres's schema-qualification syntax for operators, not just
  `public.<=>` — operators aren't resolved like function/type names).

Verified fixed against the original AMC10-combinatorics repro case post-fix.
Any other new raw-SQL pgvector usage against Neon should do the same.

## 16. Concept taxonomy is hierarchical — querying by a broad/parent slug silently matched ~nothing

`requirements/11_SYSTEM_DIAGRAMS_TESTING_AND_METRICS.md` §6's first retrieval
eval run showed **0.00 precision@10** for broad single-concept queries
("combinatorics counting problems" → `concept_slug="count"`, "AIME
combinatorics" → same). The returned problems were genuinely on-topic
AIME/AMC combinatorics problems (verified by eye), so this looked like a
search-ranking bug at first — it wasn't.

Root cause: `knowledge.concept` is a **tree**, not a flat tag set
(`knowledge.concept_relation` has a `HAS_SUBCONCEPT` relation type, e.g.
`count` → `count-subset`, `count-pie`, `count-perm`, `count-sym`, ...). The
OpenAI classification step (`classify_crawled.py`) always tags a problem with
the most **specific leaf** concept, never the broad parent — so
`knowledge.problem_concept` has rows for `count-subset` etc., but
essentially none directly for `count` itself. Any query doing
`WHERE c.slug = :slug` (the old `get_concept_problems` in
`mathbank-rest/src/mathbank_rest/db/queries.py`, which both the live
`GET /v1/concepts/{slug}/problems` endpoint and the retrieval-eval ground
truth derivation in `scripts/golden_queries.py`/`evaluate_retrieval.py`
depend on) therefore measured "relevant" as a near-empty set for every broad
parent concept, making precision/recall look like 0 regardless of how good
search actually was.

**Fix**: `get_concept_problems` now walks the `HAS_SUBCONCEPT` closure with a
recursive CTE (cycle-guarded via a `path` array) before matching
`knowledge.problem_concept`, and dedupes to one row per problem (best
role/confidence wins) since a problem can be tagged with multiple sibling
subconcepts. No caller changes needed — `/v1/concepts/{slug}/problems` and
the eval harness both call this one function. Verified via
`make eval-retrieval`: `combinatorics-general` went from
`relevant=25, P@10=0.00` to `relevant=729, P@10=0.30`; `aime-combinatorics`
from `relevant=7, P@10=0.00` to `relevant=80, P@10=0.40`.

**Separate, still-open finding (not a code bug — a data-coverage gap)**:
`pigeonhole-principle` and `invariant-technique` are *still* 0 precision
after this fix. `GET /v1/corpus/coverage` shows why: classification has only
ever been run over AMC10/AMC12/AIME (~99% tagged); SMT/CHMMC/PUMaC/CMM/Math
Prize for Girls are 0-5% tagged. Those competitions dominate the semantic
search results for niche single-technique queries, but since they're barely
classified, the derived ground truth for them is structurally tiny — this
needs a classification run over the rest of the corpus, not a query fix.
Tracked in `requirements/11_SYSTEM_DIAGRAMS_TESTING_AND_METRICS.md` §6 and
`documentation/copilot-instructions/mathematics-tutor-db-plan/00_implementation_progress.md` Round 8 follow-ups.

**Takeaway for any new "lookup by taxonomy slug" code**: check whether the
taxonomy is a tree (`knowledge.concept_relation.relation_type = 'HAS_SUBCONCEPT'`)
before assuming a flat tag match is correct — `knowledge.technique` has no
such hierarchy table, so `get_technique_problems` does NOT need this fix.

## 17. Ingestion scripts had no persistent progress record — background runs were invisible after the fact

Every classify/crawl/export script in `mathbank-data-ingestion` printed a
summary to stdout and nothing else. When run via `nohup ... &` (the norm for
anything that takes more than a couple minutes — see the `make etl-remote`/
`make classify-pdf` pattern used throughout this project), that summary is
only in the `/tmp/*.log` file you happened to redirect to, if any — there was
no queryable, persistent record of what ran, when, with what params, or
whether it actually finished vs. got silently killed.

**Fix**: `mathbank-data-ingestion/src/mathbank/db/tracking.py` — an
`IngestionRun` context-manager class that writes one row per script
invocation to a new `ingestion_runs` table in the *existing* `data/mathbank.db`
(no new DB file) plus a full-detail text log under `logs/` (gitignored).
Wired into all 4 local scripts (`crawl_unmapped.py`, `classify_crawled.py`,
`classify_pdf_corpus.py`, `export_classifications_to_csv.py`) at every exit
path. View with `make progress` (`mathbank-data-ingestion/scripts/show_progress.py`).

For scripts that already hold a live Postgres connection
(`mathbank-db/etl/load_corpus.py`, `mathbank-graph/etl/project_from_postgres.py`),
use the **existing** `pipeline.run` / `pipeline.graph_projection` tables
instead of a second SQLite tracker — `load_corpus.py` was wired into
`pipeline.run` (it previously existed in the schema but nothing wrote to it);
`project_from_postgres.py` already used `pipeline.graph_projection`. View
with `make progress` / `make progress-remote` in `mathbank-db/`.

**Takeaway for any new ingestion script**: a `RUNNING` row with no
`finished_at`/`completed_at` and no matching live process (`ps aux`) means
the run crashed or was killed — that's the signal to look for, not a
missing log file.

## 18. `etl/pdf_pipeline.py` and `etl/embed_corpus.py` only ever connected to local Postgres

Both scripts' `_connect()` hardcoded `host=127.0.0.1` — unlike
`etl/load_corpus.py`, which already supported `PG_ENV_FILE=.../remote.env`
to target Neon. This went unnoticed because `make etl`/`make etl-remote`
(load_corpus.py) were the only ETL paths exercised against Neon until the
admin pipeline work needed `pdf_pipeline.py fetch`/`reconcile`/`ingest` and
`embed_corpus.py backfill` to run against the same remote rows an admin had
just registered via `POST /v1/admin/papers` (which writes straight to Neon
through mathbank-rest). Running either script with `PG_ENV_FILE=...` set
silently still connected to `127.0.0.1:5433` and failed with a password/auth
error instead of reaching Neon.

**Fix**: both `_connect()` functions now mirror `load_corpus.py`'s
`NEON_PG_*`-first-then-local-fallback precedence. **Takeaway**: any new
`etl/*.py` script in `mathbank-db` needs this same `_connect()` pattern from
day one if it might ever run against Neon — copy it from `load_corpus.py`,
don't hardcode `127.0.0.1`.

## 19. Admin-registered papers: PENDING rows, PDF vs HTML fetch paths, every stage logged

Built per the ask: "tables automatically have rows PENDING once an admin
adds a new competition with page urls" + a pipeline covering
download/parse/populate-Postgres/populate-graph/vector-recalibration/
classification, "competition specific" (some competitions publish PDFs,
others a single HTML page per paper).

**What already existed and was reused as-is** (no rebuild): `pipeline.pdf_source`
(PENDING-by-default columns for download/parse/ingest, one row per paper) and
`etl/pdf_pipeline.py`'s `reconcile`/`ingest` commands — both are **format-agnostic**,
they only ever check for `questions/Qnn/problem.md` on disk, so a new fetch
path for HTML papers needed zero changes to either.

**What was added**:
- `source_kind` column (`PDF` | `HTML`, `sql/004_admin_pipeline.sql`) on
  `pipeline.pdf_source` — not a CHECK constraint (`ADD CONSTRAINT IF NOT EXISTS`
  isn't idempotent in Postgres), validated at the REST layer instead.
- `mathbank-rest` `/v1/admin/*` (new `routers/admin.py` + `db/admin.py`) —
  `POST /v1/admin/competitions`, `POST /v1/admin/papers` (single/batch,
  inserts the PENDING row immediately), `GET /v1/admin/papers` (status
  dashboard), `POST /v1/admin/papers/{code}/retry`, `GET /v1/admin/pipeline/runs`
  (merges `pipeline.run` + `pipeline.graph_projection`). Single shared
  `X-Admin-Api-Key` header, not a per-user role system — deliberately scoped
  down for the current one-operator reality; see the module docstring for
  the "add real admin accounts later" follow-up.
- `etl/pdf_pipeline.py::cmd_fetch_html` — a **generic**, stdlib-only
  (`urllib` + `html.parser`, no Docling/extra deps) fetcher for `source_kind=HTML`
  rows: treats the whole page as one `questions/Q01/problem.md` (+ `solution.md`
  if a solution URL is set), since generic HTML can't be assumed to have the
  AoPS-wiki or Docling-PDF per-question structure. A competition whose HTML
  actually has multiple sub-pages per paper needs its own small parser
  following the same contract (write `questions/Qnn/problem.md`), not a
  change to `reconcile`/`ingest`. `cmd_fetch` (existing PDF path) now only
  queries `source_kind='PDF'` rows; `fetch` runs both.
- `etl/embed_corpus.py backfill` wired into `pipeline.run` (run_type
  `EMBED_BACKFILL`) for parity with `load_corpus.py`/`pdf_pipeline.py` —
  "vector db recalibration" is now one of the logged stages too.
- `mathbank-web/app/admin` — form to add a competition, form to register a
  paper (code/year/URLs/source_kind), live paper-status dashboard, live
  pipeline-runs table. Proxies through new `app/api/rest/admin/*` routes that
  attach `X-Admin-Api-Key` **server-side** (`MATHBANK_ADMIN_API_KEY` env var,
  never sent to the browser) — same "browser only calls our own /api/rest/*"
  boundary as the rest of `mathbank-web`.

**Verified live against Neon**: competition create → paper register (both
`PDF` and `HTML` source_kind) → PENDING row appears immediately via both
`curl` and the web UI → `fetch` (HTML path only, using `https://example.com`
as a safe test target) → `DOWNLOADED`/`PARSED` → `reconcile` confirms it on
disk. (`ingest` for that specific test paper hit the **unrelated**, pre-existing
`PAPER_ID_RE` limitation below — not a new bug.) Test rows deleted after
verification.

**Separate, pre-existing limitation surfaced (not fixed, out of scope here)**:
`load_corpus.py`/`pdf_pipeline.py`'s `PAPER_ID_RE = r"^PAPER_[A-Z]+_(\d{4})_(.+)$"`
requires the competition-code segment to be letters only — no underscore. Real
per-question-split competitions (CHMMC/CMM/PUMAC/SMT) happen to have
no-underscore codes so this never surfaced before; a test competition named
`TEST_HTML_COMP` hit it immediately. If a future competition's natural code
needs an underscore (unlike `MPG_OLY`, which is NOT per-question-split and so
never goes through this ingest path), this regex needs widening.

## 20. Postgres `AVG()` over an exact-zero `NUMERIC` column serializes as `"0E-20"` in JSON

Hit while verifying the new `GET /v1/analytics/weak-concepts` cohort analytics
endpoint (`db/learner.py::get_cohort_weak_concepts`) — `AVG(m.mastery_score)`
where `mastery_score` is `NUMERIC` and every row happens to be exactly `0`
returns a `Decimal` with a large negative exponent (`Decimal('0E-20')`), which
then serializes in the JSON response as the *string* `"0E-20"` instead of a
clean `0.0` — technically correct but confusing for any client doing numeric
comparisons/formatting on it. Same risk applies to any `AVG()`/`SUM()` over a
`NUMERIC` column in this codebase, not just this one query. Fix: explicitly
cast in SQL, e.g. `CAST(AVG(m.mastery_score) AS DOUBLE PRECISION)`, rather
than relying on the driver/FastAPI's default `Decimal` handling.

## 21. Any raw Postgres `NUMERIC` column (not just `AVG()`) comes back as a JSON string

Broader than #20: `learner.concept_mastery.mastery_score` is a plain
`NUMERIC` column — no aggregate involved — and `GET /v1/learner/mastery`
still serializes it as the *string* `"0.6667"`, not a JSON number, because
FastAPI/psycopg round-trips `NUMERIC` as Python `Decimal` and the default
JSON encoder renders `Decimal` as a string to avoid float-precision loss.
Hit in the student-profile UI (`mathbank-web/app/profile/page.jsx`):
`score.toFixed(2)` threw `score.toFixed is not a function` until every
mastery-score value was coerced with `Number(score)` first. Rule of thumb for
any new frontend code consuming a `mathbank-rest` endpoint that returns a
`NUMERIC`/`mastery_score`/similar field: always `Number(...)` it before doing
arithmetic or calling number methods — don't assume REST JSON numbers are
JS numbers.

## 22. Next.js API route relative-import depth is easy to miscount — recurring mistake

Hit a second time this session (`app/api/rest/learner/me/route.js` used
`../../../../lib/restClient.js`, one level too shallow, caught immediately by
the Next.js build-error overlay: `Module not found`). Pattern: count directory
segments from the route file to the project root precisely —
`app/api/rest/<a>/<b>/route.js` needs 5 `../` to reach `lib/`, one level
deeper (`app/api/rest/<a>/<b>/<c>/route.js`) needs 6. Sibling route files at
the exact same depth (e.g. `attempts/route.js` and `mastery/route.js` next to
`me/route.js`) are the fastest sanity check — if they already import `lib/`
correctly, copy their exact `../` count rather than recounting from scratch.

## 23. Interrupting `route_projection.project()` mid-run leaves the graph partially rebuilt, not safely rolled back

`mathbank_rest.route_projection._project()` does **not** wrap its delete-then-recreate
cycle in one transaction — it commits per batch (one `session.execute_write()` call per
~500-row chunk, iterating node labels then `edges_by_shape.items()` one relationship-type
shape at a time). Confirmed live: stopping the process partway through (Ctrl-C / `stop_bash`
on its PID) left the graph with the full DELETE already committed, several relationship
types already re-created (whichever `edges_by_shape` entries were reached first in dict
iteration order), and the rest still at zero — nodes stayed intact throughout (node
recreation finishes before edges start), but several `/graph/*` tabs (`EXPLAINS`,
`CAN_TRIGGER`, `USES_CLAIM`, partial `DEPENDS_ON`) silently showed "No relationships found"
for roughly 40 minutes until the same `project()` call was re-run **to completion without
interruption** (confirmed via live Neo4j relationship counts before/after, see
[requirements/50](requirements/50_NEO4J_KNOWLEDGE_GRAPH_QUALITY_BUGS.md)). **Lesson: once
`project()` is started against the live AuraDB instance, let it run to completion — launch
it as a fully detached/`nohup` background process up front (not a foreground `read_bash`
loop you might `stop_bash`) specifically so an impatient interruption can't happen.** ~~A
derived/companion layer with a *different* `projection_kind` tag (e.g. this session's new
`misconception_relations` / `RELATES_TO` edges) is unaffected by `project()`'s own
delete-filter, but can still go stale if it depends on relationship types `project()`
temporarily zeroed out mid-run — re-run the companion script once `project()` is fully
done, don't assume it's still consistent.~~ **Correction (see §24): this claim was wrong.**
A companion layer's relationship-level `projection_kind` tag does not protect it — see §24
for why, and for the fix (projecting it from inside `_project()` itself instead of as a
separate companion script). Separately: the AuraDB free-tier instance can
raise `Neo.TransientError.General.MemoryPoolOutOfMemoryError` on `project()`'s single
unbatched bulk `DELETE` statement once the `tutoring_routes` layer passes roughly 1M
relationships; that specific error mode *does* roll back cleanly (confirmed: node/edge
counts were unchanged after it), unlike a deliberate mid-run interruption once the recreate
loop has started. **Fixed in a later pass (requirements/51 ENR-2): see §25** — this is no
longer a live limitation, the unbatched DELETE itself was rewritten to batch internally.

## 24. A companion projector's edges are NOT safe from `route_projection.project()`'s node-level DETACH DELETE, even with a different `projection_kind`

§23 claimed a companion script's edges (tagged with their own distinct `projection_kind`,
e.g. `misconception_relations`) survive `project()`'s rebuild because the rebuild's
relationship-delete query filters `WHERE r.projection_kind=$kind`. **This is false, and it
was proven false live, the hard way**: a routine, fully-uninterrupted re-run of `project()`
(launched specifically to propagate unrelated taxonomy-label changes, requirements/51 ENR-8)
silently zeroed `misconception-concepts`/`misconception-skills`/`misconception-techniques`
from 82,019 edges to **0**, with no error, no warning, and no connection to anything the
run was actually trying to do.

**Root cause:** `_project()`'s rebuild does two separate delete statements:
```python
session.run("MATCH ()-[r]->() WHERE r.projection_kind=$kind DELETE r", kind=KIND)
session.run("MATCH (n) WHERE n.projection_kind=$kind DETACH DELETE n", kind=KIND)
```
The first line is scoped correctly (only deletes `tutoring_routes`-tagged relationships).
The second line is **not** relationship-scoped at all — `DETACH DELETE` on a *node* removes
**every relationship attached to that node, regardless of the relationship's own
`projection_kind`**. Since `Misconception` (and every other label `project()` manages) is
tagged `projection_kind='tutoring_routes'` at the *node* level, the second statement wipes
out any edge any other script ever attached to it, no matter what tag that edge itself
carries. A relationship's `projection_kind` only protects it from the *first* line, never
from the second.

**Fix applied (requirements/51 ENR-1/ENR-4):** stop treating the taxonomy-link edges as an
out-of-band companion projection at all. Fold them into `_project()`'s own node/edge
generation inside `route_projection.py` itself, so they are recreated by the very same
rebuild that could otherwise destroy them, every single time, atomically. The retired
companion script (`mathbank-graph/etl/project_misconception_relations.py`) is kept only for
historical reference with a `DEPRECATED` docstring — it must not be run again; its
RouteStep-join-derived edges have been fully superseded by a direct projection from the
canonical `knowledge.misconception_taxonomy_link` table.

**General lesson for this codebase: there is no such thing as a safely-isolated companion
graph projection against the `tutoring_routes` layer.** Any relationship that touches a node
`project()` manages will be destroyed on every rebuild unless `project()` itself is the one
recreating it. Before adding a new "derived edge" script against any node label this
projector owns, fold the projection into `route_projection.py` directly instead.

## 25. `route_projection.py`'s unbatched DELETE/DETACH DELETE needed batching once the graph passed ~1.5M edges — fixed with Neo4j 5's native `CALL (...) { ... } IN TRANSACTIONS`

§23 documented `MemoryPoolOutOfMemoryError` on `project()`'s bulk relationship `DELETE` as a
known, cleanly-rolling-back failure mode once the `tutoring_routes` layer passed roughly 1M
relationships — but left it as a known limitation, not a fix. Confirmed live that adding
requirements/51 ENR-2's ~310K new `SIMILAR_TO` edges (pushing total edges to 1.55M) reliably
triggered it on every attempt, not just occasionally:
```
Neo.TransientError.General.MemoryPoolOutOfMemoryError: The allocation of an extra 2.0 MiB
would use more than the limit 1.3 GiB. Currently using 1.3 GiB.
```
Confirmed first (via `pipeline.graph_projection` + a direct Neo4j node/edge count) that this
failure mode still rolls back cleanly — no partial damage, same lesson as §23 — before fixing
the actual root cause: the two delete statements were each a single unbatched Cypher `DELETE`/
`DETACH DELETE` over potentially millions of rows, unlike every node/edge *write* in the same
function, which was already correctly batched at `PROJECTION_BATCH_SIZE` (500) per transaction.

**Fix:** rewrite both deletes using Neo4j 5's native `CALL (var) { ... } IN TRANSACTIONS OF N
ROWS` construct (already used elsewhere in this codebase, e.g.
`project_misconception_relations.py`'s `RELATES_TO` MERGE), which commits internally in
batches rather than requiring one giant transaction:
```cypher
MATCH ()-[r]->() WHERE r.projection_kind=$kind
CALL (r) { DELETE r } IN TRANSACTIONS OF 5000 ROWS
```
Called via plain `session.run()`, **not** `session.execute_write()` — `IN TRANSACTIONS`
manages its own transaction boundaries internally and cannot be nested inside an explicit
managed-transaction function; wrapping it in one raises a Cypher syntax/semantic error, not a
runtime one, so this is worth getting right before a live run, not discovering it mid-rebuild.
Verified live: re-run completed successfully (`pipeline.graph_projection` status
`COMPLETED`, 415,682 nodes / 1,551,106 edges) with no further memory errors. **This threshold
will be hit again as the graph keeps growing — if a future addition pushes well past 1.55M
edges and this batched form somehow still errors, raise the `ROWS` batch size down (not up)
before assuming the whole approach needs rethinking.**

## 26. `mathbank-web`'s `MathText` component renders a `<div>` root — wrapping it in a `<p>` causes a React hydration error

Confirmed live (requirements/53, building the new quiz UI): `<MathText>` (`app/_components/MathText.jsx`)
renders `<div className="markdown-body">...</div>` at its root, because the markdown it renders
internally can itself contain block-level elements (paragraphs, display math, code blocks). Any
caller that writes `<p><MathText>{...}</MathText></p>` produces an invalid `<div>`-inside-`<p>`
DOM nesting. The browser silently "fixes" this by closing the `<p>` early, which differs from
what React's virtual DOM expects, and throws exactly this error in the console at hydration time:
```
In HTML, %s cannot be a descendant of <%s>. This will cause a hydration error. <p>
```
**Fix:** always wrap `<MathText>` in a `<div>` (or nothing, if the parent is already a `<div>`),
never a `<p>`. The same rule applies to `<span>` (an inline element) wrapping `<MathText>` — also
invalid HTML, use a `<div>` there too even if the visual intent is an inline-looking label (use
flex layout on the div instead, e.g. `<div className="d-flex gap-1">`).

## 27. A long-running `mathbank-rest` dev server started without `--reload` will not pick up new routers/migrations — restart via `make stop && make start`

Confirmed live (requirements/53): a `mathbank-rest` dev server left running from an earlier
session (started as a plain `uvicorn mathbank_rest.main:app --app-dir src --port 8000`, no
`--reload` flag — not matching the Makefile's own `make run` target, which does include
`--reload`) silently 404'd every new endpoint added in this session (`/v1/quiz/*`) until
explicitly restarted. Before concluding a new endpoint/router registration is broken, check
whether the currently-running dev server process actually has `--reload` in its command line
(`ps aux | grep uvicorn`) — if not, `make stop && make start` (or `make run` in the foreground)
picks up the change immediately. This is not specific to the quiz feature; it will recur for
any future new router/model-reload-sensitive change made while an old, non-reloading server
instance is still running.


## 28. A leading JSDoc comment line left over from a block replacement can silently swallow the *next* `const`/function declaration into a dangling, unterminated `/** ... */` comment

Hit live while implementing requirements/47's `GradableItem` adapter in
`mathbank-web/app/learn/courses/[code]/page.jsx`: an `edit` replaced the old `QuizActivity`
function body but left its original one-line docblock opener (`/** Interactive preview quiz
question (MCQ/NUMERIC). Grades locally against the`) directly above the *new*
`LEARNING_ITEM_PURPOSE_LABELS` constant, with no matching `*/` anywhere before it. JS/JSX
comments don't nest — the parser kept consuming source (including the entire `const
LEARNING_ITEM_PURPOSE_LABELS = {...}` object and the next function's own opening docblock
line) until it hit the *first* real `*/` several lines later, which happened to belong to a
different, later docblock. The swallowed `const` never executed, producing a runtime-only
`ReferenceError: LEARNING_ITEM_PURPOSE_LABELS is not defined` the moment the component using it
rendered — `next build` and the dev server's own compile step both stayed silent because the
result was still syntactically valid JS (an oversized comment, not a parse error). **Lesson:**
after any edit that removes a block preceded by its own `/** ... */` docblock, explicitly check
the one or two lines immediately above the edit for an orphaned opener line with no closing
`*/` — `grep -n '/\*\*\|\*/' <file>` and eyeball that every `/**` has a `*/` before the next
`/**` is a fast way to catch this; a clean `next build` is **not** sufficient evidence the
comment structure is intact, since a dangling comment is valid syntax, not a build error.

## 29. An unkeyed stateful component rendered at the same JSX position for *different* data items leaks state across items — use `key={itemId}` to force a remount

Hit live in the same requirements/47 work: `SequencedStepContent` renders one `GradableItem`
(or `AssetMedia`/`InteractionTemplateRenderer`) per current sequenced item, swapped in place as
`itemIndex` changes — but without a `key` prop, React treats it as the *same* component
instance across renders (same type, same JSX position) and keeps its internal state (`result`,
`selectedIndex`, `numericValue`) instead of resetting it. Confirmed live: after giving up on
item 1 (a `learning_item`), clicking "Next item" to item 2 (an unrelated `activity`) rendered
item 2's own fresh MCQ options as already-disabled, because `result` from item 1 was still set
on the reused fiber. **Fix:** always pass `key={<stable item/content id>}` on any per-item
child component whose own `useState` must reset when the "current item" changes — matches the
existing pattern already used one level up for `SequencedStepContent` itself
(`key={activeState.state_id}`) to reset progress when the *state* changes.

## 30. A section's `layout.jsx` can already render the one shared `<PageHeader>`/`<h1>` for every page beneath it — a per-page "add a missing PageHeader" fix can silently create a duplicate heading

Hit live while implementing requirements/48 (site-wide UX audit) across `mathbank-web/app/db/*`
and `mathbank-web/app/graph/*`: both sections have a `layout.jsx` (`app/db/layout.jsx`,
`app/graph/layout.jsx`) that already renders one `<PageHeader>` for the whole section (plus a
`NavTabs` sub-nav), confirmed by a static audit that only read individual `page.jsx` files was
genuinely missing: the audit correctly saw no `PageHeader` import in `db/concepts/page.jsx` (for
example) but had no visibility into the sibling `layout.jsx` that actually supplies the section's
single `<h1>`. Delegated fix work that followed the audit's literal "add a PageHeader here"
instruction added a **second** `<PageHeader>` (and therefore a second `<h1>`) on five `db/*`
pages and two `graph/*` pages — caught only by `e2e/public.spec.mjs`'s strict-mode
`getByRole("heading", { level: 1 })` lookup failing with "resolved to 2 elements," and would have
shipped silently on the `graph/*` pages (whose heading text isn't asserted by any e2e spec).
**Lesson:** before adding a `PageHeader`/`<h1>` to any `page.jsx`, check for a `layout.jsx` in the
same directory (and any parent directory) that might already render one for the whole route
group — `find app -iname layout.jsx | xargs grep -l PageHeader` is a one-line way to see every
section that already owns a shared header. If a page's own title is still worth surfacing
distinctly (e.g. `graph/[rel]/page.jsx`'s per-relationship name), demote it to an `<h2>`
sub-heading or plain text instead of a second `PageHeader`/`<h1>`, and re-run `e2e/public.spec.mjs`
(or at minimum manually grep the rendered page for more than one `<h1`) before considering the
change done — a clean `next build` does not catch a duplicate-heading regression.

## 31. `FastMCPApp` must be fully constructed and decorated *before* `FastMCP(..., providers=[...])` is built — there is no `.mount()` path for a `Provider`

Hit live while building `mathbank-mcp-competitions` (requirements/49's first implementation). The
intuitive pattern — build `mcp = FastMCP("name")` first, then attach Prefab UI apps to it the way
you'd mount a sub-server — does not exist for `FastMCPApp`. `FastMCP.mount()` is for composing two
full `FastMCP` server instances together (e.g. a gateway aggregating several MCP servers); a
`FastMCPApp` is a `Provider`, and the only way to attach one is to pass it at construction time via
`FastMCP(name, providers=[app])`. Since a `FastMCPApp`'s `@app.tool()`/`@app.ui()` decorators mutate
the app object in place, the app must be fully built — every tool and `.ui()` entry point already
decorated onto it — *before* that `FastMCP(...)` call, not after. This drove `server.py`'s file
layout: the `FastMCPApp` and all its decorated functions come first, `mcp = FastMCP(...,
providers=[competitions_app])` is constructed next, and only then do the plain `@mcp.tool()`
functions get defined (order doesn't matter for those, since they decorate the already-built `mcp`
object directly). **Lesson:** when adding a `FastMCPApp`/Prefab `.ui()` surface to an existing
`FastMCP` server, check whether the server object is already constructed elsewhere in the file —
if so, the app must be moved above that construction line, not just decorated wherever is
convenient.

## 32. Prefab `Select`'s `value` field does not accept a reactive `Rx` binding — use `name=` + per-`SelectOption(selected=...)` instead; and never debug a Prefab component tree via a bare `.model_dump()`

Two related `prefab_ui` (0.20.2) gotchas found while building the same competition-explorer Prefab
UI:

1. Most Prefab fields that look reactive — `DataTableColumn.rows`, `Badge.label`,
   `SelectOption.value`/`.label` — genuinely do accept an `Rx(...)` binding. `Select.value` is the
   exception: it's typed `str | None`, a plain form-field value, not a reactive prop. Passing
   `Select(value=Rx(STATE.competition))` fails type validation. The correct pattern (confirmed by
   grepping `prefab_ui`'s own bundled `field.py`/`form.py`, which never bind `value=Rx(...)` on a
   `Select`) is `Select(name="competition")` plus computing `selected=(code == competition)` on each
   `SelectOption` server-side at render time — the form's `name` is what ties the selected value
   back to state on submit, not a live reactive binding on the widget itself.
2. Calling `.model_dump()` directly on a returned `PrefabApp`/`Column` Python object in a quick
   debug script can make the component tree look broken — nested children appear to show only
   `id`/`css_class`/`on_mount` with no `type`, as if they collapsed to base `Component` placeholders.
   This is **not a real bug**; it's an artifact of pydantic's default polymorphic-list serialization
   not resolving subclass fields without `prefab_ui`'s own custom serializer path. The actual
   wire-format output — what any real MCP host or test actually receives — is correct and complete;
   confirmed by calling through `fastmcp.Client.call_tool(...).structured_content`, which showed the
   full, correctly nested tree. **Lesson:** always verify a Prefab component tree via a real
   `fastmcp.Client` call, never via a bare `.model_dump()` on the Python object in a REPL/debug
   script — the latter is not representative of the real protocol output and will send you chasing
   a bug that doesn't exist.

## 33. An LLM asked to author a SceneSpec will use plausible-but-wrong field names (`"text"` instead of `"label"`) and leak LaTeX into plain-text fields — a loose, future-proof JSON Schema cannot catch this; a second, stricter layer must

Hit live while building `mathbank-manim-studio`'s research agent (requirements/60). The
SceneSpec JSON Schema (`scene_spec.schema.json`) is deliberately loose —
`additionalProperties` unconstrained on objects/timeline entries — so it can grow to
ITL-4's full future object/action vocabulary without a schema migration every time. That
looseness means a model-generated SceneSpec that uses `"text"` where the compiler expects
`"label"` (or vice versa) passes the schema cleanly and silently renders as empty text,
not an error. Separately, the same model put raw `\(...\)` LaTeX delimiters inside a
plain `TEXT` object's label (which renders via `Text(...)`, not `MathTex(...)`) — again
schema-valid, again silently wrong (garbled literal backslashes on screen, not a crash).
**Lesson:** when an LLM authors a payload against a deliberately loose, extensible
schema, layer a second, stricter, *implementation-specific* validator on top that checks
exactly what the current renderer/compiler actually consumes (required field names per
type, and content-shape heuristics like "a backslash command does not belong in a
plain-text field") — and wire real validation failures back into an automatic one-shot
repair turn, not just a one-time check. Caught by rendering the model's actual output and
visually inspecting an extracted frame, not by unit-testing the JSON Schema check alone.

## 34. `subprocess.run(["manim", ...])` resolves against the invoking shell's `PATH`, not the active project's `.venv` — spawn `[sys.executable, "-m", "manim", ...]` instead

Hit live in the same project: a bare `"manim"` argv0 raised `FileNotFoundError` the
moment the render function was called from a process whose `PATH` didn't happen to
include the venv's `bin/` (true for almost any real caller — a different shell, a test
runner, `uvicorn` started by a Makefile target). Spawning
`[sys.executable, "-m", "manim", ...]` instead always resolves against the same
interpreter the calling code is already running under, regardless of `PATH` or which
shell launched the parent process — the same fix category as GOTCHAS.md's general
"don't assume a bare binary name on PATH" lesson, concretely encountered here for manim.

## 35. A service-layer function with keyword-only parameters (`def f(conn, *, a, b)`) silently breaks a generic `_call(fn, *args)` router wrapper — pass a lambda, not positional args

Hit live while wiring `mathbank-rest`'s scene-catalog-promotion endpoints
(requirements/60 §7): `interaction_templates.py`'s existing `_call(operation, *args)`
helper (`return operation(conn, *args)`) has always worked for every prior service
function in that file because they all took purely positional arguments after `conn`.
`scene_spec_promotion.promote_render_job(conn, *, render_job_id, canonical_code,
created_by)` was deliberately written with keyword-only parameters (to make call sites
self-documenting), which raised `TypeError: promote_render_job() takes 1 positional
argument but 4 were given` the moment the router tried `_call(promote_render_job,
request.render_job_id, request.canonical_code, request.created_by)` — caught immediately
by a live end-to-end test (not a type checker, since `_call`'s signature is generically
typed as `*args`). **Fix:** wrap the call in a lambda —
`_call(lambda conn: promote_render_job(conn, render_job_id=..., canonical_code=...,
created_by=...))` — whenever the target function uses keyword-only parameters; a
positional-args-forwarding wrapper like `_call` can never support them directly.

## 36. This environment's FastAPI build lazily wraps `include_router()` results as `_IncludedRouter`, not flattened `APIRoute` objects — `app.routes` introspection in a plain Python REPL undercounts real routes; always verify via the live OpenAPI schema or a running server instead

Hit live while confirming new scene-promotion routes were registered: a quick
`from mathbank_rest.main import app; [r.path for r in app.routes]` sanity check showed
only 7 routes (just `/health`/`/docs`/etc.) even though `main.py` correctly calls
`app.include_router(...)` 26 times and the router objects themselves had the expected
routes when inspected directly. `Counter(type(r).__name__ for r in app.routes)` revealed
the real shape: 26 `_IncludedRouter` wrapper objects (not standard Starlette/FastAPI
`APIRoute`s), meaning this environment's installed FastAPI build defers resolving
included-router paths until ASGI dispatch/startup, not at `include_router()` call time.
**This is not a bug in application code** — it is specific to this sandbox's FastAPI
build and does not reflect how a real deployed FastAPI app behaves. **Lesson:** don't
debug "are my routes registered?" via bare `app.routes` introspection in a throwaway
script in this environment — restart the real server and check `curl .../openapi.json`
(or hit the endpoint directly), which is authoritative regardless of how a given FastAPI
build internally represents routers before first dispatch.

## 37. Two services sharing one physical Postgres instance still cannot see each other's *uncommitted* writes — a cross-service callback that depends on a just-inserted row needs the local transaction committed *before* firing, not just before returning

Hit live while wiring promoted scenes into `interaction_instance` (requirements/60 §7):
`scene_spec_promotion.promote_render_job` inserted a new `visual.scene_spec` row, then
(while still inside the same, not-yet-committed `conn`) called
`mathbank-manim-studio`'s `POST /v1/render-jobs/{id}/mark-promoted` endpoint — which
writes `promoted_scene_spec_id` into *its own* `studio.video_render_job` row, guarded by
a real foreign key into `visual.scene_spec` (migration 045). That FK check runs on
manim-studio's own, separate database connection, which — exactly as Postgres MVCC
guarantees — cannot see mathbank-rest's just-inserted row until mathbank-rest's
transaction actually commits. The result was a silent, swallowed failure (caught by a
deliberately permissive `except httpx.HTTPError: pass`, since the peer service's own flag
was designed to be best-effort) — `promoted_scene_spec_id` stayed `NULL` even though the
promotion otherwise fully succeeded. Caught by explicitly asserting the peer service's
state after the call completed, not just asserting the local 200 OK. **Fix:** restructured
`promote_render_job` to own its own `engine.begin()` block for the local INSERT work,
so the `with` block's normal exit commits *before* the cross-service HTTP call fires,
rather than accepting an externally-managed `conn` whose commit timing the function
doesn't control. **Lesson:** whenever a function's job is "write locally, then tell
another service about it," the local write must be verifiably committed (not merely
`execute()`'d) before the cross-service call — "same physical database" does not mean
"same transaction," and an uncommitted row is invisible outside its own transaction no
matter how physically close the two connections are.

## 38. A locally-invented object-storage URI scheme (`object://key`) will silently diverge from the one the rest of the codebase already uses (`object-store:key`) — grep for the real prefix before inventing a new one

Hit live in the same feature: `scene_spec_promotion.py` wrote `visual.asset.uri` as
`f"object://{key}"`, which *looked* like a reasonable URI scheme and worked fine for the
admin-only read path this feature wrote first (both the writer and that one reader used
the same self-consistent, if non-standard, prefix). It silently broke the moment a
different, pre-existing function (`micro_course_service.get_published_asset`, the
student-facing asset-serving path) checked `asset["uri"].startswith("object-store:")` —
a single-colon, no-double-slash convention used everywhere else in `mathbank-rest`
(`corpus_authoring.py`, `micro_course_service.py`, `step_runtime.py`). **Lesson:** before
writing a new `visual.asset.uri`/similar convention-bearing value, `grep -rn
"object-store:"` (or whatever the established prefix is) across the codebase first —
an internally-consistent-but-wrong convention won't fail until a *different*,
pre-existing code path tries to read it, which can be much later and much harder to
trace back to the actual mistake.

## 39. GitHub's Mermaid renderer is stricter than this environment's local Mermaid preview — several patterns that preview fine locally fail to render on GitHub

Hit live writing the README's Architecture and Data-model sequence diagrams. The local
`mermaid-diagram-preview` tool rendered every one of these without complaint; GitHub's
renderer rejected them with real parse errors once pushed. Three confirmed-fragile
patterns so far, all specific to **unquoted, raw message/label text** in
`sequenceDiagram` (not inside a quoted string, and not in diagram types like
`C4Container` whose labels are always quoted strings):

1. **Parentheses in a `participant`/`actor` alias**, e.g.
   `participant WEB as mathbank-web (admin UI)`.
2. **A literal `->` inside message text** (not as an arrow token), e.g.
   `scene_spec -> APPROVED`.
3. **Curly-brace pseudo-code placeholders in message text**, e.g.
   `POST /v1/research-jobs {topic}`.
4. **A semicolon inside `Note over X: ...` text**, e.g.
   `Note over ETL,Neo: Rebuildable any time; zero diff on repeated runs` — GitHub's
   parser error was a `NEWLINE`-expecting-an-arrow-token error pointing at the *next*
   statement, because the `;` silently terminated the `Note` statement early and
   merged the remainder with the following line. Fixed by replacing `;` with `,`.

**Lesson:** local Mermaid preview success does not guarantee GitHub rendering success.
Before relying on the local preview tool as a final check, scan unquoted
`sequenceDiagram` message/note/alias text for `(`, `)`, `->`, `{`, `}` and `;` and
rewrite around them (commas, "and", spelled-out words) — these are the specific
characters GitHub's parser has repeatedly tripped on in this repo, even though they are
individually harmless prose punctuation everywhere else in the same README.

## 40. A `sys.path.insert(0, Path(__file__).resolve().parents[N] / "sibling-dir")` import trick only works for an *editable* (`pip install -e .`) checkout — a real (non-editable) install, like a Lambda container image, resolves `parents[N]` to somewhere inside the Python installation, not the monorepo

Hit live deploying `mathbank-rest` to a Lambda container image (requirements/62-63).
Two modules used this exact pattern to reach a sibling `mathbank-scripts/*.py` file
that isn't an installed package: `project_credentials.py` (`configure_openai`, reaching
`project_env.py`) and `db/retrieval_audit.py` (reaching `power_geometry_evidence.py`).
Both work perfectly in every local dev/test run, because `make install` always installs
`mathbank-rest` editable (`pip install -e .`), which preserves the real source-tree
depth that `Path(__file__).resolve().parents[N]` assumes. A genuine `pip install .`
(non-editable — required for any container image, and for any deployment outside this
specific monorepo checkout) installs the package into `site-packages` at a completely
different depth, so `parents[N]` silently resolves to a nonsensical path and the import
fails with a plain `ModuleNotFoundError`, not a path-related error that would hint at
the real cause.

**Fixes applied** (two different shapes, matched to what each case actually needed):
- `configure_openai()`: the goal was *credentials*, and deployed environments already
  provide `OPENAI_API_KEY` as a real process environment variable — added an
  env-var-first short-circuit, falling back to the existing sibling-import trick
  unchanged (still exercised by every local dev/test run, since a bare env var isn't
  normally set locally).
- `retrieval_audit.py`: the goal was *application logic* (regex constants, zero external
  deps), not a secret — added a `try: <existing sibling import> except ImportError:
  <fall back to a small vendored copy inside mathbank_rest/_vendor/>`, keeping the real
  monorepo source as the editable-dev source of truth and the vendored copy as a
  manually-synced fallback for installed/non-monorepo deployments.

**Lesson:** any `sys.path.insert` keyed off a hardcoded `parents[N]` depth is implicitly
asserting "this package is always installed editable, from this exact checkout" — grep
for this pattern (`parents\[\d\]`) before any non-editable packaging/deployment attempt,
not after it fails.

## 41. `httpx` was declared only under a package's `dev` extras, even though production route code imports it directly — invisible locally because `make install` always installs `.[dev]` too

Hit live in the same Lambda deployment: `mathbank-rest/pyproject.toml` had
`httpx>=0.27` listed under `[project.optional-dependencies] dev`, alongside `pytest`/
`ruff`/`mypy` — but `routers/interaction_templates.py`, `route_batch.py`,
`route_ollama.py` and `scene_spec_promotion.py` all `import httpx` directly in
non-test, non-dev production code. A Lambda container image installs only
`dependencies` (the base/runtime group), not `.[dev]` — so this was a real, pre-existing
packaging bug, not a Lambda-specific quirk; it just had never been exercised before
because `mathbank-rest/Makefile`'s `install` target always runs `uv pip install -e
".[dev]"`, so every local dev venv and every CI/test run had `httpx` present by
accident. **Fix:** moved `httpx` into the base `dependencies` list. **Lesson:** a
dependency installed only via `dev`/test extras but imported by non-test production code
is latent breakage waiting for the first deployment path that doesn't install those
extras — grep each heavy/optional-looking import (`httpx`, `pytest`, mocking libraries)
against where it's actually imported *from*, not just whether `pip install -e ".[dev]"`
happens to make it available today.

## 42. CloudFormation rejects an `{{resolve:ssm-secure:...}}` dynamic reference inside `AWS::Lambda::Function`'s `Environment.Variables` — confirmed live via CDK's own template-validation warning (rule E1027)

Hit live wiring secrets (`POSTGRES_PASSWORD`, `OPENAI_API_KEY`, etc.) into the
`mathbank-rest` Lambda stack (requirements/62-63). The natural-looking CDK pattern —
`aws_cdk.aws_ssm.StringParameter.value_for_secure_string_parameter(...)` (or the newer
`SecretValue.ssm_secure(...)`) passed straight into a `DockerImageFunction`'s
`environment={...}` dict — synths without error, but `cdk deploy` surfaces a template-
validation warning: *"Dynamic reference '{{resolve:ssm-secure:/...}}' to SSM secure
strings can only be used in resource properties"* (rule `E1027`). This is a real,
documented CloudFormation constraint: `ssm-secure` dynamic references are supported in
specific resource properties (e.g. an RDS `MasterUserPassword`, an ECS task
definition's `secrets` list) but **not** in a plain Lambda environment-variable value —
deploying anyway risks the Lambda actually receiving the literal, unresolved
`{{resolve:...}}` string rather than the real secret, silently breaking the app instead
of failing loudly.

**Fix:** the standard AWS pattern for this exact situation — fetch secrets from SSM
*inside the Lambda function itself*, once at cold start, before importing the real
application module (`lambda_handler.py`'s `_load_secrets_from_ssm()`, called before
`from mathbank_rest.main import app`), using only plain (non-secret) environment
variables to tell it *which* parameters to fetch and *where* to put them
(`MATHBANK_SSM_PREFIX`, `MATHBANK_SECRET_MAP`), with the function's execution role
granted `ssm:GetParameter` on exactly those parameter ARNs (least privilege, via CDK's
`add_to_role_policy`). **Lesson:** a CDK pattern that synths cleanly can still fail at
`cdk deploy` with a CloudFormation-specific resource-property constraint that CDK's own
type system doesn't prevent — always run a real `cdk deploy` (not just `cdk synth`)
against a scratch/dev stack before assuming a secrets-wiring pattern works, and read
`cdk deploy`'s own template-validation warnings, not just its final success/failure line.

## 43. A whole-directory `COPY <service-dir> ${LAMBDA_TASK_ROOT}/` in a Lambda Dockerfile bakes the real local `.env` (secrets and all) into the pushed container image, unless explicitly excluded

Hit live deploying `mathbank-agent` to Lambda (requirements/62-63): unlike
`mathbank-rest` (which does a scoped `pip install` of just its Python package —
`.env` was never part of the install), `mathbank-agent` has no installable package
structure, so its `Dockerfile.lambda` did `COPY mathbank-agent ${LAMBDA_TASK_ROOT}/` —
a literal whole-directory copy. The repo root's `.dockerignore` existed but did **not**
list `.env`, so the real `mathbank-agent/.env` (actual `POSTGRES_PASSWORD`,
`OPENAI_API_KEY`, etc.) was copied straight into the image, pushed to ECR, and
deployed. The immediate symptom was a crash, not a quiet leak: the file kept its host
permissions (`-rw-------`, 0600, owner-only) through the `COPY`, and the Lambda
runtime's execution user couldn't read it, so `session_config.py`'s
`dotenv_values(ROOT / ".env")` raised `PermissionError: [Errno 13] Permission denied`
at cold-start module-import time — but had the permissions merely been more permissive,
the real secrets would have been silently baked in and successfully read, with no
crash at all to notice.

**Fix:** exclude `.env`/`.env.*` (keeping `.env.example`) in the root `.dockerignore`
globally — `**/.env`, `**/.env.*`, `!**/.env.example` — so this is impossible for
*every* service's Dockerfile, not just the one that happened to crash. **Lesson:** a
whole-directory `COPY` is categorically riskier than a scoped package install for
secret hygiene; if a service's Dockerfile must use whole-directory `COPY` (no
installable package structure), treat `.dockerignore` coverage of `.env*` as
load-bearing, not optional — and don't assume "no crash" means "no leak": verify
directly with `docker run --entrypoint sh <image> -c "ls /var/task/.env*"` on every new
image, and if a non-compromised digest already exists with the fix, delete the
compromised digest from ECR (`aws ecr batch-delete-image`) rather than just letting the
Lambda's pointer move on — the old image blob persists in the registry until deleted.

## 44. `DockerImageCode.from_image_asset(directory=REPO_ROOT, ...)` does not reliably honour the root `.dockerignore` for its own asset-staging copy — pass `exclude=[...]` explicitly, especially to exclude `cdk.out` itself

Hit live redeploying after fixing gotcha #43 above: `cdk deploy` failed with
`ENAMETOOLONG: name too long, mkdir '.../cdk.out/asset.<hash>/mathbank-infra-aws/
cdk.out/asset.<hash>/mathbank-infra-aws/cdk.out/...'` — a self-nesting, exponentially
deepening directory structure. This happens because CDK's `from_image_asset()` stages
a copy of the Docker build context (here, the whole repo root) into
`mathbank-infra-aws/cdk.out/asset.<hash>/` *before* invoking `docker build` — and if
`cdk.out` (which lives inside the build context, under `mathbank-infra-aws/`) is not
excluded from that staging copy, the walk visits the very directory it is currently
writing into, re-copying it into itself. Deleting `cdk.out/` entirely and re-running
`cdk deploy` did **not** fix it — the recursion reproduced within a single fresh synth,
proving the root `.dockerignore` (which did list `**/cdk.out/`) was not being applied
to this particular staging-copy step at all, regardless of CDK version/ignore-mode
defaults.

Passing `exclude=[...]` explicitly to `from_image_asset()` (even with `/**`-suffixed
recursive patterns like `"**/cdk.out/**"`) reduced but did **not** eliminate the bug: a
`cdk synth` against a freshly-emptied `cdk.out/` succeeded, but the very next
`cdk deploy` — which internally re-runs `app.py` and, because multiple stacks each call
`from_image_asset(directory=REPO_ROOT, ...)` in the same process, starts its *second*
internal synth pass with the *first* stack's own just-written `cdk.out/asset.<hash>/`
already on disk — still recursed. The exclude patterns were not reliably protecting
against this self-referential copy regardless of how they were written.

**Real fix:** don't fight it — stop giving `from_image_asset()` a `directory` that
contains `cdk.out` at all, wherever the service doesn't actually need the repo root
(e.g. `mathbank-agent` has no sibling-package dependency, so its stack now points
`directory` at `mathbank-agent/` itself, with its own small `.dockerignore`, never
touching `mathbank-infra-aws/cdk.out`). For the one service that *does* need repo-root
context for a real sibling dependency (`mathbank-rest`, reaching
`mathbank-geometry-engine`), make `rm -rf cdk.out` an unconditional prerequisite of
`make synth`/`make deploy`/`make diff` (a `clean-cdk-out` Makefile target), so that
directory genuinely never has prior content to recurse over. **Lesson:** when a CDK
app's own `cdk.out` lives inside the same tree used as a Docker build context, treat
`exclude` patterns as a secondary defense, not the primary fix — the primary fix is
to keep `cdk.out` out of the build context's reach in the first place (scope the
`directory` to the smallest real dependency boundary per service) and to never run a
synth/deploy against a `cdk.out` that might already contain output from an earlier,
same-run stack construction.

## 45. A FastMCP server's `.run(transport="http")` blocks forever running its own Uvicorn — use `.http_app(stateless_http=True)` for an ASGI app Mangum can wrap, and force `Mangum(app, lifespan="on")`

Hit live deploying `mathbank-mcp-competitions` to Lambda (requirements/62 §4.5,
requirements/63). The service's existing local-dev HTTP entrypoint
(`__main__.py`: `mcp.run(transport="http", port=...)`) is not usable in a Lambda
handler — it's a blocking call that starts and owns its own Uvicorn server loop, never
returning an importable ASGI app. `FastMCP.http_app(...)` is the correct call instead:
it returns a plain `Starlette` ASGI app, usable exactly like any other ASGI app.

Two non-obvious settings are required, not just the call itself:
- `stateless_http=True` — the MCP streamable-HTTP transport's *default* mode is
  stateful (a client is expected to resend an `Mcp-Session-Id` header and reconnect to
  the *same* server process across a tool-call sequence), but Lambda offers no such
  process affinity across requests — a second request may hit a different warm
  execution environment, or a cold one. Stateless mode creates a fresh in-memory
  session per request, the only mode compatible with Lambda's request model.
- `Mangum(app, lifespan="on")`, not Mangum's default `lifespan="auto"` — FastMCP's
  Starlette app relies on its ASGI lifespan (startup/shutdown) to initialise its
  session-manager task group; Mangum's `"auto"` heuristic does not reliably detect this
  need for Function-URL-sourced events (it is tuned around API Gateway's event shapes),
  so lifespan handling must be forced on explicitly or the server silently never
  finishes initialising its session machinery.

**Verified live:** a real `curl` `initialize` JSON-RPC call against the deployed
Function URL returned a correct MCP handshake response (`protocolVersion`,
`capabilities`, `serverInfo`), and a real `tools/call` for `list_competitions`
round-tripped through to the already-deployed `mathbank-rest` Lambda and back.
**Separate, expected (not a bug) observation:** the very first such call, with both
Lambdas simultaneously cold, hit the downstream `httpx` client's 15s timeout
(`rest_client.py`) — a cold-calling-cold chain across two Lambdas can exceed a
conservative per-call timeout that was tuned assuming an always-warm REST backend;
retrying (second Lambda now warm) succeeded immediately. Worth widening that timeout
or accepting occasional cold-chain retries in a low-traffic dev environment, but not
something to "fix" by changing the MCP/Lambda wiring itself.

## 46. colima's VM disk defaults to `~/.colima` on the *internal* disk and will not surface its own root cause when the host fills up — it silently corrupts containerd's content-addressed blob store instead of erroring cleanly

Hit live mid-build of `mathbank-manim-studio` (requirements/63): a `docker build` step
failed with a plain "disk I/O error", and a subsequent `docker info`/`docker images`
failed with `failed to retrieve image list: ... blob sha256:... expected at
/var/lib/containerd/.../blobs/sha256/...: input/output error`. The error message
points at containerd's content store, not at "your Mac is almost out of disk" — the
actual root cause (confirmed via `diskutil apfs list` / `df -h`) was the host's
internal "Data" APFS volume sitting at ~117–132MB free out of 228GB, mostly consumed
by unrelated Xcode iOS/watchOS Simulator runtime disk images (~43–55GB, each its own
APFS container layered on a disk-image file) that had nothing to do with this project.
Once a write to colima's qcow-backed containerd blob store failed partway through
(disk full), the blob was left truncated/corrupt on-disk permanently — restarting
colima did **not** self-heal it; the only fix was deleting the VM's data entirely.

**Fix applied, not just a one-time recovery:** rather than only deleting and
recreating `~/.colima` (which puts the VM disk right back on the already-tight
internal volume), relocate colima's entire VM data directory to the external disk via
the `COLIMA_HOME` environment variable (persisted in `~/.zshrc`):
```bash
export COLIMA_HOME="/Volumes/External/colima-home"
colima stop        # old instance, if still salvageable
rm -rf ~/.colima    # discard the corrupted VM disk from the internal volume
colima start --cpu 4 --memory 8 --disk 60 --vm-type=vz --mount-type=virtiofs
```
`colima start` recreates `$COLIMA_HOME/default/{docker,containerd}.sock` and the VM
disk image under the new location on first run — no other config file needed. This is
the same project-data-belongs-on-the-external-disk principle already applied to the
repo itself; a Docker VM disk that can grow to tens of GB building multiple Lambda
container images (Cairo/Pango/TeX Live in particular) should never share the
already-constrained internal volume. **Verified live:** `docker run --rm hello-world`
succeeded immediately after the relocated restart, and `/Volumes/External/colima-home`
began accumulating image-layer data while `df -h /System/Volumes/Data` stayed flat.

## 47. A local dev server left running against the SAME shared production database as a newly-deployed Lambda will silently steal and mis-process its job queue — "it's DONE in the DB" does not mean "it ran where you think it ran"

Hit live deploying `mathbank-manim-studio`'s worker Lambda (requirements/60,
requirements/63): a render job created via the live Function URL reached `status: DONE`
with a plausible `video_object_key` and `video_duration_ms` within ~90 seconds, yet
fetching the video returned `500 Internal Server Error`, and `boto3.head_object` against
the real S3-compatible bucket confirmed the key genuinely did not exist — not an
eventual-consistency delay (re-checked 15+ minutes later, still absent). `aws logs
filter-log-events` against the *exact* timestamp window the job completed in showed only
17-24ms worker Lambda invocations in that window — nowhere near long enough to run a real
Manim + LaTeX + ffmpeg render (empirically 1.6s-47s depending on scene complexity) — yet
the row was indisputably marked `DONE`.

Root cause: `ps aux` found a **local `uvicorn mathbank_manim_studio.main:app`
process from an earlier session still running** on the dev machine. `main.py`'s FastAPI
`lifespan` starts an in-process `asyncio` polling loop (`worker.run_worker_loop`,
`worker_poll_seconds: float = 2.0`) exactly as designed for local dev — but this
project's `.env` points at the **same shared production Neon Postgres** the deployed
Lambda uses (no separate local/dev database), and that local process's own `.env` still
has the default `MATHBANK_OBJECT_BACKEND=filesystem`. Polling every 2 seconds, this
stale local process claimed the job (`FOR UPDATE SKIP LOCKED`) *faster than the
EventBridge-scheduled Lambda worker's 1-minute cadence could*, rendered it for real —
just on the local machine, not in Lambda — wrote the video to the **local filesystem
object store**, and marked the row `DONE` in the shared database, all correctly from the
local process's own point of view. Nothing in Lambda was ever broken; the deployed
worker simply never got a chance to claim that row.

**Fix:** `kill <pid>` the stale local process; re-tested the identical scene end-to-end
through the Function URL alone and it completed correctly (confirmed via `aws logs tail`
showing a real multi-second `REPORT` duration for that invocation, and a real `200 OK` +
valid `ftypisom` MP4 magic bytes on fetch). **General lesson, not manim-studio-specific:**
any service whose local dev loop is a *singleton polling/claim consumer* (not a
stateless request/response API) is unsafe to leave running locally once that same
service is also deployed against the same shared database — the two will race for the
same rows, and the deployed copy will look silently, totally idle while the local one
absorbs all the work. Plain REST services (`mathbank-rest`, `mathbank-ml-inference`)
don't have this failure mode — concurrent local + deployed instances just serve
independent reads/writes, they don't compete to "claim" anything — so this is specific
to queue/worker-shaped services.

## 48. A valid Bedrock bearer token/IAM session and a successful `list_foundation_models()` call do not mean Bedrock *invocation* actually works on that account — "Error 002: Access to Bedrock models is not allowed for this account" is a genuine, account-level restriction, not a model-ID or region problem

Hit live building `mathbank-exam-agent` (requirements/64): every attempt to actually call
a Bedrock model — via the AWS Strands Agents SDK's `BedrockModel`, using the
`AWS_BEARER_TOKEN_BEDROCK` already present in the root `.env` — failed identically:
```
botocore.errorfactory.ValidationException: An error occurred (ValidationException) when
calling the ConverseStream operation: Error 002: Access to Bedrock models is not allowed
for this account
```
Confirmed this is **not** a per-model access-grant gap (the usual "request model access
in the Bedrock console" friction most Claude-on-Bedrock guides mention) by trying two
completely different providers' models — `anthropic.claude-haiku-4-5-20251001-v1:0` and
`amazon.nova-2-lite-v1:0` (Amazon's own first-party model, which is not normally gated
behind a separate access request) — both failed with the exact same "Error 002" text.
Also confirmed the credential itself is valid and not the issue: `bedrock.
list_foundation_models()` (a metadata-only call) succeeded fine with the same bearer
token, returning 97 real model entries — only the actual invoke/converse operation is
blocked. This points to an account-level restriction (e.g. Bedrock not yet enabled for
this account/region combination, a billing/payment-verification gate specific to
Bedrock, or an organizational policy), resolvable only via the AWS Console (Bedrock →
Model access page) or AWS Support, not via any code change.

**Fix applied, not a workaround for the restriction itself**: per the user's explicit
instruction, continued with **`strands.models.openai.OpenAIModel`** instead of
`BedrockModel` — confirmed live that the Strands Agents SDK's `Agent`/`MCPClient`/
`agent(prompt, structured_output_model=...)` interface is completely unchanged regardless
of which `Model` backs it, so the actual "AWS agent framework, not Google ADK"
architecture requirement was preserved; only the LLM provider changed. Isolated this
choice to three small factory functions (`llm_models.py`) so swapping back once Bedrock
access is resolved touches no other file. **Separate, smaller finding from the same
investigation**: `Agent.structured_output(Model, prompt)` is deprecated in the installed
SDK version (`strands-agents==1.59.0`) in favour of
`agent(prompt, structured_output_model=Model)` — the deprecation warning names the
replacement directly; worth using the non-deprecated form from the start rather than
hitting the warning mid-project.

## 49. A new service's `.env` using lowercase keys (fine for the app itself — pydantic-settings matches env vars case-insensitively) silently breaks a CDK stack's own case-sensitive `env_values.get("UPPERCASE_KEY")` lookup — no error, just an empty `present_secrets`/`plain_env_vars` result

Hit live deploying `mathbank-exam-agent` (requirements/64): the new
`exam_agent_service_stack.py` built and deployed cleanly, with no synth/deploy error at
all, yet every request needing `ADMIN_API_KEY` failed with a clean-looking (but wrong)
`401 invalid admin API key` — not a crash, just silently always-wrong. Root cause: this
service's `.env` uses lowercase keys (`admin_api_key`, `openai_api_key`, …), unlike every
other service's `.env` in this repo (always uppercase). The stack's own
`SECRET_KEY_TARGETS = {"ADMIN_API_KEY": "ADMIN_API_KEY", ...}` dict and `_parse_env_file()`
helper did a plain case-sensitive `env_values.get("ADMIN_API_KEY")` — which found nothing
in a dict keyed by `"admin_api_key"` — so `present_secrets` came back `{}`,
`grant_and_map_secrets()` short-circuited (`if not secret_to_target: return {}`), and the
Lambda's `MATHBANK_SECRET_MAP`/`MATHBANK_SSM_PREFIX` env vars were simply never set. The
app itself never errors on a missing secret — it just reads the field's blank pydantic
default (`admin_api_key: str = ""`) and sends an empty string, which `require_admin_api_key`
correctly (and silently, from the stack's point of view) rejects. `seed_ssm.sh` was
*not* affected by this (it already does a case-insensitive `grep -iE`), which made this
extra confusing: the secrets really were sitting in SSM with the right values the whole
time — this stack's code just never asked for them. **Fix**: normalize every key to
uppercase in `_parse_env_file()` (`values[key.strip().upper()] = ...`), matching
`seed_ssm.sh`'s existing case-insensitive handling, rather than assuming every `.env` in
the repo uses the same casing convention. **General lesson**: when adding a new CDK
stack for a service whose `.env` convention you haven't verified, normalize case
up front — a silently-empty secrets map produces a working-looking deploy and a
clean-looking auth error, not an obvious stack-misconfiguration signal.

## 50. Both ends of a freshly-deployed two-Lambda call chain can cold-start on the very
first real request, and a 15s httpx client timeout tuned for a warm steady-state can
trip before either one finishes — not a hung call, just two sequential cold starts

Hit live deploying `mathbank-exam-agent` → `mathbank-rest` (requirements/64): right
after `cdk deploy` of both stacks, the first `/v1/auth/anonymous` call failed with a raw
httpx `ReadTimeout`/`ConnectTimeout`-mapped exception at almost exactly 15.0s — the exact
value `rest_client.py`'s `_request()` used as its default `timeout`. `mathbank-rest`'s own
Lambda was also freshly redeployed moments earlier, so this specific request paid for
*two* cold starts back to back (exam-agent's own ~3-10s init, plus a network round trip
to a cold-starting downstream Lambda) — comfortably over a timeout sized for an
already-warm steady state. Retrying immediately (both Lambdas now warm) succeeded in
under half a second. **Fix**: raised the default timeout to 30s — enough headroom for a
worst-case simultaneous cold-start cascade without masking a genuinely hung call.
**General lesson**: a client timeout tuned against warm-path latency numbers needs a
deliberate cold-start margin for any call chain that can itself trigger a downstream
Lambda's cold start — the very first request after any deploy is the one most likely to
need it.

## 51. A `DockerImageAsset` built `platform=LINUX_ARM64` (for cheaper Graviton Fargate pricing) still runs on a standard x86_64 task unless `FargateTaskDefinition`'s own `runtime_platform` is set to match — the container fails instantly with `exec format error`, and the task can briefly look RUNNING if you only check `desiredStatus`

Hit deploying `mathbank-web`/`mathbank-live`/`mathbank-ml-frontend` to Fargate
(`fargate_web_stack.py`, this revision of requirements/62): the three
`ecs.FargateTaskDefinition(...)` calls had no `runtime_platform` argument, so CDK left
it at its default (`LINUX`/`X86_64`), while the `ecr_assets.DockerImageAsset(...)` a few
lines later was deliberately built with `platform=ecr_assets.Platform.LINUX_ARM64` (for
the ~20% cheaper Graviton Fargate rate). An ARM64 image launched on an x86_64 task fails
at the container's very first `exec` with `exec format error` — visible only in
CloudWatch Logs, not in `aws ecs describe-services`/`describe-tasks`, both of which can
report the task as `RUNNING` for a few seconds between ECS restart attempts. A start
script polling only `desiredStatus == RUNNING` (set the instant `update-service` is
called) rather than the task's actual `lastStatus`, or not checking logs at all, can read
this as a successful start and then time out confusingly on the next step (e.g. resolving
a public IP that is about to disappear when the task cycles to `STOPPED` again). **Fix**:
`runtime_platform=ecs.RuntimePlatform(cpu_architecture=ecs.CpuArchitecture.ARM64,
operating_system_family=ecs.OperatingSystemFamily.LINUX)` passed to
`FargateTaskDefinition`, matching the image's `platform=` exactly. **General lesson**:
whenever a Fargate task definition and its container image are constructed in two
separate CDK calls, their CPU architectures are two independent settings that silently
default differently (task definition defaults to x86_64; nothing stops you building an
ARM64 image) — always pin both explicitly or grep for both before debugging container
logs as if it were an application bug.

## 52. A Fargate task role, unlike a Lambda execution role built from the same `FargateAppSpec`-style config, needs its own explicit per-app IAM grant for any non-SSM/non-S3 AWS API a container calls — a generic "Fargate app" CDK construct that only wires `ssm:GetParameter` leaves any app-specific SDK call (e.g. Cognito `AdminInitiateAuth`) with zero permissions, failing only at the first real call, not at deploy or container-boot time

Hit deploying `mathbank-web`/`mathbank-live` (both now calling Cognito's
`AdminInitiateAuth`/`AdminCreateUser`/`AdminSetUserPassword`/`AdminGetUser` from
`lib/cognito.js`, same four actions `mathbank-exam-agent`'s Lambda execution role already
had): the container started fine, the homepage returned 200, and `/login` rendered
correctly — the first sign something was wrong was a real login POST returning
`AccessDeniedException: ... is not authorized to perform: cognito-idp:AdminInitiateAuth
... because no identity-based policy allows the cognito-idp:AdminInitiateAuth action`.
The generic `FargateWebStack`/`FargateAppSpec` construct only ever wired
`ssm:GetParameter` (for `fetch-secrets.mjs`'s runtime secret fetch) onto the task role,
since most of this stack's Fargate apps don't call any other AWS service directly — there
was no equivalent of `exam_agent_service_stack.py`'s explicit Cognito policy grant for
the generic multi-app construct. **Fix**: a `needs_cognito: bool` field on
`FargateAppSpec` (`True` only for the two apps that actually call Cognito), conditionally
attaching the same 4-action policy scoped to the one User Pool ARN. **General lesson**: a
shared/generic infra construct's IAM wiring tends to cover only the lowest-common
denominator of what *most* apps using it need (here, SSM) — any app with an extra
AWS SDK dependency needs its own explicit grant added to that construct, and the failure
mode for a missing grant is a normal-looking running container that only errors on the
specific API call, not at deploy time or container startup, making "it's up and the
homepage works" an insufficient smoke test for anything Cognito/IAM-related.

## 53. The AWS CLI's browser-based `aws login` session (`login_session` profile, not classic SSO) silently expires mid-session — every `aws`/`cdk`/`make deploy`/`make fargate-*` command then fails with the *same* generic `Your session has expired. Please reauthenticate using 'aws login'` error, regardless of which API call actually triggered it

Hit mid-session, between one `make fargate-*-start` call and the next: a previously
working `aws ecr describe-repositories` call (and, moments later, `aws sts
get-caller-identity`) both failed with `aws: [ERROR]: Your session has expired. Please
reauthenticate using 'aws login'` — this repo's `~/.aws/config` uses the newer
`login_session = arn:aws:iam::<account>:root` profile shape (AWS CLI's own browser-based
Console-credential login, added for local dev — see the `us-east-1.signin.aws.amazon.com/
v1/authorize?...` URL this project's earlier session used to first set it up), not a
classic IAM-user access-key pair or an IAM Identity Center/SSO profile. Unlike SSO's
`aws sso login`, this flow's session/refresh-token lifetime is comparatively short and
there is **no proactive warning** before every single `aws`/`cdk`-wrapping command (the
`fargate_ctl.sh` script, every `make fargate-*`/`make deploy`/`make seed-ssm` target) just
starts failing identically, whether the underlying call was STS, ECR, ECS, SSM, or
CloudFormation — the error message is generic, not tied to the specific API that
happened to be called first. **Fix**: re-run `aws login --profile aws-sutanu-admin`
(opens a local browser callback; add `--remote` only if working over SSH with no local
browser) — no CDK/stack state is lost, this only affects the CLI's own credentials, not
anything already deployed. **General lesson**: before diagnosing a sudden, otherwise
unexplained failure across *several unrelated* AWS CLI/CDK commands in the same session
(not just one), check `aws sts get-caller-identity --profile <profile>` first — a session
expiry masquerades as whatever command happens to need credentials next, which can look
like a new infra bug if you don't check the simplest explanation first.

## Single-command recreation


```bash
# one-time, from a fresh clone, with OPENAI_API_KEY in root .env:
cp mathbank-db/.env.example mathbank-db/.env           # fill in passwords
cp mathbank-graph/.env.example mathbank-graph/.env
cp mathbank-rest/.env.example mathbank-rest/.env        # match the passwords above
cp mathbank-agent/.env.example mathbank-agent/.env
cp mathbank-web/.env.example mathbank-web/.env

make bootstrap    # installs Postgres+pgvector+Neo4j, loads the corpus,
                  # embeds it, installs mathbank-rest/mathbank-agent/mathbank-web
```

See [DATABASES.md](DATABASES.md) for the day-to-day start/stop commands and
[documentation/copilot-instructions/mathematics-tutor-db-plan/00_implementation_progress.md](copilot-instructions/mathematics-tutor-db-plan/00_implementation_progress.md)
for the full history of what was built and why.
