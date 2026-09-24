import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError

load_dotenv()
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
MODEL = os.getenv("LLM_MODEL", "anthropic:claude-sonnet-5")
MAX_TOKENS = 16000

# "server busy / rate limited" - worth waiting for; anything else is a real error
TRANSIENT = {429, 500, 502, 503, 529}
ATTEMPTS = 3

TRACE_PATH = Path(__file__).resolve().parents[2] / "data" / "llm_calls.jsonl"
TRACING = os.getenv("LLM_TRACE", "1") != "0"

T = TypeVar("T", bound=BaseModel)


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
            "input_tokens": usage.input_tokens if usage else None,
            "output_tokens": usage.output_tokens if usage else None,
            "system": system,
            "user": user,
            "output": output,
        }) + "\n")


def _run(kind: str, system: str, user: str, output_type, model: str | None = None):
    """The only place a model is called."""
    agent = Agent(model or MODEL, output_type=output_type, instructions=system,
                  model_settings={"max_tokens": MAX_TOKENS})
    t0 = time.monotonic()
    for attempt in range(1, ATTEMPTS + 1):
        try:
            result = agent.run_sync(user)
            break
        except Exception as e:
            # log failures too - otherwise the call log only ever shows successes
            _record(kind, system, user, f"ERROR {type(e).__name__}: {e}", None, time.monotonic() - t0)
            busy = isinstance(e, ModelHTTPError) and e.status_code in TRANSIENT
            if not busy or attempt == ATTEMPTS:
                raise
            time.sleep(5 * attempt)
    usage = result.usage() if callable(result.usage) else result.usage
    _record(kind, system, user, str(result.output), usage, time.monotonic() - t0)
    return result.output


def structured(system: str, user: str, schema: type[T], model: str | None = None) -> T:
    """Ask the model to fill in `schema` (a form); returns a validated instance."""
    return _run(schema.__name__, system, user, schema, model)


def text(system: str, user: str) -> str:
    """Free-text answer, for synthesis."""
    return _run("text", system, user, str)
