# mathbank-web

Next.js chat frontend for the MathBank tutor. The browser only ever talks to
**this app** (same-origin, no CORS needed) — `app/api/agent/*` route handlers
run server-side and proxy to the `mathbank-agent` Google ADK REST server,
which itself calls `mathbank-rest` → Postgres.

```
browser ──same-origin──▶ mathbank-web (Next.js, :5173)
                              │ app/api/agent/session, app/api/agent/run
                              │ (server-side fetch, no CORS)
                              ▼
                         mathbank-agent (ADK REST, :8001) ──▶ mathbank-rest ──▶ Postgres
```

This replaces an earlier Vite/React version that called `mathbank-agent`
directly from the browser — `adk api_server` rejects cross-origin browser
requests by default (`403 Forbidden: origin not allowed`), so routing through
Next.js's own server avoids needing to configure CORS on the agent at all.

## Quick start

```bash
cp .env.example .env   # MATHBANK_AGENT_BASE_URL, defaults to http://127.0.0.1:8001
make install
make dev                # http://localhost:5173
```

Requires `mathbank-agent` running (`make -C ../mathbank-agent run`), which in
turn requires `mathbank-rest` running (`make -C ../mathbank-rest run`).

## Current user model

Students sign in at `/login` (httpOnly JWT cookie); admins at `/admin/login`.
The ADK `user_id` is derived on the server (`/api/agent/session`): the student
UUID when signed in, otherwise `anonymous`; any client-supplied id is ignored.
Signed-in chats are linked to the student in `learner.agent_session_link`, so
the full conversation can be rebuilt at `/learn/conversations` (student) and
`/admin/conversations` (admin, incl. tool calls). Anonymous chats stay
unlinked. See [requirements/22](../requirements/22_AGENT_SESSION_TRANSCRIPTS.md).

Admins can browse the imported Prasolov corpus at `/admin/textbooks`:

- Coverage matrix across source, Postgres, pgvector and Neo4j.
- Problems, transformations and taxonomy.
- `/admin/textbooks/problems/{canonical_code}`, which shows solution steps, transformations, diagrams (including solution-hidden ones) and per-store status.

See [requirements/24](../requirements/24_ADMIN_TEXTBOOK_CORPUS_DASHBOARD.md).

## Math and embedded source diagrams

### Guided problem workspace

`/learn?problem=CANONICAL_CODE` pairs Tutor with My work rather than requiring
an opening self-diagnosis. A temporary Understand/Plan/Work/Check/Reflect journey
supports jump/skip/self-reported completion; editable step tabs keep provisional
coaching and hint counts attached to each draft. Retry of unavailable teaching
context preserves typed work and the canonical question when possible, and
disables coaching until recovery.

The practice search accepts topics, descriptions, pasted question text and
codes. Free text uses existing graph/text search without paid embeddings;
up to ten collapsed canonical question/diagram previews require an explicit
practice selection. Exact AMC/AIME references are optional shortcuts; ambiguous
papers require a choice. Search does not discard the current question or work.

The compact view collapses change-problem controls, source metadata, working
preferences and routine warnings. Real service/upload errors remain visible;
workspace details explain temporary drafts and provisional coaching. KaTeX
renderer/CSS versions match, with measured smaller/lowered subscripts. Shared
server/UI statement presentation repairs recognized PDF word breaks and
source-specific Q31 notation without modifying canonical text or invoking a
paid formatter.

Question/orientation bootstrap is independent of the graph. Background context
has a 15-second browser deadline, bootstrap has 12 seconds and tutor GET proxies
have 20 seconds; errors offer recovery without discarding drafts/progression.

Q31 and AIME 1985 Q1 have statement-gated authored orientation MCQs. Q31 also
offers prompt-specific validated circumcenter constructions: exact defining
triangles, centers, circumcircles and radii, followed after orientation by all
first-level centers and the second iteration. Missing required elements or
invalid definitions suppress the diagram; no generic quadrilateral replaces
it. Coordinates are illustrative, with equal-radii checks and an independently
magnified second-level panel, not a recovered source or similarity proof.
Source details and
lower-level practice are collapsed. MathComposer retains math/voice support;
upload/paste opens the existing private, editable-transcription workflow with
explicit approval/analysis. These browser drafts and journey choices are **not**
a durable PedagogySession or a correctness/mastery assessment.
See [requirement 34](../requirements/34_GUIDED_PROBLEM_WORKSPACE.md).

Problem-linked chat now consults stored solutions privately before selecting
a roadmap. Activity shows actual reference counts and verification status;
only high-level stages and one checkpoint appear in the reply. Step coaching
also receives private stored references through REST, not browser payloads.
No problem-opening request automatically generates a solution plan.

### Corpus previews and problem-linked chat

At `/db`, selecting a competition shows coverage stats and a collapsed
question-preview panel. `/db/problems` offers filtered, paginated collapsed
cards with formatted statements, published concept/technique pills and
question-specific source figures. Missing text is labelled incomplete, and the
original source opens through the existing split-pane viewer.

Each question has a collapsed **Explore related problems** panel. It uses the
existing graph/text search with semantic embeddings disabled, excludes the
current question/duplicate matches, and shows bounded cross-competition
candidates. These are discovery candidates, not verified practice assignments.
Retrieval limitations and errors are visible.

**Discuss with tutor** opens `/?problem=CANONICAL_CODE`, previews that question
in chat and prepares a coaching prompt. The learner still clicks Send to invoke
the tutor; opening the link does not make a paid inference call. Signed-in
session links include `problem_code` context. Existing diagnosis/step-solving
links are preserved; answers and solutions require an explicit reveal.

The tutor activity timeline shows actual tool progress and allowlisted evidence:
graph queried/unavailable/disabled, vector/text search configuration, candidate
counts and learning-context metadata provenance. Machine-approved skill metadata
and pending generated hints are visibly qualified. Raw tool payloads, private
thoughts and provider/database warning strings are never copied to the timeline.
Missing retrieval telemetry is not presented as successful graph/vector evidence.
Topic pedagogy activity also shows roadmap stages and complete step-supported
candidate counts. Bare topics open a theory/checkpoint lesson before contest
practice; Power of a Point has persisted seven-stage progress and an interactive
four-frame chord illustration. Private preview frame controls reuse theme/icon
components and announce their current frame; generated figures remain explicitly
distinct from original sources. Unsupported topics disclose missing authored
checkpoints. A checkpoint is not a mastery certification.
Relevance reports are pending review, not silently ingested as
graph truth. Admin `/admin/pedagogy` includes the paginated learner-report queue;
correction snapshots expose actual step counts/support and structural review
flags. Human relevance/error decisions require an evidence note and do not
themselves publish corrections or train models.

When a document/web URL is registered, Source controls include its direct original
link. Book identity without a document is separately shown as “Source book
identified; original page/location provenance incomplete,” with chapter/problem
identity and no guessed PDF/highlight controls. Clicking Source or Original PDF opens a shared right-hand split pane;
modifier-click/new-tab links still open the untouched original. On mobile this
becomes a bottom pane with its own Close control. Cached PDFs with an unambiguous
text match or current-hash extraction coordinates open at the verified physical
page and highlight the problem in an annotated full-document copy. A highlighted
page preview is also shown. Originals are never modified; annotated responses
are no-store and never registered as individual problem diagrams.
Statements and diagrams on different physical pages have separate page pills;
all verified regions are highlighted in the annotated document.

Unknown/ambiguous locations are not highlighted. When only a web source is
registered, its direct link remains available and the pane explicitly says no
PDF is known; it never fabricates a PDF URL. Missing source registration is
shown explicitly. Full documents may include other questions/answers.

Chat, guided practice and corpus details share `MathText`: prose LaTeX
`\(...\)` / `\[...\]` becomes KaTeX math without modifying code strings.
Single and double-escaped legacy delimiters normalize without visible backslashes;
complete expressions render during streaming and when reopening saved messages.
The agent also guards final prose server-side. Its optional presentation formatter
returns deterministic exact-span emphasis: bold, italic, and semantic givens/goals/
insights/cautions. Reserved links `#mb-tone-given`, `#mb-tone-goal`,
`#mb-tone-insight`, `#mb-tone-warning` render as styled spans (not clickable links),
using theme tokens rather than arbitrary agent-supplied colors or executable HTML.
Legacy `[asy]...[/asy]` and fenced `asy`/`asymptote` blocks render as PNG
diagrams; their code stays in collapsed source details, not the statement.
Incomplete streaming blocks wait until complete. Malformed inline Problem/Source
labels are separated into the same tinted problem and neutral source panels.

`POST /api/diagrams/asymptote` requires a same-origin request and a student token
verified through REST `/v1/learner/me` (not merely a cookie's presence).
It uses the installed macOS `/usr/bin/sandbox-exec`, Asymptote and TeX/Ghostscript.
Default compiler: `/Library/TeX/texbin/asy`; server-only
`MATHBANK_ASYMPTOTE_PATH` can select an installed executable. Child processes
receive no application/provider credentials, cannot read project/home files or
use the network, and can write only their unique temporary directory.
Unsafe imports/process/file/configuration primitives are rejected too.
PNG responses are private/no-store; temporary files are removed after rendering.

Limits: 32,000 source characters, two concurrent renders per server process,
15-second wall/10-second CPU timeout, 8 MiB per generated file, 2 MiB returned
PNG, and a 512 MiB process-group RSS monitor polled every 250 ms (not a hard
instantaneous allocation ceiling). Raster conversion uses the supplied source
projection, not model-invented geometry. Source scale parameters are not answers.
Unsupported code and missing dependencies produce explicit errors. Other
operating systems fail closed with 503 until an equivalent isolation backend is
implemented; there is no unsandboxed fallback or browser JavaScript execution.

Verify the real compiler/isolation without paid calls:

```sh
RUN_ASYMPTOTE_TESTS=1 node --test tests/asymptoteRenderer.test.mjs tests/markdownText.test.mjs tests/tutorProblem.test.mjs
RUN_ASYMPTOTE_TESTS=1 npx playwright test e2e/tutor-asymptote.spec.mjs
```

## Tests

```bash
make test           # node unit tests (tests/*.test.mjs), no services needed
make e2e-install    # one-time: Playwright Chromium
make e2e            # Playwright regression against the running stack (no paid calls)
make e2e-llm        # also runs @llm specs (small paid OpenAI calls)
make e2e-report     # open the last HTML report
```

`E2E_BASE_URL` overrides `http://localhost:5173`. See
[requirements/23](../requirements/23_E2E_REGRESSION_SUITE.md).
