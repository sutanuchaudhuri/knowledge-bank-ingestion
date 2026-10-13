# 29 — Student Input Add-ons: LaTeX Composer, ElevenLabs Voice, Agentic Formatting (`UXA`)

Requirement IDs: `UXA-*`. Requested 2026-10-06 together with the fluid-widget ([27](27_FLUID_WIDGET_LAYER.md)) and
distributed live ([28](28_DISTRIBUTED_LIVE_PLATFORM.md)) packs. Goal: students post and format math faster with a
**slim** UI. Every add-on is an opt-in user control, delegated through same-origin Next.js server routes, so keys
stay on the server.

## 1. Components (shared package `mathbank-widgets/`)

The add-ons live in one local package, which both deployables consume. `make -C mathbank-web sync-widgets` and
`make -C mathbank-live sync-widgets` copy it into `node_modules/mathbank-widgets`; re-run after editing the package
(GOT-FW-3).

| Export | File | Behaviour |
|---|---|---|
| `MathComposer` | `src/MathComposer.jsx` | A textarea with a slim action row. **Σ** toggles a symbol palette with four groups (Geometry, Algebra, Greek, Logic). Each symbol inserts a snippet at the caret; `|` in a snippet marks where the caret lands. **Format** runs the deterministic formatter in the browser. **✨** sends `mode: "agentic"` to the host's `/api/format-math`. A live KaTeX preview appears only when the text contains math. 🎤 dictation can be added as a child. Keys: Enter sends a single-line box; Ctrl/⌘+Enter sends a multi-line box. |
| `SpeakButton` | `src/VoiceControls.jsx` | 🔊 reads text aloud through `POST /api/voice/tts`. `speakableText` turns LaTeX into words first (for example `$PA \cdot PB = PT^2$` → "P A times P B equals P T squared"). Only one clip plays at a time; a second click stops it. If the call fails, the button shows "!" for 2.5 s. |
| `MicButton` | `src/VoiceControls.jsx` | 🎤 records with `MediaRecorder` for at most 60 s, then sends `POST /api/voice/stt` as multipart with the field `file`. The transcript is appended to the composer. Browser support is checked **after mount** so the server and client render the same markup (no hydration mismatch, GOT-FW-4). |
| `deterministicFormat`, `checkLatex`, `insertSnippet`, `SYMBOL_GROUPS` | `src/format.mjs` | A JS mirror of the REST formatter: `sqrt(x)`, `^`, `*`, `<=`, `!=`, `angle ABC`, `pi`, `theta`, … become `$…$` LaTeX. It works offline. |
| `speakableText`, `mathToSpeech` | `src/speech.mjs` | Converts LaTeX into spoken text. |
| `createVoiceHandlers`, `createFormatHandler` | `src/server.mjs` | Server-side route factories that both apps reuse (§2). |
| `WidgetHost` | `src/WidgetHost.jsx` | Renders validated WidgetSpecs (all 13 registry types). |

### Where the add-ons are used

| Surface | Add-ons |
|---|---|
| `mathbank-web` home chat (`app/Chat.jsx`) | MathComposer with 🎤; 🔊 on each tutor answer. |
| `mathbank-web` solve workspace (`app/learn/solve/[code]/SolveWorkspace.jsx`) | MathComposer for step answers and recovery answers; 🔊 on hints. |
| `mathbank-web` admin widget gallery (`/admin/widgets`) | WidgetHost previews; 🔊 to check what the speakable text sounds like. |
| `mathbank-live` classroom (`/s/[sid]`) | MathComposer with 🎤 to ask the tutor or instructor; 🔊 on tutor and instructor messages; WidgetHost for widgets on stage and in messages. |

## 2. Server routes (Next.js, same-origin only)

These routes exist in both `mathbank-web` (:5173) and `mathbank-live` (:5174). A cross-origin `Origin` header gets **403**.

| Route | Behaviour | Cost |
|---|---|---|
| `GET /api/voice/health` | Calls ElevenLabs `/v1/models` to check that the key works. | Free |
| `POST /api/voice/tts` `{text}` | 400 if the text is empty; 413 if it is over **1,200 chars**. Calls ElevenLabs TTS (`eleven_flash_v2_5`, voice `ELEVEN_VOICE_ID`, default `JBFqnCBsd6RMkjVDRZzb`) and returns `audio/mpeg`. | Paid per character |
| `POST /api/voice/stt` multipart `file` | 413 if the file is over **10 MB**. Calls ElevenLabs Speech-to-Text (`scribe_v1`) and returns `{text}`. | Paid per second |
| `POST /api/format-math` `{text, mode}` | Proxies to REST `POST /v1/tutor/format-math`. With no student/live token it is answered deterministically, with the warning "not logged in; used quick format". | Agentic mode is paid (small model) |

`ELEVEN_TTS_MODEL`, `ELEVEN_STT_MODEL` and `ELEVEN_VOICE_ID` can override the defaults. Students never see the key.
If the key is missing, the voice routes return 503 `Voice is not configured` and the buttons degrade; there is **no browser
speech-synthesis fallback**.

## 3. Agentic vs deterministic formatting (`mathbank-rest/src/mathbank_rest/math_format.py`)

- `deterministic` is the default. It is rule-based, with no model call; input is truncated at 4,000 chars. The result is checked by `check_latex`, which looks for unbalanced `$` delimiters, unbalanced braces and disallowed commands.
- `agentic` calls `MATH_FORMAT_MODEL` (default `gpt-4.1-mini`, temperature 0), told to keep the student's words and only add LaTeX. The output is **rejected** and replaced by the deterministic result in any of these cases:
  - the model call fails;
  - `check_latex` finds problems;
  - more than about 25% of the student's words of four or more letters disappear (a sign the model *answered* instead of formatting);
  - the output is more than 3× the input length + 200 chars.

  The response always says which engine was used (`engine`) and lists any `warnings`.
- Auth: `staff_or_student` (admin key or student JWT).
- The agent tool `format_math` (in `mathbank-agent/.../widget_tools.py`) is deterministic only. `propose_widget` calls `/v1/widgets/generate` and returns a validated spec, which chat renders inline.

## 4. Requirements

| ID | Requirement | Status |
|---|---|---|
| UXA-1 | Add-ons stay hidden until used: the palette opens on Σ, the preview appears only when the text has math, the voice buttons are small icons. | ✅ |
| UXA-2 | A student can insert common geometry/algebra symbols without typing LaTeX. | ✅ |
| UXA-3 | One-click formatting works without network access (deterministic, in the browser). | ✅ |
| UXA-4 | AI formatting never changes the student's meaning; invalid output falls back to deterministic and says so. | ✅ (validation + tests) |
| UXA-5 | `ELEVEN_API_KEY` is read only from the project `.env` (synced by make) and is used only server-side. | ✅ |
| UXA-6 | Voice is optional and bounded: 1,200-char TTS cap, 60 s / 10 MB STT cap, same-origin only, 30 voice requests per minute per caller (429). | ✅ |
| UXA-7 | Rendering uses KaTeX with `trust:false`; no raw HTML from students or models. | ✅ |
| UXA-8 | The add-ons also work in the separate live deployable. | ✅ |
| UXA-9 | Voice output reads math naturally rather than reading out LaTeX source. | ✅ (`speech.test.mjs`) |

## 5. Operations

```bash
make sync-eleven-key        # ELEVEN_API_KEY from root .env → mathbank-web/.env, mathbank-live/.env (never printed)
make check-eleven           # free auth check (models/voices)
make check-eleven TTS=1     # also synthesises one tiny phrase (paid, a few characters)
make sync-live-env          # mathbank-live/.env from root .env
make sync-keys              # OpenAI + Eleven + live env in one go
```

Restart web/live after a key changes (`make -C mathbank-web restart`, `make -C mathbank-live restart`).

## 6. Verification (2026-10-06)

| Check | Result |
|---|---|
| `node --test mathbank-widgets/tests/*.test.mjs` (format + speech) | 10 passed |
| `npx playwright test e2e/input-addons.spec.mjs` (5 tests: composer symbols/format/preview; format proxy same-origin + anonymous deterministic; voice health + validation without billing; mocked AI format keeps words; gallery + 🔊 with mocked TTS) | pass |
| REST `tests/test_fluid_widgets.py` (formatter, agentic rejection paths, auth) | 55 passed |
| **Live ElevenLabs calls (paid; disclosed)** | **Two tiny calls only.** TTS returned 200 with a 32 KB mp3. STT of that clip returned 200 with "Power of a point PA times PB equals PT squared". No other paid voice calls. The Playwright tests mock TTS/STT. |

## 7. Not yet implemented

The gaps are tracked as NYI-UXA rows in [20](20_NOT_YET_IMPLEMENTED.md):

- streaming TTS while the tutor is still writing;
- push-to-talk keyboard shortcut;
- per-student voice preference;
- handwriting/OCR input;
- a MathLive-style WYSIWYG editor (deliberately not added, to keep the UI slim).

## 8. Change log

- 2026-10-06: Created; `mathbank-widgets` package, web + live integration, Eleven make targets, REST `math_format.py`.
