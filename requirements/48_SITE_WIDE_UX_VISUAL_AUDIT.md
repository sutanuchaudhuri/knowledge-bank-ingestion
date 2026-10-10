# 48. Site-wide UX/visual-cue audit against the modern-ui-design contract (planning only)

> **Explicit scope note.** Planning and documentation only — **no page, component, or style has
> been changed**. This is a read-only audit of all 33 page routes under `mathbank-web/app/`
> (every `page.jsx`) against the existing design contract in
> [.github/skills/modern-ui-design/SKILL.md](/Volumes/External/Developer/knowledge-bank-ingestion/.github/skills/modern-ui-design/SKILL.md)
> and its tracked status in [doc 30](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/30_MODERN_UI_DESIGN_SYSTEM.md).
> Findings were produced by directly reading every page file (and, for the micro-course workspace,
> its sibling tab components) against the skill's own "Review checklist" — not by running the app
> or guessing. Line numbers are cited for every finding that has one; `—` means the violation is
> an absence (e.g. "no `PageHeader` anywhere in the file") rather than a specific line.

## 0. Status and scope

| | |
|---|---|
| Status | **Planning only.** Not implemented. |
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

- **Not** fixing any of the findings above — this is a documentation-only sweep (§0).
- **Not** a visual/screenshot-based review — purely static source reading. A real implementation
  pass must still do the skill's own step 5 (open each route at 1440px/390px in a browser) before
  calling any fix done.
- **Not** re-litigating component design (`EmptyState`, `Pager`, `PageHeader`, etc.) — every
  suggested direction in §2 reuses an existing component from
  [ui.jsx](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-web/app/_components/ui.jsx),
  none proposes a new one.
- **Not** prioritizing or sequencing the fixes — that's an implementation-time decision; §6 lists
  requirements, not an execution order.

## 6. Requirement inventory (UXS-*)

| ID | Requirement | Acceptance evidence |
|---|---|---|
| UXS-1 | Every page uses a structured loading state (no raw "Loading…" text) | None of the pages listed under category 8 in §2 shows a bare loading string |
| UXS-2 | Every list/empty-result page uses `<EmptyState>` | None of the pages listed under category 8 in §2 shows a raw empty-list paragraph instead |
| UXS-3 | Every page has exactly one `<h1>` via `PageHeader` | `admin/login`, `login`, and all five `db/*` pages gain a `PageHeader`; grep for `<h1` outside `ui.jsx` returns none |
| UXS-4 | `db/*` and `graph/*` routes are swept onto design tokens | No inline hex colors/font-sizes/shadows remain in `db/concepts`, `db/page`, `db/problems`, `db/search`, `db/techniques`, `graph/page`, `graph/[rel]` |
| UXS-5 | Raw Bootstrap alert/badge markup replaced with `Callout`/`Pill` | `conversations`, `graph/page`, `graph/[rel]` show no `.alert`/raw-badge markup |
| UXS-6 | Dense action regions reduced to one primary + ghost/icon secondary actions | `admin/corpus`, `admin/knowledge-gaps`, `admin/pedagogy`, `graph/[rel]`'s toolbar, and the micro-course creation wizard each show one visually dominant action per region |
| UXS-7 | No locale-dependent date/number formatting during render | `conversations`, `textbooks`, `profile`, `graph/page.jsx` format dates/numbers only after mount, via a shared deterministic formatter |
| UXS-8 | Doc 30's `UI-*` table reflects verified-exception scope, not an unqualified blanket ✅ | UI-2/UI-6/UI-14/UI-15 rows in doc 30 list their known exceptions (or are updated once §2's findings are resolved) |

## Cross-document relationship

- Audits against the contract owned by [.github/skills/modern-ui-design/SKILL.md](/Volumes/External/Developer/knowledge-bank-ingestion/.github/skills/modern-ui-design/SKILL.md)
  and tracked in [doc 30](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/30_MODERN_UI_DESIGN_SYSTEM.md).
- Independent of [docs 45–47](/Volumes/External/Developer/knowledge-bank-ingestion/requirements/45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md)
  (backend/API scope) — this document is frontend-visual-only. No ordering dependency with them.
