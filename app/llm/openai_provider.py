from __future__ import annotations

import json

import httpx
from pydantic import ValidationError

from app.agents.context import SYSTEM_PROMPT, render_user_prompt
from app.llm.base import LLMError
from app.models import ReasoningOutput, ReasoningRequest

_CONFIDENCE_WORDS = {"very low": 0.1, "low": 0.3, "medium": 0.6, "moderate": 0.6, "high": 0.85, "very high": 0.95}


def _normalise(raw: dict) -> dict:
    """LLM output is untrusted: accept a qualitative confidence ("medium") by mapping it to a number.
    Anything else that does not fit the schema is still rejected by ReasoningOutput."""
    for h in raw.get("hypotheses") or []:
        if isinstance(h, dict) and isinstance(h.get("confidence"), str):
            c = h["confidence"].strip().lower()
            if c in _CONFIDENCE_WORDS:
                h["confidence"] = _CONFIDENCE_WORDS[c]
    return raw


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, timeout: float = 20.0, transport: httpx.BaseTransport | None = None) -> None:
        if not api_key:
            raise LLMError("OPENAI_API_KEY missing")
        self._model = model
        self._client = httpx.Client(base_url="https://api.openai.com/v1", timeout=timeout, transport=transport,
                                    headers={"Authorization": f"Bearer {api_key}"})

    def reason(self, req: ReasoningRequest) -> ReasoningOutput:
        body = {"model": self._model, "temperature": 0, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": render_user_prompt(req)}]}
        try:
            r = self._client.post("/chat/completions", json=body)
            r.raise_for_status()
            data = r.json()
            out = ReasoningOutput.model_validate(_normalise(json.loads(data["choices"][0]["message"]["content"])))
        except httpx.TimeoutException as e:
            raise LLMError("LLM timeout") from e
        except httpx.HTTPError as e:
            raise LLMError(f"LLM provider error: {type(e).__name__}") from e  # never echo response bodies/keys
        except (KeyError, IndexError, ValueError, ValidationError) as e:
            raise LLMError("LLM returned malformed output") from e
        usage = data.get("usage", {})
        out.tokens_in, out.tokens_out = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
        return out
