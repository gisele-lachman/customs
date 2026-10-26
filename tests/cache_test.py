"""Cache comparison (real, paid runs): 4 situations run normally, then again with caching defeated
(CUSTOMS_DEFEAT_CACHE=on puts a random line at the very start of every model call). Writes tests/cache_runs.json.
Run: .venv/bin/python tests/cache_test.py
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agent import CoachError, coach  # noqa: E402

TESTS = Path(__file__).resolve().parent
PAUSE = 20
CASES = ["Business dinner with my client's boss in Seoul", "Attending a wedding in India",
         "First business meeting with a German company in Munich", "Having tea with my host family in Morocco"]


def brief(u: dict) -> dict:
    return {k: u[k] for k in ("input", "cached", "cache_write", "output", "requests", "cost_usd")}


async def one(situation: str, mode: str) -> dict:
    os.environ["CUSTOMS_DEFEAT_CACHE"] = "on" if mode == "cache defeated" else "off"
    t0 = time.monotonic()
    try:
        r = await coach(situation, source=f"cache-test ({mode})", debug=True)
    except CoachError as exc:
        return {"situation": situation, "mode": mode, "error": str(exc)}
    finally:
        os.environ["CUSTOMS_DEFEAT_CACHE"] = "off"
    d, c = r["debug"], r["check"]
    return {"situation": situation, "mode": mode, "seconds": round(time.monotonic() - t0, 2),
            "agent": brief(d["agent_usage"]), "checker": brief(d["checker_usage"]),
            "total_cost_usd": r["usage"]["cost_usd"], "tool_calls": r["usage"]["tool_calls"],
            "tips_before": c["before"], "tips_kept": c["kept"], "partly": c["partly"],
            "removed": len(c["removed"]), "limited_coverage": (r.get("coverage") or {}).get("limited"),
            "models": r["usage"]["models"]}


async def main() -> None:
    runs = []
    for mode in ("normal", "cache defeated"):
        for s in CASES:
            if runs:
                await asyncio.sleep(PAUSE)
            res = await one(s, mode)
            runs.append(res)
            print(mode, "|", s, "|", res.get("error") or
                  f"agent in {res['agent']['input']} cached {res['agent']['cached']} out {res['agent']['output']}; "
                  f"checker cached {res['checker']['cached']}; total ${res['total_cost_usd']:.5f}; kept {res['tips_kept']}",
                  flush=True)
            (TESTS / "cache_runs.json").write_text(json.dumps(runs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
