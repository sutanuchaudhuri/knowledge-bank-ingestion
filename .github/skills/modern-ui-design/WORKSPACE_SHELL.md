# Workspace shell standard — templates and examples

This is the reference for the **calm workspace look** first shipped in the Socratic Studio
(`mathbank-socratic-admin`) and approved as the look for **every MathBank module**: student
(`mathbank-web`, `mathbank-exam-web`), live (`mathbank-live`), staff (Studio, `mathbank-web/admin`),
and ML ops (`mathbank-ml-frontend`). The contract in [SKILL.md](SKILL.md) still governs tokens,
math, accessibility and testing; this file shows **how to lay out and compose screens**.

Live references: [Studio source](../../../mathbank-socratic-admin/src/) and the clickable
[navigation prototype](../../../documentation/architecture/prototype/studio-unified-navigation.html).

---

## 1. Design principles

| # | Principle | In practice |
|---|---|---|
| P1 | **One job per surface** | The canvas shows the thing being worked on; editing happens in a drawer; searching/selecting happens in a focus view. Never all three on one surface. |
| P2 | **Progressive disclosure** | Show the minimum to decide. Details, staff/debug tools, history and technical identifiers live in a drawer, a `<details>` or a tooltip. |
| P3 | **Pills, not prose** | Status, counts, roles, topics and states are pills/chips. A sentence is allowed once per screen (the hero description). |
| P4 | **One primary action per region** | Region = top bar, drawer footer, tray, card. Everything else is a light button, link or icon button. |
| P5 | **Return to where you were** | Every temporary surface (drawer, focus view, sidecar, micro chat) closes with ✕ or **Esc**, keeps unsaved edits in the draft, and **restores keyboard focus** to the control that opened it. |
| P6 | **Context stays visible** | The breadcrumb says where you are; drawers and focus views say what they act on ("For step “Check the justification” · Quiz"). |
| P7 | **Truth comes from the server** | Saved/unsaved/review states, grades, routing and permissions are shown from server responses, never inferred in the UI. |
| P8 | **AI proposes, people decide** | AI output appears as a proposal card with *Apply/Accept* and *Dismiss*; it never edits silently. |
| P9 | **Calm visuals** | White surfaces, one accent (`--mb-primary`), soft borders, 9–14px radii, almost no shadows, generous whitespace, no gradients/emoji decoration. |

## 2. Real-estate budget

Desktop layout is a horizontal set of **zones**. At most **three content zones** are visible at
once (plus the rail); opening a fourth hides the least relevant one.

```
┌──────┬────────────┬──────────────────────────────┬─────────────────┬──────────────┐
│ Rail │ Sidebar    │ Canvas                       │ Drawer          │ Sidecar      │
│ 56–60│ 240–260    │ flex; reading width ≤ 860    │ 400–440         │ 400–420      │
│ views│ search +   │ hero + one representation    │ edit one thing  │ preview /    │
│      │ grouped    │ (flow, list, cards, student) │ head/body/foot  │ micro chat   │
│      │ list       │                              │                 │              │
└──────┴────────────┴──────────────────────────────┴─────────────────┴──────────────┘
```

| Situation | Visible zones |
|---|---|
| Browsing | Rail · Sidebar · Canvas |
| Editing an item | Rail · Sidebar · Canvas · Drawer (sidebar may collapse < 1280px) |
| Previewing while editing | Rail · Canvas · Drawer · Sidecar (sidebar hidden) |
| Searching / selecting (**focus view**) | Rail · Focus view (facets 220 + results) · optional Sidecar |
| Finding & wiring at scale (**Finder**, §7a) | Rail · Facets 220 · Results (flex) · Inspector **or** target mini-map 380 · sticky tray |
| Phone (< 760px), **staff tools** | Rail · Canvas; sidebar slides in over a scrim; drawer/sidecar/micro chat are full-height overlays; focus view hides facets behind a *Filters* button. **Student apps use the separate device layouts in §2b.** |

Rules:
- Reading text caps at ~80ch; cards/flows cap at ~720–860px and centre in the canvas.
- Never let a zone cause horizontal page scroll; long math, JSON and codes scroll **inside** their box.
- A hidden zone must be truly hidden (`display:none` / `visibility:hidden`), not just moved
  off-screen, so it can't take focus or intercept clicks.
- Sticky elements: top bar, drawer footer, focus-view tray. Nothing else is sticky.

## 2b. Device classes for student apps (phone, tablet, desktop)

Student apps (mathbank-web `/learn`, exam-web, live student view) get **separate compositions per
device class**, not a squeezed desktop. Requirement and wireframes:
[69](../../../documentation/requirements/69_MOBILE_TABLET_VOICE_STUDENT_EXPERIENCE.md),
[student-mobile-voice-wireframes.html](../../../documentation/architecture/prototype/student-mobile-voice-wireframes.html).

| Class | Width | Navigation | Zones | Detail | Voice entry |
|---|---|---|---|---|---|
| Phone | < 600 | **Bottom tab bar** (Today · Learn · Practice · Exams · Me) + app bar (back · title · ≤ 1 action) | 1 column | **Bottom sheet** (half → full) | Floating 🎙 button above the tab bar → full-screen voice session |
| Tablet portrait | 600–899 | Bottom tab bar | 1 column, reading width ≤ 720 | Bottom or right sheet ≤ 50% | **Voice dock** under the content |
| Tablet landscape | 900–1199 | Icon rail (no sidebar) | **Split view**: content + companion 360 (tutor/voice transcript or exam navigator) | Right sheet | Voice in the companion |
| Desktop | ≥ 1200 | Rail + sidebar | §2 zones | Drawer | Mic in composer + voice dock |

```
PHONE                     TABLET PORTRAIT                 TABLET LANDSCAPE
┌──────────────┐          ┌────────────────────────┐      ┌──┬──────────────┬────────┐
│ ← Title    ⋯ │          │ ← Title              ◔ │      │⌂ │ ← Title      │Companion│
│              │          │ content ≤ 720          │      │▤ │ content      │ tutor / │
│ one column   │          │                        │      │✎ │              │ voice / │
│              │          │ ┌ voice dock ────────┐ │      │⏱ │              │ exam nav│
│         (🎙) │          │ └────────────────────┘ │      │◔ │ [◂]    [▸]   │         │
│ [2nd] [Pri ▸]│          │ [2nd]          [Pri ▸] │      └──┴──────────────┴────────┘
│ ⌂ ▤ ✎ ⏱ ◔    │          │ ⌂  ▤  ✎  ⏱  ◔          │
└──────────────┘          └────────────────────────┘
```

Rules: touch targets ≥ 44 px; `env(safe-area-inset-*)`; inputs ≥ 16 px; `100dvh`; no hover-only
actions; the **one primary action sits bottom-right in thumb reach**; the keyboard hides the tab bar;
features that don't fit a class show a calm *Best on a larger screen* card with *Email me the link*,
never a broken layout (availability matrix in req 69 §3).

## 3. Typography and spacing

Font: **Inter Variable** (self-hosted). KaTeX keeps its own font. Use these roles only:

| Role | Size / weight | Use |
|---|---|---|
| Micro label | 10px / 700, uppercase, letter-spacing .11em, muted | Sidebar group titles ("WORKSPACES") |
| Kicker | 12px / 650, uppercase, letter-spacing .04em, primary | Above every hero title ("DESIGNER", "STUDENT SIMULATION") |
| Hero (the one `h1`) | 27–29px / 720, letter-spacing −.03em | Page/view title |
| Section | 15px / 700 | Drawer sections ("Connections", "Step content") |
| Body | 14px / 400, line-height 1.5 | Everything else |
| Meta | 12px / 400, muted | Subtitles under names, counts, timestamps |
| Numbers | `font-variant-numeric: tabular-nums` | Tables, stats, timers |

Spacing scale: 4 · 8 · 12 · 14 · 16 · 22 · 30px. Radius: 7 (chips) · 9 (inputs/buttons) ·
12 (cards) · 14 (boxes). Shadows only for floating layers (drawer overlay on phones, toast, tray).

## 4. Navigation template

| Element | Contents | Rules |
|---|---|---|
| **Rail** | Logo, 4–6 view icons, spacer, avatar, sign-out | Icon-only with `aria-label` + `title`; active view tinted with `aria-current="page"`; each view has a URL/hash. |
| **Sidebar** | Module title, **search box**, grouped list (micro label + items), *Quick actions* | Search is a separate pure module (see `mathbank-socratic-admin/src/search.ts`): multi-term, accent/case-insensitive, grouped results, count in a status line. Items show title + one muted meta (domain, revision). |
| **Top bar** | Breadcrumb · spacer · status pills · ≤ 1 icon button (settings) · ≤ 1 light button · 1 primary | Breadcrumb ends with the current object, not the view name. Status pills: *Saved · r4*, *Unsaved changes*, *Local test session*. |
| **Canvas hero** | Kicker · `h1` · one-line description · ≤ 1 light action | Representation switches (e.g. Flow / Natural language / JSON) use the segmented control directly below. |

Keyboard: Tab order rail → sidebar → top bar → canvas → drawer. **Esc** closes the top-most layer
(sidecar → focus view → drawer → mobile sidebar). Lists of cards support ↑/↓/Home/End when they
represent an ordered sequence.

## 5. Component templates

Use the module's kit (`mathbank-web/app/_components/ui.jsx`, `mathbank-socratic-admin/src/ui.tsx`).
Same names and behaviour everywhere.

| Component | Anatomy | Use / don't |
|---|---|---|
| `Hero` | kicker, `h1`, description, actions | Exactly one per view. |
| `Segmented` | 2–4 pressed toggle buttons with icons | Switch representation of the **same data**. Not for navigation (use the rail). |
| Item card / step node | glyph tile · name · meta · chips · trailing "Edit ›" | Whole card is one button opening the drawer. Secondary links (e.g. rules) sit below it, not inside. |
| `Pill` | tone + 1–3 words | See §6. |
| Chip | small neutral rounded tag | Attached items (`CHECK · Stars and bars AR`), topics, filters. Red chip only for exclusions. |
| `Drawer` | head (title + ✕) · scroll body · sticky footer (≤ 1 primary) | One drawer at a time; replaces its content when another item is opened. Edits apply to the draft live; *Save changes* persists. |
| Focus view | focus bar (← Back, kicker, context, "Esc returns") · facets column · results · sticky **tray** | For search, select, add-existing, bulk actions. Opens with focus in the search box. |
| Selection tray | count · role/target · light *Cancel* · primary *Attach / Apply & return* | Primary disabled until something is selected. |
| Sidecar | head (title + ✕) · iframe or native preview · footer note | Preview without leaving the current task. Selection inside it adds to the tray. |
| `Callout` / hint | tinted box, icon, one sentence | Explanations, warnings, impact previews. Not for errors from the server (use the alert banner). |
| Alert banner | below top bar, dismissable | Server errors and conflicts with explicit recovery buttons (*Reload*, *Discard & open*). |
| `EmptyState` | icon · one line · ≤ 1 action | Never a paragraph. |
| Toast | bottom-centre, 2–4s, one at a time, `role="status"` | Confirmation of a completed action only. |
| API disclosure (staff only) | `<details>` "API this action calls" | Prototypes and admin tools; never in student UI. |

## 6. Pills and chips — tone meaning

| Tone | Means | Examples |
|---|---|---|
| `success` | Done / approved / saved | *Saved · r4*, *Approved*, *Student here* |
| `warning` | Needs attention, not broken | *Unsaved changes*, *Review draft*, *Local test session*, *Critic-approved* |
| `danger` | Blocked / excluded / failed | *Excluded · Grade 9A*, *Failed* |
| `primary` | Current / active / selected | *Active*, *Move 2 of 30* |
| `neutral` | Metadata | *Quiz*, *r3*, *Course quiz*, topic names |

Max 3 pills in a row; put the rest in the drawer. Pills never contain sentences or buttons.

## 7. Interaction templates

**Open → edit → save**
1. Click a card → drawer opens for that item; card shows the selected ring.
2. Edits apply to the draft immediately; top bar shows *Unsaved changes*.
3. *Save changes* (drawer footer or top bar) → server response → *Saved · rN* + toast.
4. 409/stale → alert banner with *Discard edits & reload*; never auto-retry.

**Search → select → attach → return** (focus view)
1. From the drawer: *Search & attach* → focus view replaces sidebar + drawer, focus in search.
2. Pre-filled from context (topics, prompt); facets on the left; tick results; *Preview* opens the sidecar.
3. Tray: choose role/target → *Attach & return*.
4. Return to the drawer; focus on its content section; toast "Attached 2 items".

**Exclude for an audience**
1. *Exclude…* in a drawer → audience picker (group and/or pasted IDs).
2. *Preview impact* → hint shows affected students and side effects.
3. *Save exclusion* → red chip on the card.

**Preview without losing place**: *Preview* opens the sidecar (native render first; iframe for a
whole existing student page) — the drawer and its unsaved edits stay intact.

## 7a. Finder — full-width search & wire (for large libraries)

Use when the library is large (hundreds–thousands of items) and the goal is **reuse**: find, compare,
then wire into what is being built. It is a focus view with a third pane. Contract:
[plan 68 §4.13](../../../documentation/requirements/68_UNIFIED_STUDIO_PORTAL_PLAN.md).

```
┌──────┬──────────────┬──────────────────────────────────────┬──────────────────────────┐
│ Rail │ FACETS 220   │ ← Back  FINDER · for step “Justify”   │ INSPECTOR 380            │
│      │ Kind ☐ Step  │ [ justify why cases are disjoint  ⌘K]│ Step · Approved · r3     │
│      │      ☐ Quiz  │ chips: topic: incl–excl ✕  unused ✕   │ prompt / preview         │
│      │ Status       │ ─────────────────────────────────────│ Used in (12) · Lineage   │
│      │ Topic        │ ☐ ◆ Justify disjoint cases            │ [Compare with current]   │
│      │ Used / unused│   Step · 3 forks · matches intent     │ ── or in wire mode ──    │
│      │ Owner        │   [Approved] [Used 12×]               │ target mini-map:         │
│      │              │ ☐ ◆ Complement-count loop (4 steps)   │  ○ Setup → ○ Justify →   │
│      │              │   Sequence · matches intent + topic   │  [drop here: CHECK]      │
├──────┴──────────────┴──────────────────────────────────────┴──────────────────────────┤
│ TRAY  2 selected · Link ▾ / Fork · target: step “Justify” · CHECK   [Cancel] [Attach & return] │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

Rules:
- **Full width**: sidebar, drawer and canvas are hidden while the Finder is open; Back/Esc returns
  to the opener with focus restored (P5). Phone: one pane at a time (results → inspector), facets
  behind *Filters*, tray stays sticky.
- **Context first**: opened from an item, the query and chips are pre-filled from it (intent,
  topics, "not used here"). Chips are editable; AI-understood queries appear as chips, never as
  hidden filters.
- **Result row** = glyph · title · one meta line (kind, family size, *match reason*) · ≤ 3 pills
  (status, *Used N×*, *Indexing…*). Families (forks / near-duplicates) collapse into one row with a
  count; expand inline.
- **Inspector** shows the focused row: preview (native render), *Used in*, lineage, *Compare with
  current*. It never edits — editing happens in the drawer after returning.
- **Wire mode** swaps the inspector for a **mini-map of the target** (workflow graph or course
  outline). Drop or *Wire to…* shows role and **Link vs Fork** before confirming; invalid drops
  explain why (e.g. "a step can have only one CHECK").
- **Create is last**: *Create new* sits at the end of results; creating runs *find similar* and
  shows "N close matches — reuse instead?" before the editor opens.
- Keyboard: `/` search · ↑/↓ move · `Space` select · `Enter` inspect · `W` wire · `Esc` back.
- Performance feel: lexical results render immediately; semantic results merge in without
  reordering what the user is pointing at (pin the focused row); show skeleton rows, not spinners.

## 8. Micro chat (contextual AI, separate module)

A **micro chat** is a small conversation scoped to **one item** — a workflow step, a quiz item,
a video, an exam question or (for students) the current problem step. It is a reusable module
(`micro-chat`), not part of the Designer, so any screen can host it with a context object.

**Where it appears**
- Staff: *Chat about this* icon button in an item drawer header (`chat-square-dots`) and on item
  cards' hover actions. Opens in the **sidecar** zone (desktop) or a bottom sheet (phone).
- Students: the existing tutor chat stays the main conversation; micro chat is the inline
  "ask about this step/question" panel inside the workspace, using the same composer.

**Anatomy**

```
┌ Sidecar ───────────────────────────────────────┐
│ Chat about · [Quiz] Stars and bars AR  r3   ✕  │  ← context chip (kind · title · revision)
│ ─────────────────────────────────────────────  │
│ (Explain the distractors) (Make it harder)     │  ← 2–4 quick-prompt pills (only when empty)
│ (Add a hint) (Check the math)                  │
│                                                │
│  You: Why is option B tempting?                │  ← compact bubbles, MathText rendered
│  AI : Students who … [cites a-17 r3]           │
│  ┌ Proposal ──────────────────────────────┐    │  ← proposals as cards, never silent edits
│  │ Add hint H2: “Count the separators…”   │    │
│  │ [Apply to draft]  [Dismiss]            │    │
│  └────────────────────────────────────────┘    │
│ ─────────────────────────────────────────────  │
│ [ Ask about this item…            🎤  ➤ ]     │  ← MathComposer: mic + send inside the field
└────────────────────────────────────────────────┘
```

**Rules**
1. **Scoped**: the context chip is always visible; the conversation, its history and its
   proposals belong to that item (and revision). Switching items switches the thread.
2. **Grounded**: the server sends the item's safe context (staff view for staff, student-safe for
   students) and recent edits; answers cite ids/revisions. Students never receive answer keys
   through micro chat.
3. **Proposals, not edits**: suggested changes render as cards with *Apply to draft* / *Dismiss*.
   Applying goes through the normal write call with the item's base hash; stale → rejected.
4. **Small**: one column, compact bubbles, no avatars beyond a 20px initial, no system chatter;
   streaming shows a single typing indicator; *Stop* replaces *Send* while streaming.
5. **Closable and resumable**: ✕/Esc closes and restores focus; reopening shows the last 20
   messages of that item's thread; *New thread* is a link in the header menu.
6. **Costed and audited** (staff): per-staff budgets; each turn records model, prompt version,
   item ref and accepted/dismissed proposals.
7. **Accessible**: `role="log"` with `aria-live="polite"` for new messages; composer label
   "Ask about {item title}"; quick prompts are buttons.

**Contract (module API)** — see [requirement 68 §4.11](../../../documentation/requirements/68_UNIFIED_STUDIO_PORTAL_PLAN.md):
`POST /v1/admin/studio/micro-chat/threads {context:{kind,id,revision}}` → thread;
`POST …/threads/{id}/messages {text}` (streams); `POST …/proposals/{id}/apply {expected_hash}`.
Student micro chat reuses the tutor agent with a step/question-scoped context.

## 8a. Voice session (real-time voice agent, separate module)

Anatomy (phone full-screen; tablet as a dock; landscape inside the companion):

```
┌──────────────────────────┐
│ ↓  Tutor · Quiz item 3   │  context chip + [Captions] (on by default)
│ Tutor: Which option…?    │  live transcript, math rendered
│ You: I think B           │
│ ┌──────────────────────┐ │  CONFIRM CARD — every spoken answer, before submit
│ │ You chose B. Submit? │ │  [Change] [Submit ✓] · "or say yes, submit"
│ └──────────────────────┘ │
│         ( ◉ )            │  orb = state: listening / thinking / speaking (reduced-motion aware)
│ [⏸ Pause] [⌨ Type] [✕ End]│
│ 16 min of voice left     │  budget, never hidden
└──────────────────────────┘
```

- **Modes**: Read-aloud · Push-to-talk · Hands-free; automatic fallback to turn-based or text.
- **Policies per context** (tutor, course step, practice, exam, live) decide the tools; the exam
  policy only reads aloud and records answers — no hints or tutoring.
- **Never grade by voice**: answers go through the confirm card to the REST scorer.
- Captions on, barge-in allowed, haptic + audio cues for listening/speaking, idle auto-pause.
- Same component in all student apps: `<VoiceSession context audience policy onConfirm onEnd />`.

## 9. Do / don't

| Do | Don't |
|---|---|
| Put editing in a drawer and keep the canvas for reading | Inline-edit everything on the canvas |
| Use a focus view for search/select with a sticky tray | Show a cramped search list inside a 420px drawer |
| Give phones and tablets their own layout (tabs, sheets, split view) | Shrink the desktop sidebar layout onto a phone |
| Confirm every spoken answer on screen before submitting | Let the voice model grade or submit silently |
| Offer *find similar* / reuse before *Create new* | Let staff create a near-duplicate without seeing existing matches |
| Use one segmented control for alternative representations | Add tabs + toggles + dropdowns for the same switch |
| Show status as pills from server truth | Write "This draft has been saved successfully on the server." |
| Collapse staff tools (`<details>`) | Show debug traces, ids and API names to students |
| Restore focus after closing a layer | Reset scroll/focus to the top of the page |
| Use tokens (`var(--mb-*)`) | Hard-code colours or font sizes in components |
| Keep one primary per region | Put two filled buttons side by side |

## 10. Code templates

**Shell (React)**

```tsx
<div className={`sc-app${focus ? " focus" : ""}${sidebarOpen ? " sc-sidebar-open" : ""}`}>
  <nav className="sc-rail" aria-label="Module navigation">{/* view links, avatar, sign out */}</nav>
  <Sidebar query={query} setQuery={setQuery} results={search(query, data)} />
  <div className="sc-main">
    <header className="sc-top">{/* breadcrumb · spacer · status pills · settings · light · primary */}</header>
    <section className="sc-workspace">
      <main id="main-content" className="sc-canvas">{focus ? <FocusView … /> : canvas}</main>
      {drawer}{sidecar}
    </section>
  </div>
</div>
```

**Drawer**

```tsx
<Drawer title="Edit step" onClose={close}
  footer={<><button className="sc-light">Preview as student</button><button className="sc-primary">Save changes</button></>}>
  <div className="sc-kicker">Quiz · quiz</div>
  <label>Step title<input … /></label>
  <h3 className="sc-section-title" id="step-content" tabIndex={-1}>Step content</h3>
  {/* chips + Search & attach · Add existing · Create from template */}
</Drawer>
```

**Focus view with tray**

```tsx
<div className="focuswrap" aria-label="Search & attach">
  <div className="focusbar"><button onClick={back}>← Back</button><Kicker/>…<span>Esc returns without changes</span></div>
  <div className="focusbody"><aside className="facets" aria-label="Filters">…</aside><section className="results" aria-label="Results">…</section></div>
  <div className="tray" role="region" aria-label="Selection">
    <span><b>{n}</b> selected</span>{roleOrTarget}<span className="sp"/>
    <button className="sc-light" onClick={back}>Cancel</button>
    <button className="sc-primary" disabled={!n} onClick={attachAndReturn}>Attach to step &amp; return</button>
  </div>
</div>
```

**Micro chat**

```tsx
<MicroChat context={{ kind: "activity", id, revision, title }} audience="staff"
  quickPrompts={["Explain the distractors", "Make it harder", "Add a hint", "Check the math"]}
  onApply={proposal => applyWithBaseHash(proposal)} onClose={restoreFocus} />
```

**Layout CSS (tokens only)**

```css
.sc-app{display:grid;grid-template-columns:60px 260px minmax(0,1fr);height:100dvh;overflow:hidden}
.sc-app.focus{grid-template-columns:60px minmax(0,1fr)} .sc-app.focus .sc-sidebar{display:none}
.sc-drawer{width:min(420px,42vw);border-left:1px solid var(--mb-border);display:flex;flex-direction:column}
.sc-canvas-inner{max-width:860px;margin:0 auto;display:grid;gap:14px}
[hidden]{display:none!important}
@media (max-width:760px){/* sidebar off-canvas + scrim; drawer/sidecar/micro chat full-height overlays */}
```

## 11. Adoption checklist per module

- [ ] Rail + searchable sidebar + top bar with breadcrumb and status pills.
- [ ] One hero (`h1`) per view; segmented control for representations.
- [ ] Editing in a drawer; search/select in a focus view with a tray; previews in a sidecar.
- [ ] Esc closes the top-most layer and focus returns to the opener.
- [ ] Student screens: phone / tablet-portrait / tablet-landscape layouts per §2b; 44 px targets; safe areas; unavailable features show the larger-screen card.
- [ ] Voice: session per §8a with captions, confirm card and budget; exam policy has no tutoring tools.
- [ ] Large libraries use the Finder (§7a): full width, inspector or target mini-map, link vs fork shown, *find similar* before *Create new*.
- [ ] Pills follow §6 tones; ≤ 3 per row; no prose status.
- [ ] Micro chat available on item drawers where AI help is enabled (staff) or on the current
      step/question (students), scoped and proposal-only.
- [ ] 1440 / 390 px: one `h1`, no horizontal overflow, no console errors, focus visible.
