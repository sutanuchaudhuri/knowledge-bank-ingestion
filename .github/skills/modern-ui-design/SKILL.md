---
name: modern-ui-design
description: 'Design and revamp MathBank web UIs (mathbank-web, mathbank-live, mathbank-widgets) into a modern, wide, low-clutter, student-friendly interface: consistent theme tokens, Inter font, Bootstrap Icons, pills instead of prose, explanation highlights, pagination, master-detail and drill-down, breadcrumbs, sidebar menu, avatars, analytics dashboards, fewer buttons and natural-language input with the microphone inside the composer. Use when asked to restyle, modernise, declutter, add a page, or review UI consistency.'
argument-hint: 'Optional scope: a route (/learn, /admin/...), a package (mathbank-live), or "audit" for a review-only pass'
---

# MathBank modern UI design system

Students use this every day, often on a laptop beside a notebook. Every screen must be
**calm, wide, scannable and quick to act on**. This skill is the contract for UI work in
`mathbank-web/`, `mathbank-live/` and the shared `mathbank-widgets/` package. The
requirement and progress record is `requirements/30_MODERN_UI_DESIGN_SYSTEM.md`.

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
6. Update `requirements/30_MODERN_UI_DESIGN_SYSTEM.md` (status and remaining pages).

## Review checklist

- [ ] Single `h1` via `PageHeader`; breadcrumbs correct; sidebar item active.
- [ ] No hard-coded colours, font sizes or `#666` text; inline `style` only for layout sizes.
- [ ] Icons follow the vocabulary; icon-only controls have `aria-label` and `title`.
- [ ] Status shown as pills; explanations as callouts; at most one primary button per region.
- [ ] Lists over 25 rows paginate; master-detail selection is visible and reachable by keyboard.
- [ ] Composer: mic and send inside the field; Stop replaces Send while streaming.
- [ ] No hydration warnings; e2e test ids and names intact; usable at 390px.
