"""Check project credentials without printing keys, provider bodies or prompts."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import dotenv_values
from openai import APIError, OpenAI
from project_env import load_project_openai

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chat", action="store_true",
                        help="Also test the configured LiteLLM model (small paid request)")
    args = parser.parse_args()
    try:
        key = load_project_openai(ROOT / "mathbank-agent/.env")
    except RuntimeError:
        print("Configuration FAILED: set a literal key in root .env; shell keys are ignored.")
        return 1
    print("Credential source: project .env only (value hidden).")
    for service in ("mathbank-rest", "mathbank-agent", "mathbank_data_ingestion"):
        matches = dotenv_values(ROOT / service / ".env", interpolate=False).get("OPENAI_API_KEY") == key
        print(f"{service} key sync: {'MATCH' if matches else 'OUT OF SYNC; run make sync-openai-key'}")
    try:
        client = OpenAI(api_key=key, timeout=20, max_retries=0)
        client.models.list()
    except APIError as exc:
        print(f"OpenAI authentication FAILED: {type(exc).__name__}; "
              f"HTTP {getattr(exc, 'status_code', None)}; code {getattr(exc, 'code', None)}.")
        return 1
    print("OpenAI authentication: PASS.")
    if args.chat:
        from litellm import completion
        from litellm.exceptions import (
            APIConnectionError,
            AuthenticationError,
            BadRequestError,
            NotFoundError,
            PermissionDeniedError,
            RateLimitError,
            Timeout,
        )
        from litellm.exceptions import (
            APIError as LiteAPIError,
        )
        values = dotenv_values(ROOT / "mathbank-agent/.env", interpolate=False)
        model = values.get("MATHBANK_AGENT_MODEL") or "openai/gpt-4o-mini"
        if not model.startswith("openai/"):
            print("Chat check FAILED: this command checks only openai/ LiteLLM models.")
            return 1
        try:
            result = completion(
                model=model, api_key=key,
                api_base=os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
                or "https://api.openai.com/v1",
                messages=[{"role": "user", "content": "Reply OK."}],
                max_tokens=8, timeout=30, num_retries=0,
            )
        except (LiteAPIError, APIConnectionError, AuthenticationError, BadRequestError,
                NotFoundError, PermissionDeniedError, RateLimitError, Timeout) as exc:
            print(f"LiteLLM chat FAILED: {type(exc).__name__}; "
                  f"HTTP {getattr(exc, 'status_code', None)}. "
                  "401: key; 403/404: model permissions; 429: quota/rate limit.")
            return 1
        if not result.choices or not result.choices[0].message.content:
            print("LiteLLM chat FAILED: no answer returned.")
            return 1
        print(f"LiteLLM configured chat model: PASS ({model}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
