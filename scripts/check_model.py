"""Manual check: one tiny gpt-6-luna call through Portkey. Prints the reply, the model that answered, and token usage."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic_ai import Agent  # noqa: E402

from app.config import build_model, is_allowed_model, load_env  # noqa: E402


def main() -> None:
    env_path = load_env()
    print(f".env used: {env_path}")
    agent = Agent(build_model())
    result = agent.run_sync("Reply with exactly one word: ok")
    reply_models = {m.model_name for m in result.all_messages() if hasattr(m, "model_name") and m.model_name}
    usage = result.usage
    print(f"reply: {result.output!r}")
    print(f"answered by: {sorted(reply_models)}")
    print(f"tokens: input={usage.input_tokens} output={usage.output_tokens} total={usage.total_tokens} "
          f"requests={usage.requests}")
    bad = [m for m in reply_models if not is_allowed_model(m)]
    if bad or not reply_models:
        sys.exit(f"FAIL: unexpected model(s): {bad or 'none reported'}")
    print("OK: only gpt-6-luna replied")


if __name__ == "__main__":
    main()
