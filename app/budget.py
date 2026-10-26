"""Budget guard: checked before any model call. Limits live in app/config.py (Limits)."""

import json
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from app.config import USAGE_LOG, Limits

_lock = threading.Lock()
_runs_by_visitor: dict[str, deque] = defaultdict(deque)  # in memory only; IPs are never written to disk

DAILY_BUDGET_MESSAGE = ("I'm terribly sorry, dear traveler, but Customs has used its travel budget for today. "
                        "Do come back tomorrow, and I'll gladly look things up for you then.")
VISITOR_LIMIT_MESSAGE = ("My, you have been a busy traveler! You've asked {n} questions this past hour, which is "
                         "my limit for now. Please rest a moment and try again in about {minutes} minute{s}.")
TOO_LONG_MESSAGE = ("That's a rather long itinerary, dear traveler. Could you describe your situation in "
                    "{max} characters or fewer? (Yours is {n}.)")
RUN_LIMIT_MESSAGE = ("I'm afraid this one needed more looking-up than I'm allowed on a single trip. Could you "
                     "describe the situation a little more narrowly, and I'll try again?")


def spent_today_usd() -> float:
    """Total cost of today's runs (UTC day), from usage_log.json."""
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        log = json.loads(USAGE_LOG.read_text()) if USAGE_LOG.exists() else []
    except json.JSONDecodeError:
        log = []
    return sum(e.get("cost_usd") or 0 for e in log if str(e.get("time", "")).startswith(today))


def over_daily_budget() -> bool:
    return spent_today_usd() >= Limits.daily_budget_usd


def take_visitor_slot(visitor: str) -> int | None:
    """Record a run for this visitor. Returns None if allowed, else the minutes until a slot frees up."""
    now = time.time()
    with _lock:
        runs = _runs_by_visitor[visitor]
        while runs and now - runs[0] >= 3600:
            runs.popleft()
        if len(runs) >= Limits.runs_per_hour_per_visitor:
            wait = 3600 - (now - runs[0]) if runs else 3600
            return max(1, round(wait / 60))
        runs.append(now)
        return None
