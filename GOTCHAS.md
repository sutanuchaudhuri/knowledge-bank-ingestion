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

`mathbank_data_ingestion`'s shared PDF splitter keeps the **first** occurrence
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
`mathematics_tutor_db_plan/00_implementation_progress.md` Round 8 follow-ups.

**Takeaway for any new "lookup by taxonomy slug" code**: check whether the
taxonomy is a tree (`knowledge.concept_relation.relation_type = 'HAS_SUBCONCEPT'`)
before assuming a flat tag match is correct — `knowledge.technique` has no
such hierarchy table, so `get_technique_problems` does NOT need this fix.

## 17. Ingestion scripts had no persistent progress record — background runs were invisible after the fact

Every classify/crawl/export script in `mathbank_data_ingestion` printed a
summary to stdout and nothing else. When run via `nohup ... &` (the norm for
anything that takes more than a couple minutes — see the `make etl-remote`/
`make classify-pdf` pattern used throughout this project), that summary is
only in the `/tmp/*.log` file you happened to redirect to, if any — there was
no queryable, persistent record of what ran, when, with what params, or
whether it actually finished vs. got silently killed.

**Fix**: `mathbank_data_ingestion/src/mathbank/db/tracking.py` — an
`IngestionRun` context-manager class that writes one row per script
invocation to a new `ingestion_runs` table in the *existing* `data/mathbank.db`
(no new DB file) plus a full-detail text log under `logs/` (gitignored).
Wired into all 4 local scripts (`crawl_unmapped.py`, `classify_crawled.py`,
`classify_pdf_corpus.py`, `export_classifications_to_csv.py`) at every exit
path. View with `make progress` (`mathbank_data_ingestion/scripts/show_progress.py`).

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
[mathematics_tutor_db_plan/00_implementation_progress.md](mathematics_tutor_db_plan/00_implementation_progress.md)
for the full history of what was built and why.
