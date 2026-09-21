import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

TRACE_PATH = Path(__file__).resolve().parents[2] / "data" / "llm_calls.jsonl"
TRACING = os.getenv("LLM_TRACE", "1") != "0"


def _record(kind: str, system: str, user: str, output: str, usage, seconds: float) -> None:
    if not TRACING:
        return
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRACE_PATH.open("a") as f:
        f.write(json.dumps({
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": kind,
            "model": MODEL,
            "seconds": round(seconds, 2),
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "system": system,
            "user": user,
            "output": output,
        }) + "\n")

PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
MODEL = os.getenv("LLM_MODEL", "claude-sonnet-5")

T = TypeVar("T", bound=BaseModel)


def _client() -> anthropic.Anthropic:
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY not set - put it in .env")
    return anthropic.Anthropic()


def structured(system: str, user: str, schema: type[T], max_tokens: int = 1024) -> T:
    """Ask the model for an instance of `schema`. The only place the SDK is called."""
    t0 = time.monotonic()
    response = _client().messages.parse(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=schema,
    )
    _record(schema.__name__, system, user, str(response.parsed_output), response.usage,
            time.monotonic() - t0)
    if response.parsed_output is None:
        raise RuntimeError(f"no structured output (stop_reason={response.stop_reason})")
    return response.parsed_output


def text(system: str, user: str, max_tokens: int = 2048) -> str:
    """Free-text answer, for synthesis."""
    t0 = time.monotonic()
    response = _client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    out = "".join(b.text for b in response.content if b.type == "text")
    _record("text", system, user, out, response.usage, time.monotonic() - t0)
    return out
