# 48. Site-wide UX/visual-cue audit against the modern-ui-design contract

> **Status: implemented.** The findings below were produced by a static, page.jsx-only read (see
> §1); implementation found several were false positives caused by that method missing sibling
> components/`layout.jsx` files that already satisfy the requirement — §7 (new) documents exactly
> what was fixed, what was already compliant, and the one real regression caught and fixed during
> implementation (a duplicate `<h1>` from not checking for a section `layout.jsx`).
>
> Findings were produced by directly reading every page file (and, for the micro-course workspace,
> its sibling tab components) against the skill's own "Review checklist" — not by running the app
> or guessing. Line numbers are cited for every finding that has one; `—` means the violation is
> an absence (e.g. "no `PageHeader` anywhere in the file") rather than a specific line.

## 0. Status and scope

| | |
|---|---|
| Status | **Implemented and live-verified.** All real findings fixed; false positives (content living in a sibling component or already-shared `layout.jsx` the original audit didn't read) verified and left unchanged; see §7 for the full breakdown and evidence. |
| Trigger | Follow-on from this session's docs 45–47: having documented backend/API and micro-course UX gaps, do the same evidence-grounded sweep for general visual-cue consistency across the whole app, per the user's request. |
| Relationship to doc 30 | **Important finding, not a contradiction of intent**: several checklist items doc 30 marks ✅ today (UI-2 "no hard-coded colours," UI-6 pagination coverage, UI-14 "one `h1` via `PageHeader`... no implementation detail in student UI") are **not actually true for every page** — doc 30's ✅ marks appear to describe the pages that were explicitly worked on in past sessions (shell, student course reader, admin dashboard, corpus/pedagogy workflows), not a verified sweep of literally every route. This document is that missing sweep. §4 maps each finding back to the specific `UI-*` ID it affects. |

## 1. Audit method

1. Read [SKILL.md](/Volumes/External/Developer/knowledge-bank-ingestion/.github/skills/modern-ui-design/SKILL.md)'s
   "Review checklist" (8 items) as the acceptance bar.
2. Read every one of the 33 `page.jsx` files under `mathbank-web/app/`, plus the 8 sibling tab
   components of the micro-course admin workspace (`OverviewTab.jsx` through `JsonTab.jsx`),
   against 8 concrete categories derived from that checklist:

   | # | Category |
   |---|---|
   | 1 | Hard-coded colors / inline `style={{...}}` for color, font-size, or shadow instead of `--mb-*` tokens or shared classes |
   | 2 | Missing shared `PageHeader` (duplicate/page-local `<h1>`, or a page-local "back" link duplicating the shell) |
   | 3 | Raw Bootstrap `.alert`/`.badge` markup instead of `<Callout>`/`<Pill>` |
   | 4 | Icon-only controls missing `aria-label`/`title` |
   | 5 | Hydration-risk patterns (`Date.now()`, `Math.random()`, `toLocaleString()`/locale formatting, or `new Date()` during render rather than after mount) |
   | 6 | Lists/tables over ~25 rows with no visible `Pager` |
   | 7 | Dense action regions: more than ~2-3 similarly-weighted buttons with no primary/ghost hierarchy |
   | 8 | Missing structured loading/`<EmptyState>` treatment (raw "Loading…" text, or an empty list with no `<EmptyState>`) |

3. No code was run; no screenshots were taken. This is a static-source review, same rigor level as
   docs 45–47, not a substitute for the skill's own step 5 ("open each touched route in the
   integrated browser at 1440px/390px") once any of this is actually implemented.

## 2. Findings by page

Legend: category numbers refer to the table in §1.

| Page | Line(s) | Category | Finding | Suggested direction (not a prescription) |
|---|---:|---|---|---|
| `admin/(protected)/conversations/page.jsx` | 17 | 5 | `new Date(ts).toLocaleString()` runs during render; locale-dependent. | Format after mount with a stable formatter |
| `admin/(protected)/conversations/page.jsx` | 43 | 3 | Raw `.alert alert-danger` for errors. | `<Callout tone="danger">` |
| `admin/(protected)/conversations/page.jsx` | 55 | 8 | Raw "Loading…" table cell. | Structured loading state |
| `admin/(protected)/corpus/page.jsx` | 125 | 7 | Error callout carries an extra text action button alongside the primary one. | `<IconButton>` for the retry action |
| `admin/(protected)/corpus/page.jsx` | 139–227 | 7 | Find/save/upload/generate/approve/reject/open-practice all appear with similar visual weight in one region. | One primary action per region; demote the rest |
| `admin/(protected)/geometry-scenes/page.jsx` | — | 8 | No `<EmptyState>` for an empty diagnostics result. | Add it |
| `admin/(protected)/imports/page.jsx` | — | 8 | No `<EmptyState>` for an empty imports result. | Add it |
| `admin/(protected)/knowledge-gaps/page.jsx` | 123–216 | 7 | Filter/search/details/status actions form a dense, similarly-weighted control region. | Keep search primary; demote the rest |
| `admin/(protected)/micro-courses/[code]/page.jsx` | 129–134 | 8 | Loading/unavailable states are header text only, no skeleton/`<EmptyState>`. | Add both |
| `.../micro-courses/[code]/{Overview,Content,Media,Quizzes,Widgets,Versions,Activity,Json}Tab.jsx` | — | 8 | None of the 8 tabs has a structured empty-state treatment for its own empty case. | Add `<EmptyState>` per tab |
| `admin/(protected)/micro-courses/new/page.jsx` | 71 | 7 | Create-form actions aren't visually hierarchized (create vs. cancel/reset). | One primary, rest ghost |
| `admin/(protected)/micro-courses/page.jsx` | — | — | **No violation found** — already uses `PageHeader`, `EmptyState`, `Pager`. | — |
| `admin/(protected)/page.jsx` (admin dashboard) | 21 | 1, 3 | Status shown as a raw badge with an inline/hard-coded fallback color. | `<Pill tone={...}>` |
| `admin/(protected)/page.jsx` | 145, 214 | 1, 8 | Loading states use inline font sizing and raw "Loading…" text. | Tokenized structured loading state |
| `admin/(protected)/pedagogy/page.jsx` | 227–374 | 7 | Bulk-review/publish/reclassify/reload/paging/decision controls form several dense clusters. | One primary per region |
| `admin/(protected)/textbooks/page.jsx` | 12, 146 | 5 | Locale-dependent date formatting during render. | Format after mount |
| `admin/(protected)/textbooks/page.jsx` | 213, 266 | 1 | Inline `maxWidth` on table cells instead of a shared class. | Reusable utility class |
| `admin/(protected)/textbooks/problems/[code]/page.jsx` | 215 | 1 | Inline `objectFit`/`maxHeight` on the diagram image. | Shared media class |
| `admin/(protected)/tutoring-routes/page.jsx` | — | — | **No violation found** — uses `EmptyState`/`Callout`. | — |
| `admin/(protected)/widgets/page.jsx` | — | — | **No violation found** — uses `PageHeader`/structured feedback. | — |
| `admin/attempt-media/page.jsx` | — | 2, 8 | No shared `PageHeader`; no `<EmptyState>` for an empty review queue. | Add both |
| `admin/login/page.jsx` | 35 | 2 | Page-local `<h1>` instead of `PageHeader`. | Replace |
| `artifacts/page.jsx` | — | 8 | No `<EmptyState>` for an empty artifact library. | Add it |
| `db/concepts/page.jsx` | 39, 52, 64, 71, 91, 96, 99, 104, 120, 123 | 1 | Extensive page-local inline spacing/colors/font sizes/table/link styling. | Move to tokenized shared classes |
| `db/concepts/page.jsx` | 57, 93, 111, 124 | 8 | Raw "Loading…" text; sliced lists with no clear empty-state. | Structured loading + empty states |
| `db/concepts/page.jsx` | — | 2 | No `PageHeader`. | Add it |
| `db/page.jsx` | 21 | 8 | Raw "Loading…" text on the corpus landing page. | Structured skeleton |
| `db/page.jsx` | — | 2 | No `PageHeader`. | Add it |
| `db/problems/page.jsx` | 108, 133 | 8 | Raw "Loading…" in the list and in the `Suspense` fallback. | Structured loading states |
| `db/problems/page.jsx` | — | 2 | No `PageHeader`. | Add it |
| `db/search/page.jsx` | 64, 69, 76–88 | 1 | Inline colors/table/row/layout styles throughout. | Replace with design-system classes |
| `db/search/page.jsx` | 71 | 8 | Empty results shown as a raw paragraph. | `<EmptyState>` |
| `db/search/page.jsx` | — | 2 | No `PageHeader`. | Add it |
| `db/techniques/page.jsx` | 37, 48–56, 74, 79–92 | 1 | Inline colors/font sizes/table/row/link styling. | Tokenized shared classes |
| `db/techniques/page.jsx` | 42, 76 | 8 | Raw "Loading…" text in both list and detail. | Structured loading states |
| `db/techniques/page.jsx` | — | 2 | No `PageHeader`. | Add it |
| `graph/[rel]/page.jsx` | 189, 200 | 3 | Raw Bootstrap alert markup for explanatory/error content. | `<Callout>` |
| `graph/[rel]/page.jsx` | 226, 301 | 1, 3 | Raw badges with inline font/background/foreground colors. | `<Pill tone=...>` |
| `graph/[rel]/page.jsx` | 261, 278–280 | 1 | Hard-coded hex colors for labels/graph controls. | `--mb-*` tokens or semantic classes |
| `graph/[rel]/page.jsx` | 237 | 8 | Raw-text loading state for the graph. | Structured loading state |
| `graph/[rel]/page.jsx` | 249–255 | 7 | Six similarly-weighted toolbar controls. | Group + demote secondary actions |
| `graph/page.jsx` | 37, 56 | 3 | Raw alert-style markup (same pattern as `[rel]`). | `<Callout>` |
| `graph/page.jsx` | 47 | 8 | Raw-text loading overview. | Structured loading state |
| `graph/page.jsx` | 70, 74, 99, 125 | 5 | Locale-dependent numeric formatting during render. | Deterministic formatter |
| `graph/page.jsx` | 87, 96, 107 | 1 | Inline padding/text-alignment styles. | Reusable classes |
| `graph/page.jsx` | 56–65 | 7 | Retry + guided-practice actions with similar visual weight. | Retry primary; demote navigation |
| `learn/attempt-media/page.jsx` | — | 8 | No `<EmptyState>` for an empty submitted-work list. | Add it |
| `learn/conversations/page.jsx` | 19 | 5 | `new Date(ts).toLocaleString()` during render. | Format after mount |
| `learn/conversations/page.jsx` | 49, 69 | 8 | Raw text/spinner loading paragraphs. | Skeleton/loading components |
| `learn/courses/[code]/page.jsx` | 107 | 1 | Inline `maxWidth` on a course control. | Shared layout class |
| `learn/courses/page.jsx` | — | — | **No violation found** — uses `PageHeader`/`EmptyState`. | — |
| `learn/page.jsx` | — | 8 | No `<EmptyState>` for an empty guided-practice state. | Add it |
| `learn/solve/[code]/page.jsx` | — | 8 | No `<EmptyState>` for unavailable/empty solve content. | Add it |
| `login/page.jsx` | 53 | 2 | Page-local `<h1>` instead of `PageHeader`. | Replace |
| `page.jsx` (home) | — | — | **No violation found** — uses `PageHeader`. | — |
| `profile/page.jsx` | 44, 188 | 5 | Locale-dependent date formatting during render. | Format after mount |
| `profile/page.jsx` | 169, 209 | 8 | Raw loading paragraphs for progress/practice data. | Structured loading states |
| `profile/page.jsx` | — | — | Lists elsewhere correctly use `EmptyState`/`Pager`. | — |

## 3. Cross-app patterns (the few root causes behind most rows above)

Four recurring root causes account for the large majority of findings above, not 33 independent
problems:

1. **No shared loading/empty-state primitive is used consistently.** Nearly every "Category 8"
   row is the same shape: a raw `"Loading…"` string instead of a skeleton, or a list with no
   `<EmptyState>`. `EmptyState` already exists and is already used correctly on ~8 of the 33 pages
   (micro-courses catalog, tutoring-routes, widgets, learn/courses, profile) — this is a rollout
   gap, not a missing component.
2. **The `db/*` and `graph/*` routes predate the design-token system and were never swept.** Every
   one of `db/concepts`, `db/page`, `db/problems`, `db/search`, `db/techniques`, `graph/page`, and
   `graph/[rel]` shows inline colors/styles and a missing `PageHeader` — these read as an older
   generation of the app that the `modern-ui-design` work never reached, not scattered one-off
   mistakes.
3. **Dense admin authoring/review screens accumulate buttons over time with no later pruning
   pass** (`admin/corpus`, `admin/knowledge-gaps`, `admin/pedagogy`, `graph/[rel]`'s toolbar) —
   each individual action was presumably added for a real reason, but no one screen has had an
   explicit "what's the one primary action here" pass applied after the fact.
4. **Locale-dependent date/number formatting during render is a recurring hydration-risk pattern**
   (`conversations` ×2, `textbooks`, `profile`, `graph/page.jsx`'s numeric formatting) — the skill's
   own non-negotiable #5 already names this exact anti-pattern; it has regressed/was never swept
   on these five pages specifically.

## 4. Mapping back to doc 30's existing `UI-*` status table

| `UI-*` ID | Doc 30's current claim | What this audit found |
|---|---|---|
| UI-2 (no hard-coded colours) | ✅ "shell, student, admin and section headers" | True for the pages doc 30 names explicitly; **not** true for `db/*`, `graph/*`, and parts of `admin/(protected)/page.jsx`/`textbooks` — doc 30's ✅ scope was narrower than "no page in the app," which is easy to misread given the unqualified checkmark. |
| UI-6 (pagination) | ✅ "db lists, profile attempts, admin paper jobs... and paper sources" | The `db/*` *list* pages may well already page server-side; the finding here is narrower — those same pages lack `PageHeader`/`EmptyState`/tokenized styling, which doc 30's UI-6 row doesn't claim to cover (no contradiction, just adjacent gaps on the same pages). |
| UI-14 (one `h1`/no repetition) | ✅ "student and admin; ⏳ see §3" | `admin/login`, `login`, and all five `db/*` pages still use a page-local `<h1>` instead of `PageHeader` — this is likely exactly the kind of gap doc 30's own "⏳ see §3" qualifier was already hedging against, now enumerated concretely. |
| UI-15 (hydration stability) | ✅ | Five pages (`conversations` ×2, `textbooks`, `profile`, `graph/page.jsx`) format dates/numbers during render using locale-dependent calls — a real, specific exception to this ✅ that should be corrected if/when this document is implemented. |

This document does not propose rewriting doc 30's historical ✅ marks (they were accurate for the
pages in scope at the time); it proposes that any future implementation pass update doc 30's rows
to explicitly list known exceptions (or flip to ⏳) rather than leave an unqualified ✅ that a
sweep like this one can quietly disprove.

## 5. Explicit non-goals

- **Not** re-litigating component design (`EmptyState`, `Pager`, `PageHeader`, etc.) — every
  fix in §7 reuses an existing component from
  [ui.jsx](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-web/app/_components/ui.jsx),
  none introduced a new one (two new formatting helpers, `formatDateTime`/`formatDate`, were added
  to that same file — see §7).
- **Not** a comprehensive pixel-level redesign — dense-action-region fixes (UXS-6) demote/relabel
  buttons to establish one primary action per region; they do not restructure page layout.

## 6. Requirement inventory (UXS-*) — final status

| ID | Requirement | Acceptance evidence | Status |
|---|---|---|---|
| UXS-1 | Every page uses a structured loading state (no raw "Loading…" text) | None of the pages listed under category 8 in §2 shows a bare loading string | ✅ Done — see §7 |
| UXS-2 | Every list/empty-result page uses `<EmptyState>` | None of the pages listed under category 8 in §2 shows a raw empty-list paragraph instead | ✅ Done — see §7 (several were already compliant via a sibling component the original audit didn't read) |
| UXS-3 | Every page has exactly one `<h1>` via `PageHeader` | `admin/login`, `login`, and all five `db/*` pages gain a `PageHeader`; grep for `<h1` outside `ui.jsx` returns none | ✅ Done, with a correction: `db/*` and `graph/*` already get their one `<h1>` from a section `layout.jsx` (missed by the original per-`page.jsx` audit) — `admin/login`/`login` now use `PageHeader`'s new `centered` variant instead |
| UXS-4 | `db/*` and `graph/*` routes are swept onto design tokens | No inline hex colors/font-sizes/shadows remain in `db/concepts`, `db/page`, `db/problems`, `db/search`, `db/techniques`, `graph/page`, `graph/[rel]` | ✅ Done — see §7 |
| UXS-5 | Raw Bootstrap alert/badge markup replaced with `Callout`/`Pill` | `conversations`, `graph/page`, `graph/[rel]` show no `.alert`/raw-badge markup | ✅ Done — see §7 |
| UXS-6 | Dense action regions reduced to one primary + ghost/icon secondary actions | `admin/corpus`, `admin/knowledge-gaps`, `admin/pedagogy`, `graph/[rel]`'s toolbar, and the micro-course creation wizard each show one visually dominant action per region | ✅ Done — see §7 |
| UXS-7 | No locale-dependent date/number formatting during render | `conversations`, `textbooks`, `profile`, `graph/page.jsx` format dates/numbers only after mount, via a shared deterministic formatter | ✅ Done — new `formatDateTime`/`formatDate` helpers in `ui.jsx` (fixed `"en-US"` locale), applied everywhere a bare `toLocaleString()`/`toLocaleDateString()` was found |
| UXS-8 | Doc 30's `UI-*` table reflects verified-exception scope, not an unqualified blanket ✅ | UI-2/UI-6/UI-14/UI-15 rows in doc 30 list their known exceptions (or are updated once §2's findings are resolved) | ✅ Done — doc 30 updated in this pass |

## 7. Implementation evidence (this pass)

**Method**: fixed every concrete, line-numbered finding in §2. Before fixing each "No `PageHeader`"/"No `EmptyState`" finding against a thin `page.jsx` wrapper, checked whether the real content lives in a sibling component (`ArtifactLibrary.jsx`, `AttemptMediaWorkspace.jsx`, `LearningWorkspace.jsx`, `GeometrySceneRun.jsx`, `SolveWorkspace.jsx`) or a section `layout.jsx` (`db/layout.jsx`, `graph/layout.jsx`) — several findings turned out to already be satisfied there, a direct consequence of the original audit's own disclosed method (§1: "every one of the 33 `page.jsx` files," not their sibling components).

**Confirmed false positives (no change needed, already compliant)**:
- `admin/(protected)/geometry-scenes/page.jsx` → `GeometrySceneRun.jsx` already has `EmptyState`.
- `admin/attempt-media/page.jsx` / `learn/attempt-media/page.jsx` → shared `AttemptMediaWorkspace.jsx` already has `PageHeader` + `EmptyState` (×3).
- `artifacts/page.jsx` → `ArtifactLibrary.jsx` already has `PageHeader` + `EmptyState` (×3).
- `learn/page.jsx` → `LearningWorkspace.jsx` already has `EmptyState`.
- 7 of the 8 micro-course admin tabs already had `EmptyState`; only `OverviewTab.jsx` needed one (added, for its "no primary targets" case).
- `learn/courses/[code]/page.jsx`'s cited inline `maxWidth` — the skill's own checklist explicitly allows "inline `style` only for layout sizes"; `maxWidth` on a form input is a layout size, not a color/font-size, so left as-is.
- `db/*`/`graph/*` "No `PageHeader`" findings — both sections already get one `<h1>` from their `layout.jsx` (see the regression below).

**Real fixes applied**:
- New shared helpers in [ui.jsx](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-web/app/_components/ui.jsx): `formatDateTime`/`formatDate` (fixed `"en-US"` locale, replacing every bare `toLocaleString()`/`toLocaleDateString()` found: `admin/conversations`, `learn/conversations`, `profile` ×2, `_components/Transcript.jsx`, `admin/textbooks`); `PageHeader`'s new `centered` prop + `.mb-page-header-centered` CSS (for `admin/login`/`login`, replacing manually-duplicated `mb-page-icon`/`mb-page-title`/`mb-page-sub` markup with the real component, satisfying UXS-3's literal "no raw `<h1>` outside `ui.jsx`" bar).
- `admin/(protected)/conversations/page.jsx`, `admin/(protected)/imports/page.jsx` (+ `importsClient.jsx`): raw `.alert`→`Callout`, raw "Loading…"→structured spinner status, raw empty-text→`EmptyState` (multiple instances across Packages/Issues/Conflicts/Reconciliation/Queue tabs).
- `learn/solve/[code]/SolveWorkspace.jsx`: the "could not open" unavailable state → `EmptyState` with an action link.
- `mathbank-web/app/db/{page,concepts,problems,search,techniques}/page.jsx` and `mathbank-web/app/graph/{page,[rel]}/page.jsx`: full sweep (tokenized colors, structured loading, `EmptyState`, `Callout`/`Pill`, mount-safe numeric formatting, dense-toolbar hierarchy) — built via 2 parallel background agents, each scoped to exactly these files with the skill's rules and the specific cited findings.
- `admin/(protected)/{corpus,knowledge-gaps,pedagogy}/page.jsx`, `admin/(protected)/micro-courses/new/page.jsx`: one primary action per dense region, built via a parallel background agent.
- `admin/(protected)/page.jsx`, `admin/(protected)/textbooks/page.jsx`, `admin/(protected)/textbooks/problems/[code]/page.jsx`: `Pill` tones, structured loading, `formatDateTime`, two new shared CSS utility classes (`.mb-cell-wrap`, `.mb-diagram-preview`) replacing inline `maxWidth`/`objectFit` — built via a parallel background agent.
- `OverviewTab.jsx` (micro-course admin): `EmptyState` for the no-targets case.

**One real regression caught and fixed during verification** (now [GOTCHAS.md](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/GOTCHAS.md) §30): the `db/*` and `graph/*` sweeps (run by background agents scoped only to those files, with no visibility into sibling `layout.jsx` files) each added a **second** `<PageHeader>`/`<h1>` on top of the one `db/layout.jsx`/`graph/layout.jsx` already renders for the whole section — caught by `e2e/public.spec.mjs`'s strict-mode heading lookup failing on `/db` with "resolved to 2 elements." Fixed by removing the duplicate headers from all 5 `db/*` pages (relying solely on the layout's shared header, matching the existing `NavTabs` wayfinding) and demoting `graph/page.jsx`/`graph/[rel]/page.jsx`'s page-specific title to a plain intro line / `<h2>` sub-heading respectively, preserving their unique content (actions, pills, per-relationship name) without a second `<h1>`.

**Verification**:
- `cd mathbank-web && npx next build` — succeeds cleanly after every change (checked incrementally and once at the end).
- `npx playwright test e2e/admin.spec.mjs e2e/admin-corpus.spec.mjs e2e/artifacts.spec.mjs e2e/attempt-media.spec.mjs e2e/corpus-previews.spec.mjs e2e/geometry-scenes.spec.mjs e2e/profile-practice.spec.mjs e2e/public.spec.mjs e2e/micro-courses.spec.mjs e2e/guided-workspace.spec.mjs e2e/student.spec.mjs` — 82/84 passing. The 2 failures (`admin.spec.mjs`'s textbook diagram-image test, `student.spec.mjs`'s solve-workspace diagram test) were confirmed **pre-existing and unrelated** by temporarily `git stash`-reverting the touched files and re-running — both fail identically against the original, unmodified code (a diagram-image-loading issue, not a UX-sweep regression).
- Full repo-wide `npx playwright test` (all 126 tests, every spec) — 119 passed, 5 failed, 2 skipped. All 5 failures confirmed unrelated: 3 are the same pre-existing diagram-image-loading issue (`admin.spec.mjs:51`, `student.spec.mjs:31`, plus `problem-diagrams.spec.mjs` ×2 — a spec that touches none of this pass's files at all, confirming the issue is environmental/pre-existing, not UX-sweep fallout); the 5th (`micro-courses.spec.mjs:217`) passed cleanly when re-run in isolation, indicating full-suite test-order flakiness rather than a real regression.
- Live browser spot-check (1440px) of `/db/search` and `/graph/step-requires-technique` — confirmed exactly one `<h1>`, correct NavTabs active state, tokenized styling, and (for the graph page) the new `<h2>` sub-heading + pills rendering correctly beneath the shared layout header.

## Cross-document relationship

- Audits against the contract owned by [.github/skills/modern-ui-design/SKILL.md](/Volumes/External/Developer/knowledge-bank-ingestion/.github/skills/modern-ui-design/SKILL.md)
  and tracked in [doc 30](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/requirements/30_MODERN_UI_DESIGN_SYSTEM.md).
- Independent of [docs 45–47](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/requirements/45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md)
  (backend/API scope) — this document is frontend-visual-only. No ordering dependency with them.

- Audits against the contract owned by [.github/skills/modern-ui-design/SKILL.md](/Volumes/External/Developer/knowledge-bank-ingestion/.github/skills/modern-ui-design/SKILL.md)
  and tracked in [doc 30](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/requirements/30_MODERN_UI_DESIGN_SYSTEM.md).
- Independent of [docs 45–47](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/requirements/45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md)
  (backend/API scope) — this document is frontend-visual-only. No ordering dependency with them.
