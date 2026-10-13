# mathbank-exam-agent

Natural-language mock-exam paper generation on the **AWS Strands Agents SDK**
(requirements/64) — a genuinely separate project from `mathbank-agent` (which uses
Google ADK), with its own independent service layer and (planned) independent UI.

## Status (this session)

**Service layer implemented and live-verified end-to-end.** Not yet built: the
independent UI (`mathbank-exam-web`) and the Lambda deployment stack — see
[requirements/64_AWS_BEDROCK_MOCK_EXAM_AGENT.md](/Volumes/External/Developer/knowledge-bank-ingestion/documentation/requirements/64_AWS_BEDROCK_MOCK_EXAM_AGENT.md)
for the full design and current progress tracker.

**Model backend: OpenAI, not Bedrock, for now.** Bedrock model invocation is blocked
account-wide on this AWS account (`ValidationException: Error 002: Access to Bedrock
models is not allowed for this account`, confirmed live with two different models).
The Strands Agents SDK itself — the actual "AWS agent framework, not Google ADK"
requirement — is unchanged; only the model provider is swapped (`llm_models.py`'s
`_openai_model()` instead of a `BedrockModel`). Swapping back once Bedrock access is
resolved is a one-line change per factory function in `llm_models.py`.

## What this project reuses vs. adds new

See requirements/64 §2 for the full table. In short: the `quiz.*` Postgres schema and
grading/mastery-absorption logic (requirements/53) are reused via `mathbank-rest`'s
REST surface — this project **never connects to Postgres/Neo4j directly**. What's new
here: the natural-language intake parser, the generator↔critic agent loop (both Strands
`Agent`s), the diagnosis agent, and a thin FastAPI wrapper.

## Architecture

```
mathbank-exam-agent/
  src/mathbank_exam_agent/
    config.py          # settings (OpenAI key, mathbank-rest URL, MCP server URL, model ids)
    llm_models.py       # model-backend factory (OpenAI now; Bedrock is a one-line swap)
    rest_client.py      # the ONE write/read path into mathbank-rest's quiz.* data
    mcp_tools.py         # Strands MCPClient session against the deployed mathbank-mcp-competitions
    schemas.py           # Pydantic models for every agent's structured output
    intake.py            # NL request -> GenerationIntake (one Strands Agent call)
    generator_agent.py   # drafts one question, using MCP tools for corpus grounding
    critic_agent.py      # reviews one draft against a fixed rubric
    diagnosis_agent.py   # synthesizes the post-exam holistic report
    exam_service.py      # orchestration: intake -> generate+critique loop -> import; diagnosis
    main.py               # FastAPI app (thin — all logic above)
```

## Running locally

```bash
make install
cp .env.example .env   # fill in openai_api_key, admin_api_key (shared with mathbank-rest), mcp_competitions_url
aws login               # or otherwise refresh the aws-sutanu-admin SSO session — Cognito
                        # signup/login/forgot-password all need live AWS credentials, even
                        # for local dev (`make run` exports AWS_PROFILE=aws-sutanu-admin and
                        # AWS_DEFAULT_REGION=us-east-2 for you; override either if your
                        # account/profile differs)
make run                # needs mathbank-rest already running on :8000
make test                # unit tests only — no network/LLM calls, fast and free
```

The one real end-to-end flow (NL request → generator↔critic loop → persisted paper →
student response → diagnosis) was run manually, live, this session — against the real
OpenAI API, the real deployed `mathbank-mcp-competitions` Function URL, and the real
Neon Postgres instance. It is not yet encoded as an automated pytest case (each real
run costs real tokens and takes 60-120+ seconds) — tracked as a known gap in
requirements/64 §11.
