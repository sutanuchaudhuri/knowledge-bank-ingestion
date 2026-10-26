# MathBank Studio platform — architecture, sequences and deployment (done vs pending)

**Evidence mode:** source-derived from Git `fbd44ed` **plus uncommitted worktree changes** (ledger 67
steps 01–03 and the UI rebuild), and one read-only AWS observation:
`cloudformation list-stacks` on **2026-10-26 00:29 UTC** (account 848941468793, `us-east-2`).
No live database schema was queried for this document. Planned items come from
[requirement 65](../requirements/65_ADAPTIVE_SOCRATIC_ADMIN_AND_AGENTCORE.md),
[ledger 67](../requirements/67_SOCRATIC_IMPLEMENTATION_HANDOFF.md) and the
[unified portal plan 68](../requirements/68_UNIFIED_STUDIO_PORTAL_PLAN.md) (still under review).
Platform-wide C1/C2 and the original six flows remain in the [root README](../../README.md#architecture).

## Status legend

| Mark | Meaning |
|---|---|
| 🟩 **Done** (solid green) | Implemented and tested; deployed where noted |
| 🟨 **Partial** (solid amber) | Implemented locally/offline, or works but not yet integrated, deployed or reviewed |
| ⬜ **Pending** (dashed grey) | Planned in requirement 65/67/68; not implemented |
| 🟥 **Retire** (dashed red) | Existing surface to be replaced by the Studio after parity (plan 68 P10) |

In sequence diagrams, **green bands are done**, **amber bands are partial** and **grey bands are
pending**.

Clickable navigation prototype (static, fake data, shows the API each action calls):
[prototype/studio-unified-navigation.html](prototype/studio-unified-navigation.html). The screen-by-screen
API contract and the iframe/sidecar preview design are in [plan 68 §7](../requirements/68_UNIFIED_STUDIO_PORTAL_PLAN.md).

## 1. Full architecture

```mermaid
flowchart TB
    subgraph People
        Staff([Staff author / reviewer / publisher])
        Student([Student])
    end

    subgraph StudioUI["Socratic Studio (mathbank-socratic-admin)"]
        Shell[Rail + searchable sidebar + canvas + drawer]
        Designer[Designer: flow / natural language / JSON]
        RulesV[Rules by topic]
        LibraryV[Library: strategies / sources / steps]
        Sim[Student simulator]
        AskAI[Ask AI drawer]
        QuizLib[Library: quizzes by topic]
        QBank[Step content: search and attach, add existing, create from template]
        VideoLib[Library: videos]
        ExamsV[Exams: templates / pool / assignments]
        AccessV[Students and groups: exclusions + features]
        SearchK[Finder: full-width vector search, inspector, wire link or fork]
        Assistant[AI assistant with tools]
        MicroChat[Micro chat scoped to a step or quiz item]
    end

    subgraph LegacyUI["Existing student and admin apps"]
        Web[mathbank-web student UI]
        WebAdmin[mathbank-web admin: courses, quizzes tab, media tab, manim review]
        ExamWeb[mathbank-exam-web]
        Live[mathbank-live]
    end

    subgraph REST["mathbank-rest (only database boundary)"]
        StaffAuth[Staff session: Cognito or local, CSRF, capabilities]
        Drafts[Socratic drafts + validation]
        Preview[Synthetic preview runtime]
        Scorer[Shared activity scorer]
        LegacyAdmin[Legacy admin routes: shared admin key]
        StudioAPI[Studio adapters /v1/admin/studio]
        Catalog[Artifact catalog + topic tags]
        QuizAuthor[Quiz authoring, review, revisions]
        VideoOrch[Video register + manim orchestration]
        ExamAuthor[Exam templates, pool review, assignments]
        Access[Audience and exclusion module: groups, EXCLUDE rules, feature policies]
        StaffSearch[Finder service: hybrid + graph fusion, families, find-similar, usage, lineage]
        Proposals[Proposal jobs + acceptance]
        MicroChatSvc[micro_chat threads + proposals]
        Hybrid[Problem/concept hybrid search]
        QuizRuntime[Quiz/exam runtime + grading]
    end

    subgraph Agents["Agent and job services"]
        Tutor[mathbank-agent tutor]
        ExamAgent[mathbank-exam-agent]
        Manim[mathbank-manim-studio]
        MCP[mathbank-mcp-competitions]
        AgentCore[Socratic AgentCore agent DeepSeek V3.2]
        SFN[Step Functions proposal workflow]
    end

    subgraph Data["Data"]
        PGd[(Postgres orchestration.socratic_* drafts 053)]
        PGp[(Postgres socratic_preview* 054)]
        PGc[(Postgres corpus, knowledge, pedagogy, activity, quiz, visual, learner)]
        PGn[(Postgres new: studio, exam templates, audience groups, exclusions, feature policy)]
        Vec[(pgvector search.* problems, solutions, steps, learning items)]
        VecN[(studio.unit_embedding HNSW: quiz items, quizzes, Socratic steps, step sequences, courses, video segments, exams)]
        Neo[(Neo4j AuraDB graph)]
        Obj[(Object storage videos)]
    end

    Cognito{{Amazon Cognito}}
    OpenAI{{OpenAI}}

    Staff --> Shell
    Shell --> Designer & RulesV & LibraryV & Sim & AskAI
    Designer -.-> QBank
    QBank -.-> StaffSearch
    Designer -.-> MicroChat
    MicroChat -.-> MicroChatSvc
    MicroChatSvc -.-> AgentCore
    Shell -.-> QuizLib & VideoLib & ExamsV & AccessV & SearchK & Assistant
    Designer --> Drafts
    RulesV --> Drafts
    LibraryV --> Drafts
    Sim --> Preview
    AskAI -.-> Proposals
    QuizLib & VideoLib & ExamsV & AccessV & SearchK & Assistant -.-> StudioAPI
    Shell --> StaffAuth
    StaffAuth --> Cognito
    Drafts --> PGd
    Preview --> Scorer
    Preview --> PGp
    Preview --> PGc
    StudioAPI -.-> Catalog & QuizAuthor & VideoOrch & ExamAuthor & Access & StaffSearch
    Catalog -.-> PGn
    QuizAuthor -.-> PGc
    ExamAuthor -.-> PGn
    Access -.-> PGn
    StaffSearch -.-> VecN
    StaffSearch -.-> Neo
    VideoOrch -.-> Manim
    ExamAuthor -.-> ExamAgent
    QuizAuthor -.-> ExamAgent
    Proposals -.-> SFN
    SFN -.-> AgentCore

    Student --> Web & ExamWeb & Live
    Web --> Tutor
    Web --> Hybrid
    Web -.->|"filtered content + feature checks"| Access
    ExamAuthor -.->|"apply exclusions"| Access
    Preview -.->|"preview as group"| Access
    ExamWeb --> ExamAgent
    ExamAgent --> QuizRuntime
    ExamAgent --> MCP
    ExamAgent --> OpenAI
    Tutor --> OpenAI
    Manim --> OpenAI
    Manim --> MCP
    Manim --> Obj
    Hybrid --> Vec
    Hybrid --> Neo
    QuizRuntime --> PGc
    WebAdmin --> LegacyAdmin
    LegacyAdmin --> PGc
    Live --> PGc

    classDef done fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef partial fill:#fef3c7,stroke:#d97706,color:#78350f
    classDef pending fill:#f8fafc,stroke:#94a3b8,color:#475569,stroke-dasharray:5 5
    classDef retire fill:#fff1f2,stroke:#e11d48,color:#881337,stroke-dasharray:5 5
    class Shell,Designer,RulesV,LibraryV,StaffAuth,Drafts,PGd,Web,ExamWeb,Live,Hybrid,QuizRuntime,Tutor,ExamAgent,Manim,MCP,PGc,Vec,Neo,Obj done
    class Sim,AskAI,Preview,Scorer,PGp,LegacyAdmin partial
    class MicroChat,MicroChatSvc,QBank,QuizLib,VideoLib,ExamsV,AccessV,SearchK,Assistant,StudioAPI,Catalog,QuizAuthor,VideoOrch,ExamAuthor,Access,StaffSearch,Proposals,AgentCore,SFN,PGn,VecN pending
    class WebAdmin retire
```

Why some items are **partial**: the simulator, preview runtime, shared scorer and migration 054 are
done locally and on Neon but **not deployed to the hosted Studio**; *Ask AI* has a finished UI with
no proposal backend; legacy admin routes work but use the shared admin key, so the Studio cannot
call them until adapters exist.

## 2. Studio internals (frontend → REST → tables)

```mermaid
flowchart LR
    subgraph SPA["mathbank-socratic-admin src/"]
        App[App.tsx shell, routing, drawer state]
        Side[Sidebar.tsx + search.ts]
        Des[Designer.tsx + narrative.ts]
        Pan[Panels.tsx step/rule/settings/new]
        RV[RulesView.tsx]
        Lib[Library.tsx]
        SimU[Simulator.tsx]
        Co[Coauthor.tsx Ask AI]
        ApiC[api.ts CSRF, idempotency, timeouts]
    end

    subgraph Router["routers/socratic.py /v1/admin/socratic"]
        Sess["POST/GET/DELETE /session"]
        Cat["GET /strategies, /resources"]
        Wf["GET/POST/PUT /workflows, /revisions, /validate"]
        Sm["POST /workflows/id/simulate"]
        Pv["GET /previews/id, POST respond, assist, reveal, transition"]
        Pr["POST /workflows/id/proposals, GET /jobs/id, POST accept"]
    end

    subgraph Svc["Services"]
        Auth[socratic_auth + socratic_local_auth]
        Dsvc[socratic_service]
        Psvc[socratic_preview]
        Sco[activity_scoring]
        Mc[micro_course_service]
    end

    subgraph Tables["Postgres"]
        T1[(orchestration.socratic_strategy, workflow, revision, command)]
        T2[(orchestration.socratic_preview, preview_event)]
        T3[(activity.definition read-only snapshot)]
        T4[(core.problem, core.solution, pedagogy.solution_route_release read-only)]
        T5[(audit.action_log, pipeline.outbox_event)]
    end

    App --> Side & Des & Pan & RV & Lib & SimU & Co
    App --> ApiC
    ApiC --> Sess & Cat & Wf & Sm & Pv
    ApiC -.-> Pr
    Sess --> Auth
    Cat --> Dsvc
    Wf --> Dsvc
    Sm --> Psvc
    Pv --> Psvc
    Psvc --> Sco
    Mc --> Sco
    Dsvc --> T1 & T4 & T5
    Psvc --> T2 & T3

    classDef done fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef partial fill:#fef3c7,stroke:#d97706,color:#78350f
    classDef pending fill:#f8fafc,stroke:#94a3b8,color:#475569,stroke-dasharray:5 5
    class App,Side,Des,Pan,RV,Lib,ApiC,Sess,Cat,Wf,Auth,Dsvc,Mc,T1,T3,T4,T5 done
    class SimU,Sm,Pv,Psvc,Sco,T2 partial
    class Co,Pr pending
```

## 3. Deployment

```mermaid
flowchart TB
    subgraph Local["Local development (operator workstation)"]
        L1["Studio UI Vite :5186 (make socratic-start)"]
        L2["Local staff API :8019 loopback, local login (DRAFTS=1 real Neon)"]
        L3["Full REST :8000 (Cognito mode)"]
        L4["web :5173 · live :5174 · agent :8001 · exam-web :5176 · exam-agent :8030 · manim :8020 · ml :8010/:5175"]
        L5["Colima Docker build runtime"]
    end

    subgraph AWS["AWS account 848941468793 · us-east-2 · CDK mathbank-infra-aws"]
        subgraph Iso["Isolated Studio app socratic_app.py"]
            A1["MathBankSocraticStack: Lambda Function URL, API + SPA same origin (step 02 build)"]
            A1b["Redeploy with step 03 + new UI"]
        end
        subgraph Shared["Shared app app.py"]
            A2[MathBankRestStack Lambda URL]
            A3[MathBankAgentStack Lambda URL]
            A4[MathBankExamAgentStack Lambda URL]
            A5[MathBankManimStudioStack Lambda URL]
            A6[MathBankMcpCompetitionsStack Lambda URL]
            A7[MathBankMlInferenceStack Lambda URL]
            A8[MathBankExamWebStack S3 + CloudFront]
            A9[MathBankFargateWebStack web, live, ml-frontend desired_count 0]
        end
        S1[(SSM SecureString parameters)]
        S2{{Cognito user pool}}
        S3[(ECR images via CDK bootstrap)]
        P1["Bedrock AgentCore runtime DeepSeek V3.2"]
        P2["Step Functions + proposal Lambda, budget and pause switch"]
        P3["Studio adapters, catalog, exams, access, search, assistant routes"]
    end

    subgraph Managed["Managed data services (public TLS, no NAT)"]
        D1[(Neon Postgres + pgvector: migrations through 054 applied)]
        D2[(Neo4j AuraDB)]
        D3[(Neon S3-compatible object storage)]
        D4{{OpenAI API}}
    end

    L1 --> L2
    L1 -.->|optional| L3
    L2 --> D1
    L3 --> D1 & D2
    L5 --> S3
    A1 --> S1 & S2 & D1
    A1b -.-> A1
    A2 --> D1 & D2
    A4 --> A2
    A5 --> D1 & D3
    A3 --> A2
    A2 --> D4
    P3 -.-> A1
    A1 -.-> P2
    P2 -.-> P1

    classDef done fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef partial fill:#fef3c7,stroke:#d97706,color:#78350f
    classDef pending fill:#f8fafc,stroke:#94a3b8,color:#475569,stroke-dasharray:5 5
    class L1,L2,L3,L4,L5,A2,A3,A4,A5,A6,A7,A8,A9,S1,S2,S3,D1,D2,D3,D4 done
    class A1 partial
    class A1b,P1,P2,P3 pending
```

Observed 2026-10-26 00:29 UTC: all nine `MathBank*` stacks are in `CREATE_COMPLETE`/`UPDATE_COMPLETE`.
`MathBankSocraticStack` was last updated 2026-10-25 18:18 UTC (step 02 + CSP fix), i.e. **before**
step 03 and the UI rebuild, which is why it is marked partial. Fargate apps are deployed with
`desired_count=0` by design (started on demand). The Studio stack has no reserved concurrency
(account limit 10). The low-cost component view remains in
[low-cost-scalable-deployment.svg](low-cost-scalable-deployment.svg).

## 4. Sequence diagrams

### 4.1 Staff sign-in — done (Cognito path deployed; successful real-staff login not yet observed)

```mermaid
sequenceDiagram
    autonumber
    actor S as Staff
    participant UI as Studio SPA
    participant API as REST staff boundary
    participant C as Cognito
    rect rgb(220, 252, 231)
    S->>UI: Username + password
    UI->>API: POST /v1/admin/socratic/session (exact Origin)
    alt Cognito mode (hosted and local REST)
        API->>C: AdminInitiateAuth, GetUser, live group lookup
        C-->>API: Identity + groups
    else Local mode (loopback only, explicit)
        API->>API: bcrypt check, in-memory session
    end
    API-->>UI: HttpOnly cookies + CSRF token + capabilities
    UI->>API: Later mutations send X-CSRF-Token
    S->>UI: Sign out
    UI->>API: DELETE /session (RevokeToken in Cognito mode)
    end
    rect rgb(254, 243, 199)
    Note over S,C: Real staff Cognito login, revocation and replay on the hosted URL still need acceptance (ledger 67 step 01/02)
    end
```

### 4.2 Draft authoring — done (local and hosted step 02)

```mermaid
sequenceDiagram
    autonumber
    actor S as Staff
    participant UI as Studio SPA
    participant API as socratic router
    participant D as socratic_service
    participant PG as Postgres
    rect rgb(220, 252, 231)
    S->>UI: Search sidebar, open or create workflow
    UI->>API: POST /workflows (Idempotency-Key)
    API->>D: create_workflow
    D->>PG: workflow + revision 1 + command receipt + audit + outbox (one transaction)
    S->>UI: Edit steps and rules in the drawer, switch Flow / Natural language / JSON
    S->>UI: Link source in Library (explicit solution revision)
    UI->>API: PUT /workflows/id (expected_hash, Idempotency-Key)
    API->>D: update_workflow
    D->>PG: lock, re-read, dependency + route freshness, new immutable revision
    D-->>UI: Saved revision or 409 stale
    UI->>API: POST /workflows/id/validate
    API-->>UI: Structural findings incl. unbindable activity refs
    end
```

### 4.3 Synthetic student preview — partial (done locally on Neon, not yet deployed)

```mermaid
sequenceDiagram
    autonumber
    actor S as Staff as synthetic student
    participant UI as Studio simulator
    participant API as socratic router
    participant P as socratic_preview
    participant SC as activity_scoring
    participant PG as Postgres
    rect rgb(254, 243, 199)
    S->>UI: Save and start preview
    UI->>API: POST /workflows/id/simulate (expected_hash)
    API->>P: start_preview
    P->>PG: Read activity.definition, pin private snapshot, insert preview + START event
    P-->>UI: Safe screen (no keys, hints or future nodes)
    S->>UI: Answer, Hint or Reveal
    UI->>API: POST /previews/id/respond (expected_version, idempotency_key)
    API->>P: respond
    P->>SC: evaluate(snapshot policy, response)
    SC-->>P: CORRECT / INCORRECT / UNCERTAIN + private evidence
    P->>PG: Route rule, CAS state_version, immutable event with result (one transaction)
    P-->>UI: Feedback, next step, decision trace
    end
    rect rgb(248, 250, 252)
    Note over S,PG: Pending: deploy to hosted Studio, staff-approved AR golden cases, real AR/MULTISELECT activities
    end
```

### 4.4 AI rule proposal via AgentCore — pending (ledger steps 04–05)

```mermaid
sequenceDiagram
    autonumber
    actor S as Staff
    participant UI as Ask AI drawer
    participant API as REST
    participant SF as Step Functions
    participant AC as AgentCore DeepSeek V3.2
    participant PG as Postgres
    rect rgb(220, 252, 231)
    S->>UI: Describe a rule in plain English
    UI->>API: PUT /workflows/id (save first)
    end
    rect rgb(248, 250, 252)
    UI->>API: POST /workflows/id/proposals (expected_hash, instruction)
    API->>PG: Durable job intent + budget check
    API->>SF: Start execution (outside the transaction)
    SF->>AC: Minimal context, typed proposal request
    AC-->>SF: Edge proposal + provenance
    SF->>API: Callback with result
    API->>PG: Store proposal, reject if base hash stale
    UI->>API: GET /jobs/id (bounded polling)
    S->>UI: Compare, adjust, Accept
    UI->>API: POST /proposals/job/accept (REST revalidates)
    API->>PG: New draft revision
    end
```

### 4.5 Quizzes by topic and link to a step — pending (plan 68 P2–P3)

```mermaid
sequenceDiagram
    autonumber
    actor S as Staff
    participant UI as Studio Library / step drawer
    participant API as /v1/admin/studio
    participant Q as quiz_service + catalog
    participant PG as Postgres
    rect rgb(220, 252, 231)
    Note over Q,PG: Existing: activity CRUD, skill/source mapping and course-state attach (requirement 46) behind the shared admin key
    end
    rect rgb(248, 250, 252)
    S->>UI: Library, Quizzes, choose topic in topic tree
    UI->>API: GET /artifacts?kind=quiz&topic=concept
    API->>Q: Catalog over activity, learning item, pool question
    Q->>PG: Read catalog view + artifact_topic
    API-->>UI: Quizzes with status, usage, coverage counts
    S->>UI: Link existing to current step, or Create new (typed form)
    UI->>API: POST /links {kind, id, revision} or POST /quizzes
    API->>PG: Typed ref on draft revision or attach to course state, review state DRAFT for new quiz
    S->>UI: Send for review, reviewer approves
    UI->>API: POST /quizzes/id/review (review capability)
    end
```

### 4.5b Step content: search and attach, add existing, create new from template — pending (plan 68 §4.5a–4.5b, P2–P3, semantic via the Finder in P2b)

```mermaid
sequenceDiagram
    autonumber
    actor S as Staff
    participant UI as Step drawer: Step content
    participant API as /v1/admin/studio
    participant IX as Postgres lexical + pgvector
    participant G as Neo4j + taxonomy similarity
    participant PG as Postgres question / video stores
    rect rgb(220, 252, 231)
    Note over IX,G: Existing: problem/solution/step/learning-item vectors, hybrid problem search, concept search, exam-pool match (service only)
    end
    rect rgb(248, 250, 252)
    alt Search and attach
        S->>UI: Search and attach (pre-filled from step topics, prompt, source problem)
        UI->>API: POST /question-bank/search {topics, query, kinds, status, difficulty}
        API->>G: Related concepts and reviewed neighbours
        API->>IX: Lexical + semantic over activities, learning items, pool questions, corpus
        API->>PG: Review state, usage, exclusions, duplicates collapsed
        API-->>UI: Selectable grouped results with staff-only preview
        S->>UI: Tick results, choose role (CHECK / PRACTICE / PRESENT), Attach selected
        opt Not yet approved (pool question, corpus problem, draft)
            UI->>API: POST /convert (Fetch as draft, provenance kept)
        end
    else Add existing
        S->>UI: Browse Library by topic or paste ID / YouTube URL
        UI->>API: GET /artifacts or POST /videos/external
    else Create new from template
        S->>UI: Pick question, strategy-phase, video or exam template (or Use as template)
        UI->>API: POST /templates/id/instantiate
        API->>PG: New draft artifact (PENDING_REVIEW)
        API-->>UI: Ref of the new draft
    end
    UI->>UI: Add to step content list [{ref, role, order}] (one CHECK per step)
    UI->>API: POST /links for the step, then save draft (expected_hash, Idempotency-Key)
    API->>PG: Validate kinds, roles, cross-source, pin revisions, new draft revision
    end
```

### 4.6 AI quiz drafts (semi-automatic and gap filling) — pending (plan 68 P4)

```mermaid
sequenceDiagram
    autonumber
    actor S as Staff
    participant UI as Studio
    participant API as /v1/admin/studio
    participant G as Generator + critic (exam-agent library)
    participant AI as Model provider
    participant PG as Postgres
    rect rgb(220, 252, 231)
    Note over G,AI: Existing: exam-agent generator and critic loop for student papers (automatic, critic-only)
    end
    rect rgb(248, 250, 252)
    S->>UI: Generate drafts: topic, kind, difficulty, count
    UI->>API: POST /quizzes/generate (budget, ai_generate capability)
    API->>G: Job with corpus sources and duplicate check
    G->>AI: Draft + critique rounds
    G-->>API: Draft activities with provenance
    API->>PG: activity.definition review_status PENDING_REVIEW, origin AI
    S->>UI: Edit and approve each draft (never auto-approved)
    Note over API,PG: Gap filling: scheduled job creates drafts for topics below N approved quizzes, review queue only
    end
```

### 4.7 Videos: generate or add existing — partial (pipeline done, Studio orchestration pending)

```mermaid
sequenceDiagram
    autonumber
    actor S as Staff
    participant UI as Studio video drawer
    participant API as REST
    participant M as manim-studio
    participant O as Object storage
    participant PG as Postgres
    rect rgb(220, 252, 231)
    Note over M,PG: Existing: research job, render job, promote, validate, approve, VIDEO_EXPLAINER instance · MP4 upload up to 25 MB and YouTube embed in mathbank-web
    end
    rect rgb(248, 250, 252)
    alt Generate from a step or topic
        S->>UI: Generate explainer
        UI->>API: POST /videos/generate
        API->>M: POST /v1/research-jobs (service key)
        M-->>API: SceneSpec for staff edit
        API->>M: POST /v1/render-jobs
        M->>O: MP4
        API->>PG: Promote scene DRAFT, staff approves, interaction instance
    else Add existing video
        S->>UI: Upload file or paste YouTube/Vimeo URL
        UI->>API: POST /videos/uploads (presign) or /videos/external (oEmbed)
        UI->>O: Direct upload with presigned URL
        API->>PG: visual.asset + pedagogy.video_asset PENDING_REVIEW
    end
    S->>UI: Tag topics, link to step or course state
    UI->>API: POST /links {kind: video}
    end
```

### 4.8 Exam from the content, attached to a student or group — pending (plan 68 P6, D-3 decided)

```mermaid
sequenceDiagram
    autonumber
    actor S as Staff
    actor St as Student
    participant UI as Studio
    participant API as REST
    participant EA as exam-agent
    participant EW as exam-web / mathbank-web
    participant PG as Postgres
    rect rgb(220, 252, 231)
    Note over EA,PG: Existing: student self-serve generation, pool reuse, generator/critic, grading in quiz_runtime, diagnosis
    end
    rect rgb(248, 250, 252)
    S->>UI: In a workflow or course, Create exam for this content
    UI->>API: POST /exams {source: workflow or course + revision} (manage_exams)
    API->>PG: Read content topics and linked approved quizzes, matching APPROVED pool items
    API-->>UI: Draft template with content-derived blueprint and candidate questions
    S->>UI: Add, remove, reorder, set points, time limit, attempts
    opt Missing slots
        UI->>API: Generate missing questions
        API->>EA: Generator + critic for blueprint gaps
        EA-->>API: Draft questions (PENDING_REVIEW)
        S->>UI: Approve or edit each draft
    end
    S->>UI: Attach to students, a group or the course enrollment, set dates
    UI->>API: POST /exams/id/assignments {audience, opens_at, due_at, variation off}
    opt Exclude for some students
        S->>UI: Exclude questions or the exam for a group or student-ID list
        UI->>API: POST /exclusions (audience module)
    end
    API->>PG: exam_assignment + resolved recipients
    St->>EW: Sees the assigned exam (and an EXAM step if linked to the workflow or course)
    EW->>EA: Start
    EA->>API: Materialize this student's paper from the approved template
    API->>PG: quiz.paper (student_id, exam_template_id, assignment_id), all approved questions minus this student's exclusions
    St->>EW: Answer and submit, graded per student by quiz_runtime
    S->>UI: Results per student and per group, manual grading queue
    end
```

### 4.9 Audience module: groups, EXCLUDE content and features — pending (plan 68 P7, decided 2026-10-25)

```mermaid
sequenceDiagram
    autonumber
    actor S as Staff
    actor St as Student
    participant UI as Studio
    participant API as REST
    participant AU as audience module
    participant RT as Exam / workflow / course / video delivery
    participant W as mathbank-web / exam-web
    participant PG as Postgres audience schema
    rect rgb(248, 250, 252)
    S->>UI: Students and groups: create group, add students or paste student IDs
    UI->>API: POST /groups, POST /groups/id/members (manage_access)
    API->>PG: student_group + members + audit
    S->>UI: On an exam question, video or step: Exclude for group or student IDs
    UI->>API: POST /exclusions/impact (dry run)
    API->>AU: Affected students, skipped steps, mandatory-path warnings
    AU-->>UI: Impact preview
    S->>UI: Confirm
    UI->>API: POST /exclusions
    API->>PG: exclusion_rule + audit + outbox
    St->>W: Opens exam, course or workflow
    W->>API: Request content
    API->>RT: Build student view
    RT->>AU: filter_items(student, items) and is_excluded(student, step or exam)
    AU-->>RT: Excluded question, video, step ids with reasons
    RT-->>W: Content already filtered (excluded step routed via ALWAYS or SUCCESS rule, else fallback)
    W->>API: GET /v1/me/features
    API->>AU: effective_features(student) most specific wins, EXCLUDE beats APPLY
    AU-->>W: Effective features for UI gating
    St->>W: Calls a guarded feature
    API->>AU: Server-side check, 403 when excluded
    S->>UI: Effective view for one student (what they see and why)
    end
```

### 4.10 Search everything and the AI assistant — pending (plan 68 P8–P9)

```mermaid
sequenceDiagram
    autonumber
    actor S as Staff
    participant UI as Studio search + assistant
    participant API as REST
    participant LLM as Model provider
    participant IX as Postgres lexical + pgvector
    participant G as Neo4j
    rect rgb(220, 252, 231)
    Note over IX,G: Existing: hybrid search for problems, solutions, steps, learning items · concept search · sidebar quick search in the Studio (client side)
    end
    rect rgb(248, 250, 252)
    S->>UI: "unused hard AR quizzes on inclusion-exclusion"
    UI->>API: POST /v1/admin/studio/search
    API->>LLM: Parse into filters + semantic query (optional)
    API->>IX: Lexical + vector over all artifact kinds
    API->>G: Topic neighbourhood expansion
    API-->>UI: Fused results with facets and editable filter chips
    S->>UI: Ask assistant to cover gaps in this workflow
    UI->>API: POST /assistant (context: workflow, step, filters)
    API->>LLM: Tools: search, coverage, propose quizzes, links, videos, exam blueprint, policies
    LLM-->>API: Typed proposals citing artifact ids and revisions
    API-->>UI: Proposals, staff accepts each one (stale proposals rejected)
    end
```

### 4.11 Finder: reuse-first vector search and wiring — pending (plan 68 §4.13, P2b)

```mermaid
sequenceDiagram
    autonumber
    actor S as Staff
    participant UI as Studio Finder
    participant API as REST studio boundary
    participant IX as Postgres lexical + studio.unit_embedding HNSW
    participant G as Neo4j
    participant OB as Outbox + embedding worker
    rect rgb(220, 252, 231)
    Note over IX,OB: Existing: representation, chunk, embedding pipeline with outbox jobs (corpus only, no ANN index on search.embedding)
    end
    rect rgb(248, 250, 252)
    S->>UI: Search and attach from step Justify (Finder opens full width)
    UI->>API: POST /v1/admin/studio/search {query from step intent, context, kinds}
    par lexical first
        API->>IX: tsvector + trigram on unit titles and prompts
    and semantic
        API->>IX: HNSW cosine top 200 over content, intent and topic vectors
    and graph
        API->>G: Reviewed concept and technique neighbours of the step
    end
    API-->>UI: RRF fused results, families collapsed, match reasons, facets
    S->>UI: Inspect a step sequence, then W to wire
    UI->>API: GET /artifacts/socratic_step/ID/usage and lineage
    S->>UI: Drop on target slot, choose Fork
    UI->>API: POST /workflows/ID/insert-units {expected_hash, units, entry_from, exit_to, mode fork}
    API->>API: Remap node keys and rules, validate draft, record derived_from
    API-->>UI: New draft hash, Finder closes, focus returns to the step
    S->>UI: Create new quiz item instead
    UI->>API: POST /search/similar {draft text}
    API-->>UI: 3 close matches, reuse instead
    API->>OB: On save, enqueue unit embedding (lexical row written in same transaction)
    OB->>IX: Upsert unit vectors, item leaves Indexing state
    end
```

## 5. Status matrix

| Component | Status | Evidence / next action |
|---|---|---|
| Staff sessions (Cognito + explicit local) | 🟩 Done | Ledger 67 step 01; hosted Cognito login acceptance pending |
| Draft persistence, migration 053 | 🟩 Done, deployed | Ledger 67 step 02; `MathBankSocraticStack` |
| Studio UI rebuild (rail, search, drawer, flow/NL/JSON) | 🟨 Partial | 34 unit + 10 e2e passing locally; not deployed |
| Synthetic preview, migration 054, shared scorer | 🟨 Partial | Ledger 67 step 03; 872 REST tests; deploy + AR approval pending |
| Local operator tooling (`make socratic-*`, password) | 🟩 Done | Root Makefile, `mathbank-socratic` skill |
| Ask AI proposals (AgentCore, Step Functions) | ⬜ Pending | Ledger 67 steps 04–05 |
| Live Neon/AWS vertical acceptance | ⬜ Pending | Ledger 67 step 06 |
| Full inspector, review cockpit, visuals, pilot | ⬜ Pending | Ledger 67 steps 07–10 |
| Studio adapters + capabilities | ⬜ Pending | Plan 68 P1 |
| Quizzes by topic, link existing, authoring + review | ⬜ Pending | Plan 68 P2–P3 (activity CRUD exists behind admin key) |
| Step content: search and attach (multi-select), add existing, create new from template | ⬜ Pending | Plan 68 §4.5a–4.5b: P2 search/attach + add existing, P3 templates, P8 semantic + concept similarity |
| AI quiz drafts and gap filling | ⬜ Pending | Plan 68 P4 |
| Videos from Studio (generate / register existing) | ⬜ Pending (pipeline 🟩) | Plan 68 P5 |
| Staff exams from content, attached to student/group (D-3, D-3a decided) | ⬜ Pending (student exams 🟩) | Plan 68 P6, uses audience module |
| Audience module: student groups, content EXCLUDE (exam, question, video, step, course item), feature APPLY/EXCLUDE | ⬜ Pending | Plan 68 P7 (before P6) |
| Finder: unit vector index (incl. Socratic steps, sequences, video segments), hybrid + graph fusion, find-similar/dedupe, where-used, lineage, link/fork/insert-sequence, full-width UI with wire mode | ⬜ Pending (corpus hybrid search 🟩; `search.embedding` has no ANN index) | Plan 68 §4.13, P2b |
| AI query understanding + rerank on the Finder | ⬜ Pending | Plan 68 P8, D-16 |
| Studio AI assistant with tools | ⬜ Pending | Plan 68 P9 |
| Micro chat scoped to one step / quiz item (separate module) | ⬜ Pending | Plan 68 §4.11, P9b |
| Workspace look consistent across all modules | 🟨 Partial (Studio done) | modern-ui-design `WORKSPACE_SHELL.md`; requirement 30 UI-23–UI-27 |
| mathbank-web admin quiz/media tabs, `/admin/manim-studio` | 🟥 Retire after parity | Plan 68 P10 |

## 6. Maintenance

Update this file whenever a ledger 67 step or plan 68 phase changes status: move the component's
class in the diagrams, the band colour in its sequence diagram and its row in §5. Re-run the
read-only stack listing to refresh §3 rather than assuming a deployment happened.
