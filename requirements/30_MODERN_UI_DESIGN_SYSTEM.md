# 30 — Modern UI Design System and Navigation Revamp (`UI`)

Requirement IDs: `UI-*`. Requested 2026-10-08. The goal is a modern, wide, low-clutter interface that students find easy
to use. It should be consistent across pages, use icons and pills rather than prose, and make navigation obvious.
The working contract for agents is the skill
[`.github/skills/modern-ui-design/SKILL.md`](../.github/skills/modern-ui-design/SKILL.md). This document holds the
requirements and records progress.

## 1. Requirements

| ID | Requirement | Status |
|---|---|---|
| UI-1 | **Wide layout:** full-width content beside a sidebar; no fixed `max-width` page columns. | ✅ |
| UI-2 | **One theme:** colours, radii and shadows come from CSS tokens (`--mb-*` in `app/globals.css`) that override Bootstrap 5 variables; no hard-coded colours in pages. | ✅ (shell, student, admin and section headers) |
| UI-3 | **Student-friendly font:** Inter Variable (`@fontsource-variable/inter`, self-hosted, no network font fetch); KaTeX keeps its own fonts. | ✅ |
| UI-4 | **Icons and pills instead of text:** Bootstrap Icons (`bootstrap-icons`) used from one vocabulary; status, counts and metadata shown as `Pill`. Icon-only controls have `aria-label` and `title`. | ✅ |
| UI-5 | **Explanation highlights:** micro-lessons, hints, feedback and "why" notes use `Callout` (insight, hint, warning, success, danger, neutral). | ✅ |
| UI-6 | **Pagination:** lists longer than 25 rows page with the shared `Pager` (icon buttons "Previous page" / "Next page"). | ✅ db lists, profile attempts, admin paper jobs (10 per page) and paper sources |
| UI-7 | **Master-detail and drill-down:** list on the left and detail on the right (`app-master-detail`); dashboard cards link to the page behind them. | ✅ conversations (student and admin), knowledge gaps, admin dashboard cards |
| UI-8 | **Breadcrumbs:** built from the route by `lib/navigation.mjs#breadcrumbs`, with relationship titles for graph routes. | ✅ |
| UI-9 | **Menu:** one sidebar from `NAV_GROUPS` (Learn / Explore / Admin). It collapses to an icon rail (remembered in `localStorage`) and becomes off-canvas on phones. Outside `/admin` the Admin group shows a single link. | ✅ |
| UI-10 | **Avatars:** deterministic initials and colour (`avatarFor`) for students, a tutor avatar in chat and a shield avatar for the admin menu. | ✅ |
| UI-11 | **Analytics dashboards:** `StatCard` and `Bar` on the student profile (attempts, accuracy, hints, solid skills) and the admin dashboard (papers, textbook problems with import progress, open gaps, conversations, coverage per entity, gap outcomes). | ✅ |
| UI-12 | **Fewer buttons:** at most one primary button per region; secondary actions are `IconButton`s; rarely used admin forms and logs sit in collapsible `<details>`; logout lives only in the avatar menu. | ✅ |
| UI-13 | **Natural-language input:** in `MathComposer` the mic and Send/Stop sit **inside** the input field (right); the Σ / $ / ✨ format tools are ghost icons inside it (left). Stop replaces Send while streaming. Starter suggestions are pills that appear only at the greeting. | ✅ web chat, solve workspace, live console |
| UI-14 | **No repetition:** each page has one `h1` via `PageHeader`; section titles are not echoed by their items; no duplicate "back" links (breadcrumbs replace them); no implementation detail in student UI. | ✅ student and admin; ⏳ see §3 |
| UI-15 | **Accessibility and stability:** visible focus states, usable at 390 px, no hydration mismatches (client-only data such as `/learner/me`, `localStorage` and dates is read after mount). | ✅ |

## 2. Building blocks

| Piece | File | Notes |
|---|---|---|
| Tokens and component CSS | `mathbank-web/app/globals.css` | Shell, kit, chat, solve and tab styles. Extend tokens here; don't add styles local to one page. |
| UI kit | `mathbank-web/app/_components/ui.jsx` | `Icon`, `PageHeader`, `Pill`, `IconButton`, `Avatar`, `StatCard`, `Callout`, `EmptyState`, `SectionTitle`, `Bar`, `Pager`, `TabBar` (in-page `role="tab"` pills). Usable from server components (no hooks). |
| Route tabs | `mathbank-web/app/_components/NavTabs.jsx` | Pill tabs for routes; the longest matching prefix is active. |
| Shell | `mathbank-web/app/AppShell.jsx`, `app/layout.jsx` | Sidebar, top bar, breadcrumbs, "Ask the tutor" shortcut and a user menu: student, admin on `/admin/*`, or a "Student login" link. |
| Navigation model | `mathbank-web/lib/navigation.mjs` | `NAV_GROUPS`, `activeHref`, `breadcrumbs`, `avatarFor`; unit tested in `tests/navigation.test.mjs`. |
| Composer | `mathbank-widgets/src/MathComposer.jsx`, `VoiceControls.jsx`, `icons.jsx` | Scoped `.mbw-*` styles that React 19 hoists (`<style href precedence>`), so `mathbank-live` gets the same look. Re-sync after edits: `make -C mathbank-web sync-widgets` and `make -C mathbank-live sync-widgets`. |
| Source diagrams | `mathbank-web/app/_components/ProblemDiagrams.jsx` | Responsive question-specific figures with accessible labels and explicit loading failures; no whole-page fallback. See [31](31_QUESTION_SPECIFIC_DIAGRAMS.md). |
| Original document viewer | `mathbank-web/app/_components/ProblemSource.jsx` | Compact Source toggle above figures; opens a full-width PDF iframe only on click, including when no crop exists. Labels the full document separately and provides a new-tab fallback. Shared by chat/history, corpus, guided practice and step solving. See [31](31_QUESTION_SPECIFIC_DIAGRAMS.md). |

## 3. Page coverage

| Area | Pages | Status |
|---|---|---|
| Student | `/` (tutor chat + agent activity timeline), `/learn`, `/learn/solve/[code]`, `/learn/conversations`, `/profile`, `/login` | ✅ revamped |
| Admin | `/admin` (analytics dashboard), `/admin/textbooks`, `/admin/textbooks/problems/[code]`, `/admin/imports`, `/admin/knowledge-gaps`, `/admin/conversations`, `/admin/pedagogy`, `/admin/widgets`, `/admin/login` | ✅ headers, tabs, pagination, menu; inner tables keep Bootstrap styling |
| Explore | `/db/*`, `/graph/*` | ✅ section headers and route tabs; ⏳ inner page bodies still use the older `dbStyles.js` classes and some inline styles |
| Live | `mathbank-live` console and classroom | ✅ shares the new composer; ⏳ its page chrome is not yet on the kit |

## 4. Verification

### Evidence-backed coaching activity

Activity includes deterministic allowlisted retrieval/context summaries, with
graph degradation and machine approval qualified rather than implied verified.
Private thoughts and raw tool payloads remain excluded. The tutor prompt requests
an answer-free context lookup, a concise teaching roadmap and one first checkpoint
for selected-problem coaching; this is not a full solution or internal reasoning.
Unit and desktop/mobile mocked browser cases cover evidence visibility and redaction.

### Server and UI formatting controls

Shared math preparation handles single/double-escaped delimiters and trims inner
delimiter whitespace without changing code or link destinations. A real ADK
presentation formatter provides bounded exact-span bold/italic and token-driven
given/goal/insight/warning styles; final formatter output is pinned to a validated
tool result. An automatic root-agent final-output guard runs without extra
inference; the UI independently handles streaming text and archived messages.
Desktop/mobile mocked browser tests verify three rendered SMT formulas, no
visible delimiter backslashes, inline math within semantic highlights, preserved
code, distinct Problem/Source panels and no overflow/page errors. Existing
diagram/source-pane cases and production build pass. Scripted ADK delegation
tests verify preservation/authorization, not live paid-model style selection.

### Multimodal attempts and artifacts

Tutor practice statements now have a tinted problem panel and a separate neutral
source panel; surrounding coaching remains outside both. Explicit generated
geometry requests render private validated SVG previews in chat, labelled
"Generated illustration · not the source figure". Desktop/mobile mocked
browser tests at 1440/390 px verify distinct backgrounds, loaded diagrams and
no horizontal overflow. The immediate geometry capability is separate from
staff publication; illustrative quadrilateral incircles are computed from
actual vertices, not guessed to satisfy the theorem.

The same private declarative preview component supports Algebra, Combinatorics
and Number Theory. Algebra equation lines render through the existing KaTeX
renderer below the safe SVG image. An additional mocked browser case verifies
this path; the latest production build passes. Root specialist tool calls appear
in chat activity, but nested ADK AgentTool child events are not yet streamed.

Embedded source-diagram rendering now recognizes `[asy]...[/asy]` and fenced
Asymptote in the shared math renderer (chat, practice, corpus detail/solutions).
The statement is KaTeX-formatted; source code is collapsed below the rendered
PNG. Inline/unclosed model Problem/Source labels keep the full statement in
the problem panel instead of turning it into an unformatted title.
Incomplete streaming blocks wait. The macOS compiler is authenticated,
OS-isolated and credential-free; missing/unsupported renderers show explicit
errors. No browser code execution or fabricated replacement figure is used.
Verification: 90 web units (including real isolated compiler and filesystem/network
denial checks) and seven focused browser cases passed. AIME_2016_I_Q04 had
flattened `//` comments in its imported diagram; with explicit user approval,
only that block was replaced with the supplied valid source. Problem wording and
official answer were preserved. Live authenticated rendering returned PNG/200
and the corpus detail image loaded at 283 pixels wide. No paid inference or
embedding refresh was run.

Practice recommendations now use verified complete candidates: required diagrams
must be present and readable; unparsed figures are skipped instead of offered
with an unavailable-image warning. The direct original PDF/source link stays
visible beside Source. Source or ordinary PDF-link click opens the shared split
pane; mobile uses a bottom pane with an accessible Close control.

Cached PDFs with an unambiguous text location or current-PDF-hash extraction
coordinates open at the verified physical page. Both a highlighted page preview
and an annotated full-document PDF are shown, without altering the original.
Ambiguous/unknown locations receive no guessed highlight. Web-only sources
explicitly report no registered PDF and retain their original link.
SMT 2010 Geometry Q06's image and direct PDF were verified live; the actual
question text is on physical page 1. Seven focused browser regressions passed,
including mobile closing and web-only fallback. Paid tutor tool-selection
quality was not tested.

The shared shell now includes `/learn/attempt-media`, `/admin/attempt-media` and
`/artifacts`. They reuse the wide layout, Inter/Bootstrap theme, status pills,
breadcrumbs, master-detail pattern and pagination. Original student evidence is
primary; LaTeX candidates and assessments are distinct, ungraded attempts show
"Awaiting assessment", and private image/video regions and audio seeking remain
inside the review workspace. Destructive/paid actions require explicit controls.

Artifact playback uses validated server-rendered SVG frames rather than injecting
model-authored SVG into the page. Semantic search/index requests use the verified
embedding profile and explicit confirmation. Expired-session and service errors
are visible and disable creation rather than masquerading as empty data.

Verified: 25 focused unit/regression tests, 17 mocked Playwright cases with
desktop/mobile checks, and a successful production Next.js build. Live-provider
quality verification remains blocked by external account quota; see
[runtime acceptance progress](32_MULTIMODAL_ATTEMPTS_AND_ARTIFACTS.md).

- Unit tests: `make -C mathbank-web test` (includes `tests/navigation.test.mjs` and the widget tests).
- E2E: `cd mathbank-web && npx playwright test` against the running stack. The suite relies on the accessible names and
  test ids listed in the skill; keep them when restyling.
- Visual: check each touched route at 1440 px and 390 px. Use `http://localhost:5173` (the Playwright `baseURL`) for automated browsers. With
  `127.0.0.1` the Next 16 dev server rendered the pages, but no client fetches ran (observed 2026-10-08).
