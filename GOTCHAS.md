# GOTCHAS — things that will bite you on a fresh machine

Every item here was hit for real while building this repo. `make bootstrap`
(root Makefile) automates around all of them where possible; this file
explains *why* each workaround exists, for when it inevitably breaks again on
a different macOS version / Xcode CLT version / Homebrew state.

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

## 6. `OPENAI_API_KEY` must be in the environment — never in a file or command line

Both `mathbank-db/etl/embed_corpus.py` and `mathbank-rest`'s
`vector_search.py` (and `mathbank-agent`'s LiteLLM model) read `OPENAI_API_KEY`
via the OpenAI/LiteLLM SDK defaults (`os.environ`). **Never** pass it as a
`--flag`, write it into `.env` if it's already exported globally (e.g.
`~/.zshrc`), or echo it in a terminal command — `python-dotenv`/`load_dotenv()`
only fills in variables that aren't already set, so an already-exported shell
variable always wins safely.

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

## Single-command recreation

```bash
# one-time, from a fresh clone, with OPENAI_API_KEY already exported:
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
