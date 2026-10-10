"""Thin OpenAI structured-output adapter sharing the OllamaProvider.complete() interface."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class OpenAIChatProvider:
    model: str = "gpt-4o-mini"
    digest: str = ""  # Filled per-model in __post_init__; OpenAI exposes no local model digest.
    temperature: float = 0.1
    timeout: int = 120

    def __post_init__(self):
        if not self.digest:
            # A model-specific stable placeholder so two different OpenAI models used as
            # generator/critic are distinguishable; OpenAI itself has no local digest concept.
            object.__setattr__(self, "digest", f"openai-hosted:{self.model}")

    def config(self) -> dict:
        return {
            "provider": "openai",
            **asdict(self),
            "generation_profile": "atomic-steps-mandatory-enrichment-v1",
        }

    def preflight(self) -> "OpenAIChatProvider":
        # Credential/connectivity checks happen on the first real paid call;
        # this mirrors OllamaProvider.preflight()'s return-self contract.
        return self

    def complete(self, messages: list[dict], schema: dict) -> tuple[str, dict]:
        from mathbank_rest.tutor import _client

        response = _client.with_options(
            timeout=self.timeout, max_retries=0
        ).chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "offline_tutoring_route",
                    "strict": True,
                    "schema": schema,
                },
            },
            messages=messages,
        )
        if not response.choices or not response.choices[0].message.content:
            raise ValueError("Provider refused or returned no program.")
        if response.choices[0].finish_reason == "length":
            from mathbank_rest.route_ollama import OutputTruncated

            raise OutputTruncated(
                "OpenAI output exceeded token budget; no partial program accepted."
            )
        raw = response.choices[0].message.content
        metrics = {
            "usage": response.usage.model_dump() if getattr(response, "usage", None) else None
        }
        return raw, metrics
