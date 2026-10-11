# 12 — Implementation, Testing and Deployment

## 1. Dependency policy

Install Apps support:

```bash
pip install "fastmcp[apps]"
```

or project-equivalent `uv add`.

Because FastMCP documentation says Prefab is under active development and FastMCP does
not pin an upper bound, pin exact tested versions in the application lockfile.

Do not place an unbounded `prefab-ui>=...` in production requirements.

## 2. Development preview

FastMCP documents:

```bash
fastmcp dev apps server.py
```

Use it for:
- student app;
- progress app;
- admin app;
- Prefab component regression checks.

Also test inside the actual target MCP host.

## 3. Repository structure

Suggested:

```text
intellitutor_mcp/
  server.py
  apps/
    student.py
    tutoring.py
    progress.py
    admin.py
  ui/
    fragments/
      course_state.py
      quiz.py
      feedback.py
      progress.py
    custom/
      geometry/
      graph_matrix/
      video_timeline/
  contracts/
    course.py
    quiz.py
    interaction.py
    tutor.py
  services/
    adapters.py
```

Domain services should remain in the existing MathBank service modules where possible.

## 4. Tests

### Unit
- DTO validation;
- authorization;
- student payload strips answer keys;
- course advancement;
- hint-level policy;
- route pinning;
- evidence rules;
- progress summary.

### Prefab snapshot/structure
- correct headings/buttons/components;
- no hidden answer in state;
- disabled loading state;
- correct app tool references.

### MCP
- model-visible UI entry points appear;
- app-only backend tools omitted from model-facing discovery where host honors visibility;
- direct calls still require authorization;
- function-reference `CallTool` survives mounted namespace.

### Apps fallback
- client supports Apps -> rich UI;
- client does not -> safe plain text.

### Custom HTML
- CSP minimal;
- semantic event sent;
- no secret data;
- host SDK reconnect/fallback.

### Generative UI
- admin flag only;
- no hidden student data;
- output not auto-promoted.

## 5. Security tests

Explicitly test the FastMCP warning that visibility is not a security boundary:

Attempt direct MCP call to:
- submit quiz for someone else's enrollment;
- publish course without role;
- request a future hint;
- record event against unrelated interaction.

All must fail server-side.

## 6. Performance

Do not call server for every harmless local UI change.

Use client state for:
- filters;
- disclosure toggles;
- temporary manipulation.

Commit meaningful semantic events:
- answer submit;
- slider settled/commit;
- matrix row submit;
- drag completion;
- course advance;
- hint request.

## 7. Observability

Attach request/correlation IDs across:
- FastMCP tool call;
- domain transaction;
- learner event;
- AI usage;
- outbox event;
- graph/search job.

## 8. Deployment gates

Before production:
- exact FastMCP/Prefab lock tested;
- host Apps support tested;
- CSP verified;
- auth tested independently of visibility;
- plain-text fallback tested;
- published course golden flow tested;
- hidden-answer scan passed;
- learner-private data scan passed.

## 9. Golden flow

```text
user asks to learn
-> model calls open_course
-> Prefab course UI
-> PRE quiz
-> deterministic grade
-> course advance
-> video
-> timestamped Q&A
-> interaction
-> evidence/feedback
-> hint
-> tutoring route
-> return
-> POST assessment
-> progress dashboard
-> model-readable progress summary
```

## 10. Copilot implementation sequence

```text
Phase 1  Pin/test FastMCP + Prefab versions.
Phase 2  Build student FastMCPApp shell and fallback.
Phase 3  Implement secure course-state DTO.
Phase 4  Implement quiz submit/advance backend tools.
Phase 5  Implement hint/route FastMCPApp.
Phase 6  Integrate interaction runtime.
Phase 7  Implement progress ToolResult dashboard.
Phase 8  Implement timestamp Q&A.
Phase 9  Add Custom HTML math renderers where Prefab has real gaps.
Phase 10 Build admin FastMCPApp.
Phase 11 Add internal Generative UI flag.
Phase 12 Security/performance/accessibility regression suite.
```
