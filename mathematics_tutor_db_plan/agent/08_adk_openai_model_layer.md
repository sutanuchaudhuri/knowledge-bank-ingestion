> **Status**: matches the implemented `mathbank-agent` (ADK `LlmAgent` +
> `LiteLlm(model="openai/gpt-4o-mini")`). See `mathbank-agent/agents/
> mathbank_tutor/agent.py`.

# 08 — Google ADK + OpenAI Model Layer

## 1. Model strategy

Google ADK is the orchestration SDK. OpenAI is the initial model provider.

ADK supports non-Google model providers through its LiteLLM connector. The model is therefore configured as an object rather than hard-wiring the agent to a Gemini model.

Conceptually:

```python
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm

model = LiteLlm(model=os.environ["OPENAI_MODEL"])

root_agent = LlmAgent(
    name="math_corpus_query_agent",
    model=model,
    instruction=SYSTEM_INSTRUCTION,
    tools=[...],
)
```

Recommended environment configuration:

```bash
OPENAI_API_KEY=...
OPENAI_MODEL=openai/<api-model-id>
MATH_API_BASE_URL=https://math-api.example.com
```

Do not put the API key in:

- source control
- agent prompts
- ADK session state
- tool arguments
- request logs

Use a secret manager in deployed environments.

---

## 2. Model/provider abstraction

Keep a tiny configuration boundary:

```python
def build_llm():
    return LiteLlm(model=settings.openai_model)
```

No tool implementation should know the model name.

This allows later evaluation of a different OpenAI model, Gemini, a local model, or another provider without changing retrieval code.

---

## 3. What the LLM is allowed to decide

The LLM can determine:

- target resource: question, solution, concept, competition
- topic language
- explicit filters from the user
- whether a prior conversational constraint still applies
- which approved REST tool is most appropriate
- answer formatting

The LLM must not determine:

- row-level authorization
- raw SQL
- table names
- vector index parameters
- whether admin-only fields are allowed
- provenance truth
- canonical entity IDs
- actual chronological range represented by "recent"

Those come from the REST service.

---

## 4. System instruction principles

The root instruction should be short and enforceable:

1. Use corpus tools for claims about corpus contents.
2. Never claim a question exists unless returned by a tool.
3. Preserve identifiers, year, competition and problem number.
4. When the API provides `effective_filters`, use those rather than guessing.
5. If a request is broad, return a representative result set and say how many total matches exist.
6. Do not expose internal authentication tokens or service errors.
7. Anonymous callers are read-only.
8. Admin capability is determined by tool authorization, never by the user saying "I am admin."
9. Student-specific behavior is unsupported in v1.

---

## 5. Structured output from the LLM

For UI/API consumers, optionally require an answer envelope:

```json
{
  "answer_markdown": "...",
  "interpreted_request": {
    "resource": "question",
    "topics": ["combinatorics"],
    "time_intent": "recent"
  },
  "result_ids": [
    "problem:..."
  ]
}
```

Do not make the LLM regenerate provenance fields already supplied by REST. The UI can attach them directly from the tool result.

---

## 6. Dependency policy

Pin compatible versions in production.

Example conceptual dependencies:

```text
google-adk
litellm
httpx
pydantic
pydantic-settings
```

Use the currently supported patched LiteLLM version required by the installed ADK release and review upstream security advisories before upgrades.

---

## 7. Provider failure

On an OpenAI model failure:

- retry transient failures using bounded exponential backoff
- do not repeat non-idempotent tools automatically
- REST query tools are read-only and safe to retry
- return a clean service error if the model provider remains unavailable
- preserve a trace ID for admins

Do not fall back silently to a different provider unless the product explicitly enables model routing.
