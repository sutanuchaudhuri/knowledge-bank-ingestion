// Tutor interaction flow — step-synced chat mock + "behind the scenes" panel.
// Page-specific state machine (not shared via app.js since no other page needs it).
(function () {
  "use strict";

  var TURNS = {
    search: {
      steps: [
        {
          layer: "web",
          status: "live",
          chat: { type: "user", text: "Find me recent AIME problems about combinatorics" },
          title: "1 \u00b7 Student sends a message",
          body: "<p>The chat UI POSTs the raw message to mathbank-web's own <code>/api/agent/*</code> route, which proxies server-side to mathbank-agent \u2014 the browser never talks to the agent directly.</p>",
          code: "POST /api/agent/chat\n{ \"message\": \"Find me recent AIME problems about combinatorics\" }"
        },
        {
          layer: "agent",
          status: "live",
          chat: { type: "system", text: "Agent received the message, starting a tool-calling turn\u2026" },
          title: "2 \u00b7 ADK agent opens a tool-calling turn",
          body: "<p>mathbank-agent (Google ADK <code>LlmAgent</code> + <code>LiteLlm</code> connector) forwards the conversation to OpenAI along with its registered tool schema. The agent itself holds no business logic \u2014 it only decides <em>whether</em> and <em>which</em> tool to call.</p>",
          code: null
        },
        {
          layer: "openai",
          status: "live",
          chat: { type: "tool", text: "\ud83d\udd27 search_problems(query=\"combinatorics\", filters={competition:\"AIME\"}, order_by=\"year_desc\")" },
          title: "3 \u00b7 OpenAI picks a tool + arguments",
          body: "<p><code>gpt-4o-mini</code> returns a structured tool call, not free text \u2014 the model decided this needs the search tool, a competition filter, and \"most recent first\" ordering, purely from the natural-language request.</p>",
          code: null
        },
        {
          layer: "rest",
          status: "live",
          chat: null,
          title: "4 \u00b7 mathbank-rest receives the call",
          body: "<p>The agent's tool call becomes one REST request \u2014 the <strong>only</strong> door onto Postgres/Neo4j. This is the full request body, matching <code>ProblemSearchRequest</code> in <code>routers/v1.py</code>.</p>",
          code: "POST /v1/search/problems\n{\n  \"query\": \"combinatorics\",\n  \"filters\": {\"competition\": \"AIME\"},\n  \"retrieval\": {\"semantic\": true, \"lexical\": true},\n  \"order_by\": \"year_desc\",\n  \"limit\": 10\n}"
        },
        {
          layer: "vector",
          status: "live",
          chat: { type: "system", text: "Embedding the query text\u2026" },
          title: "5 \u00b7 The query itself gets embedded",
          body: "<p>Before any SQL runs, <code>vector_search.embed_query()</code> calls OpenAI's <code>text-embedding-3-small</code> to turn the query string into a 1536-dimension vector \u2014 the same embedding space every problem statement was chunked and embedded into ahead of time.</p>",
          code: "embed_query(\"combinatorics\")\n\u2192 \"[0.0123, -0.0041, 0.0187, ...]\"   # 1536 floats, pgvector literal"
        },
        {
          layer: "sql",
          status: "live",
          chat: null,
          title: "6 \u00b7 Pre-filter, then hybrid-rank in Postgres",
          body: "<p>The competition filter narrows the candidate pool <strong>before</strong> ranking (the fix for a real empty-results bug \u2014 see <a href='architecture.html#inference'>Ingestion &amp; Inference</a>). Semantic (pgvector ANN) and lexical (Postgres FTS) candidate lists are then combined with Reciprocal Rank Fusion.</p>",
          code: "WITH eligible_problem AS (\n  SELECT p.problem_id FROM core.problem p\n  JOIN core.paper pa ON pa.paper_id = p.paper_id\n  JOIN core.competition_edition ed ON ed.edition_id = pa.edition_id\n  JOIN core.competition comp ON comp.competition_id = ed.competition_id\n  WHERE comp.external_code = 'AIME'\n),\nsemantic AS (\n  SELECT e.chunk_id,\n         row_number() OVER (ORDER BY e.embedding <=> :query_vector) AS rnk\n  FROM search.embedding e\n  JOIN search.chunk c ON c.chunk_id = e.chunk_id\n  JOIN eligible_problem ep ON ep.problem_id = c.problem_id\n  ORDER BY e.embedding <=> :query_vector LIMIT 100\n),\nlexical AS ( /* same pattern, websearch_to_tsquery + ts_rank_cd */ )\nSELECT ..., 1.0/(60+s.rnk) + 1.0/(60+l.rnk) AS rrf_score\nFROM semantic s FULL OUTER JOIN lexical l USING (chunk_id)\nORDER BY ed.year DESC, rrf_score DESC LIMIT 10"
        },
        {
          layer: "rest",
          status: "live",
          chat: null,
          title: "7 \u00b7 Ranked rows return to the agent",
          body: "<p>mathbank-rest joins the winning chunk_ids back to <code>core.problem</code>/<code>core.competition</code> and returns plain JSON \u2014 no SQL, no internal IDs leak past this boundary.</p>",
          code: "{\n  \"query\": \"combinatorics\",\n  \"results\": [\n    {\"canonical_code\": \"AIME_2023_I_Q11\", \"year\": 2023,\n     \"statement_text\": \"Find the number of subsets of {1,2,...,10}...\",\n     \"rrf_score\": 0.0161},\n    { \"...\": \"2 more results\" }\n  ]\n}"
        },
        {
          layer: "openai",
          status: "live",
          chat: { type: "system", text: "Synthesizing an answer from the tool results\u2026" },
          title: "8 \u00b7 Model synthesizes a grounded answer",
          body: "<p>Turn 2 of the OpenAI call includes the JSON above as tool-result context. The grounding rule: the model may only cite a <code>canonical_code</code> that actually appeared in a tool response this turn \u2014 it cannot invent a problem.</p>",
          code: null
        },
        {
          layer: "web",
          status: "live",
          chat: {
            type: "agent",
            text: "Here are 3 recent AIME combinatorics problems:",
            cites: ["AIME_2023_I_Q11", "AIME_2016_II_Q08", "AIME_2010_II_Q08"]
          },
          title: "9 \u00b7 Answer rendered in the chat UI",
          body: "<p>The reply streams back through mathbank-agent \u2192 mathbank-web's proxy \u2192 the browser. Every cited code is a real, clickable problem in the corpus (see <a href='graph.html'>Knowledge Graph</a> for the same problems' concept tags).</p>",
          code: null
        }
      ]
    },

    mastery: {
      steps: [
        {
          layer: "web",
          status: "live",
          chat: { type: "system", text: "Student marks AIME_1983_Q01 as incorrect in the practice view" },
          title: "1 \u00b7 Student answers a problem",
          body: "<p>This happens outside the chat panel \u2014 a practice/problem view with a submit button. It's the same JWT-authenticated student session either way.</p>",
          code: null
        },
        {
          layer: "rest",
          status: "live",
          chat: null,
          title: "2 \u00b7 POST /v1/learner/attempts",
          body: "<p>Authenticated via <code>Authorization: Bearer &lt;jwt&gt;</code>. <code>get_current_student_id()</code> resolves the token to a <code>student_id</code> before anything touches the database.</p>",
          code: "POST /v1/learner/attempts\nAuthorization: Bearer eyJhbGciOi...\n{\n  \"problem_code\": \"AIME_1983_Q01\",\n  \"is_correct\": false,\n  \"time_spent_seconds\": 240\n}"
        },
        {
          layer: "sql",
          status: "live",
          chat: null,
          title: "3 \u00b7 Attempt logged \u2014 append-only",
          body: "<p><code>learner.attempt</code> is never updated or deleted, only inserted \u2014 it's the event log every mastery score is later recomputed from, so the history is always reconstructable.</p>",
          code: "INSERT INTO learner.attempt\n  (student_id, problem_id, is_correct, time_spent_seconds)\nVALUES ($1, $2, false, 240)"
        },
        {
          layer: "sql",
          status: "live",
          chat: null,
          title: "4 \u00b7 Mastery recomputed inline, same request",
          body: "<p><code>recompute_mastery_for_problem()</code> looks up every concept/technique this problem is tagged with, then recomputes a time-decayed, difficulty-weighted score per concept \u2014 not a running average, a fresh calculation over the full attempt history every time.</p>",
          code: "mastery(s,c) = \u03a3 correct(a)\u00b7e^(-days(a)/45)\u00b7(1+0.5\u00b7difficulty(a))\n               \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n               \u03a3            e^(-days(a)/45)\u00b7(1+0.5\u00b7difficulty(a))\n\nUPSERT INTO learner.concept_mastery (student_id, concept_id, mastery_score, ...)"
        },
        {
          layer: "web",
          status: "live",
          chat: { type: "system", text: "mastery updated: count-subset  0.63 \u2192 0.54" },
          title: "5 \u00b7 Updated score comes back in the same response",
          body: "<p><code>POST /v1/learner/attempts</code> returns <code>{attempt, updated_mastery}</code> in one round trip \u2014 no separate poll needed for the UI to reflect the new score.</p>",
          code: null
        },
        {
          layer: "web",
          status: "live",
          chat: { type: "user", text: "I got that one wrong \u2014 what should I work on next?" },
          title: "6 \u00b7 Student asks for guidance in chat",
          body: "<p>Same chat entry point as Turn 1 \u2014 this message goes through the identical agent \u2192 OpenAI tool-calling path.</p>",
          code: null
        },
        {
          layer: "rest",
          status: "live",
          chat: { type: "tool", text: "\ud83d\udd27 get_student_mastery_summary(student_id)" },
          title: "7 \u00b7 Agent calls the mastery tool \u2014 this part is live",
          body: "<p><code>GET /v1/learner/mastery</code> exists and works today, returning every concept/technique the student has attempted, sorted weakest-first.</p>",
          code: "GET /v1/learner/mastery\nAuthorization: Bearer eyJhbGciOi...\n\u2192 {\n  \"concepts\": [\n    {\"slug\": \"count-subset\", \"mastery_score\": 0.54, \"attempts_count\": 4},\n    {\"slug\": \"count-pie\",    \"mastery_score\": 0.71, \"attempts_count\": 2}\n  ],\n  \"techniques\": [ ... ]\n}"
        },
        {
          layer: "neo4j",
          status: "planned",
          chat: null,
          title: "8 \u00b7 Prerequisite-gap traversal \u2014 PLANNED, not wired yet",
          body: "<p>This is the <strong>designed</strong> next step, not a live call: once <code>Student</code>/<code>MASTERED</code>/<code>STRUGGLES_WITH</code> edges are projected into Neo4j (MST-05/06), a graph traversal could find the <em>prerequisite</em> concept behind a weak spot \u2014 not just \"more of the same topic\". The Cypher for this is already written; the projection step that would make it runnable isn't.</p>",
          code: "// Designed, not yet executable \u2014 MASTERED/STRUGGLES_WITH don't exist in the graph yet\nMATCH (s:Student {canonical_id: $studentId})-[:STRUGGLES_WITH]->(weak:Concept)\nMATCH (weak)<-[:HAS_SUBCONCEPT]-(parent:Concept)\nWHERE NOT (s)-[:MASTERED]->(parent)\nRETURN parent.name AS prerequisite_gap, weak.name AS specific_weak_spot"
        },
        {
          layer: "web",
          status: "mixed",
          chat: {
            type: "agent",
            text: "You've recently struggled with subset-counting (count-subset, score 0.54). Here are two problems to practice:",
            cites: ["AIME_1988_Q01", "AIME_1986_Q12"],
            note: "The topic pick is from live mastery data; the \"prerequisite, not just more of the same\" framing shown here is the planned behavior above \u2014 today the agent just sorts by lowest mastery score."
          },
          title: "9 \u00b7 Grounded answer \u2014 partly live, partly the target behavior",
          body: "<p>This is the honest state of the system today: the recommendation is real and driven by real mastery scores, but it isn't yet prerequisite-aware the way the graph traversal above would make it.</p>",
          code: null
        }
      ]
    },

    scaffold: {
      steps: [
        {
          layer: "web",
          status: "live",
          chat: { type: "user", text: "I'm stuck on AIME_1992_Q06 \u2014 can you break it into smaller steps instead of just telling me the answer?" },
          title: "1 \u00b7 Student asks for scaffolding, not an answer",
          body: "<p>Same entry point as Turns 1-2 (<code>POST /api/agent/chat</code>) \u2014 what's different here is the <em>intent</em>: the student wants to be walked through it, not handed a result.</p>",
          code: null
        },
        {
          layer: "agent",
          status: "live",
          chat: { type: "system", text: "Agent recognizes this needs decomposition, not retrieval\u2026" },
          title: "2 \u00b7 The agent reaches for the decompose_problem tool",
          body: "<p>As of Round 11 the agent has two more tools alongside the original six: <code>decompose_problem(problem_code, max_steps)</code> and <code>check_subproblem_answer(subproblem_prompt, student_answer)</code>, both registered in <code>mathbank-agent/agents/mathbank_tutor/agent.py</code> and backed by real REST endpoints.</p>",
          code: null
        },
        {
          layer: "openai",
          status: "live",
          chat: { type: "tool", text: "\ud83d\udd27 decompose_problem(problem_code=\"AIME_1992_Q06\", max_steps=3)" },
          title: "3 \u00b7 A real decomposition response",
          body: "<p><code>POST /v1/tutor/decompose</code> fetches the real problem statement via <code>db/queries.get_problem_by_code</code>, then calls <code>gpt-4o-mini</code> in JSON mode with a prompt that explicitly forbids revealing the final answer. The example below is an actual response captured against the live corpus, not a hypothetical.</p>",
          code: "// Real response \u2014 captured via curl against localhost:8000\n{\n  \"problem_code\": \"AIME_1992_Q06\",\n  \"subproblems\": [\n    {\"step\": 1, \"prompt\": \"Determine the range of integers\u2026 no carrying in the units place\u2026\", \"targets_skill\": \"addition properties\"},\n    {\"step\": 2, \"prompt\": \"Analyze the conditions\u2026 no carrying in the tens place\u2026\", \"targets_skill\": \"digit analysis\"},\n    {\"step\": 3, \"prompt\": \"Combine the findings\u2026 total number of pairs\u2026\", \"targets_skill\": \"counting\"}\n  ]\n}"
        },
        {
          layer: "web",
          status: "live",
          chat: { type: "agent", text: "Let's start smaller. Subproblem 1: how many ways can you pick 2 non-consecutive integers from {1, ..., 8}?" },
          title: "4 \u00b7 First subproblem presented",
          body: "<p>The agent's instructions tell it to present exactly one subproblem at a time, never dumping the full list \u2014 a bite-sized version of the real sub-skill, not a restatement of the whole problem.</p>",
          code: null
        },
        {
          layer: "openai",
          status: "live",
          chat: { type: "user", text: "9? I think I just subtracted the consecutive pairs from all pairs." },
          title: "5 \u00b7 check_subproblem_answer grades the free-form answer",
          body: "<p><code>POST /v1/tutor/check-subproblem</code> calls <code>gpt-4o-mini</code> to judge the reasoning, not just match a number. Verified live: for this exact answer (9) the real correct count is 28\u22127=21, so the grader correctly returned <code>correct: false</code> with substantive feedback \u2014 it isn't rubber-stamping.</p>",
          code: "// Real response \u2014 captured via curl\n{\"correct\": false, \"feedback\": \"You're on the right track thinking about pairs, but let's refine your approach to find the correct count!\"}"
        },
        {
          layer: "web",
          status: "live",
          chat: { type: "agent", text: "Subproblem 2: now extend that pattern to 10 integers, avoiding any 3 picked consecutively. What changes?" },
          title: "6 \u00b7 Subproblem 2 \u2014 student starts to struggle",
          body: "<p>The agent only advances to the next subproblem once <code>check_subproblem_answer</code> reports <code>correct: true</code> (or the student asks to move on) \u2014 this is the moment a real weakness surfaces, specifically around casework technique, not the topic overall.</p>",
          code: null
        },
        {
          layer: "sql",
          status: "mixed",
          chat: { type: "system", text: "hint given \u2014 logging the attempt with hint_count incremented" },
          title: "7 \u00b7 A hint gets logged \u2014 and now actually discounts mastery",
          body: "<p><code>learner.attempt.hint_count</code> is real, and as of Round 11 it's finally consumed by scoring (MST-09). <strong>Still not built:</strong> logging a hint against a specific <em>subproblem</em> \u2014 subproblems aren't persisted anywhere (no <code>core.subproblem</code> table), so today this would only conservatively log against the parent problem via the existing <code>POST /v1/learner/attempts</code>.</p>",
          code: "INSERT INTO learner.attempt\n  (student_id, problem_id, is_correct, hint_count, source)\nVALUES ($1, $2, false, 1, 'agent_chat')\n-- hint_count now feeds mastery.hint_penalty() \u2014 see step 8"
        },
        {
          layer: "sql",
          status: "live",
          chat: null,
          title: "8 \u00b7 Mastery recompute now discounts for hints (gap closed)",
          body: "<p>This reuses the live machinery from Turn 2 \u2014 <code>recompute_mastery_for_problem()</code> runs on every attempt. <strong>Round 11 closed the honest gap this scenario used to expose:</strong> <code>mastery.py</code>'s <code>hint_penalty(hint_count) = max(0.4, 1/(1+0.25*hint_count))</code> now multiplies into <code>correctness_weight</code>, so an answer reached only after repeated hints scores lower than one solved cold \u2014 floored at 0.4 so it never drops to zero.</p>",
          code: "mastery(count-case) = 0.33   # now actually discounted by hint_penalty(hint_count=3) \u2248 0.57x\n-- formula: time-decayed * difficulty-weighted * hint_penalty(hint_count)\n-- hint_penalty(0)=1.0, hint_penalty(3)\u22480.57, floored at 0.4"
        },
        {
          layer: "rest",
          status: "live",
          chat: { type: "tool", text: "\ud83d\udd27 get_concept_problems(slug=\"count-case\", limit=3)" },
          title: "9 \u00b7 Agent finds a smaller practice problem \u2014 this endpoint is real",
          body: "<p><code>GET /v1/concepts/count-case/problems</code> exists and works today (it's the same hierarchy-aware endpoint fixed in GOTCHAS.md #16). All three tools in this turn — <code>decompose_problem</code>, <code>check_subproblem_answer</code>, <code>get_problems_for_concept</code> — are now real; it's up to the agent's own reasoning to chain them together after a subproblem failure.</p>",
          code: "GET /v1/concepts/count-case/problems?limit=3\n\u2192 [{\"canonical_code\": \"AIME_1986_Q12\", ...}, {\"canonical_code\": \"AIME_1988_Q01\", ...}]"
        },
        {
          layer: "web",
          status: "mixed",
          chat: {
            type: "agent",
            text: "Let's practice casework on something smaller first \u2014 try this, then we'll go back and finish AIME_1992_Q06 together:",
            cites: ["AIME_1986_Q12"],
            note: "Every tool call in this hand-off is real (decompose, check-subproblem, concept-problems). What's still agent-reasoning-dependent, not a guaranteed scripted pipeline: deciding to route here specifically because a subproblem-level weakness was detected — the agent's instructions encourage this but don't force it step-by-step."
          },
          title: "10 · Scaffolded hand-off — all tools real, orchestration is agent-reasoning",
          body: "<p>The full loop — decompose, grade reasoning, detect a specific weak sub-skill, remediate, then return to the original problem — now runs on entirely real endpoints (AGT-11, MST-09). What remains a design choice rather than a hard guarantee: whether the LLM reliably chains all of them together unprompted versus needing more explicit multi-step instructions — a natural next refinement, not a missing capability.</p>",
          code: null
        }
      ]
    }
  };

  var currentTurnKey = "search";
  var currentStepIndex = 0;
  var playTimer = null;
  var playProgressTimer = null;

  var $transcript, $badge, $title, $body, $dots, $counter, $bar, $playBtn;

  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function renderChatBubble(msg) {
    var el = document.createElement("div");
    el.className = "chat-msg " + msg.type;
    if (msg.type === "system") {
      el.textContent = msg.text;
      return el;
    }
    var html = escapeHtml(msg.text);
    if (msg.cites) {
      html += "<br/>" + msg.cites.map(function (c) { return '<span class="cite">' + c + "</span>"; }).join(" ");
    }
    if (msg.note) {
      html += '<div style="margin-top:8px;font-size:11.5px;color:var(--text-dim);font-style:italic">' + escapeHtml(msg.note) + "</div>";
    }
    el.innerHTML = html;
    return el;
  }

  function renderDots(steps) {
    $dots.innerHTML = "";
    steps.forEach(function (_, i) {
      var d = document.createElement("div");
      d.className = "dot";
      d.addEventListener("click", function () { stopPlay(); goToStep(i); });
      $dots.appendChild(d);
    });
  }

  function updateDots(steps) {
    Array.from($dots.children).forEach(function (d, i) {
      d.classList.toggle("done", i < currentStepIndex);
      d.classList.toggle("current", i === currentStepIndex);
    });
  }

  function renderStep() {
    var turn = TURNS[currentTurnKey];
    var steps = turn.steps;
    var step = steps[currentStepIndex];

    document.querySelectorAll("#pipeline-strip .layer").forEach(function (el) {
      el.classList.toggle("active", el.dataset.layer === step.layer);
    });

    $badge.textContent = step.status === "planned" ? "PLANNED" : step.status === "mixed" ? "LIVE + PLANNED" : "LIVE";
    $badge.className = "layer-badge " + (step.status === "planned" ? "planned" : "live");
    $title.textContent = step.title;
    $body.innerHTML = step.body + (step.code ? "<pre>" + escapeHtml(step.code) + "</pre>" : "");

    $transcript.innerHTML = "";
    for (var i = 0; i <= currentStepIndex; i++) {
      if (steps[i].chat) $transcript.appendChild(renderChatBubble(steps[i].chat));
    }
    $transcript.scrollTop = $transcript.scrollHeight;

    document.getElementById("btn-prev").disabled = currentStepIndex === 0;
    document.getElementById("btn-next").disabled = currentStepIndex === steps.length - 1;
    $counter.textContent = (currentStepIndex + 1) + " / " + steps.length;
    updateDots(steps);
  }

  function goToStep(i) {
    var steps = TURNS[currentTurnKey].steps;
    currentStepIndex = Math.max(0, Math.min(steps.length - 1, i));
    renderStep();
  }

  function setTurn(key) {
    stopPlay();
    currentTurnKey = key;
    currentStepIndex = 0;
    document.querySelectorAll(".turn-tabs button").forEach(function (b) {
      b.classList.toggle("active", b.dataset.turn === key);
    });
    renderDots(TURNS[key].steps);
    renderStep();
  }

  function stepForward() {
    var steps = TURNS[currentTurnKey].steps;
    if (currentStepIndex >= steps.length - 1) { stopPlay(); return; }
    goToStep(currentStepIndex + 1);
  }

  function startPlay() {
    $playBtn.textContent = "\u23f8 Pause";
    var stepMs = 2600;
    function tick() {
      $bar.style.transition = "none"; $bar.style.width = "0%";
      requestAnimationFrame(function () {
        $bar.style.transition = "width " + stepMs + "ms linear";
        $bar.style.width = "100%";
      });
    }
    tick();
    playProgressTimer = setInterval(tick, stepMs);
    playTimer = setInterval(function () {
      var steps = TURNS[currentTurnKey].steps;
      if (currentStepIndex >= steps.length - 1) { stopPlay(); return; }
      stepForward();
    }, stepMs);
  }

  function stopPlay() {
    if ($playBtn) $playBtn.textContent = "\u25b6 Play";
    clearInterval(playTimer); clearInterval(playProgressTimer);
    playTimer = null; playProgressTimer = null;
    if ($bar) { $bar.style.transition = "none"; $bar.style.width = "0%"; }
  }

  document.addEventListener("DOMContentLoaded", function () {
    $transcript = document.getElementById("chat-transcript");
    $badge = document.getElementById("behind-badge");
    $title = document.getElementById("behind-title");
    $body = document.getElementById("behind-body");
    $dots = document.getElementById("step-dots");
    $counter = document.getElementById("step-counter");
    $bar = document.getElementById("step-bar");
    $playBtn = document.getElementById("btn-play");

    document.getElementById("btn-prev").addEventListener("click", function () { stopPlay(); goToStep(currentStepIndex - 1); });
    document.getElementById("btn-next").addEventListener("click", function () { stopPlay(); goToStep(currentStepIndex + 1); });
    document.getElementById("btn-play").addEventListener("click", function () {
      if (playTimer) stopPlay(); else startPlay();
    });
    document.querySelectorAll(".turn-tabs button").forEach(function (btn) {
      btn.addEventListener("click", function () { setTurn(btn.dataset.turn); });
    });

    setTurn("search");
  });
})();
