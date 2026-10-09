"""Local-only structured generation; never falls back to a paid provider."""

from dataclasses import asdict, dataclass
from urllib.parse import urlsplit

import httpx


class OllamaError(RuntimeError):
    pass


@dataclass(frozen=True)
class OllamaProvider:
    model: str
    endpoint: str = "http://127.0.0.1:11434"
    num_ctx: int = 16384
    num_thread: int = 8
    num_predict: int = 4096
    timeout: int = 900
    digest: str = ""
    runtime_version: str = ""

    def __post_init__(self):
        if not 2048 <= self.num_ctx <= 32768 or not 1 <= self.num_thread <= 10:
            raise ValueError("Ollama context must be 2048-32768 and CPU threads 1-10.")
        if not 1 <= self.num_predict < self.num_ctx:
            raise ValueError("Output budget must be positive and smaller than context.")

    def config(self) -> dict:
        return {
            "provider": "ollama",
            **asdict(self),
            "temperature": 0.1,
            "generation_profile": "atomic-steps-mandatory-enrichment-critic-v3",
        }

    def preflight(self) -> "OllamaProvider":
        parsed = urlsplit(self.endpoint)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or (parsed.username or parsed.password or parsed.query or parsed.fragment)
        ):
            raise ValueError("Ollama generation requires a credential-free loopback HTTP endpoint.")
        try:
            with httpx.Client(timeout=30) as client:
                tags = client.get(self.endpoint + "/api/tags")
                tags.raise_for_status()
                version = client.get(self.endpoint + "/api/version")
                version.raise_for_status()
                model = next((m for m in tags.json()["models"] if m["name"] == self.model), None)
                if not model:
                    raise ValueError("Requested Ollama model is not installed.")
                return OllamaProvider(
                    **(
                        asdict(self)
                        | {"digest": model["digest"], "runtime_version": version.json()["version"]}
                    )
                )
        except httpx.HTTPError:
            raise OllamaError("Local Ollama preflight failed; no paid fallback.") from None

    def complete(self, messages: list[dict], schema: dict) -> tuple[str, dict]:
        # UTF-8 byte count is a conservative token upper bound, plus chat-template overhead.
        prompt_bound = sum(len(m["content"].encode("utf-8")) for m in messages) + 512
        if prompt_bound + self.num_predict > self.num_ctx:
            raise ValueError(
                "Canonical source/repair exceeds safe local context budget; no truncation."
            )
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    self.endpoint + "/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "format": schema,
                        "keep_alive": "30m",
                        "options": {
                            "temperature": 0.1,
                            "num_ctx": self.num_ctx,
                            "num_thread": self.num_thread,
                            "num_predict": self.num_predict,
                        },
                    },
                )
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError):
            raise OllamaError(
                "Local Ollama generation/transport failed; no paid fallback."
            ) from None
        if data.get("done_reason") == "length":
            raise ValueError("Ollama output exceeded token budget; no partial program accepted.")
        raw = data.get("message", {}).get("content")
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("Ollama returned no structured program.")
        metrics = {
            key: data.get(key)
            for key in (
                "model",
                "created_at",
                "done_reason",
                "total_duration",
                "load_duration",
                "prompt_eval_count",
                "prompt_eval_duration",
                "eval_count",
                "eval_duration",
            )
        }
        metrics["prompt_token_upper_bound"] = prompt_bound
        return raw, metrics
