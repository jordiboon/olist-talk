import os
from typing import TypeVar

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5")

T = TypeVar("T", bound=BaseModel)


def _client() -> anthropic.Anthropic:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set - put it in .env")
    return anthropic.Anthropic()


def structured(system: str, user: str, schema: type[T], max_tokens: int = 1024) -> T:
    """Ask the model for an instance of `schema`. The only place the SDK is called."""
    response = _client().messages.parse(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=schema,
    )
    if response.parsed_output is None:
        raise RuntimeError(f"no structured output (stop_reason={response.stop_reason})")
    return response.parsed_output


def text(system: str, user: str, max_tokens: int = 2048) -> str:
    """Free-text answer, for synthesis."""
    response = _client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in response.content if b.type == "text")
