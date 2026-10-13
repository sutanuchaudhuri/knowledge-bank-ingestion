# 21 — ADK / OpenAI Version Notes

This architecture was checked against current Google ADK documentation as of October 2026.

Relevant upstream references:

- Google ADK LiteLLM model connector:
  https://adk.dev/agents/models/litellm/
- Google ADK agent-team tutorial demonstrating multi-model use:
  https://adk.dev/tutorials/agent-team/
- Google Agents CLI authentication/model-provider guidance:
  https://google.github.io/agents-cli/guide/authentication/
- Google ADK Python LiteLLM implementation:
  https://github.com/google/adk-python/blob/main/src/google/adk/models/lite_llm.py

Important current implementation note:

- ADK documents OpenAI access via `google.adk.models.lite_llm.LiteLlm`.
- Configure the OpenAI provider key through `OPENAI_API_KEY`.
- Use the LiteLLM provider/model string format (`openai/<model-id>`).
- Pin supported patched dependency versions rather than copying old example versions blindly.

> **Status**: matches `mathbank-agent`'s actual dependency pins (`google-adk`,
> `litellm`, `httpx` — see `mathbank-agent/pyproject.toml`) and its
> `LiteLlm(model="openai/gpt-4o-mini")` usage in `agent.py`.
