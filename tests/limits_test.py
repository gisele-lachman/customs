"""Budget-guard and run-limit test. For each limit, start a throwaway server on port 8001 with that limit set very low
(via its environment override), use the real page in headless Chrome, then stop that exact server process.
The real app's limits in app/config.py are never edited, so nothing needs to be set back.

Run with a Python that has Playwright installed (not needed by the app itself):
    <python-with-playwright> tests/limits_test.py
Writes tests/limits_test.json.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "bin" / "python"
LOG = ROOT / "usage_log.json"
PORT = 8001
URL = f"http://127.0.0.1:{PORT}/"

CASES = [
    {"limit": "daily spending cap", "env": {"CUSTOMS_DAILY_BUDGET_USD": "0.0000001"},
     "situation": "Business dinner with my client's boss in Seoul", "expect": "refused before any model call"},
    {"limit": "per-visitor runs per hour", "env": {"CUSTOMS_RUNS_PER_HOUR_PER_VISITOR": "0"},
     "situation": "Attending a wedding in India", "expect": "refused before any model call"},
    {"limit": "input length", "env": {"CUSTOMS_MAX_SITUATION_CHARS": "10"},
     "situation": "example:Meeting my partner's parents in Lagos", "expect": "refused before any model call"},
    {"limit": "tool calls per run = 1", "env": {"CUSTOMS_MAX_TOOL_CALLS": "1"},
     "situation": "Business dinner with my client's boss in Seoul", "expect": "run stops gracefully with a message"},
    {"limit": "model requests per run = 1", "env": {"CUSTOMS_MAX_MODEL_REQUESTS": "1"},
     "situation": "Attending a wedding in India", "expect": "run stops gracefully with a message"},
]


def log_entries() -> list:
    return json.loads(LOG.read_text()) if LOG.exists() else []


def wait_up(timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(URL, timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        for case in CASES:
            env = {**os.environ, **case["env"]}
            server = subprocess.Popen([str(PY), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
                                      cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                assert wait_up(), "test server did not start"
                before = log_entries()
                page = browser.new_page(viewport={"width": 1280, "height": 900})
                page.goto(URL)
                page.wait_for_selector(".country")
                with page.expect_response("**/api/coach", timeout=240_000) as info:
                    if case["situation"].startswith("example:"):  # examples bypass the box's maxlength, like a paste would
                        page.get_by_role("button", name=case["situation"].split(":", 1)[1]).click()
                    else:
                        page.fill("#situation", case["situation"])
                        page.click("#go")
                resp = info.value
                body = resp.json()
                page.wait_for_selector("#error:not([hidden])", timeout=10_000)
                shown = page.inner_text("#error").strip()
                visa_bubble = page.locator("#error .visa-says").count() > 0
                after = log_entries()
                new = after[len(before):]
                model_calls = sum((e.get("tokens") or {}).get("requests", 0) for e in new)
                res = {**case, "status": resp.status, "message_on_page": shown, "visa_bubble": visa_bubble,
                       "new_log_entries": [{"outcome": e.get("outcome"), "requests": (e.get("tokens") or {}).get("requests"),
                                            "cost_usd": e.get("cost_usd")} for e in new],
                       "model_requests_made": model_calls,
                       "usage_reported": body.get("usage")}
                if case["expect"].startswith("refused"):
                    res["pass"] = resp.status in (400, 429) and visa_bubble and model_calls == 0
                else:
                    res["pass"] = resp.status == 422 and visa_bubble and bool(new) and "looking-up" in shown
                results.append(res)
                print(f"{'PASS' if res['pass'] else 'FAIL'} {case['limit']}: HTTP {resp.status}, model requests "
                      f"{model_calls}, page: {shown[:110]!r}", flush=True)
                page.close()
            finally:
                server.terminate()  # the exact process this test started
                server.wait(timeout=10)
        browser.close()
    (ROOT / "tests" / "limits_test.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print("all passed:", all(r["pass"] for r in results))


if __name__ == "__main__":
    sys.exit(main())
