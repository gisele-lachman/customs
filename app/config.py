"""Settings: .env lookup, the one allowed model, and the Portkey model builder."""

import os
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent  # the customs/ folder
ENV_CANDIDATES = [APP_DIR / ".env", APP_DIR.parent / ".env"]

MODEL_NAME = "gpt-6-luna"
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
PRICES_FILE = APP_DIR / "prices.json"
USAGE_LOG = APP_DIR / "usage_log.json"


def load_env() -> Path | None:
    """Load the first .env found (customs/.env, then the folder above). Returns its path, or None."""
    for path in ENV_CANDIDATES:
        if path.is_file():
            load_dotenv(path)
            return path
    return None


load_env()  # so limit overrides and switches in .env apply


def _env_number(name: str, default, cast=int):
    """Every limit can be overridden by an environment variable (used to test limits on a throwaway server)."""
    raw = os.environ.get(name, "").strip()
    try:
        return cast(raw) if raw else default
    except ValueError:
        return default


class Limits:
    """Every limit in one place. Budget limits refuse before any model call; run limits stop a run gracefully."""
    # budget guard (checked before any model call)
    daily_budget_usd = _env_number("CUSTOMS_DAILY_BUDGET_USD", 2.00, float)  # whole app, per UTC day, from usage_log.json
    runs_per_hour_per_visitor = _env_number("CUSTOMS_RUNS_PER_HOUR_PER_VISITOR", 15)  # per IP address, rolling hour
    max_situation_chars = _env_number("CUSTOMS_MAX_SITUATION_CHARS", 500)  # longer situations are refused
    # per-run limits (the agent stops with a friendly message)
    max_tool_calls = _env_number("CUSTOMS_MAX_TOOL_CALLS", 8)            # Wikipedia searches + page fetches
    max_model_requests = _env_number("CUSTOMS_MAX_MODEL_REQUESTS", 10)   # model requests
    max_output_tokens_per_request = 4000  # token cap on each model request (includes reasoning tokens)
    reasoning_effort = "low"
    checker_max_requests = 2        # one call, plus one retry if the output doesn't validate
    checker_max_output_tokens = 2500


def defeat_cache() -> bool:
    """Test switch (off by default): put a random line at the very start of every model call so nothing is cached."""
    return os.environ.get("CUSTOMS_DEFEAT_CACHE", "off").strip().lower() in ("on", "1", "true", "yes")


def checker_enabled() -> bool:
    """The Checker is on by default. Set CUSTOMS_CHECKER=off (in .env or the environment) to measure without it."""
    load_env()
    return os.environ.get("CUSTOMS_CHECKER", "on").strip().lower() not in ("off", "0", "false", "no")


def portkey_api_key() -> str:
    load_env()
    key = os.environ.get("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is missing. Copy .env.example to .env and fill it in.")
    return key


def is_allowed_model(name: str | None) -> bool:
    """Portkey may report gpt-6-luna as e.g. gpt-6-luna-global or a dated release; anything else fails."""
    return bool(name) and (name == MODEL_NAME or name.startswith(MODEL_NAME + "-"))


def build_model():
    # Responses API: Portkey's chat-completions route may reject function tools for this model.
    from openai import AsyncOpenAI
    from pydantic_ai.models.openai import OpenAIResponsesModel
    from pydantic_ai.providers.openai import OpenAIProvider

    key = portkey_api_key()
    client = AsyncOpenAI(base_url=PORTKEY_BASE_URL, api_key=key, default_headers={"x-portkey-api-key": key})
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))
