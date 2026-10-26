---
name: modern-ui-design
description: 'Design and revamp MathBank web UIs (mathbank-web, mathbank-live, mathbank-widgets, mathbank-exam-web, mathbank-socratic-admin, mathbank-ml-frontend) into one calm, wide, low-clutter workspace look: rail + searchable sidebar + canvas + detail drawer, full-width focus view with selection tray for search/select, preview sidecar, scoped micro chat, real-estate budget, typography roles, consistent theme tokens, Inter font, Bootstrap Icons, pills instead of prose, explanation highlights, pagination, master-detail and drill-down, breadcrumbs, sidebar menu, avatars, analytics dashboards, fewer buttons, natural-language input with the microphone inside the composer, and the LaTeX/KaTeX math presentation contract (delimiters, normalisation of control-character-damaged TeX, no choices or Markdown in a question stem). Use when asked to restyle, modernise, declutter, add a page, fix broken math rendering, or review UI consistency.'
argument-hint: 'Optional scope: a route (/learn, /admin/...), a package (mathbank-live), or "audit" for a review-only pass'
---

# MathBank modern UI design system

Students use this every day, often on a laptop beside a notebook. Every screen must be
**calm, wide, scannable and quick to act on**. This skill is the contract for UI work in
`mathbank-web/`, `mathbank-live/`, `mathbank-exam-web/`, `mathbank-socratic-admin/` (Studio),
`mathbank-ml-frontend/` and the shared `mathbank-widgets/` package. The **workspace shell standard**
(layout zones, navigation, drawers, focus view, sidecar, micro chat, templates and examples) is in
[WORKSPACE_SHELL.md](WORKSPACE_SHELL.md) and applies to every module. The requirement and progress record is `requirements/30_MODERN_UI_DESIGN_SYSTEM.md`.

`mathbank-exam-web` is a separate Vite app with its own `src/theme.css`, but it is governed by
this same contract — especially the math presentation rules below, since every screen it renders
is mathematical content produced by an LLM.

## Non-negotiables

1. **One theme.** Colours, radius, shadows, spacing and type come from the tokens in
   `mathbank-web/app/globals.css` (`--mb-*`, plus the Bootstrap `--bs-*` overrides). Never
   hard-code hex colours, `style={{ color: "#666" }}`, font sizes or one-off shadows in JSX.
2. **One shell.** Pages render inside `AppShell` (sidebar plus top bar with breadcrumbs and an avatar).
   Pages must not add their own "← Back to chat" links, link rows or duplicate site
   navigation; the sidebar and breadcrumbs handle that.
3. **One header per page.** Use `<PageHeader icon title subtitle actions pills />` from
   `app/_components/ui.jsx`. Exactly one `<h1>`; the subtitle is one short sentence.
4. **Wide layout.** The main area is full width with `--mb-gutter` padding. Reading
   text (statements, hints, chat bubbles) caps at about 80ch inside wide grids.
5. **No hydration drift.** Server and client markup must match: no `Date.now()`,
   `Math.random()`, `typeof window` branches or locale dates during render, and no stray
   `{" "}` text nodes between block siblings. Load client-only state after mount (`useEffect`), as
   `AppShell` does for the signed-in student.
6. **Accessibility survives icon-only UI.** Every icon-only control has an `aria-label`
   and a `title` tooltip that keeps the old visible text, so tests and screen readers keep
   working. Decorative icons get `aria-hidden="true"`. Keep visible focus rings.
7. **Never break test contracts.** Preserve `data-testid`, form labels and accessible names
   used by `mathbank-web/e2e/*.spec.mjs` and `mathbank-live/e2e`. If a heading or label must
   change, update the spec in the same change.
8. **Math is rendered, never shown raw.** Every string that can contain TeX goes through a
   math-aware renderer (`MathText`), never into `{text}` or `dangerouslySetInnerHTML`. Math is
   normalised before it is rendered and KaTeX always runs with `throwOnError={false}`. See
   *Math and LaTeX presentation* below — it is the single most common source of visible
   breakage in this product.

## Foundations

| Token | Use |
|---|---|
| Font | `@fontsource-variable/inter` (self-hosted, no CDN). Tabular numbers (`.mb-num`) in tables and stats. KaTeX keeps its own math font. |
| Icons | `bootstrap-icons` font via `<Icon name="lightbulb" />`. One icon per concept, used consistently (see map). |
| Primary | Indigo `--mb-primary` (#4f46e5); success emerald, warning amber, danger rose, info sky. |
| Surfaces | App background `--mb-bg`; cards white with `--mb-border` and `--mb-shadow-sm`; radius `--mb-radius` (14px). |
| Density | 8px spacing scale; touch targets at least 36px; tables use `table-hover align-middle`. |

### Icon vocabulary (keep consistent)

| Concept | Icon | Concept | Icon |
|---|---|---|---|
| Tutor chat | `chat-dots` | Guided practice | `signpost-split` |
| Step-by-step solve | `list-check` | Hint | `lightbulb` |
| Problem | `file-earmark-text` | Solution | `journal-check` |
| Concept / taxonomy | `diagram-3` | Technique | `tools` |
| Skill / mastery | `bullseye` | Knowledge gap | `exclamation-diamond` |
| Recovery detour | `sign-turn-right` | Graph | `bezier2` |
| Corpus / database | `database` | Search / similar | `search` / `stars` |
| Conversations | `chat-left-text` | Progress | `graph-up-arrow` |
| Imports | `box-arrow-in-down` | Textbooks | `book` |
| Widgets | `puzzle` | Admin dashboard | `speedometer2` |
| Microphone | `mic` / `mic-fill` (recording) | Listen | `volume-up` |
| Send / Stop | `arrow-up` / `stop-fill` | AI format | `magic` |
| Diagram | `image` | Diagnosis | `activity` |
| Micro chat | `chat-square-dots` | Ask AI (proposals) | `stars` |
| Drawer settings | `sliders` | Close layer | `x-lg` |
| Search & attach | `search` | Exclude for audience | `slash-circle` |

## Components (`mathbank-web/app/_components/ui.jsx`)

| Component | Rules |
|---|---|
| `Icon` | Wraps `bi bi-*`; decorative by default; pass `label` to make it meaningful. |
| `PageHeader` | Icon tile, the `h1`, a one-line subtitle, optional `pills` (status chips) and at most 2 `actions`. |
| `Pill` | Status, counts and tags. Tones: `primary success warning danger info neutral`. Prefer an icon pill over a sentence ("AI-ranked", "Checkpoint", "3 hints"). |
| `IconButton` | Square ghost button with tooltip and `aria-label`; use for secondary actions instead of text buttons. |
| `Avatar` | Initials with a deterministic tone from the name or email (stable across server and client). Used in the shell, transcripts and lists. |
| `StatCard` | KPI tile: icon, tabular value, label, optional hint or progress, optional `href` for drill-down. |
| `Callout` | Explanation highlight: `tone="insight|hint|warning|success|danger"` with an icon and a left accent. Use it for micro-lessons, hints, feedback and "why" notes instead of `alert` boxes. |
| `EmptyState` | Icon, one line and at most one action. Never a paragraph. |
| `SectionTabs` | Icon pill links for sub-sections (corpus, graph). In-place tab panels keep `role="tab"`. |
| `Pager` | Icon prev/next, "Page N" and the row range; never unmounts the table. |
| `Bar` | A CSS distribution bar for dashboards; no chart library. |
| Breadcrumbs | Rendered by the shell from the pathname (`lib/navigation.mjs`). Never rebuilt per page. |

## Layout patterns

- **Shell:** a 248px sidebar (a 72px icon rail when collapsed, off-canvas below 992px), grouped as
  *Learn*, *Explore* and *Admin*. The top bar has breadcrumbs on the left and the avatar menu on the right.
  The active item has a tinted pill and `aria-current="page"`.
- **Master-detail:** list on the left, detail on the right (`.app-master-detail`); the selected
  row gets a primary left bar. On narrow screens, stack them.
- **Drill-down:** stat card → filtered list → detail. Each level has a URL (query string
  or route) so breadcrumbs and the back button work.
- **Dashboards:** first row has 4–6 `StatCard`s; then distribution `Bar`s and recent activity;
  dense tables last, inside collapsible sections when they are operator-only.
- **Student workspaces:** the problem stays visible (sticky on wide screens); the composer
  sits at the bottom of the working column; hints, diagnosis and the solution path go in a right
  rail as `Callout`s and timelines.

## Workspace shell standard (all modules)

Approved 2026-10-25 from the Socratic Studio: **this look must be consistent across every module.**
Full templates, examples and code skeletons: [WORKSPACE_SHELL.md](WORKSPACE_SHELL.md).

- **Zones:** icon rail (56–60px) · searchable sidebar (240–260px) · canvas (reading width ≤ 860px)
  · drawer (400–440px) · sidecar (400–420px). At most three content zones visible; on phones the
  sidebar, drawer, sidecar and micro chat become overlays.
- **One job per surface:** canvas = read/overview, **drawer** = edit one item, **focus view** =
  search/select at full width with a sticky **selection tray**, **sidecar** = preview or micro chat.
- **Finder for large libraries (reuse first):** full-width facets · results · inspector/target
  mini-map, families collapsed, match reason shown, link vs fork chosen at wire time, *find
  similar* before *Create new* ([WORKSPACE_SHELL §7a](WORKSPACE_SHELL.md)).
- **Return to origin:** ✕/Esc closes the top-most layer, unsaved edits stay in the draft and
  keyboard focus returns to the opener.
- **Typography roles only:** micro label 10/700 caps · kicker 12/650 caps · hero 27–29/720 (the one
  `h1`) · section 15/700 · body 14 · meta 12 muted · tabular numbers.
- **Pills/chips by tone meaning** (success = done/approved/saved, warning = needs attention,
  danger = blocked/excluded, primary = current, neutral = metadata); ≤ 3 per row; never prose.
- **Micro chat** is a separate module scoped to one item (step, quiz item, video, exam question,
  or the student's current step): context chip, quick-prompt pills, `MathComposer` with mic/send
  inside, AI changes only as *Apply/Dismiss* proposal cards, thread per item, Esc to close.
- The existing `mathbank-web` `AppShell` (248px grouped sidebar) is the student/admin variant of the
  same zones; new pages adopt drawer/focus-view/sidecar/micro-chat patterns rather than new layouts.

## Math and LaTeX presentation

Almost every string in this product is LLM-authored mathematics. Treat it as **untrusted,
frequently damaged input** that must be repaired on the way in *and* on the way out. The rules
below are the whole contract; the implementations are listed at the end of the section.

### Authoring contract (what a generator may emit)

- **Delimiters:** `\( ... \)` for inline math, `\[ ... \]` for display math. Never `$...$` or
  `$$...$$` in newly generated content — single `$` is ambiguous with currency and splits badly
  across line breaks. (Renderers still *accept* `$`-forms for historical rows; generators must
  not produce them.)
- **One field, one job.** The question stem holds the stem only. Never duplicate MCQ answer
  choices inside the stem, and never emit answer labels like `\textbf{(A)}` / `\qquad` choice
  rows there — the options array and the UI render them. A paired `prompt_latex` field stays
  `null`; the text field already carries its own math.
- **No Markdown inside a stem or option.** No `**bold**`, no headings, no bullet syntax. The UI
  supplies all emphasis via tokens and `Callout`s. (`mathbank-web`'s tutor stream is the one
  exception: it is deliberately Markdown + `remark-math`.)
- **JSON escaping is the generator's job.** A model writing JSON must emit `\\frac`, not
  `\frac` — see the failure mode below.

### Normalisation contract (repair before anything else)

The classic corruption: a model emits JSON in which `\f`, `\t`, `\b` and `\r` are parsed as
**control characters**, so `\frac` arrives as `\x0c` + `rac` and `\text` as a tab + `ext`.
Normalisation must therefore match **the control character plus the command remainder**, not a
literal backslash sequence:

| Damaged | Repaired to |
|---|---|
| `\x08` + `egin` | `\begin` |
| `\x0c` + `rac` | `\frac` |
| `\r` + `ight` | `\right` |
| `\t` + `ext` | `\text` |
| `\\\\(`, `\\\\)`, `\\\\[`, `\\\\]` (2+ backslashes) | single-backslash delimiter |
| literal two-character `\n` | a real newline |

Normalise on **both sides, deliberately**:

- **Backend**, before criticism and before persistence — so no new row is ever stored damaged.
- **Frontend**, at render time — so the thousands of already-persisted historical rows still
  render. Removing either half is a regression, not a simplification.

### Deterministic rejection (not a judgement call)

After normalisation, content is **rejected outright** — no LLM opinion involved — when it:

- still contains a control character (`\x08 \x0c \r \t`);
- has unbalanced inline delimiters (`\(` count ≠ `\)` count) or display delimiters (`\[` vs `\]`);
- is an MCQ that doesn't have exactly four options, unique keys, distinct option texts, a
  `correct_key` naming one of them, and exactly one explanation per key.

These run as cheap pre-checks before any expensive critic pass. A failing draft is regenerated
or fails the paper closed — never persisted "for review".

### Rendering contract (the UI half)

- Split text on `\[...\]`, `\(...\)`, `$$...$$`, `$...$` — **block forms before inline forms**,
  or `$$a$$` mis-splits into two `$...$` runs. Render each math span with KaTeX and leave the
  rest as plain text with `white-space: pre-wrap`.
- `throwOnError={false}` plus a `try/catch` that falls back to the **raw source text**. One
  malformed expression must degrade to visible TeX, never blank the span or crash the page.
- A `$...$` run containing two or more `\qquad`s is an answer-choice row: render it as a block,
  not inline.
- Math lives on contained surfaces: `.mb-math-inline` (plain `display: inline`) and
  `.mb-math-display` (bordered, padded, `overflow-x: auto`, `max-width: 100%`). Long expressions
  scroll inside their own box — they never widen the page or trigger horizontal scroll.
- KaTeX keeps its own math font; never override it with the Inter stack.

### Implementations (extend these, don't fork them)

| File | Role |
|---|---|
| `mathbank-exam-agent/src/mathbank_exam_agent/math_format.py` | Canonical backend normaliser and the deterministic format/MCQ checks (`normalize_math_text`, `normalize_draft_math`, `math_format_issues`, `mcq_structure_issues`). |
| `mathbank-exam-web/src/components/mathText.js` | JS mirror of the same normalisation (`normalizeMathText`). Keep the two tables in sync. |
| `mathbank-exam-web/src/components/MathText.jsx` | Split + KaTeX render with raw-text fallback. |
| `mathbank-exam-web/src/theme.css` | `.mb-math-inline` / `.mb-math-display` surfaces. |
| `mathbank-web/lib/markdownText.mjs` | `prepareMathMarkdown` — the Markdown pipeline's converse: rewrites `\(...\)`/`\[...\]` into `$`/`$$` for `remark-math`, while leaving fenced code, inline code, `[asy]` blocks and link targets verbatim. |
| `mathbank-web/app/_components/MathText.jsx` | The tutor-stream renderer (`remark-math` + `rehype-katex` + widgets). |

## Natural-language input

- One composer component (`MathComposer` in `mathbank-widgets`) wherever students type.
- It is a single rounded field. **Mic and Send sit inside the field, bottom-right**; formatting
  tools (∑ symbols, `$x$` quick format, ✨ AI format) are small ghost icons bottom-left.
  Enter sends in single-line mode; Shift+Enter adds a new line; ⌘/Ctrl+Enter always sends.
- While streaming, Send becomes Stop in the same position. The mic shows a recording pulse.
- Placeholders are short ("Ask anything… use $x$ for math"), not a manual.

## Writing rules (less clutter)

- Replace explanatory paragraphs with a pill, a tooltip (`title`) or an info icon.
- No repeated labels: if the section title says "Hints", items don't repeat "Hint:".
- No implementation leakage in student UI (table names, `make` targets, provider names).
  Admin UI may show them in `<code>` inside collapsible details.
- At most **one primary button** per region; everything else is ghost or icon.
- Dates go through a formatter after mount; never in server-rendered markup.

## Procedure

1. Read `app/globals.css`, `app/_components/ui.jsx`, `app/AppShell.jsx` and
   `lib/navigation.mjs`; extend the tokens and components rather than adding page-local styles.
2. For each page in scope: swap the header for `PageHeader`, remove duplicate nav links,
   convert badges to `Pill`, explanatory alerts to `Callout`, secondary text buttons to
   `IconButton`, and inline colours to tokens.
3. Keep data fetching, state machines and API calls unchanged unless the user asks
   otherwise; this is a presentation-layer change.
4. Grep the e2e specs for each touched page's test ids and accessible names and keep them.
5. Verify:
   - `node --test tests/` (unit) and, with the stack up, `npx playwright test` (e2e; `@llm`
     specs only when `E2E_LLM=1`).
   - Open each touched route in the integrated browser at 1440px and 390px widths; check
     there are no console or hydration errors, no horizontal scroll and visible focus states.
   - On any route showing LLM-authored mathematics, confirm no raw `\frac`, stray backslashes,
     doubled `\\(` or literal `\n` are visible, and that long display math scrolls inside its
     own box rather than widening the page.
6. Update `requirements/30_MODERN_UI_DESIGN_SYSTEM.md` (status and remaining pages).

## Review checklist

- [ ] Single `h1` via `PageHeader`; breadcrumbs correct; sidebar item active.
- [ ] No hard-coded colours, font sizes or `#666` text; inline `style` only for layout sizes.
- [ ] Icons follow the vocabulary; icon-only controls have `aria-label` and `title`.
- [ ] Status shown as pills; explanations as callouts; at most one primary button per region.
- [ ] Lists over 25 rows paginate; master-detail selection is visible and reachable by keyboard.
- [ ] Composer: mic and send inside the field; Stop replaces Send while streaming.
- [ ] Every TeX-bearing string goes through `MathText`; normalised first; KaTeX falls back to
      raw text instead of crashing; display math is contained and scrollable.
- [ ] No answer choices, answer labels or Markdown leaked into a question stem.
- [ ] No hydration warnings; e2e test ids and names intact; usable at 390px.
- [ ] Workspace shell: editing in a drawer, search/select in a focus view with a tray, previews
      and micro chat in the sidecar; ≤ 3 content zones; Esc closes the top layer and focus returns.
- [ ] Typography roles and pill tones follow [WORKSPACE_SHELL.md](WORKSPACE_SHELL.md) §3 and §6.
